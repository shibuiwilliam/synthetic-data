"""dataset/<doc_id>/render.html から render.pdf を作る（デバッグ用の再確認）。

canonical な doc.pdf は `yakkan render`（source.json → HTML → WeasyPrint）が唯一の生成元
（CLAUDE.md §0.4-3・§0.4-4）。この render.pdf はそれを置き換えるものではなく、
render.html（配布対象外の中間HTML）を目視・機械チェックしやすい形にするためだけの
デバッグ用副産物として dataset/<doc_id>/ に追加する。

WeasyPrint の呼び出しは yakkan/render/weasy.py の layout_html() / write_pdf() と
同じ形（base_url・pdf_identifier）に合わせ、doc.pdf と条件を揃える。
"""

from __future__ import annotations

import sys
from pathlib import Path

from weasyprint import HTML
from weasyprint.text.fonts import FontConfiguration

PDF_IDENTIFIER = b"yakkan-synth"
ROOT = Path(__file__).resolve().parent.parent
DATASET_DIR = ROOT / "dataset"


def main() -> int:
    targets = sorted(d for d in DATASET_DIR.iterdir() if d.is_dir() and (d / "render.html").exists())
    if not targets:
        print("render.html を持つディレクトリが見つからない", file=sys.stderr)
        return 1

    failures: list[str] = []
    for directory in targets:
        html_path = directory / "render.html"
        pdf_path = directory / "render.pdf"
        html = html_path.read_text(encoding="utf-8")
        try:
            document = HTML(string=html, base_url=str(ROOT)).render(font_config=FontConfiguration())
            document.write_pdf(pdf_path, pdf_identifier=PDF_IDENTIFIER)
            print(f"OK   {directory.name}  ({len(document.pages)} pages)")
        except Exception as exc:  # noqa: BLE001 - 失敗した文書を全部知りたい
            failures.append(directory.name)
            print(f"FAIL {directory.name}  {type(exc).__name__}: {exc}", file=sys.stderr)

    print(f"\n{len(targets) - len(failures)}/{len(targets)} 件成功")
    if failures:
        print("失敗:", ", ".join(failures), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
