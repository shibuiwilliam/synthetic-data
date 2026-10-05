"""L17：表の `header_cols` が、行見出し（stub）の列を覆っているか。

`role: "stub"` は「この列は行見出しである」という執筆の宣言だが、
`layout.header_cols` が 0 のままだと `header_path` が行見出しを持たず、
**意味座標（行見出し・列見出し・値）の正解が崩れる**。

実際に 272 表のうち 23 表がこの状態で、紙面どおりに読んだ VLM の予測が
その表で 1 件も当たらなかった（docs/remaining_issues.md X3）。
紙面からは「1 列目が行見出しかどうか」しか分からないので、
宣言のほうを紙面に合わせる。
"""

from __future__ import annotations

from collections.abc import Iterator

from keiyaku.lint.base import Finding, LintContext, rule
from keiyaku.lint.walk import iter_blocks
from keiyaku.models import Cell, Table


def _leading_stub_columns(table: Table) -> int:
    """本文行の先頭から、すべての行で `stub` になっている列がいくつ続くか。"""
    body = table.grid[table.layout.header_rows :]
    if not body:
        return 0
    width = min(len(row) for row in body)
    count = 0
    for col in range(width):
        cells = [row[col] for row in body]
        if all(isinstance(c, Cell) and c.role == "stub" for c in cells):
            count += 1
        else:
            break
    return count


@rule("L17", "表の header_cols が行見出しの列を覆っている")
def l17_header_cols(ctx: LintContext) -> Iterator[Finding]:
    for block, _owner, _article in iter_blocks(ctx.draft):
        if not isinstance(block, Table):
            continue
        declared = block.layout.header_cols
        if declared == 0:
            # この体裁の表はどれも 1 列目が行の見出しになっている（15 種別すべてで
            # header_cols >= 1。外れ値は 2 表だけだった）。0 のままだと `header_path` が
            # 行見出しを持たず、意味座標の正解が崩れる。
            yield Finding(
                "L17",
                "error",
                "header_cols=0。1 列目は行見出しのはずで、0 のままだと header_path が行見出しを持たない",
                element_id=block.id,
            )
            continue
        stub = _leading_stub_columns(block)
        if stub > declared:
            yield Finding(
                "L17",
                "error",
                f"先頭 {stub} 列が stub なのに header_cols={declared}。"
                f"行見出しが header_path に出ず、表の意味座標が崩れる",
                element_id=block.id,
            )


@rule("L18", "列挙用に組んだ表（semantic_type: enumeration/exclusions）に caption を付けない")
def l18_enumeration_table_caption(ctx: LintContext) -> Iterator[Finding]:
    """`build.assign_caption_labels` は `caption` の有無だけを見て「表N」を振る。

    `semantic_type` が enumeration/exclusions の表は、eval ハーネス（`_gold_tables`）が
    表としての採点対象から外す（列挙として `derived.enumerations` 側で採点する）。
    ここに `caption` を付けると、紙面には「表N」が印字されて実在の表と見分けが付かないのに
    採点からは除外される、という矛盾が起きる。実際に auto-0001（2 件）・quake-0002（4 件）で
    起きており、blind な読み手（HITL_TODO.md H7）が「表5」「表6」として律儀に読み取った
    結果、表セル F1 が 0.53 まで落ちた（`docs/remaining_issues.md` Z2）。
    """
    from keiyaku.build import AUTO_LABEL_TYPES

    for block, _owner, _article in iter_blocks(ctx.draft):
        if not isinstance(block, Table):
            continue
        if block.semantic_type in AUTO_LABEL_TYPES and (block.caption or "").strip():
            yield Finding(
                "L18",
                "error",
                f"semantic_type={block.semantic_type} の表に caption が付いている"
                "（列挙として採点され表番号は振らない設計なので、caption は null にする）",
                element_id=block.id,
            )
