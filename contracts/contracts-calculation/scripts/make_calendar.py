"""packs/calendar/holidays_jp.json を決定的に生成する（実在ベースの固定版）。

- 日本の国民の祝日 2026〜2033 年。春分・秋分は近似式（1980〜2099 年用）による計算値。
- 振替休日（祝日が日曜のとき直後の平日）と国民の休日（祝日に挟まれた平日）を含める。
- 実行時に外部へ取りに行かない。作り直すときだけこのスクリプトを実行する。

実行: cd contracts-calculation && python3 scripts/make_calendar.py
"""

from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

YEARS = range(2026, 2034)


def _nth_monday(year: int, month: int, n: int) -> date:
    d = date(year, month, 1)
    offset = (7 - d.weekday()) % 7  # 最初の月曜まで
    return d + timedelta(days=offset + 7 * (n - 1))


def _equinox(year: int, spring: bool) -> date:
    base = 20.8431 if spring else 23.2488
    day = int(base + 0.242194 * (year - 1980)) - (year - 1980) // 4
    return date(year, 3 if spring else 9, day)


def holidays_of(year: int) -> dict[date, str]:
    h: dict[date, str] = {
        date(year, 1, 1): "元日",
        _nth_monday(year, 1, 2): "成人の日",
        date(year, 2, 11): "建国記念の日",
        date(year, 2, 23): "天皇誕生日",
        _equinox(year, True): "春分の日",
        date(year, 4, 29): "昭和の日",
        date(year, 5, 3): "憲法記念日",
        date(year, 5, 4): "みどりの日",
        date(year, 5, 5): "こどもの日",
        _nth_monday(year, 7, 3): "海の日",
        date(year, 8, 11): "山の日",
        _nth_monday(year, 9, 3): "敬老の日",
        _equinox(year, False): "秋分の日",
        _nth_monday(year, 10, 2): "スポーツの日",
        date(year, 11, 3): "文化の日",
        date(year, 11, 23): "勤労感謝の日",
    }
    # 振替休日：祝日が日曜のとき、その後の最初の「祝日でない日」
    for d in sorted(h):
        if d.weekday() == 6:
            sub = d + timedelta(days=1)
            while sub in h:
                sub += timedelta(days=1)
            h[sub] = "休日（振替）"
    # 国民の休日：前日と翌日が祝日である平日（敬老の日と秋分の日の間に生じうる）
    for d in sorted(h):
        nxt = d + timedelta(days=2)
        if nxt in h:
            mid = d + timedelta(days=1)
            if mid not in h and mid.weekday() != 6:
                h[mid] = "休日（国民の休日）"
    return h


def main() -> None:
    out = {
        "note": (
            "日本の国民の祝日 2026〜2033 年の固定版。出典は国民の祝日に関する法律の規則を機械適用したもの。"
            "春分の日・秋分の日は近似式による計算値であり、官報告示と1日ずれる可能性がある。"
            "データセットの評価は本ファイルを入力として行うため、評価の再現性はこのファイルで閉じる。"
        ),
        "generated_by": "scripts/make_calendar.py",
        "years": {},
    }
    for y in YEARS:
        out["years"][str(y)] = {d.isoformat(): name for d, name in sorted(holidays_of(y).items())}
    path = Path(__file__).resolve().parent.parent / "packs" / "calendar" / "holidays_jp.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{path} を書き出した（{sum(len(v) for v in out['years'].values())} 日）")


if __name__ == "__main__":
    main()
