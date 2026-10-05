"""計算仕様 → Python の決定的コンパイラ。

生成物は拡張に依存しない単独のモジュールで、**標準ライブラリだけ**を使う（DESIGN.md §11.1）。
参照インタプリタ（`spec/interp.py`）とは別の経路で同じ意味論を実装し、差分テストで一致を確かめる。

変数名は仕様の**手順名**にする。手順名は約款の文・表の行・図のノードと対応しているので、
生成コードを読めばどの文がどの計算に当たるかが追える。
"""

from __future__ import annotations

from ..spec.ops import CMP, LOGIC
from ..spec.validate import RuleSet, input_unit

_PYOP = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "==", "ne": "!="}

_ANNOT = {"int": "int | None", "bool": "bool | None", "str": "str | None", "date": "date | None"}

#: 共通処理。`spec/interp.py` と同じ意味論を別経路で実装する（両者の一致はテストで固定）
_PRELUDE_CORE = '''
def _muldiv(a, b, c, rounding):
    """a×b÷c を整数で返す。不明・負数・ゼロ除算は None（不明）。"""
    if a is None or b is None or c is None or c == 0 or a < 0 or b < 0 or c < 0:
        return None
    n = a * b
    if rounding == "floor":
        return n // c
    if rounding == "ceil":
        return -((-n) // c)
    return (2 * n + c) // (2 * c)


def _round_to(x, unit, rounding):
    """x を unit の倍数に丸める。unit が 0 以下なら不明。"""
    if x is None or unit is None or unit <= 0:
        return None
    if rounding == "floor":
        return (x // unit) * unit
    if rounding == "ceil":
        return -((-x) // unit) * unit
    return ((2 * x + unit) // (2 * unit)) * unit


def _lookup_exact(table, key):
    return None if key is None else dict(table).get(key)


def _lookup_step(table, key):
    """キー以上で最も小さい行の値。どの行にも当たらなければ不明。"""
    if key is None:
        return None
    return next((v for k, v in table if key <= k), None)


def _all3(*vals):
    """Kleene の論理積（確定できるときだけ確定する）。"""
    if any(v is False for v in vals):
        return False
    return None if any(v is None for v in vals) else True


def _any3(*vals):
    """Kleene の論理和。"""
    if any(v is True for v in vals):
        return True
    return None if any(v is None for v in vals) else False


def _not3(v):
    return None if v is None else (not v)
'''

_PRELUDE_DATE = '''
def _add_days(d, n):
    return None if (d is None or n is None) else d + timedelta(days=n)


def _add_months(d, n):
    """月末を丸める（1 月 31 日に 1 か月を加えると 2 月末日）。"""
    if d is None or n is None:
        return None
    total = (d.year * 12 + d.month - 1) + n
    y, m = divmod(total, 12)
    m += 1
    return date(y, m, min(d.day, monthrange(y, m)[1]))


def _days_between(a, b):
    """後の日付 b から前の日付 a までの日数（b − a）。"""
    return None if (a is None or b is None) else (b - a).days


def _end_of_month(d):
    return None if d is None else date(d.year, d.month, monthrange(d.year, d.month)[1])
'''


def fn_name(rule_id: str) -> str:
    """仕様に `interface.function` が無いときの既定の関数名。"""
    return rule_id.replace(".", "_").replace("-", "_")


def uses_date(rs: RuleSet) -> bool:
    for rid in rs.rules:
        if any(i["type"] == "date" for i in rs.rules[rid].get("inputs", {}).values()):
            return True
        for node in _all_nodes(rs, rid):
            if node.get("op") in ("add_days", "add_months", "days_between", "end_of_month"):
                return True
    return False


def _all_nodes(rs: RuleSet, rid: str):
    for s in rs.steps_of(rid):
        yield from _nodes(s["expr"])


def _nodes(e):
    if not isinstance(e, dict):
        return
    yield e
    for a in e.get("args", []):
        yield from _nodes(a)
    for v in (e.get("with") or {}).values():
        yield from _nodes(v)


# --------------------------------------------------------------- 厳密性の解析
_LAZY_ARGS = {"if": (1, 2), "coalesce": (0, 1), "and": "all", "or": "all"}


