"""WeasyPrint の挙動を実測する probe（CLAUDE.md §14 / docs/rendering.md の「要probe」項目）。

    make probe        # 結果表を標準出力に出す

**設計より先にこれを走らせる。** 結果は docs/decisions.md と docs/gotchas.md に転記する。
各 probe は独立した最小 HTML を描画し、対応／非対応／注意点を 1 行にまとめて返す。
"""

from __future__ import annotations

import io
import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from yakkan.fonts import font_face_css  # noqa: E402

PX_TO_PT = 0.75
FIXED_DATE = "2026-09-21T00:00:00+00:00"


@dataclass
class Result:
    name: str
    ok: bool | None  # None = 判定保留（観察のみ）
    summary: str
    notes: list[str] = field(default_factory=list)


def base_css(extra: str = "") -> str:
    return f"""{font_face_css()}
body {{ margin: 0; }}
html {{ font-family: 'Noto Serif JP', serif; font-size: 9.5pt; line-height: 1.6; }}
@page {{ size: A4; margin: 16mm 14mm 18mm 14mm; }}
{extra}"""


def render(html_body: str, extra_css: str = "", **page_css):
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration

    html = (
        "<!DOCTYPE html><html lang='ja'><head><meta charset='utf-8'>"
        f"<style>{base_css(extra_css)}</style></head><body>{html_body}</body></html>"
    )
    return HTML(string=html, base_url=str(ROOT)).render(font_config=FontConfiguration())


def walk_boxes(document):
    """(page, box) を文書順に返す。"""
    for page_number, page in enumerate(document.pages, start=1):

        def visit(box):
            yield box
            for child in getattr(box, "children", []):
                yield from visit(child)

        for box in visit(page._page_box):
            yield page_number, box


def boxes_by_id(document) -> dict[str, list[tuple[int, tuple[float, float, float, float], str]]]:
    out: dict[str, list[tuple[int, tuple[float, float, float, float], str]]] = {}
    for page_number, box in walk_boxes(document):
        element = getattr(box, "element", None)
        if element is None or not hasattr(element, "get"):
            continue
        element_id = element.get("id")
        if not element_id:
            continue
        x = box.border_box_x() * PX_TO_PT
        y = box.border_box_y() * PX_TO_PT
        w = box.border_width() * PX_TO_PT
        h = box.border_height() * PX_TO_PT
        out.setdefault(element_id, []).append((page_number, (x, y, x + w, y + h), type(box).__name__))
    return out


# --- 1. box ツリー -------------------------------------------------------------


def probe_box_tree() -> list[Result]:
    filler = "この条項は、検証のために書き下ろした文です。" * 120  # 1 段に収まらない量にする
    body = f"""
    <div id="cols" class="cols">
      <h2 id="h2">検証用の章</h2>
      <p id="p_long">{filler}</p>
      <p id="p_short">短い段落です。</p>
    </div>"""
    css = ".cols { column-count: 2; column-gap: 8mm; column-fill: auto; } h2 { column-span: all; }"
    doc = render(body, css)
    found = boxes_by_id(doc)
    results = [
        Result(
            "box: element id → border box",
            "p_long" in found and "h2" in found,
            f"id を持つ box を {len(found)} 種類検出（{sum(len(v) for v in found.values())} 断片）",
            [
                f"h2 bbox(pt) = {tuple(round(v, 1) for v in found['h2'][0][1])}"
                if "h2" in found
                else "h2 なし"
            ],
        )
    ]

    blocks = [f for f in found.get("p_long", []) if f[2] == "BlockBox"]
    results.append(
        Result(
            "box: 段またぎで fragment が複数になる",
            len(blocks) >= 2,
            f"p_long の BlockBox 断片 = {len(blocks)} 個",
            [f"page={p} x0={b[0]:.1f}" for p, b, _ in blocks[:4]],
        )
    )

    # 改ページ分割
    long_body = f'<p id="p_page">{"改ページの検証のための文章です。" * 400}</p>'
    doc2 = render(long_body)
    found2 = boxes_by_id(doc2)
    pages = {p for p, _, kind in found2.get("p_page", []) if kind == "BlockBox"}
    results.append(
        Result(
            "box: 改ページで fragment が複数ページになる",
            len(pages) >= 2,
            f"p_page が現れたページ = {sorted(pages)}（全 {len(doc2.pages)} ページ）",
        )
    )

    texts = []
    for _, box in walk_boxes(doc):
        if type(box).__name__ == "TextBox":
            texts.append((box.text, box.border_box_x() * PX_TO_PT, box.border_box_y() * PX_TO_PT))
    results.append(
        Result(
            "box: TextBox から文字列と座標が取れる",
            bool(texts) and all(isinstance(t[0], str) for t in texts),
            f"TextBox {len(texts)} 個。先頭 = {texts[0][0][:18]!r} @ ({texts[0][1]:.1f}, {texts[0][2]:.1f})pt"
            if texts
            else "TextBox なし",
        )
    )
    return results


