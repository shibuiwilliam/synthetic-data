"""段組レイアウトの「帯」を測る probe（shared_fixes A1 / D2）。

実文書の本文を少しずつ伸ばして配置をずらし、次の 2 つを数える。

1. **内容欠落**（`verify` の V03／V05）— 脚注や表が PDF から落ちる事象
2. **`RenderLayoutError`**（WeasyPrint の AssertionError / IndexError）が出る字数の帯

`docs/gotchas.md` は「同じ内容でも数十字ぶん増減させると通ることが多い」と書いているが、
それが**どれくらいの幅の帯なのか**を実測するのがこの probe の目的。

    uv run python scripts/probe_layout_band.py                       # 既定（sample_min・A4 2段）
    uv run python scripts/probe_layout_band.py --content content/auto-0001 --style nl-b5-2col-dense
    uv run python scripts/probe_layout_band.py --steps 60 --pad 8
"""

from __future__ import annotations

import argparse
import json
import shutil
import traceback
from pathlib import Path
from typing import Any

WORK = Path("content/_probe_layout_band")
OUT = Path("/tmp/probe_layout_band")
#: 1 単位ぶんの詰め物。約款らしく、かつ意味を持たない文にする。
PAD = "この場合の取扱いは別に定めます。"


def _prepare(src: Path, units: int, pad: str) -> None:
    if WORK.exists():
        shutil.rmtree(WORK)
    shutil.copytree(src, WORK)
    doc = json.loads((WORK / "doc.json").read_text(encoding="utf-8"))
    doc["content_id"] = WORK.name
    (WORK / "doc.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

    target = sorted((WORK / "parts").glob("2*.json"))[0]
    data = json.loads(target.read_text(encoding="utf-8"))
    done = False

    def patch(obj: Any) -> None:
        nonlocal done
        if isinstance(obj, dict):
            if not done and obj.get("kind") == "paragraph" and isinstance(obj.get("text"), str):
                obj["text"] += pad * units
                done = True
            for value in obj.values():
                patch(value)
        elif isinstance(obj, list):
            for value in obj:
                patch(value)

    patch(data)
    target.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def _run(src: Path, style_id: str, units: int, pad: str) -> tuple[str, int]:
    """(状態, V03/V05 の件数) を返す。"""
    from yakkan.build import build
    from yakkan.compose import load_draft
    from yakkan.render.weasy import render_source
    from yakkan.styles import load_style
    from yakkan.verify.checks import verify_dataset

    _prepare(src, units, pad)
    source = build(load_draft(WORK))
    try:
        render_source(source, load_style(style_id), OUT, render_png=False)
    except Exception as error:  # noqa: BLE001 — どこで落ちたかを知りたい
        cause = error.__cause__ or error.__context__ or error
        tb = traceback.extract_tb(cause.__traceback__)
        where = f"{Path(tb[-1].filename).name}:{tb[-1].lineno}" if tb else "?"
        return f"{type(cause).__name__} @ {where}", -1
    results = verify_dataset(OUT)
    lost = [r for r in results if r.code in ("V03", "V05") and r.severity == "error"]
    if lost:
        return "内容欠落", len(lost)
    others = [r for r in results if r.severity == "error"]
    return ("他の verify error" if others else "ok"), len(others)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--content", type=Path, default=Path("tests/golden/sample_min"))
    parser.add_argument("--style", default="nl-a4-2col-mincho")
    parser.add_argument("--steps", type=int, default=40, help="何単位まで伸ばすか")
    parser.add_argument("--pad", default=PAD, help="1 単位ぶんの詰め物")
    args = parser.parse_args()

    rows: list[tuple[int, str, int]] = []
    for units in range(args.steps + 1):
        state, count = _run(args.content, args.style, units, args.pad)
        rows.append((units, state, count))
        mark = "" if state == "ok" else f"  ← {state}"
        print(f"  {units:3d} 単位（{units * len(args.pad):5d} 字）{mark}")

    lost = [r for r in rows if r[1] == "内容欠落"]
    layout = [r for r in rows if "Error" in r[1]]
    print(f"\n試行 {len(rows)} 通り（1 単位 = {len(args.pad)} 字、{args.content.name} / {args.style}）")
    print(f"  内容欠落：            {len(lost)} 通り {[r[0] for r in lost][:10]}")
    print(f"  RenderLayoutError：   {len(layout)} 通り {[r[0] for r in layout][:10]}")
    if layout:
        bands, start, prev = [], layout[0][0], layout[0][0]
        for units, _s, _c in layout[1:]:
            if units != prev + 1:
                bands.append((start, prev))
                start = units
            prev = units
        bands.append((start, prev))
        widths = [(b - a + 1) * len(args.pad) for a, b in bands]
        print(f"  帯の数 {len(bands)} / 帯の幅（字）{widths}")
        print("  → 帯を**またぐ**だけの増減が要る。帯の中で数字を振っても通らない。")
    if WORK.exists():
        shutil.rmtree(WORK)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
