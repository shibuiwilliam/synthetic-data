"""計算仕様 → 正解プログラム（Python モジュール）の生成（DESIGN.md §13.1）。

- 1 文書 1 モジュール。標準ライブラリだけで単独で動く（暦の関数を同梱する）。
- 1 ルール 1 関数。引数はキーワード専用。手順の名前が変数名になる。
- 入力が None（不明）で結果を確定できないときは None を返す
  （optional 宣言の入力は guard せず、coalesce で既定値に落とす）。
- 定数は根拠（単位 ID か条の表記）をコメントに付けてモジュールの先頭に置く。
"""

from __future__ import annotations

from ..spec.model import BUSINESS_DAY_OPS, OPS_DATE, CalcSpec, Rule

_TYPE_HINTS = {"int": "int", "bool": "bool", "date": "date", "enum": "str", "list": "list[int]"}

_CALENDAR_FUNCS = '''
def _end_of_month(d: date) -> date:
    return d.replace(day=_calendar.monthrange(d.year, d.month)[1])


def _add_months(d: date, n: int) -> date:
    """n か月後の応当日。応当日がない月は、その月の末日。"""
    y, m = divmod(d.year * 12 + d.month - 1 + n, 12)
    m += 1
    return date(y, m, min(d.day, _calendar.monthrange(y, m)[1]))


def _set_day(d: date, day: int) -> date:
    """日の指定。指定日がその月に無ければ末日。"""
    return d.replace(day=min(day, _calendar.monthrange(d.year, d.month)[1]))


def _period_end(start: date, n: int, unit: str, include_start: bool) -> date:
    first = start if include_start else start + timedelta(days=1)
    if unit == "day":
        return first + timedelta(days=n - 1)
    months = n * 12 if unit == "year" else n
    y, m = divmod(first.year * 12 + first.month - 1 + months, 12)
    m += 1
    last = _calendar.monthrange(y, m)[1]
    if first.day > last:
        return date(y, m, last)
    return date(y, m, first.day) - timedelta(days=1)


def _is_business_day(d: date, holidays: frozenset, closed: tuple = ()) -> bool:
    if d.weekday() >= 5 or d in holidays:
        return False
    md = (d.month, d.day)
    for a, b in closed:
        if (a <= md <= b) if a <= b else (md >= a or md <= b):
            return False
    return True


def _next_business_day(d: date, holidays=frozenset(), closed=()) -> date:
    while not _is_business_day(d, holidays, closed):
        d += timedelta(days=1)
    return d


def _prev_business_day(d: date, holidays=frozenset(), closed=()) -> date:
    while not _is_business_day(d, holidays, closed):
        d -= timedelta(days=1)
    return d


def _add_business_days(d: date, n: int, holidays=frozenset(), closed=()) -> date:
    while n > 0:
        d += timedelta(days=1)
        if _is_business_day(d, holidays, closed):
            n -= 1
    return d
'''


_LOGIC3_FUNCS = '''
def _and3(*vs):
    """三値の and（偽が 1 つでもあれば偽、それ以外で不明があれば不明）。"""
    if any(v is False for v in vs):
        return False
    if any(v is None for v in vs):
        return None
    return True


def _or3(*vs):
    """三値の or（真が 1 つでもあれば真、それ以外で不明があれば不明）。"""
    if any(v is True for v in vs):
        return True
    if any(v is None for v in vs):
        return None
    return False


def _not3(v):
    return None if v is None else (not v)


def _cmp3(op, a, b):
    if a is None or b is None:
        return None
    return {"lt": a < b, "le": a <= b, "gt": a > b, "ge": a >= b, "eq": a == b, "ne": a != b}[op]


def _if3(c, t, e):
    return None if c is None else (t if c else e)


def _days_between3(a, b):
    return None if a is None or b is None else (b - a).days


def _add3(*vs):
    return None if any(v is None for v in vs) else sum(vs)


def _sub3(a, b):
    return None if a is None or b is None else a - b


def _mul3(*vs):
    if any(v is None for v in vs):
        return None
    out = 1
    for v in vs:
        out *= v
    return out


def _min3(*vs):
    return None if any(v is None for v in vs) else min(vs)


def _max3(*vs):
    return None if any(v is None for v in vs) else max(vs)


def _muldiv3(a, bn, bd, cn, cd, rounding):
    """a × (bn/bd) ÷ (cn/cd) を整数で。いずれかが None なら None、分母 0 も None。"""
    if any(v is None for v in (a, bn, bd, cn, cd)):
        return None
    num = a * bn * cd
    den = bd * cn
    if den == 0:
        return None
    if den < 0:
        num, den = -num, -den
    if rounding == "floor":
        return num // den
    if rounding == "ceil":
        return -((-num) // den)
    return (2 * num + den) // (2 * den)
'''

