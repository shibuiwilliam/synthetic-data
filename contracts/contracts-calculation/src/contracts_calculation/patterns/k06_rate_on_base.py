"""K06 料率×基準額：売上 × 料率。最低保証額と上限額つき。"""

from __future__ import annotations

from .base import (
    ParamDraft,
    PatternDef,
    RuleDraft,
    concept,
    lit,
    money,
    op,
    param,
    pct_surface,
    sentence_rounding,
    step,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K06")
    permille = rng.choice(v["rate_permille"])
    min_fee = rng.choice(v["min_fee"])
    cap_fee = min_fee * rng.choice(v["cap_mult"])
    ds = ctx.digit_style
    n_rate = ctx.free_const_name("perf_fee_rate")
    n_min = ctx.free_const_name("perf_min_fee")
    n_cap = ctx.free_const_name("perf_cap_fee")
    payer, payee = ctx.payer_key, ctx.payee_key
    # 下限・上限のクランプが効かない帯（raw が min と cap の間）を正確に踏む売上高。
    # 1000 の倍数にして、丸めの読みに依存しないケースとしても使えるようにする。
    lo_s = min_fee * 1000 // permille // 1000 * 1000
    hi_s = cap_fee * 1000 // permille // 1000 * 1000
    mid_s = (lo_s + hi_s) // 2 // 1000 * 1000
    hints = [
        {"sales_amount": v}
        for v in sorted({lo_s, lo_s + 1000, mid_s, hi_s - 1000, hi_s})
        if 0 <= v <= 1_000_000_000
    ]
    # クランプ帯の内側で ×permille が 1000 で割り切れない売上高を必ず 1 つ入れる
    # （mid_s は 1000 の倍数なので +1 で剰余が permille になる）。丸め方向の変異が
    # 下限・上限に吸収されず、乱数ケースの運に依らず出力の差として現れる。
    if lo_s < mid_s + 1 < hi_s and mid_s + 1 <= 1_000_000_000:
        hints.append({"sales_amount": mid_s + 1})
    return RuleDraft(
        pattern_id="K06",
        rule_id="performance_fee",
        function="performance_fee",
        title="成果連動の手数料",
        kind="calculation",
        params={
            n_rate: ParamDraft(n_rate, "ratio", pct_surface(permille, ds), num=permille, den=1000),
            n_min: ParamDraft(n_min, "int", money(min_fee, ds), value=min_fee, unit="JPY"),
            n_cap: ParamDraft(n_cap, "int", money(cap_fee, ds), value=cap_fee, unit="JPY"),
        },
        inputs={"sales_amount": concept("sales_amount")},
        steps=[
            {
                "name": "raw_fee",
                "label": "料率による手数料",
                "expr": op("muldiv", var("sales_amount"), param(n_rate), lit(1), rounding="floor"),
            },
            {
                "name": "floored",
                "label": "最低保証を適用した額",
                "expr": op("max", step("raw_fee"), param(n_min)),
            },
            {"name": "fee", "label": "成果連動の手数料", "expr": op("min", step("floored"), param(n_cap))},
        ],
        output={"step": "fee", "type": "int", "unit": "JPY"},
        obligations=["rounding:floor_1yen", "floor_then_cap:min_first"],
        paragraphs=[
            f"{{party:{payer}}}は、成果連動の手数料として、対象期間の売上高に{{const:{n_rate}}}を乗じた額を"
            f"{{party:{payee}}}に支払う。" + sentence_rounding("floor", ds),
            (
                f"前項の額は、{{const:{n_min}}}を下回らず、{{const:{n_cap}}}を超えないものとする。"
                "下限と上限は、この順に適用する。"
            ),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        case_hints=hints,
        difficulty={"depth": 3},
    )


PATTERN = PatternDef(
    id="K06",
    title="料率×基準額",
    genres=frozenset({"outsourcing", "consulting", "delegation"}),
    topics=("成果連動",),
    sampler=_sample,
)
