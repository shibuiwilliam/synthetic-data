"""K21 補償の下限・バスケット・上限：個別の下限、累計のしきい値、総額の上限。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, lit, money, op, param, step, values_of


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K21")
    de_minimis = rng.choice(v["de_minimis"])
    threshold = rng.choice([t for t in v["threshold"] if t > de_minimis])
    cap = threshold * rng.choice(v["cap_mult"])
    method = rng.choice(v["method"])
    ds = ctx.digit_style
    n_dm = ctx.free_const_name("ind_de_minimis")
    n_th = ctx.free_const_name("ind_threshold")
    n_cap = ctx.free_const_name("ind_cap")
    payer, payee = ctx.payee_key, ctx.payer_key  # 補償するのは受託者・売主側
    eligible = {
        "name": "eligible",
        "label": "対象損害の合計",
        "expr": {
            "op": "agg",
            "mode": "sum",
            "over": "damages",
            "filter": op("ge", {"item": True}, param(n_dm)),
            "args": [],
        },
    }
    if method == "full":
        basket_step = {
            "name": "basket",
            "label": "しきい値の判定（全額方式）",
            "expr": op("if", op("gt", step("eligible"), param(n_th)), step("eligible"), lit(0)),
        }
        how = "対象となる損害の全額について補償を行う"
        ob = "basket:full_amount"
    else:
        basket_step = {
            "name": "basket",
            "label": "しきい値を超える部分（超過額方式）",
            "expr": op("max", lit(0), op("sub", step("eligible"), param(n_th))),
        }
        how = "その超える部分に限り補償を行う"
        ob = "basket:excess_only"
    return RuleDraft(
        pattern_id="K21",
        rule_id="indemnity_payable",
        function="indemnity_payable",
        title="補償",
        kind="calculation",
        params={
            n_dm: ParamDraft(n_dm, "int", money(de_minimis, ds), value=de_minimis, unit="JPY"),
            n_th: ParamDraft(n_th, "int", money(threshold, ds), value=threshold, unit="JPY"),
            n_cap: ParamDraft(n_cap, "int", money(cap, ds), value=cap, unit="JPY"),
        },
        inputs={"damages": concept("damages")},
        steps=[
            eligible,
            basket_step,
            {"name": "payable", "label": "補償する額", "expr": op("min", step("basket"), param(n_cap))},
        ],
        output={"step": "payable", "type": "int", "unit": "JPY"},
        obligations=[ob, "de_minimis:per_item", "cap:aggregate"],
        paragraphs=[
            (
                f"{{party:{payer}}}は、{{party:{payee}}}に生じた損害のうち{fw('1件', ds)}あたり{{const:{n_dm}}}に"
                f"満たない損害を除き、対象となる損害の合計が{{const:{n_th}}}を超えたときに限り、{how}。"
            ),
            f"補償の累計は、{{const:{n_cap}}}を超えないものとする。",
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"depth": 3, "condition": "basket"},
    )


PATTERN = PatternDef(
    id="K21",
    title="補償の下限・バスケット・上限",
    genres=frozenset({"sysdev", "license", "purchase"}),
    topics=("補償",),
    sampler=_sample,
)
