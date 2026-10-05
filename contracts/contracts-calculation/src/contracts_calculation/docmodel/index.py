"""契約書JSON（source.json）→ 文書モデル（単位・参照・定義語・数値・当事者の索引）。

本体の `derived` を信頼して索引にする。`derived` が無い source.json（build 前）は受け付けない。
単位 = 根拠として指せる最小のテキスト。節点（a1_p2）・表セル（tbl_x__r1c2）の両方が
`derived.plain_text` に載っているので、それをそのまま単位の全集合とする。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class Party:
    """当事者。alias は紙面の呼称（甲・乙）、name は架空の正式名称。"""

    key: str
    alias: str
    name: str
    role_label: str | None = None


@dataclass(frozen=True)
class Unit:
    """根拠として指せる最小単位。text はラベル無しの本文、citation は「第1条 2」形。"""

    id: str
    kind: str
    citation: str
    text: str
    text_with_label: str
    parent_id: str | None = None


@dataclass(frozen=True)
class TermDef:
    """定義語。"""

    id: str
    term: str
    definition: str


@dataclass
class DocumentIndex:
    """1 文書の索引。"""

    content_id: str
    doctype: str
    seed: int
    title: str
    contract_date: str | None
    parties: dict[str, Party]
    constants: dict[str, str]
    defined_terms: dict[str, TermDef]
    units: dict[str, Unit]
    refs: list[dict] = field(default_factory=list)
    tables: dict[str, dict] = field(default_factory=dict)
    figures: dict[str, dict] = field(default_factory=dict)

    # --- 構築 -----------------------------------------------------------------

    @classmethod
    def from_source(cls, source: dict) -> DocumentIndex:
        derived = source.get("derived")
        if not derived:
            raise ValueError("derived が無い（`keiyaku build` 前の source.json は索引にできない）")
        meta = source["meta"]
        parties = {
            p["key"]: Party(
                key=p["key"],
                alias=p["alias"],
                name=p["name"],
                role_label=p.get("role_label"),
            )
            for p in meta["parties"]
        }
        terms = {
            t["id"]: TermDef(id=t["id"], term=t["term"], definition=_plain(t.get("definition", "")))
            for t in source.get("defined_terms", [])
        }
        labels: dict[str, dict] = derived["labels"]
        plain: dict[str, dict] = derived["plain_text"]
        units: dict[str, Unit] = {}
        for uid, texts in plain.items():
            lab = labels.get(uid, {})
            units[uid] = Unit(
                id=uid,
                kind=lab.get("kind", "cell" if "__r" in uid else "unknown"),
                citation=lab.get("citation", ""),
                text=texts.get("without_label", ""),
                text_with_label=texts.get("with_label", ""),
                parent_id=lab.get("parent_id"),
            )
        return cls(
            content_id=source["content_id"],
            doctype=source["doctype"],
            seed=source.get("seed", 0),
            title=meta["title"],
            contract_date=meta.get("contract_date"),
            parties=parties,
            constants=dict(meta.get("constants") or {}),
            defined_terms=terms,
            units=units,
            refs=list(derived.get("refs", [])),
            tables=dict(derived.get("tables", {})),
            figures=dict(derived.get("figures", {})),
        )

    @classmethod
    def load(cls, content_dir: Path) -> DocumentIndex:
        source = json.loads((Path(content_dir) / "source.json").read_text(encoding="utf-8"))
        return cls.from_source(source)

    # --- 照会 -----------------------------------------------------------------

    def unit(self, unit_id: str) -> Unit:
        return self.units[unit_id]

    def quote_in_unit(self, unit_id: str, quote: str) -> bool:
        """逐語照合：引用が単位のテキスト（ラベル有り・無しのどちらか）に含まれるか。"""
        u = self.units.get(unit_id)
        if u is None:
            return False
        return quote in u.text or quote in u.text_with_label

    def find_units_containing(self, needle: str) -> list[str]:
        """文字列を含む単位 ID の一覧（ID 順で安定）。"""
        return sorted(uid for uid, u in self.units.items() if needle in u.text)

    def party_by_alias(self, alias: str) -> Party | None:
        for p in self.parties.values():
            if p.alias == alias:
                return p
        return None

    def constant_units(self, key: str) -> list[str]:
        """定数の値（表記）が紙面に現れる単位の一覧。値の重複出現の検査に使う。"""
        surface = self.constants.get(key)
        if not surface:
            return []
        return self.find_units_containing(surface)


def _plain(value) -> str:
    """RichText（文字列または段落の配列）を素朴に連結する。"""
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "".join(_plain(v) for v in value)
    if isinstance(value, dict):
        return _plain(value.get("text", ""))
    return str(value)
