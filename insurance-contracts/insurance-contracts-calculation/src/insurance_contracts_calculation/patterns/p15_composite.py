"""P15 合成。複数の項目の合計から免責金額を差し引き、限度額を適用する"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from .base import LIT, P, PatternBase, RuleDraft, S, StepDraft, V, op


class P15Composite(PatternBase):
    id = "P15"
    title = "複数項目の合成"
    needs_inputs = ("amount", "sub_amount")
    needs_params = ("deductible", "limit")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        a_arg, a_spec = self.input_of(ctx, subject, "amount")
        b_arg, b_spec = self.input_of(ctx, subject, "sub_amount")
        inside = self.inside(a_spec)
        ded = self.const(ctx, subject, "deductible", rng, **inside)
        limit = self.const(ctx, subject, "limit", rng, above=ded.value)
        fn = self.func(subject, "payout")
        steps = [
            StepDraft("total", op("add", V(a_arg), V(b_arg)), "core", {"shape": "sum"}),
            StepDraft("after_deductible", op("sub", S("total"), P(ded.name)), "core", {"shape": "sub"}),
            StepDraft("capped", op("min", S("after_deductible"), P(limit.name)), "qualify", {"shape": "cap"}),
            StepDraft(
                fn, op("max", LIT(0), S("capped")), "qualify", {"shape": "floor_zero", "own_paragraph": True}
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
                inputs={a_arg: a_spec, b_arg: b_spec},
                output={"step": fn, "type": "int", "unit": "JPY"},
                consts=[ded, limit],
                obligations=["order:deductible_then_limit", "floor:zero"],
                properties=[{"type": "range", "min": 0, "max_param": limit.name}],
                # 設例は「限度額に届かない例」と「限度額で頭打ちになる例」を 1 つずつにする
                example_sets=[
                    [
                        {
                            a_arg: self._fit(a_spec, limit.value // 2 + 10_000 * k),
                            b_arg: self._fit(b_spec, limit.value // 4),
                        },
                        {
                            a_arg: self._fit(a_spec, limit.value + 10_000 * k),
                            b_arg: self._fit(b_spec, limit.value // 2),
                        },
                    ]
                    for k in (0, 1, 2, 3)
                ],
                vocab=dict(subject.vocab),
                anchor=subject.anchor,
                difficulty={"composite": True},
            )
        ]
