"""`yakkan/datacard.py`（`dataset/data-card.md` の生成）。仕様は `docs/data_card.md`。

検査するのは 5 つ。

1. **統計値を固定文字列に焼き込んでいない**こと（文書を減らしたら数が動く）。
2. **鮮度検査が古さを検出する**こと（文書を足したら `check` が落ちる）。
3. **母数の小さい観点・使用 0 の観点を自動で挙げる**こと。
4. **決定論**（同じ `dataset/` なら同じカード）。
5. **`status: failed` の文書で落ちない**こと（`answer.json` / `qa.json` / `*.jsonl` が無い）。

実データを 2〜3 文書だけ tmp へ写して小さな `dataset/` を組む。`dataset/` が無い環境では飛ばす。
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from yakkan.datacard import (
    CARD_NAME,
    MIN_CONTENTS,
    all_blocks,
    check,
    collect,
    render_card,
    write_card,
)

DATASET = Path("dataset")
MANIFEST = DATASET / "manifest.json"
needs_dataset = pytest.mark.skipif(not MANIFEST.exists(), reason="dataset/ が無い")


def _manifest_entries() -> list[dict]:
    return json.loads(MANIFEST.read_text(encoding="utf-8"))["documents"]


def _mini(tmp_path: Path, doc_ids: list[str]) -> Path:
    """指定した文書だけを含む小さな `dataset/` を tmp に作る。"""
    entries = {d["doc_id"]: d for d in _manifest_entries()}
    out = tmp_path / "dataset"
    out.mkdir(parents=True, exist_ok=True)
    for doc_id in doc_ids:
        shutil.copytree(DATASET / doc_id, out / doc_id)
    payload = {
        "schema_version": "1.0",
        "dataset_version": "test",
        "corpus_artifacts": [],
        "documents": [entries[doc_id] for doc_id in doc_ids],
    }
    (out / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return out


def _ready_ids(count: int, *, genre: str | None = None) -> list[str]:
    rows = [d for d in _manifest_entries() if d["status"] == "ready"]
    if genre:
        rows = [d for d in rows if d["genre"] == genre]
    return [d["doc_id"] for d in rows[:count]]


# --- 焼き込み禁止 -------------------------------------------------------------


@needs_dataset
def test_カードの数値は文書構成に追従する(tmp_path: Path) -> None:
    """**固定文字列に統計値を焼き込まない。**

    `dataset/README.md` は以前「1,944 クエリ中 28 件」を直書きしており、文書構成が
    変わっても `yakkan export` を再実行するだけでは更新されなかった
    （`docs/decisions.md` 2026-10-04）。同じ失敗をカードで繰り返さない。
    """
    ids = _ready_ids(3)
    assert len(ids) == 3, "ready な文書が 3 本以上要る"
    big = render_card(collect(_mini(tmp_path / "a", ids)))
    small = render_card(collect(_mini(tmp_path / "b", ids[:1])))
    assert "**3 文書**" in big
    assert "**1 文書**" in small
    assert big != small
    # 実測値が本文に出ていること（表だけでなく §1 の文にも入る）
    entries = {d["doc_id"]: d for d in _manifest_entries()}
    assert f"**{sum(entries[i]['pages'] for i in ids):,} ページ**" in big
    assert f"**{sum(entries[i]['qa_items'] for i in ids):,} 問**" in big


@needs_dataset
def test_規模の実測値がmanifestと一致する(tmp_path: Path) -> None:
    ids = _ready_ids(3)
    entries = {d["doc_id"]: d for d in _manifest_entries()}
    stats = collect(_mini(tmp_path, ids))
    assert stats.scale.documents == len(ids)
    assert stats.scale.ready == len(ids)
    assert stats.scale.failed == 0
    assert stats.scale.pages == sum(entries[i]["pages"] for i in ids)
    assert stats.scale.chars == sum(entries[i]["chars"] for i in ids)
    assert stats.scale.qa_items == sum(entries[i]["qa_items"] for i in ids)
    assert stats.scale.tables == sum(entries[i]["tables"] for i in ids)
    assert stats.scale.figures == sum(entries[i]["figures"] for i in ids)
    assert stats.dataset_version == "test"


# --- 鮮度検査 -----------------------------------------------------------------


@needs_dataset
def test_checkは文書を足すと古さを検出する(tmp_path: Path) -> None:
    ids = _ready_ids(2)
    base = _mini(tmp_path, ids[:1])
    write_card(base)
    assert check(base) == []

    # 文書を 1 本足して manifest を書き換える（= `datacard update` を忘れた状態）
    shutil.copytree(DATASET / ids[1], base / ids[1])
    entries = {d["doc_id"]: d for d in _manifest_entries()}
    payload = json.loads((base / "manifest.json").read_text(encoding="utf-8"))
    payload["documents"].append(entries[ids[1]])
    (base / "manifest.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")

    problems = check(base)
    assert problems, "文書が増えたのにカードが古いままなら検出するはず"
    assert any("一致しない" in line for line in problems)
    # 更新すれば通る
    write_card(base)
    assert check(base) == []


@needs_dataset
def test_checkはカードが無いことを報告する(tmp_path: Path) -> None:
    base = _mini(tmp_path, _ready_ids(1))
    problems = check(base)
    assert len(problems) == 1
    assert CARD_NAME in problems[0]


def test_manifestが無ければcheckは案内だけ返す(tmp_path: Path) -> None:
    (tmp_path / "dataset").mkdir()
    problems = check(tmp_path / "dataset")
    assert len(problems) == 1
    assert "manifest.json が無い" in problems[0]


# --- 決定論 -------------------------------------------------------------------


@needs_dataset
def test_同じdatasetなら同じカードが出る(tmp_path: Path) -> None:
    """`datetime.now()` を入れないこと・自分自身を数えないこと。

    カードのファイルサイズを容量に数えると、書き出すたびに数が動いて鮮度検査が
    収束しない（`docs/data_card.md` §4.1）。
    """
    base = _mini(tmp_path, _ready_ids(2))
    first = render_card(collect(base))
    write_card(base)
    # 1 度書き出したあとに測り直しても同じ（自分自身を数えていない）
    second = render_card(collect(base))
    assert first == second
    write_card(base)
    assert (base / CARD_NAME).read_text(encoding="utf-8") == first


# --- 観点の自動検出 -----------------------------------------------------------


@needs_dataset
def test_母数の小さい観点と使用0の観点を挙げる(tmp_path: Path) -> None:
    base = _mini(tmp_path, _ready_ids(1))
    stats = collect(base)
    # 1 content しか無いので、覆っている観点はすべて「母数が足りない」
    assert stats.thin, "1 content なら母数不足の観点が挙がるはず"
    assert all(0 < c.contents < MIN_CONTENTS for c in stats.thin)
    # 宣言はあるが使われていない観点（表の意味種別・図の種別・他ジャンル・他 style）
    assert stats.unused
    assert all(c.contents == 0 for c in stats.unused)
    card = render_card(stats)
    assert "母数の小さい観点" in card
    assert "宣言はあるが使っている文書が 0 の観点" in card


@needs_dataset
def test_条文型と丸数字型は条ラベルの形で分かれる(tmp_path: Path) -> None:
    """**ノード種別では分かれない。**

    `jyusetsu`（重要事項説明書）は blueprint で「条を持たない」と宣言しているが、
    実装は他のジャンルと同じ `kind: "article"` のノードを使い、番号方式が「①」と
    振るだけである（`docs/data_card.md` §4.3）。
    """
    jyusetsu = _ready_ids(1, genre="jyusetsu")
    nonlife = _ready_ids(1, genre="teikan")
    if not jyusetsu or not nonlife:
        pytest.skip("jyusetsu と teikan の ready な文書が要る")
    names = {
        name: {
            c.name
            for c in collect(_mini(tmp_path / name, ids)).coverage
            if c.group == "骨格" and c.contents > 0
        }
        for name, ids in (("jyusetsu", jyusetsu), ("teikan", nonlife))
    }
    assert any("丸数字型" in n for n in names["jyusetsu"])
    assert not any("条文型" in n for n in names["jyusetsu"])
    assert any("条文型" in n for n in names["teikan"])
    assert not any("丸数字型" in n for n in names["teikan"])


@needs_dataset
def test_front_matterの表も数える() -> None:
    """`purpose_index` / `rider_index` は `Node.blocks` の外にある。

    本文の木だけを走ると `semantic_type: purpose_index` が「使用 0」に見える
    （`docs/data_card.md` §4.1）。
    """
    from yakkan.models import Source

    found = {"purpose_index": 0, "rider_index": 0}
    for entry in _manifest_entries():
        path = DATASET / entry["doc_id"] / "source.json"
        source = Source.model_validate_json(path.read_text(encoding="utf-8"))
        front = source.front_matter
        if front.purpose_index is None and front.rider_index is None:
            continue
        kinds = {b.semantic_type for b in all_blocks(source) if getattr(b, "type", "") == "table"}
        for name in found:
            if getattr(front, name) is not None:
                assert name in kinds, f"{entry['doc_id']}: front_matter の {name} が数えられていない"
                found[name] += 1
        if all(found.values()):
            return
    assert any(found.values()), "front_matter に表を持つ文書が 1 本も無い"


# --- failed 文書への耐性 ------------------------------------------------------


@needs_dataset
def test_failedの文書があっても落ちない(tmp_path: Path) -> None:
    """不合格の文書は `answer.json` / `qa.json` / `*.jsonl` を持たない。

    理由（`manifest.errors`）はカードにそのまま載せる——隠さない（`docs/data_card.md` §2-5）。
    """
    failed = [d for d in _manifest_entries() if d["status"] != "ready"]
    if not failed:
        pytest.skip("failed な文書が無い")
    doc_id = failed[0]["doc_id"]
    base = _mini(tmp_path, [doc_id, *_ready_ids(1)])
    stats = collect(base)
    assert stats.scale.failed == 1
    card = render_card(stats)
    assert "不合格の 1 文書" in card
    assert doc_id in card


@needs_dataset
def test_成果物でないファイルを申告する(tmp_path: Path) -> None:
    base = _mini(tmp_path, _ready_ids(1))
    doc_dir = next(p for p in base.iterdir() if p.is_dir())
    (doc_dir / "render.pdf").write_bytes(b"%PDF-1.7\n")
    stats = collect(base)
    assert [(r.name, r.items) for r in stats.scale.strays] == [("render.pdf", 1)]
    assert "`render.pdf`" in render_card(stats)


# --- 現行コーパス -------------------------------------------------------------


@needs_dataset
def test_現行のカードが鮮度検査を通る() -> None:
    """`make check` に入っている検査そのもの。古ければ `datacard update` を忘れている。"""
    assert check(DATASET) == []


@needs_dataset
def test_カードが固定値を持ち込んでいない() -> None:
    """カードの本文に「過去の実測値」が残っていないことの抜き取り検査。

    仕様（`docs/data_card.md` §2-1）は「数値はすべて実ファイルから測る」。
    `yakkan/datacard.py` のソースに 3 桁以上のカンマ区切り数値が書かれていたら、
    それは焼き込みである。
    """
    import re

    #: 統計値ではなく、`apply` 型 QA の説明に出す例示（「日額 5,000 円で…」）。
    #: ここに足すときは「測った値ではない」ことを確かめる
    allowed = {"5,000"}
    source = Path("yakkan/datacard.py").read_text(encoding="utf-8")
    baked = [n for n in re.findall(r"\d{1,3}(?:,\d{3})+", source) if n not in allowed]
    assert baked == [], f"固定の統計値が書かれている: {baked}"


@needs_dataset
def test_観点名の正本と実装がずれていない() -> None:
    """`SKELETON_FEATURES` / `FORMAT_FEATURES` が `_features()` の実装と一致すること。

    片方にしか無い観点は、**使用 0 のときに「未使用」の表に出ず黙って消える**
    （`docs/data_card.md` §2-4）。カードが観点を隠さないことを型ではなく実測で守る。
    """
    from yakkan.datacard import FORMAT_FEATURES, SKELETON_FEATURES, _features
    from yakkan.models import Source

    declared = {("骨格", n) for n in SKELETON_FEATURES} | {("体裁", n) for n in FORMAT_FEATURES}
    seen: set[tuple[str, str]] = set()
    for entry in _manifest_entries():
        path = DATASET / entry["doc_id"] / "source.json"
        seen |= _features(Source.model_validate_json(path.read_text(encoding="utf-8")))
    static = {k for k in seen if k[0] in ("骨格", "体裁")}
    # 枠・箇条書きの style・発行体は種別ごとに動的に足すので、正本の一覧には入れない
    dynamic = {k for k in static if k[1].startswith(("枠（", "箇条書きの style（", "発行体が"))}
    unknown = static - dynamic - declared
    assert unknown == set(), f"実装にあるが正本の一覧に無い観点: {sorted(unknown)}"


@needs_dataset
def test_使用0の観点が未使用の表に出る(tmp_path: Path) -> None:
    """実測で 0 の観点（縦書きセル・qa_heading など）を黙って消さない。"""
    stats = collect(DATASET)
    unused = {c.name for c in stats.unused}
    for name in ("縦書きセル", "Q 見出し（qa_heading）", "強制改ページ（page_break）"):
        assert name in unused, f"{name} は使用 0 なので「未使用」に出るはず"
    assert name in render_card(stats)
