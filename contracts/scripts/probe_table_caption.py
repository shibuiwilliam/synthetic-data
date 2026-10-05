"""表題（caption）が表本体とページ・段で離れないかを測る（docs/shared_fixes.md B1）。

`<figcaption>` を表の外に置く現行の形と、`<caption>` を `<table>` の中に置く形を、
表の直前の本文の長さを少しずつ変えながら描き比べる。
「表題と表の 1 行目が別のページ／別の段に出た回数」を数える。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FILLER = "なお、この場合の取扱いについては、当会社が別に定めるところによるものとします。"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--style", default="nl-a4-2col-mincho")
    parser.add_argument("--steps", type=int, default=24)
    parser.add_argument("--stride", type=int, default=18)
    args = parser.parse_args()

    import tempfile

    from keiyaku.build import build
    from keiyaku.compose import load_draft
    from keiyaku.lint.walk import iter_blocks
    from keiyaku.models import ParagraphBlock, Table
    from keiyaku.render.weasy import render_source
    from keiyaku.styles import load_style

    style = load_style(args.style)
    base = load_draft(ROOT / "tests" / "golden" / "sample_min")

    # 表の直前の段落を探す（字数を伸ばして表の位置をずらす）
    target_id = None
    for block, _owner, _article in iter_blocks(base):
        if isinstance(block, ParagraphBlock):
            target_id = block.id
        if isinstance(block, Table) and (block.caption or "").strip():
            break
    assert target_id, "表の直前の段落が見つからない"

    split = 0
    with tempfile.TemporaryDirectory() as tmp:
        for step in range(args.steps):
            draft = base.model_copy(deep=True)
            for block, _owner, _article in iter_blocks(draft):
                if isinstance(block, ParagraphBlock) and block.id == target_id:
                    block.text = block.text + "　" + FILLER[: args.stride] * (step % 3 + 1) * (step // 3 + 1)
                    break
            source = build(draft)
            out = Path(tmp) / f"s{step}"
            try:
                result = render_source(source, style, out, render_png=False)
            except Exception as exc:  # noqa: BLE001 - 帯に当たることがある
                print(f"{step:3d} 描画失敗 {type(exc).__name__}")
                continue
            layout = result.layout
            for tid, caption_id in _caption_pairs(source):
                table = layout.elements.get(tid)
                caption = layout.elements.get(caption_id)
                if not table or not caption:
                    continue
                cpage = caption.fragments[0].page
                cx = caption.fragments[0].bbox[0]
                tpage = table.fragments[0].page
                tx = table.fragments[0].bbox[0]
                if cpage != tpage or abs(cx - tx) > 1.0:
                    split += 1
                    print(f"{step:3d} {tid}: 表題 p{cpage} x={cx:.0f} / 表 p{tpage} x={tx:.0f}")
    print(f"離れた回数 {split} / 試行 {args.steps}")
    return 0


def _caption_pairs(source) -> list[tuple[str, str]]:
    from keiyaku.lint.walk import iter_blocks
    from keiyaku.models import Table

    return [
        (b.id, f"{b.id}__caption")
        for b, _o, _a in iter_blocks(source)
        if isinstance(b, Table) and (b.caption or "").strip()
    ]


if __name__ == "__main__":
    raise SystemExit(main())
