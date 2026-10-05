"""K03・K04 で共有する段階表の抽選と文書化。"""

from __future__ import annotations

from .base import RuleDraft, TableDraft, TableRowDraft, concept, fw, money, op, values_of, var


def sample_tiered(ctx, rng, method: str) -> RuleDraft:
    v = values_of("K03K04")
    u1 = rng.choice(v["tier1_upto"])
    u2 = u1 * rng.choice(v["tier_width_mult"])
    p1 = rng.choice(v["tier1_price"])
    stp = rng.choice(v["price_step"])
    while p1 - 2 * stp <= 0:
        stp //= 2
        if stp == 0:
            stp = 50 if p1 > 100 else 10
            break
    p2, p3 = p1 - stp, p1 - 2 * stp
    ds = ctx.digit_style
    rows = [
        TableRowDraft(fw(f"1件以上{u1}件以下", ds), u1, p1, money(p1, ds)),
        TableRowDraft(fw(f"{u1 + 1}件以上{u2}件以下", ds), u2, p2, money(p2, ds)),
        TableRowDraft(fw(f"{u2 + 1}件以上", ds), None, p3, money(p3, ds)),
    ]
    table = TableDraft(
        name="case_fee_table",
        caption="処理手数料の単価",
        semantic_type="rate",
        col_labels=("当月の処理件数", fw("1件あたりの単価", ds)),
        rows=rows,
    )
    payer, payee = ctx.payer_key, ctx.payee_key
    if method == "all_units":
        how = "{TBL:case_fee_table}の区分に応じた単価を当月の全件数に乗じて得た額"
        rule_id = "case_fee_all_units"
        obligation = "tier_method:all_units"
    else:
        how = "{TBL:case_fee_table}の各区分に属する件数に当該区分の単価を乗じて得た額の合計"
        rule_id = "case_fee_marginal"
        obligation = "tier_method:marginal"
    return RuleDraft(
        pattern_id="K03" if method == "all_units" else "K04",
        rule_id=rule_id,
        function=rule_id,
        title="処理手数料",
        kind="calculation",
        tables={"case_fee_table": table},
        inputs={"case_count": concept("case_count")},
        steps=[
            {
                "name": "fee",
                "label": "処理手数料",
                "expr": op("tiered", var("case_count"), table="case_fee_table", method=method),
            },
        ],
        output={"step": "fee", "type": "int", "unit": "JPY"},
        obligations=[obligation, "tier_boundary:inclusive_lower"],
        paragraphs=[
            (
                f"{{party:{payer}}}は、処理手数料として、当月の処理件数に応じ、{how}を{{party:{payee}}}に支払う。"
                "区分の境界にあたる件数は、その件数を含む下位の区分による。"
            ),
        ],
        table_paragraph=0,
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"value_location": "body_table", "depth": 1},
    )
