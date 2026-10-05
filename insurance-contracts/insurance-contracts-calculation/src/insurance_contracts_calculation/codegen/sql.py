"""IR → SQL の決定的コンパイラ。

方針:
  * 1演算=1列の「層」をCTEで積む（式の重複展開をしない。Python側の一時変数と1対1）。
  * NULL を「不明」として扱う。SQL が標準で厳密に伝播しない箇所は明示的に書く:
      - CASE は条件が NULL のとき ELSE に落ちるため、IS NULL を先に判定する。
      - LEAST/GREATEST は方言で NULL の扱いが違うため使わず、CASE で書く。
      - 整数除算の演算子は方言で違うため、方言オブジェクトで切り替える。
  * 参照表は実テーブル。明細（1事故に複数の品目など）は子テーブルを集約して結合する。
"""

from __future__ import annotations

from dataclasses import dataclass

from .compile_py import fn_name
from .ir import CMP, RuleSet

_SQLOP = {"lt": "<", "le": "<=", "gt": ">", "ge": ">=", "eq": "=", "ne": "<>"}


@dataclass(frozen=True)
class Dialect:
    name: str
    intdiv_op: str
    cast_int: bool

    def int(self, n: int) -> str:
        return f"CAST({n} AS BIGINT)" if self.cast_int else str(n)

    def intdiv(self, a: str, b: str) -> str:
        return f"({a}) {self.intdiv_op} ({b})"


SQLITE = Dialect("sqlite", "/", False)
DUCKDB = Dialect("duckdb", "//", True)
POSTGRES = Dialect("postgres", "/", True)  # 生成のみ（この検証では未実行）
_SQLTYPE = {"int": "BIGINT", "bool": "BOOLEAN", "str": "VARCHAR"}


def _lit(v, d: Dialect) -> str:
    if isinstance(v, bool):
        return "TRUE" if v else "FALSE"
    if isinstance(v, str):
        return "'" + v.replace("'", "''") + "'"
    return d.int(v)


class _Chain:
    """SELECT p.*, <式> AS <列> を積み上げるCTEの鎖。"""

    def __init__(self, prefix: str, col: str, source: str, ctes: list[str]):
        self.prefix, self.col, self.ctes = prefix, col, ctes
        self.k = 0
        ctes.append(f"{prefix}0 AS (SELECT * FROM {source})")

    @property
    def last(self) -> str:
        return f"{self.prefix}{self.k}"

    def layer(self, expr_sql: str, join: str = "") -> str:
        prev = self.last
        self.k += 1
        name = f"{self.col}{self.k}"
        self.ctes.append(f"{self.last} AS (SELECT p.*, {expr_sql} AS {name} FROM {prev} p{join})")
        return f"p.{name}"


def _nullable(atom: str) -> bool:
    """列参照だけが NULL になり得る（リテラル・定数はならない）。"""
    return atom.startswith("p.")


def _any_null(*atoms: str) -> str:
    return " OR ".join(f"{a} IS NULL" for a in atoms if _nullable(a)) or "FALSE"


NAIVE_OPTIONS = ("case", "minmax", "div", "sum")


class _SqlEmitter:
    def __init__(self, rs: RuleSet, rule_id: str, d: Dialect, naive: frozenset = frozenset()):
        """naive は「素朴な書き方」の実験用。本番の生成では常に空集合。"""
        self.rs, self.rid, self.d, self.naive = rs, rule_id, d, naive
        self.fn = fn_name(rule_id)
        self.ctes: list[str] = []
        self.main = _Chain("s", "t", f"in_{self.fn}", self.ctes)
        self.n_agg = 0

    def emit(self, e: dict, chain: _Chain) -> str:
        d = self.d
        if "lit" in e:
            return _lit(e["lit"], d)
        if "param" in e:
            return d.int(self.rs.params[e["param"]]["value"])
        if "var" in e:
            return f"p.{e['var']}"
        if "item" in e:
            return f"p.{e['item']}"
        op = e["op"]
        if op == "agg":
            self.n_agg += 1
            j = self.n_agg
            items = _Chain(f"i{j}_", f"u{j}_", f"in_{self.fn}__{e['over']}", self.ctes)
            inner = self.emit(e["args"][0], items)
            self.ctes.append(
                f"a{j} AS (SELECT p.claim_id, COUNT(*) AS n, COUNT({inner}) AS nn, "
                f"SUM({inner}) AS s, MAX({inner}) AS m FROM {items.last} p GROUP BY p.claim_id)"
            )
            empty, value = ("0", "g.s") if e["func"] == "sum" else ("NULL", "g.m")
            if "sum" in self.naive:
                return chain.layer(
                    f"COALESCE({value}, {empty})", f" LEFT JOIN a{j} g ON g.claim_id = p.claim_id"
                )
            return chain.layer(
                f"CASE WHEN g.n IS NULL THEN {empty} WHEN g.n <> g.nn THEN NULL ELSE {value} END",
                f" LEFT JOIN a{j} g ON g.claim_id = p.claim_id",
            )
        a = [self.emit(x, chain) for x in e["args"]]
        if op == "add":
            return chain.layer(" + ".join(a))
        if op == "sub":
            return chain.layer(f"{a[0]} - {a[1]}")
        if op == "mul":
            return chain.layer(" * ".join(a))
        if op in ("min", "max"):
            cmp = "<=" if op == "min" else ">="
            if "minmax" in self.naive:
                fn = {("sqlite", "min"): "MIN", ("sqlite", "max"): "MAX"}.get(
                    (d.name, op), "LEAST" if op == "min" else "GREATEST"
                )
                return chain.layer(f"{fn}({', '.join(a)})")
            cur = a[0]
            for nxt in a[1:]:
                cur = chain.layer(
                    f"CASE WHEN {_any_null(cur, nxt)} THEN NULL "
                    f"WHEN {cur} {cmp} {nxt} THEN {cur} ELSE {nxt} END"
                )
            return cur
        if op in CMP:
            return chain.layer(f"{a[0]} {_SQLOP[op]} {a[1]}")
        if op == "and":
            return chain.layer("(" + " AND ".join(a) + ")")
        if op == "or":
            return chain.layer("(" + " OR ".join(a) + ")")
        if op == "not":
            return chain.layer(f"NOT {a[0]}")
        if op == "if":
            if "case" in self.naive:
                return chain.layer(f"CASE WHEN {a[0]} THEN {a[1]} ELSE {a[2]} END")
            return chain.layer(f"CASE WHEN {a[0]} IS NULL THEN NULL WHEN {a[0]} THEN {a[1]} ELSE {a[2]} END")
        if op == "coalesce":
            return chain.layer(f"COALESCE({a[0]}, {a[1]})")
        if op == "lookup":
            t = f"t_{e['table']}"
            if self.rs.tables[e["table"]]["mode"] == "exact":
                return chain.layer(f"(SELECT l.v FROM {t} l WHERE l.k = {a[0]})")
            return chain.layer(
                f"(SELECT l.v FROM {t} l WHERE l.k = (SELECT MIN(m.k) FROM {t} m WHERE m.k >= {a[0]}))"
            )
        if op == "muldiv":
            x, y, z = a
            n = f"{x} * {y}"
            if "div" in self.naive:
                return chain.layer(f"{n} / {z}")
            body = {
                "floor": d.intdiv(n, z),
                "ceil": d.intdiv(f"{n} + {z} - 1", z),
                "half_up": d.intdiv(f"2 * {n} + {z}", f"2 * {z}"),
            }[e["rounding"]]
            return chain.layer(
                f"CASE WHEN {_any_null(x, y, z)} THEN NULL "
                f"WHEN {z} = 0 OR {x} < 0 OR {y} < 0 OR {z} < 0 THEN NULL ELSE {body} END"
            )
        raise ValueError(op)


