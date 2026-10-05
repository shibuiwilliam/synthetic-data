"""タスクカード：評価対象システムへ渡す関数の契約（DESIGN.md §13.2）。

ヒントは hints に 3 水準で持ち、評価側（evalkit）が水準に応じて削って渡す。
H0 = 関数名と入出力だけ ／ H1 = H0＋主な条の条番号 ／ H2 = H1＋根拠単位の ID。
"""

from __future__ import annotations

from ..spec.model import BUSINESS_DAY_OPS, CalcSpec
from .cases import rule_ops

_CONVENTIONS = {
    "call": "キーワード引数で呼び出す",
    "money": "金額は整数（円）",
    "date": "日付は datetime.date（テストデータでは YYYY-MM-DD の文字列）",
    "unknown": "入力が None で結果を確定できないときは None を返す",
    "calendar": "uses_calendar が true の関数は holidays（frozenset[date]）を受け取る",
}


def build_taskcards(spec: CalcSpec, answer_key: list[dict], citations: dict[str, str]) -> list[dict]:
    cards: list[dict] = []
    cid = spec.document.get("content_id", "")
    key_by_rule = {a["rule"]: a for a in answer_key}
    for rule in spec.rules:
        ak = key_by_rule.get(rule.id, {})
        inputs = []
        for name, decl in rule.inputs.items():
            entry = {
                "name": name,
                "type": decl.type,
                "desc": decl.desc,
                "origin": decl.origin,
                "nullable": True,
            }
            if decl.unit:
                entry["unit"] = decl.unit
            inputs.append(entry)
        article = ak.get("article")
        card = {
            "task_id": f"{cid}:{rule.id}",
            "function": rule.function,
            "title": rule.title,
            "kind": rule.kind,
            **({"parties": rule.parties} if rule.parties else {}),
            "inputs": inputs,
            "output": {
                "type": rule.output.get("type", "int"),
                **({"unit": rule.output["unit"]} if rule.output.get("unit") else {}),
                "nullable": True,
            },
            "uses_calendar": bool(rule_ops(rule) & BUSINESS_DAY_OPS),
            "conventions": dict(_CONVENTIONS),
            "hints": {
                "H1": {"articles": [citations.get(article, article)] if article else []},
                "H2": {"units": ak.get("units", []) + ak.get("definition_units", [])},
            },
        }
        cards.append(card)
    return cards


def strip_hints(card: dict, level: str) -> dict:
    """ヒント水準に応じてタスクカードを削る（H0 / H1 / H2）。"""
    out = {k: v for k, v in card.items() if k != "hints"}
    if level == "H0":
        return out
    hints = card.get("hints", {})
    if level == "H1":
        out["hints"] = {"articles": hints.get("H1", {}).get("articles", [])}
    elif level == "H2":
        out["hints"] = {
            "articles": hints.get("H1", {}).get("articles", []),
            "units": hints.get("H2", {}).get("units", []),
        }
    return out
