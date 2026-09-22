"""番号付けとラベル導出（docs/rendering.md §6.4）。

執筆者は番号を書かない。ツリー上の位置と番号方式から `label` / `heading_text` / `path` を
**純関数で** 導出する（CLAUDE.md §2-2）。ここが唯一の番号の出どころ。

方式（scheme）ごとの割り当て

| scheme | chapter | section | article | paragraph | item | subitem | subsubitem | footnote | appendix |
|---|---|---|---|---|---|---|---|---|---|
| nonlife | 第１章 | 第１節 | 第１条 | （１）※単項なら無番号 | ①② | ｱ. | (ｱ) | （*1） | 別表１ |
| life | 第１章 | 第１節 | 第１条 | １． | (1) | ① | ｱ | （注1） | 別表１ |
| teikan | 第１章 | （節なし） | 第１条 | ２（第１項は無番号） | (1) | ① | （なし） | （*1） | 附則 |

別紙（appendix）の内部は独立体系（「第１」「１．」「①」「ｱ.」）。
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Literal

from yakkan.models import DigitStyle, LabelInfo, Node, NodeKind, NumberingScheme

#: 全角数字への変換表
_FULLWIDTH = str.maketrans("0123456789", "０１２３４５６７８９")
#: 丸数字 ①〜⑳
CIRCLED = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
CIRCLED_MAX = len(CIRCLED)
#: 半角カタカナ（ｱ.ｲ.… 用）。実物の約款と同じ並び。
KATAKANA = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎ"
#: ローマ数字（小文字）
ROMAN = "ⅰⅱⅲⅳⅴⅵⅶⅷⅸⅹ"

#: 見出しラベルと文言の区切り（条は括弧、それ以外は全角空白）
HEADING_SPACE = "　"


def to_digits(n: int, style: DigitStyle) -> str:
    """整数を digit_style に従って文字列にする。"""
    s = str(n)
    return s.translate(_FULLWIDTH) if style == "fullwidth" else s


@dataclass(frozen=True)
class NumberWarning:
    """番号付けで妥協した箇所（lint が warning として拾う）。"""

    node_id: str
    message: str


def circled(n: int, style: DigitStyle, warnings: list[NumberWarning] | None = None, node_id: str = "") -> str:
    """丸数字。⑳ を超えたら `(21)` にフォールバックし警告する（docs/rendering.md §6.4）。"""
    if 1 <= n <= CIRCLED_MAX:
        return CIRCLED[n - 1]
    if warnings is not None:
        warnings.append(
            NumberWarning(
                node_id, f"丸数字は{CIRCLED_MAX}までしか無いため {n} は括弧数字にフォールバックした"
            )
        )
    open_paren, close_paren = ("（", "）") if style == "fullwidth" else ("(", ")")
    return f"{open_paren}{to_digits(n, style)}{close_paren}"


def _katakana(n: int, style: DigitStyle) -> str:
    if 1 <= n <= len(KATAKANA):
        return KATAKANA[n - 1]
    return to_digits(n, style)


def _roman(n: int, style: DigitStyle) -> str:
    if 1 <= n <= len(ROMAN):
        return ROMAN[n - 1]
    return to_digits(n, style)


#: 条を「章をまたいで通し番号」にする方式。
#: 実物の定款は第1条から最終条まで通しで振る（章ごとに 1 に戻さない）。
#: 損保・生保の約款は章（または条項）ごとに 1 から振り直すのが普通。
CONTINUOUS_ARTICLE_SCHEMES: frozenset[str] = frozenset({"teikan"})


@dataclass
class NumberingContext:
    """1 文書ぶんの番号付け設定。"""

    scheme: NumberingScheme
    digit_style: DigitStyle = "fullwidth"
    warnings: list[NumberWarning] = field(default_factory=list)
    #: 条見出しの体裁。`above` は見出し文言だけを条の上に置き、条ラベルを第1項に走り込ませる
    #: （docs/reference_structures.md #12）。
    article_heading: Literal["inline", "above"] = "inline"
    #: 条末脚注の体裁。`remarks_box` は黒丸数字のマーカーと「備考」の枠（#13）。
    footnote_style: Literal["inline", "remarks_box"] = "inline"

    @property
    def continuous_articles(self) -> bool:
        return self.scheme in CONTINUOUS_ARTICLE_SCHEMES

    def paren(self, body: str) -> str:
        return f"（{body}）" if self.digit_style == "fullwidth" else f"({body})"


def _label_nonlife(ctx: NumberingContext, kind: NodeKind, n: int, node_id: str, siblings: int) -> str:
    d = ctx.digit_style
    match kind:
        case "part":
            return f"第{to_digits(n, d)}編"
        case "chapter":
            return f"第{to_digits(n, d)}章"
        case "section":
            return f"第{to_digits(n, d)}節"
        case "article":
            return f"第{to_digits(n, d)}条"
        case "paragraph":
            return "" if siblings <= 1 else ctx.paren(to_digits(n, d))
        case "item":
            return circled(n, d, ctx.warnings, node_id)
        case "subitem":
            return f"{_katakana(n, d)}."
        case "subsubitem":
            return ctx.paren(_katakana(n, d))
    return ""


def _label_life(ctx: NumberingContext, kind: NodeKind, n: int, node_id: str, siblings: int) -> str:
    d = ctx.digit_style
    match kind:
        case "part":
            return f"第{to_digits(n, d)}編"
        case "chapter":
            return f"第{to_digits(n, d)}章"
        case "section":
            return f"第{to_digits(n, d)}節"
        case "article":
            return f"第{to_digits(n, d)}条"
        case "paragraph":
            return "" if siblings <= 1 else f"{to_digits(n, d)}．"
        case "item":
            return ctx.paren(to_digits(n, d))
        case "subitem":
            return circled(n, d, ctx.warnings, node_id)
        case "subsubitem":
            return _katakana(n, d)
    return ""


def _label_group(ctx: NumberingContext, kind: NodeKind, n: int, node_id: str, siblings: int) -> str:
    """団体保険（docs/reference_structures.md #12）。項＝丸数字・号＝「１．」・細目＝(ｱ)。"""
    d = ctx.digit_style
    match kind:
        case "part":
            return f"第{to_digits(n, d)}編"
        case "chapter":
            return f"第{to_digits(n, d)}章"
        case "section":
            return f"第{to_digits(n, d)}節"
        case "article":
            return f"第{to_digits(n, d)}条"
        case "paragraph":
            # 第1項は無番号。第2項以降を丸数字で示す（実物の体裁）。
            return "" if n <= 1 else circled(n, d, ctx.warnings, node_id)
        case "item":
            return f"{to_digits(n, d)}．"
        case "subitem":
            return ctx.paren(_katakana(n, d))
        case "subsubitem":
            ctx.warnings.append(NumberWarning(node_id, "団体保険に細々目の番号方式は無い"))
            return ""
    return ""


