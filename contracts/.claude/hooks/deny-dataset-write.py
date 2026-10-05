#!/usr/bin/env python3
"""dataset/ 配下の手編集を拒否する PreToolUse フック（CLAUDE.md §0.4-3）。

stdin に PreToolUse のイベント JSON を受け取り、`tool_input.file_path` が
プロジェクトの `dataset/` 配下なら deny を返す。生成物はコマンドで作り直す。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REASON = (
    "dataset/ 配下は生成物であり手編集を禁止している（CLAUDE.md §0.4-3）。"
    "直すときは入力（content/<cid>/parts/、blueprints/、styles/、keiyaku/）を編集し、"
    "`make doc CONTENT=… STYLE=…`（build → render → verify）で作り直すこと。"
)


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except json.JSONDecodeError:
        return 0  # 解釈できない入力では止めない（フックの誤作動で作業を壊さない）

    file_path = (event.get("tool_input") or {}).get("file_path")
    if not file_path:
        return 0

    project = Path(event.get("cwd") or ".").resolve()
    target = Path(file_path)
    if not target.is_absolute():
        target = project / target
    try:
        relative = target.resolve().relative_to(project)
    except ValueError:
        return 0  # プロジェクト外は対象外

    if relative.parts and relative.parts[0] == "dataset":
        json.dump(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": REASON,
                }
            },
            sys.stdout,
            ensure_ascii=False,
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
