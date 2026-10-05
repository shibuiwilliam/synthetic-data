"""約款JSONへの追加（パッチ）の記録と適用。

追加は**操作の列**として記録する。何をどこに足したかが後から追え、
既存の文言を書き換える操作を持たないので、既定の約款を壊さない。

| 操作 | 内容 |
|---|---|
| `add_constant` | `meta.constants` に定数を足す |
| `add_term` | `defined_terms` に定義語を足す |
| `add_node` | 条・項・号・特約・別表を足す |
| `add_block` | 既存または追加したノードに、表・算式・図・囲み・脚注を足す |
| `add_index_row` | 目的別もくじ・特約一覧に行を足す |
"""

from __future__ import annotations

import copy
from typing import Any

OPS = ("add_constant", "add_term", "add_node", "add_block", "add_index_row")


class PatchError(ValueError):
    """パッチが適用できない（場所が無い、衝突している、など）。"""


def add_constant(key: str, value: str) -> dict:
    return {"op": "add_constant", "key": key, "value": value}


def add_term(term: dict) -> dict:
    return {"op": "add_term", "term": term}


def add_node(parent: str | None, node: dict, position: str = "last", target: str = "body") -> dict:
    """ノードを足す。`parent` が `None` なら最上位（`body` か `appendices`）に足す。"""
    return {"op": "add_node", "parent": parent, "position": position, "node": node, "target": target}


def add_block(owner: str, block: dict, position: str = "last") -> dict:
    return {"op": "add_block", "owner": owner, "position": position, "block": block}


def add_index_row(target: str, row: list[str]) -> dict:
    """`target` は `front_matter.purpose_index` / `front_matter.rider_index`。"""
    return {"op": "add_index_row", "target": target, "row": row}


# --------------------------------------------------------------------- 適用
def apply(data: dict, ops: list[dict]) -> dict:
    """操作の列を適用した**新しい**辞書を返す（引数は変更しない）。"""
    out = copy.deepcopy(data)
    for op in ops:
        kind = op["op"]
        if kind not in OPS:
            raise PatchError(f"知らない操作: {kind}")
        _APPLY[kind](out, op)
    return out


def _apply_constant(data: dict, op: dict) -> None:
    consts = data["meta"].setdefault("constants", {})
    if op["key"] in consts:
        raise PatchError(f"定数 {op['key']} は既定の約款にある（衝突）")
    consts[op["key"]] = op["value"]


def _apply_term(data: dict, op: dict) -> None:
    terms = data.setdefault("defined_terms", [])
    if any(t["id"] == op["term"]["id"] for t in terms):
        raise PatchError(f"定義語 {op['term']['id']} は既定の約款にある（衝突）")
    terms.append(op["term"])
    terms.sort(key=lambda t: (t.get("index_kana") or "", t["id"]))


def _apply_node(data: dict, op: dict) -> None:
    if op.get("parent") is None:
        target = op.get("target", "body")
        if target not in ("body", "appendices"):
            raise PatchError(f"最上位に足せるのは body か appendices だけ（{target}）")
        kids = data.setdefault(target, [])
    else:
        parent = find_node(data, op["parent"])
        if parent is None:
            raise PatchError(f"追加先のノード {op['parent']} が無い")
        kids = parent.setdefault("children", [])
    if any(k["id"] == op["node"]["id"] for k in kids):
        raise PatchError(f"ノードID {op['node']['id']} が重複")
    if op["position"] == "first":
        kids.insert(0, op["node"])
    elif isinstance(op["position"], int):
        kids.insert(op["position"], op["node"])
    else:
        kids.append(op["node"])


def _apply_block(data: dict, op: dict) -> None:
    owner = find_node(data, op["owner"])
    if owner is None:
        raise PatchError(f"ブロックの持ち主 {op['owner']} が無い")
    blocks = owner.setdefault("blocks", [])
    if any(b.get("id") == op["block"].get("id") for b in blocks):
        raise PatchError(f"ブロックID {op['block'].get('id')} が重複")
    if op["position"] == "first":
        blocks.insert(0, op["block"])
    else:
        blocks.append(op["block"])


def _apply_index_row(data: dict, op: dict) -> None:
    key = op["target"].split(".")[-1]
    table = (data.get("front_matter") or {}).get(key)
    if not isinstance(table, dict) or table.get("type") != "table":
        raise PatchError(f"{op['target']} が表でない（既定の約款に無い）")
    grid = table["grid"]
    r = len(grid)
    tid = table["id"]
    cols = len(grid[0])
    if len(op["row"]) != cols:
        raise PatchError(f"{op['target']}: 列数が合わない（表は{cols}列、行は{len(op['row'])}列）")
    sample = grid[1] if len(grid) > 1 else []
    row = [
        {
            "id": f"{tid}__r{r}c{c}",
            "text": text,
            "rowspan": 1,
            "colspan": 1,
            "role": _cell_role(sample, c, default="stub" if c == 0 else "body"),
            "align": _cell_align(sample, c),
            "vertical_text": False,
        }
        for c, text in enumerate(op["row"])
    ]
    grid.append(row)
    if isinstance(table.get("records"), list) and table["records"]:
        # 結合セル（`merged_into`）には text が無い。意味のレコードは見出しの文字だけで作る
        header = [c.get("text", "") for c in grid[0]]
        table["records"].append(dict(zip(header, op["row"], strict=False)))


