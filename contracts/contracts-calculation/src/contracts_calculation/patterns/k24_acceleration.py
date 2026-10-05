"""K24 期限の利益の喪失（判定）：当然に失う事由と、請求により失う事由。"""

from __future__ import annotations

from .base import PatternDef, RuleDraft, op, step, var


def _sample(ctx, rng) -> RuleDraft:
    return RuleDraft(
        pattern_id="K24",
        rule_id="acceleration_triggered",
        function="acceleration_triggered",
        title="期限の利益の喪失",
        kind="determination",
        inputs={
            "insolvency_event": {
                "type": "bool",
                "origin": "judgment",
                "desc": "支払停止または破産等の申立てがあったか",
            },
            "attachment_event": {
                "type": "bool",
                "origin": "judgment",
                "desc": "差押えまたは滞納処分を受けたか",
            },
            "covenant_breach": {"type": "bool", "origin": "judgment", "desc": "本契約上の義務違反があるか"},
            "demanded": {"type": "bool", "origin": "notice", "desc": "書面による請求があったか"},
        },
        steps=[
            {
                "name": "automatic",
                "label": "当然喪失の事由",
                "expr": op("or", var("insolvency_event"), var("attachment_event")),
            },
            {
                "name": "on_demand",
                "label": "請求による喪失の要件",
                "expr": op("and", var("covenant_breach"), var("demanded")),
            },
            {
                "name": "accelerated",
                "label": "期限の利益を失うか",
                "expr": op("or", step("automatic"), step("on_demand")),
            },
        ],
        output={"step": "accelerated", "type": "bool"},
        obligations=["forfeiture:two_routes", "demand:written"],
        paragraphs=[
            {
                "text": "次の各号のいずれかに該当するときは、これに該当した当事者は、何らの通知を要せず当然に"
                "期限の利益を失い、未払の債務を直ちに支払う。",
                "items": [
                    "支払の停止、または破産手続開始その他これに類する申立てがあったとき",
                    "差押えまたは滞納処分を受けたとき",
                ],
            },
            (
                "当事者の一方に本契約上の義務違反があるときは、相手方は、書面により請求して期限の利益を"
                "失わせることができる。この場合、義務違反と書面による請求の両方があったときに限り、"
                "期限の利益を失う。"
            ),
        ],
        difficulty={"condition": "two_routes", "unknown": True},
    )


PATTERN = PatternDef(
    id="K24",
    title="期限の利益の喪失",
    genres=frozenset({"purchase", "lease", "license", "contracting"}),
    topics=("期限の利益",),
    sampler=_sample,
)
