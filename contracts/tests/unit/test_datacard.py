"""`keiyaku/datacard.py` — `dataset/data-card.md` の生成（仕様は `docs/data_card.md`）。

ここで縛るのは 4 つ：**固定文字列に数値を焼き込まない**・**文書を足したら追従する**・
**自分自身のサイズを数えない（鮮度検査が収束する）**・**母数の小さい観点を自分で挙げる**。
"""

from __future__ import annotations

import json
from pathlib import Path

from keiyaku.datacard import CARD_NAME, check, collect, embedded_fonts, render_card, write_card
from keiyaku.manifest import DocumentEntry, Manifest
from keiyaku.models import (
    Cell,
    CommentaryBlock,
    Derived,
    Figure,
    Flowchart,
    FlowEdge,
    FlowNode,
    FrontMatter,
    LabelInfo,
    Layout,
    Meta,
    Node,
    PartyDef,
    Renderer,
    Source,
    Table,
)
from keiyaku.search_set import MAX_RELATED

A4 = (595.2755905511812, 841.8897637795277)


def _source(
    content_id: str,
    *,
    doctype: str,
    parties: int,
    commentary: bool,
    semantic: str,
    article_label: str = "第１条",
) -> Source:
    party_defs = [
        PartyDef(key=f"party{i}", alias=alias, name=f"架空{alias}社")
        for i, alias in enumerate(["甲", "乙", "丙"][:parties])
    ]
    blocks: list = [
        Table(
            id="tbl1",
            caption="定義",
            semantic_type=semantic,
            grid=[
                [
                    Cell(id="tbl1__r0c0", text="語", role="header"),
                    Cell(id="tbl1__r0c1", text="意味", role="header"),
                ],
                [Cell(id="tbl1__r1c0", text="本件", role="stub"), Cell(id="tbl1__r1c1", text="この契約")],
            ],
        ),
        Figure(
            id="fig1",
            caption="手順",
            alt="図の説明",
            facts=["甲が申し出る"],
            diagram=Flowchart(
                nodes=[
                    FlowNode(id="n1", label="申出", shape="start", col=0, row=0),
                    FlowNode(id="n2", label="承諾", shape="end", col=0, row=1),
                ],
                edges=[FlowEdge(**{"from": "n1", "to": "n2"})],
            ),
        ),
    ]
    if commentary:
        blocks.append(CommentaryBlock(id="cm1", anchor="a1", text=["この条の趣旨は…"]))
    return Source(
        content_id=content_id,
        doctype=doctype,
        seed=3,
        meta=Meta(
            title="秘密保持契約書",
            parties=party_defs,
            numbering_scheme="contract-standard",
            digit_style="fullwidth",
            disclaimer="本書は架空の契約書であり、法的効力を有しません。",
            constants={"term_years": "２年"},
        ),
        front_matter=FrontMatter(),
        body=[
            Node(id="pre", kind="preamble", text="甲と乙とは、次のとおり契約する。"),
            Node(id="a1", kind="article", title="目的", blocks=blocks),
        ],
        derived=Derived(
            labels={
                "a1": LabelInfo(
                    label=article_label,
                    title="目的",
                    heading_text=f"{article_label}（目的）",
                    path=[],
                    kind="article",
                    depth=0,
                )
            }
        ),
    )


def _write_doc(
    dataset_dir: Path,
    content_id: str,
    style_id: str,
    *,
    doctype: str = "nda",
    pages: int = 3,
    parties: int = 2,
    commentary: bool = False,
    semantic: str = "definitions",
    qa_items: int = 2,
    article_label: str = "第１条",
) -> DocumentEntry:
    doc_id = f"{content_id}--{style_id}"
    doc_dir = dataset_dir / doc_id
    doc_dir.mkdir(parents=True, exist_ok=True)
    source = _source(
        content_id,
        doctype=doctype,
        parties=parties,
        commentary=commentary,
        semantic=semantic,
        article_label=article_label,
    )
    (doc_dir / "source.json").write_text(source.model_dump_json(indent=2), encoding="utf-8")
    layout = Layout(
        doc_id=doc_id,
        content_id=content_id,
        style_id=style_id,
        renderer=Renderer(version="70.0", fonts=["IPAexMincho"]),
        page_size_pt=A4,
        page_count=pages,
    )
    (doc_dir / "layout.json").write_text(layout.model_dump_json(indent=2), encoding="utf-8")
    (doc_dir / "answer.json").write_text(
        json.dumps({"doc_id": doc_id, "pages": [{"number": 1, "chars": 100}], "outline": []}),
        encoding="utf-8",
    )
    (doc_dir / "qa.json").write_text(
        json.dumps(
            {
                "doc_id": doc_id,
                "items": [
                    {"type": "extract", "source": "auto", "answer_type": "string"} for _ in range(qa_items)
                ],
            }
        ),
        encoding="utf-8",
    )
    (doc_dir / "elements.jsonl").write_text('{"element_id": "a1"}\n', encoding="utf-8")
    (doc_dir / "passages.jsonl").write_text('{"passage_id": "p1"}\n', encoding="utf-8")
    return DocumentEntry(
        doc_id=doc_id,
        content_id=content_id,
        doctype=doctype,
        style_id=style_id,
        seed=3,
        pages=pages,
        status="ready",
        chars=1000,
        tables=1,
        figures=1,
        refs=5,
        qa_items=qa_items,
    )


