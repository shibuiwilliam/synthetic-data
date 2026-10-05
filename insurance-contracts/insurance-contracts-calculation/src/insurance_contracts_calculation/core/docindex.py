"""約款JSON（schema_version 1.0）の索引化。

読取結果JSONを「テキスト単位（unit）」の集合と参照グラフに展開する。
以降の候補選定・根拠検証・コンテキスト組立はすべてこの索引の上で決定的に行う。
"""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

PLACEHOLDER = re.compile(r"\{(const|term|ref|fn):([^}]+)\}")


@dataclass
class Unit:
    """根拠として引用できる最小のテキスト単位。"""

    id: str
    #: paragraph / item / cell / table_note / footnote / formula / figure /
    #: term / caption / box_title / list_item
    utype: str
    raw: str  # {const:..} 等のプレースホルダを残した原文
    text: str  # プレースホルダ解決後の文
    owner: str | None  # 属する本文ノードID（条・項など）
    block: str | None  # 属するブロックID（表・図・算式・囲み）
    zone: str  # body / appendix / rider / front / back / terms
    extra: dict = field(default_factory=dict)


class Doc:
    def __init__(self, path: str | Path | None = None, data: dict | None = None):
        self.path = Path(path) if path is not None else Path("<memory>")
        if data is None:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        self.data = data
        d = self.data
        self.content_id: str = d["content_id"]
        self.meta: dict = d["meta"]
        self.constants: dict[str, str] = dict(d["meta"].get("constants", {}))
        self._fn_marker = _footnote_marker_format(d["meta"])
        self.terms: dict[str, dict] = {t["id"]: t for t in d.get("defined_terms", [])}
        self.labels: dict[str, dict] = d["derived"]["labels"]
        self.plain: dict[str, dict] = d["derived"]["plain_text"]
        self.refs: list[dict] = d["derived"]["refs"]
        #: (引用元の単位ID, 参照先ID) → 本体が実際に描いた文字列。
        #: `{ref:}` の表示は引用元からの相対（最小共通祖先より下の鎖＋条の見出し文言）で決まり、
        #: `labels[..].citation` とは別物である。本体の規則を写すのは誤りの元なので、
        #: 本体が `derived.refs` に残した結果をそのまま使う。
        self._rendered_refs: dict[tuple[str, str], str] = {
            (r["from_id"], r["to_id"]): r["rendered"] for r in self.refs
        }
        self.nodes: dict[str, dict] = {}
        self.parent: dict[str, str | None] = {}
        self.blocks: dict[str, dict] = {}
        self.block_owner: dict[str, str | None] = {}
        self.units: dict[str, Unit] = {}
        self._build()

    @classmethod
    def from_dict(cls, data: dict) -> Doc:
        """ファイルを介さずに索引を作る（生成の途中で使う）。"""
        import copy

        return cls(None, copy.deepcopy(data))

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        d = self.data
        for n in d["body"]:
            self._walk_node(n, None, "body")
        for n in d["appendices"]:
            self._walk_node(n, None, "appendix")
        fm = d["front_matter"]
        for b in fm.get("preface", []):
            self._walk_block(b, None, "front")
        for key in ("purpose_index", "rider_index", "petname_table"):
            b = fm.get(key)
            if isinstance(b, dict) and b.get("type") == "table":
                self._walk_block(b, None, "front")
        for i, note in enumerate(fm.get("cover", {}).get("notes", []) or []):
            self._add(f"cover__note{i}", "cover_note", note, None, None, "front")
        for b in d["back_matter"].get("colophon", []):
            self._walk_block(b, None, "back")
        for t in d.get("defined_terms", []):
            self._add(f"term_{t['id']}", "term", t["definition"], None, None, "terms", {"term": t["term"]})

    def _zone_of(self, node: dict, zone: str) -> str:
        return "rider" if node["kind"] == "rider" else zone

    def _walk_node(self, n: dict, parent: str | None, zone: str) -> None:
        zone = self._zone_of(n, zone)
        self.nodes[n["id"]] = n
        self.parent[n["id"]] = parent
        n["_zone"] = zone
        if n.get("text"):
            self._add(n["id"], n["kind"], n["text"], n["id"], None, zone)
        for b in n.get("blocks", []):
            self._walk_block(b, n["id"], zone)
        for c in n.get("children", []):
            self._walk_node(c, n["id"], zone)

    def _walk_block(self, b: dict, owner: str | None, zone: str, box: str | None = None) -> None:
        bid, t = b["id"], b["type"]
        self.blocks[bid] = b
        self.block_owner[bid] = owner
        if t == "paragraph":
            self._add(bid, "paragraph", b["text"], owner, box, zone, {"in_box": box is not None})
        elif t == "table":
            if b.get("caption"):
                self._add(f"{bid}__caption", "caption", b["caption"], owner, bid, zone)
            for row in b["grid"]:
                for cell in row:
                    if cell.get("text"):
                        self._add(
                            cell["id"], "cell", cell["text"], owner, bid, zone, {"role": cell.get("role")}
                        )
            for i, note in enumerate(b.get("notes", []) or []):
                self._add(f"{bid}__note{i}", "table_note", note, owner, bid, zone)
        elif t == "formula":
            parts = []
            for term in b["terms"]:
                if "box" in term:
                    parts.append(term["box"])
                elif "op" in term:
                    parts.append(term["op"])
                elif "fraction" in term:
                    parts.append(f"{term['fraction']['num']} ÷ {term['fraction']['den']}")
            self._add(bid, "formula", " ".join(parts), owner, bid, zone)
            if b.get("alt"):
                self._add(f"{bid}__alt", "formula_alt", b["alt"], owner, bid, zone)
        elif t == "figure":
            if b.get("caption"):
                self._add(f"{bid}__caption", "caption", b["caption"], owner, bid, zone)
            if b.get("alt"):
                self._add(f"{bid}__alt", "figure", b["alt"], owner, bid, zone)
            for i, fact in enumerate(b.get("facts", []) or []):
                self._add(f"{bid}__fact{i}", "figure", fact, owner, bid, zone)
            dia = b.get("diagram", {}) or {}
            for n in dia.get("nodes", []) or []:  # 図だけに書かれた規定の根拠にできるようにする
                if n.get("label"):
                    self._add(
                        f"{bid}__{n['id']}",
                        "figure_node",
                        n["label"],
                        owner,
                        bid,
                        zone,
                        {"shape": n.get("shape")},
                    )
            for i, e in enumerate(dia.get("edges", []) or []):
                if e.get("label"):
                    self._add(f"{bid}__e{i}", "figure_edge", e["label"], owner, bid, zone)
        elif t == "box":
            if b.get("title"):
                self._add(f"{bid}__title", "box_title", b["title"], owner, bid, zone)
            for inner in b.get("blocks", []):
                self._walk_block(inner, owner, zone, box=bid)
        elif t == "footnotes":
            for note in b.get("notes", []):
                self._add(f"{bid}__n{note['n']}", "footnote", note["text"], owner, bid, zone)
        elif t == "list":

            def items(lst):
                for it in lst:
                    self._add(
                        it["id"], "list_item", it["text"], owner, bid, zone, {"in_box": box is not None}
                    )
                    items(it.get("children", []))

            items(b.get("items", []))

    def _add(self, uid, utype, raw, owner, block, zone, extra=None) -> None:
        text = self.plain[uid]["without_label"] if uid in self.plain else self.resolve(raw)
        self.units[uid] = Unit(uid, utype, raw, text, owner, block, zone, extra or {})

    # ---------------------------------------------------------------- helpers
    def resolve(self, raw: str, *, from_id: str | None = None) -> str:
        """プレースホルダを表示文字列に解決する（derived.plain_text が無い単位用）。

        `from_id` を渡すと、`{ref:}` をその単位から見た表示文字列
        （本体が `derived.refs` に残したもの）に解決する。渡さないと `citation` で代用する。
        """

        def sub(m: re.Match) -> str:
            kind, key = m.group(1), m.group(2)
            if kind == "const":
                return self.constants.get(key, m.group(0))
            if kind == "term":
                return self.terms.get(key, {}).get("term", m.group(0))
            if kind == "ref":
                return self.ref_text(key, from_id)
            return self._fn_marker(key)

        return PLACEHOLDER.sub(sub, raw)

    def ref_text(self, to_id: str, from_id: str | None = None) -> str:
        """`{ref:to_id}` の表示文字列。引用元が分かれば本体の描画結果をそのまま返す。"""
        if from_id is not None:
            hit = self._rendered_refs.get((from_id, to_id))
            if hit is not None:
                return hit
        return self.labels.get(to_id, {}).get("citation") or f"{{ref:{to_id}}}"

    def citation(self, uid: str) -> str:
        """人が読める根拠表記（例: 第2章 第4条 (2)）。"""
        u = self.units.get(uid)
        node = uid if uid in self.labels else (u.owner if u else None)
        base = self.labels[node]["citation"] if node in self.labels else ""
        if u and u.block and u.block in self.blocks:
            cap = self.data["derived"]["tables"].get(u.block, {}).get("caption_label") or self.data[
                "derived"
            ]["figures"].get(u.block, {}).get("caption_label")
            if cap:
                base = f"{base} {cap}".strip()
        if u and u.utype == "term":
            base = f"用語「{u.extra['term']}」"
        return base or uid

    def article_of(self, node_id: str | None) -> str | None:
        """最も近い条（article）または別表節。なければ自身。"""
        cur = node_id
        while cur is not None:
            if self.nodes[cur]["kind"] in ("article", "appendix_section"):
                return cur
            cur = self.parent.get(cur)
        return node_id

    def placeholders(self, uid: str, kind: str) -> list[str]:
        return [m.group(2) for m in PLACEHOLDER.finditer(self.units[uid].raw) if m.group(1) == kind]


