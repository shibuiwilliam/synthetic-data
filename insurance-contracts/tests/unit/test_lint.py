"""lint ルール（CLAUDE.md §8）。壊した入力で検出されることを確かめる。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from yakkan.lint.runner import lint_content, summarize

SAMPLE = Path(__file__).resolve().parents[1] / "golden" / "sample_min"


#: 文書全体を対象にする規則。sample_min は 3 ページの抜粋なので、これらは対象外にする
#: （L16 は 15 問の執筆 QA を求めるので、抜粋には課さない）
DOCUMENT_RULES = ["L04", "L09", "L15", "L16"]


def codes(findings, severity="error") -> set[str]:
    return {f.code for f in findings if f.severity == severity}


@pytest.fixture
def content(tmp_path: Path) -> Path:
    target = tmp_path / "sample"
    shutil.copytree(SAMPLE, target)
    return target


def edit(path: Path, mutate) -> None:
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def first_paragraph(data: dict) -> dict:
    """sample_min の ch1 → 第1条 → 第1項。"""
    return data["items"][0]["children"][0]["children"][0]


def test_サンプルはerrorもwarnも出ない(content: Path) -> None:
    findings = lint_content(content, exclude=DOCUMENT_RULES)
    assert findings == [], "\n".join(f.format() for f in findings)


def test_quickはフォント被覆を飛ばす(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json", lambda d: first_paragraph(d).__setitem__("text", "絵文字🙂です。")
    )
    assert "L07" in codes(lint_content(content, quick=False, exclude=DOCUMENT_RULES))
    assert "L07" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L00_執筆物にderivedがあるとエラー(content: Path) -> None:
    edit(content / "doc.json", lambda d: d.__setitem__("derived", {"labels": {}}))
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert codes(findings) == {"L00"}
    assert "derived" in findings[0].message


def test_L01_id重複(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json", lambda d: d["items"][0]["children"][1].__setitem__("id", "ch1_a1")
    )
    assert "L01" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L01_参照先が無い(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{ref:nowhere}です。"),
    )
    assert "L01" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L01_anchorが無いmargin_note(content: Path) -> None:
    def drop_anchor(data: dict) -> None:
        article = data["items"][0]["children"][0]["children"][1]
        article["blocks"][1].pop("anchor")

    edit(content / "parts" / "30_ch4.json", drop_anchor)
    assert "L01" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L02_脚注の双方向対応(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "事変{fn:9}です。"),
    )
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L02" in codes(findings)


def test_L02_未使用の脚注(content: Path) -> None:
    def add_unused(data: dict) -> None:
        article = data["items"][0]["children"][1]
        article["blocks"][0]["notes"].append({"n": 2, "text": "使われない脚注です。"})

    edit(content / "parts" / "20_ch1.json", add_unused)
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert any("参照されていない" in f.message for f in findings if f.code == "L02")


@pytest.mark.parametrize(
    "text",
    [
        "第１条に定めるとおりです。",
        "第2章のとおりです。",
        "（１）当会社は支払います。",
        "①当会社は支払います。",
        "ｱ.当会社は支払います。",
    ],
)
def test_L03_番号ラベルの直書き(content: Path, text: str) -> None:
    edit(content / "parts" / "20_ch1.json", lambda d: first_paragraph(d).__setitem__("text", text))
    assert "L03" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L03_未知トークン(content: Path) -> None:
    edit(content / "parts" / "20_ch1.json", lambda d: first_paragraph(d).__setitem__("text", "{foo:1}です。"))
    assert "L03" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L03_auto_labelは列挙表のセルだけ(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{auto_label}です。"),
    )
    assert "L03" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L03_number_overrideには理由が要る(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("number_override", "第１の２"),
    )
    assert "L03" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L07_フォントに無い文字(content: Path) -> None:
    edit(content / "parts" / "20_ch1.json", lambda d: first_paragraph(d).__setitem__("text", "記号🙂です。"))
    findings = lint_content(content)
    assert "L07" in codes(findings)


@pytest.mark.parametrize(
    "text",
    [
        "東京海上日動火災保険株式会社",
        "ニッセイのご案内",
        "詳しくは https://www.aoba-minato.co.jp/ をご覧ください。",
        "お問い合わせは info@aoba-minato.jp まで",
        "電話 0120-123-456",
        "電話 ０１２０－１２３－４５６",
    ],
)
def test_L08_架空性(content: Path, text: str) -> None:
    edit(content / "parts" / "90_back.json", lambda d: d["items"][1].__setitem__("text", text))
    assert "L08" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


@pytest.mark.parametrize(
    "text",
    ["お問い合わせ 0120-000-000", "https://www.example.jp/", "sample@example.co.jp"],
)
def test_L08_許可されている書き方は通る(content: Path, text: str) -> None:
    edit(content / "parts" / "90_back.json", lambda d: d["items"][1].__setitem__("text", text))
    assert "L08" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L13_disclaimerが奥付に無い(content: Path) -> None:
    edit(content / "parts" / "90_back.json", lambda d: d["items"].pop())
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L13" in codes(findings)


def test_L13_日付形式(content: Path) -> None:
    edit(content / "doc.json", lambda d: d["meta"].__setitem__("edition_date", "2026/10/01"))
    assert "L13" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L13_未宣言のconst(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{const:unknown}です。"),
    )
    assert "L13" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L12_未定義の用語はwarn(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{term:unknown}です。"),
    )
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L12" in codes(findings, "warn")
    assert summarize(findings)[0] == 0


def test_onlyで絞り込める(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "第１条{ref:nowhere}"),
    )
    assert codes(lint_content(content, quick=True, only=["L01"])) == {"L01"}
    assert codes(lint_content(content, quick=True, only=["L03"])) == {"L03"}


# --- L06（図）-----------------------------------------------------------------

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "diagrams"


def with_figure(content: Path, fixture: str, mutate=None) -> None:
    """sample_min の第1条に、fixture の図を差し込む。"""
    figure = json.loads((FIXTURES / f"{fixture}.json").read_text(encoding="utf-8"))
    if mutate:
        mutate(figure)

    def put(data: dict) -> None:
        data["items"][0]["children"][0]["blocks"] = [figure]

    edit(content / "parts" / "20_ch1.json", put)


@pytest.mark.parametrize("fixture", ["flowchart", "tree", "steps", "timeline", "annotated_mock", "matrix"])
def test_L06_6種のfixtureは通る(content: Path, fixture: str) -> None:
    with_figure(content, fixture)
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L06" not in codes(findings), "\n".join(f.format() for f in findings)


def test_L06_altとfactsは必須(content: Path) -> None:
    with_figure(content, "flowchart", lambda f: f.update(alt="", facts=[]))
    findings = [f for f in lint_content(content, quick=True, exclude=DOCUMENT_RULES) if f.code == "L06"]
    assert len(findings) == 2


def test_L06_エッジの端点が存在しない(content: Path) -> None:
    with_figure(content, "flowchart", lambda f: f["diagram"]["edges"].append({"from": "n1", "to": "nowhere"}))
    assert "L06" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L06_格子座標の重複(content: Path) -> None:
    def dup(f: dict) -> None:
        f["diagram"]["nodes"][1]["col"] = f["diagram"]["nodes"][0]["col"]
        f["diagram"]["nodes"][1]["row"] = f["diagram"]["nodes"][0]["row"]

    with_figure(content, "flowchart", dup)
    findings = [f for f in lint_content(content, quick=True, exclude=DOCUMENT_RULES) if f.code == "L06"]
    assert any("格子座標が重複" in f.message for f in findings)


def test_L06_flowchartの最小複雑度(content: Path) -> None:
    def shrink(f: dict) -> None:
        f["diagram"]["nodes"] = f["diagram"]["nodes"][:3]
        f["diagram"]["edges"] = [{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}]

    with_figure(content, "flowchart", shrink)
    findings = [f for f in lint_content(content, quick=True, exclude=DOCUMENT_RULES) if f.code == "L06"]
    assert any("ノードが 3 個" in f.message for f in findings)
    assert any("分岐が無い" in f.message for f in findings)


def test_L06_treeの階層不足(content: Path) -> None:
    with_figure(
        content, "tree", lambda f: f["diagram"]["root"].update(children=[{"id": "x", "label": "浅い"}])
    )
    findings = [f for f in lint_content(content, quick=True, exclude=DOCUMENT_RULES) if f.code == "L06"]
    assert any("階層が 2" in f.message for f in findings)


def test_L06_stepsとmatrixの最小複雑度(content: Path) -> None:
    with_figure(content, "steps", lambda f: f["diagram"].update(steps=f["diagram"]["steps"][:2]))
    assert "L06" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))
    with_figure(
        content,
        "matrix",
        lambda f: f["diagram"].update(cols=["基本", "標準"], marks=[r[:2] for r in f["diagram"]["marks"]]),
    )
    assert "L06" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L06_timelineの要素不足(content: Path) -> None:
    def shrink(f: dict) -> None:
        f["diagram"]["spans"] = f["diagram"]["spans"][:1]
        f["diagram"]["events"] = f["diagram"]["events"][:1]

    with_figure(content, "timeline", shrink)
    assert "L06" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L06_バッジと凡例の対応(content: Path) -> None:
    with_figure(content, "annotated_mock", lambda f: f["diagram"].update(legend=f["diagram"]["legend"][:3]))
    findings = [f for f in lint_content(content, quick=True, exclude=DOCUMENT_RULES) if f.code == "L06"]
    assert any("凡例が無い" in f.message for f in findings)


def test_L06_matrixの行列数の不一致(content: Path) -> None:
    with_figure(content, "matrix", lambda f: f["diagram"]["marks"].__setitem__(0, ["○", "○"]))
    findings = [f for f in lint_content(content, quick=True, exclude=DOCUMENT_RULES) if f.code == "L06"]
    assert any("列数が cols と合わない" in f.message for f in findings)


# --- L05：2 段ヘッダ（colspan）— §3.1 の C10 ---------------------------------


def _two_row_header_table() -> dict:
    """上段が結合セルの大区分、下段がその内訳という 2 行構成の表頭。

    結合された位置には `merged_into` のプレースホルダを置く（rowspan と同じ規約）。
    """
    tid = "tbl_two_row_header"
    return {
        "type": "table",
        "id": tid,
        "semantic_type": "rate",
        "caption": "保険料の区分",
        "layout": {"header_rows": 2, "header_cols": 1, "repeat_header": True, "style": "grid"},
        "grid": [
            [
                {"id": f"{tid}__r0c0", "text": "区分", "role": "header", "rowspan": 2},
                {"id": f"{tid}__r0c1", "text": "年間の保険料", "role": "header", "colspan": 2},
                {"merged_into": f"{tid}__r0c1"},
            ],
            [
                {"merged_into": f"{tid}__r0c0"},
                {"id": f"{tid}__r1c1", "text": "本人", "role": "header"},
                {"id": f"{tid}__r1c2", "text": "家族", "role": "header"},
            ],
            [
                {"id": f"{tid}__r2c0", "text": "区分あ", "role": "stub"},
                {"id": f"{tid}__r2c1", "text": "１２，０００円"},
                {"id": f"{tid}__r2c2", "text": "１８，０００円"},
            ],
        ],
        "records": [{"区分": "区分あ", "本人": "１２，０００円", "家族": "１８，０００円"}],
    }


def _put_table(content: Path, table: dict) -> None:
    def mutate(data):
        para = first_paragraph(data)
        para.setdefault("blocks", []).append(table)

    edit(content / "parts" / "20_ch1.json", mutate)


def test_L05_2段ヘッダのcolspanを通す(content: Path) -> None:
    """`colspan` を足して幅を数えていたため、2 段ヘッダが必ず error になっていた。"""
    _put_table(content, _two_row_header_table())
    findings = lint_content(content, exclude=DOCUMENT_RULES)
    assert [f.format() for f in findings if f.severity == "error"] == []


def test_L05_colspanのプレースホルダが欠けているとエラー(content: Path) -> None:
    table = _two_row_header_table()
    tid = table["id"]
    table["grid"][0][2] = {"id": f"{tid}__r0c2", "text": "余計", "role": "header"}
    _put_table(content, table)
    findings = lint_content(content, exclude=DOCUMENT_RULES)
    assert "L05" in codes(findings)


def test_L05_rowspanのプレースホルダが欠けているとエラー(content: Path) -> None:
    table = _two_row_header_table()
    tid = table["id"]
    table["grid"][1][0] = {"id": f"{tid}__r1c0", "text": "余計", "role": "header"}
    _put_table(content, table)
    findings = lint_content(content, exclude=DOCUMENT_RULES)
    assert "L05" in codes(findings)


def test_header_pathが2段ヘッダを両方の見出しで拾う(content: Path) -> None:
    """上段の大区分と下段の内訳が both col_headers に入る（table_lookup の正解になる）。"""
    from yakkan.build import build
    from yakkan.compose import load_draft

    _put_table(content, _two_row_header_table())
    source = build(load_draft(content))
    path = source.derived.tables["tbl_two_row_header"].header_path["tbl_two_row_header__r2c1"]
    assert path.row_headers == ["区分あ"]
    assert path.col_headers == ["年間の保険料", "本人"]


def test_header_pathはrowspanの見出しを全行で指す(content: Path) -> None:
    """rowspan の見出しがページ／段の境界で継続側に描かれなくても、
    意味の正解（`header_path`）はその見出しを指し続ける。

    実測（28 データセット）：見出しが別ページにある本文セルが 35 件あり、
    すべて `row_headers` で見出しを指せていた。読み手には空欄に見えるが、
    正解は失われていない（`docs/shared_fixes.md` A5）。
    """
    from yakkan.build import build
    from yakkan.compose import load_draft

    tid = "tbl_rowspan_stub"
    table = {
        "type": "table",
        "id": tid,
        "semantic_type": "generic",
        "caption": "区分ごとの取扱い",
        "layout": {"header_rows": 1, "header_cols": 1, "repeat_header": True, "style": "grid"},
        "grid": [
            [
                {"id": f"{tid}__r0c0", "text": "区分", "role": "header"},
                {"id": f"{tid}__r0c1", "text": "取扱い", "role": "header"},
            ],
            [
                {"id": f"{tid}__r1c0", "text": "第一分類", "role": "stub", "rowspan": 3},
                {"id": f"{tid}__r1c1", "text": "一つ目の取扱いです。"},
            ],
            [
                {"merged_into": f"{tid}__r1c0"},
                {"id": f"{tid}__r2c1", "text": "二つ目の取扱いです。"},
            ],
            [
                {"merged_into": f"{tid}__r1c0"},
                {"id": f"{tid}__r3c1", "text": "三つ目の取扱いです。"},
            ],
        ],
    }

    def mutate(data):
        para = first_paragraph(data)
        para.setdefault("blocks", []).append(table)

    edit(content / "parts" / "20_ch1.json", mutate)
    source = build(load_draft(content))
    paths = source.derived.tables[tid].header_path
    for row in (1, 2, 3):
        assert paths[f"{tid}__r{row}c1"].row_headers == ["第一分類"], f"{row} 行目が見出しを失っている"


def test_L01_キャプションのある表と図は参照できる(content: Path) -> None:
    """docs/shared_fixes.md A3。build が「表N」「図N」を振るので参照先にできる。"""
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__(
            "text", "{ref:tbl_duties}および{ref:fig_accident_flow}のとおりとします。"
        ),
    )
    assert "L01" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L01_キャプションの無い表は参照できない(content: Path) -> None:
    """列挙表には番号が振られないので、参照先にすると解決できない。"""
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{ref:tbl_exclusions}のとおりとします。"),
    )
    assert "L01" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L06_図の中の値トークンは使える(content: Path) -> None:
    """docs/shared_fixes.md A2。{ref:} {term:} {const:} は build が解決する。"""

    def put(data: dict) -> None:
        _find_figure(data)["diagram"]["nodes"][0]["label"] = "事故の発生（{const:notify_days}日以内）"

    edit(content / "parts" / "30_ch4.json", put)
    assert "L06" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L06_図の中のマークアップはエラー(content: Path) -> None:
    """SVG は行内マークアップを持てない。"""

    def put(data: dict) -> None:
        _find_figure(data)["diagram"]["nodes"][0]["label"] = "事故の{b:発生}{br}のとき"

    edit(content / "parts" / "30_ch4.json", put)
    assert "L06" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def _find_figure(data: dict) -> dict:
    """part の中の最初の flowchart 図を探す。"""
    found: list[dict] = []

    def walk(obj: object) -> None:
        if isinstance(obj, dict):
            if obj.get("type") == "figure" and obj.get("diagram", {}).get("kind") == "flowchart":
                found.append(obj)
            for value in obj.values():
                walk(value)
        elif isinstance(obj, list):
            for value in obj:
                walk(value)

    walk(data)
    assert found, "part に flowchart の図が無い"
    return found[0]


def test_L01_番号を持たない参照先を弾く() -> None:
    """`resolve_ref` が空文字を返す参照を L01 が error にする。"""
    from yakkan.models import Node
    from yakkan.numbering import DocumentIndex, NumberingContext, resolve_ref

    ctx = NumberingContext(scheme="group", digit_style="halfwidth")
    body = [
        Node(
            id="ch1",
            kind="chapter",
            title="章",
            children=[
                Node(
                    id="ch1_a1",
                    kind="article",
                    title="条",
                    children=[Node(id="ch1_a1_p1", kind="paragraph"), Node(id="ch1_a1_p2", kind="paragraph")],
                )
            ],
        )
    ]
    index = DocumentIndex(ctx, body)
    assert resolve_ref(index, "ch1_a1_p2", "ch1_a1_p1").strip(), "空文字を返してはいけない"


# --- L16 執筆 QA の配り方（docs/remaining_issues.md S1） ----------------------


def _authored(items: list[dict]) -> dict:
    return {"items": items}


def _qa_item(qa_type: str) -> dict:
    return {"type": qa_type, "question": "問い", "answer": "答え", "evidence": ["ch1_a1_p1"]}


def _run_l16(tmp_path: Path, items: list[dict]) -> list[str]:
    import json

    from yakkan.lint.base import LintContext
    from yakkan.lint.qa_authored import l16_authored_qa

    (tmp_path / "qa_authored.json").write_text(
        json.dumps(_authored(items), ensure_ascii=False), encoding="utf-8"
    )
    ctx = LintContext(draft=None, content_dir=tmp_path)  # type: ignore[arg-type]
    return [f.message for f in l16_authored_qa(ctx)]


def _balanced() -> list[dict]:
    types = (
        ["table_lookup"] * 2
        + ["table_reason"]
        + ["figure_fact"] * 2
        + ["figure_path"]
        + ["apply"]
        + ["extract"] * 8
    )
    return [_qa_item(t) for t in types]


def test_L16は配りが足りていれば通る(tmp_path: Path) -> None:
    assert _run_l16(tmp_path, _balanced()) == []


def test_L16はapplyが無いと落ちる(tmp_path: Path) -> None:
    items = _balanced()
    items[6] = _qa_item("extract")
    messages = _run_l16(tmp_path, items)
    assert any("apply" in m for m in messages)


def test_L16は件数と観点の不足を数える(tmp_path: Path) -> None:
    items = [_qa_item("extract")] * 14
    messages = _run_l16(tmp_path, items)
    assert any("14 問" in m for m in messages)
    assert any(m.startswith("表に関する問いが") for m in messages)
    assert any(m.startswith("図に関する問いが") for m in messages)


def test_L16はevidenceの空を見つける(tmp_path: Path) -> None:
    items = _balanced()
    items[0] = {"type": "table_lookup", "question": "問い", "answer": "答え", "evidence": []}
    assert any("evidence が無い" in m for m in _run_l16(tmp_path, items))
