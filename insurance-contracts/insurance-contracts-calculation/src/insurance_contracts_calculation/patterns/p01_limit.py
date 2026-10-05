"""P01 実費と限度額。`min(x, L)`"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import P, PatternBase, RuleDraft, S, StepDraft, V, op


class P01Limit(PatternBase):
    id = "P01"
    title = "実費と限度額"
    needs_inputs = ("amount",)
    needs_params = ("limit",)

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        arg, spec = self.input_of(ctx, subject, "amount")
        limit = self.const(ctx, subject, "limit", rng, **self.inside(spec))
        fn = self.func(subject, "payout")
        # 文型の変種: 1 文で「いずれか低い額」か、2 文で「ただし、…を限度とします。」
        one_sentence = rng.random() < 0.5
        if one_sentence:
            steps = [StepDraft(fn, op("min", V(arg), P(limit.name)), "core", {"shape": "min"})]
        else:
            steps = [
                StepDraft("actual", V(arg), "core", {"shape": "identity"}),
                StepDraft(fn, op("min", S("actual"), P(limit.name)), "qualify", {"shape": "cap"}),
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
                consts=[limit],
                obligations=["limit"],
                properties=[
                    {"type": "range", "min": 0, "max_param": limit.name},
                    {"type": "monotone", "input": arg, "dir": "+"},
                ],
                example_sets=[
                    [{arg: limit.value // 2}, {arg: limit.value + 20_000}],
                    [{arg: limit.value // 2 + 3_000}, {arg: limit.value + 50_000}],
                    [{arg: limit.value // 4 * 3}, {arg: limit.value * 2}],
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
            )
        ]
