"""参照インタプリタ（意味論の正本。DESIGN.md §12.3）。

- 金額は整数の円。float は現れない。
- 割り算は muldiv だけ。割合（ratio）の値は muldiv の乗数・除数の位置にだけ現れる。
- 不明は None。算術・比較・表引き・日付の演算は、引数に不明があれば不明を返す。
- 真偽は三値。and は偽が 1 つでもあれば偽、or は真が 1 つでもあれば真、それ以外で不明があれば不明。
- if は条件が不明なら不明。coalesce は最初の非 None。
- ゼロ除算と、表にないキーは不明。
"""

from __future__ import annotations

from datetime import date
from typing import Any

from . import calendar as cal
from .model import CalcSpec, Rule, SpecTable


class SpecError(Exception):
    """仕様が意味論に反している（validate で落とすべきものが実行まで来た）。"""


_RATIO = "ratio"  # ratio 値の印：("ratio", num, den)


def parse_input_value(decl_type: str, value: Any) -> Any:
    """JSON のテストケース・設例の入力値を実行時の値へ（date 文字列 → date）。"""
    if value is None:
        return None
    if decl_type == "date":
        return date.fromisoformat(value)
    if decl_type == "list":
        return list(value)
    return value


def eval_rule(
    spec: CalcSpec,
    rule: Rule,
    inputs: dict[str, Any],
    holidays: frozenset[date] = frozenset(),
) -> Any:
    """ルールを評価する。inputs の date は date 型または "YYYY-MM-DD" 文字列。"""
    env: dict[str, Any] = {}
    for name, decl in rule.inputs.items():
        raw = inputs.get(name)
        if isinstance(raw, str) and decl.type == "date":
            raw = date.fromisoformat(raw)
        env[name] = raw
    ev = _Evaluator(spec, rule, env, holidays)
    steps: dict[str, Any] = {}
    for step in rule.steps:
        steps[step.name] = ev.eval(step.expr, steps)
    result = steps[rule.output["step"]]
    if isinstance(result, tuple) and result and result[0] == _RATIO:
        raise SpecError("出力が割合のまま（割合は muldiv で整数に落とす）")
    return result