# --- 2. 目次 -------------------------------------------------------------------


def probe_toc() -> list[Result]:
    body = (
        """
    <nav id="toc">
      <p class="toc-line"><a id="toc_a1" href="#a1"><span class="t">告知義務</span></a></p>
      <p class="toc-line"><a id="toc_a2" href="#a2"><span class="t">通知義務</span></a></p>
    </nav>
    <h3 id="a1">告知義務</h3>
    <p>"""
        + "本文です。" * 500
        + """</p>
    <h3 id="a2">通知義務</h3>
    <p>次の条です。</p>"""
    )
    css = """
    .toc-line a { text-decoration: none; color: inherit; }
    .toc-line a::after { content: leader('.') target-counter(attr(href), page); }
    """
    doc = render(body, css)
    pdf = io.BytesIO()
    doc.write_pdf(pdf)
    text = extract_text(pdf.getvalue())
    # 目次行に数字が入っているか
    line1 = re.search(r"告知義務[.\s]*(\d+)", text)
    line2 = re.search(r"通知義務[.\s]*(\d+)", text)
    found = boxes_by_id(doc)
    real_page = {k: v[0][0] for k, v in found.items() if k in ("a1", "a2")}
    ok = (
        bool(line1 and line2)
        and int(line1.group(1)) == real_page.get("a1")
        and int(line2.group(1)) == real_page.get("a2")
    )
    leaders = "..." in text or "…" in text
    return [
        Result(
            "target-counter による目次ページ番号",
            ok,
            f"目次の数字 = {line1.group(1) if line1 else None}"
            f"/{line2.group(1) if line2 else None}、実ページ = {real_page}",
        ),
        Result("leader('.')", leaders, f"テキスト層にリーダー罫の点 {'あり' if leaders else 'なし'}"),
    ]


# --- 3. 段組 -------------------------------------------------------------------


def probe_columns() -> list[Result]:
    body = f"""<div id="cols" class="cols">
      <h2 id="span_h">段またぎ見出し</h2>
      <p id="p1">{"段組の検証文です。" * 60}</p>
      <table id="span_tbl_direct"><tr><td>table に直接指定</td></tr></table>
      <div id="span_wrap"><table id="tbl_inner"><tr><td>div でくるんだ表</td></tr></table></div>
      <p id="p2">{"後続の段落です。" * 20}</p>
    </div>"""
    css = """
    .cols { column-count: 2; column-gap: 8mm; column-fill: auto; }
    h2, #span_tbl_direct, #span_wrap { column-span: all; }
    table { border-collapse: collapse; width: 100%; } td { border: 0.5pt solid #333; }
    """
    doc = render(body, css)
    found = boxes_by_id(doc)
    content_width = 595.276 - 2 * 14 * 2.83465
    span_w = found["span_h"][0][1][2] - found["span_h"][0][1][0]
    col_w = found["p1"][0][1][2] - found["p1"][0][1][0]
    direct_w = found["span_tbl_direct"][0][1][2] - found["span_tbl_direct"][0][1][0]
    wrap_w = found["span_wrap"][0][1][2] - found["span_wrap"][0][1][0]
    return [
        Result(
            "column-count: 2",
            abs(col_w - (content_width - 8 * 2.83465) / 2) < 1.0,
            f"段の幅 = {col_w:.1f}pt（期待 {(content_width - 8 * 2.83465) / 2:.1f}pt）",
        ),
        Result(
            "column-span: all（ブロック要素）",
            abs(span_w - content_width) < 1.0,
            f"見出し h2 = {span_w:.1f}pt（本文領域 {content_width:.1f}pt）",
        ),
        Result(
            "column-span: all（<table> に直接）",
            abs(direct_w - content_width) < 1.0,
            f"table 直接 = {direct_w:.1f}pt（本文領域 {content_width:.1f}pt）",
            ["効かない場合は <div>/<figure> でくるむ"],
        ),
        Result(
            "column-span: all（<div> でくるんだ表）",
            abs(wrap_w - content_width) < 1.0,
            f"div でくるむ = {wrap_w:.1f}pt",
        ),
    ]


