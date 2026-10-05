"""L04（blueprint の必須要素）・L05（表）・L06 は rules.py・L09（ページ数）の実装。"""

from __future__ import annotations

import re
from collections.abc import Iterator

from keiyaku.blueprints import Blueprint, Requirement, load_blueprint
from keiyaku.lint.base import Finding, LintContext, rule
from keiyaku.lint.walk import document_nodes, iter_blocks, iter_nodes, iter_texts
from keiyaku.models import BoxBlock, Cell, Figure, FootnotesBlock, Formula, ListBlock, MergedCell, Table


def _blueprint(ctx: LintContext) -> Blueprint | None:
    try:
        return load_blueprint(ctx.draft.doctype)
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
    from keiyaku.models import BoxBlock

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

    for node in document_nodes(draft):
        collect(node)
    return out


#: ブロックとして数えない要件。`_matches` ではなく専用の数え方をする
_NON_BLOCK_KINDS = frozenset({"node", "enumeration", "ref", "term"})


def _count_non_block(ctx: LintContext, req: Requirement) -> int:
    """ブロック以外の要件を数える（docs/doctypes.md §1）。

    実装が無い kind を黙って 0 件成功にすると、blueprint の宣言が意味を失う
    （2026-09-26：`node/signature` を宣言したのに L04 が素通りし、L20 だけが捕まえた）。
    """
    draft = ctx.draft
    match req.kind:
        case "node":
            nodes = [n for n, _a in iter_nodes(document_nodes(draft))]
            return sum(1 for n in nodes if req.subtype is None or n.kind == req.subtype)
        case "enumeration":
            # 列挙表・箇条書き・号ノードの 3 系統（docs/schema.md §1.1）。
            # `min_items` が宣言されていたら、**その項目数に届く列挙だけ**を数える。
            least = req.min_items or 0
            count = 0
            for block, _owner, _article in iter_blocks(draft):
                if isinstance(block, Table) and block.semantic_type in ("enumeration", "exclusions"):
                    count += len(block.grid) - block.layout.header_rows >= least
                elif isinstance(block, ListBlock):
                    count += len(block.items) >= least
            for node, _a in iter_nodes(document_nodes(draft)):
                items = sum(1 for c in node.children if c.kind == "item")
                if items and items >= least:
                    count += 1
            return count
        case "ref":
            return sum(len(re.findall(r"\{ref:", owned.text)) for owned in iter_texts(draft) if owned.rich)
        case "term":
            return len(draft.defined_terms)
    return 0


@rule("L04", "blueprint の必須要素と最小件数を満たす")
def l04_required_elements(ctx: LintContext) -> Iterator[Finding]:
    blueprint = _blueprint(ctx)
    if blueprint is None:
        yield Finding("L04", "warn", f"blueprint が読めない: blueprints/{ctx.draft.doctype}.yaml")
        return

    owned = [(b, owner) for b, owner, _article in iter_blocks(ctx.draft)]
    blocks = [b for b, _owner in owned]
    descendants = _descendants_of(ctx.draft)
    # 見出しのバッジはブロックではなくノードが持つので、別に数える
    badge_nodes = [(node, node.badges) for node, _a in iter_nodes(ctx.draft.body) if node.badges]
    for req in blueprint.all_requirements():
        if req.kind in _NON_BLOCK_KINDS:
            found = _count_non_block(ctx, req)
            if found < req.min_count:
                label = req.kind + (f"/{req.subtype}" if req.subtype else "")
                detail = f"（{req.note}）" if req.note else ""
                yield Finding(
                    "L04",
                    "error",
                    f"必須要素が足りない: {label} が {found}/{req.min_count} 件{detail}",
                )
            continue
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
        "rate",
        "plan_matrix",
        "procedure",
        "mapping",
        "history",
        # 契約書の登録語彙（docs/schema.md §6）
        "fee_schedule",
        "deliverables",
        "inventory",
        "head_matter",
        "form_fields",
        "allocation",
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
    from keiyaku.lint.budget import estimate_pages

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
    from keiyaku.numbering import resolve_ref as _resolve_ref
    from keiyaku.richtext import PlainContext, RichTextError, parse, to_plain

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


#: 子を連ねる「容れ物」の kind。この直下に表・図を置くと**導入文より前に描画される**
#: （`docs/style_guide.md` §4）。`preamble` / `signature` は本文を持たない枠なので除く。
_CONTAINER_KINDS = frozenset({"chapter", "section", "article", "appendix", "appendix_section", "supplement"})

#: 配置の検査対象にするブロック。本文の流れの中に「図表として」現れるもの。
_PLACED_BLOCK_TYPES = (Table, Figure, Formula)


@rule("L22", "表・図・算式は導入文を持つ項に付ける（条や章の直下に置かない）")
def l22_block_placement(ctx: LintContext) -> Iterator[Finding]:
    """`article` 直下の表・図は、その条の第1項より**前**に描画される。

    「下表のとおり」と書いた項が表の 2 段落あとに来るため、読み順・アンカーの QA が総崩れになる。
    子を持たない条（表だけで構成する条）は導入文の置きようがないので見逃す。
    """
    for node, _ in iter_nodes(document_nodes(ctx.draft)):
        if node.kind not in _CONTAINER_KINDS or not node.children:
            continue
        for block in node.blocks:
            if not isinstance(block, _PLACED_BLOCK_TYPES):
                continue
            kind = {Table: "表", Figure: "図", Formula: "算式"}[type(block)]
            first = node.children[0].id
            yield Finding(
                "L22",
                "error",
                f"{kind}が {node.kind} 直下にあり導入文より前に描画される"
                f"（{first} などの項の blocks に移す。docs/style_guide.md §4）",
                element_id=getattr(block, "id", None),
                path=node.id,
            )


