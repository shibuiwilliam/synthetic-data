"""L04（blueprint の必須要素）・L05（表）・L06 は rules.py・L09（ページ数）の実装。"""

from __future__ import annotations

from collections.abc import Iterator

from yakkan.blueprints import Blueprint, Requirement, load_blueprint
from yakkan.lint.base import Finding, LintContext, rule
from yakkan.lint.walk import iter_blocks, iter_nodes
from yakkan.models import BoxBlock, Cell, Figure, FootnotesBlock, Formula, ListBlock, MergedCell, Table


def _blueprint(ctx: LintContext) -> Blueprint | None:
    try:
        return load_blueprint(ctx.draft.genre)
    except (FileNotFoundError, ValueError):
        return None


def _matches(block, req: Requirement) -> bool:
    match req.kind:
        case "table":
            return isinstance(block, Table) and (req.subtype is None or block.semantic_type == req.subtype)
        case "figure":
            return isinstance(block, Figure) and (req.subtype is None or block.diagram.kind == req.subtype)
        case "formula":
            return isinstance(block, Formula) and (req.subtype is None or block.layout == req.subtype)
        case "box":
            return isinstance(block, BoxBlock) and (req.subtype is None or block.style == req.subtype)
        case "footnotes":
            return isinstance(block, FootnotesBlock)
        case "list":
            return isinstance(block, ListBlock)
    return False


def _size_ok(block, req: Requirement) -> bool:
    if isinstance(block, Table):
        if req.min_rows and len(block.grid) < req.min_rows:
            return False
        if req.min_cols and (not block.grid or len(block.grid[0]) < req.min_cols):
            return False
    return True


def _descendants_of(draft) -> dict[str, set[str]]:
    """ノード id → そのノード自身と配下のノード id の集合。

    `Requirement.under`（「このノードの配下に要る」）の判定に使う。
    box の中のブロックは owner が box の id になるので、それも配下に含める。
    """
    from yakkan.models import BoxBlock

    out: dict[str, set[str]] = {}

    def box_ids(blocks: list) -> set[str]:
        ids: set[str] = set()
        for block in blocks:
            if isinstance(block, BoxBlock):
                ids.add(block.id)
                ids |= box_ids(block.blocks)
        return ids

    def collect(node) -> set[str]:
        ids = {node.id} | box_ids(node.blocks)
        for child in node.children or []:
            ids |= collect(child)
        out[node.id] = ids
        return ids

    for node in draft.body + draft.appendices:
        collect(node)
    return out


@rule("L04", "blueprint の必須要素と最小件数を満たす")
def l04_required_elements(ctx: LintContext) -> Iterator[Finding]:
    blueprint = _blueprint(ctx)
    if blueprint is None:
        yield Finding("L04", "warn", f"blueprint が読めない: blueprints/{ctx.draft.genre}.yaml")
        return

    owned = [(b, owner) for b, owner, _article in iter_blocks(ctx.draft)]
    blocks = [b for b, _owner in owned]
    descendants = _descendants_of(ctx.draft)
    # 見出しのバッジはブロックではなくノードが持つので、別に数える
    badge_nodes = [(node, node.badges) for node, _a in iter_nodes(ctx.draft.body) if node.badges]
    for req in blueprint.all_requirements():
        if req.kind == "badge":
            hits = [
                b for _node, badges in badge_nodes for b in badges if req.subtype is None or b == req.subtype
            ]
            if len(hits) < req.min_count:
                label = "badge" + (f"/{req.subtype}" if req.subtype else "")
                detail = f"（{req.note}）" if req.note else ""
                yield Finding(
                    "L04",
                    "error",
                    f"必須要素が足りない: {label} が {len(hits)}/{req.min_count} 件{detail}",
                )
            continue
        # `under` は「そのノードの配下に要る」という指定。
        # 実装が無く、文書のどこかに 1 つあれば通ってしまっていた。
        scope = blocks
        if req.under:
            allowed = descendants.get(req.under)
            if allowed is None:
                continue  # そのノード自体が無い場合は、下の別表チェックが warn で報告する
            scope = [b for b, owner in owned if owner in allowed]
        hits = [b for b in scope if _matches(b, req)]
        sized = [b for b in hits if _size_ok(b, req)]
        label = req.kind + (f"/{req.subtype}" if req.subtype else "")
        if len(sized) < req.min_count:
            detail = f"（{req.note}）" if req.note else ""
            size = ""
            if req.min_rows:
                size += f" {req.min_rows}行以上"
            if req.min_cols:
                size += f" {req.min_cols}列以上"
            yield Finding(
                "L04",
                "error",
                f"必須要素が足りない: {label}{size} が {len(sized)}/{req.min_count} 件{detail}",
            )

    # 別表：blueprint が挙げたものが content に無い／題材が違う場合は warn。
    # どちらも執筆の判断で変えてよい（別表を削るのも、題材を差し替えるのも実際に起きた）。
    node_ids = set(descendants)
    for spec in blueprint.appendices:
        if spec.optional:
            continue
        if spec.id not in node_ids:
            yield Finding(
                "L04",
                "warn",
                f"blueprint が挙げる{spec.kind_label}が無い: {spec.id}"
                f"（{'／'.join(spec.title_options[:2])}）。意図して削ったなら blueprint も直す",
            )
            continue

    # 用語の定義（defined_terms）の件数
    term_req = next((r for r in blueprint.all_requirements() if r.subtype == "definitions"), None)
    if term_req and term_req.min_rows and len(ctx.draft.defined_terms) < term_req.min_rows:
        yield Finding(
            "L04",
            "error",
            f"defined_terms が {len(ctx.draft.defined_terms)} 語（{term_req.min_rows} 語以上）",
            path="defined_terms",
        )

    # 脚注・欄外注の最小件数
    footnote_count = sum(1 for b in blocks if isinstance(b, FootnotesBlock))
    if footnote_count < blueprint.budget.footnotes_min:
        yield Finding(
            "L04",
            "error",
            f"条末脚注が {footnote_count}/{blueprint.budget.footnotes_min} 箇所",
        )
    margin_notes = sum(1 for b in blocks if isinstance(b, BoxBlock) and b.style == "margin_note")
    if margin_notes < blueprint.budget.margin_notes_min:
        yield Finding(
            "L04",
            "error",
            f"欄外解説ボックスが {margin_notes}/{blueprint.budget.margin_notes_min} 箇所",
        )


