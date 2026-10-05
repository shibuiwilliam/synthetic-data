"""素朴な読み取り器（docs/remaining_issues.md T1）。

**`doc.pdf` だけを見て** `docs/evaluation.md` の予測 JSON を作る。
`source.json` / `layout.json` / `answer.json` は開かない。

目的は読み取りモデルを作ることではない（CLAUDE.md §1.4 の非目標）。
`keiyaku eval` の契約——「予測に内部 id は無い前提で、中身だけで突合できる」——が
本当に成り立つかを、**外側から一度通して確かめる**ことである。
規則は素朴なままにしてある。点の高さではなく、
「出せる／出せない」と「採点されるかどうか」を見るための道具。

    uv run python scripts/baseline_reader.py dataset/<doc_id> -o pred.json
    uv run keiyaku eval dataset/<doc_id> --pred pred.json

**分かっている限界**（直さない。素朴さを保つのが目的なので、ここに書いて残す）：

- 段・ページをまたいで続く段落をつながない。2 段組の文書で構造位置のカバー率が伸びない
  いちばんの理由がこれ。
- 曲線を持たない図（matrix・timeline）を図と見分けられない。図の中の文字が本文に混ざる。
- 図のエッジ・経路は復元しない（線の向きを追っていない）。指標は 0 になる。
- 条を持たないジャンル（jyusetsu・契約書では **様式型 `employment`**）の見出しを拾えない。
  見出しが番号を持たないため。outline・citation・列挙がすべて 0 になる（2026-09-28 の実測）。
- **約款型（`contracting`）の見出しを拾えない。** 条見出しが条番号の**上**に括弧書きで来て、
  条番号の行には本文が続く（`article_heading: above`）。行の先頭を見る規則では見出しと本文を
  分けられない。漢数字の条番号そのものは読めるようにした（`KANJI`）。
- QA には答えない。読み取りの器であって、質問応答の器ではない。
"""

from __future__ import annotations

import argparse
import json
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# --- 見出しの見分け -----------------------------------------------------------

DIGITS = "0-9０-９"
#: 漢数字の条番号（「第一条」「第二十三条」）。**約款型はこの体裁**（docs/schema.md §7.1 の
#: `contract-kanji`）。算用数字しか見ていなかったため、`contracting` の 2 文書で
#: 見出しが 1 つも拾えず outline F1 が 0 になっていた（2026-09-28 の P7-1）。
KANJI = "一二三四五六七八九十百"
CHAPTER = re.compile(rf"^第[{DIGITS}{KANJI}]+章")
SECTION = re.compile(rf"^第[{DIGITS}{KANJI}]+節")
ARTICLE = re.compile(rf"^第[{DIGITS}{KANJI}]+条")
APPENDIX = re.compile(rf"^(別表|付表|別紙)[{DIGITS}]+")
#: 項の番号（行頭の全角数字ひとつ）。teikan / group がこの形
PARA_NUM = re.compile(rf"^([{DIGITS}]+)(?=[^{DIGITS}）\).、])")
#: 号の番号
ITEM_NUM = re.compile(rf"^[（(][{DIGITS}]+[）)]")
CIRCLED = re.compile(r"^[①-⑳]")
#: キャプション。**語をつなぐと空白が消える**ので、番号の後の区切りは求めない
TABLE_CAPTION = re.compile(rf"^表[{DIGITS}]+(-[{DIGITS}]+)?[\s　]?(?![{DIGITS}])")
FIGURE_CAPTION = re.compile(rf"^図[{DIGITS}]+(-[{DIGITS}]+)?[\s　]?(?![{DIGITS}])")
TITLE_IN_PARENS = re.compile(r"[（(](.+)[）)]\s*$")


def norm(text: str) -> str:
    return re.sub(r"[\s　]+", "", unicodedata.normalize("NFKC", text or ""))


@dataclass
class Word:
    text: str
    x0: float
    x1: float


