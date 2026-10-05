"""K08 消費税の加算：税抜額 × 税率。端数処理つき。"""

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
    step,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K08")
    pct = rng.choice(v["tax_rate_pct"])
    rounding = rng.choice(v["rounding"])
    ds = ctx.digit_style
    n_rate = ctx.free_const_name("tax_rate")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K08",
        rule_id="tax_added_total",
        function="tax_added_total",
        title="消費税等相当額",
        kind="calculation",
        params={n_rate: ParamDraft(n_rate, "ratio", pct_surface(pct * 10, ds), num=pct, den=100)},
        inputs={"base_amount": concept("base_amount")},
        steps=[
            {
                "name": "tax",
                "label": "消費税等相当額",
                "expr": op("muldiv", var("base_amount"), param(n_rate), lit(1), rounding=rounding),
            },
            {"name": "total", "label": "支払総額", "expr": op("add", var("base_amount"), step("tax"))},
        ],
        output={"step": "total", "type": "int", "unit": "JPY"},
        obligations=["tax:amount_is_exclusive", f"rounding:{rounding}_1yen"],
        paragraphs=[
            "本契約の対価には、消費税および地方消費税に相当する額を含まない。",
            f"{{party:{payer}}}は、対価に{{const:{n_rate}}}を乗じて得た額を消費税等相当額として、"
            f"対価に加算して{{party:{payee}}}に支払う。" + sentence_rounding(rounding, ds),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"value_location": "body", "depth": 2},
    )


PATTERN = PatternDef(
    id="K08",
    title="消費税の加算",
    genres=frozenset(
        {"outsourcing", "delegation", "consulting", "sysdev", "license", "lease", "purchase", "contracting"}
    ),
    topics=("消費税",),
    sampler=_sample,
)