#: 段またぎ（`span_columns: true`）にしてよい表の行数の上限。
#: これを超えると 1 ページに収まらず、**WeasyPrint が以降の内容を黙って捨てる**
#: （docs/gotchas.md「段組の中に 1 ページを超える段またぎ要素」）。
SPAN_TABLE_MAX_ROWS = 14


# 参照表（table_lookup / table_reason QA の正解源）は records を持つべき型。
# 列挙表（enumeration / exclusions）は「文と一体の箇条書き」なので対象外。
RECORDS_REQUIRED_TYPES: frozenset[str] = frozenset(
    {
        "definitions",
        "benefit_schedule",
        "grade_schedule",
        "surgery_schedule",
        "rate",
        "plan_matrix",
        "procedure",
        "rider_index",
        "purpose_index",
        "history",
    }
)


@rule("L05", "表：列数の一致・header_rows/cols が範囲内・records の値が grid に出現")
def l05_tables(ctx: LintContext) -> Iterator[Finding]:
    for block, owner, _article in iter_blocks(ctx.draft):
        if not isinstance(block, Table):
            continue
        if not block.grid:
            yield Finding("L05", "error", "grid が空", element_id=block.id)
            continue

        # 幅は **格子の位置数**で数える。結合されたセルの位置には `MergedCell` を明示的に置く
        # 規約なので（rowspan も colspan も同じ）、`colspan` を足すと二重に数えてしまい、
        # 2 段ヘッダ（§3.1 の C10）が必ず error になっていた。
        widths = {len(row) for row in block.grid}
        if len(widths) > 1:
            yield Finding(
                "L05",
                "error",
                f"行ごとに格子の位置数が違う: {sorted(widths)}"
                "（結合された位置には merged_into を持つプレースホルダを置く）",
                element_id=block.id,
            )
        # colspan / rowspan がプレースホルダの数と合っているか
        for r, row in enumerate(block.grid):
            for c, cell in enumerate(row):
                if not isinstance(cell, Cell):
                    continue
                if cell.colspan > 1:
                    covered = row[c + 1 : c + cell.colspan]
                    if len(covered) != cell.colspan - 1 or any(
                        isinstance(x, Cell) or x.merged_into != cell.id for x in covered
                    ):
                        yield Finding(
                            "L05",
                            "error",
                            f"colspan={cell.colspan} だが右隣の位置が merged_into={cell.id} になっていない",
                            element_id=cell.id,
                        )
                if cell.rowspan > 1:
                    for rr in range(r + 1, min(r + cell.rowspan, len(block.grid))):
                        below = block.grid[rr][c] if c < len(block.grid[rr]) else None
                        if below is None or isinstance(below, Cell) or below.merged_into != cell.id:
                            yield Finding(
                                "L05",
                                "error",
                                f"rowspan={cell.rowspan} だが下の位置が merged_into={cell.id} になっていない",
                                element_id=cell.id,
                            )
        width = max(widths)
        if block.layout.header_rows > len(block.grid):
            yield Finding(
                "L05",
                "error",
                f"header_rows が行数を超えている: {block.layout.header_rows} > {len(block.grid)}",
                element_id=block.id,
            )
        if block.layout.header_cols > width:
            yield Finding(
                "L05",
                "error",
                f"header_cols が列数を超えている: {block.layout.header_cols} > {width}",
                element_id=block.id,
            )

        if block.layout.span_columns and len(block.grid) > SPAN_TABLE_MAX_ROWS:
            yield Finding(
                "L05",
                "warn",
                f"段またぎの表が {len(block.grid)} 行ある（{SPAN_TABLE_MAX_ROWS} 行以下にする）。"
                "1 ページを超えると以降の内容が描画されずに消える",
                element_id=block.id,
            )

        # 被結合セルの参照先が結合元であること
        cells = {c.id: c for row in block.grid for c in row if isinstance(c, Cell)}
        for row in block.grid:
            for cell in row:
                if isinstance(cell, MergedCell):
                    owner = cells.get(cell.merged_into)
                    if owner is not None and owner.rowspan == 1 and owner.colspan == 1:
                        yield Finding(
                            "L05",
                            "error",
                            f"merged_into の参照先が結合していない: {cell.merged_into}",
                            element_id=block.id,
                        )

        # records の値が grid のどこかに現れること。
        # **比較はトークンを解いた平文で行う**：records は「意味読み取り用の正規化レコード」なので、
        # セルの生テキスト（`{const:...}` 入り）と突き合わせるのは筋が違う（docs/decisions.md 2026-09-21）。
        if block.records:
            # 参照元は表を抱えるノード（build の from_id と同じ）
            from_id = getattr(owner, "id", "") or ""
            texts = {c.text for c in cells.values()} | {_plain(c.text, ctx, from_id) for c in cells.values()}
            for i, record in enumerate(block.records):
                for key, value in record.items():
                    if str(value) not in texts:
                        yield Finding(
                            "L05",
                            "error",
                            f"records[{i}][{key}] の値が grid に無い: {value!r}",
                            element_id=block.id,
                        )
        elif block.semantic_type in RECORDS_REQUIRED_TYPES:
            # 参照表に records が無いと、table_lookup / table_reason QA の正解が
            # grid の文字列照合に退化する（CLAUDE.md §2-4 の二重表現）。
            # 結合セルの無い表は `uv run python scripts/fill_records.py <content_dir> --write` で導出できる。
            yield Finding(
                "L05",
                "warn",
                f"参照表に records が無い（semantic_type={block.semantic_type}）",
                element_id=block.id,
            )


