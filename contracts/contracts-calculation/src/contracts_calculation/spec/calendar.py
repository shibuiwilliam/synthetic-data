from __future__ import annotations

import calendar
from datetime import date, timedelta


def end_of_month(d: date) -> date:
    return d.replace(day=calendar.monthrange(d.year, d.month)[1])


def add_months(d: date, n: int) -> date:
    """n か月後の応当日。応当日がない月は、その月の末日。"""
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    m += 1
    return date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def period_end(start: date, n: int, unit: str, include_start: bool) -> date:
    """start から n（日・月・年）の期間の満了日。

    include_start=True は start を1日目に数える。False は翌日から数える。
    月・年の期間は暦で数え、起算日に応当する日の前日に満了する。
    最後の月に応当する日がなければ、その月の末日に満了する。
    """
    first = start if include_start else start + timedelta(days=1)
    if unit == "day":
        return first + timedelta(days=n - 1)
    months = n * 12 if unit == "year" else n
    y, m = divmod(first.year * 12 + first.month - 1 + months, 12)
    m += 1
    last = calendar.monthrange(y, m)[1]
    if first.day > last:
        return date(y, m, last)
    return date(y, m, first.day) - timedelta(days=1)


def is_business_day(d: date, holidays: frozenset[date], closed: tuple = ()) -> bool:
    """土日、holidays、closed（年をまたげる月日の範囲。例 ((12, 29), (1, 3))）を除いた日。"""
    if d.weekday() >= 5 or d in holidays:
        return False
    md = (d.month, d.day)
    for a, b in closed:
        if (a <= md <= b) if a <= b else (md >= a or md <= b):
            return False
    return True


def next_business_day(d: date, holidays=frozenset(), closed=()) -> date:
    """d が営業日なら d。そうでなければ直後の営業日。"""
    while not is_business_day(d, holidays, closed):
        d += timedelta(days=1)
    return d


def prev_business_day(d: date, holidays=frozenset(), closed=()) -> date:
    """d が営業日なら d。そうでなければ直前の営業日。"""
    while not is_business_day(d, holidays, closed):
        d -= timedelta(days=1)
    return d


def add_business_days(d: date, n: int, holidays=frozenset(), closed=()) -> date:
    """d の翌日を1日目として数えた、n 営業日目の日。"""
    while n > 0:
        d += timedelta(days=1)
        if is_business_day(d, holidays, closed):
            n -= 1
    return d
