from __future__ import annotations

import json
from pathlib import Path

from contracts_calculation.fictionalize import fictionalize_content


def test_fictionalize_replaces_only_string_values(tmp_path) -> None:
    source = tmp_path / "content"
    source.mkdir()
    path = source / "doc.json"
    path.write_text(
        json.dumps(
            {
                "旧社名": "旧社名は旧商品を扱う。",
                "nested": ["旧商品", {"name": "旧社名"}],
                "number": 10,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    found = fictionalize_content(source, {"旧社名": "合成社名", "旧商品": "合成商品"})

    assert found == {"旧社名", "旧商品"}
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result == {
        "旧社名": "合成社名は合成商品を扱う。",
        "nested": ["合成商品", {"name": "合成社名"}],
        "number": 10,
    }


def test_dataset_does_not_contain_denied_names() -> None:
    root = Path(__file__).resolve().parents[1]
    replacements = json.loads((root / "packs" / "fictional_names.json").read_text(encoding="utf-8"))
    offenders: list[str] = []
    for path in sorted((root / "dataset").rglob("*")):
        if path.is_file() and path.suffix in {".json", ".jsonl", ".html"}:
            text = path.read_text(encoding="utf-8")
            for denied in replacements:
                if denied in text:
                    offenders.append(f"{path.relative_to(root)}: {denied}")
    assert not offenders, "\n".join(offenders)
