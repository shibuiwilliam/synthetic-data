"""参照インタプリタ。**意味論の正本**であり、生成コードの比較基準になる。

意味論（三値・厳密）:
  * `None` は「不明」。算術・比較・min/max・表引き・日付演算は、引数に不明があれば不明。
  * `and` / `or` は Kleene の三値論理（確定できるときだけ確定する）。
  * `if` は条件が不明なら不明。条件が確定していれば選ばれた枝の値。
  * `coalesce` だけが `None` を「記載なし」として既定値に置き換える。
  * `muldiv(a, b, c)` = a×b÷c を整数で返す。端数処理は必須指定。負数・ゼロ除算は不明。
  * `round_to(x, u)` = x を単位 u で丸める。u が 0 以下なら不明。負の x も Python の床除算に従う。
  * 日付は `datetime.date`。`add_months` は月末を丸める（1/31 + 1 か月 = 2/28）。

意味論を変えるときは `codegen/python.py` の `_PRELUDE` を同時に直し、
`tests/unit/test_ops_coverage.py` の照合で両者が一致することを確かめる。
"""

from __future__ import annotations

import calendar
import datetime as dt

from .validate import RuleSet


def evaluate(rs: RuleSet, rule_id: str, inputs: dict, variant: str | None = None, expr: dict | None = None):
    if expr is None:
        expr = rs.full_expr(rule_id, variant)
    return _ev(rs, expr, inputs, None)


def muldiv(a, b, c, rounding):
    if a is None or b is None or c is None or c == 0 or a < 0 or b < 0 or c < 0:
        return None
    n = a * b
    if rounding == "floor":
        return n // c
    if rounding == "ceil":
        return -((-n) // c)
    return (2 * n + c) // (2 * c)  # half_up


def round_to(x, unit, rounding):
    """x を単位 unit の倍数に丸める。"""
    if x is None or unit is None or unit <= 0:
        return None
    if rounding == "floor":
        return (x // unit) * unit
    if rounding == "ceil":
        return -((-x) // unit) * unit
    return ((2 * x + unit) // (2 * unit)) * unit  # half_up


def add_days(d, n):
    if d is None or n is None:
        return None
    return d + dt.timedelta(days=n)


def add_months(d, n):
    """月末を丸める（1 月 31 日に 1 か月を加えると 2 月末日）。"""
    if d is None or n is None:
        return None
    total = (d.year * 12 + d.month - 1) + n
    y, m = divmod(total, 12)
    m += 1
    return dt.date(y, m, min(d.day, calendar.monthrange(y, m)[1]))


def days_between(a, b):
    """後の日付 b から前の日付 a までの日数（b − a）。"""
    if a is None or b is None:
        return None
    return (b - a).days


def end_of_month(d):
    if d is None:
        return None
    return dt.date(d.year, d.month, calendar.monthrange(d.year, d.month)[1])


def lookup(table: dict, key):
    if key is None:
        return None
    if table["mode"] == "exact":
        for k, v, *_ in table["rows"]:
            if k == key:
                return v
        return None
    for k, v, *_ in table["rows"]:  # step_le: キー以上で最小の行
        if k >= key:
            return v
    return None


def _ev(rs: RuleSet, e: dict, env: dict, item: dict | None):
    if "lit" in e:
        return e["lit"]
    if "param" in e:
        return rs.params[e["param"]]["value"]
    if "var" in e:
        return env.get(e["var"])
    if "item" in e:
        return item.get(e["item"])
    op = e["op"]
    if op == "agg":
        vals = [_ev(rs, e["args"][0], env, it) for it in (env.get(e["over"]) or [])]
        if any(v is None for v in vals):
            return None
        if e["func"] == "sum":
            return sum(vals)
        return max(vals) if vals else None
    a = [_ev(rs, x, env, item) for x in e["args"]]
    if op == "and":
        return False if any(x is False for x in a) else None if any(x is None for x in a) else True
    if op == "or":
        return True if any(x is True for x in a) else None if any(x is None for x in a) else False
    if op == "not":
        return None if a[0] is None else not a[0]
    if op == "if":
        return None if a[0] is None else a[1] if a[0] else a[2]
    if op == "coalesce":
        return a[0] if a[0] is not None else a[1]
    if op == "lookup":
        return lookup(rs.tables[e["table"]], a[0])
    if op == "muldiv":
        return muldiv(a[0], a[1], a[2], e["rounding"])
    if op == "round_to":
        return round_to(a[0], a[1], e["rounding"])
    if op == "add_days":
        return add_days(a[0], a[1])
    if op == "add_months":
        return add_months(a[0], a[1])
    if op == "days_between":
        return days_between(a[0], a[1])
    if op == "end_of_month":
        return end_of_month(a[0])
    if any(x is None for x in a):
        return None
    if op == "add":
        return _sum(a)
    if op == "sub":
        return a[0] - a[1]
    if op == "mul":
        out = 1
        for x in a:
            out *= x
        return out
    if op == "min":
        return min(a)
    if op == "max":
        return max(a)
    return {
        "lt": a[0] < a[1],
        "le": a[0] <= a[1],
        "gt": a[0] > a[1],
        "ge": a[0] >= a[1],
        "eq": a[0] == a[1],
        "ne": a[0] != a[1],
    }[op]


def _sum(a: list):
    """日付＋日数の加算も通るように、0 からではなく先頭から足す。"""
    out = a[0]
    for x in a[1:]:
        out = out + dt.timedelta(days=x) if isinstance(out, dt.date) else out + x
    return out
