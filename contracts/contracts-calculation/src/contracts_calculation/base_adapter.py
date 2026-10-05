"""本体（contracts / keiyaku）を呼ぶ唯一の場所。

- 本体のファイルは読むだけ。書き込みは本サブプロジェクト配下へのコピーに対してのみ行う。
- 索引の再計算は `uv run keiyaku build <dir>`、描画は `uv run keiyaku render <dir> --style <sid> --out <root>`。
  いずれも本体リポジトリのルートを作業ディレクトリにして呼ぶ（2026-10-03 実物確認）。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_THIS_DIR = Path(__file__).resolve()

# HC-2 で確定した v1 の基準集合。親 content は増減し得るため、再現性が必要な
# --all-bases・回帰テストでは動的な全件列挙と分けて扱う。
V1_BASE_CONTENT_IDS = (
    "con-0001",
    "con-0002",
    "csl-0001",
    "csl-0002",
    "dlg-0001",
    "dlg-0002",
    "emp-0001",
    "emp-0002",
    "lea-0001",
    "lea-0002",
    "lic-0001",
    "lic-0002",
    "nda-0001",
    "nda-0002",
    "ots-0001",
    "ots-0002",
    "pur-0001",
    "pur-0002",
    "sys-0001",
    "sys-0002",
)


def repo_root() -> Path:
    """本体リポジトリ（keiyaku/ を含むディレクトリ）を探す。"""
    for parent in _THIS_DIR.parents:
        if (parent / "keiyaku").is_dir() and (parent / "pyproject.toml").is_file():
            return parent
    raise FileNotFoundError("本体リポジトリ（keiyaku/）が見つからない")


def calc_root() -> Path:
    """contracts-calculation のルート。"""
    return repo_root() / "contracts-calculation"


@dataclass(frozen=True)
class BaseCapabilities:
    """本体が描画できる表現手段の宣言（DESIGN.md §9.5。2026-10-03 実物確認）。"""

    node_kinds: frozenset[str]
    table: bool
    header_sheet: bool
    figure_kinds: frozenset[str]
    formula: bool
    constants: str  # "dictionary"（meta.constants ＋ {const:}）
    style: str  # 既定の文体


def capabilities() -> BaseCapabilities:
    """本体の能力。docs/schema.md と models.py の実物から確定した固定値。"""
    return BaseCapabilities(
        node_kinds=frozenset(
            {
                "part",
                "chapter",
                "rider",
                "section",
                "article",
                "paragraph",
                "item",
                "subitem",
                "subsubitem",
                "appendix",
                "appendix_section",
                "preamble",
                "head_matter",
                "signature",
                "supplement",
            }
        ),
        table=True,
        header_sheet=True,
        figure_kinds=frozenset({"flowchart", "tree", "steps", "timeline", "annotated_mock", "matrix"}),
        formula=True,
        constants="dictionary",
        style="jotai",  # 常体「…ものとする。」が既定（blueprint の tone で変わる）
    )


def list_base_contents() -> list[Path]:
    """本体の既定の契約書（content/<cid>）の一覧。source.json を持つものだけ。"""
    root = repo_root() / "content"
    return sorted(p for p in root.iterdir() if (p / "source.json").is_file())


def list_v1_base_contents() -> list[Path]:
    """HC-2 で固定した v1 の 20 基準契約を、決定済みの順で返す。"""
    root = repo_root() / "content"
    contents = [root / cid for cid in V1_BASE_CONTENT_IDS]
    missing = [p.name for p in contents if not (p / "source.json").is_file()]
    if missing:
        raise FileNotFoundError(f"v1 の基準契約が見つからない: {', '.join(missing)}")
    return contents


def load_source(content_dir: Path) -> dict:
    """source.json を読む（読むだけ）。"""
    return json.loads((Path(content_dir) / "source.json").read_text(encoding="utf-8"))


def _run(args: list[str], timeout: int = 600) -> subprocess.CompletedProcess:
    env = dict(os.environ)
    if sys.platform == "darwin":
        # WeasyPrint が Homebrew の dylib を見つけるため（本体 docs/gotchas.md。make 経由なら自動）
        env.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")
    proc = subprocess.run(  # noqa: PLW1510 — 戻り値で自前判定する
        args,
        cwd=repo_root(),
        capture_output=True,
        text=True,
        timeout=timeout,
        env=env,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"本体のコマンドが失敗した: {' '.join(args)}\n--- stdout ---\n{proc.stdout}\n--- stderr ---\n{proc.stderr}"
        )
    return proc


def run_fill_records(content_dir: Path) -> None:
    """表の records を本体のスクリプトで埋める（grid から機械生成。lint L05 の前提）。"""
    _ensure_ours(content_dir)
    _run(["uv", "run", "python", "scripts/fill_records.py", str(Path(content_dir).resolve()), "--write"])


def run_lint(content_dir: Path, similarity: bool = False) -> None:
    """本体の lint（L00〜L26）。error が 1 件でもあれば例外になる。"""
    _ensure_ours(content_dir)
    args = ["uv", "run", "keiyaku", "lint", str(Path(content_dir).resolve())]
    if not similarity:
        args.append("--no-similarity")
    _run(args)


def run_build(content_dir: Path) -> None:
    """索引の再計算（derived の付与）。content_dir は本サブプロジェクト配下のコピーであること。"""
    _ensure_ours(content_dir)
    _run(["uv", "run", "keiyaku", "build", str(Path(content_dir).resolve())])


def run_render(content_dir: Path, out_root: Path, style: str | None = None, png: bool = True) -> None:
    """PDF の描画。出力先は本サブプロジェクト配下であること。"""
    _ensure_ours(content_dir)
    _ensure_ours(out_root)
    args = [
        "uv",
        "run",
        "keiyaku",
        "render",
        str(Path(content_dir).resolve()),
        "--out",
        str(Path(out_root).resolve()),
    ]
    if style:
        args += ["--style", style]
    if not png:
        args += ["--no-png"]
    _run(args)


def _ensure_ours(path: Path) -> None:
    """本体側のパスへの書き込みを防ぐ（規則11）。"""
    resolved = Path(path).resolve()
    if not str(resolved).startswith(str(calc_root().resolve())):
        raise ValueError(f"contracts-calculation の外へ書こうとした: {resolved}")
