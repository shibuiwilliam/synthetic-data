"""P14 フローチャート判定（図だけに書かれた判定の連鎖）＋ P03 日額×日数。

図が規範で、本文は「下図の手順により判定します」とだけ書く。図を読めないと実装できない。
"""

from __future__ import annotations

import random

from ..core.packs import Subject
from ..planning.context import Context
from ..realize.figures import Decision, FlowSpec
from .base import LIT, FigureDraft, P, PatternBase, R, RuleDraft, S, StepDraft, V, op


class P14Flowchart(PatternBase):
    id = "P14"
    title = "フローチャート判定＋日額×日数"
    needs_inputs = ("immobile", "days", "other_cover")
    needs_params = ("min_days", "daily", "max_days")

    def sample(self, ctx: Context, subject: Subject, rng: random.Random) -> list[RuleDraft]:
        imm_arg, imm_spec = self.input_of(ctx, subject, "immobile")
        days_arg, days_spec = self.input_of(ctx, subject, "days")
        inside = self.inside(days_spec)
        min_days = self.const(ctx, subject, "min_days", rng, **inside)
        daily = self.const(ctx, subject, "daily", rng, per="DAY")
        max_days = self.const(
            ctx,
            subject,
            "max_days",
            rng,
            above=max(min_days.value, inside.get("above", 0)),
            **{k: v for k, v in inside.items() if k != "above"},
        )
        other_arg, other_spec = self.input_of(ctx, subject, "other_cover")
        inputs = {imm_arg: imm_spec, days_arg: days_spec, other_arg: other_spec}

        q_move = ctx.resolve_tokens(ctx.pack.word("q_immobile", subject))
        q_days = ctx.resolve_tokens(
            ctx.pack.word("q_min_days", subject).replace("{days}", f"{{const:{min_days.name}}}")
        )
        q_other = ctx.resolve_tokens(ctx.pack.word("q_other_cover", subject))
        flow = FlowSpec(
            decisions=[
                Decision("n1", q_move, yes_continues=True),
                Decision("n2", q_days, yes_continues=True),
                Decision("n3", q_other, yes_continues=False),
            ],
            start_label=ctx.resolve_tokens(ctx.pack.word("flow_start", subject)),
            pay_label=f"{subject.benefit}を支払う",
            nopay_label=f"{subject.benefit}を支払わない",
            caption=f"{subject.benefit}の支払の判定",
        )
        eligible_fn = self.func(subject, "eligible")
        payout_fn = self.func(subject, "payout")
        eligible = RuleDraft(
            pattern=self.id,
            subject_key=subject.key,
            rule_id=self.rule_id(subject, "eligible"),
            function=eligible_fn,
            title=f"{subject.benefit}の支払の判定",
            kind="decision",
            benefit=subject.benefit,
            trigger="",
            steps=[
                StepDraft(
                    eligible_fn,
                    op(
                        "and",
                        V(imm_arg),
                        op("ge", V(days_arg), P(min_days.name)),
                        op("not", V(other_arg)),
                    ),
                    "decide",
                    {"shape": "decision", "label": f"{subject.benefit}を支払うかどうかの判定"},
                )
            ],
            inputs=inputs,
            output={"step": eligible_fn, "type": "bool"},
            consts=[min_days],
            obligations=["threshold:ge"],
            figure=FigureDraft("flowchart", flow, normative=True),
            vocab={**subject.vocab, "decision_what": f"{subject.benefit}を支払うかどうか"},
            anchor=subject.anchor,
            group=subject.key,
            difficulty={"figure_only": True},
        )
        payout = RuleDraft(
            pattern=self.id,
            subject_key=subject.key,
            rule_id=self.rule_id(subject, "payout"),
            function=payout_fn,
            title=f"{subject.benefit}の額",
            kind="calculation",
            benefit=subject.benefit,
            trigger="",
            steps=[
                StepDraft(
                    "payable_days",
                    op("min", V(days_arg), P(max_days.name)),
                    "core",
                    {"shape": "limited", "no_formula": True},
                ),
                StepDraft("gross", op("mul", P(daily.name), S("payable_days")), "core", {"shape": "mul"}),
                StepDraft(
                    payout_fn,
                    op("if", R(self.rule_id(subject, "eligible")), S("gross"), LIT(0)),
                    "silent",
                    {"label": f"{subject.benefit}の額"},
                ),
            ],
            inputs=inputs,
            output={"step": payout_fn, "type": "int", "unit": "JPY"},
            consts=[daily, max_days],
            obligations=["limit"],
            properties=[{"type": "range", "min": 0}],
            example_sets=[
                [
                    {
                        imm_arg: True,
                        days_arg: min(days_spec.get("max", 60), max_days.value + 2 + k),
                        other_arg: False,
                    },
                    {imm_arg: True, days_arg: max(1, min_days.value - 1), other_arg: False},
                ]
                for k in (0, 1, 2, 3)
            ],
            vocab=dict(subject.vocab),
            anchor=subject.anchor,
            group=subject.key,
            depends=[self.rule_id(subject, "eligible")],
            difficulty={"figure_only": False, "depth": 3},
        )
        return [eligible, payout]
