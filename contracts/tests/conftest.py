"""pytest 共通設定。

`--update-golden` を付けると golden ファイルを現在の出力で上書きする（CLAUDE.md §13）。
更新したら差分の理由をコミットメッセージに書くこと。
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--update-golden",
        action="store_true",
        default=False,
        help="golden ファイルを現在の出力で更新する（差分の理由をコミットメッセージに書く）",
    )


@pytest.fixture(scope="session")
def update_golden(request: pytest.FixtureRequest) -> bool:
    return bool(request.config.getoption("--update-golden"))
