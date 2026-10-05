"""数値の表記は、必ず読み戻せること（`CLAUDE.md`「約款JSONを組み立てるときの決まり」）。"""

from __future__ import annotations

import pytest

from insurance_contracts_calculation.core import numbers_ja as nj
from insurance_contracts_calculation.core.docindex import parse_quantity


@pytest.mark.parametrize(
    ("value", "unit"),
    [
        (10_000, "JPY"),
        (1_000, "JPY"),
        (150_000, "JPY"),
        (100_000_000, "JPY"),
        (12_345, "JPY"),
        (15, "DAY"),
        (3, "BUSINESS_DAY"),
        (24, "MONTH"),
        (5, "YEAR"),
        (30, "PERCENT"),
        (3, "COUNT"),
        (2, "PERSON"),
        (4, "GRADE"),
        (60, "AGE"),
    ],
)
def test_surface_round_trips(value: int, unit: str) -> None:
    surface = nj.surface(value, unit)
    got = parse_quantity(surface)
    assert got is not None, f"{surface} を読み戻せない"
    assert got["value"] == value


def test_unknown_unit_stops_generation() -> None:
    with pytest.raises(ValueError):
        nj.surface(1, "PARSEC")


def test_yen_uses_man_only_for_round_values() -> None:
    assert nj.yen(150_000) == "15万円"
    assert nj.yen(150_500) == "150,500円"
