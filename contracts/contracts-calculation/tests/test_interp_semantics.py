"""§12.3 の意味論ごとの単体テスト（T1.6）。"""

import pytest
from appendix_b_specs import SPECS, lit, op, param, var

from contracts_calculation.spec.interp import SpecError, eval_rule
from contracts_calculation.spec.model import CalcSpec


def _mini_rule(steps: list[dict], inputs: dict | None = None, params: dict | None = None, output_unit="JPY"):
    raw = {
        "spec_version": "0.1",
        "document": {},
        "params": params or {},
        "tables": {},
        "rules": [
            {
                "id": "r",
                "title": "t",
                "kind": "calculation",
                "origin": "added",
                "parties": {"payer": "乙", "payee": "甲"},
                "interface": {"function": "f"},
                "inputs": inputs or {},
                "steps": steps,
                "output": {"step": steps[-1]["name"], "type": "int", "unit": output_unit},
                "obligations": ["rounding:any", "day_count:any", "tier_method:any"],
            }
        ],
    }
    spec = CalcSpec.from_dict(raw)
    return spec, spec.rules[0]


INT_IN = {
    "x": {"type": "int", "unit": "JPY", "origin": "fact"},
    "y": {"type": "int", "unit": "JPY", "origin": "fact"},
}
BOOL_IN = {"p": {"type": "bool", "origin": "notice"}, "q": {"type": "bool", "origin": "notice"}}


def test_none_propagates_through_arithmetic() -> None:
    spec, rule = _mini_rule([{"name": "s", "label": "", "expr": op("add", var("x"), var("y"))}], INT_IN)
    assert eval_rule(spec, rule, {"x": None, "y": 1}) is None


def test_three_valued_and_or() -> None:
    spec, rule = _mini_rule([{"name": "s", "label": "", "expr": op("and", var("p"), var("q"))}], BOOL_IN)
    assert eval_rule(spec, rule, {"p": False, "q": None}) is False  # 偽が1つでもあれば偽
    assert eval_rule(spec, rule, {"p": True, "q": None}) is None
    spec, rule = _mini_rule([{"name": "s", "label": "", "expr": op("or", var("p"), var("q"))}], BOOL_IN)
    assert eval_rule(spec, rule, {"p": True, "q": None}) is True  # 真が1つでもあれば真
    assert eval_rule(spec, rule, {"p": False, "q": None}) is None


def test_if_with_unknown_condition_is_unknown() -> None:
    spec, rule = _mini_rule(
        [{"name": "s", "label": "", "expr": op("if", var("p"), lit(1), lit(2))}],
        {"p": {"type": "bool", "origin": "notice"}},
    )
    assert eval_rule(spec, rule, {"p": None}) is None


def test_coalesce_takes_first_known() -> None:
    spec, rule = _mini_rule(
        [{"name": "s", "label": "", "expr": op("coalesce", var("x"), lit(30))}],
        {"x": {"type": "int", "unit": "DAY", "origin": "order", "optional": True}},
    )
    assert eval_rule(spec, rule, {"x": None}) == 30
    assert eval_rule(spec, rule, {"x": 10}) == 10


def test_zero_division_is_unknown() -> None:
    spec, rule = _mini_rule(
        [{"name": "s", "label": "", "expr": op("muldiv", var("x"), lit(1), var("y"), rounding="floor")}],
        INT_IN,
    )
    assert eval_rule(spec, rule, {"x": 100, "y": 0}) is None


def test_missing_table_key_is_unknown() -> None:
    raw = dict(SPECS["k03"])
    spec = CalcSpec.from_dict(raw)
    rule = spec.rules[0]
    # exact lookup を直接検査する（k03 の表を exact で引く）
    from contracts_calculation.spec.interp import _Evaluator

    ev = _Evaluator(spec, rule, {}, frozenset())
    assert ev._lookup(spec.tables["unit_price"], "exact", 999) is None


def test_muldiv_rounding_modes() -> None:
    for rounding, expect in (("floor", 166), ("ceil", 167), ("half_up", 167)):
        spec, rule = _mini_rule(
            [{"name": "s", "label": "", "expr": op("muldiv", var("x"), lit(1), lit(3), rounding=rounding)}],
            INT_IN,
        )
        assert eval_rule(spec, rule, {"x": 500, "y": 0}) == expect


def test_ratio_outside_muldiv_raises() -> None:
    spec, rule = _mini_rule(
        [{"name": "s", "label": "", "expr": op("add", param("r"), lit(1))}],
        INT_IN,
        params={"r": {"type": "ratio", "num": 1, "den": 10, "source": {"unit": "a1", "quote": "1割"}}},
    )
    with pytest.raises(SpecError):
        eval_rule(spec, rule, {"x": 1, "y": 1})


def test_round_to_unit() -> None:
    spec, rule = _mini_rule(
        [{"name": "s", "label": "", "expr": op("round_to", var("x"), unit_value=100, rounding="floor")}],
        INT_IN,
    )
    assert eval_rule(spec, rule, {"x": 1234, "y": 0}) == 1200
