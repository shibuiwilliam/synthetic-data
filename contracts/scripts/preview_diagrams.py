"""図 6 種を 1 枚の PDF/PNG に並べて目視確認する（P3）。

uv run python scripts/preview_diagrams.py     # scratch/diagrams/
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from keiyaku.fonts import font_face_css  # noqa: E402
from keiyaku.models import Figure  # noqa: E402
from keiyaku.render.diagrams import DiagramStyle, render_diagram  # noqa: E402
from keiyaku.styles import load_style  # noqa: E402

FIXTURES = ROOT / "tests" / "fixtures" / "diagrams"
OUT = ROOT / "scratch" / "diagrams"


def main() -> int:
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration

    style = load_style("nl-a4-2col-mincho")
    ds = DiagramStyle.from_style(style)
    blocks = []
    for path in sorted(FIXTURES.glob("*.json")):
        figure = Figure.model_validate(json.loads(path.read_text(encoding="utf-8")))
        result = render_diagram(figure.diagram, ds, figure.id)
        blocks.append(
            f"<figure><figcaption>{figure.diagram.kind}／{figure.caption}"
            f"（{result.width:.0f}×{result.height:.0f}px・ノード {len(result.nodes)}）</figcaption>"
            f"{result.svg}</figure>"
        )
        print(
            f"{figure.diagram.kind:16} {result.width:6.0f}×{result.height:6.0f}px  nodes={len(result.nodes)}"
        )

    html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><style>
{font_face_css()}
body {{ margin: 0; }}
@page {{ size: A4; margin: 12mm; }}
html {{ font-family: 'Noto Serif JP', serif; font-size: 9pt; }}
figure {{ margin: 0 0 8mm; break-inside: avoid; }}
figcaption {{ font-family: 'Noto Sans JP', sans-serif; font-size: 8.5pt; font-weight: 700;
              margin-bottom: 1.5mm; color: #1f4e79; }}
svg {{ display: block; max-width: 100%; }}
</style></head><body>{"".join(blocks)}</body></html>"""

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "preview.html").write_text(html, encoding="utf-8")
    document = HTML(string=html, base_url=str(ROOT)).render(font_config=FontConfiguration())
    pdf_path = OUT / "preview.pdf"
    document.write_pdf(pdf_path)

    import pypdfium2 as pdfium

    pdf = pdfium.PdfDocument(pdf_path)
    for i, page in enumerate(pdf, start=1):
        page.render(scale=150 / 72).to_pil().save(OUT / f"page-{i:03d}.png")
    print(f"\n{pdf_path} / {len(pdf)} ページ")
    return 0


if __name__ == "__main__":
    sys.exit(main())
