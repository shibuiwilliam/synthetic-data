"""K11 締日と支払期日：月末締め、翌月（翌々月）の指定日または末日払い。休業日は前後の営業日。"""

from __future__ import annotations

from .base import (
    ParamDraft,
    PatternDef,
    RuleDraft,
    calendar_def_paragraph,
    concept,
    fw,
    lit,
    op,
    param,
    step,
    values_of,
    var,
)


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K11")
    style = rng.choice(v["style"])
    offset = rng.choice(v["month_offset"])
    adjust = rng.choice(v["adjust"])
    ds = ctx.digit_style
    month_word = "翌月" if offset == 1 else "翌々月"
    payer, payee = ctx.payer_key, ctx.payee_key
    params = {}
    if style == "day":
        day = rng.choice(v["pay_day"])
        n_day = ctx.free_const_name("fee_pay_day")
        params[n_day] = ParamDraft(n_day, "int", fw(f"{day}日", ds), value=day, unit="DAY")
        due_raw = op("set_day", op("add_months", var("closing_date"), lit(offset)), param(n_day))
        due_text = f"{month_word}{{const:{n_day}}}"
    else:
        due_raw = op("end_of_month", op("add_months", var("closing_date"), lit(offset)))
        due_text = f"{month_word}の末日"
    adjust_op = "prev_business_day" if adjust == "prev" else "next_business_day"
    adjust_text = "直前" if adjust == "prev" else "直後"
    return RuleDraft(
        pattern_id="K11",
        rule_id="added_fee_due_date",
        function="added_fee_due_date",
        title="手数料の支払期日",
        kind="calculation",
        params=params,
        inputs={"closing_date": concept("closing_date")},
        steps=[
            {"name": "due_raw", "label": "支払期日（調整前）", "expr": due_raw},
            {"name": "due", "label": "支払期日", "expr": op(adjust_op, step("due_raw"))},
        ],
        output={"step": "due", "type": "date"},
        obligations=["business_days:defined_in_article", f"holiday_adjust:{adjust}_business_day"],
        paragraphs=[
            (
                "本契約に基づき新たに生じる手数料は、毎月末日をもって締め切る。"
                f"{{party:{payer}}}は、締め切った月の{due_text}までに、"
                f"{{party:{payee}}}の指定する方法により支払う。"
            ),
            f"支払期日が営業日でないときは、その{adjust_text}の営業日を支払期日とする。",
            calendar_def_paragraph(ds),
        ],
        parties={"payer": ctx.alias(payer), "payee": ctx.alias(payee)},
        needs_calendar=True,
        difficulty={"calendar": "business_days", "depth": 2},
    )


PATTERN = PatternDef(
    id="K11",
    title="締日と支払期日",
    genres=frozenset({"outsourcing", "delegation", "consulting", "sysdev", "license", "lease", "purchase"}),
    topics=("手数料の支払期日",),
    sampler=_sample,
)
