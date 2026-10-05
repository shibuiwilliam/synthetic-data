"""文脈：既定の契約書から、種類・当事者・定数・既存の事項・章構成を読み取る。"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from ..docmodel.index import DocumentIndex

#: 金銭（委託料・賃料・実施料など）を支払う側の当事者の位置（meta.parties の添字）
_PAYER_POSITION = {"lease": 1, "license": 1, "nda": 1}


@dataclass
class Context:
    """1 つの既定の契約書についての文脈。"""

    content_dir: Path
    doc: dict  # doc.json（執筆物の器）
    idx: DocumentIndex
    doctype: str
    digit_style: str
    payer_key: str
    payee_key: str
    chapters: list[tuple[str, str]] = field(default_factory=list)  # (id, title)
    head_matter_id: str | None = None  # 頭書ノードの id（無い文書は None）
    head_item_prefix: str = "head_i"  # 頭書の項目 id の接頭辞（lea は head_s）
    _full_text: str = ""

    @classmethod
    def load(cls, content_dir: Path) -> Context:
        content_dir = Path(content_dir)
        doc = json.loads((content_dir / "doc.json").read_text(encoding="utf-8"))
        idx = DocumentIndex.load(content_dir)
        parties = list(idx.parties.values())
        pos = _PAYER_POSITION.get(idx.doctype, 0)
        payer = parties[pos] if pos < len(parties) else parties[0]
        payee = parties[1 - pos] if 1 - pos < len(parties) else parties[-1]
        src = json.loads((content_dir / "source.json").read_text(encoding="utf-8"))
        chapters = [
            (n.get("id"), n.get("title") or "") for n in src.get("body", []) if n.get("kind") == "chapter"
        ]
        head_id = None
        head_prefix = "head_i"
        for n in src.get("body", []):
            if n.get("kind") == "head_matter":
                head_id = n.get("id")
                children = n.get("children", []) or []
                if children and str(children[0].get("id", "")).startswith("head_s"):
                    head_prefix = "head_s"
        full = "\n".join(u.text for u in idx.units.values())
        return cls(
            content_dir=content_dir,
            doc=doc,
            idx=idx,
            doctype=idx.doctype,
            digit_style=doc["meta"].get("digit_style", "halfwidth"),
            payer_key=payer.key,
            payee_key=payee.key,
            chapters=chapters,
            head_matter_id=head_id,
            head_item_prefix=head_prefix,
            _full_text=full,
        )

    # --- 照会 ---------------------------------------------------------------

    def has_topic(self, *keywords: str) -> bool:
        """既定の契約書に同じ事項の条項があるか（見出しと本文の語で検出）。"""
        return any(kw in self._full_text for kw in keywords)

    def alias(self, key: str) -> str:
        return self.idx.parties[key].alias

    @property
    def constants(self) -> dict[str, str]:
        return dict(self.doc["meta"].get("constants") or {})

    def free_const_name(self, base: str) -> str:
        """既定の契約書と衝突しない定数名を返す。候補が尽きたら止める。"""
        for cand in (base, f"{base}_b"):
            if cand not in self.constants:
                return cand
        raise ValueError(f"定数名が衝突した: {base}（生成を止める）")

    def next_article_ids(self, count: int, chapter_id: str | None = None) -> list[str]:
        """既存 ID と衝突しない連番の条 ID を払い出す（本体の命名規則に従う）。"""
        prefix = f"{chapter_id}_a" if chapter_id else "a"
        pat = re.compile(re.escape(prefix) + r"(\d+)$")
        used = set(self.idx.units)
        top = 0
        for uid in used:
            m = pat.match(uid)
            if m:
                top = max(top, int(m.group(1)))
        out = []
        n = top + 1
        while len(out) < count:
            cand = f"{prefix}{n}"
            if cand not in used:
                out.append(cand)
            n += 1
        return out

    def next_head_item_id(self) -> str:
        """頭書の項目 id を 1 つ払い出す（既存の連番の続き）。"""
        pat = re.compile(re.escape(self.head_item_prefix) + r"(\d+)")
        top = 0
        for uid in self.idx.units:
            m = pat.match(uid)
            if m:
                top = max(top, int(m.group(1)))
        return f"{self.head_item_prefix}{top + 1}"

    def next_appendix_ids(self, count: int) -> list[str]:
        """既存と衝突しない別紙 ID（sch<n>）を払い出す。"""
        pat = re.compile(r"^sch(\d+)")
        top = 0
        for uid in self.idx.units:
            m = pat.match(uid)
            if m:
                top = max(top, int(m.group(1)))
        out = []
        n = top + 1
        while len(out) < count:
            cand = f"sch{n}"
            if cand not in self.idx.units:
                out.append(cand)
            n += 1
        return out

    def pick_chapter(self, hints: tuple[str, ...]) -> str | None:
        """章立ての文書で、追加先の章を選ぶ。該当が無ければ最後の章。"""
        if not self.chapters:
            return None
        for cid, title in self.chapters:
            if any(h in title for h in hints):
                return cid
        return self.chapters[-1][0]
