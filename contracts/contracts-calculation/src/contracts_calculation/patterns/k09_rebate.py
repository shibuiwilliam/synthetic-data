"""K09 割戻し：年間取引額に応じた割戻率の表（lookup、階段）。"""

from __future__ import annotations

from .base import (
    PatternDef,
    RuleDraft,
    TableDraft,
    TableRowDraft,
    concept,
    fw,
    lit,
    money,
    op,
    pct_surface,
    sentence_rounding,
    step,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K09")
    u1 = rng.choice(v["tier1_upto"])
    u2 = u1 * rng.choice(v["width_mult"])
    r1 = rng.choice(v["rate1_permille"])
    stp = rng.choice(v["rate_step"])
    r2, r3 = r1 + stp, r1 + 2 * stp
    ds = ctx.digit_style
    rows = [
        TableRowDraft(
            fw(f"{money(u1, 'halfwidth')}以下", ds).replace("円以下", "円以下"), u1, r1, pct_surface(r1, ds)
        ),
        TableRowDraft(
            fw(f"{money(u1, 'halfwidth')}を超え{money(u2, 'halfwidth')}以下", ds), u2, r2, pct_surface(r2, ds)
        ),
        TableRowDraft(fw(f"{money(u2, 'halfwidth')}を超えるとき", ds), None, r3, pct_surface(r3, ds)),
    ]
    table = TableDraft(
        name="rebate_table",
        caption="割戻率",
        semantic_type="rate",
        col_labels=("年間の取引額", "割戻率"),
        rows=rows,
        unit="PERMILLE",
    )
    payer, payee = ctx.payee_key, ctx.payer_key  # 割戻しは受け取る側（売主）が支払う
    return RuleDraft(
        pattern_id="K09",
        rule_id="annual_rebate",
        function="annual_rebate",
        title="割戻金",
        kind="calculation",
        tables={"rebate_table": table},
        inputs={"annual_amount": concept("annual_amount")},
        steps=[
            {
                "name": "rate_permille",
                "label": "割戻率（千分率）",
                "expr": op("lookup", var("annual_amount"), table="rebate_table", mode="step"),
            },
            {
                "name": "rebate",
                "label": "割戻金の額",
                "expr": op(
                    "muldiv", var("annual_amount"), step("rate_permille"), lit(1000), rounding="floor"
                ),
            },
        ],
        output={"step": "rebate", "type": "int", "unit": "JPY"},
        obligations=["rebate:rate_by_annual_amount", "rounding:floor_1yen", "tier_boundary:inclusive_lower"],
        paragraphs=[
            f"{{party:{payer}}}は、{{party:{payee}}}の年間の取引額に応じ、{{TBL:rebate_table}}の割戻率を"
            "年間の取引額に乗じた額を割戻金として支払う。区分の境界にあたる額は、その額を含む下位の区分による。"
            + sentence_rounding("floor", ds),
        ],
        table_paragraph=0,
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"value_location": "body_table", "depth": 2},
    )


PATTERN = PatternDef(
    id="K09",
    title="割戻し",
    genres=frozenset({"purchase"}),
    topics=("割戻",),
    sampler=_sample,
)