#: 黒丸数字（本体 `numbering.BLACK_CIRCLED`。`footnote_style: remarks_box` のマーカー）
BLACK_CIRCLED = "❶❷❸❹❺❻❼❽❾❿"
_FULLWIDTH = str.maketrans("0123456789", "０１２３４５６７８９")


def _footnote_marker_format(meta: dict):
    """`{fn:n}` の表示文字列を作る関数を、文書の `meta` から組む。

    本体の `numbering.footnote_marker` と同じ規則にそろえる。ここを `（*1）` に決め打ちすると、
    `digit_style: fullwidth` の文書（例: quake-0004）で根拠の引用が原文と 1 文字違い、
    G2 が落ちる。同じ規則を 2 か所に書くのは本来よくないが、本体は読むだけなので写している。
    """
    style = meta.get("digit_style", "halfwidth")
    scheme = meta.get("numbering_scheme", "nonlife")
    footnote_style = meta.get("footnote_style", "inline")

    def fmt(key: str) -> str:
        if not key.isdigit():
            return f"（*{key}）"
        n = int(key)
        if footnote_style == "remarks_box":
            return BLACK_CIRCLED[n - 1] if 1 <= n <= len(BLACK_CIRCLED) else f"({n})"
        body = str(n).translate(_FULLWIDTH) if style == "fullwidth" else str(n)
        return f"（注{body}）" if scheme == "life" else f"（*{body}）"

    return fmt


