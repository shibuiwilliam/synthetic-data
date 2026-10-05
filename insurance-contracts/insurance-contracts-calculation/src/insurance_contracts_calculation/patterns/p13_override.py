"""P13 上書き。保険証券の記載による限度額の差し替え（記載がないときの既定値を明示する）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import P, PatternBase, RuleDraft, S, StepDraft, V, op


class P13Override(PatternBase):
    id = "P13"
    title = "証券の記載による上書き"
    needs_inputs = ("amount", "policy_limit")
    needs_params = ("limit",)

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        arg, spec = self.input_of(ctx, subject, "amount")
        limit_arg, limit_spec = self.input_of(ctx, subject, "policy_limit")
        default = self.const(ctx, subject, "limit", rng, **self.inside(spec))
        fn = self.func(subject, "payout")
        steps = [
            StepDraft("actual", V(arg), "core", {"shape": "identity"}),
            StepDraft(
                "applied_limit",
                op("coalesce", V(limit_arg), P(default.name)),
                "silent",
                {"label": "適用する限度額", "phrase": limit_spec["desc"], "override": True},
            ),
            StepDraft(
                fn,
                op("min", S("actual"), S("applied_limit")),
                "qualify",
                {"shape": "policy_limit", "limit_phrase": limit_spec["desc"], "default": default.name},
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
                inputs={arg: spec, limit_arg: {**limit_spec, "optional": True}},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[default],
                obligations=["default:policy_absent", "limit"],
                properties=[{"type": "range", "min": 0}],
                example_sets=[
                    [
                        {arg: self.nice_amount(spec, k), limit_arg: None},
                        {arg: self.nice_amount(spec, k), limit_arg: default.value // 2},
                    ]
                    for k in (0, 1, 2, 3)
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"override": "policy"},
            )
        ]
