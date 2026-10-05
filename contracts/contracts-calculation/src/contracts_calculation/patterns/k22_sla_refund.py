"""K22 サービスレベルの返金：稼働率の段階に応じた定額の返金（割合比較は乗算で行う）。"""

from __future__ import annotations

from .base import (
    ParamDraft,
    PatternDef,
    RuleDraft,
    concept,
    lit,
    money,
    op,
    pct_surface,
    step,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K22")
    monthly = rng.choice(v["monthly_fee"])
    mid_pct = rng.choice(v["refund_mid_pct"])
    low_pct = rng.choice([x for x in v["refund_low_pct"] if x > mid_pct])
    refund_mid = monthly * mid_pct // 100
    refund_low = monthly * low_pct // 100
    ds = ctx.digit_style
    n_high = ctx.free_const_name("sla_high")
    n_low = ctx.free_const_name("sla_low")
    n_mid = ctx.free_const_name("sla_refund_mid")
    n_lowr = ctx.free_const_name("sla_refund_low")
    provider, customer = ctx.payee_key, ctx.payer_key
    # しきい値を正確に踏む入力（対象時間 43,000 分 = 総時間 43,200 − 計画停止 200）
    target = 43_000
    up_high = target * 999 // 1000
    up_low = target * 990 // 1000
    hints = [
        {"month_minutes": 43_200, "planned_stop": 200, "downtime": target - up_high},
        {"month_minutes": 43_200, "planned_stop": 200, "downtime": target - up_high + 1},
        {"month_minutes": 43_200, "planned_stop": 200, "downtime": target - up_low},
        {"month_minutes": 43_200, "planned_stop": 200, "downtime": target - up_low + 1},
        {"month_minutes": 43_200, "planned_stop": 200, "downtime": target - up_low - 1},
    ]
    return RuleDraft(
        pattern_id="K22",
        rule_id="sla_refund",
        function="sla_refund",
        title="サービスレベルと返金",
        kind="calculation",
        params={
            n_high: ParamDraft(n_high, "int", pct_surface(999, ds), value=999, unit="PERMILLE"),
            n_low: ParamDraft(n_low, "int", pct_surface(990, ds), value=990, unit="PERMILLE"),
            n_mid: ParamDraft(n_mid, "int", money(refund_mid, ds), value=refund_mid, unit="JPY"),
            n_lowr: ParamDraft(n_lowr, "int", money(refund_low, ds), value=refund_low, unit="JPY"),
        },
        inputs={
            "month_minutes": concept("month_minutes"),
            "planned_stop": concept("planned_stop"),
            "downtime": concept("downtime"),
        },
        steps=[
            {
                "name": "target",
                "label": "対象時間",
                "expr": op("sub", var("month_minutes"), var("planned_stop")),
            },
            {
                "name": "uptime",
                "label": "稼働時間",
                "expr": op("max", lit(0), op("sub", step("target"), var("downtime"))),
            },
            {
                "name": "ok_high",
                "label": "基準稼働率以上か",
                "expr": op(
                    "ge", op("mul", step("uptime"), lit(1000)), op("mul", param(n_high), step("target"))
                ),
            },
            {
                "name": "ok_low",
                "label": "下限稼働率以上か",
                "expr": op(
                    "ge", op("mul", step("uptime"), lit(1000)), op("mul", param(n_low), step("target"))
                ),
            },
            {
                "name": "refund",
                "label": "返金額",
                "expr": op(
                    "if", step("ok_high"), lit(0), op("if", step("ok_low"), param(n_mid), param(n_lowr))
                ),
            },
        ],
        output={"step": "refund", "type": "int", "unit": "JPY"},
        obligations=["uptime:planned_stop_excluded_both", "ratio_compare:by_multiplication"],
        paragraphs=[
            (
                f"{{party:{provider}}}は、本サービスの稼働率を維持する。稼働率は、当月の総時間から計画停止の"
                "時間を除いた時間（対象時間）に対する稼働時間の割合とする。計画停止の時間は、分母および分子の"
                "双方から除く。割合の判定は、割り算によらず乗算により行う。"
            ),
            (
                f"稼働率が{{const:{n_high}}}以上の月は、返金を行わない。これに満たない月は、"
                f"{{party:{provider}}}は{{party:{customer}}}に{{const:{n_mid}}}を返金する。ただし、"
                f"稼働率が{{const:{n_low}}}に満たない月の返金額は、{{const:{n_lowr}}}とする。"
            ),
        ],
        parties={"payer": ctx.alias(provider), "payee": ctx.alias(customer)},
        case_hints=hints,
        difficulty={"depth": 4, "condition": "tiers"},
    )


def param(n: str) -> dict:
    return {"param": n}


PATTERN = PatternDef(
    id="K22",
    title="サービスレベルの返金",
    genres=frozenset({"sysdev", "outsourcing"}),
    topics=("稼働率",),
    sampler=_sample,
)
