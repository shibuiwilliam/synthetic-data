"""IR → 日本語の逆翻訳（決定的）。

レビュー担当者が条文と見比べるための表示であり、LLM による「原文と同じ意味か」の
照合（逆翻訳チェック）の入力にもなる。式の木をそのまま字下げで示す。
"""

from __future__ import annotations

from ..spec.validate import RuleSet

_CMP = {"ge": "以上", "gt": "を超える", "le": "以下", "lt": "未満", "eq": "と等しい", "ne": "と異なる"}
_ROUND = {"floor": "切捨て", "ceil": "切上げ", "half_up": "四捨五入"}


def _atom(rs: RuleSet, r: dict, e: dict) -> str | None:
    if "step" in e:
        label = next((s["label"] for s in r["steps"] if s["name"] == e["step"]), e["step"])
        return f"〈{label}〉"
    if "rule" in e:
        return f"〈{rs.rules[e['rule']]['title']}の判定〉"
    if "lit" in e:
        v = e["lit"]
        if isinstance(v, bool):
            return "真" if v else "偽"
        return f"「{v}」" if isinstance(v, str) else f"{v:,}"
    if "param" in e:
        p = rs.params[e["param"]]
        return p["surface"] if p["value"] == _plain(p) else f"{p['value']:,}（{p['surface']}）"
    if "var" in e:
        return f"［{r['inputs'][e['var']]['desc']}］"
    if "item" in e:
        coll = next(c for c in r["collections"].values() if e["item"] in c["fields"])
        return f"［明細の {coll['fields'][e['item']]['desc']}］"
    return None


def _plain(p: dict) -> int:
    from ..core.docindex import parse_quantity

    q = parse_quantity(p["surface"])
    return q["value"] if q else -1


def render(rs: RuleSet, rule_id: str, variant: str | None = None, expr: dict | None = None) -> str:
    r = rs.rules[rule_id]
    expr = expr if expr is not None else rs.full_expr(rule_id, variant)
    lines = [f"{r['title']} ＝"]

    def walk(e: dict, depth: int, prefix: str = "") -> None:
        pad = "  " * depth + prefix
        a = _atom(rs, r, e)
        if a is not None:
            lines.append(pad + a)
            return
        op, args = e["op"], e.get("args", [])
        kids = lambda: [walk(x, depth + 1, "・") for x in args]  # noqa: E731
        if op == "add":
            lines.append(pad + "次の合計")
            kids()
        elif op == "sub":
            lines.append(pad + "1つ目から2つ目を差し引いた額")
            kids()
        elif op == "mul":
            lines.append(pad + "次を掛け合わせた額")
            kids()
        elif op == "muldiv":
            lines.append(pad + f"1つ目×2つ目÷3つ目（端数は{_ROUND[e['rounding']]}）")
            kids()
        elif op == "max" and len(args) == 2 and args[0] == {"lit": 0}:
            lines.append(pad + "次の額（0を下回るときは0）")
            walk(args[1], depth + 1, "・")
        elif op in ("min", "max"):
            lines.append(pad + f"次のうち最も{'小さい' if op == 'min' else '大きい'}額")
            kids()
        elif op in _CMP:
            lines.append(pad + f"1つ目が2つ目{_CMP[op]}")
            kids()
        elif op in ("and", "or"):
            lines.append(pad + ("次のすべてに該当" if op == "and" else "次のいずれかに該当"))
            kids()
        elif op == "not":
            lines.append(pad + "次に該当しない")
            kids()
        elif op == "if":
            lines.append(pad + "条件により分ける")
            walk(args[0], depth + 1, "条件: ")
            walk(args[1], depth + 1, "該当するとき: ")
            walk(args[2], depth + 1, "該当しないとき: ")
        elif op == "coalesce":
            lines.append(pad + "1つ目（記載がなければ2つ目）")
            kids()
        elif op == "lookup":
            t = rs.tables[e["table"]]
            cap = rs.doc.blocks[t["from_block"]].get("caption") or t["from_block"]
            how = "キーが一致する行" if t["mode"] == "exact" else "キー以上で最も近い行"
            lines.append(pad + f"表「{cap}」の{how}の値。キーは")
            kids()
        elif op == "round_to":
            lines.append(pad + f"1つ目を2つ目の単位で{_ROUND[e['rounding']]}した額")
            kids()
        elif op == "add_days":
            lines.append(pad + "1つ目の日付に2つ目の日数を加えた日")
            kids()
        elif op == "add_months":
            lines.append(pad + "1つ目の日付に2つ目の月数を加えた日（月末は丸める）")
            kids()
        elif op == "days_between":
            lines.append(pad + "1つ目の日付から2つ目の日付までの日数")
            kids()
        elif op == "end_of_month":
            lines.append(pad + "その日の属する月の末日")
            kids()
        elif op == "agg":
            lines.append(pad + f"明細ごとに次を求め、その{'合計' if e['func'] == 'sum' else '最大'}をとる")
            kids()
        else:
            raise ValueError(op)

    walk(expr, 1)
    return "\n".join(lines)


def render_steps(rs: RuleSet, rule_id: str) -> str:
    """手順ごとに分けて示す（約款の文と 1 対 1 で見比べるための表示）。"""
    r = rs.rules[rule_id]
    out = [f"{r['title']}（{rs.function_of(rule_id)}）"]
    for s in r["steps"]:
        out.append(f"  手順 {s['name']}: {s['label']}")
        body = render(rs, rule_id, expr=rs.inline(s["expr"]))
        out += ["    " + line for line in body.splitlines()[1:]]
    return "\n".join(out)
