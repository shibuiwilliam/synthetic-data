"""設例（囲み）の生成。

設例の数値は**仕様を参照インタプリタで計算した値**から作る（DESIGN.md §8.7）。
説明側の記述なので規範の根拠にはせず、正解表では `explanatory_units` に分けて記録する。

本体 lint L11 は「`meta.constants` の表記が素の文字列で書かれている」ことを警告する。
設例に出る数値がどれかの定数の表記と重なると当たるので、
(1) 自分が足した定数と一致する値は `{const:キー}` で書き、
(2) それでも重なる候補は捨てて次の候補に移る（`collides`）。
"""

from __future__ import annotations

import datetime as dt
import random

from ..core import numbers_ja as nj
from ..spec import interp
from ..spec.validate import RuleSet
from . import lexicon_ja as lex


def surface_of(value, unit: str | None) -> str:
    if isinstance(value, dt.date):
        return nj.date_ja(value)
    if isinstance(value, bool):
        return "はい" if value else "いいえ"
    if value is None:
        return "不明"
    return nj.surface(int(value), unit or "JPY")


def condition_phrase(spec: dict, value) -> str:
    """設例の条件 1 つを日本語にする（真偽は「…場合」、値は「…が◯◯」）。"""
    desc = spec["desc"]
    if spec["type"] == "bool":
        stem = desc.removesuffix("かどうか")
        return f"{stem}場合" if value else f"{stem}場合に該当しないとき"
    return f"{desc}が{surface_of(value, spec.get('unit'))}"


def condition_head(rule: dict, case: dict) -> str:
    """条件を並べた前置き。真偽の条件を先に置き、値の条件は最後に「のとき」で締める。"""
    bools, values = [], []
    for name, v in case.items():
        spec = rule["inputs"].get(name)
        if spec is None:
            continue
        (bools if spec["type"] == "bool" else values).append(condition_phrase(spec, v))
    parts = []
    if bools:
        parts.append("、".join(bools))
    if values:
        parts.append("、".join(values) + "のとき")
    return "で、".join(parts) or "この場合"


def const_token(value, unit: str | None, consts: dict[str, str]) -> str:
    """自分が足した定数と同じ値なら `{const:}` で書く（L11 を避ける）。"""
    s = surface_of(value, unit)
    for key, surface in consts.items():
        if surface == s:
            return f"{{const:{key}}}"
    return s


def texts_for(
    rs: RuleSet,
    rule_id: str,
    inputs_sets: list[dict],
    own_consts: dict[str, str],
    rng: random.Random,
) -> tuple[list[str], list[tuple[dict, object]]]:
    """設例の文と、(入力, 期待値) の組を返す。期待値は参照インタプリタで求める。"""
    rule = rs.rules[rule_id]
    expr = rs.full_expr(rule_id)
    out_texts: list[str] = []
    pairs: list[tuple[dict, object]] = []
    unit = rule["output"].get("unit")
    for case in inputs_sets:
        value = interp._ev(rs, expr, case, None)
        head = condition_head(rule, case)
        if rule["output"]["type"] == "bool":
            tail = "お支払いします。" if value else "お支払いしません。"
            out_texts.append(f"{head}は、{rule['title'].replace('の支払の判定', '')}を{tail}")
        elif value == 0:
            out_texts.append(
                f"{head}は、{_benefit(rule)}を"
                + lex.pick(rng, ["お支払いしません。", "お支払いできません。"])
            )
        else:
            amount = const_token(value, unit, own_consts)
            out_texts.append(
                f"{head}は、{amount}を" + lex.pick(rng, ["お支払いします。", "お支払いします。"])
            )
        pairs.append((case, value))
    return out_texts, pairs


def _benefit(rule: dict) -> str:
    return rule["title"].removesuffix("の額")


def collides(texts: list[str], const_surfaces: set[str]) -> str | None:
    """本体 lint L11 と同じ判定。素の文字列として定数の表記が現れたらその表記を返す。"""
    import re

    literal = "".join(re.sub(r"\{[a-z]+:[^}]+\}", "", t) for t in texts)
    for surface in sorted(const_surfaces):
        if len(surface) >= 2 and surface in literal:
            return surface
    return None
