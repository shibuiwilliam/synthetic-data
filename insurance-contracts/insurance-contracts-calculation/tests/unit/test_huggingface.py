"""Hugging Face 用のリポジトリ組み立てのテスト（`export/huggingface.py`）。

本体（`yakkan`）も PDF も要らないように、**最小のデータセットをその場で組む**
（`test_datacard.make_dataset` を使い回す）。確かめるのは次の 5 点である。

1. データセットカードの frontmatter が**妥当な YAML** で、HF が要る欄が入っている。
2. **配らないもの**（`render.html`・重複した `source.json`）が入っていない。
   重複でなくなったら `check()` が止める。
3. ビューの行数が元データと合い、**型が揺れる欄は文字列**になっている。
4. 正解（`cases`）が HF の**既定の config にならない**。
5. 決定的である（同じ入力から同じ索引が出る）。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
import yaml
from test_datacard import make_dataset

from insurance_contracts_calculation.export import huggingface as hf

OPTS = hf.Options(version="vtest", generator_version="0.7.0")


def _dataset(root: Path, doc_ids: tuple[str, ...] = ("auto-0001-c1", "quake-0002-c1")) -> Path:
    """最小のデータセットに、描画結果（`render.html`・`source.json`・`layout.json`）を足す。"""
    make_dataset(root, doc_ids)
    (root / "data-card.md").write_text("# 検査用カード\n", encoding="utf-8")
    (root / "_run_report.json").write_text('{"not_generated": []}', encoding="utf-8")
    for doc_id in doc_ids:
        policy = (root / doc_id / "policy.json").read_bytes()
        render = root / doc_id / f"{doc_id}--st-a4-1col"
        (render / "pages").mkdir(parents=True, exist_ok=True)
        # `source.json` は `policy.json` のバイト単位の複製（実データと同じ関係）
        (render / "source.json").write_bytes(policy)
        (render / "render.html").write_text("<html>中間物</html>", encoding="utf-8")
        (render / "doc.pdf").write_bytes(b"%PDF-1.7 fake")
        (render / "pages" / "page-001.png").write_bytes(b"\x89PNG fake")
        (render / "layout.json").write_text(
            json.dumps(
                {
                    "doc_id": f"{doc_id}--st-a4-1col",
                    "content_id": doc_id,
                    "style_id": "st-a4-1col",
                    "page_count": 1,
                    "dpi_png": 150,
                    "page_size_pt": [595.0, 842.0],
                    "pages": [{"number": 1, "columns": 1}],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        # 出題は実データと同じ形にする（`make_dataset` のものは `rule_id` も `title` も持たない）
        for name, hint in (("tasks.jsonl", "H0"), ("tasks_H1.jsonl", "H1"), ("tasks_H2.jsonl", "H2")):
            (root / doc_id / "calc" / name).write_text(
                json.dumps(
                    {
                        "task_id": f"{doc_id}:t_payout",
                        "content_id": doc_id,
                        "rule_id": "t.payout",
                        "function": "t_payout",
                        "title": "検査用の保険金の額",
                        "kind": "calculation",
                        "hint": hint,
                        "inputs": [{"name": "amount", "type": "int", "unit": "JPY", "desc": "損害の額"}],
                        "output": {"type": "int", "unit": "JPY", "nullable": True},
                        "conventions": {"money": "金額は整数（円）"},
                    },
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        # 描画結果を作ったので manifest の `renders` も合わせる（`make_dataset` は空で作る）
        man_path = root / doc_id / "calc" / "manifest.json"
        man = json.loads(man_path.read_text(encoding="utf-8"))
        man["renders"] = [{"style": "st-a4-1col", "pages": 1}]
        man["pages"]["rendered"] = 1
        man_path.write_text(json.dumps(man, ensure_ascii=False), encoding="utf-8")
    return root


def _frontmatter(out: Path) -> dict:
    text = (out / "README.md").read_text(encoding="utf-8")
    assert text.startswith("---\n"), "frontmatter が先頭に無い"
    return yaml.safe_load(text.split("---\n", 2)[1])


# --------------------------------------------------------------------------- カード


def test_frontmatter_is_valid_yaml_with_the_fields_hf_needs(tmp_path: Path) -> None:
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    fm = _frontmatter(out)
    # license が無いと HF は unknown と表示する
    assert fm["license"] == hf.DEFAULT_LICENSE
    assert fm["language"] == ["ja"]
    assert fm["annotations_creators"] == ["machine-generated"]
    # configs が無いと load_dataset() が入れ子の木を読もうとして失敗する
    assert [c["config_name"] for c in fm["configs"]] == list(hf.VIEW_ORDER)
    assert set(fm["task_categories"]) <= set(hf.TASK_CATEGORIES)


def test_pretty_name_with_a_colon_does_not_break_the_yaml(tmp_path: Path) -> None:
    """`pretty_name: a: b` は YAML として壊れる。値を引用していることの回帰テスト。"""
    out = tmp_path / "hf"
    opts = hf.Options(version="v", generator_version="0", pretty_name="名前: 副題（記号 #&*）")
    hf.build(_dataset(tmp_path / "ds"), out, opts)
    assert _frontmatter(out)["pretty_name"] == "名前: 副題（記号 #&*）"


def test_answers_are_not_the_default_config(tmp_path: Path) -> None:
    """HF は先頭の config を既定にする。正解（cases）を既定にしない。"""
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    configs = _frontmatter(out)["configs"]
    assert configs[0]["config_name"] == "documents"
    assert configs[0].get("default") is True
    assert configs[-1]["config_name"] == "cases"
    assert all(c.get("default") is not True for c in configs[1:])


def test_card_warns_about_answers_and_carries_the_canary(tmp_path: Path) -> None:
    out = tmp_path / "hf"
    index = hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    card = (out / "README.md").read_text(encoding="utf-8")
    assert "正解が入っています" in card
    assert "学習データに使わないでください" in card
    assert index["canary"] in card
    assert index["contains_answers"] is True


def test_license_is_recorded_and_unknown_ones_are_refused(tmp_path: Path) -> None:
    ds = _dataset(tmp_path / "ds")
    out = tmp_path / "hf"
    index = hf.build(ds, out, hf.Options(version="v", generator_version="0", license_id="cc0-1.0"))
    assert index["license"] == "cc0-1.0"
    assert "Creative Commons Zero" in (out / "LICENSE").read_text(encoding="utf-8")
    with pytest.raises(ValueError, match="知らないライセンス"):
        hf.build(ds, tmp_path / "x", hf.Options(version="v", generator_version="0", license_id="gpl"))


def test_undecided_license_says_so_in_the_license_file(tmp_path: Path) -> None:
    out = tmp_path / "hf"
    hf.build(
        _dataset(tmp_path / "ds"), out, hf.Options(version="v", generator_version="0", license_id="other")
    )
    assert "未決" in (out / "LICENSE").read_text(encoding="utf-8")


# --------------------------------------------------------------------------- 配らないもの


def test_debug_html_and_duplicated_source_json_are_excluded(tmp_path: Path) -> None:
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    assert list(out.rglob("render.html")) == [], "render.html は本体が配布対象外と定めている"
    assert list(out.rglob("source.json")) == [], "source.json は policy.json の重複"
    # 原本は残っている
    assert (out / "documents" / "auto-0001-c1" / "policy.json").is_file()
    assert (out / "documents" / "auto-0001-c1" / "auto-0001-c1--st-a4-1col" / "layout.json").is_file()


def test_check_refuses_when_source_json_is_not_a_duplicate(tmp_path: Path) -> None:
    """重複でなくなったら黙って落とさずに止まる。"""
    ds = _dataset(tmp_path / "ds")
    src = ds / "auto-0001-c1" / "auto-0001-c1--st-a4-1col" / "source.json"
    src.write_text('{"違う": "中身"}', encoding="utf-8")
    with pytest.raises(ValueError, match="source.json が policy.json と一致しない"):
        hf.build(ds, tmp_path / "hf", OPTS)


def test_no_png_drops_the_images_only(tmp_path: Path) -> None:
    out = tmp_path / "hf"
    index = hf.build(
        _dataset(tmp_path / "ds"), out, hf.Options(version="v", generator_version="0", include_png=False)
    )
    assert list(out.rglob("*.png")) == []
    assert list(out.rglob("doc.pdf")), "PDF は残す（PNG は PDF から作り直せる）"
    assert index["includes_page_images"] is False
    assert "ページ画像（PNG）は入っていません" in (out / "README.md").read_text(encoding="utf-8")


def test_font_licenses_are_bundled(tmp_path: Path) -> None:
    """PDF にフォントが埋め込まれているので、配るならライセンス本文が要る。"""
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    listing = (out / "licenses-fonts" / "README.md").read_text(encoding="utf-8")
    assert "SIL Open Font License 1.1" in listing
    assert "IPA フォントライセンス v1.0" in listing
    # 本体の assets/fonts/ が見つかる環境では本文も入る
    for filename, _font, _license in hf.FONT_LICENSES:
        if (out / "licenses-fonts" / filename).is_file():
            assert f"[`{filename}`]" in listing


def test_gitattributes_puts_binaries_in_lfs_but_not_json(tmp_path: Path) -> None:
    """JSON を LFS に入れると HF のデータセットビューアが中身を見せられなくなる。"""
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    ga = (out / ".gitattributes").read_text(encoding="utf-8")
    assert "*.pdf filter=lfs" in ga
    assert "*.png filter=lfs" in ga
    assert "json filter=lfs" not in ga
    assert "jsonl filter=lfs" not in ga


# --------------------------------------------------------------------------- ビュー


def test_view_rows_match_the_source_data(tmp_path: Path) -> None:
    ds = _dataset(tmp_path / "ds")
    out = tmp_path / "hf"
    index = hf.build(ds, out, OPTS)
    rows = {name: _read_jsonl(out / "views" / f"{name}.jsonl") for name in hf.VIEW_ORDER}

    assert index["views"] == {k: len(v) for k, v in rows.items()}
    assert len(rows["documents"]) == 2
    # ケースは全文書の cases.jsonl の合計
    want = sum(len(_read_jsonl(p)) for p in sorted(ds.glob("*/calc/cases.jsonl")))
    assert len(rows["cases"]) == want == index["totals"]["cases"]
    # 出題はヒント 3 水準ぶん
    assert {r["hint"] for r in rows["tasks"]} == {"H0", "H1", "H2"}
    # ページは描画 1 件 × 1 ページ × 2 文書
    assert len(rows["pages"]) == 2
    assert rows["pages"][0]["image"].endswith("pages/page-001.png")
    assert rows["pages"][0]["dpi"] == 150


def test_polymorphic_columns_are_json_strings(tmp_path: Path) -> None:
    """`expected` は真偽・整数・日付・None を取る。列にそのまま並べると型推論が壊れる。"""
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    for row in _read_jsonl(out / "views" / "cases.jsonl"):
        assert isinstance(row["inputs_json"], str)
        assert isinstance(row["expected_json"], str)
        json.loads(row["inputs_json"])  # 読み戻せる
    for row in _read_jsonl(out / "views" / "rules.jsonl"):
        assert isinstance(row["difficulty_json"], str)
        assert isinstance(row["units"], list), "list[str] は型が安定しているので素のまま"


def test_views_have_a_schema_datasets_can_infer(tmp_path: Path) -> None:
    """`load_dataset()` が型を決められる形であること。

    壊れ方は 3 つある。(1) 行ごとに列が違う、(2) 同じ列にスカラーの型が混ざる、
    (3) **全行が空のリスト**で要素の型が決まらない。(3) は `challenge` で実際に起きた
    （challenge モードを使わないと 100 行すべて `[]` になる）。
    """
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    for name in hf.VIEW_ORDER:
        rows = _read_jsonl(out / "views" / f"{name}.jsonl")
        assert rows, f"{name}.jsonl が空"
        assert len({tuple(r) for r in rows}) == 1, f"{name}.jsonl の列が行ごとに違う"
        for key in rows[0]:
            values = [r[key] for r in rows]
            scalars = {type(v).__name__ for v in values if v is not None and not isinstance(v, list)}
            assert len(scalars) <= 1, f"{name}.jsonl の列 {key} にスカラーの型が混在: {scalars}"
            lists = [v for v in values if isinstance(v, list)]
            inner = {type(x).__name__ for v in lists for x in v}
            assert len(inner) <= 1, f"{name}.jsonl の列 {key} の要素型が混在: {inner}"


def test_weak_columns_are_recorded_not_hidden(tmp_path: Path) -> None:
    """型が決まらない列（全行が空／null）は、潰さずに索引へ残す。

    壊れはしないが、後の版で値が入ると schema が変わる。データカード §13 の
    「使っていない観点」と同じで、**見えるようにしておく**のが方針である。
    """
    out = tmp_path / "hf"
    index = hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    notes = index["view_schema_notes"]
    # この最小データには explanatory_units を持つルールが無い
    assert any("explanatory_units" in n for n in notes.get("rules", []))
    assert all(isinstance(v, list) for v in notes.values())


def test_every_view_row_names_its_document(tmp_path: Path) -> None:
    """平らにしたので、どの文書の行かが分からないと使えない。"""
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    for name in hf.VIEW_ORDER:
        for row in _read_jsonl(out / "views" / f"{name}.jsonl"):
            assert row["doc_id"], f"{name}.jsonl に doc_id の無い行がある"


# --------------------------------------------------------------------------- 決定性ほか


def test_deterministic(tmp_path: Path) -> None:
    ds = _dataset(tmp_path / "ds")
    a = hf.build(ds, tmp_path / "a", OPTS)
    b = hf.build(ds, tmp_path / "b", OPTS)
    assert json.dumps(a, ensure_ascii=False, sort_keys=True) == json.dumps(
        b, ensure_ascii=False, sort_keys=True
    )
    assert a["files"] == b["files"]


def test_index_hashes_every_file_it_shipped(tmp_path: Path) -> None:
    out = tmp_path / "hf"
    index = hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    shipped = {str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()}
    # index.json 自身はハッシュを取った後に書き直すので外れる
    assert shipped - set(index["files"]) == {"index.json"}


def test_empty_dataset_is_an_error(tmp_path: Path) -> None:
    (tmp_path / "ds").mkdir()
    with pytest.raises(FileNotFoundError, match="文書が無い"):
        hf.build(tmp_path / "ds", tmp_path / "hf", OPTS)


def test_data_card_and_run_report_travel_with_the_package(tmp_path: Path) -> None:
    out = tmp_path / "hf"
    hf.build(_dataset(tmp_path / "ds"), out, OPTS)
    assert (out / "data-card.md").is_file(), "詳しいカードは配布物に付ける"
    assert (out / "_run_report.json").is_file(), "作れなかった組の記録も素性の一部"


@pytest.mark.parametrize("doc_id,expected", [("auto-0001-c1", 1), ("auto-0001-c2", 2), ("auto-0001", 1)])
def test_variant_of(doc_id: str, expected: int) -> None:
    assert hf._variant_of(doc_id) == expected


def _read_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
