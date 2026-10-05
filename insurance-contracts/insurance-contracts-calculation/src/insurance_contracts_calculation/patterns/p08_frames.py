"""P08 内枠・別枠の限度。

- 内枠: `min(a + min(b, Ls), L)` — 小さい限度額が大きい限度額に含まれる
- 別枠: `min(a, L) + min(b, Ls)` — 小さい限度額は別に支払う

どちらであるかを必ず文にする（DESIGN.md §8.3）。
"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import P, PatternBase, RuleDraft, S, StepDraft, V, op


class P08Frames(PatternBase):
    id = "P08"
    title = "内枠・別枠の限度"
    needs_inputs = ("amount", "sub_amount")
    needs_params = ("limit", "sub_limit")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        arg, spec = self.input_of(ctx, subject, "amount")
        sub_arg, sub_spec = self.input_of(ctx, subject, "sub_amount")
        inside = self.inside(spec)
        limit = self.const(ctx, subject, "limit", rng, **inside)
        sub_limit = self.const(ctx, subject, "sub_limit", rng, below=limit.value)
        fn = self.func(subject, "payout")
        inner = rng.random() < 0.5
        sub_benefit = ctx.pack.word("sub_benefit", subject)

        sub_step = StepDraft(
            "sub_capped",
            op("min", V(sub_arg), P(sub_limit.name)),
            "core",
            {"shape": "limited", "no_formula": True},
        )
        frame_step = StepDraft(
            "frame_note",
            op("min", S("sub_capped"), P(sub_limit.name)),
            "sentence",
            {
                "shape": "frame",
                "inner": inner,
                "small": sub_benefit,
                "big": subject.benefit,
                "label": "枠の取扱い",
            },
        )
        if inner:
            steps = [
                sub_step,
                StepDraft(
                    "total", op("add", V(arg), S("sub_capped")), "core", {"shape": "sum", "no_formula": True}
                ),
                StepDraft(fn, op("min", S("total"), P(limit.name)), "qualify", {"shape": "cap"}),
                frame_step,
            ]
        else:
            steps = [
                sub_step,
                StepDraft(
                    "main_capped",
                    op("min", V(arg), P(limit.name)),
                    "core",
                    {"shape": "limited", "no_formula": True},
                ),
                StepDraft(
                    fn,
                    op("add", S("main_capped"), S("sub_capped")),
                    "core",
                    {"shape": "sum", "no_formula": True},
                ),
                frame_step,
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
                inputs={arg: spec, sub_arg: sub_spec},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[limit, sub_limit],
                obligations=["limit", "frame:inner" if inner else "frame:outer"],
                properties=[{"type": "range", "min": 0}],
                example_sets=[
                    [
                        {
                            arg: self._fit(spec, limit.value // 2 + 10_000 * k),
                            sub_arg: self._fit(sub_spec, sub_limit.value // 2),
                        },
                        {
                            arg: self._fit(spec, limit.value + 10_000 * k),
                            sub_arg: self._fit(sub_spec, sub_limit.value + 10_000),
                        },
                    ]
                    for k in (0, 1, 2, 3)
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"frames": "inner" if inner else "outer"},
            )
        ]
