"""K07 日割：月額 × 利用日数 ÷ 分母（当月の日数 または 30日）。"""

from __future__ import annotations

from .base import (
    ParamDraft,
    PatternDef,
    RuleDraft,
    concept,
    fw,
    money,
    op,
    param,
    sentence_rounding,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K07")
    denom = rng.choice(v["denominator"])
    monthly = rng.choice(v["monthly_fee"])
    if denom == "30":
        # 30 の倍数だと丸めの方向が結果に一度も現れず、丸め変異が等価になる（G7 が測れない）
        pool = [m for m in v["monthly_fee"] if m % 30 != 0]
        monthly = rng.choice(pool)
    rounding = rng.choice(v["rounding"])
    ds = ctx.digit_style
    n_fee = ctx.free_const_name("fac_monthly_fee")
    payer, payee = ctx.payer_key, ctx.payee_key
    inputs = {"usage_days": concept("usage_days")}
    params = {n_fee: ParamDraft(n_fee, "int", money(monthly, ds), value=monthly, unit="JPY")}
    if denom == "actual":
        inputs["month_days"] = concept("month_days")
        denom_expr = var("month_days")
        denom_text = "当該月の日数"
    else:
        n_days = ctx.free_const_name("fac_proration_days")
        params[n_days] = ParamDraft(n_days, "int", fw("30日", ds), value=30, unit="DAY")
        denom_expr = param(n_days)
        denom_text = f"{{const:{n_days}}}"
    return RuleDraft(
        pattern_id="K07",
        rule_id="facility_fee_prorated",
        function="facility_fee_prorated",
        title="設備利用料",
        kind="calculation",
        params=params,
        inputs=inputs,
        steps=[
            {
                "name": "fee",
                "label": "日割後の設備利用料",
                "expr": op("muldiv", param(n_fee), var("usage_days"), denom_expr, rounding=rounding),
            },
        ],
        output={"step": "fee", "type": "int", "unit": "JPY"},
        obligations=[
            f"proration_basis:{'actual_days' if denom == 'actual' else '30days'}",
            f"rounding:{rounding}_1yen",
        ],
        paragraphs=[
            f"{{party:{payer}}}は、設備利用料として、月額{{const:{n_fee}}}を{{party:{payee}}}に支払う。",
            f"利用が月の全部に満たない月の設備利用料は、{denom_text}に対する利用日数の割合を月額に乗じて算出する。"
            + sentence_rounding(rounding, ds),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        header_option=(
            {
                "param": n_fee,
                "title": "設備利用料（月額）",
                "body_paragraphs": [
                    (
                        f"{{party:{payer}}}は、設備利用料として、{{ref:{ctx.head_matter_id}}}に定める月額を"
                        f"{{party:{payee}}}に支払う。"
                    ),
                    f"利用が月の全部に満たない月の設備利用料は、{denom_text}に対する利用日数の割合を月額に乗じて算出する。"
                    + sentence_rounding(rounding, ds),
                ],
            }
            if ctx.head_matter_id
            else None
        ),
        difficulty={"value_location": "body", "calendar": "days", "depth": 1},
    )


PATTERN = PatternDef(
    id="K07",
    title="日割",
    genres=frozenset({"outsourcing", "delegation", "consulting", "sysdev", "license", "lease"}),
    topics=("設備利用料",),
    sampler=_sample,
)