def strict_inputs(rs: RuleSet, rid: str) -> list[str]:
    """「この入力が不明なら結果も必ず不明」といえる入力の一覧（関数冒頭の門番に使う）。"""
    expr = rs.full_expr(rid)
    inputs = list(rs.rules[rid].get("inputs", {}))
    hit: dict[str, bool] = {}

    def walk(e, strict: bool) -> None:
        if not isinstance(e, dict):
            return
        if "var" in e:
            hit[e["var"]] = hit.get(e["var"], True) and strict
            return
        op = e.get("op")
        lazy = _LAZY_ARGS.get(op)
        for i, a in enumerate(e.get("args", [])):
            if lazy == "all":
                child = False
            elif lazy is not None:
                child = strict and i not in lazy
            else:
                child = strict
            walk(a, child)
        if op == "lookup":
            return

    walk(expr, True)
    # 表引きの結果は非 None とは限らないので、門番で返すのは「不明→不明」が確かなものだけ
    return [n for n in inputs if hit.get(n) is True]


class _Emitter:
    """1 ルール分の関数本体を組み立てる。"""

    def __init__(self, rs: RuleSet, rid: str, funcs: dict[str, str]):
        self.rs = rs
        self.rid = rid
        self.rule = rs.rules[rid]
        self.funcs = funcs  # rule_id -> 関数名
        self.lines: list[str] = []
        self.nonnull: set[str] = set()
        # 局所変数が、定義済みの関数名・定数名とぶつからないようにする
        self.names: set[str] = (
            set(self.rule.get("inputs", {}))
            | set(self.rule.get("collections", {}))
            | set(funcs.values())
            | {f"P_{n.upper()}" for n in rs.params}
        )
        self.seq = 0

    # ---- 局所変数の払い出し（名前は意味のある語から作る） ----
    def local(self, hint: str) -> str:
        name = hint if hint.isidentifier() else "value"
        if name in self.names:
            self.seq += 1
            name = f"{hint}_{self.seq}"
        self.names.add(name)
        return name

    def out(self, text: str, comment: str = "") -> None:
        self.lines.append(f"    {text}{'  # ' + comment if comment else ''}")

    def hoist(self, hint: str, expr: str, nullable: bool, comment: str = "") -> tuple[str, bool]:
        name = self.local(hint)
        self.out(f"{name} = {expr}", comment)
        if not nullable:
            self.nonnull.add(name)
        return name, nullable

    # ---- 式 ----
    def expr(self, e: dict, item: str | None = None) -> tuple[str, bool]:
        """式を Python の式文字列に変換し、(式, None になりうるか) を返す。"""
        if "lit" in e:
            return repr(e["lit"]), False
        if "param" in e:
            return f"P_{e['param'].upper()}", False
        if "var" in e:
            return e["var"], e["var"] not in self.nonnull
        if "step" in e:
            # 手順は局所変数として先に代入してある（宣言順に出すので必ず定義済み）
            return e["step"], e["step"] not in self.nonnull
        if "item" in e:
            return f"_it.get({e['item']!r})", True
        if "rule" in e:
            return self.call_rule(e)
        op = e["op"]
        if op == "agg":
            return self.agg(e)
        if op in LOGIC:
            args = [self.atom(a, item) for a in e["args"]]
            fn = {"and": "_all3", "or": "_any3", "not": "_not3"}[op]
            return f"{fn}({', '.join(a for a, _ in args)})", True
        if op == "if":
            cond, cn = self.atom(e["args"][0], item)
            a, an = self.expr(e["args"][1], item)
            b, bn = self.expr(e["args"][2], item)
            body = f"({a} if {cond} else {b})"
            if cn:
                return f"(None if {cond} is None else {body})", True
            return body, an or bn
        if op == "coalesce":
            a, _an = self.atom(e["args"][0], item)
            b, bn = self.expr(e["args"][1], item)
            return f"({a} if {a} is not None else {b})", bn
        if op == "lookup":
            key, _ = self.atom(e["args"][0], item)
            tab = self.rs.tables[e["table"]]
            fn = "_lookup_exact" if tab["mode"] == "exact" else "_lookup_step"
            return f"{fn}(T_{e['table'].upper()}, {key})", True
        # ---- ここから下は厳密（引数に不明があれば不明） ----
        args = [self.atom(a, item) for a in e["args"]]
        names = [a for a, _ in args]
        guards = [a for a, nullable in args if nullable]
        body = self.strict_body(op, e, names)
        nullable = op in ("muldiv", "round_to") or bool(guards)
        if guards and op not in ("muldiv", "round_to"):
            cond = " or ".join(f"{g} is None" for g in dict.fromkeys(guards))
            return f"(None if ({cond}) else {body})", True
        return body, nullable

    def strict_body(self, op: str, e: dict, names: list[str]) -> str:
        if op == "add":
            return " + ".join(names)
        if op == "sub":
            return f"{names[0]} - {names[1]}"
        if op == "mul":
            return " * ".join(names)
        if op in ("min", "max"):
            return f"{op}({', '.join(names)})"
        if op in CMP:
            return f"{names[0]} {_PYOP[op]} {names[1]}"
        if op == "muldiv":
            return f"_muldiv({names[0]}, {names[1]}, {names[2]}, {e['rounding']!r})"
        if op == "round_to":
            return f"_round_to({names[0]}, {names[1]}, {e['rounding']!r})"
        if op == "add_days":
            return f"_add_days({names[0]}, {names[1]})"
        if op == "add_months":
            return f"_add_months({names[0]}, {names[1]})"
        if op == "days_between":
            return f"_days_between({names[0]}, {names[1]})"
        if op == "end_of_month":
            return f"_end_of_month({names[0]})"
        raise ValueError(f"コード生成が知らない演算: {op}")

    def atom(self, e: dict, item: str | None) -> tuple[str, bool]:
        """複合式は局所変数に逃がし、必ず「1 つの名前または定数」にする。"""
        code, nullable = self.expr(e, item)
        if code.isidentifier() or code.startswith("P_") or _is_simple_literal(code):
            return code, nullable
        return self.hoist(self.hint_of(e), code, nullable)

    def hint_of(self, e: dict) -> str:
        if "rule" in e:
            return e["rule"].split(".")[-1]
        if e.get("op") == "lookup":
            return e["table"]
        if e.get("op") in CMP:
            return "condition"
        return {"muldiv": "proportion", "round_to": "rounded", "and": "judged", "or": "judged"}.get(
            e.get("op"), "value"
        )

    def call_rule(self, e: dict) -> tuple[str, bool]:
        rid = e["rule"]
        fn = self.funcs[rid]
        other = self.rs.rules[rid]
        parts = []
        for name in other.get("inputs", {}):
            if name in (e.get("with") or {}):
                code, _ = self.atom(e["with"][name], None)
            else:
                code = name
            parts.append(f"{name}={code}")
        return f"{fn}({', '.join(parts)})", True

    def agg(self, e: dict) -> tuple[str, bool]:
        over = e["over"]
        vals = self.local(f"{over}_values")
        self.out(f"{vals} = []")
        self.out(f"for _it in ({over} or []):")
        mark = len(self.lines)
        inner, _ = self.expr(e["args"][0], item=over)
        # 内側の式が局所変数に逃がした行は、ループの中に入れ直す
        self.lines[mark:] = ["    " + line for line in self.lines[mark:]]
        self.lines.append(f"        {vals}.append({inner})")
        agg = f"sum({vals})" if e["func"] == "sum" else f"(max({vals}) if {vals} else None)"
        return f"(None if any(_v is None for _v in {vals}) else {agg})", True

    # ---- 手順 ----
    def build(self) -> str:
        rs, r = self.rs, self.rule
        guard = strict_inputs(rs, self.rid)
        if guard:
            cond = " or ".join(f"{n} is None" for n in guard)
            self.out(f"if {cond}:")
            self.lines.append("        return None")
            self.nonnull.update(guard)
        target = r["output"].get("step") or r["steps"][-1]["name"]
        needed = _needed_steps(r["steps"], target)
        for s in r["steps"]:
            if s["name"] not in needed:
                continue
            code, nullable = self.expr(s["expr"])
            name = s["name"]
            self.names.add(name)
            if not nullable:
                self.nonnull.add(name)
            comment = self.rs.doc.resolve(s.get("cite") or s.get("label", ""))
            if name == target:
                self.out(f"return {code}", comment)
                return "\n".join(self.lines)
            self.out(f"{name} = {code}", comment)
        self.out(f"return {target}")
        return "\n".join(self.lines)


