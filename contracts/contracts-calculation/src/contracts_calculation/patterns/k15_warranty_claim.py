"""K15 保証期間と請求期限：検収日から N か月以内に通知。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, op, param, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K15")
    months = rng.choice(v["warranty_months"])
    ds = ctx.digit_style
    n_months = ctx.free_const_name("parts_warranty_months")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K15",
        rule_id="warranty_claim_deadline",
        function="warranty_claim_deadline",
        title="交換部品の保証",
        kind="calculation",
        params={n_months: ParamDraft(n_months, "int", fw(f"{months}か月", ds), value=months, unit="MONTH")},
        inputs={"acceptance_date": concept("acceptance_date")},
        steps=[
            {
                "name": "claim_deadline",
                "label": "請求の期限",
                "expr": op("add_months", var("acceptance_date"), param(n_months)),
            },
        ],
        output={"step": "claim_deadline", "type": "date"},
        obligations=["warranty:from_acceptance", "period_count:anniversary", "notice:arrival_basis"],
        paragraphs=[
            f"{{party:{payee}}}は、交換部品の品質を、検収の日から{{const:{n_months}}}の間保証する。",
            (
                f"{{party:{payer}}}による保証の請求は、保証期間の満了日までに、書面が相手方に到達する"
                "ことを要する。保証期間の満了日は、検収の日から当該期間後の応当日とする。応当する日が"
                "ない月はその月の末日を満了日とし、満了日当日を含む。"
            ),
        ],
        difficulty={"calendar": "months", "depth": 1},
    )


PATTERN = PatternDef(
    id="K15",
    title="保証期間と請求期限",
    genres=frozenset({"purchase", "contracting"}),
    topics=("交換部品",),
    sampler=_sample,
)
