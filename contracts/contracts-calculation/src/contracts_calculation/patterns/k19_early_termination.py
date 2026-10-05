"""K19 中途解約金：残存月数 × 月額 × 率（K02 のデータ保管の手数料に付く）。"""

from __future__ import annotations

from .base import (
    ParamDraft,
    PatternDef,
    RuleDraft,
    concept,
    lit,
    op,
    param,
    pct_surface,
    sentence_rounding,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K19")
    pct = rng.choice(v["rate_pct"])
    ds = ctx.digit_style
    n_rate = ctx.free_const_name("early_term_rate")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K19",
        rule_id="early_termination_fee",
        function="early_termination_fee",
        title="データ保管の中途解約金",
        kind="calculation",
        params={n_rate: ParamDraft(n_rate, "ratio", pct_surface(pct * 10, ds), num=pct, den=100)},
        inputs={
            "remaining_months": concept("remaining_months"),
            "monthly_fee": {
                "type": "int",
                "unit": "JPY",
                "origin": "order",
                "min": 0,
                "max": 10000000,
                "desc": "解約時点のデータ保管の手数料の月額（基本料金）",
            },
        },
        steps=[
            {
                "name": "base_total",
                "label": "残存期間の基本料金の総額",
                "expr": op("mul", var("monthly_fee"), var("remaining_months")),
            },
            {
                "name": "fee",
                "label": "中途解約金の額",
                "expr": op("muldiv", {"step": "base_total"}, param(n_rate), lit(1), rounding="floor"),
            },
        ],
        output={"step": "fee", "type": "int", "unit": "JPY"},
        obligations=["rounding:floor_1yen"],
        paragraphs=[
            f"{{party:{payer}}}は、期間の途中で{{REF_RULE:storage_fee}}のデータ保管の利用を終了するときは、"
            f"終了時点の基本料金の月額に残存月数を乗じた額に{{const:{n_rate}}}を乗じた額を、"
            f"中途解約金として{{party:{payee}}}に支払う。" + sentence_rounding("floor", ds),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"depth": 2, "scatter": 2},
    )


PATTERN = PatternDef(
    id="K19",
    title="中途解約金",
    genres=frozenset({"outsourcing", "delegation", "consulting", "sysdev"}),
    topics=("中途解約金",),
    sampler=_sample,
)