# --- 4. 表 ---------------------------------------------------------------------


def probe_table() -> list[Result]:
    rows = "".join(f'<tr><td id="r{i}c0">第{i}行</td><td>内容の列です。</td></tr>' for i in range(70))
    body = f"""<table id="t">
      <thead><tr><th id="th0">見出しA</th><th id="th1">見出しB</th></tr></thead>
      <tbody>{rows}</tbody></table>"""
    css = """
    table { border-collapse: collapse; width: 100%; }
    th, td { border: 0.5pt solid #333; padding: 2mm; }
    thead { display: table-header-group; }
    tr { break-inside: avoid; }
    """
    doc = render(body, css)
    found = boxes_by_id(doc)
    th_pages = sorted({p for p, _, kind in found.get("th0", []) if kind == "TableCellBox"})
    # tr が分割されていないか（同じセルが2ページに出ない）
    split_cells = [
        k
        for k, v in found.items()
        if k.startswith("r") and len({p for p, _, kd in v if kd == "TableCellBox"}) > 1
    ]
    return [
        Result(
            "thead の改ページ時繰り返し",
            len(th_pages) >= 2,
            f"表頭セル th0 が現れたページ = {th_pages}（全 {len(doc.pages)} ページ）",
            ["繰り返された表頭は同じ id を持つ → layout.json で repeated: true を立てる必要がある"],
        ),
        Result(
            "tr の break-inside: avoid",
            not split_cells,
            f"ページをまたいで分割されたセル = {len(split_cells)} 個",
        ),
    ]


# --- 5. 欄外注 -----------------------------------------------------------------


def probe_footnote() -> list[Result]:
    head, tail = "本文です。" * 60, "続きの本文です。" * 60
    body = f'<p id="p">{head}<span id="fnote" class="fn">これは欄外注の文です。</span>{tail}</p>'
    css = """
    .fn { float: footnote; }
    @page { @footnote { border-top: 0.5pt solid #333; } }
    """
    try:
        doc = render(body, css)
    except Exception as exc:  # noqa: BLE001
        return [Result("float: footnote", False, f"例外: {type(exc).__name__}: {exc}")]
    found = boxes_by_id(doc)
    if "fnote" not in found:
        return [Result("float: footnote", False, "欄外注の box が見つからない")]
    _page, bbox, _kind = found["fnote"][0]
    p_bbox = found["p"][0][1]
    below = bbox[1] > p_bbox[3] - 1
    return [
        Result(
            "float: footnote（ページ下部配置）",
            below,
            f"欄外注 y={bbox[1]:.1f}pt / 本文の下端 y={p_bbox[3]:.1f}pt"
            f" → {'ページ下部に降りた' if below else '本文内に残った'}",
        )
    ]


# --- 6. ルビ -------------------------------------------------------------------


def probe_ruby() -> list[Result]:
    body = '<p id="p">遅滞なく<ruby id="r">遅滞<rt>ちたい</rt></ruby>お知らせください。</p>'
    doc = render(body, "ruby { ruby-position: over; }")
    pdf = io.BytesIO()
    doc.write_pdf(pdf)
    text = extract_text(pdf.getvalue())
    has_base = "遅滞" in text
    has_reading = "ちたい" in text
    tops = {}
    for _, box in walk_boxes(doc):
        if type(box).__name__ == "TextBox":
            tops.setdefault(box.text, box.border_box_y() * PX_TO_PT)
    rt_above = "ちたい" in tops and "遅滞" in tops and tops["ちたい"] < tops["遅滞"]
    return [
        Result(
            "<ruby> / <rt>（ルビとして組まれるか）",
            has_base and has_reading and rt_above,
            f"基底 {'あり' if has_base else 'なし'} / 読み {'あり' if has_reading else 'なし'}"
            f" / 読みが基底より上に出た: {rt_above}",
            ["読みが基底の上に来ないなら非対応。代替は下の inline-block 積み"],
        )
    ]


