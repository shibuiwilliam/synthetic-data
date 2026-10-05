"""P02 免責金額と限度額。`min(max(0, x − D), L)`（適用順を文で明示する）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import LIT, P, PatternBase, RuleDraft, S, StepDraft, V, op


class P02Deductible(PatternBase):
    id = "P02"
    title = "免責金額と限度額"
    needs_inputs = ("amount",)
    needs_params = ("deductible", "limit")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        arg, spec = self.input_of(ctx, subject, "amount")
        inside = self.inside(spec)
        ded = self.const(ctx, subject, "deductible", rng, **inside)
        limit = self.const(ctx, subject, "limit", rng, above=max(ded.value, inside.get("above", 0)))
        fn = self.func(subject, "payout")
        steps = [
            StepDraft("after_deductible", op("sub", V(arg), P(ded.name)), "core", {"shape": "sub"}),
            StepDraft("capped", op("min", S("after_deductible"), P(limit.name)), "qualify", {"shape": "cap"}),
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
                inputs={arg: {**spec, "max": max(spec.get("max", 0), limit.value * 3)}},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[ded, limit],
                obligations=["order:deductible_then_limit", "floor:zero"],
                properties=[
                    {"type": "range", "min": 0, "max_param": limit.name},
                    {"type": "monotone", "input": arg, "dir": "+"},
                ],
                example_sets=[
                    [{arg: ded.value + 50_000}, {arg: limit.value + ded.value + 30_000}],
                    [{arg: ded.value + 60_000}, {arg: limit.value + ded.value + 40_000}],
                    [{arg: ded.value + 70_000}, {arg: limit.value + ded.value + 70_000}],
                    [{arg: ded.value + 80_000}, {arg: limit.value + ded.value + 90_000}],
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
            )
        ]
