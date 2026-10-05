"""本体のスキーマに合うノード・ブロックの組立。

既定の約款JSON（`schema_version` 1.0）と同じ形のノード・ブロックだけを作る。
辞書を手書きせず必ずここを通す。IDや定数名には拡張由来と分かる目印を付けない
（評価対象システムへの手がかりになるため。`CLAUDE.md` 守ること 4）。

本体のモデルは未知フィールドを許さない（`extra="forbid"`）。欄を増やすときは
本体の `yakkan/models.py` を見てからにする。
"""

from __future__ import annotations

from typing import Literal

#: 算式に使える演算子（本体の `FormulaOp`）。括弧と複数行は使えない
FORMULA_OPS = ("＋", "－", "×", "÷", "＝")

#: 列挙用に組んだ表には caption を付けない（本体 lint L18）
NO_CAPTION_SEMANTICS = ("enumeration", "exclusions")


def node(
    nid: str,
    kind: str,
    title: str | None = None,
    text: str | None = None,
    blocks: list[dict] | None = None,
    children: list[dict] | None = None,
    summary: str | None = None,
    kind_label: str | None = None,
) -> dict:
    out: dict = {"id": nid, "kind": kind}
    if title is not None:
        out["title"] = title
    if text is not None:
        out["text"] = text
    if summary is not None:
        out["summary"] = summary
    if blocks:
        out["blocks"] = blocks
    if children:
        out["children"] = children
    if kind_label is not None:
        out["kind_label"] = kind_label
    return out


def paragraph(pid: str, text: str) -> dict:
    return {"type": "paragraph", "id": pid, "text": text}


def cell(
    tid: str,
    r: int,
    c: int,
    text: str,
    role: str = "body",
    align: str | None = None,
    colspan: int = 1,
    rowspan: int = 1,
) -> dict:
    out: dict = {"id": f"{tid}__r{r}c{c}", "text": text, "role": role}
    if align is not None:
        out["align"] = align
    if colspan != 1:
        out["colspan"] = colspan
    if rowspan != 1:
        out["rowspan"] = rowspan
    return out


def merged(into: str) -> dict:
    return {"merged_into": into}


def table(
    tid: str,
    semantic_type: str,
    header: list[str],
    rows: list[list[str]],
    caption: str | None = None,
    notes: tuple[str, ...] = (),
    col_widths: list[float] | None = None,
    header_cols: int = 1,
    stub: bool = True,
    align_body: str = "right",
    records: bool = True,
    records_rows: list[dict] | None = None,
) -> dict:
    """1 行目を表頭、1 列目（`stub=True` のとき）を行見出しにした表。

    `header_cols` は行見出しの列を覆う（本体 lint L17）。列挙用の表に caption は付けない（L18）。
    """
    if semantic_type in NO_CAPTION_SEMANTICS and caption is not None:
        raise ValueError(f"{semantic_type} の表に caption は付けない（本体 lint L18）")
    if any(len(r) != len(header) for r in rows):
        raise ValueError("表の列数が行ごとに違う（本体 lint L05）")
    grid = [[cell(tid, 0, c, h, "header", "center") for c, h in enumerate(header)]]
    for r, row in enumerate(rows, start=1):
        grid.append(
            [
                cell(
                    tid,
                    r,
                    c,
                    t,
                    "stub" if (stub and c == 0) else "body",
                    "left" if (stub and c == 0) else align_body,
                )
                for c, t in enumerate(row)
            ]
        )
    out: dict = {
        "type": "table",
        "id": tid,
        "semantic_type": semantic_type,
        "layout": {
            "header_rows": 1,
            "header_cols": header_cols if stub else 0,
            "col_widths": col_widths or _widths(len(header)),
            "repeat_header": True,
            "style": "grid",
            "span_columns": False,
        },
        "grid": grid,
    }
    if caption is not None:
        out["caption"] = caption
    if records_rows is not None:
        # 見た目（grid）と意味（records）の二重表現。横持ちの表でも意味は 1 キー 1 行で書く
        out["records"] = records_rows
    elif records:
        out["records"] = [dict(zip(header, row, strict=True)) for row in rows]
    if notes:
        out["notes"] = list(notes)
    return out


def _widths(n: int) -> list[float]:
    """1 列目を広め、残りを等分（段幅に収める。表が広いと黙ってはみ出す）。"""
    first = 28.0 if n <= 4 else 22.0
    rest = (100.0 - first) / (n - 1) if n > 1 else 0.0
    return [round(first, 1)] + [round(rest, 1)] * (n - 1)


def formula(fid: str, alt: str, terms: list[tuple[str, object]]) -> dict:
    """`terms` は `("box", 文字列)` `("op", 記号)` `("fraction", (分子, 分母))` の並び。"""
    out_terms: list[dict] = []
    for kind, value in terms:
        if kind == "op":
            if value not in FORMULA_OPS:
                raise ValueError(f"算式に使えない演算子: {value}")
            out_terms.append({"op": value})
        elif kind == "box":
            out_terms.append({"box": str(value)})
        elif kind == "fraction":
            num, den = value  # type: ignore[misc]
            out_terms.append({"fraction": {"num": str(num), "den": str(den)}})
        else:
            raise ValueError(f"算式の項の種類が不正: {kind}")
    layout = "fraction" if any("fraction" in t for t in out_terms) else "inline_boxes"
    return {"type": "formula", "id": fid, "alt": alt, "layout": layout, "terms": out_terms}


def box(
    bid: str,
    title: str | None,
    texts: list[str],
    style: Literal["note", "caution", "example", "margin_note"] = "margin_note",
    anchor: str | None = None,
) -> dict:
    out: dict = {
        "type": "box",
        "id": bid,
        "style": style,
        "blocks": [paragraph(f"{bid}_p{i}", t) for i, t in enumerate(texts, start=1)],
    }
    if title is not None:
        out["title"] = title
    if anchor is not None:
        out["anchor"] = anchor
    elif style == "margin_note":
        raise ValueError("margin_note の囲みには anchor が必要（本体 docs/schema.md §5.6）")
    return out


def footnotes(fid: str, notes: list[str]) -> dict:
    return {
        "type": "footnotes",
        "id": fid,
        "notes": [{"n": i, "text": t} for i, t in enumerate(notes, start=1)],
    }


def list_block(lid: str, style: str, items: list[str]) -> dict:
    return {
        "type": "list",
        "id": lid,
        "style": style,
        "items": [{"id": f"{lid}_i{i}", "text": t} for i, t in enumerate(items, start=1)],
    }


def term(tid: str, word: str, definition: str, index_kana: str) -> dict:
    return {"id": tid, "term": word, "definition": definition, "index_kana": index_kana}
