"""本体スキーマのノード・ブロックの組立（辞書を手書きせず、ここを通す）。"""

from __future__ import annotations

from ..patterns.base import RuleDraft, TableDraft


def make_table(table_id: str, draft: TableDraft) -> dict:
    """段階表 → 本体の Table ブロック。1 行目が見出し、1 列目が区分（stub）。"""
    grid: list[list[dict]] = [
        [
            {"id": f"{table_id}__r0c0", "text": draft.col_labels[0], "role": "header"},
            {"id": f"{table_id}__r0c1", "text": draft.col_labels[1], "role": "header"},
        ]
    ]
    for i, row in enumerate(draft.rows, start=1):
        grid.append(
            [
                {"id": f"{table_id}__r{i}c0", "text": row.label, "role": "stub"},
                {"id": f"{table_id}__r{i}c1", "text": row.value_text, "role": "body"},
            ]
        )
    return {
        "type": "table",
        "id": table_id,
        "caption": draft.caption,
        "semantic_type": draft.semantic_type,
        "layout": {"header_rows": 1, "header_cols": 1, "repeat_header": False, "style": "grid"},
        "grid": grid,
    }


def make_article(
    article_id: str, draft: RuleDraft, table_ids: dict[str, str], ref_ids: dict[str, str] | None = None
) -> tuple[dict, dict]:
    """条ノードと、〈仕様の要素 → 単位 ID〉の対応を作る。

    返り値: (node, unit_info)
      unit_info = {
        "paragraph_ids": [...],
        "param_units": {param名: 段落ID},
        "table_value_cells": {表名: [値セルID, ...]},
      }
    """
    children: list[dict] = []
    paragraph_ids: list[str] = []
    for i, para in enumerate(draft.paragraphs, start=1):
        pid = f"{article_id}_p{i}"
        paragraph_ids.append(pid)
        if isinstance(para, dict):
            text = para["text"]
            items = para.get("items", [])
        else:
            text, items = para, []
        # {TBL:name} → {ref:表ID または 別紙ID}
        for name, rid in (ref_ids or table_ids).items():
            text = text.replace(f"{{TBL:{name}}}", f"{{ref:{rid}}}")
        node: dict = {"id": pid, "kind": "paragraph", "text": text}
        if items:
            node["children"] = [
                {"id": f"{pid}_i{j}", "kind": "item", "text": item_text}
                for j, item_text in enumerate(items, start=1)
            ]
        children.append(node)

    # 表は導入文を持つ段落の blocks に付ける（L22）。table_ids に無い表は別紙に置かれる（M5）
    table_value_cells: dict[str, list[str]] = {}
    attach = {name: td for name, td in draft.tables.items() if name in table_ids}
    if attach:
        anchor = children[draft.table_paragraph if draft.table_paragraph is not None else 0]
        anchor.setdefault("blocks", [])
        for name, tdraft in attach.items():
            tid = table_ids[name]
            anchor["blocks"].append(make_table(tid, tdraft))
            table_value_cells[name] = [f"{tid}__r{i}c1" for i in range(1, len(tdraft.rows) + 1)]

    for para_idx, fig in draft.figure_blocks:
        children[para_idx].setdefault("blocks", []).append(fig)

    param_units: dict[str, str] = {}
    for pname in draft.params:
        token = f"{{const:{pname}}}"
        for pid, para in zip(paragraph_ids, draft.paragraphs):
            text = para["text"] if isinstance(para, dict) else para
            if token in text:
                param_units[pname] = pid
                break

    node = {"id": article_id, "kind": "article", "title": draft.title, "children": children}
    info = {
        "paragraph_ids": paragraph_ids,
        "param_units": param_units,
        "table_value_cells": table_value_cells,
    }
    return node, info


def make_appendix(appendix_id: str, title: str, intro_text: str, table_block: dict) -> dict:
    """別紙（段階表の分離先）。中身は導入文 1 段落＋表。"""
    section_id = f"{appendix_id}_s1"
    return {
        "id": appendix_id,
        "kind": "appendix",
        "kind_label": "別紙",
        "title": title,
        "children": [
            {
                "id": section_id,
                "kind": "appendix_section",
                "title": "",
                "children": [
                    {
                        "id": f"{section_id}_p1",
                        "kind": "paragraph",
                        "text": intro_text,
                        "blocks": [table_block],
                    }
                ],
            }
        ],
    }


def make_example_box(box_id: str, anchor_id: str, text: str) -> dict:
    """計算例の箱（説明。規範ではない）。margin_note は anchor が必須。"""
    return {
        "type": "box",
        "id": box_id,
        "style": "margin_note",
        "anchor": anchor_id,
        "title": "参考（計算例）",
        "blocks": [{"type": "paragraph", "id": f"{box_id}_p1", "text": text}],
    }
