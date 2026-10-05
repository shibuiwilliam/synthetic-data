"""pytest の書き出し。

テストは `cases.jsonl` を読み、関数を名前で呼ぶ。評価対象のモジュールは `--impl` で差し替える。
日付の引数は JSONL では ISO 文字列なので、呼ぶ直前に `datetime.date` に直す。
"""

from __future__ import annotations

import json

CONFTEST = '''"""評価対象の実装を差し替えて同じテストを流す。

    pytest calc/tests                      # 正解プログラムで実行
    pytest calc/tests --impl my_module.py  # 評価対象のプログラムで実行
"""
import importlib.util
from pathlib import Path

import pytest

DEFAULT_IMPL = Path(__file__).parent.parent / "programs" / "{module}.py"


def pytest_addoption(parser):
    parser.addoption("--impl", action="store", default=str(DEFAULT_IMPL),
                     help="評価対象のモジュール（既定は正解プログラム）")


@pytest.fixture(scope="session")
def impl(request):
    path = Path(request.config.getoption("--impl"))
    spec = importlib.util.spec_from_file_location("impl_under_test", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module
'''

TEST_FILE = '''"""{title} の計算・判定プログラムのユニットテスト（自動生成）。"""
import datetime
import json
from pathlib import Path

import pytest

CASES = [json.loads(line) for line in
         (Path(__file__).parent.parent / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line]

#: 日付として渡す引数（JSONL では ISO 文字列で持つ）
DATE_ARGS = {date_args}


def _call_args(case):
    dates = DATE_ARGS.get(case["function"], ())
    return {{k: (datetime.date.fromisoformat(v) if (k in dates and v is not None) else v)
            for k, v in case["inputs"].items()}}


def _expected(case):
    want = case["expected"]
    if case.get("expected_type") == "date" and want is not None:
        return datetime.date.fromisoformat(want)
    return want


@pytest.mark.parametrize("case", CASES, ids=[c["case_id"] for c in CASES])
def test_case(impl, case):
    fn = getattr(impl, case["function"])
    assert fn(**_call_args(case)) == _expected(case)
'''


def conftest(module: str) -> str:
    return CONFTEST.format(module=module)


def test_module(title: str, date_args: dict[str, list[str]]) -> str:
    return TEST_FILE.format(title=title, date_args=json.dumps(date_args, ensure_ascii=False, sort_keys=True))
