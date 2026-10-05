"""付録Bの暦の設例（K11〜K14）。期待値は DESIGN.md 付録Bの値をそのまま使う。"""

from datetime import date

from contracts_calculation.spec.calendar import (
    add_business_days,
    add_months,
    end_of_month,
    next_business_day,
    period_end,
    prev_business_day,
)

CLOSED = (((12, 29), (1, 3)),)  # 12月29日から翌年1月3日まで


# --- K11 締日と支払期日（月末締め、翌月末日払い） ---------------------------------


def test_k11_payment_due_basic() -> None:
    due = end_of_month(add_months(date(2026, 9, 30), 1))
    assert due == date(2026, 10, 31)  # 土曜日


def test_k11_adjust_prev_business_day() -> None:
    due = end_of_month(add_months(date(2026, 9, 30), 1))
    assert prev_business_day(due) == date(2026, 10, 30)  # 金曜日


def test_k11_adjust_next_business_day() -> None:
    due = end_of_month(add_months(date(2026, 9, 30), 1))
    assert next_business_day(due) == date(2026, 11, 2)  # 月曜日


def test_k11_no_adjustment_needed() -> None:
    due = end_of_month(add_months(date(2026, 10, 31), 1))
    assert due == date(2026, 11, 30)  # 月曜日。調整なし
    assert prev_business_day(due) == due
    assert next_business_day(due) == due


# --- K12 期間の満了日 ---------------------------------------------------------


def test_k12_one_year_including_start() -> None:
    assert period_end(date(2026, 10, 1), 1, "year", True) == date(2027, 9, 30)


def test_k12_one_year_excluding_start() -> None:
    assert period_end(date(2026, 10, 1), 1, "year", False) == date(2027, 10, 1)


def test_k12_one_month_no_anniversary_day() -> None:
    assert period_end(date(2027, 1, 31), 1, "month", True) == date(2027, 2, 28)


def test_k12_one_month_leap_year() -> None:
    assert period_end(date(2028, 1, 31), 1, "month", True) == date(2028, 2, 29)


# --- K13 更新と通知期限（満了日の3か月前まで） ---------------------------------


def test_k13_three_months_before() -> None:
    assert add_months(date(2027, 9, 30), -3) == date(2027, 6, 30)


def test_k13_three_months_before_aug31() -> None:
    assert add_months(date(2027, 8, 31), -3) == date(2027, 5, 31)


def test_k13_three_months_before_may31() -> None:
    assert add_months(date(2027, 5, 31), -3) == date(2027, 2, 28)


# --- K14 検査期限（納入日の翌日から10営業日。年末年始休業） ----------------------


def test_k14_inspection_deadline_over_year_end() -> None:
    assert add_business_days(date(2026, 12, 22), 10, frozenset(), CLOSED) == date(2027, 1, 11)


def test_k14_inspection_deadline_with_holiday() -> None:
    holidays = frozenset({date(2027, 1, 11)})
    assert add_business_days(date(2026, 12, 22), 10, holidays, CLOSED) == date(2027, 1, 12)
