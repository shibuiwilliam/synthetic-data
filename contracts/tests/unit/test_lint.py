"""lint ルール（CLAUDE.md §8）。壊した入力で検出されることを確かめる。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from keiyaku.lint.runner import lint_content, summarize

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


def node(data: dict, node_id: str) -> dict:
    """id でノードを引く。**位置で引かない**——サンプルに条を足すたびにテストが壊れるため。"""

    def walk(items):
        for it in items:
            if it.get("id") == node_id:
                return it
            found = walk(it.get("children", []))
            if found:
                return found
        return None

    found = walk(data["items"])
    assert found is not None, f"{node_id} がサンプルに無い"
    return found


def first_paragraph(data: dict) -> dict:
    """sample_min の ch1 → 第1条 → 第1項。"""
    return node(data, "ch1_a1_p1")


def test_サンプルはerrorもwarnも出ない(content: Path) -> None:
    findings = lint_content(content, exclude=DOCUMENT_RULES)
    assert findings == [], "\n".join(f.format() for f in findings)


def test_quickはフォント被覆を飛ばす(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "絵文字🙂とする。"),
    )
    assert "L07" in codes(lint_content(content, quick=False, exclude=DOCUMENT_RULES))
    assert "L07" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L00_執筆物にderivedがあるとエラー(content: Path) -> None:
    edit(content / "doc.json", lambda d: d.__setitem__("derived", {"labels": {}}))
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert codes(findings) == {"L00"}
    assert "derived" in findings[0].message


def test_L01_id重複(content: Path) -> None:
    edit(content / "parts" / "20_ch1.json", lambda d: node(d, "ch1_a2").__setitem__("id", "ch1_a1"))
    assert "L01" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L01_参照先が無い(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{ref:nowhere}です。"),
    )
    assert "L01" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L01_anchorが無いmargin_note(content: Path) -> None:
    def drop_anchor(data: dict) -> None:
        article = node(data, "ch4_s1_a2")
        article["blocks"][1].pop("anchor")

    edit(content / "parts" / "30_ch4.json", drop_anchor)
    assert "L01" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L02_脚注の双方向対応(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "秘密情報{fn:9}とする。"),
    )
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L02" in codes(findings)


def test_L02_未使用の脚注(content: Path) -> None:
    def add_unused(data: dict) -> None:
        article = node(data, "ch1_a2")
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
        # 実在企業（契約書の当事者名・取引先名に入りやすいもの）
        "株式会社サイボウズとの取引",
        "ＮＴＴデータに再委託する場合",
        # 参考ひな型の配布元（生成物に絶対出さない）
        "デイライト法律事務所の書式による",
        # 許可外のドメイン・メール・電話番号
        "詳しくは https://www.aoba-systems.co.jp/ を参照する。",
        "連絡先は info@aoba-systems.jp とする。",
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
    """契約日・効力発生日は任意だが、書いたら YYYY-MM-DD 形式であること。"""
    edit(content / "doc.json", lambda d: d["meta"].__setitem__("contract_date", "2026/04/01"))
    assert "L13" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L13_当事者の名称が空(content: Path) -> None:
    edit(content / "doc.json", lambda d: d["meta"]["parties"][1].__setitem__("name", " "))
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
        node(data, "ch1_a1")["blocks"] = [figure]

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
    from keiyaku.build import build
    from keiyaku.compose import load_draft

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
    from keiyaku.build import build
    from keiyaku.compose import load_draft

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
            "text", "{ref:tbl_duties}および{ref:fig_return_flow}のとおりとする。"
        ),
    )
    assert "L01" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L01_キャプションの無い表は参照できない(content: Path) -> None:
    """列挙表には番号が振られないので、参照先にすると解決できない。"""
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{ref:tbl_exclusions}のとおりとする。"),
    )
    assert "L01" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L06_図の中の値トークンは使える(content: Path) -> None:
    """docs/shared_fixes.md A2。{ref:} {term:} {const:} は build が解決する。"""

    def put(data: dict) -> None:
        _find_figure(data)["diagram"]["nodes"][0]["label"] = "本契約の終了（{const:notice_days}前の通知）"

    edit(content / "parts" / "30_ch4.json", put)
    assert "L06" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L06_図の中の当事者トークンは解決されて残らない(content: Path) -> None:
    """`{party:}` も値を差し込むだけなので図で使える（当事者の呼称は直書きできない。L19）。

    FLAT_TOKENS から外れていたため、**生の `{party:client}` がそのまま SVG に出た**。
    lint も verify も拾わなかったので、解決まで確かめる。
    """
    from keiyaku.build import build
    from keiyaku.compose import load_draft

    def put(data: dict) -> None:
        _find_figure(data)["diagram"]["nodes"][0]["label"] = "{party:discloser}の確認"

    edit(content / "parts" / "30_ch4.json", put)
    assert "L06" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))

    source = build(load_draft(content))
    labels = {k: v for fig in source.derived.figures.values() for k, v in fig.resolved_labels.items()}
    assert "{" not in labels["{party:discloser}の確認"]


def test_L06_図の中のマークアップはエラー(content: Path) -> None:
    """SVG は行内マークアップを持てない。"""

    def put(data: dict) -> None:
        _find_figure(data)["diagram"]["nodes"][0]["label"] = "本契約の{b:終了}{br}のとき"

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
    """`resolve_ref` が空文字を返す参照を L01 が error にする。

    `contract-standard` は第1項を無番号で組むので、印字どおりに連ねると空文字になる。
    宣言の `paragraph_ref_style: written` が「第1項」と書き下すことを確かめる
    （yakkan の group で 18 件の実害が出た規則。docs/schema.md §7）。
    """
    from keiyaku.models import Node
    from keiyaku.numbering import DocumentIndex, NumberingContext, resolve_ref

    ctx = NumberingContext(scheme="contract-standard", digit_style="halfwidth")
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

    from keiyaku.lint.base import LintContext
    from keiyaku.lint.qa_authored import l16_authored_qa

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
        + ["apply"] * 2
        + ["extract"] * 7
    )
    return [_qa_item(t) for t in types]


def test_L16は配りが足りていれば通る(tmp_path: Path) -> None:
    assert _run_l16(tmp_path, _balanced()) == []


def test_L16はapplyが足りないと落ちる(tmp_path: Path) -> None:
    items = _balanced()
    items[6] = _qa_item("extract")
    messages = _run_l16(tmp_path, items)
    assert any("apply" in m for m in messages)


def test_L16はblueprintの要求を使う(tmp_path: Path) -> None:
    """要求は doctype ごとに違う（契約書は図 2・apply 2）。実装の定数ではなく宣言を見る。

    実害：`lease` の 2 本目で、blueprint が図 2 と宣言しているのに実装の定数 3 で落ちた。
    """
    from keiyaku.blueprints import available_doctypes, load_blueprint
    from keiyaku.lint.qa_authored import _wanted

    if not available_doctypes():
        pytest.skip("blueprints/ がまだ無い")

    class _Draft:
        doctype = "lease"

    class _Ctx:
        draft = _Draft()

    spec = load_blueprint("lease").authored_qa
    assert _wanted(_Ctx()) == (spec.count, spec.table_min, spec.figure_min, spec.apply_min)
    assert spec.figure_min == 2, "契約書は図が 1〜2 点なので図の要求は 2（docs/decisions.md 12）"


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


# --- L17 表の header_cols（docs/remaining_issues.md X3） ----------------------


def test_L17はstubの列を覆わないheader_colsを見つける() -> None:
    """`role: stub` は行見出しの宣言。header_cols が 0 だと意味座標が崩れる。"""
    from keiyaku.lint.base import LintContext
    from keiyaku.lint.table_headers import l17_header_cols
    from keiyaku.models import SourceDraft

    def draft(header_cols: int) -> SourceDraft:
        table = {
            "type": "table",
            "id": "tbl_x",
            "caption": "表題",
            "semantic_type": "generic",
            "layout": {"header_rows": 1, "header_cols": header_cols, "col_widths": [40, 60]},
            "grid": [
                [
                    {"id": "tbl_x__r0c0", "text": "義務の名称", "role": "header"},
                    {"id": "tbl_x__r0c1", "text": "内容", "role": "header"},
                ],
                [
                    {"id": "tbl_x__r1c0", "text": "損害防止義務", "role": "stub"},
                    {"id": "tbl_x__r1c1", "text": "努めること。", "role": "body"},
                ],
            ],
        }
        return SourceDraft.model_validate(
            {
                "content_id": "x",
                "doctype": "auto",
                "seed": 1,
                "meta": {
                    "title": "t",
                    "parties": [
                        {"key": "client", "alias": "甲", "name": "株式会社青葉システムズ"},
                        {"key": "vendor", "alias": "乙", "name": "みなと技研株式会社"},
                    ],
                    "numbering_scheme": "contract-standard",
                    "digit_style": "halfwidth",
                    "disclaimer": "d",
                },
                "front_matter": {"cover": {"title": "t"}},
                "body": [
                    {
                        "id": "ch1",
                        "kind": "chapter",
                        "title": "章",
                        "children": [{"id": "ch1_a1", "kind": "article", "title": "条", "blocks": [table]}],
                    }
                ],
            }
        )

    bad = list(l17_header_cols(LintContext(draft=draft(0))))
    assert bad and "header_cols=0" in bad[0].message
    assert list(l17_header_cols(LintContext(draft=draft(1)))) == []


# --- L18 列挙用の表に caption を付けない（docs/remaining_issues.md Z2） --------


def test_L18は列挙用の表にcaptionが付いているとerror() -> None:
    """`semantic_type: enumeration` に `caption` を付けると、build が「表N」を振って

    紙面に印字される一方、eval の `_gold_tables` は採点対象から除外する（採点は
    `derived.enumerations` 側で行う）ため、紙面どおりに読んだ予測が表として扱われて
    表セル F1 を壊す（auto-0001・quake-0002 で実際に発生）。
    """
    from keiyaku.lint.base import LintContext
    from keiyaku.lint.table_headers import l18_enumeration_table_caption
    from keiyaku.models import SourceDraft

    def draft(semantic_type: str, caption: str | None) -> SourceDraft:
        table = {
            "type": "table",
            "id": "tbl_x",
            "caption": caption,
            "semantic_type": semantic_type,
            "layout": {"header_rows": 0, "header_cols": 1, "col_widths": [10, 90]},
            "grid": [
                [
                    {"id": "tbl_x__r0c0", "text": "{auto_label}", "role": "stub"},
                    {"id": "tbl_x__r0c1", "text": "免責事由その1。", "role": "body"},
                ],
            ],
        }
        return SourceDraft.model_validate(
            {
                "content_id": "x",
                "doctype": "auto",
                "seed": 1,
                "meta": {
                    "title": "t",
                    "parties": [
                        {"key": "client", "alias": "甲", "name": "株式会社青葉システムズ"},
                        {"key": "vendor", "alias": "乙", "name": "みなと技研株式会社"},
                    ],
                    "numbering_scheme": "contract-standard",
                    "digit_style": "halfwidth",
                    "disclaimer": "d",
                },
                "front_matter": {"cover": {"title": "t"}},
                "body": [
                    {
                        "id": "ch1",
                        "kind": "chapter",
                        "title": "章",
                        "children": [{"id": "ch1_a1", "kind": "article", "title": "条", "blocks": [table]}],
                    }
                ],
            }
        )

    bad = list(l18_enumeration_table_caption(LintContext(draft=draft("enumeration", "免責事由"))))
    assert bad and "semantic_type=enumeration" in bad[0].message
    bad_excl = list(l18_enumeration_table_caption(LintContext(draft=draft("exclusions", "免責事由"))))
    assert bad_excl and "semantic_type=exclusions" in bad_excl[0].message
    assert list(l18_enumeration_table_caption(LintContext(draft=draft("enumeration", None)))) == []
    assert list(l18_enumeration_table_caption(LintContext(draft=draft("generic", "表題")))) == []


# --- L19 当事者整合（docs/schema.md §9・docs/lint_rules.md §L19）---------------


def test_L19_未知の当事者キーはerror(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{party:unknown}は、これを行う。"),
    )
    assert "L19" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L19_呼称の直書きはerror(content: Path) -> None:
    """「甲」「乙」を生文字列で書くと落ちる（{party:} で書く）。"""
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "甲は、乙に対し、これを通知する。"),
    )
    assert "L19" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L19_呼称を含む一般語は誤検出しない(content: Path) -> None:
    """**単独出現のみ**を見る。「甲板」「乙種」で落としてはいけない。"""
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__(
            "text", "甲板の塗装および乙種の資格に関する情報は、これに含まれない。"
        ),
    )
    assert "L19" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L19_role_labelが無いのにroleを使うとerror(content: Path) -> None:
    def drop_role(data: dict) -> None:
        data["meta"]["parties"][0].pop("role_label")

    edit(content / "doc.json", drop_role)
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{party:discloser|role}は、これを行う。"),
    )
    assert "L19" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L19_fullの二重使用はwarn(content: Path) -> None:
    """正式名称の導入は 1 回。2 回目は不自然（前文で導入したら以降は呼称で指す）。"""
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "{party:discloser|full}は、これを行う。"),
    )
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L19" in codes(findings, severity="warn")


def test_L19_呼称の重複はerror(content: Path) -> None:
    edit(content / "doc.json", lambda d: d["meta"]["parties"][1].__setitem__("alias", "甲"))
    assert "L19" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


# --- L20 契約書の骨格 ---------------------------------------------------------


def test_L20_記名押印欄が無いとerror(content: Path) -> None:
    edit(content / "doc.json", lambda d: d["parts"].remove("95_signature.json"))
    assert "L20" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L20_記名欄に載っていない当事者がいるとerror(content: Path) -> None:
    edit(content / "parts" / "95_signature.json", lambda d: d["items"][0]["parties"].pop())
    assert "L20" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L20_後文の通数が当事者数と異なるとerror(content: Path) -> None:
    edit(content / "doc.json", lambda d: d["meta"].__setitem__("copies", 1))
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L20" in codes(findings)
    assert any(finding.path == "meta.copies" for finding in findings if finding.code == "L20")


def test_L20_前文がbodyの先頭でないとerror(content: Path) -> None:
    """前文は body の先頭にちょうど 1 つ。"""
    edit(
        content / "doc.json",
        lambda d: d.__setitem__(
            "parts",
            [
                "10_terms.json",
                "05_preamble.json",
                "20_ch1.json",
                "30_ch4.json",
                "80_appendix.json",
                "95_signature.json",
                "90_back.json",
            ],
        ),
    )
    # defined_terms は body に入らないので、並べ替えでは先頭が変わらない。
    # 章を前に出して前文を 2 番目にする。
    edit(
        content / "doc.json",
        lambda d: d.__setitem__(
            "parts",
            [
                "20_ch1.json",
                "05_preamble.json",
                "10_terms.json",
                "30_ch4.json",
                "80_appendix.json",
                "95_signature.json",
                "90_back.json",
            ],
        ),
    )
    assert "L20" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L20_別紙をbodyに置くとerror(content: Path) -> None:
    def to_body(data: dict) -> None:
        data["target"] = "body"
        data["items"][0]["kind"] = "appendix"

    edit(content / "parts" / "80_appendix.json", to_body)
    assert "L20" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


# --- L21 逐条解説 -------------------------------------------------------------


def _commentary(anchor: str, text: str) -> dict:
    return {"type": "commentary", "id": "com_1", "anchor": anchor, "title": "解説", "text": [text]}


def test_L21_anchorが存在しないとerror(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: (
            node(d, "ch1_a1")
            .setdefault("blocks", [])
            .append(_commentary("no_such_article", "この条の趣旨を説明する文である。"))
        ),
    )
    assert "L21" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L21_anchorが条でないとerror(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: (
            node(d, "ch1_a1")
            .setdefault("blocks", [])
            .append(_commentary("ch1", "この条の趣旨を説明する文である。"))
        ),
    )
    assert "L21" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L21_解説が本文の文を写しているとwarn(content: Path) -> None:
    """解説が本文のコピーになっている兆候を拾う。"""

    def put(data: dict) -> None:
        article = node(data, "ch1_a1")
        body_text = article["children"][0]["text"]
        article.setdefault("blocks", []).append(_commentary("ch1_a1", body_text))

    edit(content / "parts" / "20_ch1.json", put)
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L21" in codes(findings, severity="warn")


def test_L21_正しい解説は通る(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: (
            node(d, "ch1_a1")
            .setdefault("blocks", [])
            .append(_commentary("ch1_a1", "実務では、開示の範囲を書面で特定しておくと後の紛争を避けやすい。"))
        ),
    )
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L21" not in codes(findings) and "L21" not in codes(findings, severity="warn")


def test_L19_呼称の連なりは漢字が続いても拾う(content: Path) -> None:
    """「甲乙間」は当事者の直書き。1 文字の「甲板」とは扱いを分ける。"""
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "甲乙間の協議により、これを定める。"),
    )
    assert "L19" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L08_当事者名の実在社名を検出する(content: Path) -> None:
    """**実在の社名が最も入りやすいのは `meta.parties[].name`。**

    `iter_texts` が meta を含んでいないと、ここが素通りして架空性の検査が意味を失う
    （2026-09-26 に実際に素通りした。docs/decisions.md 45）。
    """
    edit(content / "doc.json", lambda d: d["meta"]["parties"][0].__setitem__("name", "株式会社サイボウズ"))
    assert "L08" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L08_当事者の住所の許可外ドメインも検出する(content: Path) -> None:
    edit(
        content / "doc.json",
        lambda d: d["meta"]["parties"][1].__setitem__("address", "https://aoba-systems.co.jp/office"),
    )
    assert "L08" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


# --- L22 表・図の配置 ---------------------------------------------------------


def _figure(fid: str) -> dict:
    """最小の流れ図（L06 の複雑度・alt/facts を満たす）。"""
    return {
        "type": "figure",
        "id": fid,
        "caption": "手続きの流れ",
        "alt": "受領から報告までを 3 段階で示した流れ図。",
        "facts": ["受領が起点である。", "最後は報告に至る。"],
        "diagram": {
            "kind": "flowchart",
            "direction": "TB",
            "nodes": [
                {"id": "m1", "label": "受領", "shape": "start", "col": 0, "row": 0},
                {"id": "m2", "label": "確認", "shape": "process", "col": 0, "row": 1},
                {"id": "m3", "label": "報告", "shape": "end", "col": 0, "row": 2},
            ],
            "edges": [{"from": "m1", "to": "m2"}, {"from": "m2", "to": "m3"}],
        },
    }


def test_L22_条直下の図はerror(content: Path) -> None:
    """条の直下に置いた図は第1項より前に描画される（docs/style_guide.md §4）。"""
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: node(d, "ch1_a1").setdefault("blocks", []).append(_figure("fig_l22")),
    )
    assert "L22" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L22_章直下の表もerror(content: Path) -> None:
    """項に付いていた表を章の直下へ動かすと、導入文より前に描画される。"""

    def put(data: dict) -> None:
        chapter = data["items"][0]
        paragraph = node(data, "ch1_a2_p1")  # 表を持つ項
        chapter["blocks"] = paragraph.pop("blocks")

    edit(content / "parts" / "20_ch1.json", put)
    assert "L22" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L22_項に付けた図は通る(content: Path) -> None:
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).setdefault("blocks", []).append(_figure("fig_l22_ok")),
    )
    assert "L22" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L22_子を持たない条は見逃す(content: Path) -> None:
    """表だけで構成する条は導入文の置きようがない。"""

    def put(data: dict) -> None:
        article = node(data, "ch1_a1")
        article["children"] = []
        article.setdefault("blocks", []).append(_figure("fig_l22_only"))

    edit(content / "parts" / "20_ch1.json", put)
    assert "L22" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


# --- L04 の enumeration min_items ---------------------------------------------


def _count_enumerations(content: Path, min_items: int | None) -> int:
    """`kind: enumeration` の要件が数える件数（`_count_non_block` を直接呼ぶ）。"""
    from keiyaku.blueprints import Requirement
    from keiyaku.compose import load_draft
    from keiyaku.lint.base import LintContext
    from keiyaku.lint.structure import _count_non_block

    ctx = LintContext(draft=load_draft(content), content_dir=content, quick=True)
    return _count_non_block(ctx, Requirement(kind="enumeration", min_items=min_items))


def test_L04_列挙は項目数の下限で絞られる(content: Path) -> None:
    """`min_items` を上げるほど数えられる列挙は減る（増えることはない）。

    項目数まで縛らないと「2 項目の列挙」で「深い列挙がある」要件を満たせてしまう（CT11）。
    """
    counts = [_count_enumerations(content, n) for n in (None, 2, 4, 99)]
    assert counts[0] > 0, "サンプルに列挙が 1 つも無い"
    assert all(b <= a for a, b in zip(counts, counts[1:], strict=False)), counts
    assert counts[-1] == 0, "99 項目の列挙は無いはずなのに数えられている"


def test_L02_脚注が参照より前にあるとerror(content: Path) -> None:
    """脚注ブロックを、参照より前の項に付けると注記が参照の上に描かれる。"""

    def move(data: dict) -> None:
        article = node(data, "ch4_s1_a2")
        notes = [b for b in article["blocks"] if b["type"] == "footnotes"]
        article["blocks"] = [b for b in article["blocks"] if b["type"] != "footnotes"]
        p1, p2 = article["children"][0], article["children"][1]
        p2["text"] = p1["text"]  # 参照を第2項へ移し
        p1["text"] = "この項には注記が付いている。"
        p1["blocks"] = p1.get("blocks", []) + notes  # 脚注は第1項に残す＝参照より前

    edit(content / "parts" / "30_ch4.json", move)
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L02" in codes(findings), [f.format() for f in findings]


def test_L02_条末の脚注は通る(content: Path) -> None:
    assert "L02" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L12_定義文が紙面に無いとwarn(content: Path) -> None:
    """`{term:}` は語を強調するだけで、定義の文は描画されない。

    定義条も定義表も置かないと読み手に意味が伝わらず、`definition` の QA も作れない。
    """

    def blank(data: dict) -> None:
        data["items"][0]["definition"] = "この語は紙面のどこにも書かれていない意味を持つものとする。"

    edit(content / "parts" / "10_terms.json", blank)
    assert "L12" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES), severity="warn")


def test_L12_定義文が本文にあれば通る(content: Path) -> None:
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L12" not in codes(findings, severity="warn"), [f.format() for f in findings]


# --- L23 列挙の入れ子 ---------------------------------------------------------


def test_L23_条の直下に列挙が2組あるとerror(content: Path) -> None:
    """号を導入文と兄弟に並べると、条の中で通し番号になる（(1)…(6) の次が (7)）。"""

    def put(data: dict) -> None:
        article = node(data, "ch1_a1")
        article["children"] += [
            {"id": "ch1_a1_x1", "kind": "paragraph", "text": "次に掲げるものを対象とする。"},
            {"id": "ch1_a1_x2", "kind": "item", "text": "第一の対象"},
            {"id": "ch1_a1_x3", "kind": "item", "text": "第二の対象"},
            {"id": "ch1_a1_y1", "kind": "paragraph", "text": "次に掲げるものは対象としない。"},
            {"id": "ch1_a1_y2", "kind": "item", "text": "第一の除外"},
            {"id": "ch1_a1_y3", "kind": "item", "text": "第二の除外"},
        ]

    edit(content / "parts" / "20_ch1.json", put)
    assert "L23" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L23_導入文の子にすれば通る(content: Path) -> None:
    def put(data: dict) -> None:
        article = node(data, "ch1_a1")
        article["children"] += [
            {
                "id": "ch1_a1_x1",
                "kind": "paragraph",
                "text": "次に掲げるものを対象とする。",
                "children": [
                    {"id": "ch1_a1_x2", "kind": "item", "text": "第一の対象"},
                    {"id": "ch1_a1_x3", "kind": "item", "text": "第二の対象"},
                ],
            },
            {
                "id": "ch1_a1_y1",
                "kind": "paragraph",
                "text": "次に掲げるものは対象としない。",
                "children": [
                    {"id": "ch1_a1_y2", "kind": "item", "text": "第一の除外"},
                    {"id": "ch1_a1_y3", "kind": "item", "text": "第二の除外"},
                ],
            },
        ]

    edit(content / "parts" / "20_ch1.json", put)
    assert "L23" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L23_列挙が1組なら兄弟でよい(content: Path) -> None:
    assert "L23" not in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES))


def test_L11_日付の一部は期間の直書きと数えない(content: Path) -> None:
    """「２０２７年６月２１日」の「２１日」は期間の「２１日」ではない。"""

    def put(data: dict) -> None:
        data["meta"]["constants"]["probe_days"] = "２１日"

    edit(content / "doc.json", put)
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "２０２７年６月２１日に引き渡すものとする。"),
    )
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L11" not in codes(findings, severity="warn"), [f.format() for f in findings]


def test_L11_期間そのものの直書きは拾う(content: Path) -> None:
    def put(data: dict) -> None:
        data["meta"]["constants"]["probe_days"] = "２１日"

    edit(content / "doc.json", put)
    edit(
        content / "parts" / "20_ch1.json",
        lambda d: first_paragraph(d).__setitem__("text", "求めを受けた日から２１日以内に行うものとする。"),
    )
    assert "L11" in codes(lint_content(content, quick=True, exclude=DOCUMENT_RULES), severity="warn")


def test_逐条解説の文字もlintの対象になる(content: Path) -> None:
    """解説は紙面に描かれるので、架空性（L08）などの検査が効かなければならない。"""

    def put(data: dict) -> None:
        node(data, "ch1_a1").setdefault("blocks", []).append(
            {
                "type": "commentary",
                "id": "com_walk",
                "anchor": "ch1_a1",
                "title": "解説",
                "text": ["この条の趣旨について、トヨタ自動車の事例を引いて述べる。"],
            }
        )

    edit(content / "parts" / "20_ch1.json", put)
    findings = lint_content(content, quick=True, exclude=DOCUMENT_RULES)
    assert "L08" in codes(findings), [f.format() for f in findings]


def test_L04_執筆メモが残っているとerror(content: Path) -> None:
    """`_todo` は pydantic の検証で捨てられるので、**生の JSON を読み直さないと見えない**。"""
    edit(content / "doc.json", lambda d: d.__setitem__("_todo", "まだ書いていない"))
    assert "L04" in codes(lint_content(content, quick=True, exclude=["L09", "L15", "L16"]))


def test_L04_執筆メモが無ければ通る(content: Path) -> None:
    findings = lint_content(content, quick=True, exclude=["L09", "L15", "L16"])
    assert not [f for f in findings if f.code == "L04" and "_todo" in f.message]


# --- L24 置き去りの part / L25 Markdown の名残 -------------------------------


def test_L24は参照されていないpartを見つける(content: Path) -> None:
    """書き直しで置き去りになった part は、未執筆のまま誰にも見えずに残る。"""
    (content / "parts" / "99_orphan.json").write_text(
        json.dumps({"target": "body", "items": []}, ensure_ascii=False), encoding="utf-8"
    )
    findings = [f for f in lint_content(content, quick=True) if f.code == "L24"]
    assert findings and "99_orphan.json" in findings[0].message


def test_L25はMarkdownの名残を見つける(content: Path) -> None:
    """`**強調**` は RichText では解釈されず、**そのまま紙面に印字される**。"""

    def put(data: dict) -> None:
        node(data, "ch1_a1")["children"][0]["text"] = "この定めは**置かない**。"

    edit(content / "parts" / "20_ch1.json", put)
    findings = [f for f in lint_content(content, quick=True) if f.code == "L25"]
    assert findings, "Markdown の名残を見逃している"
    assert "**" in findings[0].message


def test_L26は番号を持つ表を下表で指すと警告する(content: Path) -> None:
    """キャプション（番号）を持つ表は `{ref:}` で指す。「下表」は版面が変わると嘘になる。"""

    def put(data: dict) -> None:
        paragraph = node(data, "ch4_s2_a1_p1")
        paragraph["text"] = "手続きの期限は下表のとおりとする。"

    edit(content / "parts" / "30_ch4.json", put)
    findings = [f for f in lint_content(content, quick=True) if f.code == "L26"]
    assert findings and "tbl_duties" in findings[0].message


def test_L26は番号を持たない列挙表には出ない(content: Path) -> None:
    """列挙用に組んだ表は caption を持たない（L18）ので、「下表」でよい。"""
    findings = [f for f in lint_content(content, quick=True) if f.code == "L26"]
    assert not findings, [f.format() for f in findings]
