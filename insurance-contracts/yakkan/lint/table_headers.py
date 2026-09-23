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

from yakkan.lint.base import Finding, LintContext, rule
from yakkan.lint.walk import iter_blocks
from yakkan.models import Cell, Table


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


@rule("L17", "表の header_cols が行見出し（stub）の列を覆っている")
def l17_header_cols(ctx: LintContext) -> Iterator[Finding]:
    for block, _owner, _article in iter_blocks(ctx.draft):
        if not isinstance(block, Table):
            continue
        stub = _leading_stub_columns(block)
        declared = block.layout.header_cols
        if stub > declared:
            yield Finding(
                "L17",
                "error",
                f"先頭 {stub} 列が stub なのに header_cols={declared}。"
                f"行見出しが header_path に出ず、表の意味座標が崩れる",
                element_id=block.id,
            )
