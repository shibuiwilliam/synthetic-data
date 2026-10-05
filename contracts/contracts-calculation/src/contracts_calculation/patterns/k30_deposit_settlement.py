"""K30 精算：預り金 − 未払金 − 原状回復費用。0円を下限とする。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, lit, money, op, param, step, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K30")
    deposit = rng.choice(v["deposit"])
    ds = ctx.digit_style
    n_dep = ctx.free_const_name("gear_deposit")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K30",
        rule_id="deposit_refund",
        function="deposit_refund",
        title="貸与品の預り金",
        kind="calculation",
        params={n_dep: ParamDraft(n_dep, "int", money(deposit, ds), value=deposit, unit="JPY")},
        inputs={"unpaid_fees": concept("unpaid_fees"), "repair_cost": concept("repair_cost")},
        steps=[
            {
                "name": "deductions",
                "label": "差し引く額",
                "expr": op("add", var("unpaid_fees"), var("repair_cost")),
            },
            {
                "name": "refund",
                "label": "返還する預り金の額",
                "expr": op("max", lit(0), op("sub", param(n_dep), step("deductions"))),
            },
        ],
        output={"step": "refund", "type": "int", "unit": "JPY"},
        obligations=["settlement:deduct_unpaid_and_repair", "floor_zero:no_negative_refund"],
        paragraphs=[
            f"{{party:{payee}}}は、貸与品の預り金として{{const:{n_dep}}}を{{party:{payer}}}に差し入れる。",
            (
                f"{{party:{payer}}}は、本契約の終了後、預り金から未払の対価および貸与品の原状回復に要した"
                f"費用を差し引いた額を{{party:{payee}}}に返す。差引き後の額が負となるときは、"
                f"{fw('0円', ds)}とし、返還は要しない。"
            ),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"depth": 2},
    )


PATTERN = PatternDef(
    id="K30",
    title="精算（預り金）",
    genres=frozenset({"outsourcing", "delegation", "sysdev"}),
    topics=("預り金",),
    sampler=_sample,
)
