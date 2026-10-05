"""数値の表記（約款の書きぶりに合わせる）。

値 → 表記は生成時に 1 回だけ決め、以後は**表記を正**として扱う（値を再計算しない）。
ここで作る表記は、すべて `core.docindex.parse_quantity` で値に読み戻せなければならない。
表記を増やしたら `tests/unit/test_numbers_ja.py` に往復のテストを足す。
"""

from __future__ import annotations

import datetime as _dt


def yen(v: int) -> str:
    if v >= 100_000_000 and v % 100_000_000 == 0:
        return f"{v // 100_000_000:,}億円"
    if v >= 10_000 and v % 10_000 == 0:
        return f"{v // 10_000:,}万円"
    return f"{v:,}円"


def days(n: int) -> str:
    return f"{n}日"


def business_days(n: int) -> str:
    return f"{n}営業日"


def months(n: int) -> str:
    return f"{n}か月"


def years(n: int) -> str:
    return f"{n}年"


def pct(n: int) -> str:
    return f"{n}%"


def count(n: int) -> str:
    return f"{n}回"


def persons(n: int) -> str:
    return f"{n}名"


def grade(n: int) -> str:
    return f"{n}級"


def age(n: int) -> str:
    return f"{n}歳"


#: 単位 → 表記関数。`param` の `unit` から表記を決める
SURFACE = {
    "JPY": yen,
    "DAY": days,
    "BUSINESS_DAY": business_days,
    "MONTH": months,
    "YEAR": years,
    "PERCENT": pct,
    "1": lambda n: f"{n:,}",  # 無次元（倍率・件数）
    "COUNT": count,
    "PERSON": persons,
    "GRADE": grade,
    "AGE": age,
    "JPY/DAY": yen,
    "JPY/MONTH": yen,
    "JPY/PERSON": yen,
}


def surface(value: int, unit: str) -> str:
    """単位に応じた表記。未知の単位は生成を止める（黙って別の表記にしない）。"""
    fn = SURFACE.get(unit)
    if fn is None:
        raise ValueError(f"表記のしかたを知らない単位: {unit}")
    return fn(value)


def iso(d: _dt.date) -> str:
    return d.isoformat()


def date_ja(d: _dt.date) -> str:
    """設例の日付表記（約款の設例は西暦で書く）。"""
    return f"{d.year}年{d.month}月{d.day}日"


def ordinal_ja(n: int) -> str:
    """「1つ目」のような説明用の序数（規範の文には使わない）。"""
    return f"{n}つ目"
