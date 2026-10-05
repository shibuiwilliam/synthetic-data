"""`dataset/` を Hugging Face Hub のデータセットとして上げる（仕様は `docs/publishing.md` §7）。

    uv run python scripts/upload_hf.py             # 既定は dry-run（通信しない。上がる一覧を数える）
    uv run python scripts/upload_hf.py --yes       # 実際に上げる（HF_TOKEN が必要）

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
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from keiyaku.publish import check as publish_check  # noqa: E402
from keiyaku.publish import distributed_files, load_spec  # noqa: E402


def _ignore_patterns(spec_exclude: list[str]) -> list[str]:
    """`upload_folder` に渡す除外（`specs/publish.yaml` の `exclude` が正本）。"""
    out: list[str] = []
    for pattern in spec_exclude:
        out += [pattern, f"**/{pattern}"]
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
    args = parser.parse_args()

    spec = load_spec()
    dataset_dir: Path = args.dataset
    if not (dataset_dir / "manifest.json").is_file():
        print(f"[ng] {dataset_dir}/manifest.json が無い（`keiyaku manifest update` を先に）")
        return 2

    problems, blockers = publish_check(dataset_dir, spec)
    files = distributed_files(dataset_dir, spec)
    total = sum(p.stat().st_size for p in files)
    print(f"repo      : {spec.hub.repo_id}（{spec.hub.repo_type}）")
    print(f"visibility: {'public' if args.public else ('private' if spec.hub.private else 'public')}")
    print(f"license   : {spec.license.id}")
    print(f"files     : {len(files):,}（{total / 1024 / 1024:.1f} MiB）")
    excluded = [
        p
        for p in dataset_dir.rglob("*")
        if p.is_file() and any(fnmatch.fnmatch(p.name, x) for x in spec.exclude)
    ]
    print(f"excluded  : {len(excluded):,} ファイル（{'、'.join(spec.exclude)}）")

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
    private = False if args.public else spec.hub.private
    api.create_repo(repo_id=spec.hub.repo_id, repo_type=spec.hub.repo_type, private=private, exist_ok=True)
    api.upload_folder(
        folder_path=str(dataset_dir),
        repo_id=spec.hub.repo_id,
        repo_type=spec.hub.repo_type,
        revision=spec.hub.revision or None,
        ignore_patterns=_ignore_patterns(spec.exclude),
        commit_message=args.message or f"Add {len(files):,} files ({total / 1024 / 1024:.1f} MiB)",
    )
    print(f"[ok] {spec.hub_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