def compile_rule(rs: RuleSet, rule_id: str, d: Dialect, naive: frozenset = frozenset()) -> dict:
    """1ルール分のDDL・参照表データ・問い合わせ文を返す。"""
    r = rs.rules[rule_id]
    fn = fn_name(rule_id)
    expr = rs.inline(rs.expr_of(rule_id))
    em = _SqlEmitter(rs, rule_id, d, naive)
    result = em.emit(expr, em.main)
    out_col = r["output"]["name"]
    query = (
        "WITH "
        + ",\n     ".join(em.ctes)
        + f"\nSELECT p.claim_id, {result} AS {out_col} FROM {em.main.last} p ORDER BY p.claim_id"
    )
    cols = ", ".join(f"{k} {_SQLTYPE[v['type']]}" for k, v in r.get("inputs", {}).items())
    ddl = [f"CREATE TABLE in_{fn} (claim_id BIGINT PRIMARY KEY{', ' + cols if cols else ''})"]
    for cname, c in r.get("collections", {}).items():
        fcols = ", ".join(f"{k} {_SQLTYPE[v['type']]}" for k, v in c["fields"].items())
        ddl.append(f"CREATE TABLE in_{fn}__{cname} (claim_id BIGINT, item_no BIGINT, {fcols})")
    tables = {}
    for name in sorted(_tables_used(expr)):
        t = rs.tables[name]
        ktype = "VARCHAR" if t["key_type"] == "str" else "BIGINT"
        ddl.append(f"CREATE TABLE t_{name} (k {ktype} PRIMARY KEY, v BIGINT)")
        tables[f"t_{name}"] = [(k, v) for k, v, *_ in t["rows"]]
    return {"ddl": ddl, "tables": tables, "query": query, "output": out_col}


def _tables_used(e: dict) -> set[str]:
    if not isinstance(e, dict):
        return set()
    out = {e["table"]} if e.get("op") == "lookup" else set()
    for a in e.get("args", []):
        out |= _tables_used(a)
    return out


def render_script(rs: RuleSet, d: Dialect, rule_ids: list[str] | None = None) -> str:
    """人が読むための .sql（DDL＋参照表＋ルールごとのビュー）。"""
    doc = rs.doc
    lines = [
        f"-- 自動生成SQL（{d.name}方言）。手で編集しない。",
        f"-- 文書: {doc.meta['title']}（{doc.content_id} / {doc.meta.get('edition_date')} 版）",
        "",
    ]
    seen: set[str] = set()
    for rid in rule_ids or list(rs.rules):
        c = compile_rule(rs, rid, d)
        r = rs.rules[rid]
        cites = "; ".join(dict.fromkeys(doc.citation(s["unit"]) for s in r["sources"]))
        lines.append(f"-- ■ {rid}  {r['title']}")
        lines.append(f"--   根拠: {cites}")
        for stmt in c["ddl"]:
            tname = stmt.split()[2]
            if tname in seen:
                continue
            seen.add(tname)
            lines.append(stmt + ";")
            for k, v in c["tables"].get(tname, []):
                lines.append(f"INSERT INTO {tname} VALUES ({_lit(k, d)}, {_lit(v, d)});")
        body = c["query"].rsplit(" ORDER BY", 1)[0]
        lines.append(f"CREATE VIEW v_{fn_name(rid)} AS\n{body};\n")
    return "\n".join(lines)
