"""P07 場合分け。`if 条件 then A else B`（しきい値の境界を文で明示する）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import P, PatternBase, RuleDraft, StepDraft, V, op


class P07Cases(PatternBase):
    id = "P07"
    title = "場合分け"
    needs_inputs = ("amount",)
    needs_params = ("threshold_amount", "limit", "sub_limit")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        arg, spec = self.input_of(ctx, subject, "amount")
        threshold = self.const(ctx, subject, "threshold_amount", rng, **self.inside(spec))
        high = self.const(ctx, subject, "limit", rng, above=threshold.value)
        low = self.const(ctx, subject, "sub_limit", rng, below=high.value)
        fn = self.func(subject, "payout")
        cmp_op = rng.choice(["ge", "gt"])
        steps = [
            StepDraft(
                fn,
                op("if", op(cmp_op, V(arg), P(threshold.name)), P(high.name), P(low.name)),
                "sentence",
                {"shape": "case"},
            )
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
                consts=[threshold, high, low],
                obligations=[f"threshold:{cmp_op}"],
                properties=[{"type": "range", "min": 0, "max_param": high.name}],
                example_sets=[
                    [{arg: threshold.value + 10_000 * k}, {arg: max(0, threshold.value - 10_000 * (k + 1))}]
                    for k in (1, 2, 3, 4)
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"boundaries": 1},
            )
        ]
