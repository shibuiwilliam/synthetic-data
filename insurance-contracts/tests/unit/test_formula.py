"""算式の描画（docs/schema.md §5.6）。"""

from __future__ import annotations

from yakkan.models import Formula
from yakkan.render.formula import formula_html, formula_plain

INLINE = Formula.model_validate(
    {
        "type": "formula",
        "id": "fml_payment",
        "alt": "損害の額から免責金額を差し引いた額が保険金の額になる。",
        "layout": "inline_boxes",
        "terms": [
            {"box": "損害の額"},
            {"op": "－"},
            {"box": "免責金額"},
            {"op": "＝"},
            {"box": "保険金の額"},
        ],
    }
)

FRACTION = Formula.model_validate(
    {
        "type": "formula",
        "id": "fml_rate",
        "alt": "既経過期間を保険期間で割った割合を保険料に掛ける。",
        "layout": "fraction",
        "terms": [
            {"box": "保険料"},
            {"op": "×"},
            {"fraction": {"num": "既経過期間の月数", "den": "保険期間の月数"}},
        ],
    }
)


def test_inline_boxes() -> None:
    html = formula_html(INLINE)
    assert 'data-layout="inline_boxes"' in html
    assert html.count('class="fbox"') == 3
    assert html.count('class="fop"') == 2
    assert 'id="fml_payment__t0"' in html


def test_fraction() -> None:
    html = formula_html(FRACTION)
    assert 'class="formula formula-fraction"' in html
    assert 'id="fml_rate__t2_num"' in html
    assert 'id="fml_rate__t2_den"' in html
    assert "既経過期間の月数" in html


def test_平文() -> None:
    assert formula_plain(INLINE) == "損害の額－免責金額＝保険金の額"
    assert formula_plain(FRACTION) == "保険料×既経過期間の月数／保険期間の月数"


def test_全項にidが付く() -> None:
    html = formula_html(FRACTION)
    for i in range(len(FRACTION.terms)):
        assert f'id="fml_rate__t{i}"' in html
