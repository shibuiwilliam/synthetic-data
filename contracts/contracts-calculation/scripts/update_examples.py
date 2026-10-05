"""examples/ を作り直す（回帰テストの基準。手で編集しない）。

実行: cd contracts-calculation && PYTHONPATH=src uv run --project .. python scripts/update_examples.py
意図して出力を変えたときだけ実行し、生成器の版（generate.GENERATOR_VERSION）を上げる。
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "src"))

from contracts_calculation import base_adapter as ba
from contracts_calculation.generate import generate_one

CIDS = ["nda-0001", "dlg-0001", "sys-0001"]
#: 描画に依存しないファイルだけを基準にする（manifest は描画の有無で注記が変わるため除外）
FILES = ["contract.json", "calc/spec.json", "calc/answer_key.json", "calc/patch.json"]


def main() -> None:
    out_root = ROOT / "data" / "_examples_build"
    if out_root.exists():
        shutil.rmtree(out_root)
    examples = ROOT / "examples"
    if examples.exists():
        shutil.rmtree(examples)
    for base in CIDS:
        result = generate_one(ba.repo_root() / "content" / base, calc_seed=1, out_root=out_root, render=False)
        assert result.ok, f"{base}: ゲートを通らない出力は基準にしない"
        dst = examples / result.content_id
        for rel in FILES:
            src = result.out_dir / rel
            target = dst / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(src, target)
        for prog in sorted((result.out_dir / "calc" / "programs").glob("*.py")):
            target = dst / "calc" / "programs" / prog.name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(prog, target)
        print(f"examples/{result.content_id} を更新した")
    shutil.rmtree(out_root)


if __name__ == "__main__":
    main()
