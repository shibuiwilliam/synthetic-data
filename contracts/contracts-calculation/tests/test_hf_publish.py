"""Hugging Face 公開形の検査（docs/hf_publish.md）。

要点は 3 つ。
1. 公開してはいけないものが 1 つも入らない（許可リスト方式が効いている）。
2. 公開前ゲート P1〜P6 が、壊したときに**実際に落ちる**（検査が飾りでないこと）。
3. 2 回組み立てて全ファイルが一致する（P7 決定性）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from contracts_calculation.export import hf

CALC_ROOT = Path(__file__).resolve().parents[1]
#: 実データがあるときだけ回す検査の対象（無ければ skip）
DATASETS = [CALC_ROOT / "dataset", CALC_ROOT / "data" / "standard"]


def _any_dataset() -> Path:
    for root in DATASETS:
        if root.is_dir() and any(root.glob("*/calc/manifest.json")):
            return root
    pytest.skip("計算パックのあるデータセットが無い（generate で作る）")


def _build(tmp_path: Path, **kw) -> hf.PublishResult:
    return hf.build(_any_dataset(), tmp_path / "hf", calc_root=CALC_ROOT, **kw)


# --- 公開してはいけないものが入らない ---------------------------------------------


def test_公開形に副産物とデバッグ出力が入らない(tmp_path: Path) -> None:
    result = _build(tmp_path)
    for name in result.files:
        parts = Path(name).parts
        assert "_work" not in parts, name
        assert "_render" not in parts, name
        assert "__pycache__" not in parts, name
        assert not name.endswith(".pyc"), name
        assert Path(name).name != "render.html", name


def test_公開形に絶対パスとユーザー名が無い(tmp_path: Path) -> None:
    """`render.html` はローカルの絶対パスを含む。除外できていることを中身で確かめる。"""
    result = _build(tmp_path)
    pats = hf._secrets_patterns()
    assert pats, "検査語が空だと検査にならない"
    for name in result.files:
        path = result.out_root / name
        if path.suffix not in hf._TEXT_SUFFIXES:
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for pat in pats:
            assert pat not in text, f"{name} に {pat} が漏れている"


def test_全ゲートが通る(tmp_path: Path) -> None:
    result = _build(tmp_path)
    ng = [(g, d) for g, ok, d in result.gates if not ok]
    assert not ng, ng
    assert result.ok


# --- 構造 -------------------------------------------------------------------------


def test_出題と正解が構造で分かれている(tmp_path: Path) -> None:
    result = _build(tmp_path)
    inputs = {Path(f).parts[2] for f in result.files if f.startswith("inputs/")}
    answers = {Path(f).parts[2] for f in result.files if f.startswith("answers/")}
    # 正解にしかないものが inputs に出ていない
    assert "spec.json" not in inputs
    assert "answer_key.json" not in inputs
    assert "cases.jsonl" not in inputs
    assert {"spec.json", "answer_key.json", "cases.jsonl"} <= answers
    # 出題に要るものは inputs にある
    assert {"contract.json", "tasks.jsonl", "calendar.json", "layout.json"} <= inputs


def test_no_answers_で正解が丸ごと落ちる(tmp_path: Path) -> None:
    result = _build(tmp_path, include_answers=False)
    assert not [f for f in result.files if f.startswith("answers/")]
    assert not [f for f in result.files if f == "data/cases.jsonl"]
    assert "data/tasks.jsonl" in result.files
    assert result.ok
    # カードの configs からも cases が消える
    card = (result.out_root / hf.README_NAME).read_text(encoding="utf-8")
    assert "path: data/cases.jsonl" not in card
    assert "正解は入っていない" in card


def test_平索引の行が揃っている(tmp_path: Path) -> None:
    """HF は JSONL を Arrow に変換する。行ごとにキーや型が揺れると落ちる。"""
    result = _build(tmp_path)
    for name in ("documents.jsonl", "rules.jsonl", "tasks.jsonl", "cases.jsonl"):
        rows = [
            json.loads(line)
            for line in (result.out_root / "data" / name).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        assert rows, name
        keysets = {tuple(sorted(r)) for r in rows}
        assert len(keysets) == 1, f"{name}: キー集合が {len(keysets)} 種ある"
        seen: dict[str, str] = {}
        for row in rows:
            for key, value in row.items():
                if value is None:
                    continue
                t = type(value).__name__
                assert seen.setdefault(key, t) == t, f"{name}:{key} の型が揺れている"


def test_平索引の件数がデータセットと一致する(tmp_path: Path) -> None:
    data_root = _any_dataset()
    result = _build(tmp_path)

    def _n(name: str) -> int:
        text = (result.out_root / "data" / name).read_text(encoding="utf-8")
        return len([line for line in text.splitlines() if line.strip()])

    docs = sorted(p for p in data_root.iterdir() if (p / "calc" / "manifest.json").is_file())
    assert _n("documents.jsonl") == len(docs) == result.n_docs
    n_rules = sum(len(json.loads((d / "calc" / "answer_key.json").read_text(encoding="utf-8"))) for d in docs)
    assert _n("rules.jsonl") == n_rules
    n_cases = sum(
        len(
            [ln for ln in (d / "calc" / "cases.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
        )
        for d in docs
    )
    assert _n("cases.jsonl") == n_cases


# --- カードとライセンス -----------------------------------------------------------


def test_ライセンス未決なら未決と書く(tmp_path: Path) -> None:
    result = _build(tmp_path)
    assert result.license_id == hf.UNDECIDED_LICENSE
    card = (result.out_root / hf.README_NAME).read_text(encoding="utf-8")
    fm = card.split("---\n", 2)[1]
    assert f"license: {hf.UNDECIDED_LICENSE}" in fm
    assert f"license_name: {hf.UNDECIDED_LICENSE_NAME}" in fm
    assert f"license_link: {hf.NOTICE_NAME}" in fm  # HF は other のとき link も要る
    assert "配布条件は未決" in card
    notice = (result.out_root / hf.NOTICE_NAME).read_text(encoding="utf-8")
    assert "未決" in notice


def test_ライセンスを渡すと全面に反映される(tmp_path: Path) -> None:
    result = _build(tmp_path, license_id="cc-by-4.0")
    card = (result.out_root / hf.README_NAME).read_text(encoding="utf-8")
    assert "license: cc-by-4.0" in card.split("---\n", 2)[1]
    assert "配布条件は未決" not in card
    assert "cc-by-4.0" in (result.out_root / hf.NOTICE_NAME).read_text(encoding="utf-8")
    # 詳細カードの §12（未決と書いてある）が README と食い違ったままにならない
    detail = (result.out_root / "data-card.md").read_text(encoding="utf-8")
    assert "に決まった" in detail


def test_カードに架空性と免責がある(tmp_path: Path) -> None:
    result = _build(tmp_path)
    for name in (hf.README_NAME, hf.NOTICE_NAME):
        text = (result.out_root / name).read_text(encoding="utf-8")
        assert "架空" in text
        assert "法的に有効な契約書では" in text


def test_埋め込みフォントのライセンスを実測から書く(tmp_path: Path) -> None:
    result = _build(tmp_path)
    notice = (result.out_root / hf.NOTICE_NAME).read_text(encoding="utf-8")
    data_root = _any_dataset()
    has_pdf = any(data_root.glob("*/*.pdf"))
    if has_pdf:
        assert "SIL Open Font License 1.1" in notice
        assert "ライセンス未同定" not in notice, "同定できないフォントがある。配布前に確認する"
    else:
        assert "埋め込みフォントは無い" in notice


def test_pdf_が_lfs_に送られる(tmp_path: Path) -> None:
    result = _build(tmp_path)
    ga = (result.out_root / hf.GITATTRIBUTES_NAME).read_text(encoding="utf-8")
    assert "*.pdf filter=lfs" in ga


# --- 決定性と安全策 ---------------------------------------------------------------


def test_2回組み立てて一致する(tmp_path: Path) -> None:
    a = hf.build(_any_dataset(), tmp_path / "a", calc_root=CALC_ROOT)
    b = hf.build(_any_dataset(), tmp_path / "b", calc_root=CALC_ROOT)
    assert a.files == b.files
    for name in a.files:
        assert (a.out_root / name).read_bytes() == (b.out_root / name).read_bytes(), name


def test_dataset_の中には出力しない(tmp_path: Path) -> None:
    """生成物を書き換えないための歯止め（CLAUDE.md 規則 2）。"""
    data_root = _any_dataset()
    with pytest.raises(ValueError):
        hf.build(data_root, data_root, calc_root=CALC_ROOT)
    with pytest.raises(ValueError):
        hf.build(data_root, data_root / "hf", calc_root=CALC_ROOT)


def test_計算パックが無ければ失敗する(tmp_path: Path) -> None:
    empty = tmp_path / "empty"
    empty.mkdir()
    with pytest.raises(FileNotFoundError):
        hf.build(empty, tmp_path / "out", calc_root=CALC_ROOT)


# --- ゲートが飾りでないこと（壊したら落ちる） -------------------------------------


def _gate(out_root: Path, data_root: Path, gate: str) -> tuple[bool, str]:
    results = hf.run_gates(out_root, data_root, include_answers=True, calc_root=CALC_ROOT)
    for name, ok, detail in results:
        if name == gate:
            return ok, detail
    raise AssertionError(f"{gate} が無い")


def test_P1_想定外のファイルを混ぜると落ちる(tmp_path: Path) -> None:
    result = _build(tmp_path)
    (result.out_root / "inputs" / "stray.txt").write_text("x", encoding="utf-8")
    ok, detail = _gate(result.out_root, _any_dataset(), "P1")
    assert not ok and "stray.txt" in detail


def test_P2_絶対パスを混ぜると落ちる(tmp_path: Path) -> None:
    result = _build(tmp_path)
    (result.out_root / "data" / "documents.jsonl").write_text(
        '{"x": "/Users/someone/secret"}\n', encoding="utf-8"
    )
    ok, _ = _gate(result.out_root, _any_dataset(), "P2")
    assert not ok


def test_P3_pycache_を混ぜると落ちる(tmp_path: Path) -> None:
    result = _build(tmp_path)
    d = min((result.out_root / "answers").iterdir()) / "__pycache__"
    d.mkdir(parents=True, exist_ok=True)
    (d / "x.pyc").write_bytes(b"\x00")
    ok, _ = _gate(result.out_root, _any_dataset(), "P3")
    assert not ok


def test_P4_実在名称を混ぜると落ちる(tmp_path: Path) -> None:
    result = _build(tmp_path)
    repl = hf.load_replacements(CALC_ROOT)
    if not repl:
        pytest.skip("禁止名称の一覧が空")
    name = min(repl)
    (result.out_root / "data" / "documents.jsonl").write_text(
        json.dumps({"x": name}, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    ok, detail = _gate(result.out_root, _any_dataset(), "P4")
    assert not ok and name in detail


def test_P5_文書を落とすと落ちる(tmp_path: Path) -> None:
    import shutil

    result = _build(tmp_path)
    victim = min((result.out_root / "inputs").iterdir())
    shutil.rmtree(victim)
    ok, _ = _gate(result.out_root, _any_dataset(), "P5")
    assert not ok


def test_P6_configs_が壊れていると落ちる(tmp_path: Path) -> None:
    result = _build(tmp_path)
    (result.out_root / "data" / "rules.jsonl").unlink()
    ok, detail = _gate(result.out_root, _any_dataset(), "P6")
    assert not ok and "rules.jsonl" in detail


def test_P6_frontmatter_が無いと落ちる(tmp_path: Path) -> None:
    result = _build(tmp_path)
    (result.out_root / hf.README_NAME).write_text("# no frontmatter\n", encoding="utf-8")
    ok, detail = _gate(result.out_root, _any_dataset(), "P6")
    assert not ok and "frontmatter" in detail