def _write_manifest(dataset_dir: Path, entries: list[DocumentEntry]) -> None:
    manifest = Manifest(documents=entries)
    (dataset_dir / "manifest.json").write_text(manifest.model_dump_json(indent=2), encoding="utf-8")


def _dataset(tmp_path: Path) -> Path:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    entries = [
        _write_doc(dataset_dir, "nda-0001", "ct-a4-1col-mincho", pages=3),
        _write_doc(dataset_dir, "nda-0001", "ct-a4-1col-form", pages=5),
        _write_doc(
            dataset_dir,
            "lic-0001",
            "ct-a4-1col-mincho",
            doctype="license",
            pages=7,
            parties=3,
            commentary=True,
            semantic="rate",
        ),
    ]
    _write_manifest(dataset_dir, entries)
    return dataset_dir


def test_collectは実ファイルから実測値を集める(tmp_path: Path) -> None:
    stats = collect(_dataset(tmp_path))
    scale = stats.scale
    assert (scale.documents, scale.ready, scale.failed) == (3, 3, 0)
    assert scale.contents == 2
    assert scale.doctypes == 2
    assert scale.styles == 2
    assert scale.pages == 3 + 5 + 7
    assert scale.qa_items == 6
    assert scale.elements == 3
    assert scale.passages == 3
    assert scale.answer_chars == 300
    assert scale.table_cells == 3 * 4
    assert scale.constants == 3
    # 表の意味種別・図の種別・当事者の呼称は source.json の本文から数える
    assert {r.name: r.items for r in stats.semantic_types} == {"definitions": 2, "rate": 1}
    assert {r.name: r.items for r in stats.figure_kinds} == {"flowchart": 3}
    assert {r.name: r.items for r in stats.party_aliases} == {"甲": 3, "乙": 3, "丙": 1}
    assert {r.name: r.items for r in stats.parties_per_doc} == {"2 者": 2, "3 者": 1}
    assert {r.name: r.items for r in stats.node_kinds} == {"preamble": 3, "article": 3}
    assert [r.name for r in stats.layout.renderers] == ["weasyprint 70.0"]


def test_埋め込みフォントは登録した候補ではなく実測を出す(tmp_path: Path) -> None:
    """`layout.renderer.fonts` は描画に登録した候補で、PDF に入ったものとは違う。

    実データでは明朝 style の PDF に入るのは Noto Serif JP だけで、同梱してある IPAex は
    候補に挙がっているだけで埋め込まれない。候補を「使ったフォント」として載せない。
    """
    dataset_dir = _dataset(tmp_path)
    stats = collect(dataset_dir)
    # このフィクスチャには doc.pdf が無いので実測は空になる（候補で埋めない）
    assert stats.layout.embedded_fonts == []
    assert all(row.fonts == [] for row in stats.styles)
    assert [r.name for r in stats.layout.fonts] == ["IPAexMincho"]
    text = render_card(stats)
    assert "（PDF なし）" in text
    assert "描画に登録したフォント" in text
    assert embedded_fonts(dataset_dir / "no-such" / "doc.pdf") == []


def test_条文型と様式型は条ラベルの形で分ける(tmp_path: Path) -> None:
    """**ノード種別では分かれない。** 様式型（労働条件通知書）も `kind: "article"` のノードを
    使い、番号方式が「（１）」と振るだけである。`kind` の有無で判定すると「全 content が
    条文型」という誤った表が出る（2026-10-04 に実際に出した）。
    """
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    _write_manifest(
        dataset_dir,
        [
            _write_doc(dataset_dir, "nda-0001", "ct-a4-1col-mincho"),
            _write_doc(
                dataset_dir,
                "emp-0001",
                "ct-a4-1col-form",
                doctype="employment",
                article_label="（１）",
            ),
        ],
    )
    shape = {c.name: c.contents for c in collect(dataset_dir).coverage if c.group == "骨格"}
    assert shape["条文型（条を「第◯条」で番号する）"] == 1
    assert shape["様式型（条番号を持たない記入欄中心）"] == 1


def test_doctypeとstyleの内訳が文書とcontentを分けて数える(tmp_path: Path) -> None:
    stats = collect(_dataset(tmp_path))
    nda = next(r for r in stats.doctypes if r.doctype == "nda")
    assert (nda.contents, nda.documents) == (1, 2)
    assert (nda.pages_min, nda.pages_max) == (3, 5)
    assert [r.style_id for r in stats.styles] == ["ct-a4-1col-form", "ct-a4-1col-mincho"]
    assert [r.doc_id for r in stats.documents] == sorted(r.doc_id for r in stats.documents)


