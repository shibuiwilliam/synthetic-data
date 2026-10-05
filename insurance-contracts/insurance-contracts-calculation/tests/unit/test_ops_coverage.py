"""演算の台帳（`spec/ops.py`）にあるものが、5 モジュールすべてで扱われていること。

`CLAUDE.md`「演算や型を足すとき」の約束を機械で守らせる。
意味論（参照インタプリタ）と生成 Python が一致することも、同じ標本で確かめる。
"""

from __future__ import annotations

import datetime as dt

import pytest
from helpers import build_ruleset

from insurance_contracts_calculation.codegen import python as codegen
from insurance_contracts_calculation.realize import explain
from insurance_contracts_calculation.spec import interp
from insurance_contracts_calculation.spec.ops import OPS
from insurance_contracts_calculation.testgen import mutation

#: 演算ごとの標本（式・入力・期待値）。演算を足したらここにも足す
SAMPLES: dict[str, tuple[dict, dict, object]] = {
    "add": ({"op": "add", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 3, "b": 4}, 7),
    "sub": ({"op": "sub", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 9, "b": 4}, 5),
    "mul": ({"op": "mul", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 3, "b": 4}, 12),
    "muldiv": (
        {
            "op": "muldiv",
            "rounding": "floor",
            "args": [{"var": "a"}, {"var": "b"}, {"lit": 7, "note": "検査用"}],
        },
        {"a": 10, "b": 3},
        4,
    ),
    "min": ({"op": "min", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 3, "b": 4}, 3),
    "max": ({"op": "max", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 3, "b": 4}, 4),
    "round_to": (
        {"op": "round_to", "rounding": "floor", "args": [{"var": "a"}, {"lit": 100, "note": "検査用"}]},
        {"a": 1234},
        1200,
    ),
    "lt": ({"op": "lt", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 3, "b": 4}, True),
    "le": ({"op": "le", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 4, "b": 4}, True),
    "gt": ({"op": "gt", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 3, "b": 4}, False),
    "ge": ({"op": "ge", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 4, "b": 4}, True),
    "eq": ({"op": "eq", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 4, "b": 4}, True),
    "ne": ({"op": "ne", "args": [{"var": "a"}, {"var": "b"}]}, {"a": 4, "b": 4}, False),
    "and": ({"op": "and", "args": [{"var": "p"}, {"var": "q"}]}, {"p": True, "q": False}, False),
    "or": ({"op": "or", "args": [{"var": "p"}, {"var": "q"}]}, {"p": True, "q": False}, True),
    "not": ({"op": "not", "args": [{"var": "p"}]}, {"p": True}, False),
    "if": (
        {"op": "if", "args": [{"var": "p"}, {"var": "a"}, {"var": "b"}]},
        {"p": True, "a": 3, "b": 4},
        3,
    ),
    "coalesce": ({"op": "coalesce", "args": [{"var": "a"}, {"lit": 0}]}, {"a": None}, 0),
    "lookup": ({"op": "lookup", "table": "rate", "args": [{"var": "m"}]}, {"m": 10}, 30),
    "agg": (
        {"op": "agg", "func": "sum", "over": "items", "args": [{"item": "amount"}]},
        {"items": [{"amount": 2}, {"amount": 5}]},
        7,
    ),
    "add_days": (
        {"op": "add_days", "args": [{"var": "d"}, {"var": "n"}]},
        {"d": dt.date(2024, 2, 28), "n": 2},
        dt.date(2024, 3, 1),
    ),
    "add_months": (
        {"op": "add_months", "args": [{"var": "d"}, {"var": "m"}]},
        {"d": dt.date(2024, 1, 31), "m": 1},
        dt.date(2024, 2, 29),
    ),
    "days_between": (
        {"op": "days_between", "args": [{"var": "d"}, {"var": "e"}]},
        {"d": dt.date(2024, 3, 1), "e": dt.date(2024, 3, 11)},
        10,
    ),
    "end_of_month": (
        {"op": "end_of_month", "args": [{"var": "d"}]},
        {"d": dt.date(2024, 2, 3)},
        dt.date(2024, 2, 29),
    ),
}


def test_every_op_has_a_sample() -> None:
    assert set(SAMPLES) == set(OPS), "演算を足したら SAMPLES にも足す"


@pytest.mark.parametrize("op", sorted(SAMPLES))
def test_interpreter_matches_generated_python(op: str) -> None:
    expr, inputs, expected = SAMPLES[op]
    rs = build_ruleset(expr, inputs)
    assert interp._ev(rs, rs.full_expr("t.rule"), inputs, None) == expected
    ns: dict = {}
    exec(compile(codegen.compile_module(rs), "gen.py", "exec"), ns)  # noqa: S102
    assert ns["t_rule"](**inputs) == expected


@pytest.mark.parametrize("op", sorted(SAMPLES))
def test_unknown_propagates(op: str) -> None:
    """引数のどれかが不明なら、厳密な演算の結果は不明になる。"""
    expr, inputs, _ = SAMPLES[op]
    if not OPS[op].strict:
        return
    rs = build_ruleset(expr, inputs)
    for name in inputs:
        if isinstance(inputs[name], list):
            continue
        got = interp._ev(rs, rs.full_expr("t.rule"), {**inputs, name: None}, None)
        assert got is None, f"{op}: {name} が不明でも結果が確定している（{got}）"


@pytest.mark.parametrize("op", sorted(SAMPLES))
def test_explain_renders(op: str) -> None:
    expr, inputs, _ = SAMPLES[op]
    rs = build_ruleset(expr, inputs)
    assert explain.render(rs, "t.rule")


@pytest.mark.parametrize("op", sorted(SAMPLES))
def test_mutation_knows_the_op(op: str) -> None:
    """変異の種類が 1 つも作れない演算は、テストの十分性を測れない。"""
    expr, inputs, _ = SAMPLES[op]
    rs = build_ruleset(expr, inputs)
    muts = mutation.mutants(rs, "t.rule")
    assert muts, f"{op}: 変異体を 1 つも作れない"
