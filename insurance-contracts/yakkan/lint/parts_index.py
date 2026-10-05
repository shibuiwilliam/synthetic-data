"""L19：`parts/` にあるのに `doc.json` の `parts` に載っていないファイルを挙げる。

compose は `doc.json` の `parts` に書かれた順にファイルを読む。載っていないファイルは
**読み込まれない**ので、中身はどの `source.json` にも入らない。

scaffold が作った書きかけの断片（`_todo` 付き）がそのまま残ると、この状態になる。
出力は正しいままだが、**同じノードIDが 2 つのファイルに見える**ので、
道具を書くときに読み込まれない側を拾って混乱する（docs/decisions.md 2026-10-04）。

直し方は 2 つしかない。埋めて `doc.json` の `parts` に足すか、消すか。
"""

from __future__ import annotations

import json
from collections.abc import Iterator

from yakkan.lint.base import Finding, LintContext, rule

PARTS_DIRNAME = "parts"


@rule("L19", "parts/ にあるのに doc.json に載っていないファイル")
def l19_unlisted_parts(ctx: LintContext) -> Iterator[Finding]:
    if ctx.content_dir is None:
        return
    parts_dir = ctx.content_dir / PARTS_DIRNAME
    doc_path = ctx.content_dir / "doc.json"
    if not parts_dir.is_dir() or not doc_path.is_file():
        return
    try:
        listed = json.loads(doc_path.read_text(encoding="utf-8")).get("parts") or []
    except (json.JSONDecodeError, OSError) as error:
        # 読めないときは L00 が報告するので、ここでは黙る
        del error
        return
    if not isinstance(listed, list):
        return
    known = {str(name) for name in listed}
    for path in sorted(parts_dir.glob("*.json")):
        if path.name in known:
            continue
        todo = '"_todo"' in path.read_text(encoding="utf-8")
        hint = "scaffold の書きかけ（`_todo` 付き）" if todo else "どこからも読まれない"
        yield Finding(
            "L19",
            "warn",
            f"{path.name} は doc.json の parts に無いので読み込まれない（{hint}）。"
            "埋めて parts に足すか、削除する",
            path=str(path),
        )
