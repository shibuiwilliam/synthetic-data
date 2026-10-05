"""K20 損害賠償の上限と除外：min(損害額, 直近 N か月の対価)。故意・重過失は上限なし。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, op, step, values_of, var


def _applicable(ctx) -> bool:
    # 「賠償」と「上限」が同じ単位に現れる既定の条項があれば足さない
    for u in ctx.idx.units.values():
        if "賠償" in u.text and "上限" in u.text:
            return False
    return True


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K20")
    months = rng.choice(v["cap_months"])
    ds = ctx.digit_style
    n_months = ctx.free_const_name("liab_cap_months")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K20",
        rule_id="liability_payable",
        function="liability_payable",
        title="損害賠償の限度",
        kind="calculation",
        params={n_months: ParamDraft(n_months, "int", fw(f"{months}か月", ds), value=months, unit="MONTH")},
        inputs={
            "damage_amount": concept("damage_amount"),
            "paid_fees_recent": concept("paid_fees_recent"),
            "willful": concept("willful"),
        },
        steps=[
            {
                "name": "capped",
                "label": "上限を適用した額",
                "expr": op("min", var("damage_amount"), var("paid_fees_recent")),
            },
            {
                "name": "payable",
                "label": "賠償すべき額",
                "expr": op("if", var("willful"), var("damage_amount"), step("capped")),
            },
        ],
        output={"step": "payable", "type": "int", "unit": "JPY"},
        obligations=["cap_period:before_cause_date", "cap_exception:willful_or_gross_negligence"],
        paragraphs=[
            (
                "当事者が本契約に関連して相手方に対して負う損害賠償の責任の総額は、"
                f"損害の原因となった事由が生じた日の前日までの{{const:{n_months}}}間に"
                f"{{party:{payer}}}が{{party:{payee}}}に支払った対価の合計額を限度とする。"
            ),
            "前項は、故意または重大な過失による損害には適用しない。",
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"value_location": "order", "depth": 2, "unknown": True},
    )


PATTERN = PatternDef(
    id="K20",
    title="損害賠償の上限と除外",
    genres=frozenset({"outsourcing", "delegation", "consulting", "sysdev", "license", "purchase", "nda"}),
    topics=(),
    sampler=_sample,
    extra_applicable=_applicable,
)
