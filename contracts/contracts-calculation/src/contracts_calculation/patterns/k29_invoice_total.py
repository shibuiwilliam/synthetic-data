"""K29 請求額の合成：小計 → 値引き → 税 → 合計。"""

from __future__ import annotations

from .base import (
    ParamDraft,
    PatternDef,
    RuleDraft,
    concept,
    fw,
    lit,
    op,
    param,
    pct_surface,
    step,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K29")
    disc = rng.choice(v["discount_permille"])
    tax = rng.choice(v["tax_pct"])
    ds = ctx.digit_style
    n_disc = ctx.free_const_name("vol_discount_rate")
    n_tax = ctx.free_const_name("bill_tax_rate")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K29",
        rule_id="invoice_total",
        function="invoice_total",
        title="請求額の算定",
        kind="calculation",
        params={
            n_disc: ParamDraft(n_disc, "ratio", pct_surface(disc, ds), num=disc, den=1000),
            n_tax: ParamDraft(n_tax, "ratio", pct_surface(tax * 10, ds), num=tax, den=100),
        },
        inputs={"subtotal_amount": concept("subtotal_amount")},
        steps=[
            {
                "name": "discount",
                "label": "値引きの額",
                "expr": op("muldiv", var("subtotal_amount"), param(n_disc), lit(1), rounding="floor"),
            },
            {
                "name": "discounted",
                "label": "値引き後の額",
                "expr": op("sub", var("subtotal_amount"), step("discount")),
            },
            {
                "name": "tax_amount",
                "label": "消費税等相当額",
                "expr": op("muldiv", step("discounted"), param(n_tax), lit(1), rounding="floor"),
            },
            {"name": "total", "label": "請求額", "expr": op("add", step("discounted"), step("tax_amount"))},
        ],
        output={"step": "total", "type": "int", "unit": "JPY"},
        obligations=["discount:before_tax", "tax:amount_is_exclusive", "rounding:floor_1yen"],
        paragraphs=[
            (
                f"当月の請求額は、個別契約に基づく対価の小計（消費税等相当額を含まない）から、小計に"
                f"{{const:{n_disc}}}を乗じた額（{fw('1円', ds)}未満の端数は切り捨てる）を値引きした額を基礎とする。"
            ),
            (
                f"{{party:{payer}}}は、前項の額に{{const:{n_tax}}}を乗じた額（{fw('1円', ds)}未満の端数は切り捨てる）を"
                f"消費税等相当額として加算した額を{{party:{payee}}}に支払う。値引きは、消費税等相当額の"
                "計算の前に適用する。"
            ),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"depth": 4},
    )


PATTERN = PatternDef(
    id="K29",
    title="請求額の合成",
    genres=frozenset({"outsourcing", "delegation", "sysdev"}),
    topics=("値引",),
    sampler=_sample,
)
