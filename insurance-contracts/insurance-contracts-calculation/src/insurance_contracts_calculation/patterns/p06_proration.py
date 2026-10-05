"""P06 按分。`X × a ÷ b`（分数の算式と端数処理の明示）"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import P, PatternBase, RuleDraft, S, StepDraft, V, op


class P06Proration(PatternBase):
    id = "P06"
    title = "按分"
    needs_inputs = ("amount", "share_num", "share_den")
    needs_params = ("round_unit",)

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        round_unit = self.const(ctx, subject, "round_unit", rng)
        amount_arg, amount_spec = self.input_of(ctx, subject, "amount")
        num_arg, num_spec = self.input_of(ctx, subject, "share_num")
        den_arg, den_spec = self.input_of(ctx, subject, "share_den")
        den_spec = {**den_spec, "min": max(1, int(den_spec.get("min", 0)))}
        fn = self.func(subject, "payout")
        steps = [
            StepDraft(
                "shared",
                op("muldiv", V(amount_arg), V(num_arg), V(den_arg), rounding="floor"),
                "core",
                {"shape": "proration"},
            ),
            StepDraft(
                fn,
                op("round_to", S("shared"), P(round_unit.name), rounding="floor"),
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
                inputs={amount_arg: amount_spec, num_arg: num_spec, den_arg: den_spec},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[round_unit],
                obligations=["proration", "rounding:floor"],
                properties=[{"type": "range", "min": 0}],
                preconditions=[op("le", V(num_arg), V(den_arg))],
                example_sets=[
                    [
                        {
                            amount_arg: self.nice_amount(amount_spec, k),
                            num_arg: self.nice_amount(den_spec, 0) * 3 // 4,
                            den_arg: self.nice_amount(den_spec, 0),
                        }
                    ]
                    for k in (0, 1, 2, 3)
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
            )
        ]