@rule("L09", "推定ページ数が上限に収まる")
def l09_page_budget(ctx: LintContext) -> Iterator[Finding]:
    from yakkan.lint.budget import estimate_pages

    blueprint = _blueprint(ctx)
    if blueprint is None:
        return
    estimate = estimate_pages(ctx.draft, blueprint)
    if estimate.pages > 20:
        yield Finding(
            "L09",
            "error",
            f"推定ページ数が上限を超える: {estimate.pages:.1f} > 20（CLAUDE.md §0.4-5）",
            path=estimate.detail,
        )
    elif estimate.pages > 19:
        yield Finding(
            "L09", "warn", f"推定ページ数が 19 を超えた: {estimate.pages:.1f}", path=estimate.detail
        )
    elif estimate.pages > blueprint.target_pages[1]:
        yield Finding(
            "L09",
            "warn",
            f"推定 {estimate.pages:.1f} ページが目標上限 {blueprint.target_pages[1]} を超えた",
            path=estimate.detail,
        )

    # 字数も推定ページ数と同じ基準（トークンを解いた平文・描画される文字だけ）で数える。
    # 生の RichText を数えていたため、`{term:...}` を丁寧に使った文書ほど不利だった。
    chars = estimate.body_chars + estimate.table_chars
    if chars > blueprint.budget.chars_max:
        yield Finding("L09", "warn", f"本文が {chars} 字（上限 {blueprint.budget.chars_max} 字）")
    elif chars < blueprint.budget.chars_min:
        yield Finding("L09", "warn", f"本文が {chars} 字（下限 {blueprint.budget.chars_min} 字に届かない）")


def _plain(text: str, ctx: LintContext, from_id: str = "") -> str:
    """セルのトークンを解いた平文。解けないトークンは素通しする（lint は検査であって build ではない）。

    `{ref:}` は **build と同じ解決結果**にする。空文字に落としていたため、
    参照を含むセルの `records` が必ず「grid に無い」error になっていた（oneday 担当の指摘）。
    """
    from yakkan.numbering import resolve_ref as _resolve_ref
    from yakkan.richtext import PlainContext, RichTextError, parse, to_plain

    constants = ctx.draft.meta.constants
    terms = {t.id: t.term for t in ctx.draft.defined_terms}

    def ref(target: str, mode: str) -> str:
        try:
            return _resolve_ref(ctx.index, from_id, target, mode)  # type: ignore[arg-type]
        except Exception:
            return ""  # 参照先が無い場合は L01 が別に報告する

    try:
        return to_plain(
            parse(text),
            PlainContext(
                resolve_ref=ref,
                resolve_term=lambda term_id: terms.get(term_id, term_id),
                resolve_const=lambda key: constants.get(key, ""),
                footnote_marker=lambda n: "",
                auto_label="",
            ),
        )
    except (RichTextError, KeyError):
        return text
