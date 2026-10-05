"""blueprint・style・条文ライブラリの妥当性（docs/blueprints.md）。"""

from __future__ import annotations

import pytest

from keiyaku.blueprints import available_doctypes, load_blueprint
from keiyaku.library import available_clauses, load_clause
from keiyaku.styles import available_styles, load_style

#: P0（移植）時点では契約書の blueprint・style がまだ無い。docs/decisions.md 2026-09-26 の 27。
#: 条件はデータ駆動なので、P2 で blueprint・style を作った時点で自動的に有効になる。
pytestmark = pytest.mark.skipif(
    not available_doctypes() or not available_styles(),
    reason="blueprints/ と styles/ が無い（P2 で契約書のblueprint・styleを作ったら有効になる）",
)

DOCTYPES = available_doctypes()
STYLES = available_styles()
#: 条文ライブラリを持つ番号方式（docs/repo_layout.md）
SCHEMES = ("contract-standard",)

#: v1 で作る doctype（CLAUDE.md §4）。**作った順に足す**——
#: 「10 種そろっているか」を最初から assert すると P3〜P5 のあいだずっと赤いままになる。
V1_DOCTYPES = {
    "nda",
    "outsourcing",
    "delegation",
    "consulting",
    "purchase",
    "lease",
    "license",
    "sysdev",
    "contracting",
    "employment",
}


def test_導入済みのdoctypeはv1の一覧に含まれる() -> None:
    """綴り違い・想定外の doctype が紛れ込むのを防ぐ（10 種そろうのは P5 の完了時）。"""
    unknown = set(DOCTYPES) - V1_DOCTYPES
    assert not unknown, f"CLAUDE.md §4 に無い doctype: {sorted(unknown)}"


@pytest.mark.parametrize("genre", DOCTYPES)
def test_blueprintが読める(genre: str) -> None:
    bp = load_blueprint(genre)
    assert bp.doctype == genre
    assert bp.family == "contract"
    assert bp.target_pages[0] <= bp.target_pages[1] <= bp.page_limit, "目標ページが page_limit を超えている"
    assert bp.page_limit <= 20, "絶対上限 20 ページ（CLAUDE.md §0.4-5）"
    assert bp.budget.chars_min < bp.budget.chars_max


@pytest.mark.parametrize("genre", DOCTYPES)
def test_default_styleが存在する(genre: str) -> None:
    bp = load_blueprint(genre)
    assert bp.default_style in STYLES
    for style_id in bp.variants.styles:
        assert style_id in STYLES, f"{genre}: variants.styles の {style_id} が無い"


@pytest.mark.parametrize("genre", DOCTYPES)
def test_ノードidが一意(genre: str) -> None:
    ids = [n.id for n in load_blueprint(genre).iter_skeleton()]
    assert len(ids) == len(set(ids)), f"重複: {sorted({i for i in ids if ids.count(i) > 1})}"


@pytest.mark.parametrize("genre", DOCTYPES)
def test_参照する定型条が実在する(genre: str) -> None:
    bp = load_blueprint(genre)
    available = set(available_clauses(bp.numbering_scheme))
    for node in bp.iter_skeleton():
        if node.clause:
            assert node.clause in available, (
                f"{genre}: {node.clause} が library/clauses/{bp.numbering_scheme} に無い"
            )


@pytest.mark.parametrize("genre", DOCTYPES)
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
    from keiyaku.fonts import FONTS

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

    from keiyaku.library import LIBRARY_DIR

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


def test_条文ライブラリは常体で書かれている() -> None:
    """**契約書は全 doctype 常体**（CLAUDE.md §4・docs/style_guide.md §3）。

    ライブラリの文が敬体だと、そこを使った文書が lint L10 で警告される。
    """
    import re

    polite = re.compile(r"(ます|ません|です)[。、]")
    plain = re.compile(r"(する|とする|できる|ある|ない)。")
    for scheme in SCHEMES:
        text = "".join(
            p.text
            for c in available_clauses(scheme)
            for v in load_clause(scheme, c).variants
            for p in v.paragraphs
        )
        assert text, f"{scheme} の条文ライブラリが空"
        assert len(plain.findall(text)) > len(polite.findall(text)), f"{scheme} が常体になっていない"


def test_条文ライブラリは当事者をトークンで書く() -> None:
    """ライブラリは**位置**（`$a` `$b`）で書き、scaffold が実際の key に置き換える。

    生の「甲」「乙」を書くと、呼称プリセットを「委託者・受託者」に切り替えたときに食い違う。
    """
    import re

    for scheme in SCHEMES:
        for cid in available_clauses(scheme):
            for v in load_clause(scheme, cid).variants:
                for para in v.paragraphs:
                    assert not re.search(r"(?<![一-龠])[甲乙丙](?![一-龠])", para.text), (
                        f"{scheme}/{cid} が呼称を直書きしている（{{party:$a}} で書く）"
                    )
                    for token in re.findall(r"\{party:([^}]+)\}", para.text):
                        assert token.startswith("$"), (
                            f"{scheme}/{cid} が当事者 key を直書きしている: {token}"
                            "（key は doctype の presets で変わるので $a / $b で書く）"
                        )
