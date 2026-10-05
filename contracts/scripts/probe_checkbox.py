"""選択欄の記号を実測する probe（`PROMPT.md` P5-1・`docs/schema.md` §11.2）。

同梱フォントの被覆だけでなく、**実際に描いたときに何が起きるか**を測る：

1. 本文フォントに無い記号（`☑` U+2611）はフォールバックで描かれる。
   そのとき **V08（フォールバック整列）が何を言うか**、字形の大きさが本文とどれだけ違うか。
2. 本文フォントにある記号（`■` `□`）なら、フォールバックが起きないこと。

    uv run python scripts/probe_checkbox.py
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WORK = Path("content/_probe_checkbox")
OUT = Path("/tmp/probe_checkbox")
BASE = Path("content/nda-0001")

#: 試す組み合わせ（選択済み, 未選択）
PAIRS = [("☑", "□"), ("■", "□"), ("〇", "－")]


def build_probe(marks: tuple[str, str]) -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(BASE, WORK)
    on, off = marks
    rows = [
        ("契約期間の定め", on, "期間の定めなし", off, "期間の定めあり"),
        ("就業の場所", off, "本社", on, "支社"),
        ("所定時間外労働", on, "有", off, "無"),
    ]
    grid = [
        [
            {"id": "tbl_cb__r0c0", "text": "項目", "role": "header"},
            {"id": "tbl_cb__r0c1", "text": "選択１", "role": "header"},
            {"id": "tbl_cb__r0c2", "text": "内容１", "role": "header"},
            {"id": "tbl_cb__r0c3", "text": "選択２", "role": "header"},
            {"id": "tbl_cb__r0c4", "text": "内容２", "role": "header"},
        ]
    ]
    for r, row in enumerate(rows, 1):
        grid.append(
            [{"id": f"tbl_cb__r{r}c0", "text": row[0], "role": "stub"}]
            + [{"id": f"tbl_cb__r{r}c{c}", "text": v} for c, v in enumerate(row[1:], 1)]
        )
    part = {
        "target": "body",
        "items": [
            {
                "id": "cbx",
                "kind": "article",
                "title": "選択欄の見本",
                "children": [
                    {
                        "id": "cbx_p1",
                        "kind": "paragraph",
                        "text": "選択の状態は下表のとおりとする。",
                        "blocks": [
                            {
                                "type": "table",
                                "id": "tbl_cb",
                                "semantic_type": "form_fields",
                                "caption": "選択欄の見本",
                                "layout": {
                                    "header_rows": 1,
                                    "header_cols": 1,
                                    "repeat_header": True,
                                    "style": "grid",
                                },
                                "grid": grid,
                            }
                        ],
                    }
                ],
            }
        ],
    }
    (WORK / "parts" / "05_cbx.json").write_text(
        json.dumps(part, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    doc = json.loads((WORK / "doc.json").read_text(encoding="utf-8"))
    doc["content_id"] = "_probe_checkbox"
    doc["parts"].insert(doc["parts"].index("20_pre.json") + 1, "05_cbx.json")
    (WORK / "doc.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def report(marks: tuple[str, str], style_id: str) -> None:
    from keiyaku.build import build
    from keiyaku.compose import load_draft
    from keiyaku.lint.runner import lint_content
    from keiyaku.models import dump_json
    from keiyaku.render.weasy import render_source
    from keiyaku.styles import load_style
    from keiyaku.verify.checks import verify_dataset

    build_probe(marks)
    findings = [f for f in lint_content(WORK, quick=False) if f.code == "L07"]
    source = build(load_draft(WORK))
    result = render_source(source, load_style(style_id), OUT, render_png=False)
    dump_json(source, result.out_dir / "source.json")
    results = verify_dataset(result.out_dir)

    print(f"\n=== {marks[0]} / {marks[1]}（{style_id}）===")
    print(f"  L07（フォント被覆）: {[f.format() for f in findings] or '指摘なし'}")
    for code in ("V02", "V03", "V08"):
        hits = [r.format() for r in results if r.code == code]
        print(f"  {code}: {hits or '指摘なし'}")
    # PDF に埋め込まれたフォント（フォールバックが起きたかの実測）
    import subprocess

    out = subprocess.run(
        ["pdffonts", str(result.pdf_path)], capture_output=True, text=True
    ).stdout.splitlines()
    names = [ln.split()[0] for ln in out[2:] if ln.strip()]
    print(f"  埋め込みフォント: {sorted(set(names))}")


def main(argv: list[str]) -> int:
    style_id = argv[0] if argv else "ct-a4-1col-gothic"
    try:
        for marks in PAIRS:
            report(marks, style_id)
    finally:
        if WORK.exists():
            shutil.rmtree(WORK)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
