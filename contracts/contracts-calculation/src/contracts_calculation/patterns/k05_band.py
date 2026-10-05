"""K05 精算幅つき月額：稼働時間が下限未満なら控除、上限超過なら加算。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, lit, money, op, param, step, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K05")
    base_fee = rng.choice(v["base_fee"])
    lower = rng.choice(v["lower_hours"])
    upper = lower + rng.choice(v["band_width"])
    excess = rng.choice(v["excess_rate"])
    deduct = excess + rng.choice(v["deduct_rate_delta"])
    ds = ctx.digit_style
    n_base = ctx.free_const_name("ops_base_fee")
    n_lower = ctx.free_const_name("ops_lower_hours")
    n_upper = ctx.free_const_name("ops_upper_hours")
    n_excess = ctx.free_const_name("ops_excess_rate")
    n_deduct = ctx.free_const_name("ops_deduct_rate")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K05",
        rule_id="ops_support_fee",
        function="ops_support_fee",
        title="運用支援の対価",
        kind="calculation",
        params={
            n_base: ParamDraft(n_base, "int", money(base_fee, ds), value=base_fee, unit="JPY"),
            n_lower: ParamDraft(n_lower, "int", fw(f"{lower}時間", ds), value=lower, unit="HOUR"),
            n_upper: ParamDraft(n_upper, "int", fw(f"{upper}時間", ds), value=upper, unit="HOUR"),
            n_excess: ParamDraft(n_excess, "int", money(excess, ds), value=excess, unit="JPY/HOUR"),
            n_deduct: ParamDraft(n_deduct, "int", money(deduct, ds), value=deduct, unit="JPY/HOUR"),
        },
        inputs={"work_hours": concept("work_hours")},
        steps=[
            {
                "name": "shortage",
                "label": "下限に不足する時間",
                "expr": op("max", lit(0), op("sub", param(n_lower), var("work_hours"))),
            },
            {
                "name": "excess",
                "label": "上限を超える時間",
                "expr": op("max", lit(0), op("sub", var("work_hours"), param(n_upper))),
            },
            {
                "name": "fee_before_floor",
                "label": "下限適用前の精算後の対価",
                "expr": op(
                    "add",
                    op("sub", param(n_base), op("mul", step("shortage"), param(n_deduct))),
                    op("mul", step("excess"), param(n_excess)),
                ),
            },
            {
                "name": "fee",
                "label": "精算後の対価",
                "expr": op("max", lit(0), step("fee_before_floor")),
            },
        ],
        output={"step": "fee", "type": "int", "unit": "JPY"},
        obligations=["band:deduct_below_lower_add_above_upper", "floor_zero:no_negative_fee"],
        paragraphs=[
            f"{{party:{payer}}}は、運用支援の対価として、月額{{const:{n_base}}}を{{party:{payee}}}に支払う。",
            (
                f"当月の稼働時間が{{const:{n_lower}}}に満たないときは不足する時間{fw('1時間', ds)}につき"
                f"{{const:{n_deduct}}}を前項の額から控除し、{{const:{n_upper}}}を超えるときは超える時間"
                f"{fw('1時間', ds)}につき{{const:{n_excess}}}を前項の額に加算する。"
            ),
            f"前項の計算による額が{fw('0円', ds)}を下回るときは、精算後の対価を{fw('0円', ds)}とする。",
        ],
        literal_surfaces=[fw("1時間", ds)],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"value_location": "body", "depth": 3},
    )


PATTERN = PatternDef(
    id="K05",
    title="精算幅つき月額",
    genres=frozenset({"outsourcing", "delegation", "consulting", "sysdev"}),
    topics=("運用支援の対価", "精算幅"),
    sampler=_sample,
)
