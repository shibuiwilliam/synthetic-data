"""タスクカード（入出力の契約）。

評価対象システムのプログラムを同じテストで採点するには、関数名と引数を揃える必要がある。
ヒントは 3 水準（DESIGN.md §11.4）。

| 水準 | 渡すもの |
|---|---|
| H0 | 関数名と入出力だけ |
| H1 | H0 ＋ 主な条の条番号 |
| H2 | H1 ＋ 根拠単位のID |
"""

from __future__ import annotations

from ..core.docindex import Doc
from ..spec.validate import RuleSet

HINT_LEVELS = ("H0", "H1", "H2")

#: 出題に添える約束ごと。**約款の読み取りとは別の、呼び出しの取り決め**である。
#:
#: `unknown` の文は S10-3 の G12 で 2 度直した。どちらも実測で分かった。
#: 1. 裏側（確定するなら確定した値を返す）が無く、解き手が「`None` が 1 つでもあれば `None`」と
#:    読んで三値論理のケースを落とした（7 件の不合格すべてがこの型）。
#: 2. 裏側を足したら、今度は**計算にも**determinacy を広げ、「経過月数は 0 か 1 のどちらでも
#:    割合は同じだから確定」と推論して外した（3 件）。
#: `spec/interp.py` の意味論は **`and`/`or`/`if` だけ Kleene の三値、算術・比較・表引き・日付は厳密**
#: である。取り決めの文もそのとおりに書く（`CLAUDE.md` 守ること 8）。
CONVENTIONS = {
    "call": "キーワード引数で呼び出す",
    "money": "金額は整数（円）",
    "unknown": (
        "入力が None で結果を確定できないときは None を返す。"
        "「かつ」「または」で条件を組む判定は三値論理で、"
        "ほかの条件だけで結論が決まるなら、None の条件があっても確定した値を返す"
        "（例：いずれかの条件を満たさないと分かっていれば、残りが不明でも「支払わない」で確定する）。"
        "いっぽう計算（加減乗除・表引き・日付の計算）は厳密で、"
        "不明が混じれば結果も不明とする（取りうる値がすべて同じ結果になる場合も不明のままとする）"
    ),
    "date": "日付の引数は datetime.date",
    "bool": "真偽は三値（確定できないときは None）",
}


def card(
    rs: RuleSet, doc: Doc, rule_id: str, content_id: str, hint: str = "H0", units: list[str] | None = None
) -> dict:
    if hint not in HINT_LEVELS:
        raise ValueError(f"知らないヒントの水準: {hint}")
    r = rs.rules[rule_id]
    fn = rs.function_of(rule_id)
    out: dict = {
        "task_id": f"{content_id}:{fn}",
        "content_id": content_id,
        "rule_id": rule_id,
        "function": fn,
        "title": r["title"],
        "kind": r["kind"],
        "hint": hint,
        "inputs": [
            {
                "name": name,
                "type": spec["type"],
                "unit": spec.get("unit"),
                "desc": spec["desc"],
                "origin": spec["origin"],
                "nullable": True,
                **({"min": spec["min"]} if "min" in spec else {}),
                **({"max": spec["max"]} if "max" in spec else {}),
            }
            for name, spec in r.get("inputs", {}).items()
        ]
        + [
            # 明細（1 件 1 行の集合）。`list[dict]` で渡す
            {
                "name": name,
                "type": "list",
                "unit": None,
                "desc": "明細の並び（1 件ごとに次の項目を持つ辞書）",
                "origin": "claim_fact",
                "nullable": True,
                "fields": [
                    {
                        "name": f,
                        "type": fs["type"],
                        "unit": fs.get("unit"),
                        "desc": fs["desc"],
                        "nullable": True,
                    }
                    for f, fs in coll["fields"].items()
                ],
                "max_items": coll.get("max_items"),
            }
            for name, coll in r.get("collections", {}).items()
        ],
        "output": {"type": r["output"]["type"], "unit": r["output"].get("unit"), "nullable": True},
        "conventions": dict(CONVENTIONS),
    }
    if hint in ("H1", "H2"):
        cites = list(dict.fromkeys(doc.citation(s["unit"]) for s in r["sources"]))
        out["citations"] = cites
    if hint == "H2":
        out["evidence_units"] = list(units or [s["unit"] for s in r["sources"]])
    return out


def cards(rs: RuleSet, doc: Doc, content_id: str, hint: str, answer: list[dict]) -> list[dict]:
    units = {a["rule"]: a["units"] for a in answer}
    return [card(rs, doc, rid, content_id, hint, units.get(rid)) for rid in rs.rules]
