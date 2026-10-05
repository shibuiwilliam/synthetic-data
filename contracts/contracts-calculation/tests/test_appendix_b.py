"""付録Bの設例を CalcSpec として検証し、参照インタプリタで全件検算する（T1.7）。"""

from datetime import date

import pytest
from appendix_b_specs import SPECS

from contracts_calculation.spec.interp import eval_rule
from contracts_calculation.spec.model import CalcSpec
from contracts_calculation.spec.validate import validate_spec


def _all_cases():
    for key, raw in SPECS.items():
        spec = CalcSpec.from_dict(raw)
        for rule in spec.rules:
            for i, ex in enumerate(rule.examples):
                yield pytest.param(spec, rule, ex, id=f"{key}:{rule.id}:ex{i}")


@pytest.mark.parametrize("raw", list(SPECS.values()), ids=list(SPECS.keys()))
def test_specs_are_valid(raw: dict) -> None:
    issues = validate_spec(CalcSpec.from_dict(raw))
    assert not issues, "\n".join(str(i) for i in issues)


@pytest.mark.parametrize("spec,rule,ex", list(_all_cases()))
def test_examples_match_appendix_b(spec, rule, ex) -> None:
    holidays = frozenset(date.fromisoformat(h) for h in ex.holidays)
    got = eval_rule(spec, rule, dict(ex.inputs), holidays)
    expect = ex.expect
    if rule.output.get("type") == "date":
        expect = date.fromisoformat(expect)
    assert got == expect


def test_k03_k04_differ_at_250() -> None:
    """同じ料金表で全量方式と超過分方式の金額が違う（§8.2）。"""
    k03 = CalcSpec.from_dict(SPECS["k03"])
    k04 = CalcSpec.from_dict(SPECS["k04"])
    a = eval_rule(k03, k03.rules[0], {"qty": 250})
    b = eval_rule(k04, k04.rules[0], {"qty": 250})
    assert (a, b) == (100000, 110000)


def test_k03_not_monotone_at_boundary() -> None:
    """全量方式は境界で金額が下がる（単調性を性質にしない）。"""
    k03 = CalcSpec.from_dict(SPECS["k03"])
    assert eval_rule(k03, k03.rules[0], {"qty": 101}) < eval_rule(k03, k03.rules[0], {"qty": 100})
