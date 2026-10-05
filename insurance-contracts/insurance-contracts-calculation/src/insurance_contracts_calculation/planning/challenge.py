"""ラベル付きの難所（challenge モード。DESIGN.md §9.3）。

通常モードは**一義に読める文書だけ**を作る。challenge モードでは、あえて次を入れ、
正解表にラベルを付ける。評価対象システムが「実装できない、確認が要る」と報告できるかを測る。

| 種別 | 入れ方 | 採点 |
|---|---|---|
| `omission` | 明示性の要件を 1 つ外す（端数処理の方向、境界の向き） | 指摘の有無 |
| `unusual` | 定数の関係が通常の約款と逆になっている | 指摘の有無 |

**通常モードの正しさを壊さないことが最優先**である。
- 通常モードの文書に難所が混ざらないことをテストで固定する（`--challenge` を付けたときだけ入る）。
- 欠落を入れたルールのテストは、**2 通りの読みで同じ結果になるケースだけ**を使う。
  どちらの読みかは `alt_label` が指す変異（`testgen/mutation.py`）で表す。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from ..patterns.base import RuleDraft

KINDS = ("omission", "unusual")

#: 外せる明示性の要件 → (元の文型, 差し替える文型, 別の読みを表す変異のラベル, 連れて外す要件)
_OMISSIONS = {
    "rounding": ("round", "round_unspecified", "端数処理", ("order:rate_then_rounding",)),
    "threshold": ("case", "case_vague", "→gt", ()),
}


@dataclass
class Trap:
    """入れた難所。正解表にそのまま載せる。"""

    rule_id: str
    kind: str
    #: 何を指摘できれば正解か
    expect: str
    dropped_obligation: str | None = None
    #: 別の読みを表す変異のラベル（テストから外すケースを決めるのに使う）
    alt_label: str | None = None
    note: str = ""
    excluded_inputs: list[str] = field(default_factory=list)


def inject(drafts: list[RuleDraft], rng: random.Random, kinds: tuple[str, ...] = KINDS) -> list[Trap]:
    """下書きに難所を入れ、入れた内容を返す（`drafts` を書き換える）。"""
    traps: list[Trap] = []
    for draft in drafts:
        for kind in _order(kinds, rng):
            trap = _inject_one(draft, kind, rng)
            if trap is not None:
                traps.append(trap)
                break
    return traps


def _order(kinds: tuple[str, ...], rng: random.Random) -> list[str]:
    out = list(kinds)
    rng.shuffle(out)
    return out


def _inject_one(draft: RuleDraft, kind: str, rng: random.Random) -> Trap | None:
    if kind == "omission":
        for oid in list(draft.obligations):
            family = oid.split(":")[0]
            if family not in _OMISSIONS:
                continue
            shape, vague, alt, companions = _OMISSIONS[family]
            step = next((s for s in draft.steps if s.hint.get("shape") == shape), None)
            if step is None:
                continue
            step.hint = {**step.hint, "shape": vague}
            # 文を 1 つ落とすと、その文に頼っていた要件も満たせなくなる。まとめて外す
            drop = {oid, *companions}
            draft.obligations = [o for o in draft.obligations if o not in drop]
            draft.difficulty = {**draft.difficulty, "trap": "omission"}
            return Trap(
                draft.rule_id,
                "omission",
                f"「{oid}」に当たる定めが文言に無く、読みが 2 通りあること",
                dropped_obligation=oid,
                alt_label=alt,
                note="端数処理の方向・境界の向きが書かれていない",
            )
        return None
    if kind == "unusual":
        if len(draft.consts) < 2:
            return None
        a, b = draft.consts[0], draft.consts[1]
        if a.unit != b.unit or a.value <= b.value:
            return None
        draft.difficulty = {**draft.difficulty, "trap": "unusual"}
        return Trap(
            draft.rule_id,
            "unusual",
            f"{b.name}（{b.surface}）が {a.name}（{a.surface}）より小さく、通常の約款とは逆の関係であること",
            note="定数の大小が通常と逆",
        )
    return None


def filter_cases(rs, cases: list[dict], traps: list[dict]) -> list[dict]:
    """2 通りの読みで結果が分かれるケースをテストから外す。

    `traps` は `Trap` の列。欠落を入れたルールでは、もう 1 つの読み（`alt_label` の変異）と
    結果が一致するケースだけを残す。設例は常に残す（約款に書いた値そのものだから）。
    """
    from ..spec import interp
    from ..testgen import mutation

    alt_exprs: dict[str, dict] = {}
    for tr in traps:
        if not tr.alt_label:
            continue
        for name, expr in mutation.mutants(rs, tr.rule_id):
            if tr.alt_label in name:
                alt_exprs[tr.rule_id] = expr
                break
    if not alt_exprs:
        return cases
    out = []
    for c in cases:
        alt = alt_exprs.get(c["rule_id"])
        if alt is None or c["kind"] == "example":
            out.append(c)
            continue
        inputs = _restore(rs, c)
        base = interp._ev(rs, rs.full_expr(c["rule_id"]), inputs, None)
        if base == interp._ev(rs, alt, inputs, None):
            out.append(c)
    return out


def _restore(rs, case: dict) -> dict:
    import datetime as dt

    spec = rs.rules[case["rule_id"]].get("inputs", {})
    return {
        k: (dt.date.fromisoformat(v) if (spec.get(k, {}).get("type") == "date" and v is not None) else v)
        for k, v in case["inputs"].items()
    }
