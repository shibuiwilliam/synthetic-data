"""`dataset/data-card.md` の生成（仕様は `docs/data_card.md`）。

    uv run yakkan datacard update   # 書き出す
    uv run yakkan datacard check    # 書き換えずに鮮度を見る

**カードに出る数値はすべて `dataset/` の実ファイルから測る。** 仕様書や `docs/progress.md`、
過去のセッションの記憶を数値の出典にしない。固定文字列に統計値を焼き込まない
（`docs/decisions.md` 2026-10-04「`dataset/README.md` が統計値を焼き込んでいた」の再発防止）。

生成は決定論。`datetime.now()` を入れず、**自分自身のファイルサイズは数えない**
（数えると書き出すたびに数が動き、鮮度検査が収束しない）。
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Annotated, Literal, get_args, get_origin

from pydantic import Field

from yakkan.models import (
    Block,
    BoxStyle,
    Diagram,
    ListStyle,
    Model,
    Node,
    NumberingScheme,
    SemanticType,
    Source,
)

#: 生成するファイル名。`dataset/` 直下に置く
CARD_NAME = "data-card.md"
#: 「母数が足りない」と判断する content 数の閾値（`docs/data_card.md` §4.3）
MIN_CONTENTS = 3
#: 容量の集計から外すファイル名（自分自身を数えると鮮度検査が収束しない）
SIZE_EXCLUDE = frozenset({CARD_NAME})
#: 観点の分類。カードの並び順もこの順
CoverageGroup = Literal["骨格", "体裁", "表の意味種別", "図の種別", "宣言"]


def _union_kinds(union: object, field: str) -> tuple[str, ...]:
    """判別子つき Union から各メンバの判別子の値を取り出す。

    図の種別・ブロック種別を**モデルから引く**ための小道具。手で並べると
    `models.py` に種別を足したときにカードが黙って取りこぼす。
    """
    members = get_args(get_args(union)[0]) if get_origin(union) is Annotated else get_args(union)
    out: list[str] = []
    for member in members:
        info = getattr(member, "model_fields", {}).get(field)
        if info is not None and isinstance(info.default, str):
            out.append(info.default)
    return tuple(out)


#: 図の種別（`Diagram` の判別子）。宣言されているが使われていない種別を挙げるために使う
FIGURE_KINDS: tuple[str, ...] = _union_kinds(Diagram, "kind")
#: ブロック種別（`Block` の判別子）
BLOCK_TYPES: tuple[str, ...] = _union_kinds(Block, "type")
#: 発行体の種別の表示名
ISSUER_LABELS = {"stock": "株式会社", "mutual": "相互会社"}

#: 骨格の観点（`_features()` が見る順）。**ここが観点名の正本**で、`_universe()` も
#: これを使う——片方にしか無いと、使用 0 の観点が「未使用」の表に出ずに黙って消える
SKELETON_FEATURES: tuple[str, ...] = (
    "表紙",
    "前付けの前書き",
    "目的別もくじ",
    "特約一覧表",
    "ペットネーム対応表",
    "目次",
    "編・部（part）",
    "章（chapter）",
    "節（section）",
    "特約（rider）",
    "条（article）",
    "項（paragraph）",
    "号（item）",
    "細目（号より下）",
    "別表・別紙（appendix）",
    "条文型（条を「第◯条」で番号する）",
    "丸数字型（条の位置に丸数字の小見出し）",
)
#: 体裁の観点。枠・箇条書きの style・発行体の種別は種別ごとに別の観点として足す
FORMAT_FEATURES: tuple[str, ...] = (
    "脚注（条末）",
    "算式（formula）",
    "箇条書き（list）",
    "Q 見出し（qa_heading）",
    "強制改ページ（page_break）",
    "結合セル",
    "縦書きセル",
    "繰り返し表頭",
    "段またぎ表（span_columns）",
    "番号の例外（number_override）",
    "商品名バッジ",
    "用語集（defined_terms）",
    "定数（meta.constants）",
    "ペットネーム",
)


# --- 統計のモデル -------------------------------------------------------------


class ExtSize(Model):
    """拡張子ごとの容量。"""

    ext: str
    files: int
    bytes: int


class CountRow(Model):
    """「名前 → 件数」の 1 行。`documents` は出現した文書数、`items` は総件数。"""

    name: str
    items: int = 0
    documents: int = 0
    contents: int = 0


class Scale(Model):
    """コーパス全体の規模。"""

    documents: int = 0
    ready: int = 0
    failed: int = 0
    #: `manifest update --no-verify` で作った manifest では status が決まらない
    unverified: int = 0
    contents: int = 0
    genres: int = 0
    styles: int = 0
    pages: int = 0
    page_images: int = 0
    #: `derived.plain_text` の文字数（ラベルを除く本文）
    chars: int = 0
    #: `answer.json` のページ本文の文字数（繰り返し表頭とヘッダ/フッタを除いた紙面の文字）
    answer_chars: int = 0
    tables: int = 0
    table_cells: int = 0
    merged_cells: int = 0
    figures: int = 0
    figure_nodes: int = 0
    figure_edges: int = 0
    figure_paths: int = 0
    formulas: int = 0
    refs: int = 0
    footnotes: int = 0
    defined_terms: int = 0
    term_uses: int = 0
    constants: int = 0
    enumerations: int = 0
    enumeration_items: int = 0
    toc_entries: int = 0
    qa_items: int = 0
    elements: int = 0
    passages: int = 0
    sizes: list[ExtSize] = Field(default_factory=list)
    #: 成果物の一覧に無いファイル（調査の痕跡など）。`docs/data_card.md` §4.4
    strays: list[CountRow] = Field(default_factory=list)

    @property
    def bytes_total(self) -> int:
        return sum(s.bytes for s in self.sizes)

    @property
    def files_total(self) -> int:
        return sum(s.files for s in self.sizes)


class GenreRow(Model):
    genre: str
    #: blueprint の `description` の 1 文目。**題名は文書ごとに違う**ので §4.3 に出す
    name: str = ""
    #: blueprint の `target_pages`
    target: str = ""
    contents: int = 0
    documents: int = 0
    pages_min: int = 0
    pages_max: int = 0
    chars: int = 0
    tables: int = 0
    figures: int = 0
    qa_items: int = 0


class StyleRow(Model):
    style_id: str
    documents: int = 0
    pages: int = 0
    columns: list[str] = Field(default_factory=list)
    page_sizes: list[str] = Field(default_factory=list)
    #: その style の PDF に**実際に埋め込まれていた**フォント（`layout.renderer.fonts` は
    #: 描画に登録した候補の一覧で、使われたものとは違う）
    fonts: list[str] = Field(default_factory=list)


class DocRow(Model):
    doc_id: str
    content_id: str
    genre: str
    style_id: str
    title: str
    seed: int
    pages: int
    chars: int
    tables: int
    figures: int
    qa_items: int
    status: str
    errors: list[str] = Field(default_factory=list)


class SearchStats(Model):
    passages: int = 0
    queries: int = 0
    qrels: int = 0
    corpus_documents: int = 0
    corpus_contents: int = 0
    passage_kinds: list[CountRow] = Field(default_factory=list)
    query_kinds: list[CountRow] = Field(default_factory=list)
    grades: list[CountRow] = Field(default_factory=list)
    #: `filters`（issuer / product_name / genre）を持つクエリ
    with_filters: int = 0
    #: 「紛らわしいと宣言された非適合」を持つクエリと、その総件数
    with_hard_negatives: int = 0
    hard_negatives: int = 0
    #: gold が空集合のクエリ（`no_answer`）。qrels に 1 行も出ない
    no_answer: int = 0
    truncated: int = 0
    truncated_examples: list[str] = Field(default_factory=list)
    #: grade 1 を 1 クエリ何件で打ち切るか（`yakkan.search_set.MAX_RELATED`）。
    #: **ここも焼き込まない**——実装の定数を読む
    related_cap: int = 0
    #: 打ち切りで qrels に出なかった grade 1 の件数
    truncated_items: int = 0
    #: `search/` に出てこない content（文書を足して `yakkan export` を回していない）
    missing_contents: list[str] = Field(default_factory=list)
    available: bool = False


class LayoutStats(Model):
    #: PDF に実際に埋め込まれていたフォント（文書数）
    embedded_fonts: list[CountRow] = Field(default_factory=list)
    page_sizes: list[CountRow] = Field(default_factory=list)
    columns: list[CountRow] = Field(default_factory=list)
    regions: list[CountRow] = Field(default_factory=list)
    renderers: list[CountRow] = Field(default_factory=list)
    fonts: list[CountRow] = Field(default_factory=list)
    dpi: list[CountRow] = Field(default_factory=list)


class Coverage(Model):
    """1 つの観点を覆っている content と文書の数。"""

    group: str
    name: str
    contents: int = 0
    documents: int = 0


class DataCardStats(Model):
    """カードに出すすべての実測値。**カードの本文はここから組み立てる**。"""

    scale: Scale = Field(default_factory=Scale)
    genres: list[GenreRow] = Field(default_factory=list)
    styles: list[StyleRow] = Field(default_factory=list)
    documents: list[DocRow] = Field(default_factory=list)
    node_kinds: list[CountRow] = Field(default_factory=list)
    block_types: list[CountRow] = Field(default_factory=list)
    semantic_types: list[CountRow] = Field(default_factory=list)
    figure_kinds: list[CountRow] = Field(default_factory=list)
    qa_types: list[CountRow] = Field(default_factory=list)
    qa_sources: list[CountRow] = Field(default_factory=list)
    qa_answer_types: list[CountRow] = Field(default_factory=list)
    numbering_schemes: list[CountRow] = Field(default_factory=list)
    issuer_kinds: list[CountRow] = Field(default_factory=list)
    #: 体裁の宣言（`digit_style` / `article_heading` / `caption_numbering` / `footnote_style`）
    meta_options: list[CountRow] = Field(default_factory=list)
    #: 用語集の索引見出し（`index_kana`）の分布
    term_kana: list[CountRow] = Field(default_factory=list)
    search: SearchStats = Field(default_factory=SearchStats)
    layout: LayoutStats = Field(default_factory=LayoutStats)
    coverage: list[Coverage] = Field(default_factory=list)
    #: 覆っている content が `MIN_CONTENTS` 未満（0 は除く）
    thin: list[Coverage] = Field(default_factory=list)
    #: 宣言はあるが使っている content が 0
    unused: list[Coverage] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
    #: 宣言の総数（`blueprints/` `models.NumberingScheme` `styles/`）
    declared_genres: int = 0
    declared_schemes: int = 0
    declared_styles: int = 0
    #: `manifest.json` の `dataset_version`
    dataset_version: str = ""


# --- 測る ---------------------------------------------------------------------


def _walk(nodes: Iterable[Node]) -> Iterator[Node]:
    for node in nodes:
        yield node
        yield from _walk(node.children)


def _blocks(node_blocks: Iterable[object]) -> Iterator[object]:
    """`box` は中に block を持つので再帰で開く（`BoxBlock.blocks`）。"""
    for block in node_blocks:
        yield block
        inner = getattr(block, "blocks", None)
        if inner:
            yield from _blocks(inner)


def all_nodes(source: Source) -> list[Node]:
    """本文と別表のノードを平らにする。"""
    return list(_walk(source.body)) + list(_walk(source.appendices))


def all_blocks(source: Source) -> list[object]:
    """紙面に出るブロックをすべて集める。

    **`front_matter` の表を忘れない。** 目的別もくじ・特約一覧表・ペットネーム対応表は
    `Node.blocks` の外にあるが紙面の表であり `derived.tables` にも入る。本文の木だけを
    走ると `semantic_type: purpose_index` が「使用 0」に見える（`docs/data_card.md` §4.1）。
    """
    blocks = list(_blocks([b for node in all_nodes(source) for b in node.blocks]))
    blocks += list(_blocks(source.front_matter.preface))
    blocks += list(_blocks(source.back_matter.colophon))
    blocks += list(_blocks(source.back_matter.contact))
    front = source.front_matter
    blocks += [t for t in (front.purpose_index, front.rider_index, front.petname_table) if t is not None]
    return blocks


def _rows(counter: Counter[str], docs: Counter[str], contents: Counter[str]) -> list[CountRow]:
    """件数の多い順→名前順に並べる（決定論）。"""
    return [
        CountRow(name=name, items=count, documents=docs[name], contents=contents[name])
        for name, count in sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _sizes(dataset_dir: Path) -> list[ExtSize]:
    files: Counter[str] = Counter()
    size: Counter[str] = Counter()
    for path in dataset_dir.rglob("*"):
        if not path.is_file() or path.name.startswith(".") or path.name in SIZE_EXCLUDE:
            continue
        ext = path.suffix.lstrip(".") or "(拡張子なし)"
        files[ext] += 1
        size[ext] += path.stat().st_size
    return [
        ExtSize(ext=ext, files=files[ext], bytes=total)
        for ext, total in sorted(size.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def _strays(dataset_dir: Path, doc_ids: Iterable[str]) -> list[CountRow]:
    """文書のディレクトリにある「成果物でないファイル」を名前ごとに数える。

    調査の痕跡（`render.pdf` など）が配布物に混ざるのを黙って見逃さないため
    （`docs/data_card.md` §4.4）。
    """
    from yakkan.manifest import ARTIFACT_FILES

    known = set(ARTIFACT_FILES)
    found: Counter[str] = Counter()
    for doc_id in doc_ids:
        doc_dir = dataset_dir / doc_id
        if not doc_dir.is_dir():
            continue
        for path in doc_dir.iterdir():
            if path.is_dir():
                continue
            if path.name in known or path.name.startswith("."):
                continue
            found[path.name] += 1
    return _rows(found, Counter(), Counter())


def embedded_fonts(pdf_path: Path) -> list[str]:
    """PDF に**実際に埋め込まれていた**フォント名（サブセット接頭辞を外したもの）。

    `layout.renderer.fonts` は描画に登録した候補の一覧であって、使われたものではない
    （明朝の style でも PDF に入るのは Noto Serif JP だけ）。フォントの別は OCR の
    精度に直接効くので、候補ではなく実測を載せる。

    **ページのフォント資源（`/BaseFont`）から読む。** 全文字を走査する方法と同じ結果に
    なることは `scripts/verify_data_card.py` が別経路で突合する（114 文書で約 2 分 →
    約 2 秒）。PDF が無ければ空を返す。
    """
    if not pdf_path.is_file():
        return []
    import pdfplumber
    from pdfminer.pdftypes import resolve1

    names: set[str] = set()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            resources = resolve1(page.page_obj.resources) or {}
            for font in (resolve1(resources.get("Font")) or {}).values():
                entry = resolve1(font) or {}
                base = entry.get("BaseFont")
                if base is None:
                    for descendant in resolve1(entry.get("DescendantFonts")) or []:
                        base = (resolve1(descendant) or {}).get("BaseFont") or base
                if base is not None:
                    names.add(str(getattr(base, "name", base)).split("+")[-1])
    return sorted(names)


def _features(source: Source) -> set[tuple[str, str]]:
    """1 文書が覆っている観点の集合（`docs/data_card.md` §4.3）。"""
    nodes = all_nodes(source)
    kinds = {node.kind for node in nodes}
    blocks = all_blocks(source)
    types = {getattr(b, "type", "") for b in blocks}
    tables = [b for b in blocks if getattr(b, "type", "") == "table"]
    cells = [c for b in tables for row in b.grid for c in row]
    meta = source.meta
    front = source.front_matter
    article_labels = [
        label.label for label in source.derived.labels.values() if label.kind == "article" and label.label
    ]
    article_numbered = any(label.startswith("第") for label in article_labels)

    found: set[tuple[str, str]] = set()
    for name, ok in (
        ("表紙", True),
        ("前付けの前書き", bool(front.preface)),
        ("目的別もくじ", front.purpose_index is not None),
        ("特約一覧表", front.rider_index is not None),
        ("ペットネーム対応表", front.petname_table is not None),
        ("目次", bool(source.derived.toc)),
        ("編・部（part）", "part" in kinds),
        ("章（chapter）", "chapter" in kinds),
        ("節（section）", "section" in kinds),
        ("特約（rider）", "rider" in kinds),
        ("条（article）", "article" in kinds),
        ("項（paragraph）", "paragraph" in kinds),
        ("号（item）", "item" in kinds),
        ("細目（号より下）", bool({"subitem", "subsubitem"} & kinds)),
        ("別表・別紙（appendix）", "appendix" in kinds),
        # 条文型と丸数字型の別は**条ラベルの形**で決まる。`kind: "article"` の有無では決まらない——
        # `jyusetsu`（重要事項説明書）は「条を持たない」と宣言しているが実装は `article` ノードを
        # 使い、番号方式が「①」と振るだけである（実測。`docs/data_card.md` §4.3）
        ("条文型（条を「第◯条」で番号する）", article_numbered),
        ("丸数字型（条の位置に丸数字の小見出し）", bool(article_labels) and not article_numbered),
    ):
        if ok:
            found.add(("骨格", name))
    for name, ok in (
        ("脚注（条末）", bool(source.derived.footnote_index)),
        ("算式（formula）", "formula" in types),
        ("箇条書き（list）", "list" in types),
        ("Q 見出し（qa_heading）", "qa_heading" in types),
        ("強制改ページ（page_break）", "page_break" in types),
        ("結合セル", any(getattr(c, "merged_into", None) for c in cells)),
        ("縦書きセル", any(getattr(c, "vertical_text", False) for c in cells)),
        ("繰り返し表頭", any(b.layout.repeat_header for b in tables)),
        ("段またぎ表（span_columns）", any(b.layout.span_columns for b in tables)),
        ("番号の例外（number_override）", any(n.number_override for n in nodes)),
        ("商品名バッジ", any(n.badges for n in nodes)),
        ("用語集（defined_terms）", bool(source.defined_terms)),
        ("定数（meta.constants）", bool(meta.constants)),
        ("ペットネーム", meta.pet_name is not None),
        (f"発行体が{ISSUER_LABELS.get(meta.issuer.kind, meta.issuer.kind)}", True),
    ):
        if ok:
            found.add(("体裁", name))
    for style in get_args(BoxStyle):
        if any(getattr(b, "type", "") == "box" and getattr(b, "style", "") == style for b in blocks):
            found.add(("体裁", f"枠（{style}）"))
    for style in get_args(ListStyle):
        if any(getattr(b, "type", "") == "list" and getattr(b, "style", "") == style for b in blocks):
            found.add(("体裁", f"箇条書きの style（{style}）"))
    for table in tables:
        found.add(("表の意味種別", table.semantic_type))
    for block in blocks:
        if getattr(block, "type", "") == "figure":
            found.add(("図の種別", block.diagram.kind))
    found.add(("宣言", f"genre: {source.genre}"))
    found.add(("宣言", f"numbering: {meta.numbering_scheme}"))
    found.add(("宣言", f"digit_style: {meta.digit_style}"))
    found.add(("宣言", f"article_heading: {meta.article_heading}"))
    found.add(("宣言", f"caption_numbering: {meta.caption_numbering}"))
    found.add(("宣言", f"footnote_style: {meta.footnote_style}"))
    return found


def _universe(genres: Iterable[str], schemes: Iterable[str], styles: Iterable[str]) -> set[tuple[str, str]]:
    """「宣言されている観点」の全体。使用 0 のものを挙げるために要る。"""
    all_keys: set[tuple[str, str]] = {("表の意味種別", s) for s in get_args(SemanticType)}
    all_keys |= {("骨格", name) for name in SKELETON_FEATURES}
    all_keys |= {("体裁", name) for name in FORMAT_FEATURES}
    all_keys |= {("図の種別", k) for k in FIGURE_KINDS}
    all_keys |= {("体裁", f"枠（{s}）") for s in get_args(BoxStyle)}
    all_keys |= {("体裁", f"箇条書きの style（{s}）") for s in get_args(ListStyle)}
    all_keys |= {("体裁", f"発行体が{label}") for label in ISSUER_LABELS.values()}
    all_keys |= {("宣言", f"genre: {g}") for g in genres}
    all_keys |= {("宣言", f"numbering: {s}") for s in schemes}
    all_keys |= {("宣言", f"style: {s}") for s in styles}
    return all_keys


def _search(dataset_dir: Path, contents: set[str]) -> SearchStats:
    from yakkan.search_set import MAX_RELATED

    search_dir = dataset_dir / "search"
    stats = SearchStats(related_cap=MAX_RELATED)
    if not search_dir.is_dir():
        return stats

    def read(name: str) -> list[dict]:
        path = search_dir / name
        if not path.is_file():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    passages, queries, qrels = read("passages.jsonl"), read("queries.jsonl"), read("qrels.jsonl")
    stats.available = bool(passages or queries or qrels)
    stats.passages, stats.queries, stats.qrels = len(passages), len(queries), len(qrels)
    corpus_docs = {str(p.get("doc_id", "")) for p in passages}
    corpus_contents = {str(p.get("content_id", "")) for p in passages}
    stats.corpus_documents = len(corpus_docs - {""})
    stats.corpus_contents = len(corpus_contents - {""})
    stats.missing_contents = sorted(contents - corpus_contents)
    stats.passage_kinds = _rows(Counter(str(p.get("kind", "?")) for p in passages), Counter(), Counter())
    stats.query_kinds = _rows(Counter(str(q.get("kind", "?")) for q in queries), Counter(), Counter())
    stats.grades = _rows(Counter(f"grade {r.get('grade')}" for r in qrels), Counter(), Counter())
    stats.with_filters = sum(1 for q in queries if q.get("filters"))
    stats.with_hard_negatives = sum(1 for q in queries if q.get("hard_negatives"))
    stats.hard_negatives = sum(len(q.get("hard_negatives") or []) for q in queries)
    stats.no_answer = sum(1 for q in queries if not q.get("n_relevant"))
    truncated = [q for q in queries if q.get("related_truncated")]
    stats.truncated = len(truncated)
    stats.truncated_items = sum(
        max(0, int(q.get("n_related_total") or 0) - int(q.get("n_related") or 0)) for q in truncated
    )
    stats.truncated_examples = sorted({str(q.get("query", "")) for q in truncated})[:3]
    return stats


def collect(dataset_dir: Path) -> DataCardStats:
    """`dataset/` を走査して実測値を集める（**書き出しはしない**）。"""
    from yakkan.blueprints import available_genres, load_blueprint
    from yakkan.manifest import MANIFEST_NAME, Manifest
    from yakkan.models import Layout
    from yakkan.styles import available_styles

    stats = DataCardStats()
    manifest_path = dataset_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        return stats
    manifest = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))
    stats.dataset_version = manifest.dataset_version

    node_kinds: Counter[str] = Counter()
    block_types: Counter[str] = Counter()
    semantic: Counter[str] = Counter()
    figure_kinds: Counter[str] = Counter()
    qa_types: Counter[str] = Counter()
    qa_sources: Counter[str] = Counter()
    qa_answers: Counter[str] = Counter()
    node_docs: Counter[str] = Counter()
    block_docs: Counter[str] = Counter()
    semantic_docs: Counter[str] = Counter()
    figure_docs: Counter[str] = Counter()
    page_sizes: Counter[str] = Counter()
    columns: Counter[str] = Counter()
    regions: Counter[str] = Counter()
    renderers: Counter[str] = Counter()
    fonts: Counter[str] = Counter()
    embedded: Counter[str] = Counter()
    style_fonts: dict[str, set[str]] = {}
    dpi: Counter[str] = Counter()
    schemes: Counter[str] = Counter()
    issuers: Counter[str] = Counter()
    options: Counter[str] = Counter()
    term_kana: Counter[str] = Counter()
    feature_docs: Counter[tuple[str, str]] = Counter()
    feature_contents: dict[tuple[str, str], set[str]] = {}
    by_genre: dict[str, GenreRow] = {}
    genre_contents: dict[str, set[str]] = {}
    by_style: dict[str, StyleRow] = {}
    titles: dict[str, str] = {}
    disclaimers: set[str] = set()
    contents: set[str] = set()

    for entry in manifest.documents:
        doc_dir = dataset_dir / entry.doc_id
        source = Source.model_validate_json((doc_dir / "source.json").read_text(encoding="utf-8"))
        layout = Layout.model_validate_json((doc_dir / "layout.json").read_text(encoding="utf-8"))
        derived = source.derived
        contents.add(entry.content_id)
        titles[entry.content_id] = source.meta.title
        disclaimers.add(source.meta.disclaimer)

        nodes = all_nodes(source)
        for node in nodes:
            node_kinds[node.kind] += 1
        for kind in {n.kind for n in nodes}:
            node_docs[kind] += 1
        blocks = all_blocks(source)
        for block in blocks:
            block_types[getattr(block, "type", "?")] += 1
            if getattr(block, "type", "") == "table":
                semantic[block.semantic_type] += 1
                stats.scale.table_cells += sum(len(row) for row in block.grid)
                stats.scale.merged_cells += sum(
                    1 for row in block.grid for cell in row if getattr(cell, "merged_into", None)
                )
            if getattr(block, "type", "") == "figure":
                figure_kinds[block.diagram.kind] += 1
        for name in {getattr(b, "type", "?") for b in blocks}:
            block_docs[name] += 1
        for name in {b.semantic_type for b in blocks if getattr(b, "type", "") == "table"}:
            semantic_docs[name] += 1
        for name in {b.diagram.kind for b in blocks if getattr(b, "type", "") == "figure"}:
            figure_docs[name] += 1

        for key in _features(source):
            feature_docs[key] += 1
            feature_contents.setdefault(key, set()).add(entry.content_id)

        scale = stats.scale
        scale.pages += entry.pages
        scale.page_images += entry.page_images
        scale.chars += entry.chars
        scale.tables += entry.tables
        scale.figures += entry.figures
        scale.refs += entry.refs
        scale.footnotes += entry.footnotes
        scale.qa_items += entry.qa_items
        scale.formulas += len(derived.formulas)
        scale.defined_terms += len(source.defined_terms)
        scale.term_uses += len(derived.term_uses)
        scale.constants += len(source.meta.constants)
        scale.enumerations += len(derived.enumerations)
        scale.enumeration_items += sum(len(e.items) for e in derived.enumerations)
        scale.toc_entries += len(derived.toc)
        for figure in derived.figures.values():
            scale.figure_nodes += len(figure.graph.nodes)
            scale.figure_edges += len(figure.graph.edges)
            scale.figure_paths += len(figure.paths)
        for term in source.defined_terms:
            term_kana[term.index_kana] += 1

        # **`status: failed` の文書はここから下を持たない。** 欠けていても落ちない
        answer_path = doc_dir / "answer.json"
        if answer_path.is_file():
            answer = json.loads(answer_path.read_text(encoding="utf-8"))
            scale.answer_chars += sum(int(page.get("chars", 0)) for page in answer.get("pages", []))
        for name in ("elements", "passages"):
            path = doc_dir / f"{name}.jsonl"
            if path.is_file():
                lines = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
                setattr(scale, name, getattr(scale, name) + lines)

        qa_path = doc_dir / "qa.json"
        if qa_path.is_file():
            for item in json.loads(qa_path.read_text(encoding="utf-8")).get("items", []):
                qa_types[str(item.get("type", "?"))] += 1
                qa_sources[str(item.get("source", "?"))] += 1
                qa_answers[str(item.get("answer_type", "?"))] += 1

        meta = source.meta
        schemes[meta.numbering_scheme] += 1
        issuers[ISSUER_LABELS.get(meta.issuer.kind, meta.issuer.kind)] += 1
        options[f"digit_style: {meta.digit_style}"] += 1
        options[f"article_heading: {meta.article_heading}"] += 1
        options[f"caption_numbering: {meta.caption_numbering}"] += 1
        options[f"footnote_style: {meta.footnote_style}"] += 1

        width, height = layout.page_size_pt
        size_label = f"{width:.0f}×{height:.0f} pt（{width * 25.4 / 72:.0f}×{height * 25.4 / 72:.0f} mm）"
        page_sizes[size_label] += 1
        renderers[f"{layout.renderer.name} {layout.renderer.version}"] += 1
        dpi[f"{layout.dpi_png} dpi"] += 1
        for font in layout.renderer.fonts:
            fonts[font] += 1
        doc_columns: Counter[int] = Counter()
        for page in layout.pages:
            columns[f"{page.columns} 段"] += 1
            doc_columns[page.columns] += 1
            for line in page.text_lines:
                regions[line.region] += 1

        used = embedded_fonts(doc_dir / "doc.pdf")
        for font in used:
            embedded[font] += 1
        style_fonts.setdefault(entry.style_id, set()).update(used)

        row = by_genre.setdefault(entry.genre, GenreRow(genre=entry.genre))
        row.documents += 1
        row.chars += entry.chars
        row.tables += entry.tables
        row.figures += entry.figures
        row.qa_items += entry.qa_items
        row.pages_min = entry.pages if row.pages_min == 0 else min(row.pages_min, entry.pages)
        row.pages_max = max(row.pages_max, entry.pages)
        genre_contents.setdefault(entry.genre, set()).add(entry.content_id)
        style = by_style.setdefault(entry.style_id, StyleRow(style_id=entry.style_id))
        style.documents += 1
        style.pages += entry.pages
        if size_label not in style.page_sizes:
            style.page_sizes.append(size_label)
        for count, _ in sorted(doc_columns.items()):
            if f"{count} 段" not in style.columns:
                style.columns.append(f"{count} 段")

        stats.documents.append(
            DocRow(
                doc_id=entry.doc_id,
                content_id=entry.content_id,
                genre=entry.genre,
                style_id=entry.style_id,
                title=source.meta.title,
                seed=entry.seed,
                pages=entry.pages,
                chars=entry.chars,
                tables=entry.tables,
                figures=entry.figures,
                qa_items=entry.qa_items,
                status=entry.status,
                errors=list(entry.errors),
            )
        )

    scale = stats.scale
    scale.documents = len(manifest.documents)
    scale.ready = sum(1 for d in manifest.documents if d.status == "ready")
    scale.failed = sum(1 for d in manifest.documents if d.status == "failed")
    scale.unverified = sum(1 for d in manifest.documents if d.status == "unverified")
    scale.contents = len(contents)
    scale.genres = len(by_genre)
    scale.styles = len(by_style)
    scale.sizes = _sizes(dataset_dir)
    scale.strays = _strays(dataset_dir, (d.doc_id for d in manifest.documents))

    for genre, row in by_genre.items():
        row.contents = len(genre_contents[genre])
        # 名称と目標ページは blueprint の宣言から引く（題名は content ごとに違うので §4.3 に出す）
        try:
            blueprint = load_blueprint(genre)
        except (FileNotFoundError, ValueError):
            continue
        row.name = blueprint.description.split("。")[0]
        row.target = f"{blueprint.target_pages[0]}–{blueprint.target_pages[1]}"
    stats.genres = sorted(by_genre.values(), key=lambda r: r.genre)
    for style_id, style_row in by_style.items():
        style_row.fonts = sorted(style_fonts.get(style_id, set()))
        style_row.page_sizes.sort()
        style_row.columns.sort()
    stats.styles = sorted(by_style.values(), key=lambda r: r.style_id)
    stats.documents.sort(key=lambda r: r.doc_id)
    stats.node_kinds = _rows(node_kinds, node_docs, Counter())
    stats.block_types = _rows(block_types, block_docs, Counter())
    stats.semantic_types = _rows(semantic, semantic_docs, Counter())
    stats.figure_kinds = _rows(figure_kinds, figure_docs, Counter())
    stats.qa_types = _rows(qa_types, Counter(), Counter())
    stats.qa_sources = _rows(qa_sources, Counter(), Counter())
    stats.qa_answer_types = _rows(qa_answers, Counter(), Counter())
    stats.numbering_schemes = _rows(schemes, schemes, Counter())
    stats.issuer_kinds = _rows(issuers, issuers, Counter())
    stats.meta_options = _rows(options, options, Counter())
    stats.term_kana = _rows(term_kana, Counter(), Counter())
    stats.layout = LayoutStats(
        embedded_fonts=_rows(embedded, Counter(), Counter()),
        page_sizes=_rows(page_sizes, Counter(), Counter()),
        columns=_rows(columns, Counter(), Counter()),
        regions=_rows(regions, Counter(), Counter()),
        renderers=_rows(renderers, Counter(), Counter()),
        fonts=_rows(fonts, Counter(), Counter()),
        dpi=_rows(dpi, Counter(), Counter()),
    )
    stats.search = _search(dataset_dir, contents)
    stats.disclaimers = sorted(disclaimers)

    genres, scheme_names, styles = available_genres(), list(get_args(NumberingScheme)), available_styles()
    stats.declared_genres = len(genres)
    stats.declared_schemes = len(scheme_names)
    stats.declared_styles = len(styles)
    seen = {key: len(values) for key, values in feature_contents.items()}
    for style_id, style_row in by_style.items():
        key = ("宣言", f"style: {style_id}")
        feature_docs[key] = style_row.documents
        seen[key] = len({d.content_id for d in stats.documents if d.style_id == style_id})
    order = {name: i for i, name in enumerate(get_args(CoverageGroup))}
    keys = set(seen) | _universe(genres, scheme_names, styles)
    stats.coverage = sorted(
        (
            Coverage(
                group=group,
                name=name,
                contents=seen.get((group, name), 0),
                documents=feature_docs.get((group, name), 0),
            )
            for group, name in keys
        ),
        key=lambda c: (order.get(c.group, 99), -c.contents, c.name),
    )
    stats.thin = [c for c in stats.coverage if 0 < c.contents < MIN_CONTENTS]
    stats.unused = [c for c in stats.coverage if c.contents == 0]
    return stats


# --- 書く ---------------------------------------------------------------------


def _n(value: int) -> str:
    return f"{value:,}"


def _size(value: int) -> str:
    """1 MiB 未満は KiB で出す（1 ファイルが「0.0 MiB」になるのを避ける）。"""
    if value < 1048576:
        return f"{value / 1024:.0f} KiB"
    return f"{value / 1048576:.1f} MiB"


def _table(header: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "（該当なし）\n"
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out) + "\n"


def _count_table(rows: list[CountRow], label: str, *, with_documents: bool = True) -> str:
    if with_documents:
        return _table(
            [label, "件数", "この要素を持つ文書"],
            [[r.name, _n(r.items), _n(r.documents)] for r in rows],
        )
    return _table([label, "件数"], [[r.name, _n(r.items)] for r in rows])


def render_card(stats: DataCardStats) -> str:
    """実測値から Markdown を組み立てる。**固定文に数値を書かない**。"""
    # 配布先の ID は `yakkan/export.py` が正本（2 つのデータセットに分けて配る）
    from yakkan.export import HF_REPO_ID, SEARCH_HF_REPO_ID

    scale, search, layout = stats.scale, stats.search, stats.layout
    parts: list[str] = []
    add = parts.append

    add(
        "# データカード — yakkan-synth 合成保険約款データセット\n\n"
        "**このファイルは `yakkan datacard update`（および `yakkan export`）が生成する。"
        "手で編集しない**（CLAUDE.md §0.4-3）。仕様は `docs/data_card.md`、"
        "ファイルの読み方と配布面の要約は `dataset/README.md`（Hugging Face のデータセットカード）。\n\n"
        "数値はすべて `dataset/` の実ファイルを測った結果で、生成し直すたびに更新される。\n"
    )

    add("\n## 1. 概要\n\n")
    add(
        f"日本語の保険約款（やっかん）**{_n(scale.documents)} 文書**（PDF）と、"
        f"その**完全な正解データ**（JSON）を対にした合成データセットである。"
        f"**{_n(scale.contents)} 本**の執筆物（content）を **{_n(scale.styles)} 種**の版面で描き分け、"
        f"**{_n(scale.genres)} 種**のジャンル（genre）・計 **{_n(scale.pages)} ページ**・"
        f"本文 **{_n(scale.chars)} 文字**・QA **{_n(scale.qa_items)} 問**を収める。"
        f"配布版は `manifest.json` の `dataset_version: {stats.dataset_version}`。\n\n"
        "- **登場する保険会社・商品名・ペットネーム・連絡先・様式番号・人物名・金額はすべて架空**"
        "であり、保険商品としての内容は検証されていない（§9・§11）。\n"
        "- 正解 JSON が唯一の真実で、PDF はその決定論的な描画結果である"
        "（JSON → HTML → PDF）。紙面と正解が食い違うことが原理的に起きない。\n"
        f"- 1 文書は表紙を含め **20 ページ以下**（超過は失敗として扱い、`status: failed` で落とす）。"
        f"全 {_n(scale.documents)} 文書のうち検証を通ったもの"
        f"（`status: ready`）は **{_n(scale.ready)} 文書**、不合格は **{_n(scale.failed)} 文書**"
        + (f"、未検証は **{_n(scale.unverified)} 文書**" if scale.unverified else "")
        + "（§10）。\n"
    )

    add("\n## 2. 想定する用途／想定しない用途\n\n")
    add(
        "**想定する用途**（これに合わせて正解を設計した。`docs/evaluation.md` §1）\n\n"
        "1. ページ画像・PDF からのテキスト読み取り（OCR・VLM）の精度評価。\n"
        "2. 章節条項号の階層と別表の抽出（木と、要素の構造内の位置づけ）の評価。\n"
        "3. 表の構造理解（結合セル込みの見た目と、行見出し × 列見出し → 値）と"
        "図の構造理解（ノード・辺・経路）の評価。\n"
        "4. 参照関係の解決（`{ref:}` が指す条項・`{term:}` が指す定義語・`{const:}` の定数）の評価。\n"
        "5. 文書 QA の評価（抽出・参照・計算・場面適用を含む）。\n"
        "6. **レイアウト頑健性**の評価（同じ本文を別の版面で描いた対で、"
        "内容の正解は不変・bbox と読み順だけが変わる）。段組の違いが入るのが約款の特徴である。\n"
        "7. 検索・RAG の評価（パッセージ・クエリ・適合判定の 3 点セット。§7）。\n\n"
        "**想定しない用途**\n\n"
        "- **実務の保険約款としての利用・保険商品の比較・法的な参照。** 条文は読み取り評価のために"
        "書いたダミーで、保険実務・法務の校閲を受けていない。\n"
        "- 実在の約款・実在商品の再現（構造だけを参考にし、文章はすべてオリジナルに書いた。§9）。\n"
        "- 言語モデルの事前学習コーパス（規模が小さく、題材が意図的に偏っている）。\n"
        "- スキャン画像・手書き・印影を含む劣化画像の評価（§11）。\n"
    )

    add("\n## 3. 規模（実測）\n\n")
    add(
        _table(
            ["項目", "実測値"],
            [
                [
                    "文書（PDF）",
                    f"{_n(scale.documents)}（ready {_n(scale.ready)} / failed {_n(scale.failed)}"
                    + (f" / unverified {_n(scale.unverified)}" if scale.unverified else "")
                    + "）",
                ],
                ["content（執筆物）", _n(scale.contents)],
                ["genre（ジャンル）", f"{_n(scale.genres)}（宣言 {_n(stats.declared_genres)}）"],
                ["style（版面）", f"{_n(scale.styles)}（宣言 {_n(stats.declared_styles)}）"],
                [
                    "番号方式",
                    f"{_n(len(stats.numbering_schemes))}（宣言 {_n(stats.declared_schemes)}）",
                ],
                ["ページ", _n(scale.pages)],
                ["ページ画像（PNG）", _n(scale.page_images)],
                ["本文の文字数（`derived.plain_text`）", _n(scale.chars)],
                ["紙面の文字数（`answer.json` のページ本文）", _n(scale.answer_chars)],
                [
                    "表 / セル / 結合セル",
                    f"{_n(scale.tables)} / {_n(scale.table_cells)} / {_n(scale.merged_cells)}",
                ],
                [
                    "図 / ノード / 辺 / 経路",
                    f"{_n(scale.figures)} / {_n(scale.figure_nodes)} / "
                    f"{_n(scale.figure_edges)} / {_n(scale.figure_paths)}",
                ],
                ["算式（`formula`）", _n(scale.formulas)],
                ["参照（`{ref:}` の解決結果）", _n(scale.refs)],
                ["列挙 / 列挙の項目", f"{_n(scale.enumerations)} / {_n(scale.enumeration_items)}"],
                ["定義語 / `{term:}` の出現", f"{_n(scale.defined_terms)} / {_n(scale.term_uses)}"],
                ["定数（`{const:}` で参照する `meta.constants`）", _n(scale.constants)],
                ["脚注（条末）", _n(scale.footnotes)],
                ["目次の項目", _n(scale.toc_entries)],
                ["QA", _n(scale.qa_items)],
                ["要素索引の行（`elements.jsonl`）", _n(scale.elements)],
                [
                    "検索パッセージ（全文書の合計）",
                    f"{_n(scale.passages)}（**別スタイルを含む**。検索コーパスは §7）",
                ],
                ["容量", f"{_size(scale.bytes_total)} / {_n(scale.files_total)} ファイル"],
            ],
        )
    )
    add("\n容量の内訳：\n\n")
    add(
        _table(
            ["種類", "ファイル数", "容量"],
            [[f"`.{s.ext}`", _n(s.files), _size(s.bytes)] for s in scale.sizes],
        )
    )
    add(
        "\n**2 つの文字数は意味が違う。** 「本文の文字数」は `derived.plain_text` の"
        "`without_label` の合計で、**執筆した内容そのもの**（計算した番号ラベルを含まない）。"
        "「紙面の文字数」は `answer.json` の `pages[].text` の合計で、"
        "**表紙・目次（ページ番号つき）・番号ラベルを含む**——いずれも別の要素として描かれるので"
        "`plain_text` には入らない。読み取りの精度（CER）を測る分母は後者である。\n"
    )
    add(f"\n（`{CARD_NAME}` 自身とドットファイルは数えていない。`docs/data_card.md` §4.1）\n")
    if scale.strays:
        add(
            "\n**成果物の一覧（`manifest.json` の `artifacts`）に無いファイルが残っている。**"
            "調査の痕跡であり、配布するなら消す。\n\n"
        )
        add(_table(["ファイル名", "件数"], [[f"`{r.name}`", _n(r.items)] for r in scale.strays]))

    add("\n## 4. 内訳\n\n### 4.1 genre（ジャンル）別\n\n")
    add(
        _table(
            [
                "genre",
                "名称（blueprint の宣言）",
                "content",
                "文書",
                "目標頁",
                "実測頁",
                "本文字数",
                "表",
                "図",
                "QA",
            ],
            [
                [
                    f"`{r.genre}`",
                    r.name,
                    _n(r.contents),
                    _n(r.documents),
                    r.target,
                    f"{r.pages_min}–{r.pages_max}" if r.pages_min != r.pages_max else str(r.pages_min),
                    _n(r.chars),
                    _n(r.tables),
                    _n(r.figures),
                    _n(r.qa_items),
                ]
                for r in stats.genres
            ],
        )
    )
    add(
        "\n**実測頁が目標の範囲を外れることはある**——目標は blueprint の `target_pages` で、"
        "超過は warning、20 ページ超だけが error である（lint L09）。"
        "商品名・会社名は content ごとに違うので、題名は §4.3 の全件表に出す。\n"
    )
    add("\n### 4.2 style（版面）別\n\n")
    add(
        _table(
            ["style_id", "判型", "段組", "文書", "ページ", "PDF に埋め込まれていたフォント"],
            [
                [
                    f"`{r.style_id}`",
                    "／".join(r.page_sizes),
                    "／".join(r.columns),
                    _n(r.documents),
                    _n(r.pages),
                    "、".join(r.fonts) or "（PDF なし）",
                ]
                for r in stats.styles
            ],
        )
    )
    add(
        "\n**同じ content を複数の style で描いた対がレイアウト頑健性の評価に使える。**"
        "本文は同一で、bbox と読み順だけが変わる（§4.3 の `content_id` が同じ行を見る）。\n"
    )
    add("\n### 4.3 文書の全件\n\n")
    add(
        _table(
            ["doc_id", "genre", "題名", "seed", "ページ", "本文字数", "表", "図", "QA", "status"],
            [
                [
                    f"`{r.doc_id}`",
                    f"`{r.genre}`",
                    r.title,
                    str(r.seed),
                    str(r.pages),
                    _n(r.chars),
                    str(r.tables),
                    str(r.figures),
                    str(r.qa_items),
                    r.status,
                ]
                for r in stats.documents
            ],
        )
    )

    add("\n### 4.4 骨格と体裁の覆い\n\n")
    add(
        "実在の約款から抽出した読み取り課題は A〜F の 6 群に整理してある"
        "（`docs/reference_structures.md`）。このうち `source.json` の構造・ブロック・"
        "`meta` から**機械的に分かるもの**を実測で載せる。\n\n"
        "条文型と丸数字型の別は**条ラベルの形**で見る——`jyusetsu`（重要事項説明書）は"
        "blueprint で「条を持たない」と宣言しているが、実装は他のジャンルと同じ "
        '`kind: "article"` のノードを使い、番号方式が「第◯条」ではなく「①」と振るだけである。'
        "**ノード種別では分かれない**（`docs/data_card.md` §4.3）。"
        "**母数が足りないものは §11 が名指しする。**\n\n"
    )
    shape = [c for c in stats.coverage if c.group in ("骨格", "体裁") and c.contents > 0]
    add(
        _table(
            ["分類", "観点", "content", "文書"],
            [[c.group, c.name, _n(c.contents), _n(c.documents)] for c in shape],
        )
    )

    add("\n## 5. 正解の中身\n\n")
    add("### 5.1 構造（ノード種別）\n\n")
    add(_count_table(stats.node_kinds, "`kind`"))
    add(
        "\n`Node` は `title` だけを持ち、**「第１条」などの番号ラベルは持たない**。"
        "ラベルはツリー位置と番号方式から `yakkan build` が計算し、`derived.labels` に入る"
        "（label / title / heading_text / citation を別々に持つので、読み取り側の粒度差を"
        "採点できる。`docs/schema.md` §5）。\n"
    )
    add("\n### 5.2 ブロック種別\n\n")
    add(_count_table(stats.block_types, "`type`"))
    add("\n### 5.3 表の意味種別（`semantic_type`）\n\n")
    add(_count_table(stats.semantic_types, "`semantic_type`"))
    add(
        "\n表は `grid`（結合セル込みの見た目）と `records` / `header_path`（意味）を"
        "**両方**持つ（`docs/schema.md` §5）。`enumeration` / `exclusions` は"
        "「列挙を表として組んだもの」で、表としては採点せず列挙として採点する"
        "（`HITL_TODO.md` H6(a) で承認済み）。\n"
    )
    add("\n### 5.4 図の種別\n\n")
    add(_count_table(stats.figure_kinds, "`kind`"))
    add(
        "\n図は外部のレイアウトエンジンを使わず、JSON の格子座標から決定論的に SVG へ描く。"
        "6 種のどれも `derived.figures[].graph`（共通の nodes / edges）と `paths` に正規化されるので、"
        "種別をまたいで同じ採点ができる。`alt` と `facts` も正解として持つ。\n"
    )
    add("\n### 5.5 QA\n\n")
    add(_count_table(stats.qa_types, "種別", with_documents=False))
    add("\n出所と答えの型：\n\n")
    add(_count_table(stats.qa_sources, "`source`", with_documents=False))
    add("\n")
    add(_count_table(stats.qa_answer_types, "`answer_type`", with_documents=False))
    add(
        "\n`source: auto` は構造から機械生成した問い、`authored` は執筆者（Claude）が書いた問いである。"
        "`apply` 型は**文書に直接書かれていない値**を規定の当てはめで導く問い"
        "（「日額 5,000 円で胃の切除を受けたときの手術保険金はいくらか」→ 別表の倍率を掛けて算出）で、"
        "答えが紙面の文字列にならない（`docs/evaluation.md` §2）。\n"
    )
    add("\n### 5.6 定義語（`{term:}` の解決対象）\n\n")
    add(_count_table(stats.term_kana, "索引見出し（`index_kana`）", with_documents=False))
    add(
        "\n本文は定義語を `{term:<id>}` で書き、build が `defined_terms` の宣言から解決する。"
        "`term_id` は**文書内でしか一意でない**（同じ id が別の文書では別の語を指す）ので、"
        "コーパス全体で索引するときは `doc_id` と組にする（`docs/search_query_plan.md` W3）。\n"
    )
    add("\n### 5.7 番号方式・発行体・体裁の宣言\n\n")
    add(_count_table(stats.numbering_schemes, "`numbering_scheme`（文書数）", with_documents=False))
    add(
        "\n番号方式は「第１条／（２）／①」の振り方の規約で、ジャンルごとに違う"
        "（`nonlife` は項が算用数字、`life` は漢数字、`group` は項が丸数字で第 1 項が無番号、"
        "`jyusetsu` は条の位置に丸数字の小見出しを置く）。"
        "**執筆者はラベルを書かず、build が計算する。**\n\n"
    )
    add(_count_table(stats.issuer_kinds, "発行体の種別（文書数）", with_documents=False))
    add(
        "\n相互会社は「総代会」「社員」など株式会社と語彙が違うので、"
        "`teikan`（定款）では条文の内容そのものが分かれる。\n\n"
    )
    add(_count_table(stats.meta_options, "`meta` の体裁の宣言（文書数）", with_documents=False))

    add("\n## 6. 版面\n\n")
    add(_count_table(layout.page_sizes, "判型（文書数）", with_documents=False))
    add("\n")
    add(_count_table(layout.columns, "段組（ページ数）", with_documents=False))
    add(
        "\n**2 段組では 1 つの要素が 2 つの fragment に割れる。** `layout.json` の "
        "`elements[].fragments` は配列で、段の境界は `pages[].columns` と bbox から判定する"
        "（`docs/rendering.md`）。\n\n"
    )
    add("領域別のテキスト行数（`layout.json` の `text_lines[].region`）：\n\n")
    add(_count_table(layout.regions, "region", with_documents=False))
    add(
        "\n`header` / `footer` と繰り返し表頭は PDF のテキスト層に同じ文字列が何度も出るので、"
        "往復比較の前に除いてある（`answer.json` の `pages[].text` は除いた後、"
        "`text_with_furniture` は除く前）。\n"
    )
    add("\n描画環境（正解と紙面の対応はこの組み合わせで決定論になる）：\n\n")
    add(_count_table(layout.renderers, "renderer（文書数）", with_documents=False))
    add("\n")
    add(_count_table(layout.dpi, "PNG の解像度（文書数）", with_documents=False))
    add("\n")
    add(_count_table(layout.embedded_fonts, "PDF に埋め込まれていたフォント（文書数）", with_documents=False))
    add(
        "\n**上は実測**（PDF のフォント資源の `/BaseFont` からサブセット接頭辞を外したもの）。"
        "下は描画に**登録した候補**で、style がこの中から選ぶ——"
        "候補に挙がっているだけのフォントは PDF に埋め込まれない。\n\n"
    )
    add(_count_table(layout.fonts, "描画に登録したフォント（文書数）", with_documents=False))
    add(
        "\n同梱フォント以外が埋め込まれていないことは `yakkan verify` が検査する。"
        "`.ttf`（TrueType 輪郭）を使う——`.otf`（CFF）は pdfplumber では読めるのに "
        "macOS の Preview で本文が描画されない（`docs/gotchas.md`・`docs/decisions.md` 2026-09-26）。\n"
    )

    add("\n## 7. 検索評価セット（`dataset/search/`）\n\n")
    if not search.available:
        add("**未生成。** `uv run yakkan export` で作る。\n")
    else:
        add(
            "**この評価セットは Hugging Face では文書本体とは別のデータセットとして配る**"
            f"（`{SEARCH_HF_REPO_ID}`。2026-10-08 決定・`docs/distribution.md` §1）。"
            "ローカルの置き場所は `dataset/search/` のままで、"
            "そのディレクトリがそのまま別リポジトリの直下になる"
            "（カード・LICENSE・`SHA256SUMS` も `yakkan export` がそこに書く）。\n\n"
        )
        add(
            _table(
                ["項目", "実測値"],
                [
                    ["パッセージ", _n(search.passages)],
                    ["クエリ", _n(search.queries)],
                    ["適合判定（qrels）", _n(search.qrels)],
                    [
                        "コーパスの文書",
                        f"{_n(search.corpus_documents)} 文書 / {_n(search.corpus_contents)} content"
                        "（**content ごとに 1 スタイル**。別スタイルは本文が同一で重複になる）",
                    ],
                    ["`filters` を持つクエリ", _n(search.with_filters)],
                    [
                        "`hard_negatives` を持つクエリ / 宣言された非適合",
                        f"{_n(search.with_hard_negatives)} / {_n(search.hard_negatives)}",
                    ],
                    ["gold が空集合のクエリ（`no_answer`）", _n(search.no_answer)],
                ],
            )
        )
        add("\n")
        add(_count_table(search.passage_kinds, "パッセージの種別", with_documents=False))
        add("\n")
        add(_count_table(search.query_kinds, "クエリの種別", with_documents=False))
        add("\n")
        add(
            _count_table(
                search.grades, "適合判定（grade 2 = 答えがある / 1 = 関連する）", with_documents=False
            )
        )
        add(
            "\n**約款は文書をまたいでほぼ同じ条文を持つ**（告知義務・重大事由による解除・準拠法ほか）。"
            "そのため「告知義務」のような語を素のクエリにすると**どの文書を返すべきかが決まらない**。"
            "この評価セットは語の出現文書数で振り分けてこれを避けている——"
            "コーパス中 1 文書だけが持つ語・見出しは素の項目検索（`term` / `heading`）、"
            "複数文書にあるものは絞り込み（`scoped` はクエリ文に、`filtered` は `filters` に）、"
            "広く使われる語は網羅クエリ（`enumeration`）。"
            "設計の経緯は `docs/search_query_design.md`、実測は `docs/search_query_plan.md`。\n"
        )
        examples = "（" + "・".join(f"「{q}」" for q in search.truncated_examples) + "）"
        add(
            f"\n- **grade 1 は 1 クエリ {_n(search.related_cap)} 件で打ち切ってある。** 打ち切られたクエリは "
            f"**{_n(search.truncated)} 件**{examples if search.truncated_examples else ''}で、"
            f"qrels に出なかった grade 1 は **{_n(search.truncated_items)} 件**。"
            "打ち切ると qrels に出ないので評価上は非適合と同じ扱いになる。"
            "**この件数で Recall@k を解釈しない**（`dataset/search/README.md`）。\n"
        )
        add(
            "- **`filters` はクエリの一部である。** メタデータを索引しない検索器は `filtered` を"
            "構造的に解けないので、**何を索引したかを `search_run.json` の `index_setting` に申告する**"
            "（`docs/evaluation.md` §2）。\n"
            "- **素朴な検索器 3 系統のベースライン**は `dataset/search/README.md`"
            "（検索評価セット側のカード）に実測値で入っている。"
            "「この評価セットが簡単すぎないか」はそこで確認する。\n"
        )
        if search.missing_contents:
            add(
                f"- **警告：検索コーパスに入っていない content が {_n(len(search.missing_contents))} 件ある**"
                f"（{'・'.join(f'`{c}`' for c in search.missing_contents)}）。"
                "文書を足したあと `uv run yakkan export` を回していない可能性がある。\n"
            )

    add("\n## 8. どう作ったか\n\n")
    add(
        "1. `blueprints/<genre>.yaml` が骨組み・必須要素・分量・番号方式・バリエーションを宣言し、"
        "`yakkan scaffold` が執筆用スケルトンを生成する。\n"
        "2. 条文本文・定義・表の中身・図のノード・脚注・欄外注・`alt`／`facts`・執筆 QA は "
        "**Claude Code のセッション内で執筆**した。**外部の LLM API は使っていない。**\n"
        "3. `yakkan lint` が整合性規則（L00–L19。番号ラベルの直書き禁止・参照切れ・表と図の構造・"
        "数値整合・定義語・文体・類似度ほか）で検査する。\n"
        "4. `yakkan build` が番号・条項間参照・定義語・定数・目次・構造内の位置づけを**計算して** "
        "`derived` に入れる（執筆者は番号を書かない。CLAUDE.md §2-2）。\n"
        "5. `yakkan render` が Jinja2 → HTML → WeasyPrint → PDF を描画し、"
        "PDF から bbox・読み順・ページ別テキストを**逆に測って** `layout.json` / `answer.json` にする。\n"
        "6. `yakkan verify` がページ数上限・フォント埋め込み・テキスト往復一致・目次のページ一致・"
        "要素の欠落・はみ出し・重なり・決定論を検査する（V01–V10）。\n"
        "7. `yakkan qa` が自動 QA を生成し、`yakkan export` が `elements.jsonl` と"
        "検索評価セットを作る。\n\n"
    )
    add(
        "**決定論**：同じ content・style・seed・同じ依存版なら、同じ JSON と同じテキスト層の PDF が出る"
        "（PDF のメタデータ日時も固定値）。使った renderer は上の §6 のとおりで、"
        "版を固定している。seed は文書ごとに固定（§4.3 の表）。\n"
    )

    add("\n## 9. 架空性・転載しないこと\n\n")
    add(
        "- **完全架空**：保険会社名・商品名・ペットネーム・連絡先・URL・様式番号・人物名・"
        "金額・等級はすべて架空である。URL は `example.jp` / `example.co.jp` / `example.com` のみ、"
        "電話番号はゼロ埋め（`0120-000-000` 形式）のみを使い、"
        "`yakkan/lint/denylist.txt` で実在の保険会社名を検出して lint で落とす（L08）。\n"
        "- **転載していない**：実在の約款から参考にしたのは**構造・要素の種類・レイアウト慣行だけ**で、"
        "文章はすべてオリジナルに書いた。参考文書そのものはリポジトリに入れていない"
        "（出典 URL の一覧のみ。`docs/reference_structures.md` §3.2）。\n"
        "- **実在の法令・官公庁は名称のみ**を引用し、**法令の条番号は書かない**"
        "（架空の条文に実在の条番号を結びつけないため。CLAUDE.md §15）。\n"
        "- 同一ジャンルの content は題材を変えて書き、`yakkan lint --similarity` が"
        "文単位の重複率 30% 超を警告する（L15）。\n\n"
    )
    add(f"各文書の奥付に入れた断り書き（{_n(len(stats.disclaimers))} 種）：\n\n")
    add("\n".join(f"> {text}" for text in stats.disclaimers) + "\n")

    add("\n## 10. 品質保証\n\n")
    add(
        f"- **`status: ready` が {_n(scale.ready)} / {_n(scale.documents)} 文書。** status は"
        "自己申告ではなく `yakkan verify` の結果で決まる（`manifest.json` の `errors` に理由が入る）。\n"
        "- `yakkan manifest check` が `manifest.json` と実ファイル（checksum・ページ数・QA 数・"
        "成果物の有無・ページ画像の枚数）の一致を検査する。\n"
        "- `yakkan eval --oracle` は、正解そのものを予測として入れたとき全指標が満点になることを"
        "確かめる（採点ハーネス自身の検査）。`--misread` で現実の読み取り誤りを模して崩すと、"
        "崩しの強さに応じて単調に悪化する。\n"
        "- 検証は規則ベースの素朴な読み取り器 → VLM（Claude 自身がページ画像を読む）→ "
        "**構築経緯を知らない盲検サブエージェント**の順に厚くしてある。"
        "盲検で見つかった欠陥（列挙用の表に caption が付いていた 9 箇所）は lint L18 を新設して"
        "塞いだ（`docs/remaining_issues.md` Z1〜Z3）。\n"
        "- 全ページの PNG を人が目視する手順（`yakkan review`）を、新しい genre・style の初回に必ず通す。"
        "**lint と verify が通っても版面は崩れうる**——段またぎ要素があると WeasyPrint は"
        "それ以降の内容を黙って捨てる実例があった（CLAUDE.md §14）。\n"
    )
    failed = [d for d in stats.documents if d.status == "failed"]
    if scale.unverified:
        add(
            f"\n**{_n(scale.unverified)} 文書は `status: unverified`。** "
            "`yakkan manifest update --no-verify` で作った manifest には verify の結果が入らない。"
            "合否を知るには `--verify` 付きで作り直す。\n"
        )
    if failed:
        add(
            f"\n**不合格の {_n(len(failed))} 文書と、その理由**（`manifest.json` の `errors` のまま）。"
            "失敗痕跡を残す挙動は意図的で、調査に使う（`TASK.md` §3）。\n\n"
        )
        add(
            _table(
                ["doc_id", "status", "理由"],
                [
                    [f"`{d.doc_id}`", d.status, "；".join(e.splitlines()[0] for e in d.errors) or "（不明）"]
                    for d in failed
                ],
            )
        )

    add("\n## 11. 制限と既知の偏り\n\n")
    add(
        "**設計上の制限**（意図して外した。CLAUDE.md §1・§15）\n\n"
        "- 日本語・横書きのみ。**縦書きは対象外**（WeasyPrint が非対応で、`transform` 回転も"
        "字がセルの外に出るため採らない）。**ルビも作らない**（ルビとして組まれず読みが"
        "テキスト層に混ざる。`scripts/probe_ruby.py` で実測）。\n"
        "- PDF はデジタル生成であり、**スキャン劣化・傾き・影・手書き・印影を含まない**。"
        "紙を撮った画像での精度はこのデータでは測れない。\n"
        "- **tagged PDF ではない**（構造情報を PDF 側に持たせていない。正解は JSON 側にある）。\n"
        "- 実在約款の体裁 3 類型のうち、**素組み（F1）と標準（F2）だけを再現**し、"
        "解説冊子（F3）のイラストは作らない（`docs/reference_structures.md`）。\n"
        "- 保険実務・法務の校閲を受けていない。**条文の妥当性・網羅性・商品設計の整合は保証しない。**\n"
        "- 題材・会社・商品・金額は genre ごとに作ってあるが、**実際の保険商品の分布を模していない**"
        "（商品種別・保険金額・引受条件の偏りを統計的に再現する設計ではない）。\n\n"
    )
    add(
        f"**母数の小さい観点**（覆っている content が {MIN_CONTENTS} 本未満。"
        "この観点だけで精度を語らない）\n\n"
    )
    thin_main = [c for c in stats.thin if c.group != "宣言"]
    thin_decl = [c for c in stats.thin if c.group == "宣言"]
    add(
        _table(
            ["分類", "観点", "content", "文書"],
            [[c.group, c.name, _n(c.contents), _n(c.documents)] for c in thin_main],
        )
    )
    if thin_decl:
        add(
            f"\n宣言（genre・番号方式・style・体裁の指定）のうち {MIN_CONTENTS} 本未満の content しか"
            f"使っていないものは {_n(len(thin_decl))} 件ある："
            + "、".join(f"{c.name}（{c.contents} content）" for c in thin_decl)
            + "。\n"
        )
    add("\n**宣言はあるが使っている文書が 0 の観点**（実装が検証されていない）\n\n")
    add(_table(["分類", "観点"], [[c.group, c.name] for c in stats.unused]))
    add(
        "\nこの 2 つの表は `dataset/` の実測から毎回作り直すので、"
        "文書を足して観点が増えれば自動的に消える（`docs/data_card.md` §4.3）。\n"
    )

    add("\n## 12. ライセンスと配布\n\n")
    embedded = [r.name for r in layout.embedded_fonts]
    registered = [r.name for r in layout.fonts]
    families = {name.removesuffix("-Bold").replace("-", " ") for name in embedded}
    unused_fonts = [name for name in registered if name not in families]
    add(
        "- **生成物（PDF・JSON・PNG）の配布条件は CC BY 4.0**（`TASK.md` T11 で 2026-10-05 に決定）。"
        "本文は `dataset/LICENSE`、要約は `dataset/README.md` の「ライセンス」節にある"
        "（検索評価セットは別リポジトリなので `dataset/search/` にも同じ条件の控えを置く）。"
        "リポジトリの `pyproject.toml` が宣言する `Proprietary` は**パッケージ（コード）の宣言**であって、"
        "データセットの再配布条件ではない。\n"
        "- **AI モデルの学習・蒸留には使えない。** 本文・QA・図の説明は Claude Code セッション内で "
        "Claude（Anthropic）が書いた Output であり、Anthropic Usage Policy が「入力と出力を "
        "AI モデルの学習（model scraping・model distillation を含む）に用いること」を"
        "事前許可なしに禁じている（https://www.anthropic.com/legal/aup）。"
        "**評価・ベンチマーク・テストフィクスチャ・推論時の検索コーパスとしての利用は対象外**で、"
        "除かれるのはモデルの重みを更新する用途だけである。"
        "これは**告知であってライセンス条件ではない**——CC BY 4.0 第 2 条(a)(5)(B)が下流への"
        "追加制限を禁じているため、CC BY の付与条件としては書けない。"
        "文面の正本は `yakkan/export.py` の `LICENSE_NOTICE` と `CARD`（`docs/distribution.md` §7）。\n"
        "- 配布先は Hugging Face と GitHub と決まっている（`TASK.md` T7）が、**実行は人間が行う**。"
        f"Hugging Face では **2 つのデータセット**に分けて上げる——文書本体 `{HF_REPO_ID}` と"
        f"検索評価セット `{SEARCH_HF_REPO_ID}`（`docs/distribution.md` §4）。\n"
    )
    if embedded:
        add(
            f"- **PDF にはフォントが埋め込まれている**（実測 {_n(len(embedded))} 種："
            + "、".join(f"`{n}`" for n in embedded)
            + "）。"
        )
        if any(n.startswith("Noto") for n in embedded):
            add("Noto 系は **SIL Open Font License 1.1**。")
        if any(n.startswith("IPAex") for n in embedded):
            add("IPAex 系は **IPA フォントライセンス v1.0**。")
        add("ライセンス全文は `assets/fonts/` に同梱してある。**PDF を再配布するときはこれに従う。**\n")
    if unused_fonts:
        add(
            "- 同梱しているが現行コーパスの PDF には入っていないフォント："
            + "、".join(f"`{n}`" for n in unused_fonts)
            + "（描画の候補として登録してあるだけ。§6）。\n"
        )
    add(
        "- **PNG はラスタライズ済み**でフォントのデータを含まない。`source.json` / `layout.json` / "
        "`answer.json` / `qa.json` / `elements.jsonl` / `search/*.jsonl` も同様で、"
        "フォントのライセンスは関わらない。\n"
        "- 参考にした実在の約款は**一切含まれていない**（§9）。\n"
    )

    add("\n## 13. このカードの更新\n\n")
    add(
        "```\n"
        "uv run yakkan datacard update    # 書き出す（dataset/ を測るだけ。再描画は不要）\n"
        "uv run yakkan datacard check     # 書き換えずに古くなっていないかを見る（古ければ終了コード 1）\n"
        "uv run yakkan export             # 検索評価セットと README と各カードをまとめて作り直す\n"
        "make check                       # ruff + pytest + manifest の鮮度 + このカードの鮮度\n"
        "```\n\n"
        "文書を足したら `yakkan export`（または `make batch`）で更新される。更新を忘れると "
        "`make check` が赤くなる。仕様と節の追加手順は `docs/data_card.md`。\n"
    )
    return "".join(parts)


def write_card(dataset_dir: Path, stats: DataCardStats | None = None) -> Path:
    """`dataset/data-card.md` を書き出す。"""
    stats = stats if stats is not None else collect(dataset_dir)
    path = dataset_dir / CARD_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_card(stats), encoding="utf-8")
    return path


def check(dataset_dir: Path) -> list[str]:
    """カードが現在の `dataset/` と合っているかを見る（**書き換えない**）。

    `manifest check` と同じ流儀。食い違いの説明を返す。空なら一致している。
    """
    path = dataset_dir / CARD_NAME
    if not (dataset_dir / "manifest.json").is_file():
        return [f"{dataset_dir}/manifest.json が無い（`yakkan manifest update` を実行する）"]
    fresh = render_card(collect(dataset_dir))
    if not path.is_file():
        return [f"{path} が無い（`yakkan datacard update` を実行する）"]
    current = path.read_text(encoding="utf-8")
    if current == fresh:
        return []
    problems = [f"{path} が現在の dataset/ と一致しない"]
    current_lines, fresh_lines = current.splitlines(), fresh.splitlines()
    if len(current_lines) != len(fresh_lines):
        problems.append(f"行数が違う（{len(current_lines)} → {len(fresh_lines)}）")
    diff = [
        f"{i + 1} 行目: {was.strip()[:60]} → {now.strip()[:60]}"
        for i, (was, now) in enumerate(zip(current_lines, fresh_lines, strict=False))
        if was != now
    ]
    problems += diff[:5]
    if len(diff) > 5:
        problems.append(f"（ほか {len(diff) - 5} 行）")
    return problems
