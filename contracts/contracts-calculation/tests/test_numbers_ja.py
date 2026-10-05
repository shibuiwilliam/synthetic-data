"""numbers_ja：本体 meta.constants の実在表記を読め、書いた表記を読み戻せる（往復）。"""

from datetime import date

from contracts_calculation.docmodel import numbers_ja as nj


def test_parse_amount_real_constants() -> None:
    assert nj.parse_amount_yen("300万円") == 3_000_000
    assert nj.parse_amount_yen("180万円") == 1_800_000
    assert nj.parse_amount_yen("2億7350万円") == 273_500_000
    assert nj.parse_amount_yen("5470万円") == 54_700_000
    assert nj.parse_amount_yen("金1,000,000円") == 1_000_000
    assert nj.parse_amount_yen("1,200万円") == 12_000_000
    assert nj.parse_amount_yen("まんじゅう") is None


def test_amount_roundtrip() -> None:
    for n in (3_000_000, 273_500_000, 54_700_000, 123, 10_000, 100_000_000, 100_010_000):
        for style in ("man", "comma"):
            assert nj.parse_amount_yen(nj.format_amount_yen(n, style)) == n


def test_parse_ratio_real_constants() -> None:
    assert nj.parse_ratio("2割") == (2, 10)
    assert nj.parse_ratio("１割") == (1, 10)
    assert nj.parse_ratio("年14.6%") == (146, 1000)
    assert nj.parse_ratio("年3.6パーセント") == (36, 1000)
    assert nj.parse_ratio("4パーセント") == (4, 100)
    assert nj.parse_ratio("90パーセント") == (90, 100)
    assert nj.parse_ratio("2割5分") == (25, 100)
    assert nj.parse_ratio("割合") is None


def test_ratio_roundtrip() -> None:
    assert nj.parse_ratio(nj.format_ratio(146, 1000, yearly=True)) == (146, 1000)
    assert nj.parse_ratio(nj.format_ratio(2, 10, style="wari")) == (2, 10)
    assert nj.parse_ratio(nj.format_ratio(36, 1000, style="percent_kana", yearly=True)) == (36, 1000)
    assert nj.parse_ratio(nj.format_ratio(90, 100)) == (90, 100)


def test_parse_duration_real_constants() -> None:
    assert nj.parse_duration("10日") == nj.Duration(10, "day")
    assert nj.parse_duration("10営業日") == nj.Duration(10, "business_day")
    assert nj.parse_duration("3か月") == nj.Duration(3, "month")
    assert nj.parse_duration("3年") == nj.Duration(3, "year")
    assert nj.parse_duration("5年間") == nj.Duration(5, "year")
    assert nj.parse_duration("20日以内") == nj.Duration(20, "day")
    assert nj.parse_duration("翌月末日") is None


def test_duration_roundtrip() -> None:
    for d in (
        nj.Duration(10, "day"),
        nj.Duration(10, "business_day"),
        nj.Duration(3, "month"),
        nj.Duration(2, "year"),
    ):
        assert nj.parse_duration(nj.format_duration(d)) == d


def test_parse_date_real_formats() -> None:
    assert nj.parse_date_ja("2031年4月6日") == date(2031, 4, 6)
    assert nj.parse_date_ja("２０２７年９月１４日") == date(2027, 9, 14)
    assert nj.parse_date_ja("2026-10-31") == date(2026, 10, 31)
    assert nj.parse_date_ja("2026年2月30日") is None


def test_date_roundtrip() -> None:
    for d in (date(2031, 4, 6), date(2028, 2, 29)):
        assert nj.parse_date_ja(nj.format_date_ja(d)) == d


def test_day_of_month_and_count() -> None:
    assert nj.parse_day_of_month("毎月5日") == 5
    assert nj.parse_day_of_month("翌月末日") == "end"
    assert nj.parse_count("合計4回") == 4
