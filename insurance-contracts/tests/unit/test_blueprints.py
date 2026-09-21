"""blueprint・style・条文ライブラリの妥当性（docs/blueprints.md）。"""

from __future__ import annotations

import pytest

from yakkan.blueprints import available_genres, load_blueprint
from yakkan.library import available_clauses, load_clause
from yakkan.styles import available_styles, load_style

GENRES = available_genres()
STYLES = available_styles()
SCHEMES = ("nonlife", "life", "teikan")


def test_7ジャンルそろっている() -> None:
    assert set(GENRES) == {"auto", "oneday", "quake", "health", "life", "teikan", "travel"}


@pytest.mark.parametrize("genre", GENRES)
def test_blueprintが読める(genre: str) -> None:
    bp = load_blueprint(genre)
    assert bp.genre == genre
    assert bp.target_pages[0] <= bp.target_pages[1] <= 20, "目標ページが上限 20 を超えている"
    assert bp.budget.chars_min < bp.budget.chars_max


@pytest.mark.parametrize("genre", GENRES)
def test_default_styleが存在する(genre: str) -> None:
    bp = load_blueprint(genre)
    assert bp.default_style in STYLES
    for style_id in bp.variants.styles:
        assert style_id in STYLES, f"{genre}: variants.styles の {style_id} が無い"


@pytest.mark.parametrize("genre", GENRES)
def test_ノードidが一意(genre: str) -> None:
    ids = [n.id for n in load_blueprint(genre).iter_skeleton()]
    assert len(ids) == len(set(ids)), f"重複: {sorted({i for i in ids if ids.count(i) > 1})}"


@pytest.mark.parametrize("genre", GENRES)
def test_参照する定型条が実在する(genre: str) -> None:
    bp = load_blueprint(genre)
    available = set(available_clauses(bp.numbering_scheme))
    for node in bp.iter_skeleton():
        if node.clause:
            assert node.clause in available, (
                f"{genre}: {node.clause} が library/clauses/{bp.numbering_scheme} に無い"
            )


@pytest.mark.parametrize("genre", GENRES)
def test_字数見積りがbudgetの範囲に近い(genre: str) -> None:
    bp = load_blueprint(genre)
    planned = sum(n.chars for n in bp.iter_skeleton())
    assert planned > 0
    # skeleton の見積りは本文だけなので下限の 4 割以上あればよい（表・図・特約が上乗せされる）
    assert planned >= bp.budget.chars_min * 0.4, (
        f"{genre}: skeleton の字数 {planned} が budget に対して小さすぎる"
    )


@pytest.mark.parametrize("style_id", STYLES)
def test_styleが読めて較正値を持つ(style_id: str) -> None:
    style = load_style(style_id)
    assert style.style_id == style_id
    assert 500 <= style.chars_per_page_estimate <= 4000, (
        "chars_per_page_estimate が実測値の範囲から外れている"
    )
    assert style.page.content_width_pt() > 0
    assert style.column_width_pt() > 0


@pytest.mark.parametrize("style_id", STYLES)
def test_styleのフォントが同梱されている(style_id: str) -> None:
    from yakkan.fonts import FONTS

    families = {f.family for f in FONTS if f.exists}
    style = load_style(style_id)
    assert style.fonts.body in families, f"{style_id}: 本文フォント {style.fonts.body} が未同梱"
    assert style.fonts.heading in families, f"{style_id}: 見出しフォント {style.fonts.heading} が未同梱"


@pytest.mark.parametrize("scheme", SCHEMES)
def test_条文ライブラリが読める(scheme: str) -> None:
    clauses = available_clauses(scheme)
    assert clauses, f"{scheme} の定型条が無い"
    for clause_id in clauses:
        clause = load_clause(scheme, clause_id)
        assert clause.clause_id == clause_id
        assert clause.scheme == scheme
        assert clause.variants, f"{clause_id}: variants が空"
        for variant in clause.variants:
            assert variant.paragraphs, f"{clause_id}/{variant.id}: 項が無い"


@pytest.mark.parametrize("scheme", SCHEMES)
def test_ライブラリ本文に番号ラベルの直書きが無い(scheme: str) -> None:
    """CLAUDE.md §2-2。参照は {ref:$pN} で書く。"""
    import re

    literal = re.compile(r"第[0-9０-９]+[条章節項号]")
    for clause_id in available_clauses(scheme):
        for variant in load_clause(scheme, clause_id).variants:
            for i, paragraph in enumerate(variant.paragraphs):
                assert not literal.search(paragraph.text), f"{clause_id}/{variant.id} 第{i + 1}項に番号ラベル"


@pytest.mark.parametrize("scheme", SCHEMES)
def test_ライブラリが使う定数と用語を宣言している(scheme: str) -> None:
    import json
    import re

    from yakkan.library import LIBRARY_DIR

    for clause_id in available_clauses(scheme):
        raw = (LIBRARY_DIR / scheme / f"{clause_id}.json").read_text(encoding="utf-8")
        clause = load_clause(scheme, clause_id)
        used_consts = set(re.findall(r"\{const:([a-z_]+)\}", raw))
        assert used_consts <= set(clause.constants), (
            f"{clause_id}: 未宣言の const {used_consts - set(clause.constants)}"
        )
        used_terms = set(re.findall(r"\{term:([a-z_]+)\}", raw))
        assert used_terms <= set(clause.terms_used), (
            f"{clause_id}: 未宣言の term {used_terms - set(clause.terms_used)}"
        )
        json.loads(raw)


def test_文体がschemeに合っている() -> None:
    """nonlife / life は敬体、teikan は常体（docs/style_guide.md §7.3）。"""
    import re

    polite = re.compile(r"(ます|ません|です)[。、]")
    plain = re.compile(r"(する|とする|できる|ある)。")
    for scheme in ("nonlife", "life"):
        text = "".join(
            p.text
            for c in available_clauses(scheme)
            for v in load_clause(scheme, c).variants
            for p in v.paragraphs
        )
        assert len(polite.findall(text)) > len(plain.findall(text)), f"{scheme} が敬体になっていない"
    text = "".join(
        p.text
        for c in available_clauses("teikan")
        for v in load_clause("teikan", c).variants
        for p in v.paragraphs
    )
    assert len(plain.findall(text)) > len(polite.findall(text)), "teikan が常体になっていない"
