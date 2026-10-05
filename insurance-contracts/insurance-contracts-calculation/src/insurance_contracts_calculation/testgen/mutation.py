"""テストの十分性の測定（ミューテーション）。

仕様を 1 箇所だけ「ありそうな誤読」に置き換えた変異体を作り、生成したテスト入力が
その違いを見分けられるかを測る（検証ゲート G7）。変異は**手順の式の上**で作る。
展開後の式で作ると、2 回使われる手順が別々に変異して現実の誤読から離れるためである。

変異の種類は「読み違い」に対応させる。意味のない変異を増やしても穴の指標にならない。
"""

from __future__ import annotations

import copy

from ..spec.validate import RuleSet

#: 境界・極値の取り違え（「以上」と「超える」など）
_SWAP = {
    "ge": "gt",
    "gt": "ge",
    "le": "lt",
    "lt": "le",
    "eq": "ne",
    "ne": "eq",
    "min": "max",
    "max": "min",
    "and": "or",
    "or": "and",
}

_ROUND_SWAP = {"floor": "ceil", "ceil": "floor", "half_up": "floor"}


def _paths(e, path=()):
    if not isinstance(e, dict):
        return
    yield path, e
    for i, a in enumerate(e.get("args", [])):
        yield from _paths(a, path + (i,))


def _replace(expr: dict, path: tuple, new_node: dict) -> dict:
    root = copy.deepcopy(expr)
    if not path:
        return new_node
    cur = root
    for i in path[:-1]:
        cur = cur["args"][i]
    cur["args"][path[-1]] = new_node
    return root


def mutate_expr(expr: dict) -> list[tuple[str, dict]]:
    """1 つの式について、1 箇所だけ変えた変異体を列挙する。"""
    out: list[tuple[str, dict]] = []

    def add(label: str, path: tuple, node: dict) -> None:
        out.append((f"{'/'.join(map(str, path)) or 'root'}: {label}", _replace(expr, path, node)))

    for path, node in _paths(expr):
        op = node.get("op")
        if op in _SWAP:
            add(f"{op}→{_SWAP[op]}", path, {**node, "op": _SWAP[op]})
        if op == "add" and len(node["args"]) == 2:
            add("add→sub", path, {**node, "op": "sub"})
        if op == "mul" and len(node["args"]) == 2:
            add("mul→add（「乗じて」を「加えて」と読む）", path, {**node, "op": "add"})
        if op == "agg":
            other = "max" if node.get("func") == "sum" else "sum"
            add(f"集計 {node.get('func')}→{other}", path, {**node, "func": other})
        if op == "sub":
            add("sub→add", path, {**node, "op": "add"})
            add("差引の向きを逆に", path, {**node, "args": list(reversed(node["args"]))})
        if op == "if":
            c, a, b = node["args"]
            add("if の枝を入替", path, {**node, "args": [c, b, a]})
        if op == "not":
            add("not を削除", path, node["args"][0])
        if op in ("muldiv", "round_to"):
            other = _ROUND_SWAP[node["rounding"]]
            add(f"端数処理 {node['rounding']}→{other}", path, {**node, "rounding": other})
        if op == "round_to":
            add("端数処理を省略", path, node["args"][0])
        if op == "coalesce":
            add("既定値を無視", path, node["args"][0])
        if op in ("add_days", "add_months"):
            add(
                "期間を 1 ずらす",
                path,
                {**node, "args": [node["args"][0], {"op": "add", "args": [node["args"][1], {"lit": 1}]}]},
            )
            add(
                "初日の算入を取り違える",
                path,
                {**node, "args": [node["args"][0], {"op": "sub", "args": [node["args"][1], {"lit": 1}]}]},
            )
        if op == "days_between":
            add("起算と満了を入替", path, {**node, "args": list(reversed(node["args"]))})
        if op == "end_of_month":
            add("月末への丸めを省略", path, node["args"][0])
        if "param" in node:
            for d in (1, -1):
                add(f"定数 {node['param']} を{d:+d}", path, {"op": "add", "args": [node, {"lit": d}]})
        if "lit" in node and isinstance(node["lit"], int) and not isinstance(node["lit"], bool):
            add(f"リテラル {node['lit']} を+1", path, {**node, "lit": node["lit"] + 1})
    return out + _lookup_mode_mutants(expr)


def _lookup_mode_mutants(expr: dict) -> list[tuple[str, dict]]:
    """表引きの「段の取り方」を取り違えた変異（`step_le` を 1 段ずらす）。"""
    out = []
    for path, node in _paths(expr):
        if node.get("op") == "lookup":
            shifted = {**node, "args": [{"op": "add", "args": [node["args"][0], {"lit": 1}]}]}
            out.append(
                (f"{'/'.join(map(str, path)) or 'root'}: 表の段を 1 ずらす", _replace(expr, path, shifted))
            )
    return out


def mutants(rs: RuleSet, rule_id: str) -> list[tuple[str, dict]]:
    """ルール 1 件の変異体（展開済みの式として返す）。手順ごとに 1 箇所だけ変える。

    出力に効かない手順（文を出すためだけの手順）は変異させない。
    変異しても結果が変わらないので、「見分けられない変異」として数えても意味がないためである。
    """
    from ..codegen.python import _needed_steps

    r = rs.rules[rule_id]
    target = r["output"].get("step") or r["steps"][-1]["name"]
    needed = _needed_steps(r["steps"], target)
    out: list[tuple[str, dict]] = []
    seen: set[str] = set()
    for s in r["steps"]:
        if s["name"] not in needed:
            continue
        for label, mutated in mutate_expr(s["expr"]):
            steps = [dict(x) for x in r["steps"]]
            for x in steps:
                if x["name"] == s["name"]:
                    x["expr"] = mutated
            try:
                expr = rs.inline(rs.inline_steps(steps, r["output"]))
            except Exception:  # noqa: BLE001  変異が壊れた式になることはある（捨てる）
                continue
            name = f"{s['name']}/{label}"
            if name in seen:
                continue
            seen.add(name)
            out.append((name, expr))
    return out


def mutants_of_expr(expr: dict) -> list[tuple[str, dict]]:
    """式 1 本だけを変異させる（単体テスト用）。"""
    return mutate_expr(expr)


def mutation_score(rs: RuleSet, rule_id: str, cases: list[dict], expr: dict | None = None) -> dict:
    from ..spec import interp

    expr = expr if expr is not None else rs.full_expr(rule_id)
    base = [interp._ev(rs, expr, c, None) for c in cases]
    ms = mutants(rs, rule_id)
    survivors = [
        name
        for name, m in ms
        if all(interp._ev(rs, m, c, None) == y for c, y in zip(cases, base, strict=False))
    ]
    return {"mutants": len(ms), "killed": len(ms) - len(survivors), "survivors": survivors}
