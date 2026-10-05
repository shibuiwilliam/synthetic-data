"""計算仕様（CalcSpec v0.2）の読み込みと静的検査。

設計上の要点:
  * 数値は仕様に直書きしない。定数は `meta.constants` または根拠文中の表記から決定的に解決する。
  * 表は仕様に転記しない。表ブロックIDと読み方だけを指定し、セルは決定的に読む。
  * すべての規定は根拠（単位ID＋原文の引用）を持ち、引用が原文に実在することを検査する。
  * 式は**名前つきの手順**（`steps`）で書く。手順名は約款の文・表の行・図のノードと
    1 対 1 で対応し、生成する Python の変数名にもなる（DESIGN.md §8.1、§11.1）。
  * 解釈が割れる箇所は `variants` として並記し、人の裁定（`decisions`）が無ければ止める。

v0.1（`expr` 1 本）の仕様も読める。読み込み時に 1 手順の `steps` に正規化する。
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass
from pathlib import Path

from ..core.docindex import Doc, nfkc, parse_quantity
from .ops import AFFINE, ATOMIC_KINDS, CMP, LOGIC, ROUNDINGS, check_shape

IDENT = re.compile(r"^[a-z][a-z0-9_]*$")


@dataclass
class Issue:
    level: str  # error / block / warn / info
    rule: str | None
    code: str
    msg: str

    def __str__(self) -> str:
        return f"[{self.level}] {self.rule or '-'} {self.code}: {self.msg}"


class Blocked(Exception):
    """未決事項（variants に対する裁定なし）のためコンパイルできない。"""


class UnitError(Exception):
    pass


# ------------------------------------------------------------------ 単位演算
def _u(unit: str | None) -> dict | None:
    if unit is None:
        return None
    if unit == "1":
        return {}
    out: dict[str, int] = {}
    num, *den = unit.split("/")
    for part in num.split("*"):
        out[part] = out.get(part, 0) + 1
    for part in den:
        out[part] = out.get(part, 0) - 1
    return {k: v for k, v in out.items() if v}


def _fmt(u: dict | None) -> str:
    if u is None:
        return "?"
    if not u:
        return "1"
    num = "*".join(k for k, v in sorted(u.items()) if v > 0 for _ in range(v)) or "1"
    den = "".join("/" + k for k, v in sorted(u.items()) if v < 0 for _ in range(-v))
    return num + den


def _mul(a: dict, b: dict, sign: int = 1) -> dict:
    out = dict(a)
    for k, v in b.items():
        out[k] = out.get(k, 0) + sign * v
    return {k: v for k, v in out.items() if v}


# ------------------------------------------------------------------ 表の読取
_TABLE_KEY = {
    "upto_month": re.compile(r"^(\d+)か月まで$"),
    "upto_day": re.compile(r"^(\d+)日まで$"),
    "upto_year": re.compile(r"^(\d+)年まで$"),
    "ordinal": re.compile(r"^第?(\d+)(?:級|区分|回)$"),
    "plain_int": re.compile(r"^(\d+)$"),
}


def _parse_cell(kind: str, text: str):
    t = nfkc(text).strip()
    if kind in _TABLE_KEY:
        m = _TABLE_KEY[kind].match(t)
        return int(m.group(1)) if m else None
    if kind == "label":
        return text.strip() or None
    if kind == "percent":
        m = re.fullmatch(r"(\d+)%", t)
        return int(m.group(1)) if m else None
    if kind == "money":
        q = parse_quantity(t)
        return q["value"] if q and q["unit"] == "JPY" and q["value"] is not None else None
    if kind == "days":
        q = parse_quantity(t)
        return q["value"] if q and q["unit"] == "DAY" and q["value"] is not None else None
    if kind == "months":
        q = parse_quantity(t)
        return q["value"] if q and q["unit"] == "MONTH" and q["value"] is not None else None
    raise ValueError(kind)


CELL_PARSERS = ("label", "percent", "money", "days", "months", *sorted(_TABLE_KEY))


class RuleSet:
    def __init__(self, path: str | Path | dict, doc: Doc, decisions: dict | None = None):
        if isinstance(path, dict):
            self.path = Path("<memory>")
            self.spec = copy.deepcopy(path)
        else:
            self.path = Path(path)
            self.spec = json.loads(self.path.read_text(encoding="utf-8"))
        self.doc = doc
        self.decisions = decisions or {}
        self.issues: list[Issue] = []
        self.params: dict[str, dict] = {}
        self.tables: dict[str, dict] = {}
        self.rules: dict[str, dict] = {r["id"]: _normalize_rule(r) for r in self.spec["rules"]}
        if self.spec.get("document", {}).get("content_id") != doc.content_id:
            self._issue("error", None, "DOC_MISMATCH", "仕様と文書の content_id が一致しない")
        self._resolve_params()
        self._resolve_tables()

    # ---------------------------------------------------------------- 基本
    @property
    def version(self) -> str:
        return self.spec.get("spec_version") or self.spec.get("ir_version") or "0.1"

    def function_of(self, rule_id: str) -> str:
        r = self.rules[rule_id]
        return r.get("interface", {}).get("function") or rule_id.replace(".", "_").replace("-", "_")

    def _issue(self, level, rule, code, msg) -> None:
        self.issues.append(Issue(level, rule, code, msg))

    # ------------------------------------------------------------ 根拠の検査
    def _check_source(self, src: dict, where: str, rule: str | None = None) -> str | None:
        uid = src.get("unit")
        if uid not in self.doc.units:
            self._issue("error", rule, "SOURCE_NOT_FOUND", f"{where}: 単位ID {uid!r} が文書にない")
            return None
        text = self.doc.units[uid].text
        quote = src.get("quote")
        if quote is not None and quote not in text:
            self._issue(
                "error",
                rule,
                "QUOTE_NOT_VERBATIM",
                f"{where}: 引用が {uid} の原文に存在しない: 「{quote[:30]}…」",
            )
            return None
        return quote if quote is not None else text

    # ------------------------------------------------------------ 定数の解決
    def _resolve_params(self) -> None:
        for name, p in self.spec.get("params", {}).items():
            where = f"param {name}"
            if not IDENT.match(name):
                self._issue("error", None, "PARAM_NAME", f"{where}: 定数名が命名規則に合わない")
                continue
            if "from_const" in p:
                surface = self.doc.constants.get(p["from_const"])
                if surface is None:
                    self._issue("error", None, "CONST_NOT_FOUND", f"{where}: 定数 {p['from_const']} がない")
                    continue
            elif "from_block" in p:  # 表のセル 1 つを定数として使う
                u = self.doc.units.get(p["from_block"])
                if u is None:
                    self._issue("error", None, "CONST_NOT_FOUND", f"{where}: セル {p['from_block']} がない")
                    continue
                surface = u.text
            elif "literal" in p:
                surface = p["literal"]
            else:
                self._issue("error", None, "PARAM_UNGROUNDED", f"{where}: 値の出どころがない")
                continue
            q = parse_quantity(surface)
            if q is None or q.get("value") is None or not isinstance(q["value"], int):
                self._issue(
                    "error", None, "PARAM_NOT_NUMERIC", f"{where}: 「{surface}」を整数に正規化できない"
                )
                continue
            expect_unit = p.get("const_unit", p["unit"].split("/")[0])
            if q["unit"] != expect_unit:
                self._issue(
                    "error",
                    None,
                    "PARAM_UNIT_MISMATCH",
                    f"{where}: 原文の単位 {q['unit']} と仕様の単位 {expect_unit} が違う",
                )
                continue
            quote = self._check_source(p.get("source", {}), where)
            if quote is not None and nfkc(surface) not in nfkc(quote):
                self._issue(
                    "error", None, "PARAM_NOT_IN_QUOTE", f"{where}: 根拠の引用に「{surface}」が現れない"
                )
                continue
            self.params[name] = {
                "value": q["value"] * p.get("scale", 1),
                "unit": p["unit"],
                "surface": surface,
                "source": p.get("source"),
                "from_const": p.get("from_const"),
                "overridable_by": p.get("overridable_by"),
            }

    # -------------------------------------------------------------- 表の解決
    def _resolve_tables(self) -> None:
        for name, t in self.spec.get("tables", {}).items():
            where = f"table {name}"
            b = self.doc.blocks.get(t["from_block"])
            if not b or b["type"] != "table":
                self._issue("error", None, "TABLE_NOT_FOUND", f"{where}: 表 {t['from_block']} がない")
                continue
            if t["key_parse"] not in CELL_PARSERS or t["value_parse"] not in CELL_PARSERS:
                self._issue("error", None, "TABLE_PARSER", f"{where}: 知らないセルの読み方")
                continue
            grid = b["grid"]

            def cell(c, _doc=self.doc):
                return _doc.units[c["id"]].text if c["id"] in _doc.units else ""

            if t["shape"] == "header_keys":  # 見出し行がキー、次の行が値（横持ち）
                pairs = [
                    (grid[t["key_row"]][i], grid[t["value_row"]][i])
                    for i in range(1, len(grid[t["key_row"]]))
                ]
            else:  # 1 行 = 1 キー（縦持ち）
                hdr = b["layout"].get("header_rows", 0)
                pairs = [(row[t["key_col"]], row[t["value_col"]]) for row in grid[hdr:]]
            rows, ok = [], True
            for kc, vc in pairs:
                vtxt = t.get("value_map", {}).get(cell(vc), cell(vc))
                k, v = _parse_cell(t["key_parse"], cell(kc)), _parse_cell(t["value_parse"], vtxt)
                if k is None or v is None:
                    ok = False
                    self._issue(
                        "error",
                        None,
                        "TABLE_CELL_UNPARSED",
                        f"{where}: セル {kc['id']}/{vc['id']}（「{cell(kc)}」「{cell(vc)}」）を読めない",
                    )
                    continue
                rows.append((k, v, kc["id"], vc["id"]))
            keys = [r[0] for r in rows]
            if len(set(keys)) != len(keys):
                ok = False
                self._issue("error", None, "TABLE_DUP_KEY", f"{where}: キーが重複")
            if t["mode"] == "step_le":
                if keys != sorted(keys):
                    ok = False
                    self._issue("error", None, "TABLE_NOT_SORTED", f"{where}: 階段表のキーが昇順でない")
                vals = [r[1] for r in rows]
                if t.get("monotone") == "+" and vals != sorted(vals):
                    ok = False
                    self._issue("error", None, "TABLE_NOT_MONOTONE", f"{where}: 値が単調増加でない")
                if t.get("monotone") == "-" and vals != sorted(vals, reverse=True):
                    ok = False
                    self._issue("error", None, "TABLE_NOT_MONOTONE", f"{where}: 値が単調減少でない")
            if "expect_keys" in t and sorted(keys, key=str) != sorted(t["expect_keys"], key=str):
                ok = False
                self._issue("error", None, "TABLE_DOMAIN_GAP", f"{where}: キーの集合が想定と違う {keys}")
            if ok:
                self.tables[name] = {
                    "rows": rows,
                    "mode": t["mode"],
                    "key_unit": t["key_unit"],
                    "value_unit": t["value_unit"],
                    "from_block": t["from_block"],
                    "key_type": "str" if t["key_parse"] == "label" else "int",
                }

    # --------------------------------------------------------- 式の取り出し
    def steps_of(self, rule_id: str) -> list[dict]:
        return self.rules[rule_id]["steps"]

    def expr_of(self, rule_id: str, variant: str | None = None) -> dict:
        """手順を展開した 1 本の式。意味論・テスト生成・変異はこの式の上で行う。"""
        r = self.rules[rule_id]
        if "variants" in r:
            pick = variant or self.decisions.get(rule_id, {}).get("variant") or r.get("selected")
            if pick is None:
                raise Blocked(f"{rule_id}: 解釈が未裁定（{', '.join(r['variants'])}）")
            return self.inline_steps(
                r["variants"][pick]["steps"], r["variants"][pick].get("output", r["output"])
            )
        return self.inline_steps(r["steps"], r["output"])

    def inline_steps(self, steps: list[dict], output: dict) -> dict:
        by_name = {s["name"]: s["expr"] for s in steps}

        def sub(e, stack: tuple):
            if not isinstance(e, dict):
                return e
            if "step" in e:
                n = e["step"]
                if n in stack:
                    raise ValueError(f"手順の循環参照: {' -> '.join(stack + (n,))}")
                if n not in by_name:
                    raise ValueError(f"未知の手順 {n!r}")
                return sub(copy.deepcopy(by_name[n]), stack + (n,))
            out = dict(e)
            if "args" in out:
                out["args"] = [sub(a, stack) for a in out["args"]]
            return out

        target = output.get("step") or steps[-1]["name"]
        return sub({"step": target}, ())

    def inline(self, expr: dict, variant_for: dict | None = None, _stack: tuple = ()) -> dict:
        """他ルール参照 `{"rule": id, "with": {...}}` を式に展開する。"""
        if not isinstance(expr, dict):
            return expr
        if "rule" in expr:
            rid = expr["rule"]
            if rid in _stack:
                raise ValueError(f"循環参照: {' -> '.join(_stack + (rid,))}")
            body = copy.deepcopy(self.expr_of(rid, (variant_for or {}).get(rid)))
            body = self.inline(body, variant_for, _stack + (rid,))
            binding = {k: self.inline(v, variant_for, _stack) for k, v in expr.get("with", {}).items()}
            return _subst(body, binding)
        out = dict(expr)
        if "args" in out:
            out["args"] = [self.inline(a, variant_for, _stack) for a in out["args"]]
        return out

    def full_expr(self, rule_id: str, variant: str | None = None) -> dict:
        """手順と他ルール参照の両方を展開した式。"""
        return self.inline(self.expr_of(rule_id, variant), {rule_id: variant} if variant else None)

    def depends_on(self, rule_id: str) -> list[str]:
        out: list[str] = []
        for s in self.steps_of(rule_id):
            for e in _nodes(s["expr"]):
                if "rule" in e and e["rule"] not in out:
                    out.append(e["rule"])
        return out

    # ---------------------------------------------------------------- 検証
    def validate(self) -> list[Issue]:
        funcs: dict[str, str] = {}
        for rid, r in self.rules.items():
            fn = self.function_of(rid)
            if not IDENT.match(fn):
                self._issue("error", rid, "FUNCTION_NAME", f"関数名 {fn!r} が命名規則に合わない")
            if fn in funcs:
                self._issue("error", rid, "FUNCTION_DUP", f"関数名 {fn} が {funcs[fn]} と重複")
            funcs[fn] = rid
            self._check_steps(rid, r)
            for i, s in enumerate(r.get("sources", [])):
                self._check_source(s, f"sources[{i}]", rid)
            if not r.get("sources"):
                self._issue("error", rid, "NO_SOURCE", "根拠がない")
            for ex in r.get("examples", []):
                if "source" in ex:
                    self._check_source(ex["source"], "example", rid)
            for q in r.get("open_questions", []):
                self._issue("info", rid, "OPEN_QUESTION", q["text"])
            variants = r.get("variants")
            names = list(variants) if variants else [None]
            if variants:
                for vn, v in variants.items():
                    for i, s in enumerate(v.get("basis", [])):
                        self._check_source(s, f"variants.{vn}.basis[{i}]", rid)
                if not (self.decisions.get(rid, {}).get("variant") or r.get("selected")):
                    self._issue(
                        "block",
                        rid,
                        "UNDECIDED_VARIANT",
                        "解釈が複数あり裁定がない: "
                        + " / ".join(f"{k}={v['label']}" for k, v in variants.items()),
                    )
            for vn in names:
                try:
                    expr = self.full_expr(rid, vn)
                except Exception as e:  # noqa: BLE001
                    self._issue("error", rid, "INLINE_FAILED", str(e))
                    continue
                self._check_expr(rid, r, expr, vn)
        return self.issues

    def _check_steps(self, rid: str, r: dict) -> None:
        inputs = set(r.get("inputs", {})) | set(r.get("collections", {}))
        for name in sorted(inputs):
            if not IDENT.match(name):
                self._issue("error", rid, "INPUT_NAME", f"入力名 {name!r} が命名規則に合わない")
        seen: set[str] = set()
        for s in r["steps"]:
            n = s.get("name")
            if not n or not IDENT.match(n):
                self._issue("error", rid, "STEP_NAME", f"手順名 {n!r} が命名規則に合わない")
                continue
            if n in seen:
                self._issue("error", rid, "STEP_DUP", f"手順名 {n} が重複")
            if n in inputs:
                self._issue("error", rid, "STEP_SHADOW", f"手順名 {n} が入力名と衝突")
            if not s.get("label"):
                self._issue("error", rid, "STEP_LABEL", f"手順 {n} に日本語の名前（label）がない")
            seen.add(n)
        target = r["output"].get("step")
        if target and target not in seen:
            self._issue("error", rid, "OUTPUT_STEP", f"output.step {target!r} に対応する手順がない")
        used = {e["step"] for s in r["steps"] for e in _nodes(s["expr"]) if "step" in e}
        # 文を出すためだけの手順（但し書き・判定の言い添え）は、式から参照されなくてよい
        text_only = {s["name"] for s in r["steps"] if s.get("role") in ("sentence", "decide")}
        final = {target or (r["steps"][-1]["name"] if r["steps"] else None)}
        for n in sorted(seen - used - final - text_only):
            self._issue("warn", rid, "STEP_UNUSED", f"手順 {n} がどこからも使われていない")

    def _check_expr(self, rid: str, r: dict, expr: dict, variant: str | None) -> None:
        tag = f"（解釈{variant}）" if variant else ""
        inputs = r.get("inputs", {})
        colls = r.get("collections", {})
        used: set[str] = set()

        def walk(e: dict, item_scope: str | None) -> dict | None:
            bad = check_shape(e)
            if bad:
                raise UnitError(bad)
            if "lit" in e:
                v = e["lit"]
                if isinstance(v, bool):
                    return _u("BOOL")
                if isinstance(v, str):
                    return _u("STR")
                if v != 0 and "note" not in e:
                    self._issue("error", rid, "MAGIC_NUMBER", f"根拠のない数値リテラル {v}{tag}")
                if v == 0 and "unit" not in e:
                    return None  # 0 は任意の単位に合う
                return _u(e.get("unit", "1"))
            if "param" in e:
                if e["param"] not in self.params:
                    raise UnitError(f"未解決の定数 {e['param']}")
                return _u(self.params[e["param"]]["unit"])
            if "var" in e:
                if item_scope:
                    raise UnitError("明細の式から明細外の入力は参照できない")
                if e["var"] not in inputs:
                    raise UnitError(f"未宣言の入力 {e['var']}")
                used.add(e["var"])
                return _u(input_unit(inputs[e["var"]]))
            if "item" in e:
                if not item_scope or e["item"] not in colls[item_scope]["fields"]:
                    raise UnitError(f"未宣言の明細項目 {e.get('item')}")
                used.add(f"{item_scope}.{e['item']}")
                return _u(input_unit(colls[item_scope]["fields"][e["item"]]))
            if "step" in e:
                raise UnitError(f"手順 {e['step']} が展開されていない")
            op = e["op"]
            if op == "agg":
                if e["over"] not in colls or e.get("func") not in ("sum", "max"):
                    raise UnitError("agg の指定が不正")
                return walk(e["args"][0], e["over"])
            us = [walk(a, item_scope) for a in e["args"]]
            if op in ("add", "sub"):
                return _affine(op, us)
            if op in ("min", "max", "coalesce"):
                return _same(us, op)
            if op == "mul":
                out: dict = {}
                for u in us:
                    out = _mul(out, _alg(u, op))
                return out
            if op == "muldiv":
                if e.get("rounding") not in ROUNDINGS:
                    raise UnitError("muldiv には端数処理（rounding）の明示が必要")
                return _mul(_mul(_alg(us[0], op), _alg(us[1], op)), _alg(us[2], op), -1)
            if op == "round_to":
                if e.get("rounding") not in ROUNDINGS:
                    raise UnitError("round_to には端数処理（rounding）の明示が必要")
                return _same(us, op)
            if op in CMP:
                _same(us, op)
                return _u("BOOL")
            if op in LOGIC:
                for u in us:
                    if u != _u("BOOL"):
                        raise UnitError(f"{op} の引数が真偽値でない（{_fmt(u)}）")
                return _u("BOOL")
            if op == "if":
                if us[0] != _u("BOOL"):
                    raise UnitError("if の条件が真偽値でない")
                return _same(us[1:], op)
            if op == "lookup":
                t = self.tables.get(e["table"])
                if t is None:
                    raise UnitError(f"未解決の表 {e['table']}")
                if us[0] is not None and us[0] != _u(t["key_unit"]):
                    raise UnitError(
                        f"表 {e['table']} のキー単位 {t['key_unit']} に {_fmt(us[0])} を渡している"
                    )
                return _u(t["value_unit"])
            if op in ("add_days", "add_months"):
                want = _u("DAY") if op == "add_days" else _u("MONTH")
                if us[0] != _u("DATE") or us[1] not in (want, None):
                    raise UnitError(f"{op} は（日付, {_fmt(want)}）に対してだけ使える")
                return _u("DATE")
            if op == "days_between":
                if any(u != _u("DATE") for u in us):
                    raise UnitError("days_between の引数は日付でなければならない")
                return _u("DAY")
            if op == "end_of_month":
                if us[0] != _u("DATE"):
                    raise UnitError("end_of_month の引数は日付でなければならない")
                return _u("DATE")
            raise UnitError(op)

        try:
            got = walk(expr, None)
        except UnitError as ex:
            self._issue("error", rid, "TYPE_ERROR", f"{ex}{tag}")
            return
        want = _u(input_unit(r["output"]))
        if got is not None and got != want:
            self._issue(
                "error",
                rid,
                "UNIT_MISMATCH",
                f"式の単位 {_fmt(got)} が出力の単位 {_fmt(want)} と合わない{tag}",
            )
        declared = set(inputs) | {f"{c}.{f}" for c, spec in colls.items() for f in spec["fields"]}
        for name in sorted(declared - used):
            self._issue("warn", rid, "UNUSED_INPUT", f"入力 {name} が式で使われていない{tag}")

    # ------------------------------------------------------------- 状態集計
    def status(self, rule_id: str) -> str:
        levels = {i.level for i in self.issues if i.rule == rule_id}
        if "error" in levels:
            return "error"
        if "block" in levels:
            return "blocked"
        return "ok"

    def has_global_errors(self) -> bool:
        return any(i.level == "error" and i.rule is None for i in self.issues)

    def problems(self) -> list[str]:
        """生成を止めるべき指摘（error / block / warn）を文字列で返す。"""
        return [str(i) for i in self.validate() if i.level in ("error", "block", "warn")]


# ------------------------------------------------------------------ 補助関数
def _normalize_rule(r: dict) -> dict:
    """v0.1 の `expr` を 1 手順の `steps` に正規化する。"""
    r = dict(r)
    if "steps" not in r and "expr" in r:
        name = r["output"].get("name") or r["id"].replace(".", "_")
        r["steps"] = [{"name": name, "label": r.get("title", name), "expr": r.pop("expr")}]
        r["output"] = {**r["output"], "step": name}
    if "variants" in r:
        r["variants"] = {
            k: (
                v
                if "steps" in v
                else {**v, "steps": [{"name": "result", "label": v["label"], "expr": v["expr"]}]}
            )
            for k, v in r["variants"].items()
        }
    return r


def _nodes(e):
    if not isinstance(e, dict):
        return
    yield e
    for a in e.get("args", []):
        yield from _nodes(a)
    for v in (e.get("with") or {}).values():
        yield from _nodes(v)


def input_unit(spec: dict) -> str:
    t = spec["type"]
    if t == "bool":
        return "BOOL"
    if t == "str":
        return "STR"
    if t == "date":
        return "DATE"
    return spec.get("unit", "1")


def _alg(u: dict | None, op: str) -> dict:
    if u is None:
        return {}
    if set(u) & ATOMIC_KINDS:
        raise UnitError(f"{op} に {_fmt(u)} は使えない")
    return u


def _same(us: list, op: str) -> dict | None:
    known = [u for u in us if u is not None]
    for u in known[1:]:
        if u != known[0]:
            raise UnitError(f"{op} の引数の単位が不一致（{_fmt(known[0])} と {_fmt(u)}）")
    return known[0] if known else None


def _affine(op: str, us: list) -> dict | None:
    """日付±日数、年月±月数、日付−日付 を許す加減算。"""
    known = [u for u in us if u is not None]
    if not known:
        return None
    for abs_kind, diff_kind in AFFINE.items():
        a, d = _u(abs_kind), _u(diff_kind)
        n_abs = sum(1 for u in known if u == a)
        if n_abs == 0:
            continue
        if any(u not in (a, d) for u in known):
            raise UnitError(f"{op}: {abs_kind} と混ぜられるのは {diff_kind} だけ")
        if op == "add" and n_abs == 1:
            return a
        if op == "sub" and len(us) == 2 and us[0] == a:
            return d if us[1] == a else a
        raise UnitError(f"{op}: {abs_kind} に対して許されない加減算")
    return _same(us, op)


def _subst(expr: dict, binding: dict) -> dict:
    if not isinstance(expr, dict):
        return expr
    if "var" in expr and expr["var"] in binding:
        return copy.deepcopy(binding[expr["var"]])
    out = dict(expr)
    if "args" in out:
        out["args"] = [_subst(a, binding) for a in out["args"]]
    return out


#: 旧 `core.ir` との互換（既存の import を壊さないための再公開）
__all__ = ["CMP", "Blocked", "Issue", "RuleSet", "UnitError", "input_unit"]
