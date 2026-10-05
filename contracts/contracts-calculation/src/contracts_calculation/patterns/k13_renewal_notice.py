"""K13 更新と通知期限：満了日の N か月前までに通知がなければ更新（K12 の保守サポートに付く）。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, lit, op, param, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K13")
    months = rng.choice(v["notice_months"])
    ds = ctx.digit_style
    n_months = ctx.free_const_name("support_notice_months")
    return RuleDraft(
        pattern_id="K13",
        rule_id="support_renewal_notice_deadline",
        function="support_renewal_notice_deadline",
        title="保守サポートの更新",
        kind="calculation",
        params={n_months: ParamDraft(n_months, "int", fw(f"{months}か月", ds), value=months, unit="MONTH")},
        inputs={"expiry_date": concept("expiry_date")},
        steps=[
            {
                "name": "notify_by",
                "label": "更新しない旨の通知の期限",
                "expr": op("add_months", var("expiry_date"), op("sub", lit(0), param(n_months))),
            },
        ],
        output={"step": "notify_by", "type": "date"},
        obligations=["period_count:anniversary", "notice:arrival_basis"],
        paragraphs=[
            (
                f"保守サポートの提供期間は、その満了日の{{const:{n_months}}}前までに、"
                "いずれかの当事者から書面による更新しない旨の通知が相手方に到達しないときは、"
                "同一の条件で同一の期間更新され、以後も同様とする。通知の期限は、満了日の当該期間前の"
                "応当日とし、その日を含む。応当する日がない月は、"
                "その月の末日を期限とする。"
            ),
        ],
        difficulty={"calendar": "months", "depth": 1},
    )


PATTERN = PatternDef(
    id="K13",
    title="更新と通知期限",
    genres=frozenset({"outsourcing", "delegation", "sysdev", "purchase", "license"}),
    topics=("保守サポートの更新",),
    sampler=_sample,
)
