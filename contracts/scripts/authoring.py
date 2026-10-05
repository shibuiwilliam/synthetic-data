"""執筆用のヘルパ（`content/<cid>/parts/*.json` を組み立てる）。

`docs/authoring_checklist.md` から参照。新ジャンル 6 文書を書くのに使ったものを、
毎回作り直さずに済むよう置いてある（docs/remaining_issues.md S4）。

スキーマの正本は `docs/schema.md` と `keiyaku/models.py`。ここは**素の dict を作るだけ**で、
検証はしない。書いたら `uv run keiyaku lint content/<cid>` を通すこと。

    from scripts.authoring import art, enum_table, table, write

    part = {
        "id": "ch1",
        "kind": "chapter",
        "title": "補償条項",
        "children": [
            art("ch1_a1", "保険金を支払う場合", ["当会社は、…支払います。"]),
        ],
    }
    write("content/foo-0001/parts/ch1.json", part)
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

Cell = dict[str, Any]
Block = dict[str, Any]
Node = dict[str, Any]


def C(  # noqa: N802 - 表を字面どおりに書けるよう 1 文字にしている
    cid: str,
    text: str,
    role: str = "body",
    align: str | None = None,
    rowspan: int = 1,
    colspan: int = 1,
) -> Cell:
    """セル 1 つ。`role` は header / stub / body。"""
    cell: Cell = {"id": cid, "text": text, "rowspan": rowspan, "colspan": colspan, "role": role}
    if align:
        cell["align"] = align
    return cell


def merged(into: str) -> Cell:
    """結合セルに飲み込まれた位置。`into` は左上のセルの id。"""
    return {"merged_into": into}


def enum_table(tid: str, items: list[str], widths: tuple[int, int] = (6, 94)) -> Block:
    """文と一体の列挙表（「次に掲げる事由」の受け）。

    番号の欄は `{auto_label}` を置くだけにする。①②③ は build が振る
    （CLAUDE.md §2「番号は書かせず、計算する」）。**キャプションは付けない**ので、
    「表N」の採番からも外れる。
    """
    return {
        "type": "table",
        "id": tid,
        "caption": None,
        "semantic_type": "enumeration",
        "layout": {
            "header_rows": 0,
            "header_cols": 1,
            "col_widths": list(widths),
            "repeat_header": False,
            "style": "grid",
            "span_columns": False,
        },
        "grid": [
            [
                C(f"{tid}__r{r}c0", "{auto_label}", "stub", align="center"),
                C(f"{tid}__r{r}c1", text),
            ]
            for r, text in enumerate(items)
        ],
    }


def table(
    tid: str,
    caption: str,
    semantic: str,
    header: list[str],
    rows: list[list[str]],
    widths: list[int] | tuple[int, ...],
    notes: list[str] | None = None,
    aligns: dict[int, str] | None = None,
) -> Block:
    """見出し行が 1 行の素直な表。1 列目を stub にし、`records` も一緒に作る。

    `records` があると `header_path`（セルの意味座標）が取れる。L05 が
    「`records` の値が grid に出現すること」を検査する。
    """
    grid = [[C(f"{tid}__r0c{i}", h, "header", align="center") for i, h in enumerate(header)]]
    records: list[dict[str, str]] = []
    for r, row in enumerate(rows, start=1):
        cells: list[Cell] = []
        for i, value in enumerate(row):
            cells.append(
                C(f"{tid}__r{r}c{i}", value, "stub" if i == 0 else "body", align=(aligns or {}).get(i))
            )
        grid.append(cells)
        records.append(dict(zip(header, row, strict=True)))
    block: Block = {
        "type": "table",
        "id": tid,
        "caption": caption,
        "semantic_type": semantic,
        "layout": {
            "header_rows": 1,
            "header_cols": 1,
            "col_widths": list(widths),
            "repeat_header": True,
            "style": "grid",
            "span_columns": False,
        },
        "grid": grid,
        "records": records,
    }
    if notes:
        block["notes"] = notes
    return block


def kana_table(
    tid: str,
    caption: str,
    kana_rows: list[tuple[str, list[str]]],
    label: dict[str, str],
    defs: dict[str, str],
    head: tuple[str, str] = ("用語", "定義"),
) -> Block:
    """五十音の索引列を持つ定義表（docs/reference_structures.md C1）。

    `kana_rows` は [("あ", ["term_a", "term_b"]), …]。索引列は行を結合する。
    """
    grid = [
        [
            C(f"{tid}__r0c0", "", "header", align="center"),
            C(f"{tid}__r0c1", head[0], "header", align="center"),
            C(f"{tid}__r0c2", head[1], "header", align="center"),
        ]
    ]
    row_index = 1
    records: list[dict[str, str]] = []
    for kana, term_ids in kana_rows:
        for n, term_id in enumerate(term_ids):
            if n == 0:
                row = [C(f"{tid}__r{row_index}c0", kana, "stub", align="center", rowspan=len(term_ids))]
            else:
                row = [merged(f"{tid}__r{row_index - n}c0")]
            row += [
                C(f"{tid}__r{row_index}c1", label[term_id], "stub"),
                C(f"{tid}__r{row_index}c2", defs[term_id]),
            ]
            grid.append(row)
            records.append({"五十音": kana, head[0]: label[term_id], head[1]: defs[term_id]})
            row_index += 1
    return {
        "type": "table",
        "id": tid,
        "caption": caption,
        "semantic_type": "definitions",
        "layout": {
            "header_rows": 1,
            "header_cols": 2,
            "col_widths": [6, 20, 74],
            "repeat_header": True,
            "style": "grid",
            "span_columns": False,
        },
        "grid": grid,
        "records": records,
    }


def art(
    aid: str,
    title: str,
    paras: list[str],
    notes: list[dict[str, Any]] | None = None,
    blocks: list[tuple[int, Block]] | None = None,
    items: tuple[int, list[str]] | None = None,
    badges: list[str] | None = None,
) -> Node:
    """条 1 つ。`paras` が項、`items` が (項の index, 号のテキスト)。

    `blocks` は [(項の index, ブロック)]。`notes` は条末脚注（`{fn:n}` と対にする）。
    **見出しにも本文にも番号ラベルを書かない**（L03 が落とす）。
    """
    node: Node = {
        "id": aid,
        "kind": "article",
        "title": title,
        "children": [
            {"id": f"{aid}_p{i + 1}", "kind": "paragraph", "text": text} for i, text in enumerate(paras)
        ],
    }
    if badges:
        node["badges"] = badges
    if items:
        index, texts = items
        node["children"][index]["children"] = [
            {"id": f"{aid}_p{index + 1}_i{k + 1}", "kind": "item", "text": text}
            for k, text in enumerate(texts)
        ]
    if blocks:
        for index, block in blocks:
            node["children"][index].setdefault("blocks", []).append(block)
    if notes:
        node["blocks"] = [{"type": "footnotes", "id": f"fn_{aid}", "notes": notes}]
    return node


def jart(
    aid: str,
    title: str,
    badges: list[str],
    paras: list[str],
    notes: list[dict[str, Any]] | None = None,
    blocks: list[tuple[int, Block]] | None = None,
    items: tuple[int, list[str]] | None = None,
) -> Node:
    """重要事項説明書の大見出し（商品名バッジつき）。`jyusetsu` は条を持たない。"""
    return art(aid, title, paras, notes=notes, blocks=blocks, items=items, badges=badges)


def write(path: str | Path, obj: object) -> None:
    """UTF-8・indent 2・末尾改行で書く（リポジトリの JSON の体裁にそろえる）。"""
    Path(path).write_text(json.dumps(obj, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("書いた", path)