def _is_simple_literal(code: str) -> bool:
    return code.lstrip("-").isdigit() or code in ("True", "False", "None")


def _needed_steps(steps: list[dict], target: str) -> set[str]:
    by_name = {s["name"]: s["expr"] for s in steps}
    out: set[str] = set()
    stack = [target]
    while stack:
        n = stack.pop()
        if n in out or n not in by_name:
            continue
        out.add(n)
        for e in _nodes(by_name[n]):
            if "step" in e:
                stack.append(e["step"])
    return out


def _step_refs(expr: dict) -> list[str]:
    return [e["step"] for e in _nodes(expr) if "step" in e]


def _rule_order(rs: RuleSet) -> list[str]:
    """依存しているルールを先に定義する並び（決定的）。"""
    order: list[str] = []
    seen: set[str] = set()

    def visit(rid: str, stack: tuple = ()) -> None:
        if rid in seen:
            return
        if rid in stack:
            raise ValueError(f"ルールの循環参照: {' -> '.join(stack + (rid,))}")
        for dep in rs.depends_on(rid):
            visit(dep, stack + (rid,))
        seen.add(rid)
        order.append(rid)

    for rid in rs.rules:
        visit(rid)
    return order


def _signature(rs: RuleSet, rid: str) -> str:
    r = rs.rules[rid]
    parts = []
    for name, spec in r.get("inputs", {}).items():
        parts.append(f"{name}: {_ANNOT.get(spec['type'], 'object | None')} = None")
    for name in r.get("collections", {}):
        parts.append(f"{name}: list[dict] | None = None")
    return ", ".join(parts)


