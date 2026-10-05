"""K01 単価×数量（下限・上限つき）。単価と数量は個別契約・実績（契約書の外）にある。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, money, op, param, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K01")
    min_fee = rng.choice(v["min_fee"])
    cap_fee = min_fee * rng.choice(v["cap_mult"])
    n_min = ctx.free_const_name("af_min_fee")
    n_cap = ctx.free_const_name("af_cap_fee")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K01",
        rule_id="additional_work_fee",
        function="additional_work_fee",
        title="追加作業の対価",
        kind="calculation",
        params={
            n_min: ParamDraft(n_min, "int", money(min_fee, ctx.digit_style), value=min_fee, unit="JPY"),
            n_cap: ParamDraft(n_cap, "int", money(cap_fee, ctx.digit_style), value=cap_fee, unit="JPY"),
        },
        inputs={"unit_price": concept("unit_price"), "qty": concept("qty")},
        steps=[
            {
                "name": "raw_fee",
                "label": "単価に数量を乗じた額",
                "expr": op("mul", var("unit_price"), var("qty")),
            },
            {
                "name": "floored",
                "label": "下限を適用した額",
                "expr": op("max", step_("raw_fee"), param(n_min)),
            },
            {"name": "fee", "label": "追加作業の対価", "expr": op("min", step_("floored"), param(n_cap))},
        ],
        output={"step": "fee", "type": "int", "unit": "JPY"},
        obligations=["floor_then_cap:min_first", "value_location:order"],
        paragraphs=[
            (
                f"{{party:{payer}}}が{{party:{payee}}}に委託する追加作業の対価は、"
                "個別契約に定める単価に当該月の数量を乗じて算出する。"
            ),
            (
                f"前項の額は、月額{{const:{n_min}}}を下回らず、{{const:{n_cap}}}を超えないものとする。"
                "下限と上限は、この順に適用する。"
            ),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"value_location": "order", "depth": 3},
    )


def step_(n: str) -> dict:  # base.step と名前が重なるのを避けた別名
    return {"step": n}


PATTERN = PatternDef(
    id="K01",
    title="単価×数量（下限・上限つき）",
    genres=frozenset({"outsourcing", "delegation", "sysdev", "purchase", "contracting"}),
    topics=("追加作業の対価",),
    sampler=_sample,
)
