"""P0 の smoke レンダリング。

日本語 A4・2 段組・@page ヘッダ/フッタ・結合セル表・インライン SVG・丸数字を 1 本の PDF にまとめ、
pypdfium2 で 150dpi の PNG に焼く。本文はすべてこのファイルで書き下ろしたオリジナル文（CLAUDE.md §0.4-1）。

    make smoke        # scratch/smoke/ に出力
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from keiyaku.fonts import font_face_css  # noqa: E402
from keiyaku.layout.extract import iter_fragments  # noqa: E402

OUT_DIR = ROOT / "scratch" / "smoke"
DPI = 150
CHAPTER = "第１章　補償の概要"
FORM_CODE = "Ｄ２６１００１"


@dataclass(frozen=True)
class Expected:
    """往復検証で PDF から読み出せるべき文字列（element id つき）。"""

    id: str
    text: str
    region: str = "body"


# --- 本文（オリジナル）-------------------------------------------------------
PARAS: tuple[Expected, ...] = (
    Expected(
        "p1",
        "当会社は、被保険者が保険期間中に急激かつ偶然な外来の事故によって身体に傷害を被った場合に、"
        "この約款および付帯される特約の規定に従い、保険金を支払います。",
    ),
    Expected(
        "p2",
        "保険契約者または被保険者は、保険契約を締結した後に危険が増加する事実が生じたことを知ったときは、"
        "遅滞なく、その事実を書面等により当会社に知らせなければなりません。"
        "ただし、当会社が知らせを受ける前にその事実が消滅したときを除きます。",
    ),
    Expected(
        "p3",
        "当会社が支払う保険金の種類は、①入院保険金、②手術保険金および③通院保険金とし、"
        "それぞれの支払要件は次項に定めるところによります。",
    ),
    Expected(
        "p4",
        "被保険者が保険期間中に事故に遭われたときは、❶事故の状況、❷傷害の程度および❸受診した医療機関の名称を、"
        "事故の発生の日からその日を含めて30日以内に当会社に通知してください。",
    ),
    Expected(
        "p5",
        "前項の通知を受けた場合において、当会社が必要と認めたときは、"
        "当会社の指定する医師が作成した診断書の提出を求めることがあります。"
        "この場合の費用は、当会社の負担とします。",
    ),
    Expected(
        "p6",
        "この約款に定めのない事項については、日本国の法令に準拠して取り扱います。"
        "当会社と保険契約者との間で生じた紛争については、"
        "その解決のために当会社所定の手続によることができます。",
    ),
)

TABLE_ROWS = (
    ("①", "入院保険金", "事故の日から180日以内に入院されたとき", "入院保険金日額×入院日数"),
    ("②", "手術保険金", "その傷害の治療を直接の目的として手術を受けられたとき", "入院保険金日額×所定の倍率"),
    ("③", "通院保険金", "事故の日から180日以内に通院されたとき", "通院保険金日額×通院日数"),
)

SVG_LABELS = ("事故の発生", "当会社へ通知", "受付")
FIG_CAPTION = "図１　事故発生から通知までの流れ"
TABLE_CAPTION = "表１　保険金の種類と支払額"
NOTE = "（*1）　入院日数には、医師の指示による自宅療養の期間を含みません。"


def expected_strings() -> list[Expected]:
    """PDF のテキスト層に現れるべき文字列を、読み順で並べたもの。"""
    items: list[Expected] = [
        Expected("h1", "傷害保険普通保険約款（検証用サンプル）"),
        Expected("h2", CHAPTER),
    ]
    items += list(PARAS[:3])
    items.append(Expected("tbl_caption", TABLE_CAPTION))
    items.append(Expected("tbl_head", "保険金の種類お支払いする場合お支払いする額"))
    for mark, name, when, amount in TABLE_ROWS:
        items.append(Expected(f"tbl_{mark}", f"{mark}{name}{when}{amount}"))
    items.append(Expected("tbl_note", NOTE))
    items += list(PARAS[3:])
    items.append(Expected("fig_caption", FIG_CAPTION))
    for i, label in enumerate(SVG_LABELS):
        items.append(Expected(f"svg_label{i}", label, region="figure"))
    items.append(Expected("header", CHAPTER, region="header"))
    items.append(Expected("footer_code", FORM_CODE, region="footer"))
    return items


def build_svg() -> str:
    """矩形 2 つと矢印、SVG 内に日本語テキスト（docs/rendering.md §6.7 の最小形）。"""
    return f"""<svg id="fig1_svg" data-kind="figure" viewBox="0 0 420 90" width="100%" role="img">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto">
      <path d="M0,0 L10,5 L0,10 z" fill="#333"/>
    </marker>
  </defs>
  <rect id="fig1_n1" x="6" y="20" width="150" height="50" rx="4"
        fill="#f3f4f6" stroke="#333" stroke-width="1"/>
  <text id="fig1_n1_t" x="81" y="50" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans JP" font-size="13" fill="#111">{SVG_LABELS[0]}</text>
  <line x1="160" y1="45" x2="248" y2="45" stroke="#333" stroke-width="1.5" marker-end="url(#arrow)"/>
  <rect id="fig1_n2" x="252" y="20" width="150" height="50" rx="4"
        fill="#f3f4f6" stroke="#333" stroke-width="1"/>
  <text id="fig1_n2_t" x="327" y="42" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans JP" font-size="13" fill="#111">{SVG_LABELS[1]}</text>
  <text id="fig1_n2_s" x="327" y="60" text-anchor="middle" dominant-baseline="middle"
        font-family="Noto Sans JP" font-size="10" fill="#444">{SVG_LABELS[2]}</text>