def compile_module(rs: RuleSet, rule_ids: list[str] | None = None) -> str:
    doc = rs.doc
    needs_date = uses_date(rs)
    out: list[str] = []
    out.append(
        f'"""自動生成コード（手で編集しない）。\n\n'
        f"文書: {doc.meta['title']}（{doc.content_id} / 様式 {doc.meta.get('form_code')} / "
        f'{doc.meta.get("edition_date")} 版）\n生成元: 計算仕様 v{rs.version}\n"""'
    )
    if needs_date:
        out.append("\nfrom calendar import monthrange")
        out.append("from datetime import date, timedelta")
    out.append(_PRELUDE_CORE)
    if needs_date:
        out.append(_PRELUDE_DATE)
    out.append("# ---- 定数（値は文書から決定的に解決。根拠を併記）")
    for name, p in rs.params.items():
        cite = doc.citation(p["source"]["unit"]) if p.get("source") else ""
        over = f" ／ {p['overridable_by']}で上書き可" if p.get("overridable_by") else ""
        out.append(f"P_{name.upper()} = {p['value']}  # {p['surface']} [{p['unit']}] 根拠: {cite}{over}")
    if rs.tables:
        out.append("\n# ---- 参照表（表ブロックのセルから決定的に読取）")
    for name, t in rs.tables.items():
        rows = ", ".join(f"({k!r}, {v!r})" for k, v, *_ in t["rows"])
        out.append(f"T_{name.upper()} = ({rows},)  # {doc.citation(t['rows'][0][2])}")
    meta: list[str] = []
    funcs = {rid: rs.function_of(rid) for rid in rs.rules}
    for rid in _rule_order(rs):
        if rule_ids is not None and rid not in rule_ids:
            continue
        r = rs.rules[rid]
        variant = rs.decisions.get(rid, {}).get("variant") or r.get("selected")
        cites = "; ".join(dict.fromkeys(doc.citation(s["unit"]) for s in r["sources"]))
        ret = _ANNOT.get(r["output"]["type"], "object | None")
        out.append(f"\n\ndef {funcs[rid]}(*, {_signature(rs, rid)}) -> {ret}:")
        out.append(f'    """{r["title"]}\n')
        out.append(f"    根拠: {cites}")
        if variant:
            out.append(f"    採用した解釈: {variant}（{r['variants'][variant]['label']}）")
        for a in r.get("assumptions", []):
            out.append(f"    前提: {a}")
        out.append('    """')
        out.append(_Emitter(rs, rid, funcs).build())
        meta.append(
            f"    {rid!r}: {{'fn': {funcs[rid]}, 'title': {r['title']!r}, "
            f"'output': {input_unit(r['output'])!r}, 'sources': {cites!r}}},"
        )
    out.append("\n\nRULES = {")
    out.extend(meta)
    out.append("}")
    return "\n".join(out) + "\n"
