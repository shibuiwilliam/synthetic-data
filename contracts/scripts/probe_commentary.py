"""逐条解説（`commentary`）の枠がページ境界でどうなるかを実測する probe
（`PROMPT.md` P5-2・`docs/rendering.md` §4.6）。

`docs/gotchas.md` は「枠つきブロックはページ境界で割れると続きが版面の外に出ることがある」と
書いている。`.commentary` には `break-inside: avoid` が付いているが、**1 ページに収まらない
長さの解説**では avoid が成り立たない。そのとき何が起きるかを測る：

1. 内容欠落（`verify` の V05。全要素 ≥1 fragment）
2. はみ出し（V06）
3. 何ページに分かれたか、分かれた側の文字が PDF のテキスト層に残るか（V03）

    uv run python scripts/probe_commentary.py
    uv run python scripts/probe_commentary.py --lines 40
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

WORK = Path("content/_probe_commentary")
OUT = Path("/tmp/probe_commentary")
BASE = Path("content/nda-0001")

#: 解説 1 行ぶんの文（このファイルで書き下ろしたオリジナル。意味は持たせない）
LINE = "この条の趣旨は、当事者の間で解釈が分かれやすい点をあらかじめ明らかにしておくことにある。"


def build_probe(lines: int) -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(BASE, WORK)
    part = {
        "target": "body",
        "items": [
            {
                "id": "cmt",
                "kind": "article",
                "title": "解説の見本",
                "children": [
                    {
                        "id": "cmt_p1",
                        "kind": "paragraph",
                        "text": "この条は解説の枠を試すために置いたものである。",
                        "blocks": [
                            {
                                "type": "commentary",
                                "id": "com_probe",
                                "anchor": "cmt",
                                "title": "解説",
                                "text": [f"{i + 1}　{LINE}" for i in range(lines)],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    (WORK / "parts" / "05_cmt.json").write_text(
        json.dumps(part, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    doc = json.loads((WORK / "doc.json").read_text(encoding="utf-8"))
    doc["content_id"] = "_probe_commentary"
    doc["parts"].insert(doc["parts"].index("20_pre.json") + 1, "05_cmt.json")
    (WORK / "doc.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")


def report(lines: int, style_id: str) -> None:
    from keiyaku.build import build
    from keiyaku.compose import load_draft
    from keiyaku.models import dump_json
    from keiyaku.render.weasy import render_source
    from keiyaku.styles import load_style
    from keiyaku.verify.checks import verify_dataset

    build_probe(lines)
    source = build(load_draft(WORK))
    result = render_source(source, load_style(style_id), OUT, render_png=False)
    dump_json(source, result.out_dir / "source.json")
    layout = result.layout
    results = verify_dataset(result.out_dir)

    print(f"\n=== 解説 {lines} 行（{style_id}）===")
    print(f"  ページ数: {result.page_count}")
    entry = layout.elements.get("com_probe")
    if entry is None:
        print("  **解説の枠が layout に無い（＝描画されていない）**")
    else:
        pages = sorted({f.page for f in entry.fragments})
        print(f"  枠: {len(entry.fragments)} fragment / ページ {pages}")
    # 段落ごとに、描かれなかったものを数える
    missing = [f"com_probe__p{i}" for i in range(lines) if f"com_probe__p{i}" not in layout.elements]
    print(f"  描かれなかった行: {len(missing)} / {lines} {missing[:4]}")
    for code in ("V03", "V05", "V06"):
        hits = [r.format().splitlines()[0] for r in results if r.code == code]
        print(f"  {code}: {hits[:2] or '指摘なし'}")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lines", type=int, nargs="*", default=[6, 20, 40, 70])
    parser.add_argument("--style", default="ct-a4-1col-mincho")
    args = parser.parse_args(argv)
    try:
        for n in args.lines:
            report(n, args.style)
    finally:
        if WORK.exists():
            shutil.rmtree(WORK)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
