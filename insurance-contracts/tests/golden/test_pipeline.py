"""scaffold → lint → build → render → verify の疎通（P4-b の DoD）。

空のスケルトンは**未執筆なので lint と verify が指摘を出すのが正しい**。
ここで確かめるのは「5 段すべてが最後まで走ること」と、
「指摘の中身が『未執筆』を指していること」。
"""

from __future__ import annotations

import pytest

from yakkan.blueprints import load_blueprint
from yakkan.build import build
from yakkan.compose import load_draft
from yakkan.lint.runner import lint_content
from yakkan.scaffold import scaffold
from yakkan.styles import load_style

GENRE = "auto"


@pytest.fixture(scope="module")
def skeleton(tmp_path_factory):
    root = tmp_path_factory.mktemp("pipeline")
    return scaffold(GENRE, "auto-pipeline", seed=1, root=root)


def test_1_scaffold(skeleton) -> None:
    assert (skeleton.content_dir / "doc.json").is_file()
    assert len(list((skeleton.content_dir / "parts").glob("*.json"))) >= 4


def test_2_lintが走り未執筆を指摘する(skeleton) -> None:
    findings = lint_content(skeleton.content_dir, quick=True)
    codes = {f.code for f in findings}
    # 未執筆なので L04（必須要素）と L13（meta 必須）が出るのが正しい
    assert "L04" in codes, "空スケルトンなのに必須要素の不足が出ていない"
    assert "L13" in codes, "空スケルトンなのに meta の空欄が出ていない"
    assert "L00" not in codes, (
        f"スキーマ検証で落ちている: {[f.format() for f in findings if f.code == 'L00']}"
    )
    assert "L03" not in codes, f"記法エラーがある: {[f.format() for f in findings if f.code == 'L03']}"


def test_3_buildが通る(skeleton) -> None:
    source = build(load_draft(skeleton.content_dir))
    assert source.derived.labels, "ラベルが導出されていない"
    assert source.derived.toc, "目次が作られていない"
    # 定型条の参照がすべて解決できている
    assert source.derived.refs, "参照が 1 つも解決されていない"


def test_4_renderが通る(skeleton, tmp_path) -> None:
    from yakkan.render.weasy import render_source

    source = build(load_draft(skeleton.content_dir))
    style = load_style(load_blueprint(GENRE).default_style)
    result = render_source(source, style, tmp_path / "out", render_png=False)
    assert result.page_count >= 1
    assert result.pdf_path.is_file()
    assert result.layout.elements, "layout に要素が 1 つも無い"


def test_5_verifyが走る(skeleton, tmp_path) -> None:
    from yakkan.models import dump_json
    from yakkan.render.weasy import render_source
    from yakkan.verify.checks import verify_dataset

    source = build(load_draft(skeleton.content_dir))
    style = load_style(load_blueprint(GENRE).default_style)
    result = render_source(source, style, tmp_path / "ds", render_png=False)
    dump_json(source, result.out_dir / "source.json")

    results = verify_dataset(result.out_dir)
    codes = {r.code for r in results}
    # 5 段すべて走った。空スケルトンなので V04（目次のページ番号）や V05（描画漏れ）は出てよい
    assert "V02" not in codes, "同梱外フォントが混ざっている"
    assert "V06" not in codes, f"はみ出しがある: {[r.format() for r in results if r.code == 'V06']}"


def test_埋めれば描画漏れが消える(skeleton, tmp_path) -> None:
    """空段落（高さ 0）は WeasyPrint が落とすことがある。文字を入れれば解消することを固定する。

    docs/gotchas.md「段組内の長い段またぎ要素」「空の要素が落ちる」を参照。
    """
    from yakkan.models import dump_json
    from yakkan.render.weasy import render_source
    from yakkan.verify.checks import check_fragments, verify_dataset

    source = build(load_draft(skeleton.content_dir))
    # ×2 だと WeasyPrint の AssertionError の「帯」（docs/shared_fixes.md D2）に入る。
    # 帯は内容の長さで決まるので、長さを変えて外す。×3〜×5 はいずれも通る。
    filler = "この項は疎通確認のための仮置きの文です。" * 3

    def fill(node) -> None:
        if node.kind in ("paragraph", "item") and not (node.text or "").strip():
            node.text = filler
        for child in node.children:
            fill(child)

    for node in source.body + source.appendices:
        fill(node)

    style = load_style(load_blueprint(GENRE).default_style)
    result = render_source(source, style, tmp_path / "filled", render_png=False)
    dump_json(source, result.out_dir / "source.json")
    missing = check_fragments(source, result.layout)
    assert not missing, "\n".join(r.format() for r in missing)
    assert verify_dataset(result.out_dir) is not None