def test_カードに数値を焼き込まず実測値を埋める(tmp_path: Path) -> None:
    """固定文字列に統計値を書くと、再生成しても更新されない（docs/decisions.md 105・131）。"""
    dataset_dir = _dataset(tmp_path)
    text = render_card(collect(dataset_dir))
    assert "**3 文書**" in text
    assert "計 **15 ページ**" in text
    assert "{" not in text.replace("`{ref:}`", "").replace("`{const:}`", "").replace(
        "`{party:}`", ""
    ).replace("`{party:<key>}`", ""), "テンプレートの置換漏れがある"
    # 文書の全件表は 1 行ずつ出す（抜粋にしない）
    for row in collect(dataset_dir).documents:
        assert f"`{row.doc_id}`" in text


def test_母数の小さい観点と未使用の宣言を自分で挙げる(tmp_path: Path) -> None:
    stats = collect(_dataset(tmp_path))
    thin = {(c.group, c.name) for c in stats.thin}
    assert ("体裁", "逐条解説") in thin, "1 content しか持たない観点が挙がっていない"
    assert ("体裁", "当事者 3 者以上") in thin
    unused = {(c.group, c.name) for c in stats.unused}
    assert ("図の種別", "matrix") in unused, "宣言はあるが使われていない種別が挙がっていない"
    assert ("表の意味種別", "head_matter") in unused
    assert all(c.contents > 0 for c in stats.thin)
    text = render_card(stats)
    assert "逐条解説" in text
    assert "matrix" in text


def test_カードは決定論で自分自身のサイズを数えない(tmp_path: Path) -> None:
    """自分のサイズを数えると、書き出すたびに数が動いて鮮度検査が収束しない。"""
    dataset_dir = _dataset(tmp_path)
    first = write_card(dataset_dir).read_text(encoding="utf-8")
    second = write_card(dataset_dir).read_text(encoding="utf-8")
    assert first == second
    assert check(dataset_dir) == [], "書き出した直後なのに古いと判定された"


def test_文書を足すと古いと分かり更新で追従する(tmp_path: Path) -> None:
    dataset_dir = _dataset(tmp_path)
    write_card(dataset_dir)
    entries = Manifest.model_validate_json(
        (dataset_dir / "manifest.json").read_text(encoding="utf-8")
    ).documents
    entries.append(_write_doc(dataset_dir, "ots-0001", "ct-a4-1col-mincho", doctype="outsourcing", pages=9))
    _write_manifest(dataset_dir, entries)

    problems = check(dataset_dir)
    assert problems, "文書を足したのに古いと判定されない"
    assert any("一致しない" in p for p in problems)

    write_card(dataset_dir)
    assert check(dataset_dir) == []
    text = (dataset_dir / CARD_NAME).read_text(encoding="utf-8")
    assert "**4 文書**" in text
    assert "計 **24 ページ**" in text
    assert "`ots-0001--ct-a4-1col-mincho`" in text


def test_checkはカードやmanifestが無いことを報告する(tmp_path: Path) -> None:
    dataset_dir = tmp_path / "dataset"
    dataset_dir.mkdir()
    assert any("manifest.json が無い" in p for p in check(dataset_dir))
    _write_manifest(dataset_dir, [_write_doc(dataset_dir, "nda-0001", "ct-a4-1col-mincho")])
    assert any(CARD_NAME in p for p in check(dataset_dir))


def test_検索コーパスに入っていないcontentを警告する(tmp_path: Path) -> None:
    """文書を足したあと `keiyaku export` を回していない状態を黙って通さない。"""
    dataset_dir = _dataset(tmp_path)
    search = dataset_dir / "search"
    search.mkdir()
    (search / "passages.jsonl").write_text(
        json.dumps({"doc_id": "nda-0001--ct-a4-1col-mincho", "content_id": "nda-0001", "kind": "article"})
        + "\n",
        encoding="utf-8",
    )
    (search / "queries.jsonl").write_text(
        json.dumps({"query_id": "q1", "kind": "term", "query": "本件", "related_truncated": True}) + "\n",
        encoding="utf-8",
    )
    (search / "qrels.jsonl").write_text(
        json.dumps({"query_id": "q1", "passage_id": "p1", "grade": 2}) + "\n", encoding="utf-8"
    )
    stats = collect(dataset_dir)
    assert stats.search.missing_contents == ["lic-0001"]
    assert stats.search.truncated == 1
    # 打ち切りの上限も実装の定数から取る（カードに 20 と書き込まない）
    assert stats.search.related_cap == MAX_RELATED
    text = render_card(stats)
    assert "警告" in text
    assert "`lic-0001`" in text
    assert "「本件」" in text


def test_検索評価セットが無いときは未生成と書く(tmp_path: Path) -> None:
    text = render_card(collect(_dataset(tmp_path)))
    assert "**未生成。**" in text
