"""描画の golden テスト（P2 の DoD）。

**サンプルは `tests/golden/sample_min/` を使う。** 3 ページ・オリジナル文で、
表 4 点（列挙表 2・手続き表・等級表）・条末脚注・欄外注・目次・別表を含んでおり、
指示にあった `sample_render` の要件をそのまま満たすため、同じ内容を二重に持たない。

固定するもの
- `layout.json`（bbox は許容 0.5pt、それ以外は完全一致）
- PDF のテキスト層（完全一致）
- `verify` が error 0 件で通ること

更新は `uv run pytest --update-golden`。差分の理由をコミットメッセージに書く。
macOS では `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が要る（`make check` 経由なら自動）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from yakkan.build import build
from yakkan.compose import load_draft
from yakkan.models import dump_json
from yakkan.styles import load_style

SAMPLE = Path(__file__).parent / "sample_min"
GOLDEN_LAYOUT = Path(__file__).parent / "sample_min.layout.json"
GOLDEN_TEXT = Path(__file__).parent / "sample_min.text.txt"
STYLE_ID = "nl-a4-2col-mincho"
BBOX_TOLERANCE = 0.5


@pytest.fixture(scope="module")
def rendered(tmp_path_factory):
    from yakkan.render.weasy import render_source

    source = build(load_draft(SAMPLE))
    style = load_style(STYLE_ID)
    out = tmp_path_factory.mktemp("render")
    result = render_source(source, style, out / f"{source.content_id}--{STYLE_ID}")
    dump_json(source, result.out_dir / "source.json")
    return source, style, result


def pdf_text(pdf_path: Path) -> str:
    import pdfplumber

    with pdfplumber.open(pdf_path) as pdf:
        return "\n".join("".join(c["text"] for c in page.chars) for page in pdf.pages)


def test_3ページになる(rendered) -> None:
    _source, _style, result = rendered
    assert result.page_count == 3
    assert len(result.png_paths) == 3


def test_verifyがerror0で通る(rendered) -> None:
    from yakkan.verify.checks import verify_dataset

    _source, _style, result = rendered
    results = verify_dataset(result.out_dir)
    errors = [r for r in results if r.severity == "error"]
    assert not errors, "\n".join(r.format() for r in results)


def test_決定論_2回描画して一致する(rendered, tmp_path) -> None:
    from yakkan.verify.checks import check_determinism

    source, style, _result = rendered
    results = check_determinism(source, style, tmp_path)
    assert not results, "\n".join(r.format() for r in results)


def test_テキスト層のgolden(rendered, update_golden: bool) -> None:
    _source, _style, result = rendered
    actual = pdf_text(result.pdf_path)
    if update_golden or not GOLDEN_TEXT.exists():
        GOLDEN_TEXT.write_text(actual, encoding="utf-8")
        if not update_golden:
            pytest.fail(f"golden を作成した: {GOLDEN_TEXT}（内容を確認してコミットする）")
        return
    assert actual == GOLDEN_TEXT.read_text(encoding="utf-8"), "テキスト層が golden と一致しない"


def test_layoutのgolden(rendered, update_golden: bool) -> None:
    _source, _style, result = rendered
    actual = json.loads(dump_json(result.layout))
    if update_golden or not GOLDEN_LAYOUT.exists():
        GOLDEN_LAYOUT.write_text(json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        if not update_golden:
            pytest.fail(f"golden を作成した: {GOLDEN_LAYOUT}（内容を確認してコミットする）")
        return
    expected = json.loads(GOLDEN_LAYOUT.read_text(encoding="utf-8"))
    diffs = compare(actual, expected, path="")
    assert not diffs, "layout.json が golden と一致しない:\n" + "\n".join(diffs[:20])


def compare(actual, expected, path: str) -> list[str]:
    """bbox だけ許容 0.5pt、他は完全一致で比べる。"""
    if path.endswith(("bbox", "page_size_pt")) and isinstance(actual, list) and isinstance(expected, list):
        if len(actual) != len(expected):
            return [f"{path}: 要素数が違う {len(actual)} != {len(expected)}"]
        return [
            f"{path}[{i}]: {a} != {e}（許容 {BBOX_TOLERANCE}pt）"
            for i, (a, e) in enumerate(zip(actual, expected, strict=True))
            if abs(a - e) > BBOX_TOLERANCE
        ]
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: 型が違う"]
        diffs = (
            [
                f"{path}: キーが違う（不足 {sorted(set(expected) - set(actual))[:5]}"
                f" / 余分 {sorted(set(actual) - set(expected))[:5]}）"
            ]
            if set(actual) != set(expected)
            else []
        )
        for key in sorted(set(actual) & set(expected)):
            diffs += compare(actual[key], expected[key], f"{path}.{key}" if path else key)
        return diffs
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            got = len(actual) if isinstance(actual, list) else "?"
            return [f"{path}: 配列の長さが違う {got} != {len(expected)}"]
        diffs = []
        for i, (a, e) in enumerate(zip(actual, expected, strict=True)):
            diffs += compare(a, e, f"{path}[{i}]")
        return diffs
    if isinstance(expected, float) and isinstance(actual, int | float):
        return [] if abs(actual - expected) <= BBOX_TOLERANCE else [f"{path}: {actual} != {expected}"]
    return [] if actual == expected else [f"{path}: {actual!r} != {expected!r}"]
