"""K16 存続期間：契約終了日から N 年（資料保管義務の存続）。"""

from __future__ import annotations

from .base import ParamDraft, PatternDef, RuleDraft, concept, fw, lit, op, param, values_of, var


def _sample(ctx, rng) -> RuleDraft:
    v = values_of("K16")
    years = rng.choice(v["survival_years"])
    ds = ctx.digit_style
    n_years = ctx.free_const_name("archive_years")
    payee = ctx.payee_key
    return RuleDraft(
        pattern_id="K16",
        rule_id="archive_duty_end",
        function="archive_duty_end",
        title="資料の保管義務",
        kind="calculation",
        params={n_years: ParamDraft(n_years, "int", fw(f"{years}年", ds), value=years, unit="YEAR")},
        inputs={"end_date": concept("end_date")},
        steps=[
            {
                "name": "duty_end",
                "label": "保管義務が終わる日",
                "expr": op("add_months", var("end_date"), op("mul", param(n_years), lit(12))),
            },
        ],
        output={"step": "duty_end", "type": "date"},
        obligations=["survival:after_termination", "period_count:anniversary"],
        paragraphs=[
            (
                f"{{party:{payee}}}は、本契約の履行のために交付を受けた資料の保管義務を、本契約の終了後も負う。"
                f"この義務は、本契約の終了日から{{const:{n_years}}}を経過する日（終了日の応当日）まで存続する。"
                "応当する日がない月は、その月の末日を当該応当日とする。"
            ),
        ],
        difficulty={"calendar": "months", "depth": 1},
    )


PATTERN = PatternDef(
    id="K16",
    title="存続期間",
    genres=frozenset({"outsourcing", "delegation", "sysdev", "consulting"}),
    topics=("資料の保管義務",),
    sampler=_sample,
)
