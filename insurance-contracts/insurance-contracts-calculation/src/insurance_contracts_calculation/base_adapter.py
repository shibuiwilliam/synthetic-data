"""本体（`insurance-contracts` / `yakkan`）を呼ぶ**唯一の場所**。

公開するのは次の 6 つだけである。ほかのモジュールは本体を直接 import しない
（`tests/unit/test_base_adapter_isolation.py` がこれを固定する）。

| 関数 | 役割 |
|---|---|
| `load_base` | 既定の約款を読む（`content/<id>/` でも `source.json` でも可） |
| `apply_patch` | 追加操作を適用した draft（`derived` なし）を作る |
| `rebuild` | 本体で `derived` を再計算して約款JSONにする |
| `render` | 本体でPDF・PNG・`layout.json` を描画する |
| `lint` | 本体の lint（L00〜L18）をかける |
| `verify` | 本体の `verify_dataset`（ページ数・往復一致・はみ出し等）をかける |

本体の import は各関数の中で行う。描画しない経路で WeasyPrint を読み込まないためである
（macOS では `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が要る）。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .realize import patch as _patch


class BaseError(RuntimeError):
    """既定の約款の読み込み・本体の呼び出しに失敗した。"""


@dataclass
class Base:
    """既定の約款（追加前）。`data` は `derived` を含まない draft 相当の辞書。"""

    content_id: str
    genre: str
    data: dict[str, Any]
    path: Path
    #: 既定の約款を描画したときのスタイルID（分かるときだけ）
    style_id: str | None = None


@dataclass
class Finding:
    code: str
    severity: str
    message: str
    element_id: str | None = None
    path: str | None = None

    def __str__(self) -> str:
        where = f" <{self.path or self.element_id}>" if (self.path or self.element_id) else ""
        return f"[{self.severity}] {self.code}{where}: {self.message}"


@dataclass
class RenderInfo:
    out_dir: Path
    doc_id: str
    pages: int
    notes: list[str] = field(default_factory=list)
    pdf: Path | None = None


# --------------------------------------------------------------------- 読み込み
def load_base(path: str | Path) -> Base:
    """既定の約款を読む。`content/<content_id>/` と `source.json` の両方を受ける。"""
    p = Path(path)
    if p.is_dir():
        from yakkan.compose import load_draft

        try:
            draft = load_draft(p)
        except Exception as e:  # noqa: BLE001
            raise BaseError(f"{p} を読めない: {e}") from e
        data = _dump(draft)
        return Base(data["content_id"], data["genre"], data, p)
    if not p.is_file():
        raise BaseError(f"既定の約款が無い: {p}")
    raw = json.loads(p.read_text(encoding="utf-8"))
    data = {k: v for k, v in raw.items() if k != "derived"}
    style = None
    if p.parent.name.count("--") == 1:
        style = p.parent.name.split("--", 1)[1]
    return Base(data["content_id"], data["genre"], data, p, style)


def find_base(content_id: str, root: Path | None = None) -> Path:
    """`content_id` から既定の約款の場所を探す（`--base` を省いたときの既定）。"""
    root = root or repo_root()
    cand = root / "content" / content_id
    if cand.is_dir():
        return cand
    hits = sorted((root / "dataset").glob(f"{content_id}--*/source.json"))
    if hits:
        return hits[0]
    raise BaseError(f"{content_id} の既定の約款が見つからない（{root} の下を探した）")


def repo_root() -> Path:
    """本体（`insurance-contracts`）のディレクトリ。"""
    return Path(__file__).resolve().parents[2].parent


def available_bases(root: Path | None = None) -> list[str]:
    root = root or repo_root()
    return sorted(p.name for p in (root / "content").glob("*") if (p / "doc.json").is_file())


# --------------------------------------------------------------------- 追加
def apply_patch(base: Base, ops: list[dict]) -> dict:
    """追加操作を適用した draft 辞書を返す（`base` は変更しない）。"""
    return _patch.apply(base.data, ops)


# --------------------------------------------------------------------- 本体呼び出し
def rebuild(draft: dict) -> dict:
    """`derived` を本体で再計算し、約款JSON（`policy.json` の中身）を返す。"""
    from yakkan.build import build
    from yakkan.models import SourceDraft

    try:
        d = SourceDraft.model_validate(draft)
    except Exception as e:  # noqa: BLE001
        raise BaseError(f"追加後の約款が本体のスキーマに合わない: {e}") from e
    return _dump(build(d))


def dumps(policy: dict) -> str:
    """本体と同じ体裁（UTF-8・ensure_ascii=False・indent 2）で直列化する。"""
    return json.dumps(policy, ensure_ascii=False, indent=2, sort_keys=False) + "\n"


def lint(draft: dict, *, quick: bool = False) -> list[Finding]:
    """本体の lint をかける（`draft` は `derived` なしでよい）。"""
    from yakkan.lint.runner import lint_draft
    from yakkan.models import SourceDraft

    d = SourceDraft.model_validate({k: v for k, v in draft.items() if k != "derived"})
    return [Finding(f.code, f.severity, f.message, f.element_id, f.path) for f in lint_draft(d, quick=quick)]


def estimate_pages(draft: dict, genre: str | None = None) -> float:
    """描画前のページ数の見積り（本体の `lint/budget.py`）。"""
    from yakkan.blueprints import load_blueprint
    from yakkan.lint.budget import estimate_pages as _est
    from yakkan.models import SourceDraft

    d = SourceDraft.model_validate({k: v for k, v in draft.items() if k != "derived"})
    return _est(d, load_blueprint(genre or draft["genre"])).pages


def budget(draft: dict, genre: str | None = None) -> dict:
    """分量の余裕（本体 lint L09 と同じ数え方）。

    返すのは `pages`（推定ページ数）・`page_max`・`chars`（本文＋表の平文の字数）・`chars_max`。
    どちらかの余裕が足りない content は、最初から対象に入れない（`TASK.md` §5 R2）。
    """
    from yakkan.blueprints import load_blueprint
    from yakkan.lint.budget import estimate_pages as _est
    from yakkan.models import SourceDraft

    d = SourceDraft.model_validate({k: v for k, v in draft.items() if k != "derived"})
    bp = load_blueprint(genre or draft["genre"])
    est = _est(d, bp)
    return {
        "pages": est.pages,
        "page_max": min(max_pages() - 1, bp.target_pages[1]),
        "chars": est.body_chars + est.table_chars,
        "chars_max": bp.budget.chars_max,
    }


def reserved_appendix_ids(genre: str) -> set[str]:
    """blueprint が予約している別表のID。

    任意の別表（`optional`）でも、そのIDで作ると「その別表の中に◯行以上の表が要る」という
    必須要素（本体 lint L04 の `under`）に当たる。拡張はこれらのIDを使わない。
    """
    from yakkan.blueprints import load_blueprint

    return {a.id for a in load_blueprint(genre).appendices}


def target_pages(genre: str) -> tuple[int, int]:
    """blueprint が定める目標ページ数（本体 lint L09 はこれを超えると警告する）。"""
    from yakkan.blueprints import load_blueprint

    return tuple(load_blueprint(genre).target_pages)


def default_style(genre: str) -> str:
    from yakkan.blueprints import load_blueprint

    return load_blueprint(genre).default_style


def render(policy: dict, out_dir: Path, style_id: str | None = None, *, png: bool = True) -> RenderInfo:
    """PDF・PNG・`layout.json`・`source.json` を `out_dir` に描画する。"""
    from yakkan.models import Source
    from yakkan.render.weasy import render_source
    from yakkan.styles import load_style

    style = load_style(style_id or default_style(policy["genre"]))
    source = Source.model_validate(policy)
    out_dir = Path(out_dir)
    result = render_source(source, style, out_dir, render_png=png)
    return RenderInfo(result.out_dir, result.doc_id, result.page_count, list(result.notes), result.pdf_path)


def verify(dataset_dir: Path) -> list[Finding]:
    """描画結果に本体の検証をかける（ページ数・フォント・往復一致・はみ出し・重なり・図）。"""
    from yakkan.verify.checks import verify_dataset

    results = verify_dataset(Path(dataset_dir))
    return [Finding(r.code, r.severity, r.message, None, r.detail or None) for r in results]


def max_pages() -> int:
    from yakkan.verify.checks import MAX_PAGES

    return MAX_PAGES


def _dump(model) -> dict:
    """本体のモデル → 辞書（本体の `dump_json` と同じ設定）。"""
    return model.model_dump(mode="json", by_alias=True, exclude_none=False)
