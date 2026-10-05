"""ラベル・見出し・参照解決（docs/schema.md §7 / docs/rendering.md）。

**番号方式は Python に持たない。** `numbering/<scheme>.yaml` の宣言を
`keiyaku/numbering_spec.py` が読み、このモジュールがそれを使ってラベルを組む
（docs/architecture.md §2「番号方式の解釈器はコア、定義は宣言」）。

doctype を足しても、このファイルは書き換えなくてよいのが正しい状態。
書き換えたくなったら、宣言スキーマの表現力が足りていないということなので、
`keiyaku/numbering_spec.py` を拡張して理由を `docs/decisions.md` に記録する。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Literal

from keiyaku.models import DigitStyle, LabelInfo, Node, NodeKind
from keiyaku.numbering_spec import (
    CIRCLED,
    LevelSpec,
    SchemeSpec,
    apply_format,
    black_circled,
    load_scheme,
)
from keiyaku.numbering_spec import to_digits as _to_digits

CIRCLED_MAX = len(CIRCLED)

#: 見出しのラベルと文言のあいだは U+3000 の文字で空ける（margin では空けない。docs/rendering.md §1）
HEADING_SPACE = "　"


def to_digits(n: int, style: DigitStyle) -> str:
    """整数を digit_style に従って文字列にする。"""
    return _to_digits(n, style)


@dataclass(frozen=True)
class NumberWarning:
    """番号付けで妥協した箇所（lint が warning として拾う）。"""

    node_id: str
    message: str


def circled(n: int, style: DigitStyle, warnings: list[NumberWarning] | None = None, node_id: str = "") -> str:
    """丸数字。⑳ を超えたら括弧数字にフォールバックし警告する。"""
    spec = LevelSpec(format="{n}", counter="circled")
    return apply_format(
        spec,
        n,
        style,
        on_fallback=(lambda msg: warnings.append(NumberWarning(node_id, msg)))
        if warnings is not None
        else None,
    )


@dataclass
class NumberingContext:
    """1 文書ぶんの番号付け設定。方式の中身は `spec`（宣言）が持つ。"""

    scheme: str
    digit_style: DigitStyle = "fullwidth"
    warnings: list[NumberWarning] = field(default_factory=list)
    #: 条見出しの体裁。`above` は見出し文言だけを条の上に置き、条ラベルを第1項に走り込ませる。
    article_heading: Literal["inline", "above", "plain"] = "inline"
    #: 条末脚注の体裁。`remarks_box` は黒丸数字のマーカーと「備考」の枠。
    footnote_style: Literal["inline", "remarks_box"] = "inline"
    #: 宣言の置き場（テストで fixture を差し替えるため）
    numbering_dir: Path | None = None

    @property
    def spec(self) -> SchemeSpec:
        return load_scheme(self.scheme, self.numbering_dir)

    @property
    def continuous_articles(self) -> bool:
        return self.spec.continuous_articles

    @property
    def paragraph_ref_written(self) -> bool:
        """印字が無番号でも参照を「第N項」「第N号」と書き下す方式か。"""
        return self.spec.paragraph_ref_style == "written"

    def paren(self, body: str) -> str:
        return f"（{body}）" if self.digit_style == "fullwidth" else f"({body})"

    def warn(self, node_id: str, message: str) -> None:
        self.warnings.append(NumberWarning(node_id, message))


def _resolve_level(ctx: NumberingContext, kind: NodeKind, scope: str) -> LevelSpec | None:
    """その kind の規則を宣言から引く。別表・頭書の中はその scope の宣言を優先する。"""
    return ctx.spec.level(kind, scope=scope)


def appendix_label(ctx: NumberingContext, index: int, kind_label: str | None = None) -> str:
    """別表１ / 付表１ / 附則 のラベル。`kind_label` で呼び名を切り替える。"""
    spec = ctx.spec.appendix
    base = kind_label or spec.kind_label
    # 「附則」のように 1 つ目は番号を付けない方式（宣言の bare_when_first）。
    # 呼び名を上書きしたときも、その方式の慣行に合わせる。
    if spec.bare_when_first and base == spec.kind_label and index <= 1:
        return base
    return f"{base}{to_digits(index, ctx.digit_style)}"


def footnote_marker(ctx: NumberingContext, n: int) -> str:
    """条末脚注のマーカー。書式は宣言の `footnote.inline`、備考枠は黒丸数字。"""
    if ctx.footnote_style == "remarks_box":
        return black_circled(n, ctx.digit_style, lambda msg: ctx.warn("", msg))
    return ctx.spec.footnote.inline.replace("{n}", to_digits(n, ctx.digit_style))


#: 頭書の既定の呼び名。ノードが `kind_label` を持てばそちらが勝つ。
HEAD_MATTER_LABEL = "頭書"


def _counter_key(ctx: NumberingContext, node: Node) -> str:
    """番号を数える単位。別表だけは呼び名（別表／付表／別紙）で分ける。"""
    if node.kind == "appendix":
        return f"appendix:{node.kind_label or ctx.spec.appendix.kind_label}"
    return node.kind


def label_for(
    ctx: NumberingContext,
    kind: NodeKind,
    index: int,
    node_id: str = "",
    siblings: int = 2,
    scope: str = "body",
    kind_label: str | None = None,
) -> str:
    """1 ノードぶんのラベルを宣言から組む。

    `siblings` は同じ親を持つ同種ノードの数（`skip_when_single` の判定に使う）。
    `kind_label` は別表の呼び名（「付表」など）。ノードが持っていればそれを使う。

    `scope` は "body" / "appendix" / "head_matter"。別表・頭書の中はその scope の宣言
    （`appendix_levels` / `head_matter_levels`）を先に見る。そこに規則が無ければ
    本文の規則に落ちる（宣言側で全階層を書かなくてよいようにするため）。
    """
    if kind == "appendix":
        return appendix_label(ctx, index, kind_label)

    level = _resolve_level(ctx, kind, scope)
    if level is None:
        return ""
    if level.unsupported:
        ctx.warn(node_id, level.unsupported)
        return ""
    # 印字上その階層に番号を出さない条件（第1項無番号／単独なら無番号）
    if level.skip_first and index <= 1:
        return ""
    if level.skip_when_single and siblings <= 1:
        return ""
    return apply_format(
        level,
        index,
        ctx.digit_style,
        kind_label=kind_label or ctx.spec.appendix.kind_label,
        on_fallback=lambda msg: ctx.warn(node_id, msg),
    )


def heading_text(kind: NodeKind, label: str, title: str | None, article_heading: str = "inline") -> str:
    """見出し文字列。条は「第１条（告知義務）」、それ以外は「第１章　補償の概要」。

    `article_heading == "above"` のとき、条の見出し行には**見出し文言だけ**が出る
    （「（告知義務）」）。条ラベルは第1項の本文の先頭に走り込む。
    """
    title = title or ""
    if kind == "article" and article_heading == "above":
        return f"（{title}）" if title else label
    if kind == "article" and article_heading == "plain":
        # 条を持たない説明書では、丸数字の小見出しに括弧を使わない（#9）
        return f"{label}{HEADING_SPACE}{title}" if label and title else (label or title)
    if not label:
        return title
    if not title:
        return label
    if kind == "article":
        return f"{label}（{title}）"
    return f"{label}{HEADING_SPACE}{title}"


@dataclass(frozen=True)
class IndexedNode:
    """ツリー上の 1 ノードと、その位置から決まる情報。"""

    node: Node
    parent_id: str | None
    ancestors: tuple[str, ...]  # ルート → 親 の id
    index: int  # 同じ親・同じ kind の中での 1 始まり連番
    siblings: int  # 同じ親・同じ kind のノード数
    depth: int
    in_appendix: bool
    label: str
    heading_text: str
    #: 本文の先頭に走り込みで印字されるラベル（`article_heading == "above"` の第1項）
    run_in_label: str | None = None


class DocumentIndex:
    """文書全体のノード索引。ラベル・パス・参照解決の土台。"""

    def __init__(
        self,
        ctx: NumberingContext,
        body: list[Node],
        appendices: list[Node] | None = None,
        back_matter: list[Node] | None = None,
    ) -> None:
        """`back_matter` は記名押印欄（無番号だが索引には載せる）。

        索引に載せないと `derived.plain_text` にも `citation` にも入らず、
        記名欄が正解データから丸ごと抜ける（docs/schema.md §5）。
        """
        self.ctx = ctx
        self.nodes: dict[str, IndexedNode] = {}
        self.order: list[str] = []
        #: 章をまたぐ通し番号（契約書・定款の条）。別紙は別体系なので数えない
        self._continuous: dict[str, int] = {}
        self._index_children(body, parent_id=None, ancestors=(), depth=0, scope="body")
        self._index_children(appendices or [], parent_id=None, ancestors=(), depth=0, scope="appendix")
        self._index_children(back_matter or [], parent_id=None, ancestors=(), depth=0, scope="body")

    def _index_children(
        self,
        children: list[Node],
        parent_id: str | None,
        ancestors: tuple[str, ...],
        depth: int,
        scope: str,
    ) -> None:
        counters: dict[str, int] = {}
        totals: dict[str, int] = {}
        for child in children:
            totals[_counter_key(self.ctx, child)] = totals.get(_counter_key(self.ctx, child), 0) + 1
        for child in children:
            # 別表は**呼び名ごとに**番号を振る（別表１／付表１・付表２）。
            # ひとまとめに数えると「別表１ の次が 付表２」になって実物と違う。
            key = _counter_key(self.ctx, child)
            counters[key] = counters.get(key, 0) + 1
            index = counters[key]
            if child.kind == "article" and self.ctx.continuous_articles and scope != "appendix":
                # 章をまたいで通しで振る（実物の定款の体裁）
                self._continuous["article"] = self._continuous.get("article", 0) + 1
                index = self._continuous["article"]
            # 別表・頭書の**中**に入ったところからその scope の規則に切り替える
            # （別表そのもの・頭書そのものの label は本文の規則で決める）。
            inner = scope if not (scope == "appendix" and child.kind == "appendix") else "body"
            label = child.number_override or label_for(
                self.ctx,
                child.kind,
                index,
                node_id=child.id,
                siblings=totals[key],
                scope=inner,
                kind_label=child.kind_label,
            )
            self.nodes[child.id] = IndexedNode(
                node=child,
                parent_id=parent_id,
                ancestors=ancestors,
                index=index,
                siblings=totals[key],
                depth=depth,
                in_appendix=scope == "appendix",
                label=label,
                heading_text=heading_text(child.kind, label, child.title, self.ctx.article_heading),
            )
            self.order.append(child.id)
            self._index_children(
                child.children,
                parent_id=child.id,
                ancestors=ancestors + (child.id,),
                depth=depth + 1,
                # 頭書に入ったら、その下は頭書の番号体系で数える
                scope="head_matter" if child.kind == "head_matter" else scope,
            )
            # 条見出しを条の上に置く体裁では、条ラベルを第1項の本文の先頭に走り込ませる
            # （docs/reference_structures.md #12）。条の label は「第23条」のまま残す。
            if self.ctx.article_heading == "above" and child.kind == "article" and label:
                first = next((c for c in child.children if c.kind == "paragraph"), None)
                if first is not None:
                    self.nodes[first.id] = replace(self.nodes[first.id], run_in_label=label)

    def __contains__(self, node_id: object) -> bool:
        return node_id in self.nodes

    def __getitem__(self, node_id: str) -> IndexedNode:
        return self.nodes[node_id]

    def citation(self, node_id: str) -> str:
        """**構造内の位置づけ**を番号だけで連ねた文字列（「第2章 第1条 (1)」）。

        読み取り側が出す位置づけと素直に比較できるよう、見出し文言は入れない。
        番号を持たない特約は題名で示す（「携行品損害補償特約 第1条」）。
        番号も題名も無いノードは飛ばす。
        """
        item = self.nodes[node_id]
        parts: list[str] = []
        for nid in (*item.ancestors, node_id):
            entry = self.nodes[nid]
            if entry.node.kind == "rider":
                token = entry.node.title or ""
            elif entry.node.kind == "head_matter":
                # 頭書は番号を持たない。呼び名（既定「頭書」）そのもので指す
                # （docs/schema.md §11.1・docs/decisions.md 81）。
                token = entry.node.kind_label or HEAD_MATTER_LABEL
            else:
                # **`run_in_label` は使わない。** 条見出しを条の上に置く体裁
                # （`article_heading: above`。約款型）では、条ラベルが第1項の本文の先頭に
                # 走り込む。これを位置づけに混ぜると「第三条 第三条 (1)」と条番号が二重になり、
                # **外から読んだ予測では決して再現できない citation** になっていた
                # （2026-10-02 の V-D で発覚。`contracting` の全 4 文書が該当）。
                # 第1項は無番号なので、位置づけとしては何も足さないのが正しい。
                token = entry.label
            if token:
                parts.append(token)
        return " ".join(parts)

    def labels(self) -> dict[str, LabelInfo]:
        """`derived.labels` を組み立てる。"""
        out: dict[str, LabelInfo] = {}
        for node_id, item in self.nodes.items():
            out[node_id] = LabelInfo(
                label=item.label,
                title=item.node.title or "",
                heading_text=item.heading_text,
                path=[self.nodes[a].heading_text for a in item.ancestors],
                path_ids=list(item.ancestors),
                parent_id=item.parent_id,
                kind=item.node.kind,
                citation=self.citation(node_id),
                depth=item.depth,
                run_in_label=item.run_in_label,
            )
        return out


RefMode = Literal["relative", "short", "full"]

#: 参照表記で「章・節」まで遡ったときは見出し文言を付けない（docs/rendering.md §6.4 の例に合わせる）。
_TITLED_KINDS: frozenset[str] = frozenset({"article"})


def resolve_ref(index: DocumentIndex, from_id: str, to_id: str, mode: RefMode = "relative") -> str:
    """`{ref:}` を解決する。

    - `relative`（既定）：参照元と参照先の **最小共通祖先より下** の鎖を連ねる。
      鎖が条から始まるときだけ条の見出し文言を括弧で添える
      （同条内の項 →「（２）」、他条 →「第２条（通知義務）（２）」、
      他章 →「第４章第３節第１条」）。
    - `short`：条までで打ち切り、見出し文言も付けない（「第２条」）。
    - `full`：最小共通祖先を無視して根からの絶対表記にする。条の見出し文言は常に添える。
    """
    if to_id not in index:
        raise KeyError(to_id)
    target = index[to_id]
    target_chain = target.ancestors + (to_id,)

    if mode == "full":
        chain = list(target_chain)
    else:
        source_chain: tuple[str, ...] = ()
        if from_id in index:
            source = index[from_id]
            source_chain = source.ancestors + (from_id,)
        common = 0
        for a, b in zip(source_chain, target_chain, strict=False):
            if a != b:
                break
            common += 1
        chain = list(target_chain[common:])
        if not chain:  # 自分自身への参照
            chain = [to_id]

    # 条が文書全体で通し番号のとき（定款）、章の冠は要らない。
    # 「第３章第１４条」ではなく「第１４条（決議）」と書くのが実物の体裁で、
    # 同一章内の参照（冠が付かない）との挙動も揃う。
    if index.ctx.continuous_articles and mode != "full":
        for i, cid in enumerate(chain):
            if index[cid].node.kind == "article":
                chain = chain[i:]
                break

    # 別表の中を指す参照は、別表の名前から始める（「附則第３」「別表１第１」）。
    # 番号だけだと本文の条番号と紛らわしい。
    if mode != "short" and chain and index[chain[0]].node.kind == "appendix_section":
        appendix_id = next(
            (a for a in reversed(index[chain[0]].ancestors) if index[a].node.kind == "appendix"),
            None,
        )
        if appendix_id is not None:
            chain = [appendix_id, *chain]

    if mode == "short":
        cut = [
            cid for cid in chain if index[cid].node.kind not in {"paragraph", "item", "subitem", "subsubitem"}
        ]
        chain = cut or chain[:1]

    # relative は「鎖が条から始まるとき」だけ見出し文言を添える（章・節まで遡る長距離参照は番号だけ）。
    # full は常に添える。short は付けない。
    with_title = mode == "full" or (mode == "relative" and index[chain[0]].node.kind in _TITLED_KINDS)
    parts: list[str] = []
    for cid in chain:
        item = index[cid]
        if index.ctx.paragraph_ref_written and item.node.kind in ("paragraph", "item"):
            # 参照の書き下し方が印字と違う方式。実物は「第1項第4号」と書く。
            # 無番号の第1項をそのまま連ねると空文字になり、文がつながらない（実際に起きた）。
            unit = "項" if item.node.kind == "paragraph" else "号"
            parts.append(f"第{to_digits(item.index, index.ctx.digit_style)}{unit}")
        elif item.node.kind == "rider":
            # 特約は番号を持たないので、題名そのもので指す（「携行品損害補償特約第１条」）。
            parts.append(item.node.title or "")
        elif item.node.kind == "head_matter":
            # 頭書も番号を持たない。本文は「頭書に記載の…」と呼び名で指す。
            parts.append(item.node.kind_label or HEAD_MATTER_LABEL)
        elif with_title and item.node.kind in _TITLED_KINDS and item.node.title:
            parts.append(f"{item.label}（{item.node.title}）")
        else:
            parts.append(item.label)
    return "".join(p for p in parts if p)
