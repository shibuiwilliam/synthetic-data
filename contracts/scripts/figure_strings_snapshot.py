"""図・算式の「描かれる文字列」を書き出す。{const:} への置き換えが無害かを確かめるために使う。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from keiyaku.build import build, iter_model_strings, resolve_strings
    from keiyaku.compose import load_draft
    from keiyaku.lint.walk import iter_blocks
    from keiyaku.models import Figure, Formula

    out: dict[str, list[str]] = {}
    for cdir in sorted(Path("content").iterdir()):
        if not (cdir / "doc.json").exists() or cdir.name.startswith("sample"):
            continue
        source = build(load_draft(cdir))
        for block, _owner, _article in iter_blocks(source):
            if not isinstance(block, Figure | Formula):
                continue
            derived = (
                source.derived.figures.get(block.id)
                if isinstance(block, Figure)
                else source.derived.formulas.get(block.id)
            )
            labels = derived.resolved_labels if derived else {}
            out[f"{cdir.name}/{block.id}"] = list(iter_model_strings(resolve_strings(block, labels)))
    print(json.dumps(out, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
