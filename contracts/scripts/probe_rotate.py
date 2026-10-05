"""縦組みの表見出し（`transform: rotate`）が使えるかを測る（docs/remaining_issues.md T4）。

CLAUDE.md §14：「縦書きは WeasyPrint 非対応の前提。縦書き表見出しは `transform` で回転（P6）」。
**正解が作れないものは足さない**ので、入れる前に 3 点を実測する：

1. 回転した文字が PDF のテキスト層に残るか（残らなければ往復一致が壊れる）
2. box ツリーから bbox が取れるか。取れるとして、**回転後の見た目の矩形**になるか
3. 列幅が縮まるか（縦組みにする意味があるか）

    uv run python scripts/probe_rotate.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

LABEL = "対人賠償"

CASES: dict[str, str] = {
    "plain": "",
    "rotate": "transform: rotate(-90deg);",
    "rotate_origin": "transform: rotate(-90deg); transform-origin: center;",
    "writing_mode": "writing-mode: vertical-rl;",
}

PAGE_CSS = """
@page { size: A4; margin: 20mm; }
body { font-family: "Noto Serif JP", serif; font-size: 10pt; }
table { border-collapse: collapse; }
th, td { border: 0.5pt solid #000; padding: 2pt 4pt; }
"""


def main() -> int:
    import pdfplumber
    from weasyprint import HTML

    out_dir = ROOT / "scratch" / "probe_rotate"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'case':18} {'テキスト層に残る':>16} {'th の幅 pt':>12} {'th の高さ pt':>12}")
    for name, style in CASES.items():
        html = (
            f"<html><head><meta charset='utf-8'><style>{PAGE_CSS}</style></head><body>"
            f"<table><tr><th id='target' style='{style}'>{LABEL}</th>"
            f"<td>限度額は無制限とします。</td></tr></table></body></html>"
        )
        pdf_path = out_dir / f"{name}.pdf"
        document = HTML(string=html).render()
        document.write_pdf(str(pdf_path))

        size = None
        for page in document.pages:
            stack = [page._page_box]
            while stack:
                box = stack.pop()
                element = getattr(box, "element", None)
                if element is not None and element.get("id") == "target":
                    size = (round(box.width * 0.75, 1), round(box.height * 0.75, 1))
                stack.extend(getattr(box, "children", []) or [])

        with pdfplumber.open(str(pdf_path)) as pdf:
            text = (pdf.pages[0].extract_text() or "").replace("\n", "")
        kept = "はい" if LABEL in text.replace(" ", "") else "いいえ"
        width, height = size or (-1, -1)
        print(f"{name:18} {kept:>16} {width:>12} {height:>12}")

    print()
    print("判断の材料：")
    print("  - テキスト層に残らないなら、その見出しは正解テキストに出せない（V03 が落ちる）。")
    print("  - 回転しても box の幅が縮まないなら、列幅を詰める効果が無い＝入れる理由が無い。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
