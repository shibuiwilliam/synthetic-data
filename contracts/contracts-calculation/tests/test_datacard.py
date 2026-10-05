"""データカード（`<data>/data-card.md`）の常設テスト。仕様は `docs/data_card.md`。

守りたいこと：
- カードの数値は**実測から来る**（固定文字列に焼き込んでいない）。
- データを足したら更新され、更新を忘れたら `datacard check` が落ちる。
- 母数の小さい観点・未使用の宣言を黙って隠さない。
- 同じ `dataset/` なら同じカードが出る（決定論）。
"""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from contracts_calculation import base_adapter as ba
from contracts_calculation.bindings import engine as bindings_engine
from contracts_calculation.cli import main as cli_main
from contracts_calculation.export.datacard import (
    SMALL_SAMPLE_THRESHOLD,
    aggregate,
    check_card,
    collect,
    render,
    write_card,
)
from contracts_calculation.generate import generate_one

OUT = ba.calc_root() / "data" / "_test_datacard"


def _gen(base: str, sub: str, profile: str = "standard", calc_seed: int = 1):
    return generate_one(
        ba.repo_root() / "content" / base,
        calc_seed=calc_seed,
        out_root=OUT / sub,
        profile=profile,
        render=False,
    )


@pytest.fixture(scope="module")
def two_docs() -> Path:
    """2 文書ぶんの計算パック（描画なし）。"""
    root = OUT / "two"
    if root.exists():
        shutil.rmtree(root)
    _gen("nda-0001", "two")
    _gen("ots-0001", "two")
    return root


@pytest.fixture(scope="module", autouse=True)
def _cleanup():
    if OUT.exists():
        shutil.rmtree(OUT)
    yield
    shutil.rmtree(OUT, ignore_errors=True)


def test_card_is_deterministic(two_docs: Path) -> None:
    assert render(collect(two_docs)) == render(collect(two_docs))


def test_numbers_come_from_measurement(two_docs: Path) -> None:
    """文書を 1 件隠すとカードの数値が動く（固定文字列に焼き込んでいない）。"""
    facts = collect(two_docs)
    full = render(facts)
    assert f"| 文書（計算パック） | {len(facts.docs)} |" in full
    for doc in facts.docs:
        assert doc.content_id in full

    hidden = OUT / "hidden"
    shutil.rmtree(hidden, ignore_errors=True)
    hidden.mkdir(parents=True)
    victim = facts.docs[0].content_id
    shutil.move(str(two_docs / victim), str(hidden / victim))
    try:
        smaller = render(collect(two_docs))
    finally:
        shutil.move(str(hidden / victim), str(two_docs / victim))
    assert smaller != full
    assert f"| 文書（計算パック） | {len(facts.docs) - 1} |" in smaller
    assert victim not in smaller


