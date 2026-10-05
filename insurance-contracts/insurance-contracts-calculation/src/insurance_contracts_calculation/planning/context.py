"""既定の約款から文脈を読む。

読み取るのは、種目・章立て・定義語・既存の定数・付いている特約・既存の保険金の名称である。
パターンの `applicable()` と衝突回避（G8）、追加先の決定（§8.5）がここを見る。

用語は**概念**で引く。既定の約款ごとに用語IDが違うので（`insured_car` / `target_car` など）、
パックの `term_aliases` で候補を並べ、実在するものを `{term:ID}` に、無ければ平語に落とす。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import cached_property

from ..core import packs
from ..realize import patch as _patch

#: 文中の用語概念トークン（`{t:car}`）。パックの語彙だけが使う
TERM_TOKEN = re.compile(r"\{t:([a-z_]+)\}")

#: 既存の保険金の名称を拾う言い回し
BENEFIT_RE = re.compile(r"([一-龥ぁ-んァ-ヶA-Za-z0-9]{2,20}?(?:保険金|給付金|費用保険金))")


@dataclass
class Context:
    """1 文書分の文脈。`data` は追加前の draft 辞書（変更しない）。"""

    content_id: str
    genre: str
    data: dict
    pack: packs.Pack
    #: ページ余裕（上限 20 ページまでの見積りの余り）。追加先の選別に使う
    page_slack: float | None = None
    _added_benefits: set[str] = field(default_factory=set)

    # ---------------------------------------------------------------- 索引
    @cached_property
    def terms(self) -> dict[str, str]:
        """用語ID → 表示語。"""
        return {t["id"]: t["term"] for t in self.data.get("defined_terms") or []}

    @cached_property
    def constants(self) -> dict[str, str]:
        return dict(self.data["meta"].get("constants") or {})

    @cached_property
    def const_surfaces(self) -> set[str]:
        """既存の定数の**表記**の集合。設例で同じ表記を使うと本体 lint L11 に当たる。"""
        return set(self.constants.values())

    @cached_property
    def node_ids(self) -> set[str]:
        return _patch.node_ids(self.data)

    @cached_property
    def block_ids(self) -> set[str]:
        return _patch.block_ids(self.data)

    @cached_property
    def riders(self) -> dict[str, str]:
        return {n["id"]: n.get("title") or "" for n in _patch.iter_nodes(self.data) if n["kind"] == "rider"}

    @cached_property
    def benefits(self) -> set[str]:
        """既定の約款に出てくる保険金・給付金の名称。"""
        out: set[str] = set()
        for text in _iter_strings(self.data):
            out.update(BENEFIT_RE.findall(text))
        return out

    @cached_property
    def chapter_titles(self) -> dict[str, str]:
        return {n["id"]: n.get("title") or "" for n in _patch.chapters(self.data)}

    @cached_property
    def base_literals(self) -> str:
        """既定の約款の地の文（`{const:}` などのトークンを除いたもの）をつないだもの。

        ここに現れる表記を新しい定数の値に選ぶと、本体 lint L11（定数の直書き）に当たる。
        """
        token = re.compile(r"\{[a-z]+:[^}]+\}")
        return "".join(token.sub("", s) for s in _iter_strings(self.data))

    def surface_clashes(self, surface: str) -> bool:
        """**自分が書く素の文字列**として使えない表記か。

        既存の定数の表記と重なると本体 lint L11（定数の直書き）に当たる。
        表の割合や設例の数値がこれに当たる。
        """
        return len(surface) >= 2 and any(s in surface for s in self.const_surfaces if len(s) >= 2)

    def const_value_clashes(self, surface: str) -> bool:
        """**新しく足す定数の表記**として使えないか。

        既定の約款の地の文に同じ表記があると、その文が「定数の直書き」と見なされて
        L11 に当たる（既存の文は直せないので、こちらの値を変える）。
        """
        if len(surface) < 2:
            return False
        return surface in self.base_literals or surface in self.const_surfaces

    def reject_value(self, value: int, unit: str) -> bool:
        """定数の候補として使えない値か（表記が既定の約款とぶつかる）。"""
        from ..core import numbers_ja as nj

        try:
            return self.const_value_clashes(nj.surface(value, unit))
        except ValueError:
            return False

    # ------------------------------------------------------------ 用語の解決
    def term_id(self, concept: str) -> str | None:
        for tid in self.pack.term_aliases.get(concept, ()):
            if tid in self.terms:
                return tid
        return None

    def term(self, concept: str) -> str:
        """`{term:ID}` か、用語が無ければ平語。"""
        tid = self.term_id(concept)
        if tid:
            return f"{{term:{tid}}}"
        fallback = self.pack.fallbacks.get(concept)
        if fallback is None:
            raise packs.PackError(f"{self.genre}: 用語概念 {concept} に fallback が無い")
        return fallback

    def resolve_tokens(self, text: str) -> str:
        """パックの語彙にある `{t:concept}` を解決する。"""
        return TERM_TOKEN.sub(lambda m: self.term(m.group(1)), text)

    # ------------------------------------------------------------ 追加先
    def anchor_node(self, anchor: str) -> dict | None:
        """題材の `anchor` に対応する章（既定の約款の章タイトルで探す）。"""
        wanted = self.pack.chapters.get(anchor, ())
        for node in _patch.chapters(self.data):
            if (node.get("title") or "") in wanted:
                return node
        return None

    # ------------------------------------------------------------ 適用可能性
    def subject_applicable(self, subject: packs.Subject) -> tuple[bool, str]:
        """題材が使えるか。使えない理由も返す（ログに出して黙って外さない）。"""
        if self.anchor_node(subject.anchor) is None:
            return False, f"追加先の章（{subject.anchor}）が無い"
        missing = [c for c in subject.requires_terms if self.term_id(c) is None]
        if missing:
            return False, f"必要な用語が無い: {', '.join(missing)}"
        if subject.benefit in self.benefits:
            return False, f"保険金の名称「{subject.benefit}」が既定の約款と衝突"
        if subject.benefit in self._added_benefits:
            return False, f"保険金の名称「{subject.benefit}」をこの文書で既に使った"
        return True, ""

    def applicable_subjects(self) -> list[packs.Subject]:
        return [s for s in self.pack.subjects if self.subject_applicable(s)[0]]

    def reserve_benefit(self, name: str) -> None:
        self._added_benefits.add(name)

    # ------------------------------------------------------------ 定数名
    def const_name(self, subject_key: str, role: str) -> str:
        """定数名（`<題材>_<役割>`）。既定の約款と衝突したら生成を止める。"""
        name = f"{subject_key}_{role}"
        if name in self.constants:
            raise packs.PackError(f"定数名 {name} が既定の約款と衝突（G8）")
        return name


def _iter_strings(value) -> list[str]:
    out: list[str] = []

    def walk(v) -> None:
        if isinstance(v, str):
            out.append(v)
        elif isinstance(v, dict):
            for x in v.values():
                walk(x)
        elif isinstance(v, list):
            for x in v:
                walk(x)

    walk(value)
    return out


def build_context(base, page_slack: float | None = None) -> Context:
    """`base_adapter.Base` から文脈を作る。"""
    return Context(
        content_id=base.content_id,
        genre=base.genre,
        data=base.data,
        pack=packs.load(base.genre),
        page_slack=page_slack,
    )