#: <ruby> が使えないときの代替（CLAUDE.md §14 の「inline-block 積み」）
RUBY_FALLBACK_CSS = """
.ruby { display: inline-block; text-align: center; line-height: 1; vertical-align: baseline; }
.ruby .rt { display: block; font-size: 50%; line-height: 1; margin-bottom: -0.1em; }
.ruby .rb { display: block; line-height: 1; }
"""


def probe_ruby_fallback() -> list[Result]:
    """代替案：inline-block の中に読み（小）と基底を縦に積む。"""
    body = (
        '<p id="p" style="line-height:2.2">'
        '<span class="ruby"><span class="rt">ちたい</span><span class="rb">遅滞</span></span>なく</p>'
    )
    doc = render(body, RUBY_FALLBACK_CSS)
    tops: dict[str, float] = {}
    for _, box in walk_boxes(doc):
        if type(box).__name__ == "TextBox":
            tops.setdefault(box.text, box.border_box_y() * PX_TO_PT)
    above = tops.get("ちたい", 1e9) < tops.get("遅滞", 0.0)
    return [
        Result(
            "ルビの代替（inline-block 積み）",
            above,
            f"読み y={tops.get('ちたい')} / 基底 y={tops.get('遅滞')} → 読みが上: {above}",
            ["期待テキストは基底のみ。読みもテキスト層に載るので往復比較では除外する"],
        )
    ]


# --- 7. SVG --------------------------------------------------------------------


def probe_svg() -> list[Result]:
    body = """<figure id="fig"><svg id="svg" viewBox="0 0 200 60" width="200" height="60">
      <rect x="4" y="4" width="120" height="40" fill="#eee" stroke="#333"/>
      <text id="t1" x="64" y="28" text-anchor="middle"
            font-family="Noto Sans JP" font-size="12">事故の発生</text>
      <text id="t2" x="64" y="52" font-size="9">既定フォント</text>
    </svg></figure>"""
    doc = render(body)
    pdf_bytes = io.BytesIO()
    doc.write_pdf(pdf_bytes)
    data = pdf_bytes.getvalue()
    text = extract_text(data)
    fonts = extract_fonts(data)
    return [
        Result(
            "インライン SVG の <text> がテキスト層に載る",
            "事故の発生" in text,
            f"抽出テキスト = {text.strip()[:40]!r}",
            ["往復比較では figure 領域として本文から除外する必要がある"],
        ),
        Result(
            "SVG の font-family 指定が効く",
            any("Noto-Sans-JP" in f for f in fonts),
            f"埋め込みフォント = {sorted(fonts)}",
            ["font-family 無指定の <text> もあるので、既定にフォールバックしていないか要確認"],
        ),
    ]


# --- 8. 再現性 -----------------------------------------------------------------


def probe_determinism() -> list[Result]:
    body = '<p id="p">決定論の検証です。</p>'

    def build(fixed: bool) -> bytes:
        doc = render(body)
        if fixed:
            doc.metadata.created = FIXED_DATE
            doc.metadata.modified = FIXED_DATE
        out = io.BytesIO()
        doc.write_pdf(out, uncompressed_pdf=False, pdf_identifier=b"yakkan-probe" if fixed else None)
        return out.getvalue()

    free1, free2 = build(False), build(False)
    fixed1, fixed2 = build(True), build(True)
    has_creation = b"/CreationDate" in free1
    return [
        Result(
            "PDF に /CreationDate が入るか",
            None,
            f"未固定で /CreationDate {'あり' if has_creation else 'なし'}"
            f" / 固定後 {'あり' if b'/CreationDate' in fixed1 else 'なし'}",
        ),
        Result(
            "PDF のバイト再現性（メタデータ未固定）",
            free1 == free2,
            f"同一: {free1 == free2}"
            f"（差分 {sum(a != b for a, b in zip(free1, free2, strict=False))} バイト）",
        ),
        Result(
            "PDF のバイト再現性（created/modified と ID を固定）",
            fixed1 == fixed2,
            f"同一: {fixed1 == fixed2}",
            ["doc.metadata.created / modified を固定し、write_pdf に pdf_identifier を渡す"],
        ),
    ]


