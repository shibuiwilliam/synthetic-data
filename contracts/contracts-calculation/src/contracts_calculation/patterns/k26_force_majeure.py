"""K26 不可抗力による免責（判定）：事由に当たり、期限内に通知した。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, fw, op, param, step, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K26")
    days = rng.choice(v["notice_days"])
    ds = ctx.digit_style
    n_days = ctx.free_const_name("fm_notice_days")
    return RuleDraft(
        pattern_id="K26",
        rule_id="force_majeure_exempt",
        function="force_majeure_exempt",
        title="不可抗力",
        kind="determination",
        params={n_days: ParamDraft(n_days, "int", fw(f"{days}日", ds), value=days, unit="DAY")},
        inputs={
            "force_event": {
                "type": "bool",
                "origin": "judgment",
                "desc": "天災地変その他の不可抗力に当たる事由か",
            },
            "event_date": {
                "type": "date",
                "origin": "fact",
                "min": "2026-01-01",
                "max": "2032-12-31",
                "desc": "不可抗力の事由が生じた日",
            },
            "notice_date": {
                "type": "date",
                "origin": "notice",
                "min": "2026-01-01",
                "max": "2033-12-31",
                "desc": "相手方への通知が到達した日",
            },
        },
        steps=[
            {
                "name": "notified_in_time",
                "label": "期限内に通知したか",
                "expr": op(
                    "and",
                    op("ge", op("days_between", var("event_date"), var("notice_date")), {"lit": 0}),
                    op("le", op("days_between", var("event_date"), var("notice_date")), param(n_days)),
                ),
            },
            {
                "name": "exempt",
                "label": "免責されるか",
                "expr": op("and", var("force_event"), step("notified_in_time")),
            },
        ],
        output={"step": "exempt", "type": "bool"},
        obligations=[
            "force_majeure:enumerated",
            "notice_deadline:days_from_event",
            "day_count:from_event_date",
            "notice:arrival_basis",
        ],
        paragraphs=[
            (
                "天災地変、戦争、感染症のまん延その他の不可抗力により義務の履行が遅れ、または不能となった"
                "ときは、その当事者は、責任を負わない。"
            ),
            (
                f"前項の免責は、不可抗力の事由が生じた日から{{const:{n_days}}}以内に、その旨の通知が"
                "相手方に到達したときに限り適用する。日数は事由が生じた日の翌日から数える。"
            ),
        ],
        difficulty={"calendar": "days", "condition": "and", "unknown": True},
    )


PATTERN = PatternDef(
    id="K26",
    title="不可抗力による免責",
    genres=frozenset({"outsourcing", "delegation", "sysdev", "purchase", "license", "lease"}),
    topics=("不可抗力",),
    sampler=_sample,
)