@dataclass
class Line:
    text: str
    x0: float
    x1: float
    top: float
    bottom: float
    page: int
    column: int = 0
    #: 語の位置。**表の列を復元する**のに要る（行の文字列だけでは列が分からない）
    words: list[Word] = field(default_factory=list)

    @property
    def bbox(self) -> list[float]:
        return [self.x0, self.top, self.x1, self.bottom]


@dataclass
class Block:
    """1 段落・1 見出し・1 表の行など、予測に出す単位。"""

    lines: list[Line] = field(default_factory=list)

    @property
    def text(self) -> str:
        return "".join(line.text for line in self.lines)

    @property
    def page(self) -> int:
        return self.lines[0].page

    @property
    def bbox(self) -> list[float]:
        return [
            min(x.x0 for x in self.lines),
            min(x.top for x in self.lines),
            max(x.x1 for x in self.lines),
            max(x.bottom for x in self.lines),
        ]


# --- ページの下ごしらえ --------------------------------------------------------


def _gutter(pages_words: list[list[dict]], width: float, height: float) -> tuple[float, float] | None:
    """2 段組のノド（語がほとんど無い縦の帯）。無ければ None。

    段を見分けずに y だけで行を作ると、**左段と右段の行が 1 行につながる**。
    実際に 2 段組の文書で CER 0.41 になった。段を先に分けてから行を作る。

    **文書全体で 1 回だけ決める。** ページごとに測ると、段抜きの表が 1 枚でもあるページで
    ノドが埋まり、そのページだけ 1 段組と誤判定して段が混ざる（横長 A4 の団体保険で
    CER 0.57 になった）。ページの 15% 以下しか語が来ない帯をノドとみなす。
    """
    size = int(width) + 1
    hits = [0] * size
    top_band, bottom_band = height * 0.08, height * 0.92
    for words in pages_words:
        seen = [False] * size
        for word in words:
            if word["top"] < top_band or word["bottom"] > bottom_band:
                continue
            for i in range(max(int(word["x0"]), 0), min(int(word["x1"]) + 1, size)):
                seen[i] = True
        for i, flag in enumerate(seen):
            hits[i] += int(flag)
    # 固定のしきい値では決まらない。段抜きがどれだけあるかは文書ごとに違うので、
    # **窓の中でどれだけ落ち込んでいるか**で判断する（B5 密組みは 11 ページ中 5 ページで
    # ノドがまたがれており、4 割では拾えず 6 割では 1 段組を誤検出する）。
    lo, hi = int(width * 0.30), int(width * 0.70)
    window = sorted(hits[lo:hi])
    if not window:
        return None
    floor, base = window[0], window[len(window) // 2]
    if floor >= base * 0.8:
        return None  # 窓の中が一様に埋まっている＝1 段組
    limit = floor + (base - floor) * 0.2
    best: tuple[int, int] | None = None
    run: int | None = None
    for i in range(lo, hi):
        if hits[i] <= limit:
            run = i if run is None else run
            continue
        if run is not None:
            if best is None or i - run > best[1] - best[0]:
                best = (run, i)
            run = None
    if run is not None and (best is None or hi - run > best[1] - best[0]):
        best = (run, hi)
    if best and best[1] - best[0] >= 8:
        return float(best[0]), float(best[1])
    return None


def _group_lines(words: list[dict], page_number: int, tolerance: float = 2.5) -> list[Line]:
    """同じ段の語を y でまとめて行にする。"""
    rows: list[list[dict]] = []
    for word in sorted(words, key=lambda w: (round(w["top"], 1), w["x0"])):
        for row in rows:
            if abs(row[0]["top"] - word["top"]) <= tolerance:
                row.append(word)
                break
        else:
            rows.append([word])
    out: list[Line] = []
    for row in rows:
        row.sort(key=lambda w: w["x0"])
        out.append(
            Line(
                text="".join(w["text"] for w in row),
                x0=min(w["x0"] for w in row),
                x1=max(w["x1"] for w in row),
                top=min(w["top"] for w in row),
                bottom=max(w["bottom"] for w in row),
                page=page_number,
                words=[Word(w["text"], w["x0"], w["x1"]) for w in row],
            )
        )
    return sorted(out, key=lambda x: (x.top, x.x0))


def _lines_of(page: Any, gutter: tuple[float, float] | None = None) -> list[Line]:
    """ページの行。2 段組なら**段ごとに**行を作り、読み順に並べて返す。

    段をまたぐもの（段抜きの表・見出し）は全幅の行として扱い、
    それを境に「左段 → 右段」を繰り返す——2 段組の紙面を人が読む順。
    """
    words = page.extract_words(use_text_flow=False, keep_blank_chars=False)
    if not words:
        return []
    if gutter is None:
        return _group_lines(words, page.page_number)

    left_edge, right_edge = gutter
    left = [w for w in words if w["x1"] <= left_edge + 1]
    right = [w for w in words if w["x0"] >= right_edge - 1]
    spanning = [w for w in words if w["x0"] < right_edge - 1 and w["x1"] > left_edge + 1]

    left_lines = _group_lines(left, page.page_number)
    right_lines = _group_lines(right, page.page_number)
    span_lines = _group_lines(spanning, page.page_number)
    for line in left_lines:
        line.column = 0
    for line in right_lines:
        line.column = 1
    for line in span_lines:
        line.column = -1

    out: list[Line] = []
    cuts = [line.top for line in span_lines] + [float("inf")]
    taken_left = taken_right = 0
    for i, cut in enumerate(cuts):
        out.extend([x for x in left_lines[taken_left:] if x.top < cut])
        taken_left += sum(1 for x in left_lines[taken_left:] if x.top < cut)
        out.extend([x for x in right_lines[taken_right:] if x.top < cut])
        taken_right += sum(1 for x in right_lines[taken_right:] if x.top < cut)
        if i < len(span_lines):
            out.append(span_lines[i])
    return out


def _figure_bands(page: Any) -> list[tuple[float, float]]:
    """図が占める y の帯。**曲線（矢印・角丸）がある帯**を図とみなす。

    表は直線だけで描かれるので、曲線の有無で分けられる。
    曲線を持たない図（matrix・timeline）は取りこぼす——素朴な読み取り器の限界として残す。
    """
    spans = [(c["top"], c["bottom"]) for c in page.curves]
    if not spans:
        return []
    spans.sort()
    merged: list[list[float]] = [list(spans[0])]
    for top, bottom in spans[1:]:
        if top - merged[-1][1] <= 40:
            merged[-1][1] = max(merged[-1][1], bottom)
        else:
            merged.append([top, bottom])
    # 曲線に重なる直線まで帯を広げる（ノードの箱は直線で描かれる）
    for band in merged:
        for edge in page.edges:
            if edge["bottom"] >= band[0] - 30 and edge["top"] <= band[1] + 30:
                band[0] = min(band[0], edge["top"])
                band[1] = max(band[1], edge["bottom"])
    return [(b[0], b[1]) for b in merged]


def _furniture(pages: list[list[Line]], height: float) -> set[tuple[int, float]]:
    """ヘッダ・フッタ。**本文から離れて浮いている先頭・末尾の行**を落とす。

    人がヘッダを見分けるのと同じやり方にする：ページの一番上（下）の行が、
    次の行との間に本文の行間よりずっと大きい空きを持っていれば、それは furniture。
    「短い行を落とす」「複数ページに出る文字列を落とす」だけだと、
    章見出しのように**本文にも走りヘッダにも出る**ものを取り違える。
    返すのは (ページ, 行の top) の集合。**文字列で照合してはいけない**——
    走りヘッダと同じ文言の見出しが同じページの本文にあると、本文まで落ちる。
    """
    gaps: list[float] = []
    for lines in pages:
        tops = sorted({round(x.top, 1) for x in lines})
        gaps.extend(b - a for a, b in zip(tops, tops[1:], strict=False))
    if not gaps:
        return set()
    gaps.sort()
    typical = gaps[len(gaps) // 2] or 1.0
    threshold = typical * 1.5
    out: set[tuple[int, float]] = set()
    for lines in pages:
        if len(lines) < 3:
            continue
        ordered = sorted(lines, key=lambda x: x.top)
        # 上から：版面の外側にあって、本文との間が広く空いているあいだ furniture
        for i in range(min(2, len(ordered) - 1)):
            if ordered[i].top > height * 0.07:
                break
            if ordered[i + 1].top - ordered[i].top <= threshold:
                break
            out.add((ordered[i].page, round(ordered[i].top, 1)))
        for i in range(len(ordered) - 1, max(len(ordered) - 3, 0), -1):
            if ordered[i].bottom < height * 0.93:
                break
            if ordered[i].top - ordered[i - 1].top <= threshold:
                break
            out.add((ordered[i].page, round(ordered[i].top, 1)))
    return out


# --- 本体 ---------------------------------------------------------------------


class BaselineReader:
    """PDF のテキスト層と罫線だけから予測を組み立てる。"""

    def __init__(self, pdf_path: Path) -> None:
        self.pdf_path = pdf_path
        self.doc_id = pdf_path.parent.name

    def read(self) -> dict[str, Any]:
        import pdfplumber

        pages_out: list[dict[str, Any]] = []
        elements: list[dict[str, Any]] = []
        outline: list[dict[str, Any]] = []
        tables: list[dict[str, Any]] = []
        figures: list[dict[str, Any]] = []
        enumerations: list[dict[str, Any]] = []
        stack: dict[str, str] = {}

        with pdfplumber.open(str(self.pdf_path)) as pdf:
            height = pdf.pages[0].height if pdf.pages else 0.0
            words_of = [page.extract_words(use_text_flow=False, keep_blank_chars=False) for page in pdf.pages]
            gutter = _gutter(words_of, pdf.pages[0].width, height) if pdf.pages else None
            per_page = [_lines_of(page, gutter) for page in pdf.pages]
            furniture = _furniture(per_page, height)
            for page, lines in zip(pdf.pages, per_page, strict=True):
                bands = _figure_bands(page)
                body = [
                    x
                    for x in lines
                    if (x.page, round(x.top, 1)) not in furniture
                    and not any(b[0] <= x.top and x.bottom <= b[1] for b in bands)
                ]
                figures.extend(self._figures(lines, bands))
                blocks = self._blocks(body)
                pages_out.append({"number": page.page_number, "text": "".join(b.text for b in blocks)})
                self._walk(blocks, stack, outline, elements, tables, enumerations)

        return {
            "doc_id": self.doc_id,
            "pages": pages_out,
            "outline": outline,
            "elements": elements,
            "tables": tables,
            "figures": figures,
            "enumerations": enumerations,
        }

    # --- 行 → ブロック ---------------------------------------------------------

    @staticmethod
    def _blocks(lines: list[Line]) -> list[Block]:
        """行を段落にまとめる。見出し・番号つきの行・キャプションで切る。"""
        blocks: list[Block] = []
        # **段ごとに版面の左右を測る。** ページ全体で測ると、2 段組では左段の行がすべて
        # 「右端に届いていない」と見え、1 行ずつ別の段落に切れる（実際に 2 段組の文書で
        # 構造位置のカバー率が 0 になった）。
        edges: dict[int, tuple[float, float]] = {}
        for column in {x.column for x in lines}:
            same = [x for x in lines if x.column == column]
            edges[column] = (min(x.x0 for x in same), max(x.x1 for x in same))
        for line in lines:
            left, right = edges[line.column]
            starts = (
                not blocks
                or blocks[-1].lines[-1].column != line.column
                or CHAPTER.match(line.text)
                or SECTION.match(line.text)
                or ARTICLE.match(line.text)
                or APPENDIX.match(line.text)
                or ITEM_NUM.match(line.text)
                or CIRCLED.match(line.text)
                or TABLE_CAPTION.match(line.text)
                or FIGURE_CAPTION.match(line.text)
                or PARA_NUM.match(line.text)
                or line.x0 > left + 6  # 字下げ
                or blocks[-1].lines[-1].x1 < right - 12  # 前の行が右端まで届いていない
            )
            if starts:
                blocks.append(Block([line]))
            else:
                blocks[-1].lines.append(line)
        return blocks

    # --- ブロック → 予測 -------------------------------------------------------

    def _walk(
        self,
        blocks: list[Block],
        stack: dict[str, str],
        outline: list[dict[str, Any]],
        elements: list[dict[str, Any]],
        tables: list[dict[str, Any]],
        enumerations: list[dict[str, Any]],
    ) -> None:
        index = 0
        while index < len(blocks):
            block = blocks[index]
            text = block.text
            if TABLE_CAPTION.match(text):
                consumed = self._table(blocks, index)
                tables.append(consumed[0])
                # 表題は紙面にあるが、予測の語彙（docs/evaluation.md §3 ＝ NodeKind）に
                # 「caption」は無い。**当てられない種別は null で出す**のが契約
                # （2026-09-28 の P7-1：語彙外の値を出して採点側に弾かれていた）。
                elements.append(self._element(block, stack, None))
                index = consumed[1]
                continue
            heading = self._heading(text)
            if heading:
                kind, label, title = heading
                if kind == "chapter":
                    stack.clear()
                    stack["chapter"] = label
                elif kind == "section":
                    stack.pop("article", None)
                    stack.pop("paragraph", None)
                    stack["section"] = label
                elif kind in ("article", "appendix"):
                    stack.pop("paragraph", None)
                    stack["article"] = label
                outline.append(
                    {
                        "label": label,
                        "title": title,
                        "heading_text": text,
                        "kind": kind,
                        "page": block.page,
                        "citation": self._citation(stack),
                    }
                )
                elements.append(self._element(block, stack, kind))
                index += 1
                continue
            matched = PARA_NUM.match(text)
            if matched:
                stack["paragraph"] = matched.group(1)
            elements.append(self._element(block, stack, "paragraph"))
            if CIRCLED.match(text) or ITEM_NUM.match(text):
                items = [text]
                while index + 1 < len(blocks) and (
                    CIRCLED.match(blocks[index + 1].text) or ITEM_NUM.match(blocks[index + 1].text)
                ):
                    index += 1
                    items.append(blocks[index].text)
                    elements.append(self._element(blocks[index], stack, "item"))
                if len(items) >= 2:
                    enumerations.append({"citation": self._citation(stack), "items": items})
            index += 1

    @staticmethod
    def _heading(text: str) -> tuple[str, str, str] | None:
        for kind, pattern in (
            ("chapter", CHAPTER),
            ("section", SECTION),
            ("appendix", APPENDIX),
            ("article", ARTICLE),
        ):
            matched = pattern.match(text)
            if not matched:
                continue
            label = matched.group(0)
            rest = text[len(label) :].strip("　 ")
            in_parens = TITLE_IN_PARENS.match(rest)
            title = in_parens.group(1) if in_parens else rest
            # 本文が続く行（「第3条の規定により…」）は見出しではない
            if len(title) > 30:
                return None
            return kind, label, title
        return None

    @staticmethod
    def _citation(stack: dict[str, str]) -> str:
        parts = [stack.get(k, "") for k in ("chapter", "section", "article", "paragraph")]
        return " ".join(p for p in parts if p)

    def _element(self, block: Block, stack: dict[str, str], kind: str | None) -> dict[str, Any]:
        return {
            "text": block.text,
            "page": block.page,
            "kind": kind,
            "citation": self._citation(stack),
            "bbox": [round(v, 2) for v in block.bbox],
        }

    # --- 表 -------------------------------------------------------------------

    @staticmethod
    def _cells_of(line: Line, gap: float = 5.0) -> list[Word]:
        """1 行の語を、語間の空きでセルにまとめる。"""
        cells: list[Word] = []
        for word in sorted(line.words, key=lambda w: w.x0):
            if cells and word.x0 - cells[-1].x1 <= gap:
                cells[-1] = Word(cells[-1].text + word.text, cells[-1].x0, word.x1)
            else:
                cells.append(Word(word.text, word.x0, word.x1))
        return cells

    @classmethod
    def _table(cls, blocks: list[Block], start: int) -> tuple[dict[str, Any], int]:
        """キャプションの次から、**列の位置が揃っている行**を表として組み直す。

        罫線は style によって引かれたり引かれなかったりするので当てにしない。
        見出し行のセルの x 範囲を列の目安にし、以降の行の語を近い列へ寄せる
        ——罫線の無い表を人が読むときのやり方。
        """
        caption = blocks[start].text
        matched = TABLE_CAPTION.match(caption)
        label = (matched.group(0) if matched else caption).strip("　 ")

        rows: list[list[Word]] = []
        index = start + 1
        while index < len(blocks):
            block = blocks[index]
            if (
                TABLE_CAPTION.match(block.text)
                or FIGURE_CAPTION.match(block.text)
                or CHAPTER.match(block.text)
                or ARTICLE.match(block.text)
            ):
                break
            for line in block.lines:
                cells = cls._cells_of(line)
                if len(cells) < 2 and rows:
                    break
                rows.append(cells)
            else:
                index += 1
                continue
            index += 1
            break

        if not rows:
            return {"caption_label": label, "grid": [], "cells": []}, index

        # 見出し行のセルの中心を列の基準にする
        anchors = [(c.x0 + c.x1) / 2 for c in rows[0]]
        grid: list[list[str]] = []
        for cells in rows:
            row = [""] * len(anchors)
            for cell in cells:
                center = (cell.x0 + cell.x1) / 2
                col = min(range(len(anchors)), key=lambda i: abs(anchors[i] - center))
                row[col] = (row[col] + cell.text) if row[col] else cell.text
            grid.append(row)

        header = grid[0]
        cells_out = [
            {
                "row_headers": [row[0]],
                "col_headers": [header[col]],
                "value": value,
            }
            for row in grid[1:]
            for col, value in enumerate(row[1:], start=1)
            if value
        ]
        return {"caption_label": label, "grid": grid, "cells": cells_out}, index

    # --- 図 -------------------------------------------------------------------

    @staticmethod
    def _figures(lines: list[Line], bands: list[tuple[float, float]]) -> list[dict[str, Any]]:
        """図の帯にある文字をノードとして出す。**エッジは復元しない**。"""
        out: list[dict[str, Any]] = []
        for i, (top, bottom) in enumerate(bands):
            inside = [x for x in lines if top <= x.top and x.bottom <= bottom]
            caption = next(
                (x.text for x in lines if FIGURE_CAPTION.match(x.text) and abs(x.top - bottom) < 40),
                "",
            )
            matched = FIGURE_CAPTION.match(caption) if caption else None
            label = matched.group(0).strip("　 ") if matched else None
            out.append(
                {
                    "caption_label": label,
                    "nodes": [{"id": f"n{i}_{j}", "label": x.text} for j, x in enumerate(inside)],
                    "edges": [],
                    "paths": [],
                }
            )
        return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset_doc", type=Path, help="dataset/<doc_id> のパス")
    parser.add_argument("-o", "--out", type=Path, default=None, help="予測 JSON の書き出し先")
    args = parser.parse_args()

    pdf_path = args.dataset_doc / "doc.pdf"
    prediction = BaselineReader(pdf_path).read()
    out = args.out or (args.dataset_doc.parent / f"{args.dataset_doc.name}.pred.json")
    out.write_text(json.dumps(prediction, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        f"書いた {out} / ページ {len(prediction['pages'])}・見出し {len(prediction['outline'])}"
        f"・要素 {len(prediction['elements'])}・表 {len(prediction['tables'])}"
        f"・図 {len(prediction['figures'])}・列挙 {len(prediction['enumerations'])}"
    )


if __name__ == "__main__":
    main()