# --- 9. 座標系 -----------------------------------------------------------------


def probe_coordinates() -> list[Result]:
    body = '<p id="p" style="margin:0">座標の検証用の一行です。</p>'
    doc = render(body)
    found = boxes_by_id(doc)
    _page, bbox, _kind = found["p"][0]
    text_boxes = [
        (b.border_box_x() * PX_TO_PT, b.border_box_y() * PX_TO_PT, b.border_height() * PX_TO_PT)
        for _, b in walk_boxes(doc)
        if type(b).__name__ == "TextBox"
    ]
    out = io.BytesIO()
    doc.write_pdf(out)
    import pdfplumber

    with pdfplumber.open(io.BytesIO(out.getvalue())) as pdf:
        p = pdf.pages[0]
        chars = p.chars
        x0 = min(c["x0"] for c in chars)
        top = min(c["top"] for c in chars)
        size = (p.width, p.height)
    dx, dy = abs(x0 - bbox[0]), abs(top - bbox[1])
    tx, ty, th = text_boxes[0]
    tdy = abs(top - ty)
    return [
        Result(
            "x 座標：box ツリー と pdfplumber が一致する",
            dx < 0.5,
            f"box x0={bbox[0]:.2f}pt / pdfplumber x0={x0:.2f} → 差 {dx:.2f}pt",
            [f"ページサイズ pdfplumber={tuple(round(v, 1) for v in size)}（A4=595.3x841.9pt）"],
        ),
        Result(
            "y 座標：BlockBox の上端は文字の上端と一致しない",
            None,
            f"BlockBox y={bbox[1]:.2f}pt / pdfplumber top={top:.2f} → 差 {dy:.2f}pt（行の余白ぶん）",
        ),
        Result(
            "y 座標：TextBox なら文字の上端に近い",
            tdy < 3.0,
            f"TextBox y={ty:.2f}pt（高さ {th:.2f}pt）/ pdfplumber top={top:.2f} → 差 {tdy:.2f}pt",
            ["文字 bbox が要るところは TextBox を使う。BlockBox は要素の枠として使う"],
        ),
    ]


# --- 補助 ----------------------------------------------------------------------


def extract_text(pdf_bytes: bytes) -> str:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def extract_fonts(pdf_bytes: bytes) -> set[str]:
    import pdfplumber

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        return {c["fontname"].split("+")[-1] for page in pdf.pages for c in page.chars}


PROBES = (
    ("1. box ツリー", probe_box_tree),
    ("2. 目次", probe_toc),
    ("3. 段組", probe_columns),
    ("4. 表", probe_table),
    ("5. 欄外注", probe_footnote),
    ("6. ルビ", probe_ruby),
    ("6. ルビ", probe_ruby_fallback),
    ("7. SVG", probe_svg),
    ("8. 再現性", probe_determinism),
    ("9. 座標系", probe_coordinates),
)


def main() -> int:
    import weasyprint

    print(f"WeasyPrint {weasyprint.__version__}\n")
    all_results: list[tuple[str, Result]] = []
    for group, func in PROBES:
        try:
            for result in func():
                all_results.append((group, result))
        except Exception as exc:  # noqa: BLE001
            all_results.append(
                (group, Result(group, False, f"probe が例外で落ちた: {type(exc).__name__}: {exc}"))
            )

    width = max(len(r.name) for _, r in all_results)
    for _group, r in all_results:
        mark = "OK " if r.ok else ("NG " if r.ok is False else "-- ")
        print(f"{mark} {r.name:{width}}  {r.summary}")
        for note in r.notes:
            print(f"{' ' * (width + 6)}note: {note}")

    failed = [r.name for _, r in all_results if r.ok is False]
    print(f"\n非対応・要注意: {len(failed)} 件" + (f" → {failed}" if failed else ""))
    (ROOT / "scratch").mkdir(exist_ok=True)
    (ROOT / "scratch" / "probe_weasy.json").write_text(
        json.dumps(
            [
                {"group": g, "name": r.name, "ok": r.ok, "summary": r.summary, "notes": r.notes}
                for g, r in all_results
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
