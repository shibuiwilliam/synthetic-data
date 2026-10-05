"""P04 等級表の割合×金額。`A × 割合(等級) ÷ 100`（一致で引く別表）"""

from __future__ import annotations

import random

from ..core import numbers_ja as nj
from ..core.packs import Subject
from ..planning.context import Context
from .base import LIT, P, PatternBase, RuleDraft, S, StepDraft, TableDraft, V, op


class P04GradeTable(PatternBase):
    id = "P04"
    title = "等級表の割合×金額"
    needs_inputs = ("amount", "grade")
    needs_params = ("round_unit",)

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        amount_arg, amount_spec = self.input_of(ctx, subject, "amount")
        grade_arg, grade_spec = self.input_of(ctx, subject, "grade")
        lo, hi = int(grade_spec.get("min", 1)), int(grade_spec.get("max", 5))
        grades = list(range(lo, hi + 1))
        rates = self.safe_rates(
            ctx,
            [
                _descending(top, len(grades), step)
                for top in (100, 80, 90)
                for step in ([10, 15, 20] if len(grades) <= 5 else [5, 10])
            ],
        )
        round_unit = self.const(ctx, subject, "round_unit", rng)
        fn = self.func(subject, "payout")
        grade_name = ctx.pack.word("grade_name", subject)
        rate_name = ctx.pack.word("rate_name", subject)
        table = TableDraft(
            name=f"{subject.key}_rate",
            semantic_type="grade_schedule",
            key_header=grade_name,
            value_header=rate_name,
            keys=grades,
            values=rates,
            key_surfaces=[f"第{g}級" for g in grades],
            value_surfaces=[nj.pct(r) for r in rates],
            mode="exact",
            key_parse="ordinal",
            value_parse="percent",
            key_unit="GRADE",
            value_unit="1",
            orientation="rows",
            caption=f"{grade_name}に応じる{rate_name}",
        )
        steps = [
            StepDraft(
                "rate",
                op("lookup", V(grade_arg), table=table.name),
                "core",
                {"shape": "lookup", "key_phrase": grade_name, "value_name": rate_name, "no_formula": True},
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
                {"shape": "table_rate", "key_phrase": grade_name, "rate_name": rate_name},
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
                inputs={amount_arg: amount_spec, grade_arg: {**grade_spec, "min": lo, "max": hi}},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[round_unit],
                obligations=["order:rate_then_rounding", "rounding:floor"],
                properties=[{"type": "range", "min": 0, "max_var": amount_arg}],
                table=table,
                example_sets=[
                    [{amount_arg: self.nice_amount(amount_spec, k), grade_arg: grades[len(grades) // 2]}]
                    for k in (0, 1, 2, 3)
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"table_lookup": "exact"},
            )
        ]


def _descending(top: int, n: int, step: int) -> list[int]:
    """単調に下がる割合の列（等級が重いほど高い）。重複が出る刻みは使わない。"""
    out = [max(5, top - i * step) for i in range(n)]
    return out if len(set(out)) == len(out) else [max(5, top - i * 5) for i in range(n)]
