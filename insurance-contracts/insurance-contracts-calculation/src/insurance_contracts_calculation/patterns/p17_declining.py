"""P17 逓減・逓増。経過年数に応じた割合（階段表で引く）"""

from __future__ import annotations

import random

from ..core import numbers_ja as nj
from ..core.packs import Subject
from ..planning.context import Context
from .base import LIT, P, PatternBase, RuleDraft, S, StepDraft, TableDraft, V, op


class P17Declining(PatternBase):
    id = "P17"
    title = "逓減する割合"
    needs_inputs = ("amount", "years")
    needs_params = ("round_unit",)

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        amount_arg, amount_spec = self.input_of(ctx, subject, "amount")
        years_arg, years_spec = self.input_of(ctx, subject, "years")
        round_unit = self.const(ctx, subject, "round_unit", rng)
        keys = self.safe_series(
            ctx,
            [[1, 3, 5, 10], [2, 4, 6, 10], [1, 2, 5, 10], [3, 5, 7, 10], [2, 5, 8, 12]],
            lambda v: f"{v}年",
            "経過年数の区切り",
        )
        rates = self.safe_rates(
            ctx,
            [
                [max(10, top - i * step) for i in range(len(keys))]
                for top in (100, 90, 80)
                for step in (10, 20)
            ],
        )
        fn = self.func(subject, "payout")
        years_name = ctx.pack.word("years_name", subject)
        rate_name = ctx.pack.word("rate_name", subject)
        table = TableDraft(
            name=f"{subject.key}_rate",
            semantic_type="rate",
            key_header=years_name,
            value_header=rate_name,
            keys=keys,
            values=rates,
            key_surfaces=[f"{k}年まで" for k in keys],
            value_surfaces=[nj.pct(r) for r in rates],
            mode="step_le",
            key_parse="upto_year",
            value_parse="percent",
            key_unit="YEAR",
            value_unit="1",
            orientation="rows",
            caption=f"{years_name}に応じる{rate_name}",
            monotone="-",
        )
        steps = [
            StepDraft(
                "rate",
                op("lookup", V(years_arg), table=table.name),
                "core",
                {"shape": "lookup", "key_phrase": years_name, "value_name": rate_name, "no_formula": True},
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
                {"shape": "table_rate", "key_phrase": years_name, "rate_name": rate_name},
            ),
            StepDraft(
                fn,
                op("round_to", S("gross"), P(round_unit.name), rounding="floor"),
                "qualify",
                {"shape": "round", "own_paragraph": True},
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
                inputs={amount_arg: amount_spec, years_arg: {**years_spec, "min": 0, "max": keys[-1]}},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[round_unit],
                obligations=["order:rate_then_rounding", "rounding:floor"],
                properties=[
                    {"type": "range", "min": 0, "max_var": amount_arg},
                    {"type": "monotone", "input": years_arg, "dir": "-"},
                ],
                table=table,
                example_sets=[
                    [{amount_arg: self.nice_amount(amount_spec, k), years_arg: keys[1]}] for k in (0, 1, 2, 3)
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"table_lookup": "step", "time": True},
            )
        ]