def _cell_role(sample: list[dict], c: int, default: str) -> str:
    """見本の行から役割を写す（結合セルには役割が無いので既定に落とす）。"""
    cell = sample[c] if c < len(sample) else {}
    return cell.get("role") or default


def _cell_align(sample: list[dict], c: int) -> str | None:
    cell = sample[c] if c < len(sample) else {}
    return cell.get("align")


_APPLY = {
    "add_constant": _apply_constant,
    "add_term": _apply_term,
    "add_node": _apply_node,
    "add_block": _apply_block,
    "add_index_row": _apply_index_row,
}


# --------------------------------------------------------------------- 探索
def iter_nodes(data: dict):
    """本文・別表・特約のノードを前順に辿る。"""

    def walk(nodes):
        for n in nodes:
            yield n
            yield from walk(n.get("children") or [])

    yield from walk(data.get("body") or [])
    yield from walk(data.get("appendices") or [])


def find_node(data: dict, nid: str) -> dict | None:
    for n in iter_nodes(data):
        if n["id"] == nid:
            return n
    return None


def node_ids(data: dict) -> set[str]:
    return {n["id"] for n in iter_nodes(data)}


def block_ids(data: dict) -> set[str]:
    out: set[str] = set()

    def walk(blocks: list[dict]) -> None:
        for b in blocks or []:
            if b.get("id"):
                out.add(b["id"])
            walk(b.get("blocks") or [])

    for n in iter_nodes(data):
        walk(n.get("blocks") or [])
    fm = data.get("front_matter") or {}
    for key in ("purpose_index", "rider_index", "petname_table"):
        b = fm.get(key)
        if isinstance(b, dict) and b.get("id"):
            out.add(b["id"])
    walk(fm.get("preface") or [])
    walk((data.get("back_matter") or {}).get("colophon") or [])
    return out


def chapters(data: dict) -> list[dict]:
    return [n for n in iter_nodes(data) if n["kind"] == "chapter"]


def articles(data: dict) -> list[dict]:
    return [n for n in iter_nodes(data) if n["kind"] == "article"]


def next_appendix_id(data: dict) -> str:
    """次に空いている別表のID（既定の命名規則 `app<n>`）。"""
    nums = [
        int(n["id"][3:])
        for n in data.get("appendices") or []
        if n["id"].startswith("app") and n["id"][3:].isdigit()
    ]
    return f"app{max(nums, default=0) + 1}"


def riders(data: dict) -> list[dict]:
    return [n for n in iter_nodes(data) if n["kind"] == "rider"]


def rider_parent(data: dict) -> str | None:
    """特約を足す場所。既存の特約と同じ親に置く（life は `part` の下にある）。"""
    existing = riders(data)
    if not existing:
        return None
    first = existing[0]["id"]
    for n in iter_nodes(data):
        if any(c["id"] == first for c in n.get("children") or []):
            return n["id"]
    return None


def next_rider_id(data: dict, key: str) -> str:
    """特約のID（既定の命名規則 `rider_<題材>`）。衝突したら生成を止める。"""
    rid = f"rider_{key}"
    if rid in node_ids(data):
        raise PatchError(f"特約ID {rid} が既定の約款と衝突")
    return rid


def next_article_id(chapter: dict) -> tuple[str, int]:
    """章の中で次に空いている条のIDを、既定の命名規則（`<章>_a<n>`）で払い出す。"""
    nums = [
        int(c["id"].rsplit("_a", 1)[1])
        for c in chapter.get("children") or []
        if c["kind"] == "article" and c["id"].rsplit("_a", 1)[-1].isdigit()
    ]
    n = max(nums, default=0) + 1
    return f"{chapter['id']}_a{n}", n


def summarize(ops: list[dict]) -> dict[str, Any]:
    """パッチの要約（マニフェストに載せる）。"""
    out: dict[str, Any] = {k: 0 for k in OPS}
    for op in ops:
        out[op["op"]] += 1
    out["nodes"] = [op["node"]["id"] for op in ops if op["op"] == "add_node"]
    out["constants"] = sorted(op["key"] for op in ops if op["op"] == "add_constant")
    return out
