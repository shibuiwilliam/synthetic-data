"""計算パックに同梱する pytest の生成（DESIGN.md §13.5）。

- cases.jsonl を読み、関数を名前で呼ぶ。
- 既定は同じパックの programs/ の正解プログラム。--impl で評価対象のモジュールに差し替える。
"""

from __future__ import annotations

_CONFTEST = '''"""計算パックのテスト設定。--impl で評価対象のモジュールに差し替える。"""

import importlib.util
import json
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent


def pytest_addoption(parser):
    parser.addoption("--impl", default=None, help="評価対象の Python モジュールのパス")


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="session")
def impl(request):
    opt = request.config.getoption("--impl")
    if opt:
        return load_module(Path(opt))
    programs = sorted((HERE.parent / "programs").glob("calc_*.py"))
    assert programs, "programs/ に正解プログラムが無い"
    return load_module(programs[0])


def load_cases():
    rows = []
    with open(HERE.parent / "cases.jsonl", encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows
'''

_TEST = '''"""cases.jsonl の全件を実行する（自動生成。手で編集しない）。"""

from datetime import date

import pytest
from conftest import load_cases


def _conv(value, type_):
    if value is None:
        return None
    if type_ == "date":
        return date.fromisoformat(value)
    return value


_CASES = load_cases()
_TYPES = {TYPES}


@pytest.mark.parametrize("case", _CASES, ids=[c["case_id"] for c in _CASES])
def test_case(impl, case):
    fn = getattr(impl, case["function"])
    in_types = _TYPES[case["function"]]["inputs"]
    kwargs = {name: _conv(v, in_types.get(name, "int")) for name, v in case["inputs"].items()}
    if _TYPES[case["function"]]["uses_calendar"]:
        kwargs["holidays"] = frozenset(date.fromisoformat(h) for h in case.get("holidays", []))
    got = fn(**kwargs)
    expected = _conv(case["expected"], _TYPES[case["function"]]["output"])
    assert got == expected, f"{case['case_id']}: {got!r} != {expected!r}"
'''


def write_tests(calc_dir, spec, cards) -> None:
    """calc/tests/ に conftest.py と test_calc.py を書き出す。"""
    from pathlib import Path

    tests_dir = Path(calc_dir) / "tests"
    tests_dir.mkdir(parents=True, exist_ok=True)
    types = {}
    for rule, card in zip(spec.rules, cards):
        types[rule.function] = {
            "inputs": {n: d.type for n, d in rule.inputs.items()},
            "output": rule.output.get("type", "int"),
            "uses_calendar": card["uses_calendar"],
        }
    (tests_dir / "conftest.py").write_text(_CONFTEST, encoding="utf-8")
    (tests_dir / "test_calc.py").write_text(_TEST.replace("{TYPES}", repr(types)), encoding="utf-8")
