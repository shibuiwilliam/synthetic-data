"""`dataset/` を Hugging Face Hub のデータセットとして上げる（仕様は `docs/publishing.md` §7・§12）。

    uv run python scripts/upload_hf.py             # 既定は dry-run（通信しない。上がる一覧を数える）
    uv run python scripts/upload_hf.py --yes       # 実際に上げる（HF_TOKEN が必要）
    uv run python scripts/upload_hf.py --only search   # 検索評価セットのリポジトリだけ

**上げ先は 2 つある。** 文書のデータセット（`dataset/`。`search/` を除く）と、
検索評価セットのデータセット（`dataset/search/` がそのルート）。
宣言は `specs/publish.yaml` の `hub` と `search_dataset.hub`。

**取り消せない外向き操作なので、二段にしてある。**

1. `--yes` が無ければ通信しない。何がどれだけ上がるかだけを出す。
2. 配布条件（`specs/publish.yaml` の `license.id`）が未決なら**実行を拒否する**
   （人間の決定事項。`CLAUDE.md` §0.2-1・`HITL_TODO.md` H13）。
   `keiyaku publish check` が鮮度の食い違いを報告している場合も拒否する。

既定の可視性は `specs/publish.yaml` の `hub.private`。**最初は private で上げ、人が Hub 上で
中身を見てから public にする**（公開も人間の判断）。
"""

from __future__ import annotations

import argparse
import fnmatch
import os
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from keiyaku.publish import (  # noqa: E402
    PublishSpec,
    distributed_files,
    load_spec,
    search_distributed_files,
)
from keiyaku.publish import check as publish_check  # noqa: E402


def _ignore_patterns(spec_exclude: list[str]) -> list[str]:
    """`upload_folder` に渡す除外（`specs/publish.yaml` の `exclude` が正本）。"""
    out: list[str] = []
    for pattern in spec_exclude:
        out += [pattern, f"**/{pattern}"]
    return out


@dataclass(frozen=True)
class Target:
    """上げ先 1 つ（リポジトリ・ルートになるディレクトリ・配布するファイル）。"""

    label: str
    root: Path
    repo_id: str
    repo_type: str
    private: bool
    revision: str
    files: list[Path]

    @property
    def bytes(self) -> int:
        return sum(p.stat().st_size for p in self.files)


def _targets(dataset_dir: Path, spec: PublishSpec, only: str) -> list[Target]:
    """宣言から上げ先を作る。検索評価セットは**別リポジトリ**（`docs/publishing.md` §12）。"""
    out: list[Target] = []
    if only in ("both", "main"):
        out.append(
            Target(
                "documents",
                dataset_dir,
                spec.hub.repo_id,
                spec.hub.repo_type,
                spec.hub.private,
                spec.hub.revision,
                distributed_files(dataset_dir, spec),
            )
        )
    if only in ("both", "search") and spec.search_split:
        sd = spec.search_dataset
        out.append(
            Target(
                "retrieval",
                dataset_dir / sd.dir,
                sd.hub.repo_id,
                sd.hub.repo_type,
                sd.hub.private,
                sd.hub.revision,
                search_distributed_files(dataset_dir, spec),
            )
        )
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="dataset/ を Hugging Face Hub に上げる")
    parser.add_argument("--dataset", type=Path, default=Path("dataset"))
    parser.add_argument("--yes", action="store_true", help="実際に上げる（これが無ければ通信しない）")
    parser.add_argument("--message", default="", help="コミットメッセージ")
    parser.add_argument(
        "--public",
        action="store_true",
        help="public で作る（既定は specs/publish.yaml の hub.private。**人間が明示したときだけ**）",
    )
    parser.add_argument(
        "--only",
        choices=("both", "main", "search"),
        default="both",
        help="上げるリポジトリを絞る（既定は両方。search は検索評価セットだけ）",
    )
    args = parser.parse_args()

    spec = load_spec()
    dataset_dir: Path = args.dataset
    if not (dataset_dir / "manifest.json").is_file():
        print(f"[ng] {dataset_dir}/manifest.json が無い（`keiyaku manifest update` を先に）")
        return 2

    problems, blockers = publish_check(dataset_dir, spec)
    targets = _targets(dataset_dir, spec, args.only)
    if not targets:
        print(f"[ng] 上げ先が無い（--only {args.only}）")
        return 2
    print(f"license   : {spec.license.id}")
    for target in targets:
        visible = "public" if args.public else ("private" if target.private else "public")
        print(f"repo      : {target.repo_id or '（未決）'}（{target.repo_type}・{visible}） ← {target.root}/")
        print(f"  {target.label:<10}: {len(target.files):,} ファイル（{target.bytes / 1024 / 1024:.1f} MiB）")
    excluded = [
        p
        for p in dataset_dir.rglob("*")
        if p.is_file() and any(fnmatch.fnmatch(p.name, x) for x in spec.exclude)
    ]
    print(f"excluded  : {len(excluded):,} ファイル（{'、'.join(spec.exclude)}）")
    if args.only == "both" and spec.search_split:
        print(f"note      : 検索評価セットは本体に含めず {spec.search_dataset.hub.repo_id} に上げる")

    for line in problems:
        print(f"[ng] 公開用の面が古い: {line}")
    for line in blockers:
        print(f"[ng] {line}")
    if problems:
        print("→ `uv run keiyaku publish update` を実行してから上げる")
        return 1
    if blockers:
        print("→ 人間の決定を待つ（アップロードしない）")
        return 1
    if not args.yes:
        print("→ dry-run（通信していない）。上げるなら --yes を付ける")
        return 0

    if not (os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN")):
        print("[ng] HF_TOKEN が無い（`huggingface-cli login` か環境変数で渡す）")
        return 2
    try:
        from huggingface_hub import HfApi
    except ImportError:
        print("[ng] huggingface_hub が無い（`uv sync --group publish`）")
        return 2

    api = HfApi()
    for target in targets:
        private = False if args.public else target.private
        ignore = _ignore_patterns(spec.exclude)
        # 本体のリポジトリには検索評価セットを入れない（別リポジトリで配る）
        if target.root == dataset_dir and spec.search_split:
            ignore += [f"{spec.search_dataset.dir}/*", f"{spec.search_dataset.dir}/**"]
        api.create_repo(repo_id=target.repo_id, repo_type=target.repo_type, private=private, exist_ok=True)
        api.upload_folder(
            folder_path=str(target.root),
            repo_id=target.repo_id,
            repo_type=target.repo_type,
            revision=target.revision or None,
            ignore_patterns=ignore,
            commit_message=args.message
            or f"Add {len(target.files):,} files ({target.bytes / 1024 / 1024:.1f} MiB)",
        )
        print(f"[ok] https://huggingface.co/datasets/{target.repo_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
