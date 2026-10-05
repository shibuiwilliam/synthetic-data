"""P05 階段表の率×金額＋端数処理。`round_to(A × 率(月数) ÷ 100, u, floor)`"""

from __future__ import annotations

import random

from ..core import numbers_ja as nj
from ..core.packs import Subject
from ..planning.context import Context
from .base import LIT, P, PatternBase, RuleDraft, S, StepDraft, TableDraft, V, op


class P05StepTable(PatternBase):
    id = "P05"
    title = "階段表の率×金額＋端数処理"
    needs_inputs = ("amount", "months", "extra")
    needs_params = ("max_months", "round_unit", "rate_top", "rate_step")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        max_months = self.const(ctx, subject, "max_months", rng)
        round_unit = self.const(ctx, subject, "round_unit", rng)
        keys = self.safe_series(
            ctx,
            [_month_keys(max_months.value, random.Random(f"{subject.key}:{i}")) for i in range(6)],
            lambda v: f"{v}か月",
            "経過月数の区切り",
        )
        tops = ctx.pack.range_of(subject, "rate_top").choices
        steps = ctx.pack.range_of(subject, "rate_step").choices
        order = sorted(((t_, s_) for t_ in tops for s_ in steps), key=lambda ts: rng.random())
        rates = self.safe_rates(ctx, [[max(5, t_ - i * s_) for i in range(len(keys))] for t_, s_ in order])
        amount_arg, amount_spec = self.input_of(ctx, subject, "amount")
        months_arg, months_spec = self.input_of(ctx, subject, "months")
        extra_arg, extra_spec = self.input_of(ctx, subject, "extra")
        fn = self.func(subject, "payout")
        months_name = ctx.pack.word("months_name", subject)
        rate_name = ctx.pack.word("rate_name", subject)
        table = TableDraft(
            name=f"{subject.key}_rate",
            semantic_type="rate",
            key_header=months_name,
            value_header=rate_name,
            keys=keys,
            values=rates,
            key_surfaces=[f"{k}か月まで" for k in keys[:-1]] + [f"{{const:{max_months.name}}}まで"],
            value_surfaces=[nj.pct(r) for r in rates],
            mode="step_le",
            key_parse="upto_month",
            value_parse="percent",
            key_unit="MONTH",
            value_unit="1",
            orientation="header_keys",
            caption=f"{months_name}に応じる{rate_name}",
            monotone="-",
        )
        steps = [
            StepDraft(
                "months_counted",
                op(
                    "add",
                    V(months_arg),
                    op(
                        "if",
                        op("gt", V(extra_arg), LIT(0)),
                        LIT(1, unit="MONTH", note="1か月未満の端日数は1か月として計算する"),
                        LIT(0),
                    ),
                ),
                "core",
                {"shape": "ceil_period", "unit_word": "1か月", "phrase": months_name, "no_formula": True},
            ),
            StepDraft(
                "rate",
                op("lookup", S("months_counted"), table=table.name),
                "core",
                {"shape": "lookup", "key_phrase": months_name, "value_name": rate_name, "no_formula": True},
            ),
            StepDraft(
                "gross",
                op(
                    "muldiv",
                    V(amount_arg),
                    S("rate"),
                    LIT(100, note=f"{rate_name}は百分率で定める"),
                    rounding="floor",
                ),
                "core",
                {"shape": "table_rate", "key_phrase": months_name, "rate_name": rate_name},
            ),
            StepDraft(
                "rounded",
                op("round_to", S("gross"), P(round_unit.name), rounding="floor"),
                "qualify",
                {"shape": "round", "own_paragraph": True},
            ),
            StepDraft(
                fn,
                op("if", op("gt", S("months_counted"), P(max_months.name)), LIT(0), S("rounded")),
                "qualify",
                {"shape": "out_of_range", "key_phrase": months_name},
            ),
        ]
        return [
            RuleDraft(
                pattern=self.id,
                subject_key=subject.key,
                rule_id=self.rule_id(subject, "payout"),
                function=fn,
                title=f"{subject.benefit}の額",
                kind="calculation",
                benefit=subject.benefit,
                trigger=subject.trigger,
                steps=steps,
                inputs={
                    amount_arg: amount_spec,
                    months_arg: {**months_spec, "max": max_months.value + 24},
                    extra_arg: extra_spec,
                },
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[max_months, round_unit],
                obligations=[
                    "ceil_period",
                    "order:rate_then_rounding",
                    "rounding:floor",
                    "table:out_of_range",
                ],
                properties=[
                    {"type": "range", "min": 0, "max_var": amount_arg},
                    {"type": "monotone", "input": months_arg, "dir": "-"},
                ],
                table=table,
                example_sets=[
                    [
                        {
                            amount_arg: self.nice_amount(amount_spec, k) + 45_600,
                            months_arg: keys[0] + 6,
                            extra_arg: 0,
                        }
                    ]
                    for k in (0, 1, 2, 3)
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"table_lookup": "step"},
            )
        ]


def _month_keys(max_months: int, rng: random.Random) -> list[int]:
    """階段の区切り（昇順・きりのよい月数・最後が上限）。"""
    candidates = [k for k in (6, 12, 24, 36, 48) if k < max_months]
    n = rng.choice([2, 3]) if len(candidates) >= 3 else len(candidates)
    return candidates[-n:] + [max_months]
