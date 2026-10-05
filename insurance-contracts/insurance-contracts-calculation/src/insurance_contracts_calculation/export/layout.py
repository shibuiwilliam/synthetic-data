"""出力の配置、マニフェスト、ハッシュ（DESIGN.md §10.3）。

```
<出力先>/<content_id>/
├── policy.json                      # 追加後の約款JSON（derived 再計算済み）
├── <doc_id>/                        # 本体が描画した PDF・layout.json・PNG
└── calc/
    ├── spec.json / patch.json / answer_key.json
    ├── tasks.jsonl / cases.jsonl
    ├── programs/calc_<id>.py
    ├── tests/conftest.py / tests/test_calc_<id>.py
    └── manifest.json
```

**本体の** `dataset/` の下には絶対に書かない（本体の `manifest check` が壊れる。TASK.md §2.5）。
拡張自身の `dataset/` は名前が同じだけで本体の外にあるので、出力先に選んでよい。
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

#: 書き込みを禁じるディレクトリの名前（本体のデータセット）
FORBIDDEN = "dataset"


class OutputError(RuntimeError):
    pass


def forbidden_root() -> Path:
    """書き込みを禁じるディレクトリ（本体の `dataset/`）。"""
    from .. import base_adapter as ba

    return (ba.repo_root() / FORBIDDEN).resolve()


def check_out_dir(path: Path) -> Path:
    """**本体の** `dataset/` 配下への書き込みを止める。

    止める理由は本体の `manifest check` が壊れることなので、止めるのは本体の
    `dataset/` だけでよい。名前だけで判定すると、本体の外にある同名の
    ディレクトリ（拡張自身の `dataset/` など）まで塞いでしまう。
    """
    p = Path(path).resolve()
    forbidden = forbidden_root()
    if p == forbidden or forbidden in p.parents:
        raise OutputError(f"{p} は本体のデータセットの中なので書き込まない（TASK.md §2.5）")
    return p


@dataclass
class Paths:
    root: Path
    content_id: str

    @property
    def doc(self) -> Path:
        return self.root / self.content_id

    @property
    def calc(self) -> Path:
        return self.doc / "calc"

    @property
    def policy(self) -> Path:
        return self.doc / "policy.json"

    def render_dir(self, doc_id: str) -> Path:
        return self.doc / doc_id

    def prepare(self) -> Paths:
        check_out_dir(self.root)
        (self.calc / "programs").mkdir(parents=True, exist_ok=True)
        (self.calc / "tests").mkdir(parents=True, exist_ok=True)
        return self


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, data, indent: int = 2) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=indent) + "\n", encoding="utf-8")


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=False) + "\n" for r in rows), encoding="utf-8"
    )


def file_hashes(root: Path, skip: tuple[str, ...] = ("manifest.json",)) -> dict[str, str]:
    """出力の全ファイルのハッシュ（決定性の確認に使う）。"""
    out = {}
    for p in sorted(root.rglob("*")):
        if not p.is_file() or p.name in skip:
            continue
        if "__pycache__" in p.parts or ".pytest_cache" in p.parts:
            continue
        out[str(p.relative_to(root))] = sha256(p)
    return out


#: 公開してよいファイル（DESIGN.md §10.3）
PUBLIC = ("policy.json", "tasks.jsonl", "doc.pdf", "pages", "layout.json", "source.json")
#: 評価対象システムに渡さないファイル
PRIVATE = ("spec.json", "patch.json", "answer_key.json", "cases.jsonl", "tests", "programs", "manifest.json")


def is_public(relative: str) -> bool:
    parts = Path(relative).parts
    if any(p in PRIVATE for p in parts):
        return False
    return any(p in PUBLIC for p in parts) or parts[-1].endswith((".pdf", ".png"))
