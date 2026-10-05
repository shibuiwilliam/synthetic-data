"""数値・日付・割合・期間の日本語表記と読取。

本体の `meta.constants` の値（「300万円」「2億7350万円」「年14.6%」「2割」「10営業日」
「2031年4月6日」「翌月末日」「毎月5日」など）を、値に読み戻し、また同じ表記に書き出す。
書き出した表記は必ず同じモジュールで読み戻せる（往復テストで保証する）。

- 金額は整数の円。float を使わない。
- 割合は分子と分母の組（例：年14.6% → (146, 1000)）。
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date

__all__ = [
    "Duration",
    "format_amount_yen",
    "format_date_ja",
    "format_duration",
    "format_ratio",
    "normalize",
    "parse_amount_yen",
    "parse_count",
    "parse_date_ja",
    "parse_day_of_month",
    "parse_duration",
    "parse_ratio",
]


def normalize(s: str) -> str:
    """全角英数・記号を半角へ、空白を除去。漢数字は扱わない（本体は算用数字）。"""
    s = unicodedata.normalize("NFKC", s)
    return s.replace(" ", "").replace("　", "")


# --- 金額 ---------------------------------------------------------------------

_AMOUNT_RE = re.compile(r"^金?(?:(?P<oku>[0-9,]+)億)?(?:(?P<man>[0-9,]+)万)?(?:(?P<en>[0-9,]+))?円$")


def parse_amount_yen(s: str) -> int | None:
    """「300万円」「2億7350万円」「金1,000,000円」→ 整数の円。読めなければ None。"""
    m = _AMOUNT_RE.match(normalize(s))
    if not m or not (m.group("oku") or m.group("man") or m.group("en")):
        return None
    total = 0
    if m.group("oku"):
        total += int(m.group("oku").replace(",", "")) * 100_000_000
    if m.group("man"):
        total += int(m.group("man").replace(",", "")) * 10_000
    if m.group("en"):
        total += int(m.group("en").replace(",", ""))
    return total


def format_amount_yen(n: int, style: str = "man") -> str:
    """整数の円 → 表記。style: "man"（300万円・2億7350万円）／ "comma"（1,000,000円）。"""
    if n < 0:
        raise ValueError("金額は負にしない")
    if style == "comma":
        return f"{n:,}円"
    if style != "man":
        raise ValueError(f"未知の style: {style}")
    if n % 10_000 != 0 or n == 0:
        return f"{n:,}円"
    man = n // 10_000
    if man >= 10_000:
        oku, man_rest = divmod(man, 10_000)
        return f"{oku}億{man_rest}万円" if man_rest else f"{oku}億円"
    return f"{man}万円"


# --- 割合 ---------------------------------------------------------------------

_RATIO_RE = re.compile(
    r"^(?:年)?(?:"
    r"(?P<wari>[0-9]+)割(?:(?P<bu>[0-9]+)分)?"
    r"|(?P<pct>[0-9]+(?:\.[0-9]+)?)(?:%|パーセント)"
    r")$"
)


def parse_ratio(s: str) -> tuple[int, int] | None:
    """「2割」「年14.6%」「90パーセント」→ (分子, 分母)。既約にはしない（表記を保つ）。"""
    m = _RATIO_RE.match(normalize(s))
    if not m:
        return None
    if m.group("wari"):
        num = int(m.group("wari")) * 10
        den = 100
        if m.group("bu"):
            num += int(m.group("bu"))
        return (num // 10, 10) if num % 10 == 0 else (num, 100)
    pct = m.group("pct")
    if "." in pct:
        int_part, frac = pct.split(".")
        den = 100 * (10 ** len(frac))
        return (int(int_part + frac), den)
    return (int(pct), 100)


def format_ratio(num: int, den: int, style: str = "percent", yearly: bool = False) -> str:
    """(分子, 分母) → 表記。style: "percent"（14.6%）／ "percent_kana"（3.6パーセント）／ "wari"（2割）。"""
    prefix = "年" if yearly else ""
    if style == "wari":
        if den == 10:
            return f"{prefix}{num}割"
        raise ValueError("割表記は分母 10 のみ")
    scaled_num = num * 100
    if scaled_num % den != 0:
        # 小数1〜3桁で表せる場合
        for digits in (1, 2, 3):
            if scaled_num * (10**digits) % den == 0:
                value = scaled_num * (10**digits) // den
                text = f"{value // (10**digits)}.{str(value % (10**digits)).zfill(digits)}"
                break
        else:
            raise ValueError(f"百分率で表せない: {num}/{den}")
    else:
        text = str(scaled_num // den)
    unit = "パーセント" if style == "percent_kana" else "%"
    return f"{prefix}{text}{unit}"


# --- 期間・日数 ----------------------------------------------------------------


@dataclass(frozen=True)
class Duration:
    """期間。unit は day / business_day / month / year。"""

    n: int
    unit: str


_DURATION_RE = re.compile(
    r"^(?P<n>[0-9]+)(?P<unit>営業日|日|か月|カ月|ヶ月|箇月|月|年)(?:間)?(?:以内|前|後)?$"
)
_UNIT_MAP = {"営業日": "business_day", "日": "day", "月": "month", "年": "year"}


def parse_duration(s: str) -> Duration | None:
    """「10日」「10営業日」「3か月」「5年間」「20日以内」→ Duration。"""
    m = _DURATION_RE.match(normalize(s))
    if not m:
        return None
    unit = m.group("unit")
    unit = _UNIT_MAP.get(unit, "month" if unit in ("か月", "カ月", "ヶ月", "箇月") else None)
    if unit is None:
        return None
    return Duration(int(m.group("n")), unit)


def format_duration(d: Duration) -> str:
    """Duration → 表記（「10日」「10営業日」「3か月」「2年」）。"""
    suffix = {"day": "日", "business_day": "営業日", "month": "か月", "year": "年"}[d.unit]
    return f"{d.n}{suffix}"


# --- 日付 ---------------------------------------------------------------------

_DATE_JA_RE = re.compile(r"^(?P<y>[0-9]{4})年(?P<m>[0-9]{1,2})月(?P<d>[0-9]{1,2})日$")
_DATE_ISO_RE = re.compile(r"^(?P<y>[0-9]{4})-(?P<m>[0-9]{2})-(?P<d>[0-9]{2})$")


def parse_date_ja(s: str) -> date | None:
    """「2031年4月6日」「２０２７年９月１４日」「2026-10-31」→ date。"""
    t = normalize(s)
    m = _DATE_JA_RE.match(t) or _DATE_ISO_RE.match(t)
    if not m:
        return None
    try:
        return date(int(m.group("y")), int(m.group("m")), int(m.group("d")))
    except ValueError:
        return None


def format_date_ja(d: date) -> str:
    """date → 「2031年4月6日」。"""
    return f"{d.year}年{d.month}月{d.day}日"


# --- その他（支払期日の指定・回数） ----------------------------------------------

_DOM_RE = re.compile(r"^(?:毎月|翌月|翌々月)?(?:(?P<day>[0-9]{1,2})日|(?P<eom>末日))$")


def parse_day_of_month(s: str) -> int | str | None:
    """「毎月5日」→ 5、「翌月末日」→ "end"。読めなければ None。"""
    m = _DOM_RE.match(normalize(s))
    if not m:
        return None
    return "end" if m.group("eom") else int(m.group("day"))


_COUNT_RE = re.compile(r"^(?:合計)?(?P<n>[0-9]+)回$")


def parse_count(s: str) -> int | None:
    """「合計4回」「3回」→ 整数。"""
    m = _COUNT_RE.match(normalize(s))
    return int(m.group("n")) if m else None


# --- 総合読取（検証ゲート G4 の読取側） -------------------------------------------

_HOURS_RE = re.compile(r"([0-9]+)時間")
_AMOUNT_TOKEN_RE = re.compile(r"金?[0-9,]*(?:億[0-9,]*)?(?:万)?[0-9,]*円")


def read_value(surface: str, value_type: str, unit: str | None):
    """紙面表記 → 仕様の値。value_type: int / ratio / date。読めなければ None。

    int の解釈は unit に従う（PERCENT は百分率の整数、DAY/MONTH/YEAR は期間、
    HOUR は時間数、COUNT は回数・件数、それ以外は金額）。
    """
    s = normalize(surface)
    if value_type == "date":
        d = parse_date_ja(s)
        return d.isoformat() if d else None
    if value_type == "ratio":
        return parse_ratio(s)
    if unit == "PERCENT":
        r = parse_ratio(s)
        if r and (r[0] * 100) % r[1] == 0:
            return r[0] * 100 // r[1]
        return None
    if unit == "PERMILLE":
        r = parse_ratio(s)
        if r and (r[0] * 1000) % r[1] == 0:
            return r[0] * 1000 // r[1]
        return None
    if unit in ("DAY", "MONTH", "YEAR"):
        accepted = {"DAY": ("day", "business_day"), "MONTH": ("month",), "YEAR": ("year",)}[unit]
        d = parse_duration(s)
        if d:
            return d.n if d.unit in accepted else None
        dom = parse_day_of_month(s)
        return dom if isinstance(dom, int) and unit == "DAY" else None
    if unit == "HOUR":
        m = _HOURS_RE.search(s)
        return int(m.group(1)) if m else None
    if unit == "COUNT":
        c = parse_count(s)
        if c is not None:
            return c
        m = re.search(r"([0-9]+)[回件個]", s)
        return int(m.group(1)) if m else None
    for m in _AMOUNT_TOKEN_RE.finditer(s):
        v = parse_amount_yen(m.group(0))
        if v is not None:
            return v
    t = s.replace(",", "")
    if t.isdigit():
        return int(t)
    return None
