"""K02 固定＋従量：基本料金 ＋ 無償枠を超える部分 × 従量単価。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, lit, money, op, param, step, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K02")
    base_fee = rng.choice(v["base_fee"])
    free_units = rng.choice(v["free_units"])
    unit_rate = rng.choice(v["unit_rate"])
    n_base = ctx.free_const_name("storage_base_fee")
    n_free = ctx.free_const_name("storage_free_units")
    n_rate = ctx.free_const_name("storage_unit_rate")
    payer, payee = ctx.payer_key, ctx.payee_key
    ds = ctx.digit_style
    return RuleDraft(
        pattern_id="K02",
        rule_id="storage_fee",
        function="storage_fee",
        title="データ保管の手数料",
        kind="calculation",
        params={
            n_base: ParamDraft(n_base, "int", money(base_fee, ds), value=base_fee, unit="JPY"),
            n_free: ParamDraft(n_free, "int", fw(f"{free_units}件", ds), value=free_units, unit="COUNT"),
            n_rate: ParamDraft(n_rate, "int", money(unit_rate, ds), value=unit_rate, unit="JPY"),
        },
        inputs={"usage_qty": concept("usage_qty")},
        steps=[
            {
                "name": "over_units",
                "label": "無償枠を超える件数",
                "expr": op("max", lit(0), op("sub", var("usage_qty"), param(n_free))),
            },
            {
                "name": "fee",
                "label": "データ保管の手数料",
                "expr": op("add", param(n_base), op("mul", step("over_units"), param(n_rate))),
            },
        ],
        output={"step": "fee", "type": "int", "unit": "JPY"},
        obligations=["free_quota:excess_only_charged"],
        paragraphs=[
            f"{{party:{payer}}}は、データ保管の手数料として、月額{{const:{n_base}}}を{{party:{payee}}}に支払う。",
            (
                f"当月の保管件数が{{const:{n_free}}}を超えたときは、超える部分{fw('1件', ds)}につき"
                f"{{const:{n_rate}}}を前項の額に加算する。"
            ),
        ],
        literal_surfaces=[fw("1件", ds)],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"value_location": "body", "depth": 2},
    )


PATTERN = PatternDef(
    id="K02",
    title="固定＋従量",
    genres=frozenset({"outsourcing", "delegation", "consulting", "sysdev"}),
    topics=("保管の手数料", "データ保管"),
    sampler=_sample,
)
