"""ルビ `<ruby>` が WeasyPrint でどう出るかを測る（docs/remaining_issues.md T5）。

CLAUDE.md §14 が「要probe」としたまま P6 に送ってある項目。
**実測してから可否を決める**（実装してから直すのではなく）。

見るのは 3 点：

1. `<ruby>` / `<rt>` が組めるか（ルビが親文字の上に出るか、後ろに流れるか）
2. **PDF のテキスト層にどう出るか**（「漢字かんじ」と混ざるなら、
   `answer.json` の期待テキストと往復一致しない＝V03 が落ちる）
3. box ツリーから親文字の bbox が取れるか

    uv run python scripts/probe_ruby.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASE = "保険契約者"
READING = "ほけんけいやくしゃ"

CASES: dict[str, str] = {
    "ruby_tag": f"<ruby>{BASE}<rt>{READING}</rt></ruby>",
    "ruby_rp": f"<ruby>{BASE}<rp>（</rp><rt>{READING}</rt><rp>）</rp></ruby>",
    "ruby_display_ruby": (
        f'<span style="display: ruby">{BASE}<span style="display: ruby-text">{READING}</span></span>'
    ),
    "plain": BASE,
}

PAGE_CSS = """
@page { size: A4; margin: 20mm; }
body { font-family: "Noto Serif JP", serif; font-size: 10pt; line-height: 2.0; }
rt { font-size: 5pt; }
"""


def main() -> int:
    import pdfplumber
    from weasyprint import HTML

    out_dir = ROOT / "scratch" / "probe_ruby"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'case':22} {'テキスト層':30} {'読みが混ざる':>12} {'行の高さ pt':>12}")
    for name, markup in CASES.items():
        html = (
            f"<html><head><meta charset='utf-8'><style>{PAGE_CSS}</style></head>"
            f"<body><p id='target'>当会社は、{markup}に対して通知します。</p></body></html>"
        )
        pdf_path = out_dir / f"{name}.pdf"
        document = HTML(string=html).render()
        document.write_pdf(str(pdf_path))

        # box ツリーから対象の bbox を取る
        bbox = None
        for page in document.pages:
            stack = [page._page_box]
            while stack:
                box = stack.pop()
                element = getattr(box, "element", None)
                if element is not None and element.get("id") == "target":
                    bbox = (
                        round(box.position_x * 0.75, 1),
                        round(box.position_y * 0.75, 1),
                        round((box.position_x + box.width) * 0.75, 1),
                        round((box.position_y + box.height) * 0.75, 1),
                    )
                stack.extend(getattr(box, "children", []) or [])

        with pdfplumber.open(str(pdf_path)) as pdf:
            text = (pdf.pages[0].extract_text() or "").replace("\n", "⏎")
        mixed = "はい" if READING in text.replace(" ", "") else "いいえ"
        height = round(bbox[3] - bbox[1], 1) if bbox else -1
        print(f"{name:22} {text[:30]:30} {mixed:>12} {height:>12}")

    print()
    print("判断の材料：")
    print("  - テキスト層に読みが混ざるなら、`answer.json` の期待テキストと往復一致しない。")
    print("    その場合、ルビを入れるには verify の比較から読みを除く仕組みが要る。")
    print("  - 行の高さが `plain` と変わらないなら、ルビは親文字の上に組まれていない。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
