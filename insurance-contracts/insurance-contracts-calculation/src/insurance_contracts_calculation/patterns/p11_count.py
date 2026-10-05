"""P11 回数の限度。`日額 × min(回数, 限度回数)`（1 回ごとの定額と通算の回数）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import P, PatternBase, RuleDraft, S, StepDraft, V, op


class P11Count(PatternBase):
    id = "P11"
    title = "回数の限度"
    needs_inputs = ("count",)
    needs_params = ("sub_limit", "max_count")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        arg, spec = self.input_of(ctx, subject, "count")
        each = self.const(ctx, subject, "sub_limit", rng, per="COUNT")
        max_count = self.const(ctx, subject, "max_count", rng, **self.inside(spec))
        fn = self.func(subject, "payout")
        steps = [
            StepDraft(
                "payable_count",
                op("min", V(arg), P(max_count.name)),
                "core",
                {"shape": "limited", "no_formula": True},
            ),
            StepDraft(fn, op("mul", P(each.name), S("payable_count")), "core", {"shape": "mul"}),
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
                inputs={arg: spec},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[each, max_count],
                obligations=["limit", "scope:per_period"],
                properties=[{"type": "range", "min": 0}, {"type": "monotone", "input": arg, "dir": "+"}],
                example_sets=[
                    [{arg: max(1, max_count.value - 1)}, {arg: max_count.value + 1 + k}] for k in (0, 1, 2, 3)
                ],
                vocab={**subject.vocab, "scope_amount": f"{{const:{max_count.name}}}分"},
                anchor=subject.anchor,
                difficulty={"counting": True},
            )
        ]