def test_totals_match_independent_count(two_docs: Path) -> None:
    """規模の表の主要な数値を、カードの実装を通さずに数え直して突き合わせる。"""
    facts = collect(two_docs)
    text = render(facts)
    n_rules = n_cases = n_tasks = 0
    for pack in sorted(two_docs.glob("*/calc")):
        n_rules += len(json.loads((pack / "answer_key.json").read_text(encoding="utf-8")))
        n_cases += sum(1 for line in (pack / "cases.jsonl").read_text(encoding="utf-8").splitlines() if line)
        n_tasks += sum(1 for line in (pack / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if line)
    assert f"| ルール（計算・判定の規定） | {n_rules:,} |" in text
    assert f"| テストケース（`calc/cases.jsonl`） | {n_cases:,} |" in text
    assert f"| 評価用の関数（タスクカード `calc/tasks.jsonl`） | {n_tasks:,} |" in text


def test_check_detects_staleness_and_update_fixes_it(two_docs: Path) -> None:
    write_card(two_docs)
    ok, detail = check_card(two_docs)
    assert ok, detail

    _gen("csl-0001", "two")  # 文書を足す（カードは書き直していない）
    ok, detail = check_card(two_docs)
    assert not ok
    assert "古い" in detail

    write_card(two_docs)
    ok, detail = check_card(two_docs)
    assert ok, detail


def test_check_reports_missing_card(two_docs: Path) -> None:
    card = two_docs / "data-card.md"
    backup = card.read_text(encoding="utf-8") if card.is_file() else None
    card.unlink(missing_ok=True)
    try:
        ok, detail = check_card(two_docs)
    finally:
        if backup is not None:
            card.write_text(backup, encoding="utf-8")
    assert not ok
    assert "無い" in detail


def test_card_is_not_counted_in_its_own_size(two_docs: Path) -> None:
    """カード自身を数えると、書き出すたびに数が動いて鮮度検査が収束しない。"""
    write_card(two_docs)
    first = (two_docs / "data-card.md").read_text(encoding="utf-8")
    write_card(two_docs)
    assert (two_docs / "data-card.md").read_text(encoding="utf-8") == first


def test_small_sample_and_unused_are_named() -> None:
    """1 文書だけのデータセットでは、ほぼすべての観点が母数不足・大半の宣言が未使用になる。"""
    root = OUT / "one"
    shutil.rmtree(root, ignore_errors=True)
    result = _gen("nda-0002", "one")
    assert result.ok
    facts = collect(root)
    g = aggregate(facts)
    text = render(facts)
    assert "**母数の小さい観点**" in text
    small = [o for o in g.observations if o.docs < SMALL_SAMPLE_THRESHOLD]
    assert small, "1 文書なら母数不足の観点が出るはず"
    for pattern in facts.docs[0].patterns:
        assert f"`{pattern}`" in text
    assert "**宣言はあるが使っている文書が 0 の観点**" in text
    used = {r.pattern for r in facts.docs[0].rules}
    unused = [pid for pid, _ in facts.declared_patterns if pid not in used]
    assert unused, "31 パターンのうち使われていないものがあるはず"
    assert f"`{unused[0]}`" in text


def test_generate_refreshes_readme_and_card() -> None:
    """データを足す経路（CLI generate）が README とカードを書き直す。"""
    root = OUT / "cli"
    shutil.rmtree(root, ignore_errors=True)
    code = cli_main(
        [
            "generate",
            "--base",
            str(ba.repo_root() / "content" / "nda-0001"),
            "--calc-seed",
            "1",
            "--out",
            str(root),
            "--no-render",
        ]
    )
    assert code == 0
    assert (root / "README.md").is_file()
    assert (root / "data-card.md").is_file()
    ok, detail = check_card(root)
    assert ok, detail
    assert cli_main(["datacard", "check", "--data", str(root)]) == 0


def test_declared_bindings_match_implementation() -> None:
    """宣言（カードが使う一覧）と実装が返すバインディング名が一致する。"""
    source = Path(bindings_engine.__file__).read_text(encoding="utf-8")
    returned = set(re.findall(r'BoundRule\(binding="([^"]+)"', source))
    assert returned == set(bindings_engine.DECLARED_BINDINGS)
    assert set(bindings_engine.BINDING_TITLES) == set(bindings_engine.DECLARED_BINDINGS)
    patterns = set(re.findall(r'"pattern": "(B-[A-Z]+)"', source))
    assert patterns == set(bindings_engine.BINDING_PATTERNS)
    assert set(bindings_engine.BINDING_PATTERNS.values()) == set(bindings_engine.DECLARED_BINDINGS)


def test_card_has_no_machine_local_paths(two_docs: Path) -> None:
    text = render(collect(two_docs))
    assert str(ba.repo_root()) not in text
    assert "/Users/" not in text


def test_no_pdf_is_stated_not_hidden(two_docs: Path) -> None:
    """描画していないデータセットでは、空の表ではなく「PDF が無い」と書く。"""
    text = render(collect(two_docs))
    assert "PDF が無い文書が" in text  # §1 の警告
    assert "には PDF が無い" in text  # §6 の本文
    assert "| style_id | 文書 | ページ | PDF に埋め込まれていたフォント |" not in text


def test_pdf_is_measured_with_stdlib_only() -> None:
    """PDF のページ数とフォントを re + zlib で実測できる（規則12：実行時は標準ライブラリだけ）。"""
    from contracts_calculation.export.datacard import _scan_pdf

    candidates = sorted(ba.calc_root().glob("dataset/*/*.pdf")) or sorted(
        ba.calc_root().glob("data/*/*/*.pdf")
    )
    if not candidates:
        pytest.skip("描画済みの計算パックがローカルに無い（dataset/ は生成物）")
    facts = _scan_pdf(candidates[0])
    assert facts.page_count >= 1
    assert facts.embedded_fonts
    assert all("+" not in f for f in facts.embedded_fonts), "サブセット接頭辞を外していない"
