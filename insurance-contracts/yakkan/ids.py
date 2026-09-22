"""id の命名規則。`scaffold` が付与し、`lint` が検査する共通の規則（docs/schema.md §5.2）。

**構造ノード**（親 id を接頭辞に持つ。階層が id から読める）

| 種別 | 接尾 | 例 |
|---|---|---|
| part | `pt{n}` | `pt1` |
| chapter | `ch{n}` | `ch4`, `pt1_ch1` |
| section | `_s{n}` | `ch4_s3` |
| article | `_a{n}` | `ch4_s3_a1` |
| paragraph | `_p{n}` | `ch4_s3_a1_p2` |
| item | `_i{n}` | `..._p2_i3` |
| subitem | `_x{n}` | `..._i3_x1` |
| subsubitem | `_y{n}` | `..._x1_y1` |
| appendix | `app{n}` | `app1` |
| appendix_section | `_s{n}` | `app1_s2` |

**ブロック**（接頭辞で種別が分かる。文書内で一意ならよく、階層は要求しない）

`tbl_` 表 / `fig_` 図 / `fml_` 算式 / `box_` 囲み / `fn_` 脚注群 / `lst_` 箇条書き /
`par_` 地の文 / `qah_` Q 見出し

**用語定義（`defined_terms[].id`）は接頭辞を課さない**。`{term:policyholder}` のように
語そのものを表す短い slug にする（docs/schema.md §5.10 のサンプルに合わせる）。

**派生 id**：セル `<table_id>__r{r}c{c}`、図ノード `<fig_id>__n{k}`（`__` 区切り）。
"""

from __future__ import annotations

import re

from yakkan.models import NodeKind

#: ノード種別 → id の接尾辞に使う文字
NODE_LETTER: dict[NodeKind, str] = {
    "part": "pt",
    "chapter": "ch",
    "rider": "rider",
    "section": "s",
    "article": "a",
    "paragraph": "p",
    "item": "i",
    "subitem": "x",
    "subsubitem": "y",
    "appendix": "app",
    "appendix_section": "s",
}

#: ルート直下に置ける種別（親 id を持たない）
ROOT_KINDS: frozenset[str] = frozenset({"part", "chapter", "rider", "appendix"})

#: ブロック種別 → id 接頭辞
BLOCK_PREFIX: dict[str, str] = {
    "paragraph": "par_",
    "list": "lst_",
    "table": "tbl_",
    "figure": "fig_",
    "formula": "fml_",
    "box": "box_",
    "footnotes": "fn_",
    "qa_heading": "qah_",
}

_SEGMENT = re.compile(r"^(pt|ch|app|s|a|p|i|x|y)(\d+)$")
_SLUG = re.compile(r"^[a-z][a-z0-9_]*$")
CELL_SEPARATOR = "__"
_CELL = re.compile(r"^(?P<table>.+)__r(?P<row>\d+)c(?P<col>\d+)$")
_FIG_NODE = re.compile(r"^(?P<fig>.+)__n(?P<index>\d+)$")


def node_id(parent_id: str | None, kind: NodeKind, index: int) -> str:
    """ノード id を組み立てる。`index` は 1 始まりの兄弟内連番。"""
    letter = NODE_LETTER[kind]
    if kind in ROOT_KINDS:
        if parent_id is None:
            return f"{letter}{index}"
        return f"{parent_id}_{letter}{index}"
    if parent_id is None:
        raise ValueError(f"{kind} はルート直下に置けない")
    return f"{parent_id}_{letter}{index}"


def block_id(block_type: str, slug: str) -> str:
    """ブロック id を組み立てる（例：`block_id("table", "notify_facts")` → `tbl_notify_facts`）。"""
    if block_type not in BLOCK_PREFIX:
        raise ValueError(f"id 接頭辞が未定義のブロック種別: {block_type}")
    if not _SLUG.match(slug):
        raise ValueError(f"slug は英小文字・数字・_ のみ: {slug!r}")
    return BLOCK_PREFIX[block_type] + slug


def cell_id(table_id: str, row: int, col: int) -> str:
    return f"{table_id}{CELL_SEPARATOR}r{row}c{col}"


def figure_node_id(figure_id: str, index: int) -> str:
    return f"{figure_id}{CELL_SEPARATOR}n{index}"


def parse_cell_id(value: str) -> tuple[str, int, int] | None:
    m = _CELL.match(value)
    return (m["table"], int(m["row"]), int(m["col"])) if m else None


def parse_figure_node_id(value: str) -> tuple[str, int] | None:
    m = _FIG_NODE.match(value)
    return (m["fig"], int(m["index"])) if m else None


def is_valid_node_id(value: str) -> bool:
    """全セグメントが `<letter><number>` の形か。"""
    return bool(value) and all(_SEGMENT.match(seg) for seg in value.split("_"))


def node_id_matches_kind(value: str, kind: NodeKind) -> bool:
    """末尾セグメントの文字がノード種別と一致するか。

    section と appendix_section はどちらも `s` を使うため、文字だけでは区別しない
    （親が appendix かどうかで決まる）。
    """
    if not is_valid_node_id(value):
        return False
    m = _SEGMENT.match(value.split("_")[-1])
    assert m is not None
    return m.group(1) == NODE_LETTER[kind]


def is_child_id_of(child: str, parent: str) -> bool:
    """`child` が `parent` の直下を表す id か（親 id ＋ 1 セグメント）。"""
    if not child.startswith(parent + "_"):
        return False
    rest = child[len(parent) + 1 :]
    return "_" not in rest and bool(_SEGMENT.match(rest))


def block_id_matches_type(value: str, block_type: str) -> bool:
    prefix = BLOCK_PREFIX.get(block_type)
    return prefix is not None and value.startswith(prefix) and len(value) > len(prefix)