_TABLE_FUNCS = """
def _tiered_all_units(rows: tuple, qty):
    if qty is None:
        return None
    for upto, price in rows:
        if upto is None or qty <= upto:
            return qty * price
    raise ValueError("表に該当する区分が無い")


def _tiered_marginal(rows: tuple, qty):
    if qty is None:
        return None
    total = 0
    prev = 0
    for upto, price in rows:
        span = (qty - prev) if upto is None else (min(qty, upto) - prev)
        if span > 0:
            total += span * price
        if upto is not None:
            prev = upto
            if qty <= upto:
                break
    return total


def _lookup_step(rows: tuple, key):
    if key is None:
        return None
    for upto, value in rows:
        if upto is None or key <= upto:
            return value
    return None


def _lookup_exact(rows: tuple, key):
    if key is None:
        return None
    for k, value in rows:
        if k == key:
            return value
    return None
"""


def generate_module(spec: CalcSpec, citations: dict[str, str] | None = None) -> str:
    """仕様からモジュールのソースを作る。citations は単位 ID → 紙面表記（第12条第1項 など）。"""
    gen = _Generator(spec, citations or {})
    return gen.build()


class _Generator:
    def __init__(self, spec: CalcSpec, citations: dict[str, str]) -> None:
        self.spec = spec
        self.citations = citations
        self.used_ops: set[str] = set()
        for rule in spec.rules:
            _collect_ops(rule, self.used_ops)

    # --- モジュール全体 ----------------------------------------------------------

    def build(self) -> str:
        cid = self.spec.document.get("content_id", "")
        lines: list[str] = []
        lines.append(f'"""契約書 {cid} の計算・判定の正解プログラム（自動生成。手で編集しない）。"""')
        lines.append("")
        lines.append(
            "from datetime import date, timedelta" if self._needs_dates() else "from datetime import date"
        )
        if self._needs_calendar_module():
            lines.append("import calendar as _calendar")
        lines.append("")
        lines.append("")
        for name, p in self.spec.params.items():
            lines.append(self._param_line(name, p))
        for name, t in self.spec.tables.items():
            rows = ", ".join(f"({r.upto!r}, {r.value!r})" for r in t.rows)
            lines.append(f"T_{name.upper()} = ({rows},)" + self._source_comment(t.source, t.unit))
        if self.spec.calendar and self.spec.calendar.closed:
            closed = ", ".join(f"(({a[0]}, {a[1]}), ({b[0]}, {b[1]}))" for a, b in self.spec.calendar.closed)
            lines.append(f"P_CLOSED = ({closed},)" + self._source_comment(self.spec.calendar.source, None))
        lines.append("")
        if (
            self.used_ops & (OPS_DATE - {"days_between", "add_days", "days_in_month"})
            or self._needs_calendar_module()
        ):
            lines.append(_CALENDAR_FUNCS)
        if self.used_ops & {"tiered", "lookup"}:
            lines.append(_TABLE_FUNCS)
        needs_three = False
        for r in self.spec.rules:
            r_ops: set[str] = set()
            _collect_ops(r, r_ops)
            if r.output.get("type") == "bool" or r_ops & {"if", "case", "coalesce"}:
                needs_three = True
        if needs_three:
            lines.append(_LOGIC3_FUNCS)
        for rule in self.spec.rules:
            lines.append("")
            lines.extend(self._function(rule))
        return "\n".join(lines).rstrip() + "\n"

    def _needs_dates(self) -> bool:
        return bool(self.used_ops & OPS_DATE)

    def _needs_calendar_module(self) -> bool:
        return bool(
            self.used_ops & {"end_of_month", "add_months", "period_end", "days_in_month"}
            | (self.used_ops & BUSINESS_DAY_OPS)
        )

    def _source_comment(self, source, surface_or_unit) -> str:
        parts = []
        if surface_or_unit:
            parts.append(str(surface_or_unit))
        if source:
            where = self.citations.get(source.unit, source.unit)
            parts.append(f"根拠: {where}")
        return ("  # " + "  ".join(parts)) if parts else ""

    def _param_line(self, name: str, p) -> str:
        const = f"P_{name.upper()}"
        if p.type == "ratio":
            value = f"({p.num}, {p.den})"
        elif p.type == "date":
            y, m, d = p.value.split("-")
            value = f"date({int(y)}, {int(m)}, {int(d)})"
        else:
            value = repr(p.value)
        comment_parts = []
        if p.surface:
            comment_parts.append(p.surface)
        if p.source:
            where = self.citations.get(p.source.unit, p.source.unit)
            comment_parts.append(f"根拠: {where}")
        comment = ("  # " + "  ".join(comment_parts)) if comment_parts else ""
        return f"{const} = {value}{comment}"

    # --- 関数 1 本 ----------------------------------------------------------------

    def _function(self, rule: Rule) -> list[str]:
        ops: set[str] = set()
        _collect_ops(rule, ops)
        uses_calendar = bool(ops & BUSINESS_DAY_OPS)

        args = []
        for name, decl in rule.inputs.items():
            hint = _TYPE_HINTS[decl.type]
            args.append(f"{name}: {hint} | None = None")
        if uses_calendar:
            args.append("holidays: frozenset = frozenset()")
        signature = f"(*, {', '.join(args)})" if args else "()"
        out_hint = _TYPE_HINTS.get(rule.output.get("type", "int"), "int")

        where = "、".join(self.citations.get(s.unit, s.unit) for s in rule.sources) or "仕様"
        doc = f"{rule.title}（{where}）。"
        if rule.parties:
            doc += f"{rule.parties['payer']}が{rule.parties['payee']}に支払う。"

        three_valued = rule.output.get("type") == "bool" or bool(ops & {"if", "case", "coalesce"})
        lines = [f"def {rule.function}{signature} -> {out_hint} | None:"]
        lines.append(f'    """{doc}"""')
        required = [] if three_valued else [n for n, d in rule.inputs.items() if not d.optional]
        if required:
            cond = " or ".join(f"{n} is None" for n in required)
            lines.append(f"    if {cond}:")
            lines.append("        return None")
        for step in rule.steps:
            expr_src = self._compile(step.expr, rule, three_valued=three_valued)
            lines.append(f"    {step.name} = {expr_src}  # {step.label}")
        lines.append(f"    return {rule.output['step']}")
        lines.append("")
        return lines

    # --- 式 → Python ソース ---------------------------------------------------------

    def _compile(
        self, expr: dict, rule: Rule, item_var: str | None = None, three_valued: bool = False
    ) -> str:
        if "lit" in expr:
            v = expr["lit"]
            if isinstance(v, str):
                try:
                    y, m, d = v.split("-")
                    return f"date({int(y)}, {int(m)}, {int(d)})"
                except ValueError:
                    return repr(v)
            return repr(v)
        if "var" in expr:
            return expr["var"]
        if "param" in expr:
            return f"P_{expr['param'].upper()}"
        if "step" in expr:
            return expr["step"]
        if "item" in expr:
            if item_var is None:
                raise ValueError("item は agg の中でだけ使える")
            return item_var

        op = expr["op"]
        args = expr.get("args", [])

        def c(e: dict) -> str:
            return self._compile(e, rule, item_var, three_valued)

        if op == "add":
            if three_valued:
                return "_add3(" + ", ".join(c(a) for a in args) + ")"
            return "(" + " + ".join(c(a) for a in args) + ")"
        if op == "sub":
            if three_valued:
                return f"_sub3({c(args[0])}, {c(args[1])})"
            return f"({c(args[0])} - {c(args[1])})"
        if op == "mul":
            if three_valued:
                return "_mul3(" + ", ".join(c(a) for a in args) + ")"
            return "(" + " * ".join(c(a) for a in args) + ")"
        if op == "muldiv":
            return self._compile_muldiv(args, expr["rounding"], rule, item_var, three_valued)
        if op == "round_to":
            u = expr["unit_value"]
            x = c(args[0])
            if three_valued:
                return f"(None if {x} is None else {self._compile(expr, rule, item_var, False)})"
            body = {
                "floor": f"(({x}) // {u}) * {u}",
                "ceil": f"-((-({x})) // {u}) * {u}",
                "half_up": f"((2 * ({x}) + {u}) // (2 * {u})) * {u}",
            }[expr["rounding"]]
            return f"({body})"
        if op in ("min", "max"):
            if three_valued:
                return f"_{op}3(" + ", ".join(c(a) for a in args) + ")"
            return f"{op}(" + ", ".join(c(a) for a in args) + ")"
        if op in ("lt", "le", "gt", "ge", "eq", "ne"):
            if three_valued:
                return f"_cmp3({op!r}, {c(args[0])}, {c(args[1])})"
            sym = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "==", "ne": "!="}[op]
            return f"({c(args[0])} {sym} {c(args[1])})"
        if op == "and":
            if three_valued:
                return "_and3(" + ", ".join(c(a) for a in args) + ")"
            return "(" + " and ".join(c(a) for a in args) + ")"
        if op == "or":
            if three_valued:
                return "_or3(" + ", ".join(c(a) for a in args) + ")"
            return "(" + " or ".join(c(a) for a in args) + ")"
        if op == "not":
            return f"_not3({c(args[0])})" if three_valued else f"(not {c(args[0])})"
        if op == "if":
            if three_valued:
                return f"_if3({c(args[0])}, {c(args[1])}, {c(args[2])})"
            return f"({c(args[1])} if {c(args[0])} else {c(args[2])})"
        if op == "case":
            *pairs, default = args
            src = c(default)
            for i in range(len(pairs) - 2, -1, -2):
                src = f"({c(pairs[i + 1])} if {c(pairs[i])} else {src})"
            return src
        if op == "coalesce":
            srcs = [c(a) for a in args]
            out = srcs[-1]
            for s in reversed(srcs[:-1]):
                out = f"({s} if {s} is not None else {out})"
            return out
        if op == "lookup":
            fn = "_lookup_exact" if expr["mode"] == "exact" else "_lookup_step"
            return f"{fn}(T_{expr['table'].upper()}, {c(args[0])})"
        if op == "tiered":
            fn = "_tiered_all_units" if expr["method"] == "all_units" else "_tiered_marginal"
            return f"{fn}(T_{expr['table'].upper()}, {c(args[0])})"
        if op == "agg":
            src = self._compile_agg(expr, rule)
            if three_valued:
                return f"(None if {expr['over']} is None else {src})"
            return src

        # 日付
        if op == "add_days":
            return f"({c(args[0])} + timedelta(days={c(args[1])}))"
        if op == "add_months":
            return f"_add_months({c(args[0])}, {c(args[1])})"
        if op == "end_of_month":
            return f"_end_of_month({c(args[0])})"
        if op == "set_day":
            return f"_set_day({c(args[0])}, {c(args[1])})"
        if op == "period_end":
            return f"_period_end({c(args[0])}, {c(args[1])}, {expr['unit']!r}, {expr['include_start']!r})"
        if op == "days_between":
            if three_valued:
                return f"_days_between3({c(args[0])}, {c(args[1])})"
            return f"({c(args[1])} - {c(args[0])}).days"
        if op == "days_in_month":
            return f"_calendar.monthrange({c(args[0])}.year, {c(args[0])}.month)[1]"
        closed = "P_CLOSED" if (self.spec.calendar and self.spec.calendar.closed) else "()"
        if op == "is_business_day":
            return f"_is_business_day({c(args[0])}, holidays, {closed})"
        if op == "next_business_day":
            return f"_next_business_day({c(args[0])}, holidays, {closed})"
        if op == "prev_business_day":
            return f"_prev_business_day({c(args[0])}, holidays, {closed})"
        if op == "add_business_days":
            return f"_add_business_days({c(args[0])}, {c(args[1])}, holidays, {closed})"
        raise ValueError(f"未知の演算: {op}")

    def _compile_muldiv(
        self, args: list, rounding: str, rule: Rule, item_var: str | None, three_valued: bool = False
    ) -> str:
        if three_valued:
            parts = [self._compile(args[0], rule, item_var, True)]
            for a in args[1:]:
                ratio = self._ratio_param(a)
                if ratio:
                    parts += [ratio[0], ratio[1]]
                else:
                    parts += [self._compile(a, rule, item_var, True), "1"]
            # parts = [a, bn, bd, cn, cd] の順に揃える
            a_src, bn, bd, cn, cd = parts[0], parts[1], parts[2], parts[3], parts[4]
            return f"_muldiv3({a_src}, {bn}, {bd}, {cn}, {cd}, {rounding!r})"
        nums: list[str] = [self._compile(args[0], rule, item_var)]
        dens: list[str] = []
        for pos, a in enumerate(args[1:], start=1):
            ratio = self._ratio_param(a)
            if ratio:
                num_src, den_src = ratio
                if pos == 1:  # 乗数
                    nums.append(num_src)
                    dens.append(den_src)
                else:  # 除数：逆数を掛ける
                    nums.append(den_src)
                    dens.append(num_src)
            else:
                (nums if pos == 1 else dens).append(self._compile(a, rule, item_var))
        n = " * ".join(nums)
        d = " * ".join(dens) if dens else "1"
        return {
            "floor": f"(({n}) // ({d}))",
            "ceil": f"(-((-({n})) // ({d})))",
            "half_up": f"((2 * ({n}) + ({d})) // (2 * ({d})))",
        }[rounding]

    def _ratio_param(self, expr: dict) -> tuple[str, str] | None:
        if "param" in expr:
            p = self.spec.params[expr["param"]]
            if p.type == "ratio":
                const = f"P_{expr['param'].upper()}"
                return f"{const}[0]", f"{const}[1]"
        return None

    def _compile_agg(self, expr: dict, rule: Rule) -> str:
        over = expr["over"]
        mode = expr["mode"]
        item_var = "_it"
        body = self._compile(expr["map"], rule, item_var) if "map" in expr else item_var
        cond = f" if {self._compile(expr['filter'], rule, item_var)}" if "filter" in expr else ""
        gen = f"{body} for {item_var} in {over}{cond}"
        if mode == "sum":
            return f"sum({gen})"
        if mode == "count":
            return f"sum(1 for {item_var} in {over}{cond})"
        if mode == "max":
            return f"max(({gen}), default=None)"
        if mode == "min":
            return f"min(({gen}), default=None)"
        if mode == "any":
            return f"any({gen})"
        if mode == "all":
            return f"all({gen})"
        raise ValueError(f"未知の agg mode: {mode}")


def _collect_ops(rule: Rule, out: set[str]) -> None:
    def walk(e) -> None:
        if not isinstance(e, dict):
            return
        if "op" in e:
            out.add(e["op"])
        for a in e.get("args", []):
            walk(a)
        for k in ("filter", "map"):
            if k in e:
                walk(e[k])

    for step in rule.steps:
        walk(step.expr)
