"""`dataset/data-card.md` の生成（仕様は `docs/data_card.md`）。

    uv run keiyaku datacard update   # 書き出す
    uv run keiyaku datacard check    # 書き換えずに鮮度を見る

**カードに出る数値はすべて `dataset/` の実ファイルから測る。** 仕様書や過去の記憶を
数値の出典にしない（`TASK.md` §1.2 の検索評価セットの数は実際に古くなっていた——
クエリ 778 と書いてあったが実測 1,170）。固定文字列に統計値を焼き込まない
（`docs/decisions.md` 105・131 の再発防止）。

生成は決定論。`datetime.now()` を入れず、**自分自身のファイルサイズは数えない**
（数えると書き出すたびに数が動き、鮮度検査が収束しない）。
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Iterator
from pathlib import Path
from typing import Literal, get_args

from pydantic import Field

from keiyaku.models import BoxStyle, Model, Node, SemanticType, Source

#: 生成するファイル名。`dataset/` 直下に置く
CARD_NAME = "data-card.md"
#: 「母数が足りない」と判断する content 数の閾値（`docs/data_card.md` §4.3）
MIN_CONTENTS = 3
#: 容量の集計から外すファイル名（自分自身を数えると鮮度検査が収束しない）。
#: **公開用の包み（`keiyaku publish` の生成物）も外す**——カードは「データの中身」を測るもので、
#: かつ相互参照で収束しなくなる（カードのサイズ → SHA256SUMS → カード…。`docs/publishing.md` §3）。
SIZE_EXCLUDE = frozenset({CARD_NAME, "README.md", "SHA256SUMS", "LICENSE"})
#: 容量の集計から外すディレクトリ（`dataset/` 直下からの相対名）。理由は `SIZE_EXCLUDE` と同じ
SIZE_EXCLUDE_DIRS = frozenset({"views", "licenses"})
#: 図の種別（`Diagram` の判別子）。宣言されているが使われていない種別を挙げるために使う
FIGURE_KINDS: tuple[str, ...] = ("flowchart", "tree", "steps", "timeline", "annotated_mock", "matrix")
#: 観点の分類。カードの並び順もこの順
CoverageGroup = Literal["骨格", "体裁", "表の意味種別", "図の種別", "宣言"]


# --- 統計のモデル -------------------------------------------------------------


class ExtSize(Model):
    """拡張子ごとの容量。"""

    ext: str
    files: int
    bytes: int


class Scale(Model):
    """コーパス全体の規模。"""

    documents: int = 0
    ready: int = 0
    failed: int = 0
    contents: int = 0
    doctypes: int = 0
    styles: int = 0
    pages: int = 0
    page_images: int = 0
    #: `derived.plain_text` の文字数（ラベルを除く本文）
    chars: int = 0
    #: `answer.json` のページ本文の文字数（繰り返し表頭を除いた紙面の文字）
    answer_chars: int = 0
    tables: int = 0
    table_cells: int = 0
    figures: int = 0
    figure_nodes: int = 0
    figure_edges: int = 0
    figure_paths: int = 0
    refs: int = 0
    footnotes: int = 0
    defined_terms: int = 0
    constants: int = 0
    enumerations: int = 0
    enumeration_items: int = 0
    party_uses: int = 0
    qa_items: int = 0
    elements: int = 0
    passages: int = 0
    sizes: list[ExtSize] = Field(default_factory=list)

    @property
    def bytes_total(self) -> int:
        return sum(s.bytes for s in self.sizes)

    @property
    def files_total(self) -> int:
        return sum(s.files for s in self.sizes)


class DoctypeRow(Model):
    doctype: str
    titles: list[str] = Field(default_factory=list)
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
    #: その style の PDF に**実際に埋め込まれていた**フォント（`layout.renderer.fonts` は
    #: 描画に登録した候補の一覧で、使われたものとは違う）
    fonts: list[str] = Field(default_factory=list)


class DocRow(Model):
    doc_id: str
    content_id: str
    doctype: str
    style_id: str
    title: str
    seed: int
    pages: int
    chars: int
    tables: int
    figures: int
    qa_items: int
    status: str


class CountRow(Model):
    """「名前 → 件数」の 1 行。`documents` は出現した文書数、`items` は総件数。"""

    name: str
    items: int = 0
    documents: int = 0
    contents: int = 0


class SearchStats(Model):
    passages: int = 0
    queries: int = 0
    qrels: int = 0
    corpus_documents: int = 0
    corpus_contents: int = 0
    passage_kinds: list[CountRow] = Field(default_factory=list)
    query_kinds: list[CountRow] = Field(default_factory=list)
    grades: list[CountRow] = Field(default_factory=list)
    truncated: int = 0
    truncated_examples: list[str] = Field(default_factory=list)
    #: grade 1 を 1 クエリ何件で打ち切るか（`keiyaku.search_set.MAX_RELATED`）。
    #: **ここも焼き込まない**——実装の定数を読む
    related_cap: int = 0
    #: `search/` に出てこない content（文書を足して `keiyaku export` を回していない）
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
    note: str = ""


class DataCardStats(Model):
    """カードに出すすべての実測値。**カードの本文はここから組み立てる**。"""

    scale: Scale = Field(default_factory=Scale)
    doctypes: list[DoctypeRow] = Field(default_factory=list)
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
    #: 当事者の呼称（「甲」「乙」「事業主」…）の出現文書数
    party_aliases: list[CountRow] = Field(default_factory=list)
    #: 1 文書あたりの当事者数の分布
    parties_per_doc: list[CountRow] = Field(default_factory=list)
    search: SearchStats = Field(default_factory=SearchStats)
    layout: LayoutStats = Field(default_factory=LayoutStats)
    coverage: list[Coverage] = Field(default_factory=list)
    #: 覆っている content が `MIN_CONTENTS` 未満（0 は除く）
    thin: list[Coverage] = Field(default_factory=list)
    #: 宣言はあるが使っている content が 0
    unused: list[Coverage] = Field(default_factory=list)
    disclaimers: list[str] = Field(default_factory=list)
    #: 宣言の総数（`blueprints/` `numbering/` `styles/`）
    declared_doctypes: int = 0
    declared_schemes: int = 0
    declared_styles: int = 0


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
        if path.relative_to(dataset_dir).parts[0] in SIZE_EXCLUDE_DIRS:
            continue
        ext = path.suffix.lstrip(".") or "(拡張子なし)"
        files[ext] += 1
        size[ext] += path.stat().st_size
    return [
        ExtSize(ext=ext, files=files[ext], bytes=total)
        for ext, total in sorted(size.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def embedded_fonts(pdf_path: Path) -> list[str]:
    """PDF に**実際に埋め込まれていた**フォント名（サブセット接頭辞を外したもの）。

    `layout.renderer.fonts` は描画に登録した候補の一覧であって、使われたものではない
    （明朝の style でも PDF に入るのは Noto Serif JP だけ）。フォントの別は OCR の
    精度に直接効くので、候補ではなく実測を載せる。PDF が無ければ空を返す。
    """
    if not pdf_path.is_file():
        return []
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        names = {char["fontname"].split("+")[-1] for page in pdf.pages for char in page.chars}
    return sorted(names)


def _features(source: Source) -> set[tuple[str, str]]:
    """1 文書が覆っている観点の集合（`docs/data_card.md` §4.3）。"""
    nodes = (
        list(_walk(source.body)) + list(_walk(source.appendices)) + list(_walk(source.back_matter.signature))
    )
    kinds = {node.kind for node in nodes}
    blocks = list(_blocks([b for node in nodes for b in node.blocks]))
    blocks += list(_blocks(source.front_matter.preface))
    blocks += list(_blocks(source.back_matter.colophon))
    blocks += list(_blocks(source.back_matter.contact))
    types = {getattr(b, "type", "") for b in blocks}
    meta = source.meta

    article_labels = [
        label.label for label in source.derived.labels.values() if label.kind == "article" and label.label
    ]
    article_numbered = any(label.startswith("第") for label in article_labels)

    found: set[tuple[str, str]] = set()
    for name, ok in (
        ("頭書", "head_matter" in kinds),
        ("章立て", "chapter" in kinds),
        ("附則", "supplement" in kinds),
        ("別紙・別表・様式", "appendix" in kinds),
        ("前文", "preamble" in kinds),
        ("記名押印欄", "signature" in kinds),
        ("細目（号より下）", bool({"subitem", "subsubitem"} & kinds)),
        # 条文型 / 様式型の別は**条ラベルの形**で決まる。`kind: "article"` の有無では決まらない——
        # 様式型（労働条件通知書）も `article` ノードを使い、番号方式が「（１）」と振るだけである
        ("条文型（条を「第◯条」で番号する）", article_numbered),
        ("様式型（条番号を持たない記入欄中心）", bool(article_labels) and not article_numbered),
    ):
        if ok:
            found.add(("骨格", name))
    for name, ok in (
        ("目次", source.derived.toc != []),
        ("逐条解説", "commentary" in types),
        ("脚注", bool(source.derived.footnote_index)),
        ("改定履歴", "revision_history" in types),
        ("数式", "formula" in types),
        ("当事者 3 者以上", len(meta.parties) >= 3),
        ("収入印紙欄", meta.stamp_duty),
        ("番号の例外（number_override）", any(n.number_override for n in nodes)),
        (
            "結合セル",
            any(getattr(c, "merged_into", None) for b in blocks for r in getattr(b, "grid", []) for c in r),
        ),
    ):
        if ok:
            found.add(("体裁", name))
    for style in get_args(BoxStyle):
        if any(getattr(b, "type", "") == "box" and getattr(b, "style", "") == style for b in blocks):
            found.add(("体裁", f"枠（{style}）"))
    for block in blocks:
        if getattr(block, "type", "") == "table":
            found.add(("表の意味種別", block.semantic_type))
        if getattr(block, "type", "") == "figure":
            found.add(("図の種別", block.diagram.kind))
    found.add(("宣言", f"doctype: {source.doctype}"))
    found.add(("宣言", f"numbering: {meta.numbering_scheme}"))
    found.add(("宣言", f"digit_style: {meta.digit_style}"))
    found.add(("宣言", f"article_heading: {meta.article_heading}"))
    found.add(("宣言", f"caption_numbering: {meta.caption_numbering}"))
    return found


def _universe(doctypes: Iterable[str], schemes: Iterable[str], styles: Iterable[str]) -> set[tuple[str, str]]:
    """「宣言されている観点」の全体。使用 0 のものを挙げるために要る。"""
    all_keys: set[tuple[str, str]] = {("表の意味種別", s) for s in get_args(SemanticType)}
    all_keys |= {("図の種別", k) for k in FIGURE_KINDS}
    all_keys |= {("宣言", f"doctype: {d}") for d in doctypes}
    all_keys |= {("宣言", f"numbering: {s}") for s in schemes}
    all_keys |= {("宣言", f"style: {s}") for s in styles}
    return all_keys


def _search(dataset_dir: Path, contents: set[str]) -> SearchStats:
    from keiyaku.search_set import MAX_RELATED

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
    kinds = Counter(str(p.get("kind", "?")) for p in passages)
    stats.passage_kinds = _rows(kinds, Counter(), Counter())
    stats.query_kinds = _rows(Counter(str(q.get("kind", "?")) for q in queries), Counter(), Counter())
    stats.grades = _rows(Counter(f"grade {r.get('grade')}" for r in qrels), Counter(), Counter())
    truncated = [q for q in queries if q.get("related_truncated")]
    stats.truncated = len(truncated)
    stats.truncated_examples = [str(q.get("query", "")) for q in truncated[:3]]
    return stats


def collect(dataset_dir: Path) -> DataCardStats:
    """`dataset/` を走査して実測値を集める（**書き出しはしない**）。"""
    from keiyaku.blueprints import available_doctypes
    from keiyaku.doctypes import available_schemes
    from keiyaku.manifest import MANIFEST_NAME, Manifest
    from keiyaku.models import Layout
    from keiyaku.styles import available_styles

    stats = DataCardStats()
    manifest_path = dataset_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        return stats
    manifest = Manifest.model_validate_json(manifest_path.read_text(encoding="utf-8"))

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
    aliases: Counter[str] = Counter()
    alias_docs: Counter[str] = Counter()
    parties_per_doc: Counter[str] = Counter()
    feature_docs: Counter[tuple[str, str]] = Counter()
    feature_contents: dict[tuple[str, str], set[str]] = {}
    by_doctype: dict[str, DoctypeRow] = {}
    doctype_contents: dict[str, set[str]] = {}
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

        nodes = (
            list(_walk(source.body))
            + list(_walk(source.appendices))
            + list(_walk(source.back_matter.signature))
        )
        for node in nodes:
            node_kinds[node.kind] += 1
        for kind in {n.kind for n in nodes}:
            node_docs[kind] += 1
        blocks = list(_blocks([b for node in nodes for b in node.blocks]))
        blocks += list(_blocks(source.front_matter.preface))
        blocks += list(_blocks(source.back_matter.colophon))
        blocks += list(_blocks(source.back_matter.contact))
        for block in blocks:
            block_types[getattr(block, "type", "?")] += 1
            if getattr(block, "type", "") == "table":
                semantic[block.semantic_type] += 1
                stats.scale.table_cells += sum(len(row) for row in block.grid)
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
        scale.defined_terms += len(source.defined_terms)
        scale.constants += len(source.meta.constants)
        scale.enumerations += len(derived.enumerations)
        scale.enumeration_items += sum(len(e.items) for e in derived.enumerations)
        scale.party_uses += len(derived.party_uses)
        for figure in derived.figures.values():
            scale.figure_nodes += len(figure.graph.nodes)
            scale.figure_edges += len(figure.graph.edges)
            scale.figure_paths += len(figure.paths)

        answer_path = doc_dir / "answer.json"
        if answer_path.is_file():
            answer = json.loads(answer_path.read_text(encoding="utf-8"))
            scale.answer_chars += sum(int(page.get("chars", 0)) for page in answer.get("pages", []))
        for name, attr in (("elements", "elements"), ("passages", "passages")):
            path = doc_dir / f"{name}.jsonl"
            if path.is_file():
                lines = sum(1 for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
                setattr(scale, attr, getattr(scale, attr) + lines)

        qa_path = doc_dir / "qa.json"
        if qa_path.is_file():
            for item in json.loads(qa_path.read_text(encoding="utf-8")).get("items", []):
                qa_types[str(item.get("type", "?"))] += 1
                qa_sources[str(item.get("source", "?"))] += 1
                qa_answers[str(item.get("answer_type", "?"))] += 1

        schemes[source.meta.numbering_scheme] += 1
        parties_per_doc[f"{len(source.meta.parties)} 者"] += 1
        for party in source.meta.parties:
            aliases[party.alias] += 1
            alias_docs[party.alias] += 1

        width, height = layout.page_size_pt
        page_sizes[f"{width:.0f}×{height:.0f} pt（{width * 25.4 / 72:.0f}×{height * 25.4 / 72:.0f} mm）"] += 1
        renderers[f"{layout.renderer.name} {layout.renderer.version}"] += 1
        dpi[f"{layout.dpi_png} dpi"] += 1
        for font in layout.renderer.fonts:
            fonts[font] += 1
        for page in layout.pages:
            columns[f"{page.columns} 段"] += 1
            for line in page.text_lines:
                regions[line.region] += 1

        used = embedded_fonts(doc_dir / "doc.pdf")
        for font in used:
            embedded[font] += 1
        style_fonts.setdefault(entry.style_id, set()).update(used)

        row = by_doctype.setdefault(entry.doctype, DoctypeRow(doctype=entry.doctype))
        row.documents += 1
        row.chars += entry.chars
        row.tables += entry.tables
        row.figures += entry.figures
        row.qa_items += entry.qa_items
        row.pages_min = entry.pages if row.pages_min == 0 else min(row.pages_min, entry.pages)
        row.pages_max = max(row.pages_max, entry.pages)
        doctype_contents.setdefault(entry.doctype, set()).add(entry.content_id)
        style = by_style.setdefault(entry.style_id, StyleRow(style_id=entry.style_id))
        style.documents += 1
        style.pages += entry.pages

        stats.documents.append(
            DocRow(
                doc_id=entry.doc_id,
                content_id=entry.content_id,
                doctype=entry.doctype,
                style_id=entry.style_id,
                title=source.meta.title,
                seed=entry.seed,
                pages=entry.pages,
                chars=entry.chars,
                tables=entry.tables,
                figures=entry.figures,
                qa_items=entry.qa_items,
                status=entry.status,
            )
        )

    scale = stats.scale
    scale.documents = len(manifest.documents)
    scale.ready = sum(1 for d in manifest.documents if d.status == "ready")
    scale.failed = sum(1 for d in manifest.documents if d.status != "ready")
    scale.contents = len(contents)
    scale.doctypes = len(by_doctype)
    scale.styles = len(by_style)
    scale.sizes = _sizes(dataset_dir)

    for doctype, row in by_doctype.items():
        row.contents = len(doctype_contents[doctype])
        row.titles = sorted({titles[c] for c in doctype_contents[doctype]})
    stats.doctypes = sorted(by_doctype.values(), key=lambda r: r.doctype)
    for style_id, style_row in by_style.items():
        style_row.fonts = sorted(style_fonts.get(style_id, set()))
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
    stats.party_aliases = _rows(aliases, alias_docs, Counter())
    stats.parties_per_doc = _rows(parties_per_doc, Counter(), Counter())
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

    doctypes, schemes, styles = available_doctypes(), available_schemes(), available_styles()
    stats.declared_doctypes, stats.declared_schemes, stats.declared_styles = (
        len(doctypes),
        len(schemes),
        len(styles),
    )
    seen = {key: len(values) for key, values in feature_contents.items()}
    for style_id, style_row in by_style.items():
        key = ("宣言", f"style: {style_id}")
        feature_docs[key] = style_row.documents
        seen[key] = len({d.content_id for d in stats.documents if d.style_id == style_id})
    order = {name: i for i, name in enumerate(get_args(CoverageGroup))}
    keys = set(seen) | _universe(doctypes, schemes, styles)
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
    """1 MiB 未満は KiB で出す（README の 1 ファイルが「0.0 MiB」になるのを避ける）。"""
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


def _license_paragraph() -> str:
    """生成物の配布条件（`specs/publish.yaml` の `license` が正本。AI が決めない）。"""
    from keiyaku.publish import load_spec

    try:
        spec = load_spec()
    except (OSError, ValueError):  # 宣言が無い・壊れている
        spec = None
    if spec is not None and spec.license.decided:
        holder = f"（著作権表示：© {spec.license.year} {spec.license.holder}）" if spec.license.holder else ""
        note = f" {spec.license.note}" if spec.license.note else ""
        return (
            f"- **生成物（PDF・JSON・PNG）は `{spec.license.id}` で配布する**{holder}。"
            f"条件の正本は `specs/publish.yaml`、本文は公開物の `LICENSE`。"
            f"公開先は {spec.hub_url}（`docs/publishing.md`）。{note}\n"
        )
    return (
        "- **生成物（PDF・JSON・PNG）の配布条件は未決**である。リポジトリの `pyproject.toml` は "
        "`Proprietary` を宣言しているが、これは**パッケージ（コード）の宣言**であって、"
        "データセットとしての再配布条件を決めたものではない。配布は人間の決定事項で "
        "`HITL_TODO.md`（H13）に起票してある。**決定が入るまで外部配布しない。**"
        "公開の準備（カード・views・ライセンスの同梱）は `keiyaku publish` が済ませてあり、"
        "`specs/publish.yaml` の `license.id` が決まれば出せる（`docs/publishing.md`）。\n"
    )


def render_card(stats: DataCardStats) -> str:
    """実測値から Markdown を組み立てる。**固定文に数値を書かない**。"""
    scale, search, layout = stats.scale, stats.search, stats.layout
    parts: list[str] = []
    add = parts.append

    add(
        "# データカード — keiyaku-synth 合成契約書データセット\n\n"
        "**このファイルは `keiyaku datacard update`（および `keiyaku export`）が生成する。"
        "手で編集しない**（CLAUDE.md §0.4-3）。仕様は `docs/data_card.md`、"
        "ファイルの読み方は `dataset/README.md`。\n\n"
        "数値はすべて `dataset/` の実ファイルを測った結果で、生成し直すたびに更新される。\n"
    )

    add("\n## 1. 概要\n\n")
    add(
        f"日本語のビジネス契約書 **{_n(scale.documents)} 文書**（PDF）と、その**完全な正解データ**"
        f"（JSON）を対にした合成データセットである。"
        f"**{_n(scale.contents)} 本**の執筆物（content）を **{_n(scale.styles)} 種**の版面で描き分け、"
        f"**{_n(scale.doctypes)} 種**の契約書種別（doctype）・計 **{_n(scale.pages)} ページ**・"
        f"本文 **{_n(scale.chars)} 文字**・QA **{_n(scale.qa_items)} 問**を収める。\n\n"
        "- **登場する会社・人物・住所・物件・金額・契約書番号はすべて架空**であり、"
        "法的効力を持たない（§9）。\n"
        "- 正解 JSON が唯一の真実で、PDF はその決定論的な描画結果である"
        "（JSON → HTML → PDF）。紙面と正解が食い違うことが原理的に起きない。\n"
        f"- 全 {_n(scale.documents)} 文書のうち検証を通ったもの（`status: ready`）は "
        f"**{_n(scale.ready)} 文書**、不合格は **{_n(scale.failed)} 文書**（§10）。\n"
    )

    add("\n## 2. 想定する用途／想定しない用途\n\n")
    add(
        "**想定する用途**（これに合わせて正解を設計した。`docs/evaluation.md` §1）\n\n"
        "1. ページ画像・PDF からのテキスト読み取り（OCR・VLM）の精度評価。\n"
        "2. 条項構造の抽出（章・条・項・号・別紙の木と、要素の構造内の位置づけ）の評価。\n"
        "3. 表の構造理解（行見出し × 列見出し → 値）と図の構造理解（ノード・辺・経路）の評価。\n"
        "4. 参照関係の解決（`{ref:}` が指す先・定義語・当事者呼称「甲／乙」）の評価。\n"
        "5. 文書 QA の評価（抽出・参照・計算を含む）。\n"
        "6. **レイアウト頑健性**の評価（同じ本文を別の版面で描いた対で、"
        "内容の正解は不変・bbox と読み順だけが変わる）。\n"
        "7. 検索・RAG の評価（パッセージ・クエリ・適合判定の 3 点セット。§7）。\n\n"
        "**想定しない用途**\n\n"
        "- **実務の契約書としての利用・法的な参照**。条項は読み取り評価のために書いたダミーで、"
        "法律専門家の校閲を受けていない。\n"
        "- 実在のひな型・標準契約書の再現（構造だけを参考にし、文章はすべてオリジナルに書いた。§9）。\n"
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
                    f"{_n(scale.documents)}（ready {_n(scale.ready)} / failed {_n(scale.failed)}）",
                ],
                ["content（執筆物）", _n(scale.contents)],
                ["doctype（契約書種別）", f"{_n(scale.doctypes)}（宣言 {_n(stats.declared_doctypes)}）"],
                ["style（版面）", f"{_n(scale.styles)}（宣言 {_n(stats.declared_styles)}）"],
                ["番号方式", f"{_n(len(stats.numbering_schemes))}（宣言 {_n(stats.declared_schemes)}）"],
                ["ページ", _n(scale.pages)],
                ["ページ画像（PNG）", _n(scale.page_images)],
                ["本文の文字数（`derived.plain_text`）", _n(scale.chars)],
                ["紙面の文字数（`answer.json` のページ本文）", _n(scale.answer_chars)],
                ["表 / セル", f"{_n(scale.tables)} / {_n(scale.table_cells)}"],
                [
                    "図 / ノード / 辺 / 経路",
                    f"{_n(scale.figures)} / {_n(scale.figure_nodes)} / "
                    f"{_n(scale.figure_edges)} / {_n(scale.figure_paths)}",
                ],
                ["参照（`{ref:}` の解決結果）", _n(scale.refs)],
                ["列挙 / 列挙の項目", f"{_n(scale.enumerations)} / {_n(scale.enumeration_items)}"],
                ["定義語", _n(scale.defined_terms)],
                ["当事者呼称の出現（`{party:}`）", _n(scale.party_uses)],
                ["定数（`{const:}`）", _n(scale.constants)],
                ["脚注", _n(scale.footnotes)],
                ["QA", _n(scale.qa_items)],
                ["要素索引の行（`elements.jsonl`）", _n(scale.elements)],
                ["検索パッセージ（文書ごとの合計）", _n(scale.passages)],
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
        f"\n（`{CARD_NAME}` 自身・ドットファイル・**公開用の包み**（`README.md`・`SHA256SUMS`・"
        "`LICENSE`・`views/`・`licenses/`）は数えていない。`docs/data_card.md` §4.1）\n"
    )

    add("\n## 4. 内訳\n\n### 4.1 doctype 別\n\n")
    add(
        _table(
            ["doctype", "題名", "content", "文書", "ページ", "本文字数", "表", "図", "QA"],
            [
                [
                    f"`{r.doctype}`",
                    "／".join(r.titles),
                    _n(r.contents),
                    _n(r.documents),
                    f"{r.pages_min}–{r.pages_max}" if r.pages_min != r.pages_max else str(r.pages_min),
                    _n(r.chars),
                    _n(r.tables),
                    _n(r.figures),
                    _n(r.qa_items),
                ]
                for r in stats.doctypes
            ],
        )
    )
    add("\n### 4.2 style（版面）別\n\n")
    add(
        _table(
            ["style_id", "文書", "ページ", "PDF に埋め込まれていたフォント"],
            [
                [f"`{r.style_id}`", _n(r.documents), _n(r.pages), "、".join(r.fonts) or "（PDF なし）"]
                for r in stats.styles
            ],
        )
    )
    add("\n### 4.3 文書の全件\n\n")
    add(
        _table(
            ["doc_id", "doctype", "題名", "seed", "ページ", "本文字数", "表", "図", "QA", "status"],
            [
                [
                    f"`{r.doc_id}`",
                    f"`{r.doctype}`",
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
        "実在の契約書は骨格が 5 類型に落ちる（条文型・頭書型・様式型・約款型・章立ての長文型）。"
        "このうち**条文型・様式型・頭書型・章立て**は `source.json` の構造とラベルから機械的に分かるので"
        "実測を載せる（約款型は条番号が漢数字である点で分かれるので §5.7 の `contract-kanji` を見る）。"
        '条文型と様式型の別は**条ラベルの形**で見る——様式型も `kind: "article"` のノードを使い、'
        "番号方式が「（１）」と振るだけなので、ノード種別では分かれない。"
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
    add("\n### 5.2 ブロック種別\n\n")
    add(_count_table(stats.block_types, "`type`"))
    add("\n### 5.3 表の意味種別（`semantic_type`）\n\n")
    add(_count_table(stats.semantic_types, "`semantic_type`"))
    add("\n### 5.4 図の種別\n\n")
    add(_count_table(stats.figure_kinds, "`kind`"))
    add("\n### 5.5 QA\n\n")
    add(_count_table(stats.qa_types, "種別", with_documents=False))
    add("\n出所と答えの型：\n\n")
    add(_count_table(stats.qa_sources, "`source`", with_documents=False))
    add("\n")
    add(_count_table(stats.qa_answer_types, "`answer_type`", with_documents=False))
    add(
        "\n`source: auto` は構造から機械生成した問い、`authored` は執筆者（Claude）が書いた問いである。"
        "`apply` 型は**文書に直接書かれていない値**を規定の当てはめで導く問いで、"
        "答えが紙面の文字列にならない（`docs/evaluation.md` §2）。\n"
    )

    add("\n### 5.6 当事者（`{party:}` の解決対象）\n\n")
    add(_count_table(stats.parties_per_doc, "1 文書あたりの当事者数（文書数）", with_documents=False))
    add("\n使われている呼称：\n\n")
    add(_count_table(stats.party_aliases, "呼称（それを使う文書数）", with_documents=False))
    add(
        "\n本文は呼称を直書きせず `{party:<key>}` で書き、build が `meta.parties` の宣言から解決する。"
        "**呼称の取り違えは読み取りの典型的な失敗**なので、`meta.parties` が正解となる。\n"
    )
    add("\n### 5.7 番号方式\n\n")
    add(_count_table(stats.numbering_schemes, "`numbering_scheme`（文書数）", with_documents=False))

    add("\n## 6. 版面\n\n")
    add(_count_table(layout.page_sizes, "判型（ページ数）", with_documents=False))
    add("\n")
    add(_count_table(layout.columns, "段組（ページ数）", with_documents=False))
    add("\n領域別のテキスト行数（`layout.json` の `text_lines[].region`）：\n\n")
    add(_count_table(layout.regions, "region", with_documents=False))
    add("\n描画環境（正解と紙面の対応はこの組み合わせで決定論になる）：\n\n")
    add(_count_table(layout.renderers, "renderer（文書数）", with_documents=False))
    add("\n")
    add(_count_table(layout.dpi, "PNG の解像度（文書数）", with_documents=False))
    add("\n")
    add(_count_table(layout.embedded_fonts, "PDF に埋め込まれていたフォント（文書数）", with_documents=False))
    add(
        "\n**上は実測**（PDF のテキスト層のフォント名からサブセット接頭辞を外したもの）。"
        "下は描画に**登録した候補**で、style がこの中から選ぶ——"
        "候補に挙がっているだけのフォントは PDF に埋め込まれない。\n\n"
    )
    add(_count_table(layout.fonts, "描画に登録したフォント（文書数）", with_documents=False))
    add(
        "\n同梱フォント以外が埋め込まれていないことは `keiyaku verify`（V02）が検査する。"
        "`.ttf`（TrueType 輪郭）を使う——`.otf`（CFF）は pdfplumber では読めるのに"
        "macOS の Preview で本文が描画されない（`docs/gotchas.md`）。\n"
    )

    add("\n## 7. 検索評価セット（`dataset/search/`）\n\n")
    if not search.available:
        add("**未生成。** `uv run keiyaku export` で作る。\n")
    else:
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
        examples = "（" + "・".join(f"「{q}」" for q in search.truncated_examples) + "）"
        add(
            f"\n- **grade 1 は 1 クエリ {_n(search.related_cap)} 件で打ち切ってある。** 打ち切られたクエリは "
            f"**{_n(search.truncated)} 件**{examples if search.truncated_examples else ''}。"
            "打ち切ると qrels に出ないので評価上は非適合と同じ扱いになる。"
            "**この件数で Recall@k を解釈しない**（`dataset/README.md`）。\n"
        )
        if search.missing_contents:
            add(
                f"- **警告：検索コーパスに入っていない content が {_n(len(search.missing_contents))} 件ある**"
                f"（{'・'.join(f'`{c}`' for c in search.missing_contents)}）。"
                "文書を足したあと `uv run keiyaku export` を回していない可能性がある。\n"
            )

    add("\n## 8. どう作ったか\n\n")
    add(
        "1. `blueprints/<doctype>.yaml` が骨組み・必須要素・分量・番号方式を宣言し、"
        "`keiyaku scaffold` が執筆用スケルトンを生成する。\n"
        "2. 条文本文・表の中身・図のノード・QA は **Claude Code のセッション内で執筆**した。"
        "**外部の LLM API は使っていない。**\n"
        "3. `keiyaku lint` が整合性規則（L00–L26。番号ラベル・当事者呼称の直書き禁止、"
        "数値整合、定義語、類似度ほか）で検査する。\n"
        "4. `keiyaku build` が番号・参照・当事者呼称・目次・構造内の位置づけを**計算して** "
        "`derived` に入れる（執筆者は番号を書かない）。\n"
        "5. `keiyaku render` が Jinja2 → HTML → PDF を描画し、"
        "PDF から bbox・読み順・ページ別テキストを**逆に測って** `layout.json` / `answer.json` にする。\n"
        "6. `keiyaku verify` がページ数上限・フォント埋め込み・テキスト往復一致・要素の欠落・"
        "はみ出し・記名欄と当事者の一致などを検査する。\n"
        "7. `keiyaku qa` が自動 QA を生成し、`keiyaku export` が `elements.jsonl` と\n"
        "   検索評価セットを作る。\n\n"
    )
    add(
        "**決定論**：同じ content・style・seed・同じ依存版なら、同じ JSON と同じテキスト層の PDF が出る"
        "（PDF のメタデータ日時も固定値）。使った renderer は上の §6 のとおりで、"
        "版を固定している。seed は文書ごとに固定（§4.3 の表）。\n"
    )

    add("\n## 9. 架空性・転載しないこと\n\n")
    add(
        "- **完全架空**：会社名・屋号・商品名・人物名・住所・連絡先・URL・契約書番号・様式番号・"
        "物件名はすべて架空である。URL は `example.jp` / `example.co.jp` / `example.com` のみ、"
        "電話番号はゼロ埋めのみを使い、`keiyaku/lint/denylist.txt` で実在名を検出して lint で落とす。\n"
        "- **転載していない**：実在のひな型・標準契約書・モデル契約書から参考にしたのは"
        "**構造・要素の種類・レイアウト慣行だけ**で、文章はすべてオリジナルに書いた。"
        "参考文書そのものはリポジトリに入れていない（出典の一覧のみ）。\n"
        "- **実在の法令・裁判所・官公庁は名称のみ**を引用し、**法令の条番号は書かない**"
        "（架空の条文に実在の条番号を結びつけないため）。\n"
        "- 印影・手書き署名は描画しない。記名押印欄は枠と「印」の文字、収入印紙欄は枠と文字だけである。\n\n"
    )
    add(f"各文書の奥付に入れた断り書き（{_n(len(stats.disclaimers))} 種）：\n\n")
    add("\n".join(f"> {text}" for text in stats.disclaimers) + "\n")

    add("\n## 10. 品質保証\n\n")
    add(
        f"- **`status: ready` が {_n(scale.ready)} / {_n(scale.documents)} 文書。** status は"
        "自己申告ではなく `keiyaku verify` の結果で決まる（`manifest.json` の `errors` に理由が入る）。\n"
        "- `keiyaku manifest check` が `manifest.json` と実ファイル（checksum・ページ数・QA 数・"
        "成果物の有無）の一致を検査する。\n"
        "- `keiyaku eval --all --oracle` は、正解そのものを予測として入れたとき全指標が満点になることを"
        "確かめる（採点ハーネス自身の検査）。`--misread` で現実の読み取り誤りを模して崩すと、"
        "崩しの強さに応じて単調に悪化する。\n"
        "- 文書を足したときの検証の階段は `docs/validation_plan.md`（規則ベース読み取り → VLM → "
        "**構築経緯を知らない盲検エージェント** → 人間）。盲検で出た指摘は `docs/evaluation.md` §4.8 に"
        "落としてある。\n"
        "- 全ページの PNG を人が目視する手順（`keiyaku review`）を、新しい doctype・style の初回に必ず通す。"
        "**lint と verify が通っても版面は崩れうる。**\n"
    )

    add("\n## 11. 制限と既知の偏り\n\n")
    add(
        "**設計上の制限**（意図して外した。CLAUDE.md §1.2）\n\n"
        "- 日本語・横書きのみ。縦書き・ルビは対象外。\n"
        "- PDF はデジタル生成であり、**スキャン劣化・傾き・影・手書き・印影を含まない**。"
        "紙を撮った画像での精度はこのデータでは測れない。\n"
        "- 1 文書 1 言語・1 判型。多言語併記や差し込み印刷の揺れは入っていない。\n"
        "- 法律専門家の校閲を受けていない。**条項の妥当性・網羅性は保証しない。**\n"
        "- 題材・当事者・金額は doctype ごとに作ってあるが、**実際の取引分布を模していない**"
        "（業種・規模・地域の偏りを統計的に再現する設計ではない）。\n\n"
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
            f"\n宣言（doctype・番号方式・style・体裁の指定）のうち {MIN_CONTENTS} 本未満の content しか"
            f"使っていないものは {_n(len(thin_decl))} 件ある："
            + "、".join(f"{c.name}（{c.contents} content）" for c in thin_decl)
            + "。\n"
        )
    add("\n**宣言はあるが使っている文書が 0 の観点**（実装が検証されていない）\n\n")
    add(
        _table(
            ["分類", "観点"],
            [[c.group, c.name] for c in stats.unused],
        )
    )
    add(
        "\nこの 2 つの表は `dataset/` の実測から毎回作り直すので、"
        "文書を足して観点が増えれば自動的に消える（`docs/data_card.md` §4.3）。\n"
    )

    add("\n## 12. ライセンスと配布\n\n")
    embedded = [r.name for r in layout.embedded_fonts]
    registered = [r.name for r in layout.fonts]
    noto = [n for n in embedded if n.startswith("Noto")]
    ipa = [n for n in embedded if n.startswith("IPAex")]
    unused_fonts = [
        n for n in registered if n.replace(" ", "-") not in {e.rsplit("-Bold", 1)[0] for e in embedded}
    ]
    # 配布条件は**宣言（specs/publish.yaml）から読む**。固定文で「未決」と書くと、人間が決めた
    # あとにカードだけが古くなる（`docs/publishing.md` §6・`HITL_TODO.md` H13）
    add(_license_paragraph())
    if embedded:
        add(
            f"- **PDF にはフォントが埋め込まれている**（実測 {_n(len(embedded))} 種："
            + "、".join(f"`{n}`" for n in embedded)
            + "）。"
        )
        if noto:
            add("Noto 系は **SIL Open Font License 1.1**（`assets/fonts/LICENSE-Noto*.txt`）。")
        if ipa:
            add("IPAex 系は **IPA フォントライセンス v1.0**（`assets/fonts/IPA_Font_License_*.txt`）。")
        add("**PDF を再配布するときはこれらの条件に従う。**\n")
    if unused_fonts:
        add(
            "- 同梱しているが現行コーパスの PDF には入っていないフォント："
            + "、".join(f"`{n}`" for n in unused_fonts)
            + "（描画の候補として登録してあるだけ。§6）。\n"
        )
    add(
        "- **PNG はラスタライズ済み**でフォントのデータを含まない。`source.json` / `layout.json` / "
        "`answer.json` / `qa.json` / `elements.jsonl` も同様で、フォントのライセンスは関わらない。\n"
        "- 参考にした実在の契約書ひな型は**一切含まれていない**（§9）。\n"
    )

    add("\n## 13. このカードの更新\n\n")
    add(
        "```\n"
        "uv run keiyaku datacard update    # 書き出す（dataset/ を測るだけ。再描画は不要）\n"
        "uv run keiyaku datacard check     # 書き換えずに古くなっていないかを見る（古ければ終了コード 1）\n"
        "uv run keiyaku export             # 検索評価セット・このカード・公開用の面をまとめて作り直す\n"
        "uv run keiyaku publish check      # 公開用の面（カード・views・SHA256SUMS）の鮮度\n"
        "make check                        # ruff + pytest + manifest の鮮度 + このカードの鮮度\n"
        "```\n\n"
        "文書を足したら `keiyaku export`（または `make batch`）で更新される。更新を忘れると "
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
        return [f"{dataset_dir}/manifest.json が無い（`keiyaku manifest update` を実行する）"]
    fresh = render_card(collect(dataset_dir))
    if not path.is_file():
        return [f"{path} が無い（`keiyaku datacard update` を実行する）"]
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
