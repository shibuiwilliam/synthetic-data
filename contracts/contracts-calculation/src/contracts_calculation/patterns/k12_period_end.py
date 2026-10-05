"""K12 期間の満了日：保守サポートの提供期間（開始日から N 年、初日を含む）。"""

from __future__ import annotations

import datetime as _dt

from .base import ParamDraft, PatternDef, RuleDraft, fw, op, param, values_of


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K12")
    years = rng.choice(v["term_years"])
    start = _dt.date(rng.choice([2026, 2027, 2028, 2029]), rng.choice([1, 4, 7, 10]), 1)
    ds = ctx.digit_style
    n_start = ctx.free_const_name("support_start")
    n_years = ctx.free_const_name("support_years")
    payer, payee = ctx.payer_key, ctx.payee_key
    return RuleDraft(
        pattern_id="K12",
        rule_id="support_period_end",
        function="support_period_end",
        title="保守サポートの提供期間",
        kind="calculation",
        params={
            n_start: ParamDraft(
                n_start,
                "date",
                fw(f"{start.year}年{start.month}月{start.day}日", ds),
                value=start.isoformat(),
            ),
            n_years: ParamDraft(n_years, "int", fw(f"{years}年", ds), value=years, unit="YEAR"),
        },
        inputs={},
        steps=[
            {
                "name": "period_end_date",
                "label": "提供期間の満了日",
                "expr": op("period_end", param(n_start), param(n_years), unit="year", include_start=True),
            },
        ],
        output={"step": "period_end_date", "type": "date"},
        obligations=["period_count:include_start_day"],
        paragraphs=[
            (
                f"{{party:{payee}}}は、{{party:{payer}}}に対し、本契約に基づく保守サポートを"
                f"{{const:{n_start}}}から{{const:{n_years}}}間提供する。期間の計算には初日を含む。"
            ),
        ],
        difficulty={"calendar": "months", "depth": 1},
    )


PATTERN = PatternDef(
    id="K12",
    title="期間の満了日",
    genres=frozenset({"outsourcing", "delegation", "sysdev", "purchase", "license"}),
    topics=("保守サポート",),
    sampler=_sample,
)
