"""scaffold → lint → build → render → verify の疎通（P4-b の DoD）。

空のスケルトンは**未執筆なので lint と verify が指摘を出すのが正しい**。
ここで確かめるのは「5 段すべてが最後まで走ること」と、
「指摘の中身が『未執筆』を指していること」。
"""

from __future__ import annotations

import pytest

from keiyaku.blueprints import available_doctypes, load_blueprint
from keiyaku.build import build
from keiyaku.compose import load_draft
from keiyaku.lint.runner import lint_content
from keiyaku.scaffold import scaffold
from keiyaku.styles import available_styles, load_style

#: P0（移植）時点では契約書の blueprint・style がまだ無い。docs/decisions.md 2026-09-26 の 27。
#: 条件はデータ駆動なので、P2 で blueprint・style を作った時点で自動的に有効になる。
pytestmark = pytest.mark.skipif(
    not available_doctypes() or not available_styles(),
    reason="blueprints/ と styles/ が無い（P2 で契約書のblueprint・styleを作ったら有効になる）",
)

#: パイプラインの通し検査に使う doctype（最小の条文型）
GENRE = "nda"


@pytest.fixture(scope="module")
def skeleton(tmp_path_factory):
    root = tmp_path_factory.mktemp("pipeline")
    return scaffold(GENRE, "nda-pipeline", seed=1, root=root)


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
    # **契約書は目次を持たないのが普通**（docs/schema.md §2）。
    # 目次は blueprint が `front_matter.toc: true` を宣言した doctype（長文型）だけが持つ。
    from keiyaku.blueprints import load_blueprint

    if load_blueprint(GENRE).front_matter.toc:
        assert source.derived.toc, "目次を宣言しているのに作られていない"
    else:
        assert source.derived.toc == [], "目次を宣言していないのに作られている"
    # 定型条のプレースホルダが**残っていない**こと。
    # 「参照が 1 つ以上ある」は variant 次第（`{ref:$pN}` を持たない言い回しもある）なので、
    # 不変条件は「解決し残しが無い」ほう。`$pN`・`$a` が残ると build は素通りし、
    # 紙面に「{ref:$p1}」がそのまま出る。
    import re

    raw = source.model_dump_json()
    leftover = re.findall(r"\{(?:ref|party):\$[a-z0-9]+\}", raw)
    assert not leftover, f"ライブラリのプレースホルダが残っている: {sorted(set(leftover))}"
    # 当事者は必ず解決されている（契約書の骨格）
    assert source.derived.party_uses, "{party:} が 1 つも解決されていない"


#: 空段落（高さ 0）を埋める文。**空のままだと WeasyPrint の「帯」に入りやすい**
#: （`docs/gotchas.md`。2026-09-27：scaffold が空の別表 part を出さなくなった拍子に踏んだ）。
#: 描画を試す 3 本はこの充填を通してから描く。埋めるのは描画の前提であって、検査の対象ではない。
FILLER = "この項は疎通確認のための仮置きの文です。" * 3


def _filled(content_dir):
    """スケルトンを埋めた `Source`。空段落があると描画が不安定になる。"""
    source = build(load_draft(content_dir))

    def fill(node) -> None:
        if node.kind in ("paragraph", "item") and not (node.text or "").strip():
            node.text = FILLER
        for child in node.children:
            fill(child)

    for node in source.body + source.appendices:
        fill(node)
    return source


def test_4_renderが通る(skeleton, tmp_path) -> None:
    from keiyaku.render.weasy import render_source

    source = _filled(skeleton.content_dir)
    style = load_style(load_blueprint(GENRE).default_style)
    result = render_source(source, style, tmp_path / "out", render_png=False)
    assert result.page_count >= 1
    assert result.pdf_path.is_file()
    assert result.layout.elements, "layout に要素が 1 つも無い"


def test_5_verifyが走る(skeleton, tmp_path) -> None:
    from keiyaku.models import dump_json
    from keiyaku.render.weasy import render_source
    from keiyaku.verify.checks import verify_dataset

    source = _filled(skeleton.content_dir)
    style = load_style(load_blueprint(GENRE).default_style)
    result = render_source(source, style, tmp_path / "ds", render_png=False)
    dump_json(source, result.out_dir / "source.json")

    results = verify_dataset(result.out_dir)
    codes = {r.code for r in results}
    # 5 段すべて走った。未執筆の骨組みなので V04（目次のページ番号）や V05（描画漏れ）は出てよい
    assert "V02" not in codes, "同梱外フォントが混ざっている"
    assert "V06" not in codes, f"はみ出しがある: {[r.format() for r in results if r.code == 'V06']}"


def test_埋めれば描画漏れが消える(skeleton, tmp_path) -> None:
    """空段落（高さ 0）は WeasyPrint が落とすことがある。文字を入れれば解消することを固定する。

    docs/gotchas.md「段組内の長い段またぎ要素」「空の要素が落ちる」を参照。
    """
    from keiyaku.models import dump_json
    from keiyaku.render.weasy import render_source
    from keiyaku.verify.checks import check_fragments, verify_dataset

    source = _filled(skeleton.content_dir)

    style = load_style(load_blueprint(GENRE).default_style)
    result = render_source(source, style, tmp_path / "filled", render_png=False)
    dump_json(source, result.out_dir / "source.json")
    missing = check_fragments(source, result.layout)
    assert not missing, "\n".join(r.format() for r in missing)
    assert verify_dataset(result.out_dir) is not None


def test_7_source_staleness(skeleton, tmp_path) -> None:
    """執筆物を直したら `source.json` は古いと判定される（render が黙って旧版を描かないように）。

    render は `source.json` があればそれを使う。build を挟み忘れると**直す前の版が描かれる**。
    """
    import os

    from keiyaku.build import build_content, source_is_stale

    content_dir = skeleton.content_dir
    assert source_is_stale(content_dir) is True  # まだ build していない
    build_content(content_dir)
    assert source_is_stale(content_dir) is False

    part = sorted((content_dir / "parts").glob("*.json"))[0]
    built_at = (content_dir / "source.json").stat().st_mtime
    os.utime(part, (built_at + 10, built_at + 10))
    assert source_is_stale(content_dir) is True

    # 番号方式の宣言も build の入力（頭書の段落を無番号にしたとき気づけなかった）
    os.utime(part, (built_at - 10, built_at - 10))
    assert source_is_stale(content_dir) is False
    from keiyaku.numbering_spec import NUMBERING_DIR

    scheme = NUMBERING_DIR / "contract-standard.yaml"
    stat = scheme.stat()
    try:
        os.utime(scheme, (built_at + 10, built_at + 10))
        assert source_is_stale(content_dir) is True
    finally:
        os.utime(scheme, (stat.st_atime, stat.st_mtime))