def _label_jyusetsu(ctx: NumberingContext, kind: NodeKind, n: int, node_id: str, siblings: int) -> str:
    """重要事項説明書（#9・#10）。**条を持たない。**

    大見出し（章）は番号を持たず、節が `（1）`、条の位置に丸数字の小見出しが来る。
    """
    d = ctx.digit_style
    match kind:
        case "part":
            return to_digits(n, d)
        case "chapter":
            return to_digits(n, d)
        case "section":
            return ctx.paren(to_digits(n, d))
        case "article":
            return circled(n, d, ctx.warnings, node_id)
        case "paragraph":
            return ""
        case "item":
            return circled(n, d, ctx.warnings, node_id)
        case "subitem":
            return f"{_katakana(n, d)}."
        case "subsubitem":
            return ctx.paren(_katakana(n, d))
    return ""


def _label_teikan(ctx: NumberingContext, kind: NodeKind, n: int, node_id: str, siblings: int) -> str:
    d = ctx.digit_style
    match kind:
        case "part":
            return f"第{to_digits(n, d)}編"
        case "chapter":
            return f"第{to_digits(n, d)}章"
        case "section":
            # 定款に節は置かない（docs/rendering.md §6.4）。使われたら番号を振らず lint で拾う。
            ctx.warnings.append(NumberWarning(node_id, "teikan では節を使わない"))
            return ""
        case "article":
            return f"第{to_digits(n, d)}条"
        case "paragraph":
            # 第１項は無番号。第２項以降のみ行頭に数字を置く。
            return "" if n <= 1 else to_digits(n, d)
        case "item":
            return ctx.paren(to_digits(n, d))
        case "subitem":
            return circled(n, d, ctx.warnings, node_id)
        case "subsubitem":
            ctx.warnings.append(NumberWarning(node_id, "teikan に細々目の番号方式は無い"))
            return ""
    return ""


