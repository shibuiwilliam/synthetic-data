"""生成物の検証（docs/rendering.md §6.9）。

`yakkan verify dataset/<doc_id>` が呼ぶ。1 つでも error があればデータセットに入れない。
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from yakkan.layout.fallback_align import align_page, contains
from yakkan.models import Layout, Source
from yakkan.verify.normalize import normalize

MAX_PAGES = 20
#: 本文テキストとして往復比較する領域（figure / header / footer は除く）
BODY_REGIONS = frozenset({"body", "table", "margin_note"})
#: はみ出し・重なりの許容（pt）
OVERFLOW_TOLERANCE = 1.0
OVERLAP_TOLERANCE = 1.0


@dataclass(frozen=True)
class CheckResult:
    code: str
    severity: Literal["error", "warn"]
    message: str
    detail: str = ""

    def format(self) -> str:
        head = f"[{self.severity.upper():5}] {self.code}: {self.message}"
        return f"{head}\n        {self.detail}" if self.detail else head


def _pdf_text_by_page(pdf_path: Path, style=None) -> list[str]:
    """ページごとの文字列。`style` を渡すと **ヘッダ・フッタ帯の文字を除く**。

    ページをまたぐ段落は、次ページのヘッダ／フッタ文字が本文の途中に挟まって見える。
    そのまま部分列判定をすると必ず落ちるので、往復比較では furniture を外す。
    """
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        if style is None:
            return ["".join(c["text"] for c in page.chars) for page in pdf.pages]
        header_below = style.page.header_below_pt()
        footer_above = style.page.footer_above_pt()
        out = []
        for page in pdf.pages:
            chars = [
                c for c in page.chars if c["bottom"] > header_below + 0.5 and c["top"] < footer_above - 0.5
            ]
            out.append("".join(c["text"] for c in chars))
        return out


def check_page_count(layout: Layout) -> list[CheckResult]:
    if layout.page_count > MAX_PAGES:
        return [
            CheckResult(
                "V01",
                "error",
                f"ページ数が上限を超えた: {layout.page_count} > {MAX_PAGES}",
                "内容を削るか style を変える。フォント縮小で押し込まない（docs/rendering.md §6.10）",
            )
        ]
    return []


def check_fonts(pdf_path: Path) -> list[CheckResult]:
    """同梱フォント以外が埋め込まれていないか、豆腐が無いか。"""
    import pdfplumber

    from yakkan.fonts import FONTS

    # PDF のフォント名は "Noto-Serif-JP-Bold" のようにウェイトが付くので前方一致で見る
    allowed = tuple(sorted({f.family.replace(" ", "-") for f in FONTS}))
    out: list[CheckResult] = []
    with pdfplumber.open(pdf_path) as pdf:
        used = {c["fontname"].split("+")[-1] for page in pdf.pages for c in page.chars}
        text = "".join(c["text"] for page in pdf.pages for c in page.chars)
    unexpected = {f for f in used if not f.startswith(allowed)}
    if unexpected:
        out.append(
            CheckResult(
                "V02",
                "error",
                f"同梱外のフォントが埋め込まれている: {sorted(unexpected)}",
                "SVG の <text> に font-family を書き忘れていないか（docs/gotchas.md）",
            )
        )
    if "�" in text:
        out.append(CheckResult("V02", "error", "テキスト層に U+FFFD がある（豆腐）"))
    return out


def check_text_roundtrip(source: Source, layout: Layout, pdf_path: Path, style=None) -> list[CheckResult]:
    """JSON の期待テキストが PDF から読み出せるか、box ツリーと pdfplumber が一致するか。"""
    out: list[CheckResult] = []
    pdf_pages = _pdf_text_by_page(pdf_path, style)
    pdf_all = normalize("".join(pdf_pages))

    # (a) JSON → PDF：要素ごとの期待テキストが PDF に現れる（CLAUDE.md §0.4-6）
    missing: list[str] = []
    for element_id, plain in source.derived.plain_text.items():
        expected = normalize(plain.without_label)
        if not expected or element_id not in layout.elements:
            continue
        if expected not in pdf_all:
            missing.append(f"{element_id}: {plain.without_label[:28]}")
    if missing:
        out.append(
            CheckResult(
                "V03",
                "error",
                f"PDF から読み出せない期待テキストが {len(missing)} 件",
                " / ".join(missing[:5]),
            )
        )

    # (b) box ツリー → pdfplumber：同じページのテキストが一致する
    for page_layout in layout.pages:
        from_boxes = normalize("".join(ln.text for ln in page_layout.text_lines if ln.region in BODY_REGIONS))
        from_pdf = normalize(pdf_pages[page_layout.number - 1])
        # PDF 側にはヘッダ・フッタ・図のテキストも入るので、box ツリー側が部分列であることを見る
        if from_boxes and from_boxes not in from_pdf:
            diff = _first_difference(from_boxes, from_pdf)
            out.append(
                CheckResult(
                    "V03", "error", f"p{page_layout.number}: box ツリーのテキストが PDF と一致しない", diff
                )
            )
    return out


def _first_difference(a: str, b: str) -> str:
    import difflib

    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag != "equal":
            return f"box側 {a[i1:i2][:36]!r} / PDF側 {b[j1:j2][:36]!r}（位置 {i1}）"
    return ""


def check_toc_pages(source: Source, layout: Layout, pdf_path: Path) -> list[CheckResult]:
    """目次に印字されたページ番号 ＝ 見出しの最初の fragment のページ。

    **突合は目次行の id で行う**（テキストで探すと、同じ見出し文言の条が複数あるときに
    別の章の行と突き合わせてしまう。実際に「第1条（この条項の補償内容）」が 3 章に現れた）。
    """
    out: list[CheckResult] = []
    if not source.derived.toc:
        return out

    # 目次行 id → 印字された行のテキスト
    printed: dict[str, str] = {}
    for page_layout in layout.pages:
        for line in page_layout.text_lines:
            if line.element_id.startswith("toc_") and not line.element_id.startswith("toc_page_"):
                printed[line.element_id] = printed.get(line.element_id, "") + line.text

    for entry in source.derived.toc:
        element = layout.elements.get(entry.id)
        if element is None:
            out.append(CheckResult("V04", "error", f"目次の見出しが描画されていない: {entry.id}"))
            continue
        real_page = min(f.page for f in element.fragments)
        line = printed.get(f"toc_{entry.id}")
        if line is None:
            out.append(
                CheckResult("V04", "error", f"目次に行が見つからない: {entry.id}（{entry.heading_text}）")
            )
            continue
        number = _trailing_number(line)
        if number is None:
            out.append(CheckResult("V04", "error", f"目次行にページ番号が無い: {entry.id}", line[:40]))
        elif number != real_page:
            out.append(
                CheckResult(
                    "V04",
                    "error",
                    f"目次のページ番号が実ページと違う: {entry.heading_text}",
                    f"目次 {number} / 実際 {real_page}（{entry.id}）",
                )
            )
    return out


def _trailing_number(line: str) -> int | None:
    import re

    match = re.search(r"(\d+)\s*$", line.strip())
    return int(match.group(1)) if match else None


def _source_element_ids(source: Source) -> set[str]:
    """source が持つ「PDF に描かれるべき要素」の id を全部集める。

    図の内部（`diagram`）は `layout.elements` ではなく `layout.figures[].nodes` に入るので
    降りない。ここで集めた id が 1 つでも `layout.elements` に無ければ、
    その要素は**丸ごと描画されていない**（WeasyPrint が黙って落とした）ことになる。
    """
    ids: set[str] = set()

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            identifier = obj.get("id")
            if isinstance(identifier, str):
                ids.add(identifier)
            for key, value in obj.items():
                if key == "diagram":
                    continue
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    dumped = source.model_dump(mode="python")
    for key in ("front_matter", "body", "appendices"):
        walk(dumped.get(key))
    return ids


def _diagram_node_ids(source: Source) -> dict[str, set[str]]:
    """図ごとの内部ノード id（`layout.figures[].nodes` と突き合わせる用）。"""
    out: dict[str, set[str]] = {}

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            if obj.get("type") == "figure" and isinstance(obj.get("diagram"), dict):
                node_ids: set[str] = set()

                def collect(inner: object) -> None:
                    if isinstance(inner, dict):
                        identifier = inner.get("id")
                        if isinstance(identifier, str):
                            node_ids.add(identifier)
                        for value in inner.values():
                            collect(value)
                    elif isinstance(inner, list):
                        for value in inner:
                            collect(value)

                collect(obj["diagram"])
                out[str(obj["id"])] = node_ids
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    dumped = source.model_dump(mode="python")
    for key in ("front_matter", "body", "appendices"):
        walk(dumped.get(key))
    return out


def check_fragments(source: Source, layout: Layout) -> list[CheckResult]:
    """すべてのノード・ブロックが 1 つ以上の fragment を持つ（描画漏れ検出）。"""
    missing = [
        element_id
        for element_id in source.derived.plain_text
        if element_id in layout.elements and not layout.elements[element_id].fragments
    ]
    # ノードだけを見ていたため、表や図が丸ごと落ちても検出できていなかった
    # （span-all の表がページの残り高さに収まらないと WeasyPrint が黙って落とす）。
    # source 側の全要素 id を突き合わせる。
    never_drawn = sorted(_source_element_ids(source) - set(layout.elements))
    out: list[CheckResult] = []
    if missing:
        out.append(
            CheckResult("V05", "error", f"fragment が空の要素が {len(missing)} 件", " ".join(missing[:8]))
        )
    if never_drawn:
        out.append(
            CheckResult(
                "V05",
                "error",
                f"描画されていない要素が {len(never_drawn)} 件",
                " ".join(never_drawn[:8]),
            )
        )
    # 図の内部ノードは layout.figures 側に出る
    for figure_id, node_ids in _diagram_node_ids(source).items():
        drawn = layout.figures.get(figure_id)
        if drawn is None:
            continue  # 図そのものの欠落は上の never_drawn が報告する
        lost = sorted(node_ids - set(drawn.nodes))
        if lost:
            out.append(
                CheckResult(
                    "V05",
                    "error",
                    f"図のノードが描画されていない: {figure_id}",
                    " ".join(lost[:8]),
                )
            )
    return out


def check_overflow(layout: Layout, style) -> list[CheckResult]:
    """要素がページの内容領域から食み出していないか。"""
    left = style.page.margin_mm.left * 2.834645669291339
    right = style.page.width_pt - style.page.margin_mm.right * 2.834645669291339
    out: list[CheckResult] = []
    for element_id, element in layout.elements.items():
        for fragment in element.fragments:
            x0, _y0, x1, _y1 = fragment.bbox
            if x0 < left - OVERFLOW_TOLERANCE or x1 > right + OVERFLOW_TOLERANCE:
                out.append(
                    CheckResult(
                        "V06",
                        "error",
                        f"要素が内容領域から食み出している: {element_id}",
                        f"p{fragment.page} x=[{x0:.1f}, {x1:.1f}] / 内容領域 [{left:.1f}, {right:.1f}]",
                    )
                )
    return out


def check_overlap(layout: Layout) -> list[CheckResult]:
    """本文ブロック同士が重なっていないか（同じページ・同じ段の中で）。"""
    out: list[CheckResult] = []
    for page_layout in layout.pages:
        boxes: list[tuple[str, tuple[float, float, float, float]]] = []
        for element_id in page_layout.reading_order:
            element = layout.elements.get(element_id)
            if element is None or element.kind not in ("paragraph", "item", "subitem", "subsubitem"):
                continue
            for fragment in element.fragments:
                if fragment.page == page_layout.number:
                    boxes.append((element_id, fragment.bbox))
        for i, (id_a, a) in enumerate(boxes):
            for id_b, b in boxes[i + 1 :]:
                if _overlap_area(a, b) > OVERLAP_TOLERANCE:
                    out.append(
                        CheckResult(
                            "V07",
                            "error",
                            f"本文ブロックが重なっている: {id_a} と {id_b}",
                            f"p{page_layout.number}",
                        )
                    )
    return out


def _overlap_area(a, b) -> float:
    dx = min(a[2], b[2]) - max(a[0], b[0])
    dy = min(a[3], b[3]) - max(a[1], b[1])
    return dx * dy if dx > 0 and dy > 0 else 0.0


def check_fallback_alignment(source: Source, layout: Layout, pdf_path: Path) -> list[CheckResult]:
    """box ツリーの bbox が pdfplumber の文字群を内包するか（§6.8-4 の代替判定）。"""
    import pdfplumber

    out: list[CheckResult] = []
    mismatches: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page_layout in layout.pages:
            page = pdf.pages[page_layout.number - 1]
            expected = [
                (ln.element_id, ln.text)
                for ln in page_layout.text_lines
                if ln.region in BODY_REGIONS and ln.element_id
            ]
            if not expected:
                continue
            for aligned in align_page(page, expected):
                element = layout.elements.get(aligned.element_id)
                if element is None:
                    continue
                fragments = [f for f in element.fragments if f.page == page_layout.number]
                if not fragments:
                    continue
                union = (
                    min(f.bbox[0] for f in fragments),
                    min(f.bbox[1] for f in fragments),
                    max(f.bbox[2] for f in fragments),
                    max(f.bbox[3] for f in fragments),
                )
                # 段またぎ・表頭の繰り返しで要素が割れるため、そのページの断片の和で判定する
                if not contains(union, aligned.bbox):
                    mismatches.append(aligned.element_id)
    if mismatches:
        out.append(
            CheckResult(
                "V08",
                "warn",
                f"box ツリーと pdfplumber の bbox がずれている要素が {len(mismatches)} 件",
                " ".join(sorted(set(mismatches))[:8]),
            )
        )
    return out


def check_figures(source: Source, layout: Layout, pdf_path: Path) -> list[CheckResult]:
    """図のノードが layout に載り、ラベルが PDF のテキスト層にも出ているか。

    SVG の中身は box ツリーに現れない（WeasyPrint は inline SVG を ReplacedBox として置くため、
    `text_lines` に figure 領域の行は出ない）。図の正解は `layout.figures[].nodes` の座標と
    `alt` / `facts` が担うので、ここでは「座標が取れていること」と
    「ラベルが PDF から読めること」の 2 点を確かめる。
    """
    from yakkan.lint.walk import iter_blocks
    from yakkan.models import Figure

    out: list[CheckResult] = []
    pdf_all = normalize("".join(_pdf_text_by_page(pdf_path)))
    for block, _owner, _article in iter_blocks(source):
        if not isinstance(block, Figure):
            continue
        figure_layout = layout.figures.get(block.id)
        if figure_layout is None:
            out.append(CheckResult("V10", "error", f"図の座標が layout に無い: {block.id}"))
            continue
        if not figure_layout.nodes:
            out.append(CheckResult("V10", "error", f"図のノード座標が空: {block.id}"))
        missing = [label for label in _diagram_labels(block) if normalize(label) not in pdf_all]
        if missing:
            out.append(
                CheckResult(
                    "V10",
                    "error",
                    f"図のラベルが PDF から読めない: {block.id}",
                    " / ".join(missing[:5]),
                )
            )
    return out


def _diagram_labels(figure) -> list[str]:
    """図に描かれる文字のうち、テキスト層に出るはずのもの。"""
    diagram = figure.diagram
    match diagram.kind:
        case "flowchart":
            return [n.label for n in diagram.nodes]
        case "tree":
            labels: list[str] = []
            stack = [diagram.root]
            while stack:
                node = stack.pop()
                labels.append(node.label)
                stack.extend(node.children)
            return labels
        case "steps":
            return [s.title for s in diagram.steps]
        case "timeline":
            return [s.label for s in diagram.spans] + [e.label for e in diagram.events]
        case "annotated_mock":
            return [f.label for f in diagram.fields]
        case "matrix":
            return list(diagram.rows) + list(diagram.cols)
    return []


def verify_dataset(dataset_dir: Path, style=None) -> list[CheckResult]:
    """`dataset/<doc_id>/` を検証する。"""
    from yakkan.styles import load_style

    source = Source.model_validate(json.loads((dataset_dir / "source.json").read_text(encoding="utf-8")))
    layout = Layout.model_validate(json.loads((dataset_dir / "layout.json").read_text(encoding="utf-8")))
    pdf_path = dataset_dir / "doc.pdf"
    style = style or load_style(layout.style_id)

    results: list[CheckResult] = []
    results += check_page_count(layout)
    results += check_fonts(pdf_path)
    results += check_text_roundtrip(source, layout, pdf_path, style)
    results += check_toc_pages(source, layout, pdf_path)
    results += check_fragments(source, layout)
    results += check_overflow(layout, style)
    results += check_overlap(layout)
    results += check_fallback_alignment(source, layout, pdf_path)
    results += check_figures(source, layout, pdf_path)
    return results


def check_determinism(source: Source, style, tmp_dir: Path) -> list[CheckResult]:
    """2 回描画して layout.json と PDF のテキスト層が一致するか（CLAUDE.md §0.4-4）。"""
    from yakkan.models import dump_json
    from yakkan.render.weasy import render_source

    payloads = []
    texts = []
    for i in range(2):
        result = render_source(source, style, tmp_dir / f"run{i}", render_png=False)
        payloads.append(dump_json(result.layout))
        texts.append("".join(_pdf_text_by_page(result.pdf_path)))
    out: list[CheckResult] = []
    if payloads[0] != payloads[1]:
        out.append(CheckResult("V09", "error", "2 回描画して layout.json が一致しない"))
    if texts[0] != texts[1]:
        out.append(CheckResult("V09", "error", "2 回描画して PDF のテキスト層が一致しない"))
    return out
