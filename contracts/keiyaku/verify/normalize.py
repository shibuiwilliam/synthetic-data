"""PDF テキスト層の読み出しと正規化（docs/rendering.md §6.9 の往復検証の土台）。

**正規化ルール（明文化して固定する）**

1. 文字は `page.chars` から直接組み立てる。`extract_text()` は字間から空白を推定して挿入するため、
   原文にない ASCII 空白が混ざる。`chars` 経由なら原文の U+3000 等はそのまま残る（P0 で実測）。
2. 比較時に無視するのは **空白のみ**（ASCII 空白・タブ・改行・U+3000）。
   PDF の行分割位置は組版結果であって原文の情報ではないため。
3. **全角/半角の区別は保持する**（`１` と `1`、`％` と `%`、`（` と `(` は別物として扱う）。
   digit_style（CLAUDE.md §5.2）の検証がここに依存する。
4. Unicode 正規化（NFKC 等）は **かけない**。かけると 3. が壊れる。

P0 時点では pdfplumber のページ座標だけを使う最小版。P2 で `layout.json` の
element 単位の fragments に置き換える（そちらが本番の読み順の定義）。
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal

Region = Literal["header", "footer", "body"]
Column = Literal["left", "right", "span"]

_WHITESPACE = re.compile(r"[\s　]+")


def normalize(text: str) -> str:
    """比較用の正規化。空白だけを落とし、文字種はそのまま残す。"""
    return _WHITESPACE.sub("", text)


@dataclass(frozen=True)
class Line:
    """PDF から読み出した 1 行。"""

    text: str
    top: float
    x0: float
    x1: float
    region: Region
    column: Column


def _cluster_lines(chars: list[dict], tolerance: float = 2.0) -> list[list[dict]]:
    """top 座標が近い文字を 1 行にまとめる。"""
    lines: list[list[dict]] = []
    for char in sorted(chars, key=lambda c: (round(c["top"], 1), c["x0"])):
        if lines and abs(lines[-1][0]["top"] - char["top"]) <= tolerance:
            lines[-1].append(char)
        else:
            lines.append([char])
    return lines


def read_lines(
    page,
    *,
    header_below: float,
    footer_above: float,
    gutter: tuple[float, float] | None = None,
    columns: int = 1,
    tolerance: float = 0.5,
    span_bands: list[tuple[float, float]] | None = None,
) -> list[Line]:
    """1 ページぶんの行を、領域と段を判定したうえで返す。

    `header_below` より上をヘッダ、`footer_above` より下をフッタとみなす（pt・原点左上）。
    `gutter` は段間の空き（x0, x1）。2 段組のとき、同じ y にある左段・右段の行は
    別々の行として切り出す必要があるため、次の規則で判定する。

    1. `span_bands`（段またぎ要素の y 範囲）に入る行は **段またぎ**。
       短いキャプションや見出しは描画幅が段幅に満たないため、文字座標だけでは段内の行と
       区別できない。段またぎ帯は box ツリー側（`keiyaku.layout.extract.span_bands`）から渡す。
    2. 段間に（`tolerance` を超えて）文字がかかっている行も段またぎとみなす。
    3. そうでなく左右両方に文字がある行は、左段の行と右段の行に切り分ける。

    `span_bands` を省いた場合は 2.・3. の幾何ヒューリスティックだけで判定する（精度は落ちる）。
    P2 では `layout.json` の element bbox から読み順を決めるため、この関数は
    検証の二重化（フォールバック）用途に降格する。
    """
    if columns >= 2:
        if gutter is None:
            center = page.width / 2
            gutter = (center - 1.0, center + 1.0)
        gutter_left, gutter_right = gutter
    else:
        gutter_left = gutter_right = page.width / 2

    result: list[Line] = []
    for group in _cluster_lines(page.chars):
        top = min(c["top"] for c in group)
        if top < header_below:
            region: Region = "header"
        elif top > footer_above:
            region = "footer"
        else:
            region = "body"

        if columns < 2 or region != "body":
            result.append(_make_line(group, region, "span"))
            continue

        if span_bands:
            middle = (min(c["top"] for c in group) + max(c["bottom"] for c in group)) / 2
            if any(start <= middle <= end for start, end in span_bands):
                result.append(_make_line(group, region, "span"))
                continue

        # 右段の 1 文字目は段間の右端にぴたりと接するため、浮動小数の誤差ぶんだけ許容する。
        crosses = any(min(c["x1"], gutter_right) - max(c["x0"], gutter_left) > tolerance for c in group)
        left = [c for c in group if c["x1"] <= gutter_left + tolerance]
        right = [c for c in group if c["x0"] >= gutter_right - tolerance]
        if crosses or not (left and right):
            column: Column = "span" if crosses or (left and right) else ("left" if left else "right")
            result.append(_make_line(group, region, column))
        else:
            result.append(_make_line(left, region, "left"))
            result.append(_make_line(right, region, "right"))
    return result


def _make_line(chars: list[dict], region: Region, column: Column) -> Line:
    text = "".join(c["text"] for c in sorted(chars, key=lambda c: c["x0"]))
    return Line(
        text=text,
        top=min(c["top"] for c in chars),
        x0=min(c["x0"] for c in chars),
        x1=max(c["x1"] for c in chars),
        region=region,
        column=column,
    )


def reading_order(lines: list[Line]) -> list[Line]:
    """本文行を読み順に並べ替える（左段 → 右段、段またぎ要素を区切りとする）。

    段またぎ（`column == "span"`）の行は段組の区切りになるため、そこで左段・右段を確定させる。
    ヘッダ・フッタは読み順に含めない（CLAUDE.md §14 / docs/rendering.md §5.7）。
    """
    body = [ln for ln in sorted(lines, key=lambda ln: ln.top) if ln.region == "body"]
    ordered: list[Line] = []
    left: list[Line] = []
    right: list[Line] = []

    def flush() -> None:
        ordered.extend(left)
        ordered.extend(right)
        left.clear()
        right.clear()

    for line in body:
        if line.column == "span":
            flush()
            ordered.append(line)
        elif line.column == "left":
            left.append(line)
        else:
            right.append(line)
    flush()
    return ordered


def page_text(lines: list[Line], region: Region = "body") -> str:
    """領域ごとのテキスト。body は読み順、header/footer は左→右で連結する。"""
    if region == "body":
        return "\n".join(ln.text for ln in reading_order(lines))
    picked = [ln for ln in lines if ln.region == region]
    return "\n".join(ln.text for ln in sorted(picked, key=lambda ln: (ln.top, ln.x0)))
