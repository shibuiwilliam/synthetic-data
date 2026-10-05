"""規律（`CLAUDE.md`「守ること」）を機械で守らせるテスト。"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest

SRC = Path(__file__).resolve().parents[2] / "src" / "insurance_contracts_calculation"
ROOT = Path(__file__).resolve().parents[2]


def _modules() -> list[Path]:
    return sorted(SRC.rglob("*.py"))


def test_only_base_adapter_imports_the_base() -> None:
    """本体（yakkan）を import してよいのは `base_adapter.py` だけ（TASK.md S1-1）。"""
    offenders = []
    for path in _modules():
        if path.name == "base_adapter.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(n == "yakkan" or n.startswith("yakkan.") for n in names):
                offenders.append(f"{path.relative_to(SRC)}:{node.lineno}")
    assert not offenders, "本体を import しているのは base_adapter.py だけであるべき: " + ", ".join(offenders)


def test_no_module_level_random() -> None:
    """乱数は引数で渡された `random.Random` だけを使う（決定性）。"""
    bad = []
    for path in _modules():
        text = path.read_text(encoding="utf-8")
        for m in re.finditer(r"\brandom\.(random|randint|choice|shuffle|sample|randrange)\(", text):
            line = text[: m.start()].count("\n") + 1
            bad.append(f"{path.relative_to(SRC)}:{line}")
    assert not bad, "モジュール関数の random.* を使っている: " + ", ".join(bad)


def test_no_wall_clock_or_uuid_or_hash() -> None:
    """生成物に時刻・uuid・`hash()` を混ぜない（決定性）。"""
    bad = []
    for path in _modules():
        text = path.read_text(encoding="utf-8")
        for pat in (r"datetime\.now\(", r"\btime\.time\(", r"\buuid\b", r"(?<![\w.])hash\("):
            for m in re.finditer(pat, text):
                line = text[: m.start()].count("\n") + 1
                bad.append(f"{path.relative_to(SRC)}:{line} {pat}")
    assert not bad, "決定性を壊す呼び出しがある: " + ", ".join(bad)


def test_patterns_have_no_japanese_prose() -> None:
    """パターンのコードに日本語の文型を置かない（DESIGN.md §7.2・TASK.md S2-5）。

    語彙は `packs/*.yaml`、文型は `realize/lexicon_ja.py` にある。
    docstring とコメントは説明なので対象外。
    """
    sentence = re.compile(r"[ぁ-んァ-ヶ一-龥][^\"']*?(?:します|ます。|しません|とします)")
    bad = []
    for path in sorted((SRC / "patterns").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        # docstring（説明）は対象外。単独の文字列式がそれに当たる
        docstrings = {
            id(n.value)
            for n in ast.walk(tree)
            if isinstance(n, ast.Expr)
            and isinstance(n.value, ast.Constant)
            and isinstance(n.value.value, str)
        }
        for node in ast.walk(tree):
            is_prose = isinstance(node, ast.Constant) and isinstance(node.value, str)
            if is_prose and id(node) not in docstrings and sentence.search(node.value):
                bad.append(f"{path.name}:{node.lineno} {node.value[:30]}")
    assert not bad, "パターンに日本語の文がある（packs / lexicon_ja へ移す）: " + ", ".join(bad)


def test_no_write_path_into_dataset() -> None:
    """本体の `dataset/` に書く経路が無いこと（manifest check が壊れる。TASK.md §2.5）。"""
    from insurance_contracts_calculation.export.layout import OutputError, check_out_dir

    with pytest.raises(OutputError):
        check_out_dir(ROOT.parent / "dataset" / "auto-0001-c1")
    with pytest.raises(OutputError):
        check_out_dir(ROOT.parent / "dataset")
    assert check_out_dir(ROOT / "out")


def test_own_dataset_dir_is_writable() -> None:
    """拡張自身の `dataset/` は出力先に選べること（名前だけで塞がない。TASK.md §2.5）。"""
    from insurance_contracts_calculation.export.layout import check_out_dir

    assert check_out_dir(ROOT / "dataset") == (ROOT / "dataset").resolve()
    assert check_out_dir(ROOT / "dataset" / "auto-0001-c1")


def test_generated_programs_use_stdlib_only() -> None:
    """正解プログラムは標準ライブラリだけで動く（DESIGN.md §11.1）。"""
    for path in sorted((ROOT / "examples").rglob("programs/*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module:
                assert node.module.split(".")[0] in ("calendar", "datetime"), node.module
            if isinstance(node, ast.Import):
                for a in node.names:
                    assert a.name.split(".")[0] in ("calendar", "datetime"), a.name


def test_doc_suffix_numbers_the_variants() -> None:
    """文書IDの接尾は何本目かで決まる（1 本目は従来どおり `c1`）。"""
    import pytest as _pytest

    from insurance_contracts_calculation.generate import DOC_SUFFIX, doc_suffix

    assert doc_suffix() == DOC_SUFFIX == "c1"
    assert doc_suffix(1) == "c1"
    assert (doc_suffix(2), doc_suffix(3)) == ("c2", "c3")
    with _pytest.raises(ValueError):
        doc_suffix(0)


def test_variant_is_not_mixed_into_the_random_keys() -> None:
    """何本目かは乱数に入れない（入れると 1 本目の出力が変わる）。

    番号だけ変えても中身は同じになるので、`batch` は seed をずらす。その幅を固定する。
    """
    from insurance_contracts_calculation.batch import VARIANT_SEED_STEP
    from insurance_contracts_calculation.config import Settings

    assert Settings.of().variant == 1
    assert Settings.of(variant=2).variant == 2
    assert VARIANT_SEED_STEP >= 1000, "RETRIES の seed のずらし幅（最大 500）より大きいこと"
