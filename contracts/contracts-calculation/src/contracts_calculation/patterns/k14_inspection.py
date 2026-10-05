"""K14 検査期限とみなし合格：納入日の翌日から N 営業日以内。通知がなければ合格とみなす。"""

from __future__ import annotations

from .base import (
    ParamDraft,
    PatternDef,
    RuleDraft,
    calendar_def_paragraph,
    concept,
    fw,
    op,
    param,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K14")
    bdays = rng.choice(v["inspect_bdays"])
    ds = ctx.digit_style
    n_days = ctx.free_const_name("deliv_inspect_bdays")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K14",
        rule_id="deliverable_inspect_deadline",
        function="deliverable_inspect_deadline",
        title="成果物の検査",
        kind="calculation",
        params={n_days: ParamDraft(n_days, "int", fw(f"{bdays}営業日", ds), value=bdays, unit="DAY")},
        inputs={"delivery_date": concept("delivery_date")},
        steps=[
            {
                "name": "deadline",
                "label": "検査の期限",
                "expr": op("add_business_days", var("delivery_date"), param(n_days)),
            },
        ],
        output={"step": "deadline", "type": "date"},
        obligations=[
            "business_days:defined_in_article",
            "day_count:from_next_day",
            "deemed:at_period_expiry",
        ],
        paragraphs=[
            (
                f"{{party:{payer}}}は、成果物の引渡しを受けた日の翌日から起算して{{const:{n_days}}}以内に"
                f"検査を行い、その結果を書面により{{party:{payee}}}に通知する。"
            ),
            "前項の期間内に通知を発しないときは、その期間の満了の時に検査に合格したものとみなす。",
            calendar_def_paragraph(ds),
        ],
        needs_calendar=True,
        difficulty={"calendar": "business_days", "depth": 1},
    )


PATTERN = PatternDef(
    id="K14",
    title="検査期限とみなし合格",
    genres=frozenset({"delegation", "consulting"}),
    topics=("検査", "検収"),
    sampler=_sample,
)
