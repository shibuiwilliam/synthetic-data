"""lint ルールの実装（CLAUDE.md §8）。

P1 で実装するのは L00（スキーマ）・L01・L02・L03・L07・L08・L13。
L04 L05 L06 L09–L12 L14 L15 は後続フェーズ（blueprint・描画・QA が揃ってから）。
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from yakkan.lint.base import Finding, LintContext, rule
from yakkan.lint.walk import iter_ids, iter_texts
from yakkan.models import BoxBlock, Cell, Figure, FootnotesBlock, Table
from yakkan.richtext import (
    AutoLabel,
    Bold,
    Br,
    Const,
    Fn,
    Inline,
    Ref,
    RichTextError,
    Ruby,
    Underline,
    iter_tokens,
    parse,
    raw_text,
)

DENYLIST_PATH = Path(__file__).with_name("denylist.txt")

# --- L03：番号ラベルの直書き -------------------------------------------------
#: 「第１条」「第２章」など。全角・半角の数字の両方を拾う。
_LITERAL_NUMBER_LABEL = re.compile(r"第[0-9０-９]+[条章節項号編]")
#: 行頭の「（１）」
_LITERAL_PAREN_NUMBER = re.compile(r"^[（(][0-9０-９]+[）)]")
#: 行頭の丸数字
_LITERAL_CIRCLED = re.compile(r"^[①-⑳]")
#: 行頭の「ｱ.」
_LITERAL_KATAKANA = re.compile(r"^[ｱ-ﾝ][.．]")

# --- L08：架空性 --------------------------------------------------------------
_ALLOWED_DOMAINS = ("example.jp", "example.co.jp", "example.com")
_URL = re.compile(r"(?:https?://|www\.)([A-Za-z0-9.\-]+)")
_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@([A-Za-z0-9.\-]+)")
_PHONE = re.compile(r"[0０][0-9０-９]{1,3}[-－―‐][0-9０-９]{2,4}[-－―‐][0-9０-９]{3,4}")
_FULLWIDTH_DIGITS = str.maketrans("０１２３４５６７８９", "0123456789")


def _parsed(text: str) -> tuple[Inline, ...]:
    return parse(text)


@lru_cache(maxsize=1)
def _denylist() -> tuple[str, ...]:
    lines = DENYLIST_PATH.read_text(encoding="utf-8").splitlines()
    return tuple(s.strip() for s in lines if s.strip() and not s.lstrip().startswith("#"))


# --- L00 ---------------------------------------------------------------------


@rule("L00", "スキーマ検証（型・未知フィールド・執筆物への derived 混入）")
def l00_schema(ctx: LintContext) -> Iterator[Finding]:
    for message in ctx.schema_errors:
        hint = ""
        if message.startswith("derived"):
            hint = "（`derived` は build が付与する。執筆物には書かない）"
        yield Finding("L00", "error", f"スキーマ検証に失敗した: {message}{hint}", path=message.split(":")[0])


# --- L01 ---------------------------------------------------------------------


@rule("L01", "id 一意、{ref:}/anchor の参照先が存在する")
def l01_ids_and_refs(ctx: LintContext) -> Iterator[Finding]:
    seen: dict[str, str] = {}
    for owned in iter_ids(ctx.draft):
        if owned.id in seen:
            yield Finding(
                "L01",
                "error",
                f"id が重複している（先に {seen[owned.id]} で使用）",
                element_id=owned.id,
                path=owned.path,
            )
        else:
            seen[owned.id] = owned.path

    node_ids = {n for n in ctx.index.nodes}
    all_ids = set(seen) | node_ids
    # キャプションのある表・図は build が「表１」「図２」を振るので、{ref:} の参照先にできる
    # （docs/shared_fixes.md A3）。キャプションの無い列挙表には番号が無いので参照先にできない。
    caption_ids = {
        block.id
        for block, _owner, _article in _iter_blocks(ctx)
        if isinstance(block, Table | Figure) and (block.caption or "").strip()
    }
    ref_targets = node_ids | caption_ids

    for owned in iter_texts(ctx.draft):
        if not owned.parseable:
            continue
        try:
            tokens = _parsed(owned.text)
        except RichTextError:
            continue  # L03 が報告する
        for token in iter_tokens(tokens):
            if isinstance(token, Ref) and token.target not in ref_targets:
                detail = (
                    "（キャプションの無い表・図には番号が無いので参照できない。caption を付けるか、"
                    "その表を持つ条を参照する）"
                    if token.target in all_ids
                    else ""
                )
                yield Finding(
                    "L01",
                    "error",
                    f"{{ref:{token.target}}} の参照先が見つからない{detail}",
                    element_id=owned.owner_id,
                    path=owned.path,
                )

    for block, owner_id, _ in _iter_blocks(ctx):
        if isinstance(block, BoxBlock):
            if block.style == "margin_note" and not block.anchor:
                yield Finding(
                    "L01", "error", "margin_note には anchor（対象ノード id）が要る", element_id=block.id
                )
            if block.anchor and block.anchor not in all_ids:
                yield Finding(
                    "L01",
                    "error",
                    f"anchor の参照先が見つからない: {block.anchor}",
                    element_id=block.id,
                    path=owner_id,
                )
        if isinstance(block, Table):
            cell_ids = {c.id for row in block.grid for c in row if isinstance(c, Cell)}
            for row in block.grid:
                for cell in row:
                    if not isinstance(cell, Cell) and cell.merged_into not in cell_ids:
                        yield Finding(
                            "L01",
                            "error",
                            f"merged_into の参照先が同じ表に無い: {cell.merged_into}",
                            element_id=block.id,
                        )


def _iter_blocks(ctx: LintContext):
    from yakkan.lint.walk import iter_blocks

    return iter_blocks(ctx.draft)


# --- L02 ---------------------------------------------------------------------


@rule("L02", "{fn:n} と同一条の footnotes.n が双方向に対応し、未使用の脚注が無い")
def l02_footnotes(ctx: LintContext) -> Iterator[Finding]:
    declared: dict[str, dict[int, str]] = {}
    for block, owner_id, article_id in _iter_blocks(ctx):
        if isinstance(block, FootnotesBlock):
            owner = article_id or owner_id
            bucket = declared.setdefault(owner, {})
            for note in block.notes:
                if note.n in bucket:
                    yield Finding("L02", "error", f"脚注番号 {note.n} が重複している", element_id=block.id)
                bucket[note.n] = block.id

    used: dict[str, set[int]] = {}
    for owned in iter_texts(ctx.draft):
        if not owned.rich:
            continue
        try:
            tokens = _parsed(owned.text)
        except RichTextError:
            continue
        for token in iter_tokens(tokens):
            if isinstance(token, Fn):
                owner = owned.article_id
                if owner is None:
                    yield Finding(
                        "L02",
                        "error",
                        f"{{fn:{token.n}}} の所属先が無い（脚注は条または別表の末尾に置く）",
                        element_id=owned.owner_id,
                        path=owned.path,
                    )
                    continue
                used.setdefault(owner, set()).add(token.n)
                if token.n not in declared.get(owner, {}):
                    yield Finding(
                        "L02",
                        "error",
                        f"{{fn:{token.n}}} に対応する脚注が条 {owner} に無い",
                        element_id=owned.owner_id,
                        path=owned.path,
                    )

    for owner, notes in declared.items():
        for n, block_id in notes.items():
            if n not in used.get(owner, set()):
                yield Finding(
                    "L02", "error", f"脚注 {n} が本文から参照されていない", element_id=block_id, path=owner
                )


# --- L03 ---------------------------------------------------------------------


@rule("L03", "番号ラベルの直書きが無い／記法が正しい")
def l03_no_literal_labels(ctx: LintContext) -> Iterator[Finding]:
    for owned in iter_texts(ctx.draft):
        if owned.parseable:
            try:
                tokens = _parsed(owned.text)
            except RichTextError as exc:
                yield Finding(
                    "L03",
                    "error",
                    f"RichText の記法エラー: {exc}",
                    element_id=owned.owner_id,
                    path=owned.path,
                )
                continue
            plain_source = raw_text(tokens)
        else:
            plain_source = owned.text
            if "{" in plain_source and "{{" not in plain_source:
                yield Finding(
                    "L03",
                    "error",
                    "この項目は RichText ではないのでトークンを書けない",
                    element_id=owned.owner_id,
                    path=owned.path,
                )

        for match in _LITERAL_NUMBER_LABEL.finditer(plain_source):
            yield Finding(
                "L03",
                "error",
                f"番号ラベルの直書き {match.group()!r}（参照は {{ref:<id>}} で書く）",
                element_id=owned.owner_id,
                path=owned.path,
            )
        for line in plain_source.splitlines():
            stripped = line.strip()
            for pattern, what in (
                (_LITERAL_PAREN_NUMBER, "項番号"),
                (_LITERAL_CIRCLED, "号番号"),
                (_LITERAL_KATAKANA, "細目番号"),
            ):
                match = pattern.match(stripped)
                if match:
                    yield Finding(
                        "L03",
                        "error",
                        f"行頭に{what}の直書き {match.group()!r}（番号は build が付与する）",
                        element_id=owned.owner_id,
                        path=owned.path,
                    )

    for owned in iter_texts(ctx.draft):
        if not owned.parseable:
            continue
        try:
            tokens = _parsed(owned.text)
        except RichTextError:
            continue
        for token in iter_tokens(tokens):
            if isinstance(token, AutoLabel) and not _in_enumeration_cell(ctx, owned.owner_id):
                yield Finding(
                    "L03",
                    "error",
                    "{auto_label} は番号を振る表（semantic_type: enumeration / exclusions）のセルでのみ使う",
                    element_id=owned.owner_id,
                    path=owned.path,
                )

    for node_id, item in ctx.index.nodes.items():
        if item.node.number_override and not item.node.number_override_reason:
            yield Finding(
                "L03",
                "error",
                "number_override を使うときは number_override_reason に理由を書く",
                element_id=node_id,
            )


# --- L07 ---------------------------------------------------------------------


@rule("L07", "フォント被覆（cmap）", quick=False)
def l07_font_coverage(ctx: LintContext) -> Iterator[Finding]:
    from yakkan.fonts import FONTS

    body_fonts = [f for f in FONTS if "Symbols" not in f.family and f.exists]
    all_fonts = [f for f in FONTS if f.exists]
    if not all_fonts:
        yield Finding("L07", "error", "assets/fonts にフォントが無い（SOURCES.md の手順で取得する）")
        return

    chars: dict[str, tuple[str, str]] = {}
    for owned in iter_texts(ctx.draft):
        for char in owned.text:
            if char.isspace() or char in "{}|:":
                continue
            chars.setdefault(char, (owned.owner_id, owned.path))

    cmaps = {f.key: _cmap(f) for f in all_fonts}
    union = set().union(*cmaps.values())
    body_union = set().union(*(cmaps[f.key] for f in body_fonts)) if body_fonts else set()

    for char, (owner, path) in sorted(chars.items()):
        code = ord(char)
        if code not in union:
            yield Finding(
                "L07",
                "error",
                f"どの同梱フォントにも無い文字 {char!r}（U+{code:04X}）",
                element_id=owner,
                path=path,
            )
        elif code not in body_union:
            yield Finding(
                "L07",
                "warn",
                f"本文フォントに無く記号フォントへフォールバックする文字 {char!r}（U+{code:04X}）",
                element_id=owner,
                path=path,
            )


@lru_cache(maxsize=16)
def _cmap(spec) -> frozenset[int]:
    from fontTools.ttLib import TTFont

    with TTFont(spec.path, fontNumber=0, lazy=True) as tt:
        return frozenset(tt.getBestCmap())


# --- L08 ---------------------------------------------------------------------


@rule("L08", "denylist 語句・許可外ドメイン・ゼロ埋めでない電話番号が無い")
def l08_fiction(ctx: LintContext) -> Iterator[Finding]:
    deny = _denylist()
    for owned in iter_texts(ctx.draft):
        text = owned.text
        for word in deny:
            if word in text:
                yield Finding(
                    "L08",
                    "error",
                    f"実在の名称が含まれている: {word!r}（架空の名称に置き換える）",
                    element_id=owned.owner_id,
                    path=owned.path,
                )
        for match in _URL.finditer(text):
            host = match.group(1).rstrip(".")
            if not any(host == d or host.endswith("." + d) for d in _ALLOWED_DOMAINS):
                yield Finding(
                    "L08",
                    "error",
                    f"許可外のドメイン: {host}（{' / '.join(_ALLOWED_DOMAINS)} のみ）",
                    element_id=owned.owner_id,
                    path=owned.path,
                )
        for match in _EMAIL.finditer(text):
            host = match.group(1).rstrip(".")
            if not any(host == d or host.endswith("." + d) for d in _ALLOWED_DOMAINS):
                yield Finding(
                    "L08",
                    "error",
                    f"許可外のメールドメイン: {host}",
                    element_id=owned.owner_id,
                    path=owned.path,
                )
        for match in _PHONE.finditer(text):
            number = match.group().translate(_FULLWIDTH_DIGITS)
            groups = re.split(r"[-－―‐]", number)
            if any(set(g) != {"0"} for g in groups[1:]):
                yield Finding(
                    "L08",
                    "error",
                    f"電話番号はゼロ埋めのみ: {match.group()!r}（例 0120-000-000）",
                    element_id=owned.owner_id,
                    path=owned.path,
                )


# --- L13 ---------------------------------------------------------------------

_REQUIRED_META = ("title", "product_name", "edition_date", "form_code", "disclaimer")
_EDITION_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


@rule("L13", "奥付の disclaimer と meta 必須項目")
def l13_meta(ctx: LintContext) -> Iterator[Finding]:
    meta = ctx.draft.meta
    for name in _REQUIRED_META:
        if not str(getattr(meta, name) or "").strip():
            yield Finding("L13", "error", f"meta.{name} が空", path=f"meta.{name}")
    if not meta.issuer.name.strip() or not meta.issuer.short_name.strip():
        yield Finding("L13", "error", "meta.issuer の名称が空", path="meta.issuer")
    if not _EDITION_DATE.match(meta.edition_date):
        yield Finding(
            "L13",
            "error",
            f"meta.edition_date は YYYY-MM-DD 形式: {meta.edition_date!r}",
            path="meta.edition_date",
        )

    colophon_text = "".join(
        owned.text for owned in iter_texts(ctx.draft) if (owned.path or "").startswith("back_matter.colophon")
    )
    if meta.disclaimer and meta.disclaimer not in colophon_text:
        yield Finding(
            "L13",
            "error",
            "meta.disclaimer の文が奥付（back_matter.colophon）に入っていない",
            path="back_matter.colophon",
        )

    used_consts: set[str] = set()
    for owned in iter_texts(ctx.draft):
        if not owned.parseable:
            continue
        try:
            tokens = _parsed(owned.text)
        except RichTextError:
            continue
        for token in iter_tokens(tokens):
            if isinstance(token, Const):
                used_consts.add(token.key)
                if token.key not in meta.constants:
                    yield Finding(
                        "L13",
                        "error",
                        f"{{const:{token.key}}} が meta.constants に無い",
                        element_id=owned.owner_id,
                        path=owned.path,
                    )


def _in_enumeration_cell(ctx: LintContext, owner_id: str) -> bool:
    from yakkan.ids import parse_cell_id

    parsed = parse_cell_id(owner_id)
    if parsed is None:
        return False
    table_id = parsed[0]
    from yakkan.build import AUTO_LABEL_TYPES

    for block, _, _ in _iter_blocks(ctx):
        if isinstance(block, Table) and block.id == table_id:
            return block.semantic_type in AUTO_LABEL_TYPES
    return False


# --- L06：図 ------------------------------------------------------------------

#: 最小複雑度（docs/schema.md §5.5）
MIN_FLOWCHART_NODES = 5
MIN_FLOWCHART_BRANCHES = 1
MIN_TREE_DEPTH = 3
MIN_STEPS = 4
MIN_TIMELINE_ITEMS = 4
MIN_MATRIX_ROWS = 4
MIN_MATRIX_COLS = 3


@rule("L06", "図：エッジ端点の存在・格子座標の重複なし・最小複雑度・alt と facts の非空")
def l06_figures(ctx: LintContext) -> Iterator[Finding]:
    from yakkan.models import Figure

    for block, _owner, _article in _iter_blocks(ctx):
        if not isinstance(block, Figure):
            continue
        yield from _check_figure_meta(block)
        yield from _check_diagram(block)
        yield from _check_diagram_tokens(block)


#: 図・算式で使ってよいトークン。値を差し込むものだけ（docs/shared_fixes.md A2）。
_FLAT_TOKEN_NAMES = {"ref", "term", "const"}
#: SVG・算式の箱は行内マークアップを持てないので、これらは解決しても形にならない
_MARKUP_TOKENS = (Fn, Bold, Underline, Ruby, Br, AutoLabel)


def _check_diagram_tokens(figure) -> Iterator[Finding]:
    """`diagram` の中のトークンを検査する。

    `{const:}` `{term:}` `{ref:}` は build が `derived.figures[].resolved_labels` に
    解決して、描画側が SVG を組む前に当てる。だから図の中で使ってよい。
    太字・ルビ・改行・脚注は SVG に形が無いので弾く。
    """
    for raw in _figure_strings(figure):
        if "{" not in raw:
            continue
        try:
            nodes = parse(raw)
        except RichTextError as exc:
            yield Finding("L06", "error", f"図の中の RichText が壊れている: {exc}", element_id=figure.id)
            continue
        bad = sorted({type(t).__name__ for t in iter_tokens(nodes) if isinstance(t, _MARKUP_TOKENS)})
        if bad:
            yield Finding(
                "L06",
                "error",
                f"図の中では使えないトークンがある: {' '.join(bad)}"
                "（SVG は行内マークアップを持てない。使えるのは {ref:} {term:} {const:} だけ）",
                element_id=figure.id,
            )


def _figure_strings(figure) -> Iterator[str]:
    from yakkan.build import iter_model_strings

    return iter_model_strings(figure)


def _check_figure_meta(figure) -> Iterator[Finding]:
    if not figure.alt.strip():
        yield Finding("L06", "error", "alt（図の散文説明）が空", element_id=figure.id)
    if not figure.facts:
        yield Finding("L06", "error", "facts（図から読めるべき命題）が空", element_id=figure.id)
    for i, fact in enumerate(figure.facts):
        if not fact.strip():
            yield Finding("L06", "error", f"facts[{i}] が空", element_id=figure.id)


def _check_diagram(figure) -> Iterator[Finding]:  # noqa: C901 - 種別ごとの分岐が本質
    diagram = figure.diagram
    match diagram.kind:
        case "flowchart":
            node_ids = {n.id for n in diagram.nodes}
            if len(diagram.nodes) < MIN_FLOWCHART_NODES:
                yield Finding(
                    "L06",
                    "error",
                    f"flowchart のノードが {len(diagram.nodes)} 個（{MIN_FLOWCHART_NODES} 個以上）",
                    element_id=figure.id,
                )
            outgoing: dict[str, int] = {}
            for edge in diagram.edges:
                for end, name in ((edge.from_, "from"), (edge.to, "to")):
                    if end not in node_ids:
                        yield Finding(
                            "L06",
                            "error",
                            f"エッジの {name} が存在しないノードを指している: {end}",
                            element_id=figure.id,
                        )
                outgoing[edge.from_] = outgoing.get(edge.from_, 0) + 1
            branches = sum(1 for count in outgoing.values() if count >= 2)
            if branches < MIN_FLOWCHART_BRANCHES:
                yield Finding(
                    "L06",
                    "error",
                    f"flowchart に分岐が無い（{MIN_FLOWCHART_BRANCHES} 箇所以上）",
                    element_id=figure.id,
                )
            seen: dict[tuple[int, int], str] = {}
            for node in diagram.nodes:
                key = (node.col, node.row)
                if key in seen:
                    yield Finding(
                        "L06",
                        "error",
                        f"格子座標が重複している (col={node.col}, row={node.row}): {seen[key]} と {node.id}",
                        element_id=figure.id,
                    )
                seen[key] = node.id
        case "tree":
            depth = _tree_depth(diagram.root)
            if depth < MIN_TREE_DEPTH:
                yield Finding(
                    "L06",
                    "error",
                    f"tree の階層が {depth}（{MIN_TREE_DEPTH} 階層以上）",
                    element_id=figure.id,
                )
            ids: list[str] = []
            _tree_ids(diagram.root, ids)
            duplicates = {i for i in ids if ids.count(i) > 1}
            if duplicates:
                yield Finding(
                    "L06",
                    "error",
                    f"tree のノード id が重複している: {sorted(duplicates)}",
                    element_id=figure.id,
                )
        case "steps":
            if len(diagram.steps) < MIN_STEPS:
                yield Finding(
                    "L06",
                    "error",
                    f"steps が {len(diagram.steps)} 個（{MIN_STEPS} 個以上）",
                    element_id=figure.id,
                )
        case "timeline":
            items = len(diagram.spans) + len(diagram.events)
            if items < MIN_TIMELINE_ITEMS:
                yield Finding(
                    "L06",
                    "error",
                    f"timeline の要素が {items} 個（{MIN_TIMELINE_ITEMS} 個以上）",
                    element_id=figure.id,
                )
            ticks = {str(t) for t in diagram.axis.ticks}
            for span in diagram.spans:
                for value, name in ((span.from_, "from"), (span.to, "to")):
                    if isinstance(value, str) and ticks and str(value) not in ticks:
                        yield Finding(
                            "L06",
                            "warn",
                            f"span の {name} が目盛に無い: {value}（軸の左端に寄せて描かれる）",
                            element_id=figure.id,
                        )
            for event in diagram.events:
                if isinstance(event.at, str) and ticks and str(event.at) not in ticks:
                    yield Finding(
                        "L06", "warn", f"event の at が目盛に無い: {event.at}", element_id=figure.id
                    )
        case "annotated_mock":
            badges = [f.badge for f in diagram.fields]
            duplicates = {b for b in badges if badges.count(b) > 1}
            if duplicates:
                yield Finding(
                    "L06", "error", f"バッジ番号が重複している: {sorted(duplicates)}", element_id=figure.id
                )
            legend_badges = {item.badge for item in diagram.legend}
            for badge in sorted(set(badges) - legend_badges):
                yield Finding("L06", "error", f"バッジ {badge} に対応する凡例が無い", element_id=figure.id)
            for field_ in diagram.fields:
                if not (0.0 <= field_.x <= 1.0 and 0.0 <= field_.y <= 1.0):
                    yield Finding(
                        "L06",
                        "error",
                        f"フィールドの座標は 0..1 の相対値で書く: {field_.id} (x={field_.x}, y={field_.y})",
                        element_id=figure.id,
                    )
        case "matrix":
            if len(diagram.rows) < MIN_MATRIX_ROWS or len(diagram.cols) < MIN_MATRIX_COLS:
                yield Finding(
                    "L06",
                    "error",
                    f"matrix が {len(diagram.rows)}×{len(diagram.cols)}"
                    f"（{MIN_MATRIX_ROWS}×{MIN_MATRIX_COLS} 以上）",
                    element_id=figure.id,
                )
            for r, row in enumerate(diagram.marks):
                if len(row) != len(diagram.cols):
                    yield Finding(
                        "L06",
                        "error",
                        f"marks[{r}] の列数が cols と合わない: {len(row)} != {len(diagram.cols)}",
                        element_id=figure.id,
                    )
            if len(diagram.marks) != len(diagram.rows):
                yield Finding(
                    "L06",
                    "error",
                    f"marks の行数が rows と合わない: {len(diagram.marks)} != {len(diagram.rows)}",
                    element_id=figure.id,
                )
            marks_used = {m for row in diagram.marks for m in row}
            legend_marks = {item.mark for item in diagram.legend}
            if diagram.legend:
                for mark in sorted(marks_used - legend_marks):
                    yield Finding("L06", "warn", f"記号 {mark!r} が凡例に無い", element_id=figure.id)


def _tree_depth(node, depth: int = 1) -> int:
    return max([depth] + [_tree_depth(c, depth + 1) for c in node.children])


def _tree_ids(node, out: list[str]) -> None:
    out.append(node.id)
    for child in node.children:
        _tree_ids(child, out)
