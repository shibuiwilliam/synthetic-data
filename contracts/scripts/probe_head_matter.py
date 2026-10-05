"""頭書（大型表）の描画を実測する probe（`PROMPT.md` P4-1・`docs/rendering.md` §4.3）。

測るもの（**憶測で設計を決めないため**。`.claude/rules/render.md`）：

1. **ページをまたぐ表の繰返し表頭** — `repeat_header: true` の thead が 2 ページ目にも出るか、
   出たときに `layout` が 2 回目以降を `repeated: true` として区別できているか。
2. **rowspan がページ境界をまたいだときの継続** — 結合セルが分断されたとき、
   継続側のページに文字が残るか（yakkan の既知の挙動では継続側が空欄になる）。
3. **列数を増やしたときのはみ出し** — 版面幅を超える列数で WeasyPrint が黙ってはみ出すか。

    uv run python scripts/probe_head_matter.py
    uv run python scripts/probe_head_matter.py --rows 40 --cols 8
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WORK = Path("content/_probe_head_matter")
OUT = Path("/tmp/probe_head_matter")
#: 元にする content（頭書を差し込む先）。条文型の最小形でよい。
BASE = Path("content/nda-0001")


def head_matter_table(rows: int, cols: int, *, span_rows: int, span_at: int = 0) -> dict:
    """行見出し列を持つ大型表。`span_rows` 行ぶんの縦結合を中ほどに 1 つ置く。"""
    grid: list[list[dict]] = [
        [
            {"id": f"tbl_head__r0c{c}", "text": f"欄{c}" if c else "項目", "role": "header"}
            for c in range(cols)
        ]
    ]
    span_at = span_at or rows // 2
    for r in range(1, rows + 1):
        row: list[dict] = [{"id": f"tbl_head__r{r}c0", "text": f"項目{r:02d}", "role": "stub"}]
        for c in range(1, cols):
            if c == 1 and span_at <= r < span_at + span_rows:
                if r == span_at:
                    row.append(
                        {
                            "id": f"tbl_head__r{r}c1",
                            "text": f"{span_rows}行にわたる結合セル",
                            "rowspan": span_rows,
                        }
                    )
                else:
                    row.append({"merged_into": f"tbl_head__r{span_at}c1"})
            else:
                row.append({"id": f"tbl_head__r{r}c{c}", "text": f"値{r:02d}-{c}"})
        grid.append(row)
    return {
        "type": "table",
        "id": "tbl_head",
        "semantic_type": "head_matter",
        "layout": {"header_rows": 1, "header_cols": 1, "repeat_header": True, "style": "grid"},
        "grid": grid,
    }


def build_probe(rows: int, cols: int, span_rows: int, span_at: int) -> Path:
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(BASE, WORK)
    part = WORK / "parts" / "05_head.json"
    part.write_text(
        json.dumps(
            {
                "target": "body",
                "items": [
                    {
                        "id": "head",
                        "kind": "head_matter",
                        "kind_label": "頭書",
                        "title": "契約の内容",
                        "children": [
                            {
                                "id": "head_p1",
                                "kind": "paragraph",
                                "text": "本契約の内容は下表のとおりとする。",
                                "blocks": [
                                    head_matter_table(rows, cols, span_rows=span_rows, span_at=span_at)
                                ],
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    doc = json.loads((WORK / "doc.json").read_text(encoding="utf-8"))
    doc["content_id"] = "_probe_head_matter"
    doc["parts"].insert(doc["parts"].index("20_pre.json") + 1, "05_head.json")
    (WORK / "doc.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    return WORK


def report(rows: int, cols: int, span_rows: int, style_id: str, span_at: int) -> None:
    from keiyaku.build import build
    from keiyaku.compose import load_draft
    from keiyaku.render.weasy import render_source
    from keiyaku.styles import load_style

    build_probe(rows, cols, span_rows, span_at)
    source = build(load_draft(WORK))
    result = render_source(source, load_style(style_id), OUT, render_png=False)
    layout = result.layout

    header_ids = [f"tbl_head__r0c{c}" for c in range(cols)]
    print(f"\n=== 行 {rows} / 列 {cols} / 結合 {span_rows} 行 / style {style_id} ===")
    print(f"  ページ数: {result.page_count}")

    pages_of = {}
    repeats = 0
    for element_id in header_ids:
        entry = layout.elements.get(element_id)
        if entry is None:
            print(f"  表頭 {element_id} が layout に無い")
            continue
        pages = sorted({f.page for f in entry.fragments})
        pages_of[element_id] = pages
        repeats += sum(1 for f in entry.fragments if f.repeated)
    print(f"  表頭が出たページ: {pages_of.get(header_ids[0])}")
    total = sum(len(layout.elements[i].fragments) for i in header_ids if i in layout.elements)
    print(f"  repeated 印のついた表頭 fragment: {repeats} / {total}")

    start = span_at or rows // 2
    span_id = f"tbl_head__r{start}c1"
    entry = layout.elements.get(span_id)
    if entry:
        pages = sorted({f.page for f in entry.fragments})
        print(f"  結合セル {span_id}: {len(entry.fragments)} fragment / ページ {pages}")
    else:
        print(f"  **結合セル {span_id} が layout に無い（＝描画されていない）**")
    # 結合が覆う行の、行見出し（stub）がどのページに出たか。
    # 結合セルと stub が別ページに分かれていれば「継続側に文字が残らない」状態。
    stub_pages = {}
    for r in range(start, start + span_rows):
        e = layout.elements.get(f"tbl_head__r{r}c0")
        if e:
            stub_pages[r] = sorted({f.page for f in e.fragments})
    print(f"  結合が覆う行の stub のページ: {stub_pages}")

    # はみ出し：style の版面の右端を超える fragment（verify V06 と同じ基準）
    style = load_style(style_id)
    right = (style.page.width_mm - style.page.margin_mm.right) * 72 / 25.4
    over = [
        (eid, f.page, round(f.bbox[2], 1))
        for eid, e in layout.elements.items()
        for f in e.fragments
        if f.bbox[2] > right + 0.5
    ]
    print(f"  版面右端 {right:.1f}pt を超える fragment: {len(over)} 件 {over[:3]}")

    missing = [i for i in header_ids if i not in layout.elements]
    print(f"  描画されなかった表頭セル: {missing}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rows", type=int, default=30)
    parser.add_argument("--cols", type=int, default=5)
    parser.add_argument("--span", type=int, default=6)
    parser.add_argument("--span-at", type=int, default=0, help="結合を始める行（既定は中ほど）")
    parser.add_argument("--style", default="ct-a4-1col-mincho")
    args = parser.parse_args(argv)
    try:
        report(args.rows, args.cols, args.span, args.style, args.span_at)
    finally:
        if WORK.exists():
            shutil.rmtree(WORK)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
