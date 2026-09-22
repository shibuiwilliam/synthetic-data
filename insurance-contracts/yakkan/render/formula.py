"""算式の描画（docs/schema.md §5.6）。

`inline_boxes`：「Ａ＋Ｂ－Ｃ＝保険金の額」のように囲みと演算子を横に並べる。
`fraction`：分子・分母を横線で分けて積む。

SVG ではなく HTML/CSS で組む。文字が本文と同じフォント・同じテキスト層に載り、
往復検証（§6.9）でそのまま比較できるため。
"""

from __future__ import annotations

from html import escape

from yakkan.models import Formula, FormulaBox, FormulaFraction, FormulaOp


def formula_html(formula: Formula) -> str:
    """算式を HTML にする。各項に id を振り、`layout.json` から拾えるようにする。"""
    parts: list[str] = []
    for i, term in enumerate(formula.terms):
        term_id = f"{formula.id}__t{i}"
        if isinstance(term, FormulaBox):
            parts.append(
                f'<span class="fbox" id="{term_id}" data-kind="formula_box">{escape(term.box)}</span>'
            )
        elif isinstance(term, FormulaOp):
            parts.append(f'<span class="fop" id="{term_id}" data-kind="formula_op">{escape(term.op)}</span>')
        elif isinstance(term, FormulaFraction):
            parts.append(
                f'<span class="ffrac" id="{term_id}" data-kind="formula_fraction">'
                f'<span class="num" id="{term_id}_num" data-kind="formula_num">'
                f"{escape(term.fraction.num)}</span>"
                f'<span class="den" id="{term_id}_den" data-kind="formula_den">'
                f"{escape(term.fraction.den)}</span></span>"
            )
    layout_class = "formula formula-fraction" if formula.layout == "fraction" else "formula"
    return (
        f'<div class="{layout_class}" id="{formula.id}" data-kind="formula" '
        f'data-layout="{formula.layout}">{"".join(parts)}</div>'
    )


def formula_plain(formula: Formula) -> str:
    """平文（`derived.plain_text`）。分数は「分子 ／ 分母」と読ませる。"""
    out: list[str] = []
    for term in formula.terms:
        if isinstance(term, FormulaBox):
            out.append(term.box)
        elif isinstance(term, FormulaOp):
            out.append(term.op)
        elif isinstance(term, FormulaFraction):
            out.append(f"{term.fraction.num}／{term.fraction.den}")
    return "".join(out)