#: 別紙内の独立体系（docs/rendering.md §6.4 の「第１」「１．」「①」「ｱ.」）
def _label_appendix_inner(ctx: NumberingContext, kind: NodeKind, n: int, node_id: str, siblings: int) -> str:
    d = ctx.digit_style
    # 定款の附則は項番号「１」「２」で起こし、号は（１）とするのが慣行。
    # 損保・生保の別表は「１．」「①」で、本文の号と同じ記号を使う。
    teikan = ctx.scheme == "teikan"
    match kind:
        case "appendix_section":
            return f"第{to_digits(n, d)}"
        case "paragraph":
            return to_digits(n, d) if teikan else f"{to_digits(n, d)}．"
        case "item":
            return ctx.paren(to_digits(n, d)) if teikan else circled(n, d, ctx.warnings, node_id)
        case "subitem":
            return f"{_katakana(n, d)}."
        case "subsubitem":
            return ctx.paren(_roman(n, d))
    return ""


APPENDIX_KIND_LABELS: dict[NumberingScheme, str] = {
    "nonlife": "別表",
    "life": "別表",
    "teikan": "附則",
    "group": "別表",
    "jyusetsu": "別表",
}


def appendix_label(ctx: NumberingContext, index: int, kind_label: str | None = None) -> str:
    """別表１ / 付表１ / 附則 のラベル。`kind_label` で「付表」「別紙」に切り替える。"""
    base = kind_label or APPENDIX_KIND_LABELS[ctx.scheme]
    if base == "附則":
        return base if index <= 1 else f"{base}{to_digits(index, ctx.digit_style)}"
    return f"{base}{to_digits(index, ctx.digit_style)}"


#: 黒丸数字（❶〜❿）。団体保険の「備考」欄のマーカー（docs/reference_structures.md #13）。
BLACK_CIRCLED = "❶❷❸❹❺❻❼❽❾❿"


def footnote_marker(ctx: NumberingContext, n: int) -> str:
    """条末脚注のマーカー。nonlife/teikan は（*1）、life は（注1）、備考欄は❶。"""
    if ctx.footnote_style == "remarks_box":
        if 1 <= n <= len(BLACK_CIRCLED):
            return BLACK_CIRCLED[n - 1]
        ctx.warnings.append(NumberWarning("", f"備考のマーカーは {len(BLACK_CIRCLED)} 件まで（{n} 件目）"))
        return f"({n})"
    body = to_digits(n, ctx.digit_style)
    return f"（注{body}）" if ctx.scheme == "life" else f"（*{body}）"


def _counter_key(ctx: NumberingContext, node: Node) -> str:
    """番号を数える単位。別表だけは呼び名（別表／付表／別紙）で分ける。"""
    if node.kind == "appendix":
        return f"appendix:{node.kind_label or APPENDIX_KIND_LABELS[ctx.scheme]}"
    return node.kind