@rule("L23", "同じ親の下に列挙が 2 つあるなら、号は導入する項の子にする")
def l23_enumeration_nesting(ctx: LintContext) -> Iterator[Finding]:
    """号（`item`）を導入文と**兄弟**に並べると、条の中で号が通し番号になる。

    実物の契約書は、項が変われば号を `(1)` から振り直す。導入文の**子**に置けば
    numbering が親ごとに数え直すので、宣言を変えずに直る（2026-09-27：csl-0001 の
    第3条で 2 つ目の列挙が `(7)` から始まった。lint も verify も通ったまま目視で発覚）。

    条の中に列挙が **1 つだけ**なら兄弟に並べてよい（通し番号にならないため）。
    """
    for node, _ in iter_nodes(document_nodes(ctx.draft)):
        children = node.children
        if not children:
            continue
        #: 直下の子を「導入文 → 号の並び」の塊に区切り、塊が 2 つ以上あるかを見る
        runs = 0
        in_run = False
        for child in children:
            if child.kind == "item":
                if not in_run:
                    runs += 1
                    in_run = True
            else:
                in_run = False
        if runs >= 2:
            yield Finding(
                "L23",
                "error",
                f"{node.id} の直下に号の並びが {runs} 組ある"
                "（号は導入する項の children に入れる。兄弟に並べると通し番号になる）",
                element_id=node.id,
            )


@rule("L04", "執筆メモ（_todo）が残っていない")
def l04_todos_cleared(ctx: LintContext) -> Iterator[Finding]:
    """`_todo` が残っている content は**未執筆**として落とす。

    `_todo` は pydantic の検証で捨てられるので `ctx.draft` には残らない。
    **生の JSON を読み直さないと見えない**——そのため lint は長い間これを見逃しており、
    `keiyaku batch` だけが捕まえていた（2026-09-27：11 content 中 11 件に残っていた）。
    `docs/lint_rules.md` は L04 が「必須要素・TODO の残り」を見ると書いてあったので、実装を合わせる。
    """
    if ctx.content_dir is None:
        return
    from keiyaku.compose import ComposeError, count_todos, raw_document

    try:
        left = count_todos(raw_document(ctx.content_dir))
    except (ComposeError, FileNotFoundError):
        return  # 壊れた JSON は L00 の担当
    if left:
        yield Finding(
            "L04",
            "error",
            f"執筆メモ（_todo）が {left} 件残っている（埋めたら消す）",
            path=str(ctx.content_dir),
        )


@rule("L24", "parts/ に doc.json から参照されていないファイルが無い")
def l24_orphan_parts(ctx: LintContext) -> Iterator[Finding]:
    """`parts/*.json` はすべて `doc.json` の `parts` から参照されていること。

    参照されていないファイルは**書き直しの置き去り**である。中身は lint・build・render の
    どこにも現れないので、未執筆のスケルトン（`_todo` つき）がそのまま残っていても気づけない
    （2026-10-02：`emp-0002` に scaffold 直後の 8 ファイルが残っていた）。
    消すか、`doc.json` の `parts` に入れるかのどちらかにする。
    """
    import json as _json

    if ctx.content_dir is None:
        return
    doc_path = ctx.content_dir / "doc.json"
    parts_dir = ctx.content_dir / "parts"
    if not doc_path.is_file() or not parts_dir.is_dir():
        return
    try:
        used = set(_json.loads(doc_path.read_text(encoding="utf-8")).get("parts") or [])
    except (OSError, _json.JSONDecodeError):
        return  # 壊れた JSON は L00 の担当
    extra = sorted(p.name for p in parts_dir.glob("*.json") if p.name not in used)
    for name in extra:
        yield Finding(
            "L24",
            "error",
            f"parts/{name} が doc.json の parts から参照されていない（消すか parts に入れる）",
            path=str(parts_dir / name),
        )


#: 位置で指す言い方。番号を持つ表・図には使わない
_POSITIONAL_REFS = ("下表", "下図", "次の表", "次の図", "上表", "上図")


@rule("L26", "番号を持つ表・図を「下表」「下図」で指していない")
def l26_positional_reference(ctx: LintContext) -> Iterator[Finding]:
    """キャプション（＝番号）を持つ表・図は `{ref:}` で指す。

    「下表のとおり」は**版面が変われば嘘になる**（実際に別紙の表が次ページへ送られ、
    「下表」が前ページに取り残された）。さらに、同じ表を一方では「下表」、他方では
    `{ref:}`（＝「表1」）と呼ぶと、**同じものの呼び方が文書内で揺れる**
    （2026-10-02 の盲検で指摘された）。
    キャプションを持たない表（列挙用。L18）は番号が無いので「下表」でよい。
    """
    from keiyaku.models import Figure, Table

    caption_labels = ctx.caption_labels
    for node, _ancestors in iter_nodes(document_nodes(ctx.draft)):
        text = node.text or ""
        if not any(word in text for word in _POSITIONAL_REFS):
            continue
        for block in node.blocks:
            if not isinstance(block, Table | Figure):
                continue
            if not caption_labels.get(block.id):
                continue
            yield Finding(
                "L26",
                "warn",
                f"{caption_labels[block.id]} は番号を持つので「下表」ではなく {{ref:{block.id}}} で指す",
                element_id=node.id,
            )