class _Evaluator:
    def __init__(self, spec: CalcSpec, rule: Rule, env: dict, holidays: frozenset[date]) -> None:
        self.spec = spec
        self.rule = rule
        self.env = env
        self.holidays = holidays
        self.closed = spec.calendar.closed if spec.calendar else ()

    # --- 葉 -------------------------------------------------------------------

    def eval(self, expr: dict, steps: dict, item: Any = _RATIO) -> Any:  # item 既定は「無し」の印
        if "lit" in expr:
            v = expr["lit"]
            if isinstance(v, str):
                try:
                    return date.fromisoformat(v)
                except ValueError:
                    return v  # enum 値
            return v
        if "var" in expr:
            return self.env[expr["var"]]
        if "param" in expr:
            p = self.spec.params[expr["param"]]
            if p.type == _RATIO:
                return (_RATIO, p.num, p.den)
            if p.type == "date":
                return date.fromisoformat(p.value)
            return p.value
        if "step" in expr:
            return steps[expr["step"]]
        if "item" in expr:
            if item is _RATIO:
                raise SpecError("item は agg の中でだけ使える")
            return item
        return self._eval_op(expr, steps, item)

    # --- 演算 -----------------------------------------------------------------

    def _eval_op(self, expr: dict, steps: dict, item: Any) -> Any:
        op = expr["op"]
        args = expr.get("args", [])

        if op == "coalesce":
            for a in args:
                v = self.eval(a, steps, item)
                if v is not None:
                    return v
            return None
        if op == "if":
            cond = self.eval(args[0], steps, item)
            if cond is None:
                return None
            return self.eval(args[1] if cond else args[2], steps, item)
        if op == "case":
            *pairs, default = args
            for i in range(0, len(pairs), 2):
                cond = self.eval(pairs[i], steps, item)
                if cond is None:
                    return None
                if cond:
                    return self.eval(pairs[i + 1], steps, item)
            return self.eval(default, steps, item)
        if op == "and":
            vals = [self.eval(a, steps, item) for a in args]
            if any(v is False for v in vals):
                return False
            if any(v is None for v in vals):
                return None
            return True
        if op == "or":
            vals = [self.eval(a, steps, item) for a in args]
            if any(v is True for v in vals):
                return True
            if any(v is None for v in vals):
                return None
            return False
        if op == "not":
            v = self.eval(args[0], steps, item)
            return None if v is None else (not v)
        if op == "agg":
            return self._eval_agg(expr, steps)

        # 以降は None 伝播の演算
        vals = [self.eval(a, steps, item) for a in args]
        if any(v is None for v in vals):
            return None

        if op == "muldiv":
            return _muldiv(vals[0], vals[1], vals[2], expr["rounding"])
        if any(isinstance(v, tuple) and v and v[0] == _RATIO for v in vals):
            raise SpecError(f"割合は muldiv の中でだけ使える（{op} に渡された）")

        if op == "add":
            return sum(vals)
        if op == "sub":
            return vals[0] - vals[1]
        if op == "mul":
            out = 1
            for v in vals:
                out *= v
            return out
        if op == "round_to":
            return _round_to(vals[0], expr["unit_value"], expr["rounding"])
        if op == "min":
            return min(vals)
        if op == "max":
            return max(vals)
        if op in ("lt", "le", "gt", "ge", "eq", "ne"):
            a, b = vals
            return {
                "lt": a < b,
                "le": a <= b,
                "gt": a > b,
                "ge": a >= b,
                "eq": a == b,
                "ne": a != b,
            }[op]
        if op == "lookup":
            return self._lookup(self.spec.tables[expr["table"]], expr["mode"], vals[0])
        if op == "tiered":
            return _tiered(self.spec.tables[expr["table"]], expr["method"], vals[0])

        # 日付
        if op == "add_days":
            return vals[0] + _days(vals[1])
        if op == "add_months":
            return cal.add_months(vals[0], vals[1])
        if op == "end_of_month":
            return cal.end_of_month(vals[0])
        if op == "set_day":
            # 日の指定（「翌月5日」の 5）。指定日がその月に無ければ末日。
            import calendar as _c

            d, day = vals
            return d.replace(day=min(day, _c.monthrange(d.year, d.month)[1]))
        if op == "period_end":
            return cal.period_end(vals[0], vals[1], expr["unit"], expr["include_start"])
        if op == "days_between":
            return (vals[1] - vals[0]).days
        if op == "days_in_month":
            import calendar as _c

            return _c.monthrange(vals[0].year, vals[0].month)[1]
        if op == "is_business_day":
            return cal.is_business_day(vals[0], self.holidays, self.closed)
        if op == "next_business_day":
            return cal.next_business_day(vals[0], self.holidays, self.closed)
        if op == "prev_business_day":
            return cal.prev_business_day(vals[0], self.holidays, self.closed)
        if op == "add_business_days":
            return cal.add_business_days(vals[0], vals[1], self.holidays, self.closed)
        raise SpecError(f"未知の演算: {op}")

    def _eval_agg(self, expr: dict, steps: dict) -> Any:
        items = self.env.get(expr["over"])
        if items is None:
            return None
        mode = expr["mode"]
        picked: list[Any] = []
        for it in items:
            if "filter" in expr:
                keep = self.eval(expr["filter"], steps, item=it)
                if keep is None:
                    return None  # 判定できない要素があれば全体が不明
                if not keep:
                    continue
            v = self.eval(expr["map"], steps, item=it) if "map" in expr else it
            if v is None and mode not in ("any", "all"):
                return None
            picked.append(v)
        if mode == "sum":
            return sum(picked)
        if mode == "count":
            return len(picked)
        if mode == "max":
            return max(picked) if picked else None
        if mode == "min":
            return min(picked) if picked else None
        if mode == "any":
            if any(v is True for v in picked):
                return True
            if any(v is None for v in picked):
                return None
            return False
        if mode == "all":
            if any(v is False for v in picked):
                return False
            if any(v is None for v in picked):
                return None
            return True
        raise SpecError(f"未知の agg mode: {mode}")

    def _lookup(self, table: SpecTable, mode: str, key: int) -> Any:
        if mode == "exact":
            for row in table.rows:
                if row.upto == key:
                    return row.value
            return None  # 表にないキーは不明
        # step：key 以下の最大の upto 行（階段）
        for row in table.rows:
            if row.upto is None or key <= row.upto:
                return row.value
        return None


# --- 数値 ---------------------------------------------------------------------


def _days(n: int):
    from datetime import timedelta

    return timedelta(days=n)


def _expand(value, into_num: bool) -> tuple[int, int]:
    """muldiv の乗数・除数を (分子, 分母) に展開する。"""
    if isinstance(value, tuple) and value and value[0] == _RATIO:
        _, num, den = value
        return (num, den) if into_num else (den, num)
    return (value, 1) if into_num else (1, value)


def _muldiv(a, b, c, rounding: str):
    if isinstance(a, tuple):
        raise SpecError("muldiv の被乗数に割合は置けない")
    bn, bd = _expand(b, into_num=True)
    cn, cd = _expand(c, into_num=False)  # ÷c なので逆数
    num = a * bn * cn
    den = bd * cd
    if den == 0:
        return None  # ゼロ除算は不明
    if den < 0:
        num, den = -num, -den
    return _round_frac(num, den, rounding)


def _round_frac(num: int, den: int, rounding: str) -> int:
    if rounding == "floor":
        return num // den
    if rounding == "ceil":
        return -((-num) // den)
    if rounding == "half_up":
        return (2 * num + den) // (2 * den)
    raise SpecError(f"未知の丸め: {rounding}")


def _round_to(x: int, unit_value: int, rounding: str) -> int:
    return _round_frac(x, unit_value, rounding) * unit_value


def _tiered(table: SpecTable, method: str, qty: int):
    rows = table.rows
    if method == "all_units":
        for row in rows:
            if row.upto is None or qty <= row.upto:
                return qty * row.value
        return None
    # marginal：各区分に属する数量 × 当該区分の単価の合計
    total = 0
    prev_upto = 0
    for row in rows:
        if row.upto is None:
            span = qty - prev_upto
        else:
            span = min(qty, row.upto) - prev_upto
        if span > 0:
            total += span * row.value
        if row.upto is not None:
            prev_upto = row.upto
        if row.upto is not None and qty <= row.upto:
            break
    return total
