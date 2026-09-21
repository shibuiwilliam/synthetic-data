"""pdfplumber の文字列を期待テキストに系列整列して要素 bbox を復元する（docs/rendering.md §6.8-4）。

box ツリー（主経路）が壊れたときの保険であり、同時に **主経路の検算** でもある。
`verify` は両経路の bbox を突き合わせる。

**突合の基準（docs/decisions.md 2026-09-21）**：IoU ではなく「box ツリーの bbox が
pdfplumber の文字群を内包するか（許容 1pt）」。probe で x は 0.00pt 一致するが
y は行の余白ぶん 4〜5pt ずれるため、IoU 0.9 は原理的に達成できない。
"""

from __future__ import annotations

import difflib
from dataclasses import dataclass

from yakkan.models import BBox
from yakkan.verify.normalize import normalize

#: 内包判定の許容（pt）
CONTAIN_TOLERANCE = 1.5


@dataclass(frozen=True)
class AlignedElement:
    element_id: str
    page: int
    bbox: BBox
    text: str


def page_chars(page) -> list[dict]:
    """pdfplumber のページから、空白を除いた文字を読み順（上→左）で返す。"""
    return [c for c in page.chars if not c["text"].isspace()]


def align_page(page, expected: list[tuple[str, str]]) -> list[AlignedElement]:
    """1 ページぶんの文字列を期待テキスト列に整列する。

    `expected` は (element_id, 期待テキスト) を読み順に並べたもの。
    戻り値は、実際に一致した文字群から求めた要素ごとの bbox。
    """
    chars = page_chars(page)
    actual = "".join(c["text"] for c in chars)
    wanted = "".join(normalize(text) for _, text in expected)

    matcher = difflib.SequenceMatcher(None, actual, wanted, autojunk=False)
    # 期待テキスト上の位置 → element_id
    owner: list[str] = []
    for element_id, text in expected:
        owner.extend([element_id] * len(normalize(text)))

    spans: dict[str, list[int]] = {}
    for a_start, b_start, size in matcher.get_matching_blocks():
        for offset in range(size):
            element_id = owner[b_start + offset]
            spans.setdefault(element_id, []).append(a_start + offset)

    out: list[AlignedElement] = []
    for element_id, indexes in spans.items():
        picked = [chars[i] for i in indexes if i < len(chars)]
        if not picked:
            continue
        out.append(
            AlignedElement(
                element_id=element_id,
                page=page.page_number,
                bbox=(
                    min(c["x0"] for c in picked),
                    min(c["top"] for c in picked),
                    max(c["x1"] for c in picked),
                    max(c["bottom"] for c in picked),
                ),
                text="".join(c["text"] for c in picked),
            )
        )
    return out


def contains(outer: BBox, inner: BBox, tolerance: float = CONTAIN_TOLERANCE) -> bool:
    """`outer` が `inner` をほぼ包んでいるか。"""
    return (
        outer[0] - tolerance <= inner[0]
        and outer[1] - tolerance <= inner[1]
        and outer[2] + tolerance >= inner[2]
        and outer[3] + tolerance >= inner[3]
    )
