"""K18 違約金：違反1件につき定額、総額上限つき。違約金を超える損害の請求可否を明示する。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, fw, money, op, param, step, var


def _sample(ctx, rng) -> RuleDraft:
    unit = rng.choice([100000, 200000, 300000, 500000])
    cap = unit * rng.choice([5, 10])
    ds = ctx.digit_style
    n_unit = ctx.free_const_name("breach_penalty_unit")
    n_cap = ctx.free_const_name("breach_penalty_cap")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K18",
        rule_id="breach_penalty",
        function="breach_penalty",
        title="違約金",
        kind="calculation",
        params={
            n_unit: ParamDraft(n_unit, "int", money(unit, ds), value=unit, unit="JPY"),
            n_cap: ParamDraft(n_cap, "int", money(cap, ds), value=cap, unit="JPY"),
        },
        inputs={
            "breach_count": {
                "type": "int",
                "unit": "COUNT",
                "origin": "judgment",
                "desc": "義務違反の件数",
                "min": 0,
                "max": 100,
            }
        },
        steps=[
            {
                "name": "raw_penalty",
                "label": "件数による違約金",
                "expr": op("mul", param(n_unit), var("breach_count")),
            },
            {
                "name": "penalty",
                "label": "支払う違約金",
                "expr": op("min", step("raw_penalty"), param(n_cap)),
            },
        ],
        output={"step": "penalty", "type": "int", "unit": "JPY"},
        obligations=["cap:total_amount", "beyond_penalty:damages_claimable"],
        paragraphs=[
            (
                f"{{party:{payer}}}は、本契約上の義務に違反したときは、違反{fw('1件', ds)}につき"
                f"{{const:{n_unit}}}の違約金を{{party:{payee}}}に支払う。ただし、違約金の総額は"
                f"{{const:{n_cap}}}を超えない。"
            ),
            "前項の定めは、違約金の額を超える損害についての賠償の請求を妨げない。",
        ],
        literal_surfaces=[fw("1件", ds)],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"value_location": "body", "depth": 2},
    )


PATTERN = PatternDef(
    id="K18",
    title="違約金（件数×定額・上限つき）",
    genres=frozenset(
        {
            "nda",
            "outsourcing",
            "delegation",
            "consulting",
            "sysdev",
            "license",
            "lease",
            "purchase",
            "contracting",
        }
    ),
    topics=("違約金",),
    sampler=_sample,
)
