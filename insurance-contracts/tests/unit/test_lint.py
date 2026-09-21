"""lint ルール（CLAUDE.md §8）。壊した入力で検出されることを確かめる。"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from yakkan.lint.runner import lint_content, summarize

SAMPLE = Path(__file__).resolve().parents[1] / "golden" / "sample_min"


#: 文書全体を対象にする規則。sample_min は 3 ページの抜粋なので、これらは対象外にする
DOCUMENT_RULES = ["L04", "L09", "L15"]


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
