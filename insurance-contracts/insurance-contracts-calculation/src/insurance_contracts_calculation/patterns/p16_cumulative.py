"""P16 通算限度。`min(x, 通算限度 − 既払額)`（0 円を下回るときの扱いを明示する）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import LIT, P, PatternBase, RuleDraft, S, StepDraft, V, op


class P16Cumulative(PatternBase):
    id = "P16"
    title = "通算限度"
    needs_inputs = ("amount", "paid")
    needs_params = ("aggregate_limit",)

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        arg, spec = self.input_of(ctx, subject, "amount")
        paid_arg, paid_spec = self.input_of(ctx, subject, "paid")
        total = self.const(ctx, subject, "aggregate_limit", rng)
        fn = self.func(subject, "payout")
        steps = [
            StepDraft("remaining", op("sub", P(total.name), V(paid_arg)), "core", {"shape": "sub"}),
            StepDraft("capped", op("min", V(arg), S("remaining")), "qualify", {"shape": "min"}),
            StepDraft(
                fn,
                op("max", LIT(0), S("capped")),
                "qualify",
                {"shape": "floor_zero", "own_paragraph": True},
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
                inputs={arg: spec, paid_arg: {**paid_spec, "max": total.value}},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[total],
                obligations=["limit", "floor:zero", "scope:per_period"],
                properties=[{"type": "range", "min": 0, "max_param": total.name}],
                example_sets=[
                    [
                        {arg: self.nice_amount(spec, k), paid_arg: total.value - 10_000 * (k + 3)},
                        {arg: self.nice_amount(spec, k), paid_arg: total.value},
                    ]
                    for k in (0, 1, 2, 3)
                ],
                vocab={**subject.vocab, "scope_amount": f"{{const:{total.name}}}"},
                anchor=subject.anchor,
                difficulty={"cumulative": True},
            )
        ]
