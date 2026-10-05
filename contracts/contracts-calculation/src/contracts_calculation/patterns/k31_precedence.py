"""K31 優先順位による解決：本文と別紙に異なる単価を置き、優先順位の条項で別紙が勝つ。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, TableDraft, TableRowDraft, fw, money, op, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K31")
    body_fee = rng.choice(v["body_fee"])
    appendix_fee = body_fee + rng.choice([d for d in v["appendix_delta"] if body_fee + d > 0])
    ds = ctx.digit_style
    n_body = ctx.free_const_name("inspect_fee_body")
    payer, payee = ctx.payer_key, ctx.payee_key
    table = TableDraft(
        name="inspect_fee_table",
        caption="検査手数料の単価",
        semantic_type="rate",
        col_labels=("区分", fw("1件あたりの単価", ds)),
        rows=[TableRowDraft(fw("検査1件につき", ds), None, appendix_fee, money(appendix_fee, ds))],
    )
    return RuleDraft(
        pattern_id="K31",
        rule_id="inspection_fee",
        function="inspection_fee",
        title="検査手数料",
        kind="calculation",
        params={n_body: ParamDraft(n_body, "int", money(body_fee, ds), value=body_fee, unit="JPY")},
        tables={"inspect_fee_table": table},
        inputs={
            "inspection_count": {
                "type": "int",
                "unit": "COUNT",
                "origin": "fact",
                "min": 0,
                "max": 1000,
                "desc": "当月の検査の件数",
            }
        },
        steps=[
            {
                "name": "fee",
                "label": "検査手数料",
                "expr": op("tiered", var("inspection_count"), table="inspect_fee_table", method="all_units"),
            },
        ],
        output={"step": "fee", "type": "int", "unit": "JPY"},
        obligations=["priority:appendix_over_body", "tier_method:all_units"],
        paragraphs=[
            f"{{party:{payer}}}は、検査手数料として、検査{fw('1件', ds)}につき{{const:{n_body}}}を"
            f"{{party:{payee}}}に支払う。ただし、別紙に異なる定めがあるときは、別紙の定めによる。"
            "単価の表は" + "{TBL:inspect_fee_table}" + "による。"
            "検査手数料は、適用される単価に当月の全件数を乗じて算出する。",
        ],
        force_appendix=True,
        literal_surfaces=[fw("1件", ds)],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"priority": "appendix_over_body", "depth": 1, "distractor": "body_value"},
    )


PATTERN = PatternDef(
    id="K31",
    title="優先順位による解決",
    genres=frozenset({"outsourcing", "delegation", "sysdev", "purchase"}),
    topics=("検査手数料",),
    sampler=_sample,
)
