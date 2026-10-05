"""複数スタイル描画（S10-5・`HITL.md` H3 (c)）。

同じ内容を複数のレイアウトで描き、**文書数を増やさずに**レイアウト頑健性の評価データを増やす。
守るのは 2 点：正解（`policy.json`・`calc/`）は 1 組だけであること、
通らないスタイルは**そのスタイルだけ外して記録する**こと（文書を捨てない）。
"""

from __future__ import annotations

import json
from pathlib import Path

from conftest import BASE_CONTENT, needs_base

from insurance_contracts_calculation.config import EXTRA_STYLES, Settings
from insurance_contracts_calculation.generate import generate


@needs_base
def test_one_answer_set_for_many_layouts(tmp_path: Path) -> None:
    """2 つのスタイルで描いても、`policy.json` と `calc/` は 1 組だけ。"""
    result = generate(
        BASE_CONTENT,
        tmp_path,
        4,
        Settings.of("standard", png=False, styles=("nl-a4-2col-mincho", "nl-b5-2col-dense")),
    )
    man = json.loads((result.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))
    styles = [r["style"] for r in man["renders"]]
    assert len(styles) == 2, f"2 つのスタイルで描けていない: {styles}"
    assert len(set(styles)) == 2, "同じスタイルを 2 回描いている"

    # 描画結果はスタイルごと、正解は 1 組
    dirs = sorted(p.name for p in result.out_dir.iterdir() if p.is_dir() and p.name != "calc")
    assert len(dirs) == 2, f"描画結果がスタイルごとに分かれていない: {dirs}"
    for style in styles:
        assert (result.out_dir / f"{result.content_id}--{style}" / "layout.json").is_file()
    assert (result.out_dir / "policy.json").is_file()
    assert len(list((result.out_dir / "calc" / "programs").glob("*.py"))) == 1


@needs_base
def test_a_style_that_does_not_fit_is_dropped_with_a_reason(tmp_path: Path) -> None:
    """通らないスタイルは外して記録する。文書は捨てない。

    `auto` を 1 段組（`nl-a4-1col-gothic`）で描くと 23 ページになり上限を超える。
    それで文書ごと落とすと、スタイルを増やすほど文書が減って本末転倒になる。
    """
    result = generate(
        BASE_CONTENT,
        tmp_path,
        4,
        Settings.of("standard", png=False, styles=("nl-a4-2col-mincho", "nl-a4-1col-gothic")),
    )
    man = json.loads((result.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))
    styles = [r["style"] for r in man["renders"]]
    assert styles == ["nl-a4-2col-mincho"], f"通らないスタイルが残っている: {styles}"
    assert not (result.out_dir / f"{result.content_id}--nl-a4-1col-gothic").exists(), (
        "通らなかったスタイルの描画結果が残っている"
    )
    skipped = [s for s in man["plan"]["skipped"] if s.get("what") == "nl-a4-1col-gothic"]
    assert skipped, "外したスタイルが記録されていない（黙って省略してはいけない）"
    assert "ページ" in skipped[0]["why"], f"理由が書かれていない: {skipped[0]}"


@needs_base
def test_multi_style_uses_the_per_genre_default(tmp_path: Path) -> None:
    """`multi_style` は種目ごとの既定（`EXTRA_STYLES`）を使う。"""
    result = generate(BASE_CONTENT, tmp_path, 4, Settings.of("standard", png=False, multi_style=True))
    man = json.loads((result.out_dir / "calc" / "manifest.json").read_text(encoding="utf-8"))
    styles = [r["style"] for r in man["renders"]]
    assert styles[0] == "nl-a4-2col-mincho", f"先頭が既定のスタイルでない: {styles}"
    assert len(styles) >= 2, f"追加のスタイルで描けていない: {styles}"
    assert set(styles[1:]) <= set(EXTRA_STYLES["auto"]), f"EXTRA_STYLES の外のものが混ざった: {styles}"


def test_every_genre_has_an_extra_style() -> None:
    """計算規定のある 8 種目すべてに追加スタイルが定義されている。"""
    genres = ("auto", "quake", "health", "oneday", "travel", "golf", "group", "life")
    missing = [g for g in genres if not EXTRA_STYLES.get(g)]
    assert not missing, f"追加スタイルが無い種目: {missing}"