</svg>"""


def build_table() -> str:
    rows = []
    for mark, name, when, amount in TABLE_ROWS:
        rows.append(
            f'<tr><th id="tbl1_r{mark}_stub" data-kind="cell" class="stub" scope="row">{mark}</th>'
            f'<td id="tbl1_r{mark}_name" data-kind="cell">{name}</td>'
            f'<td id="tbl1_r{mark}_when" data-kind="cell">{when}</td>'
            f'<td id="tbl1_r{mark}_amount" data-kind="cell">{amount}</td></tr>'
        )
    return f"""<figure id="tbl1" data-kind="table" class="span-all">
  <figcaption id="tbl1_caption" data-kind="caption">{TABLE_CAPTION}</figcaption>
  <table>
    <thead>
      <tr>
        <th id="tbl1_h_kind" data-kind="cell" colspan="2" scope="colgroup">保険金の種類</th>
        <th id="tbl1_h_when" data-kind="cell" rowspan="2" scope="col">お支払いする場合</th>
        <th id="tbl1_h_amount" data-kind="cell" rowspan="2" scope="col">お支払いする額</th>
      </tr>
      <tr>
        <th id="tbl1_h_mark" data-kind="cell" scope="col">記号</th>
        <th id="tbl1_h_name" data-kind="cell" scope="col">名称</th>
      </tr>
    </thead>
    <tbody>{"".join(rows)}</tbody>
  </table>
  <p id="tbl1_note" data-kind="note" class="note">{NOTE}</p>