# ---------------------------------------------------------------- 数値正規化
_KANJI_UNIT = {"万": 10_000, "億": 100_000_000, "千": 1_000}
_NUM = r"[0-9][0-9,]*(?:\.[0-9]+)?"


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s)


def parse_quantity(s: str) -> dict | None:
    """「5万円」「1億円」「年1.5%」「30日」「無制限」等を {value, unit} に正規化する。

    解釈できない表現（「払込期月の翌月初日から末日まで」等）は None を返し、
    呼び出し側で「非数値パラメータ」として人の確認に回す。
    """
    t = nfkc(s).strip()
    if t == "無制限":
        return {"value": None, "unit": "JPY", "unlimited": True}
    m = re.fullmatch(rf"(?:年|満)?({_NUM})(万|億|千)?(円|日|営業日|か月|ヶ月|年|歳|級|回|%|割|名|人)", t)
    if not m:
        return None
    num = float(m.group(1).replace(",", ""))
    if m.group(2):
        num *= _KANJI_UNIT[m.group(2)]
    unit = {
        "円": "JPY",
        "日": "DAY",
        "営業日": "BUSINESS_DAY",
        "か月": "MONTH",
        "ヶ月": "MONTH",
        "年": "YEAR",
        "歳": "AGE",
        "級": "GRADE",
        "回": "COUNT",
        "%": "PERCENT",
        "割": "WARI",
        "名": "PERSON",
        "人": "PERSON",
    }[m.group(3)]
    value = int(num) if float(num).is_integer() else num
    return {"value": value, "unit": unit}


QUANTITY_IN_TEXT = re.compile(
    rf"({_NUM})(万|億|千)?(円|営業日|日|か月|ヶ月|年|歳|級|回|%|割|名|人|親等|倍|時|区分)"
)


def quantities_in(text: str) -> list[str]:
    """文中の「数値＋単位」表現を列挙する（網羅性台帳で使用）。"""
    return [m.group(0) for m in QUANTITY_IN_TEXT.finditer(nfkc(text))]
