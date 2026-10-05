"""P03 日額×日数。`r × min(d, M)`（日数の限度を体言の中で明示する）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import P, PatternBase, RuleDraft, S, StepDraft, V, op


class P03PerDiem(PatternBase):
    id = "P03"
    title = "日額×日数"
    needs_inputs = ("days",)
    needs_params = ("daily", "max_days")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        arg, spec = self.input_of(ctx, subject, "days")
        daily = self.const(ctx, subject, "daily", rng, per="DAY")
        max_days = self.const(ctx, subject, "max_days", rng, **self.inside(spec))
        fn = self.func(subject, "payout")
        # 変種: 日数の限度を体言の中（括弧）で示すか、独立した文で示すか
        inline_limit = rng.random() < 0.5
        cap = op("min", V(arg), P(max_days.name))
        if inline_limit:
            steps = [
                StepDraft("payable_days", cap, "core", {"shape": "limited", "no_formula": True}),
                StepDraft(fn, op("mul", P(daily.name), S("payable_days")), "core", {"shape": "mul"}),
            ]
        else:
            steps = [
                StepDraft(
                    "payable_days",
                    cap,
                    "sentence",
                    {"shape": "cap_subject", "subject_phrase": ctx.pack.word("payable_days_name", subject)},
                ),
                StepDraft(fn, op("mul", P(daily.name), S("payable_days")), "core", {"shape": "mul"}),
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
                consts=[daily, max_days],
                obligations=["limit"],
                properties=[{"type": "range", "min": 0}, {"type": "monotone", "input": arg, "dir": "+"}],
                example_sets=[
                    [{arg: max(1, max_days.value // 2)}, {arg: max_days.value + 3}],
                    [{arg: max(1, max_days.value // 2 + 1)}, {arg: max_days.value + 5}],
                    [{arg: max(2, max_days.value // 3)}, {arg: max_days.value + 7}],
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
            )
        ]
