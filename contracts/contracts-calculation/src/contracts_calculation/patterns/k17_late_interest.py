"""K17 遅延損害金：未払額 × 年率 × 遅延日数 ÷ 365。"""

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
    sentence_rounding,
    step,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K17")
    permille = rng.choice(v["late_rate_permille"])
    year_days = rng.choice(v["year_days"])
    ds = ctx.digit_style
    n_rate = ctx.free_const_name("late_charge_rate")
    n_days = ctx.free_const_name("late_year_days")
    payer, payee = ctx.payer_key, ctx.payee_key
    variant = rng.randrange(2)
    opening = (
        "支払期日までに本契約に基づく金銭を支払わないときは"
        if variant
        else "本契約に基づく金銭の支払を怠ったときは"
    )
    return RuleDraft(
        pattern_id="K17",
        rule_id="late_charge",
        function="late_charge",
        title="遅延損害金",
        kind="calculation",
        params={
            n_rate: ParamDraft(n_rate, "ratio", pct_surface(permille, ds), num=permille, den=1000),
            n_days: ParamDraft(n_days, "int", fw(f"{year_days}日", ds), value=year_days, unit="DAY"),
        },
        inputs={
            "unpaid_amount": concept("unpaid_amount"),
            "due_date": concept("due_date"),
            "paid_date": concept("paid_date"),
        },
        steps=[
            {
                "name": "late_days",
                "label": "遅延日数",
                "expr": op("max", lit(0), op("days_between", var("due_date"), var("paid_date"))),
            },
            {
                "name": "late_charge",
                "label": "遅延損害金の額",
                "expr": op(
                    "muldiv",
                    op("mul", var("unpaid_amount"), step("late_days")),
                    param(n_rate),
                    param(n_days),
                    rounding="floor",
                ),
            },
        ],
        output={"step": "late_charge", "type": "int", "unit": "JPY"},
        obligations=["day_count:next_day_to_payment_day", "year_basis:declared_days", "rounding:floor_1yen"],
        paragraphs=[
            (
                f"{{party:{payer}}}は、{opening}、支払期日の翌日から"
                f"支払済みに至る日までの日数に応じ、未払額に年{{const:{n_rate}}}の割合で計算した"
                f"遅延損害金を{{party:{payee}}}に支払う。"
            ),
            f"遅延損害金は、年{{const:{n_days}}}の日割計算により算出する。"
            + sentence_rounding("floor", ds, variant),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        difficulty={"calendar": "days", "depth": 2},
    )


PATTERN = PatternDef(
    id="K17",
    title="遅延損害金",
    genres=frozenset(
        {
            "outsourcing",
            "delegation",
            "consulting",
            "sysdev",
            "license",
            "lease",
            "purchase",
            "contracting",
            "nda",
        }
    ),
    topics=("遅延損害金", "遅延利息"),
    sampler=_sample,
)
