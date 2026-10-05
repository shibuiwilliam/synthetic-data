"""K27 最低購入義務の達成：実績が最低数量以上か。未達のときの補填額。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, lit, money, op, param, step, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K27")
    min_qty = rng.choice(v["min_qty"])
    unit_comp = rng.choice(v["unit_comp"])
    ds = ctx.digit_style
    n_qty = ctx.free_const_name("min_purchase_qty")
    n_comp = ctx.free_const_name("shortfall_unit_comp")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K27",
        rule_id="shortfall_compensation",
        function="shortfall_compensation",
        title="最低購入数量",
        kind="calculation",
        params={
            n_qty: ParamDraft(n_qty, "int", fw(f"{min_qty}個", ds), value=min_qty, unit="COUNT"),
            n_comp: ParamDraft(n_comp, "int", money(unit_comp, ds), value=unit_comp, unit="JPY"),
        },
        inputs={"actual_qty": concept("actual_qty")},
        steps=[
            {
                "name": "shortfall",
                "label": "最低購入数量に不足する数量",
                "expr": op("max", lit(0), op("sub", param(n_qty), var("actual_qty"))),
            },
            {
                "name": "compensation",
                "label": "補填金の額",
                "expr": op("mul", step("shortfall"), param(n_comp)),
            },
        ],
        output={"step": "compensation", "type": "int", "unit": "JPY"},
        obligations=["min_purchase:per_period"],
        paragraphs=[
            (
                f"{{party:{payer}}}は、各年度に{{const:{n_qty}}}以上を購入する。購入数量が最低購入数量を"
                f"下回ったときは、不足する数量{fw('1個', ds)}につき{{const:{n_comp}}}の補填金を"
                f"{{party:{payee}}}に支払う。"
            ),
        ],
        literal_surfaces=[fw("1個", ds)],
        header_option=(
            {
                "param": n_qty,
                "title": "年間の最低購入数量",
                "body_paragraphs": [
                    (
                        f"{{party:{payer}}}は、各年度に{{ref:{ctx.head_matter_id}}}に定める最低購入数量以上を"
                        f"購入する。購入数量がこれを下回ったときは、不足する数量{fw('1個', ds)}につき"
                        f"{{const:{n_comp}}}の補填金を{{party:{payee}}}に支払う。"
                    ),
                ],
            }
            if ctx.head_matter_id
            else None
        ),
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"depth": 2},
    )


PATTERN = PatternDef(
    id="K27",
    title="最低購入義務の達成",
    genres=frozenset({"purchase", "license"}),
    topics=("最低購入",),
    sampler=_sample,
)
