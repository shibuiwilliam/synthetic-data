"""HTML → PDF → PNG と layout の抽出（docs/rendering.md §6.8）。

手順は 1 回のレイアウトで完結させる：
`HTML.render()` → **同じ document から** layout を抽出 → `write_pdf()` → PNG。
再レイアウトすると bbox と PDF がずれうる（§6.8-5）。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from yakkan.layout.extract import extract_layout
from yakkan.models import Layout, Source, dump_json
from yakkan.render.html import build_html
from yakkan.styles import Style


class RenderLayoutError(RuntimeError):
    """WeasyPrint のレイアウトが破綻した（docs/gotchas.md）。

    WeasyPrint 70.0 は、内容の高さがある条件に一致すると `assert not page_is_empty` で落ちる。
    どの CSS 機能が原因というものではなく、内容をわずかに増減するだけで出たり消えたりする。
    **黙って回避すると正解データ（bbox・ページ番号）が変わるため、ここで明示的に失敗させる。**
    """


#: PDF のメタデータ日時は固定する（CLAUDE.md §0.4-4 決定論）
FIXED_TIMESTAMP = "2026-01-01T00:00:00+00:00"
PDF_IDENTIFIER = b"yakkan-synth"
DPI_PNG = 150


@dataclass
class RenderResult:
    doc_id: str
    out_dir: Path
    pdf_path: Path
    png_paths: list[Path]
    layout: Layout
    html: str
    notes: list[str] = field(default_factory=list)

    @property
    def page_count(self) -> int:
        return self.layout.page_count


def render_source(
    source: Source,
    style: Style,
    out_dir: Path,
    *,
    keep_html: bool = True,
    render_png: bool = True,
) -> RenderResult:
    """1 文書を描画して `dataset/<doc_id>/` に書き出す。"""

    doc_id = f"{source.content_id}--{style.style_id}"
    out_dir.mkdir(parents=True, exist_ok=True)
    # --- 1 パス目：target-counter でページ番号を入れ、実ページを測る ---
    html, notes, figure_nodes = build_html(source, style)
    document = _layout(html, doc_id)

    # --- 2 パス目：測った実ページを **文字として** 目次に埋め直す ---
    # WeasyPrint の target-counter は目次が長いと収束せず、印字と実ページがずれる。
    # 正解データに誤ったページ番号を残さないよう、測った値を埋めて描き直す。
    toc_pages = _measure_toc_pages(document, source)
    if toc_pages:
        html, notes, figure_nodes = build_html(source, style, toc_pages=toc_pages)
        document = _layout(html, doc_id)
        settled = _measure_toc_pages(document, source)
        moved = {k: (toc_pages[k], settled[k]) for k in settled if settled.get(k) != toc_pages.get(k)}
        if moved:
            # 番号を埋めたことで見出しが動いた場合は、その値でもう一度だけ描き直す
            html, notes, figure_nodes = build_html(source, style, toc_pages=settled)
            document = _layout(html, doc_id)
            notes.append(f"目次のページ番号が 1 回ずれたので測り直した: {sorted(moved)[:5]}")

    if keep_html:
        (out_dir / "render.html").write_text(html, encoding="utf-8")

    # bbox は write_pdf の前に、同じ document から取る（§6.8-5）
    layout = extract_layout(document, source=source, style=style, doc_id=doc_id, figure_nodes=figure_nodes)

    # --- 内容欠落の検査（§2-7「失敗は早く・明示的に」） ---
    # WeasyPrint は段組の中に収まらない段またぎ要素があると、それ以降の内容を
    # **黙って捨てる**（章見出し帯1つで5ページぶん失われた実例がある）。
    # verify まで待たず、この場で止める。壊れたデータセットを書き出さない。
    _assert_nothing_dropped(source, layout, doc_id)

    document.metadata.created = FIXED_TIMESTAMP
    document.metadata.modified = FIXED_TIMESTAMP
    pdf_path = out_dir / "doc.pdf"
    document.write_pdf(pdf_path, pdf_identifier=PDF_IDENTIFIER)

    png_paths = rasterize(pdf_path, out_dir / "pages") if render_png else []
    dump_json(layout, out_dir / "layout.json")
    # source.json も同じ場所に置く。verify / qa / eval はこの 2 つを対で読むので、
    # 書き出しを呼び出し側に任せると書き忘れる（batch で実際に起きた）。
    dump_json(source, out_dir / "source.json")
    return RenderResult(
        doc_id=doc_id,
        out_dir=out_dir,
        pdf_path=pdf_path,
        png_paths=png_paths,
        layout=layout,
        html=html,
        notes=notes,
    )


def _assert_nothing_dropped(source: Source, layout: Layout, doc_id: str) -> None:
    """source の要素が 1 つでも描画されていなければ `RenderLayoutError` にする。"""
    from yakkan.verify.checks import check_fragments

    dropped = [r for r in check_fragments(source, layout) if r.severity == "error"]
    if not dropped:
        return
    detail = "\n  ".join(f"{r.message}: {r.detail}" for r in dropped)
    raise RenderLayoutError(
        f"{doc_id}: 描画の結果、source にある要素が PDF から欠落した。\n  {detail}\n"
        "  段組の中に収まらない段またぎ要素（`column-span: all` の見出し・`span_columns: true` の表）が\n"
        "  あると、WeasyPrint はそれ以降の内容を黙って捨てる。\n"
        "  対処：(1) その表の `span_columns` を false にする、(2) 表の列数・行数を減らす、\n"
        "  (3) 直前の本文の字数を増減させて要素のページ内位置をずらす。\n"
        "  自動でレイアウトをずらす回避は入れない（bbox とページ番号が変わり正解が壊れる）。"
    )


def _layout(html: str, doc_id: str):
    """HTML をレイアウトする。WeasyPrint の内部アサーションは分かる形に包み直す。"""
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration

    try:
        return HTML(string=html, base_url=str(Path.cwd())).render(font_config=FontConfiguration())
    except (AssertionError, IndexError) as exc:
        raise RenderLayoutError(
            f"{doc_id}: WeasyPrint のレイアウトが破綻した（{type(exc).__name__}）。\n"
            "  内容と段幅の組み合わせが特定の条件に一致したときに起きる WeasyPrint 70.0 の不具合で、\n"
            "  同じ内容でも数十字ぶん増減させると通ることが多い。\n"
            "  （ページ分割の assert と、インライン整形の IndexError の 2 系統を確認している）\n"
            "  対処：(1) 本文を少し削るか足す、(2) 別の style で描く、(3) 版を上げて再試行。\n"
            "  自動でレイアウトをずらす回避はしない（bbox とページ番号が変わり正解が壊れるため）。"
        ) from exc


def _measure_toc_pages(document, source: Source) -> dict[str, int]:
    """目次に載せる見出しが、実際に何ページ目に出たかを測る。"""
    from yakkan.layout.extract import iter_fragments

    if not source.derived.toc:
        return {}
    wanted = {entry.id for entry in source.derived.toc}
    pages: dict[str, int] = {}
    for fragment in iter_fragments(document, box_types=("BlockBox",)):
        if fragment.element_id in wanted:
            pages.setdefault(fragment.element_id, fragment.page)
            pages[fragment.element_id] = min(pages[fragment.element_id], fragment.page)
    return pages


def rasterize(pdf_path: Path, pages_dir: Path, dpi: int = DPI_PNG) -> list[Path]:
    import pypdfium2 as pdfium

    pages_dir.mkdir(parents=True, exist_ok=True)
    # 前回より短い文書を描いたとき、古い page-NNN.png が残ると
    # 目視レビューで存在しないページを見てしまうので先に一掃する。
    for stale in pages_dir.glob("page-*.png"):
        stale.unlink()
    paths: list[Path] = []
    pdf = pdfium.PdfDocument(pdf_path)
    for i, page in enumerate(pdf, start=1):
        image = page.render(scale=dpi / 72).to_pil()
        path = pages_dir / f"page-{i:03d}.png"
        image.save(path)
        paths.append(path)
    return paths


def page_report(result: RenderResult, source: Source) -> list[tuple[str, str, int, int]]:
    """章ごとの使用ページ（`yakkan render --report`）。(id, 見出し, 開始, 終了)。"""
    rows: list[tuple[str, str, int, int]] = []
    for node in source.body + source.appendices:
        element = result.layout.elements.get(node.id)
        if element is None:
            continue
        start = min(f.page for f in element.fragments)
        end = _subtree_last_page(result.layout, node)
        rows.append((node.id, source.derived.labels[node.id].heading_text, start, end))
    return rows


def _subtree_last_page(layout: Layout, node) -> int:
    last = 1
    stack = [node]
    while stack:
        current = stack.pop()
        element = layout.elements.get(current.id)
        if element:
            last = max(last, max(f.page for f in element.fragments))
        for block in current.blocks:
            block_id = getattr(block, "id", None)
            if block_id and block_id in layout.elements:
                last = max(last, max(f.page for f in layout.elements[block_id].fragments))
        stack.extend(current.children)
    return last
