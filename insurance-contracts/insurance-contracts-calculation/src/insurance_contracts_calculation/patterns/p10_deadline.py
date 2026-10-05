"""P10 期限・期間。`日付 + N日`（初日算入か翌日起算かを文で明示する）"""

from __future__ import annotations

import datetime as dt
import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import P, PatternBase, RuleDraft, StepDraft, V, op


class P10Deadline(PatternBase):
    id = "P10"
    title = "期限・期間"
    needs_inputs = ("base_date",)
    needs_params = ("payment_days",)

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        days = self.const(ctx, subject, "payment_days", rng)
        base_arg, base_spec = self.input_of(ctx, subject, "base_date")
        fn = self.func(subject, "deadline")
        first_day_included = rng.random() < 0.5
        # 初日算入なら「その日を含めて N 日」＝ 起算日 + (N−1) 日が満了日
        offset = op("sub", P(days.name), {"lit": 1, "unit": "DAY", "note": "初日を算入して数える"})
        steps = [
            StepDraft(
                fn,
                op("add_days", V(base_arg), offset if first_day_included else P(days.name)),
                "sentence",
                {
                    "shape": "deadline",
                    "first_day_included": first_day_included,
                    "effect": ctx.pack.word("deadline_effect", subject),
                    "label": "支払の期限となる日",
                },
            )
        ]
        return [
            RuleDraft(
                pattern=self.id,
                subject_key=subject.key,
                rule_id=self.rule_id(subject, "deadline"),
                function=fn,
                title=f"{subject.benefit}となる日",
                kind="calculation",
                benefit=subject.benefit,
                trigger=subject.trigger,
                steps=steps,
                inputs={base_arg: base_spec},
                output={"step": fn, "type": "date"},
                consts=[days],
                obligations=["period:first_day_included" if first_day_included else "period:next_day_start"],
                properties=[],
                example_sets=[
                    [{base_arg: d}]
                    for d in (
                        dt.date(2026, 2, 26),
                        dt.date(2026, 3, 30),
                        dt.date(2026, 5, 15),
                        dt.date(2026, 7, 9),
                    )
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"time": True},
            )
        ]