</figure>"""


def build_html() -> str:
    body = []
    body.append('<h1 id="h1" data-kind="title">傷害保険普通保険約款（検証用サンプル）</h1>')
    body.append(f'<h2 id="h2" data-kind="chapter">{CHAPTER}</h2>')
    for p in PARAS[:3]:
        body.append(f'<p id="{p.id}" data-kind="paragraph">{p.text}</p>')
    body.append(build_table())
    for p in PARAS[3:]:
        body.append(f'<p id="{p.id}" data-kind="paragraph">{p.text}</p>')
    body.append(
        f'<figure id="fig1" data-kind="figure">{build_svg()}'
        f'<figcaption id="fig1_caption" data-kind="caption">{FIG_CAPTION}</figcaption></figure>'
    )
    return f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="utf-8"><title>smoke</title><style>
{font_face_css()}
@page {{
  size: A4;
  margin: 16mm 14mm 18mm 14mm;
  @top-left {{ content: string(chapter); font-family: 'Noto Sans JP'; font-size: 8pt; color: #333; }}
  @bottom-center {{ content: counter(page); font-family: 'Noto Sans JP'; font-size: 8pt; }}
  @bottom-right {{ content: "{FORM_CODE}"; font-family: 'Noto Sans JP'; font-size: 7pt; color: #666; }}
}}
body {{ margin: 0; }}   /* 既定の 8px マージンを消す。残すと本文領域が左右 6pt ずつ狭くなる */
html {{ font-family: 'Noto Serif JP', serif; font-size: 9.5pt; line-height: 1.62;
        line-break: strict; word-break: normal; color: #111; }}
h1 {{ font-family: 'Noto Sans JP', sans-serif; font-size: 13pt; font-weight: 700;
      margin: 0 0 4mm; padding-bottom: 1.5mm; border-bottom: 1.2pt solid #111; column-span: all; }}
h2 {{ font-family: 'Noto Sans JP', sans-serif; font-size: 10.5pt; font-weight: 700;
      string-set: chapter content(); margin: 0 0 3mm; column-span: all; break-after: avoid; }}
.cols {{ column-count: 2; column-gap: 8mm; column-fill: auto; }}
p {{ margin: 0 0 2.4mm; text-align: justify; }}
figure {{ margin: 2mm 0 3mm; break-inside: avoid; }}
figure.span-all {{ column-span: all; }}
figcaption {{ font-family: 'Noto Sans JP', sans-serif; font-size: 8.5pt;
              font-weight: 700; margin-bottom: 1.2mm; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.5pt; }}
th, td {{ border: 0.5pt solid #333; padding: 1.1mm 1.6mm; vertical-align: top; text-align: left; }}
thead th {{ background: #eef1f4; font-family: 'Noto Sans JP', sans-serif; text-align: center; }}
th.stub {{ text-align: center; width: 7mm; font-weight: 400; }}
thead {{ display: table-header-group; }}
tr {{ break-inside: avoid; }}
.note {{ font-size: 8pt; color: #333; margin-top: 1.2mm; }}
svg {{ display: block; }}
</style></head><body>
<div class="cols">
{chr(10).join(body)}
</div>
</body></html>"""


def render(out_dir: Path = OUT_DIR) -> tuple[Path, list[Path]]:
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration

    out_dir.mkdir(parents=True, exist_ok=True)
    html_path = out_dir / "smoke.html"
    pdf_path = out_dir / "smoke.pdf"
    html = build_html()
    html_path.write_text(html, encoding="utf-8")

    font_config = FontConfiguration()
    document = HTML(string=html, base_url=str(ROOT)).render(font_config=font_config)
    # bbox は write_pdf の前に、同じ document から取る（再レイアウトしない：§6.8-5）。
    fragments = iter_fragments(document)
    (out_dir / "fragments.json").write_text(
        json.dumps(
            [
                {
                    "id": f.element_id,
                    "box": f.box_type,
                    "page": f.page,
                    "bbox_pt": [round(f.x0, 2), round(f.y0, 2), round(f.x1, 2), round(f.y1, 2)],
                }
                for f in fragments
            ],
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    document.write_pdf(pdf_path, uncompressed_pdf=False)
    pages = rasterize(pdf_path, out_dir)
    return pdf_path, pages


def rasterize(pdf_path: Path, out_dir: Path, dpi: int = DPI) -> list[Path]:
    import pypdfium2 as pdfium

    paths: list[Path] = []
    pdf = pdfium.PdfDocument(pdf_path)
    for i, page in enumerate(pdf, start=1):
        image = page.render(scale=dpi / 72).to_pil()
        p = out_dir / f"page-{i:03d}.png"
        image.save(p)
        paths.append(p)
    return paths


if __name__ == "__main__":
    pdf, pngs = render()
    print(f"PDF : {pdf}")
    for p in pngs:
        print(f"PNG : {p}")