def label_for(
    ctx: NumberingContext,
    kind: NodeKind,
    index: int,
    node_id: str = "",
    siblings: int = 2,
    in_appendix: bool = False,
    kind_label: str | None = None,
) -> str:
    """1 ノードぶんのラベル。`siblings` は同じ親を持つ同種ノードの数（単項無番号の判定に使う）。

    `kind_label` は別表の呼び名（「付表」など）。ノードが持っていればそれを使う。
    """
    if in_appendix:
        label = _label_appendix_inner(ctx, kind, index, node_id, siblings)
        if label:
            return label
    if kind == "appendix":
        return appendix_label(ctx, index, kind_label)
    match ctx.scheme:
        case "nonlife":
            return _label_nonlife(ctx, kind, index, node_id, siblings)
        case "life":
            return _label_life(ctx, kind, index, node_id, siblings)
        case "teikan":
            return _label_teikan(ctx, kind, index, node_id, siblings)
        case "group":
            return _label_group(ctx, kind, index, node_id, siblings)
        case "jyusetsu":
            return _label_jyusetsu(ctx, kind, index, node_id, siblings)


def heading_text(
    kind: NodeKind, label: str, title: str | None, article_heading: str = "inline"
) -> str:
    """見出し文字列。条は「第１条（告知義務）」、それ以外は「第１章　補償の概要」。

    `article_heading == "above"` のとき、条の見出し行には**見出し文言だけ**が出る
    （「（告知義務）」）。条ラベルは第1項の本文の先頭に走り込む。
    """
    title = title or ""
    if kind == "article" and article_heading == "above":
        return f"（{title}）" if title else label
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

    def __init__(self, ctx: NumberingContext, body: list[Node], appendices: list[Node] | None = None) -> None:
        self.ctx = ctx
        self.nodes: dict[str, IndexedNode] = {}
        self.order: list[str] = []
        #: 章をまたぐ通し番号（teikan の条）。別紙は別体系なので数えない
        self._continuous: dict[str, int] = {}
        self._index_children(body, parent_id=None, ancestors=(), depth=0, in_appendix=False)
        self._index_children(appendices or [], parent_id=None, ancestors=(), depth=0, in_appendix=True)

    def _index_children(
        self,
        children: list[Node],
        parent_id: str | None,
        ancestors: tuple[str, ...],
        depth: int,
        in_appendix: bool,
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
            if child.kind == "article" and self.ctx.continuous_articles and not in_appendix:
                # 章をまたいで通しで振る（実物の定款の体裁）
                self._continuous["article"] = self._continuous.get("article", 0) + 1
                index = self._continuous["article"]
            inner = in_appendix and child.kind != "appendix"
            label = child.number_override or label_for(
                self.ctx,
                child.kind,
                index,
                node_id=child.id,
                siblings=totals[key],
                in_appendix=inner,
                kind_label=child.kind_label,
            )
            self.nodes[child.id] = IndexedNode(
                node=child,
                parent_id=parent_id,
                ancestors=ancestors,
                index=index,
                siblings=totals[key],
                depth=depth,
                in_appendix=in_appendix,
                label=label,
                heading_text=heading_text(child.kind, label, child.title, self.ctx.article_heading),
            )
            self.order.append(child.id)
            self._index_children(
                child.children,
                parent_id=child.id,
                ancestors=ancestors + (child.id,),
                depth=depth + 1,
                in_appendix=in_appendix,
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

    def labels(self) -> dict[str, LabelInfo]:
        """`derived.labels` を組み立てる。"""
        out: dict[str, LabelInfo] = {}
        for node_id, item in self.nodes.items():
            out[node_id] = LabelInfo(
                label=item.label,
                title=item.node.title or "",
                heading_text=item.heading_text,
                path=[self.nodes[a].heading_text for a in item.ancestors],
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
        if item.node.kind == "rider":
            # 特約は番号を持たないので、題名そのもので指す（「携行品損害補償特約第１条」）。
            parts.append(item.node.title or "")
        elif with_title and item.node.kind in _TITLED_KINDS and item.node.title:
            parts.append(f"{item.label}（{item.node.title}）")
        else:
            parts.append(item.label)
    return "".join(p for p in parts if p)
