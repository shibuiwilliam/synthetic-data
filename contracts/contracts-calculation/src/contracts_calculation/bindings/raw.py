"""content ディレクトリ（doc.json＋parts）から、単位 ID → 生テキスト（{const:} トークン入り）を作る。

付与モードのスロット抽出は、生テキストの {const:} トークンから定数キーを拾う
（本体は数値を meta.constants に置き、本文はトークンで参照する流儀のため）。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

_CONST_RE = re.compile(r"\{const:([a-z0-9_]+)\}")


def raw_text_map(content_dir: Path) -> dict[str, str]:
    """単位 ID → 生テキスト。節点と表セルの両方を含む。"""
    content_dir = Path(content_dir)
    doc = json.loads((content_dir / "doc.json").read_text(encoding="utf-8"))
    out: dict[str, str] = {}

    def walk_node(node: dict) -> None:
        nid = node.get("id")
        if nid and isinstance(node.get("text"), str):
            out[nid] = node["text"]
        for child in node.get("children", []) or []:
            walk_node(child)
        for block in node.get("blocks", []) or []:
            walk_block(block)

    def walk_block(block: dict) -> None:
        if block.get("type") == "table":
            for row in block.get("grid", []):
                for cell in row:
                    if isinstance(cell, dict) and "id" in cell and isinstance(cell.get("text"), str):
                        out[cell["id"]] = cell["text"]
        for sub in block.get("blocks", []) or []:
            walk_block(sub)

    for name in doc.get("parts", []):
        path = content_dir / "parts" / name
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for item in data.get("items", []):
            walk_node(item)
    return out


def const_keys_in(raw_text: str) -> list[str]:
    return _CONST_RE.findall(raw_text)
