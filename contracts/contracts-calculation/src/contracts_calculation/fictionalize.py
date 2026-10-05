"""生成前に、既知の実在名称との衝突を合成名称へ置き換える。

本体 ``content/`` は読取り専用なので、コピー後の作業ディレクトリだけを処理する。
置換対象は JSON の文字列値に限定し、計算値・ID・JSON のキーは変更しない。
"""

from __future__ import annotations

import json
from pathlib import Path


def load_replacements(calc_root: Path) -> dict[str, str]:
    path = Path(calc_root) / "packs" / "fictional_names.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not all(
        isinstance(source, str) and source and isinstance(target, str) and target
        for source, target in data.items()
    ):
        raise ValueError(f"名称置換表の形式が不正: {path}")
    return data


def fictionalize_content(content_dir: Path, replacements: dict[str, str]) -> set[str]:
    """content コピー内の JSON 文字列値を置換し、検出した旧名称を返す。"""

    found: set[str] = set()

    def replace(value):
        if isinstance(value, str):
            for source, target in replacements.items():
                if source in value:
                    found.add(source)
                    value = value.replace(source, target)
            return value
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        return value

    for path in sorted(Path(content_dir).rglob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        replaced = replace(data)
        if replaced != data:
            path.write_text(json.dumps(replaced, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return found
