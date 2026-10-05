"""docs/schema.md §5.10 のサンプルが lint を通ること（P1 の DoD）。

docs から JSON を切り出して検査するので、仕様のサンプルを直したら自動で追従する。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from keiyaku.lint.runner import lint_content

DOCS = Path(__file__).resolve().parents[2] / "docs" / "schema.md"
BASE = Path(__file__).parent / "sample_min"

#: サンプルが無ければ検査するものが無い（2026-09-27 に §5.10 を書いたので、いまは有効）。
pytestmark = pytest.mark.skipif(
    "### 5.10" not in DOCS.read_text(encoding="utf-8"),
    reason="docs/schema.md に記法サンプル（§5.10）が無い",
)


def extract_sample() -> dict:
    """§5.10 の ```json ブロックを取り出す。"""
    text = DOCS.read_text(encoding="utf-8")
    section = text.split("### 5.10")[1]
    match = re.search(r"```json\n(.*?)```", section, re.DOTALL)
    assert match, "docs/schema.md §5.10 に json ブロックが無い"
    return json.loads(match.group(1))


def test_サンプルはNodeとして妥当() -> None:
    from keiyaku.models import Node

    node = Node.model_validate(extract_sample())
    assert node.id == "ch4_s1_a2"
    assert node.kind == "article"


def test_サンプルがlintを通る(tmp_path: Path) -> None:
    """サンプル単体は文書ではないので、最小の枠（meta・奥付・用語）に載せて検査する。"""
    import shutil

    content = tmp_path / "schema_sample"
    shutil.copytree(BASE, content)
    # body をサンプル 1 件だけに差し替える
    (content / "parts" / "20_ch1.json").write_text(
        json.dumps(
            {
                "target": "body",
                "items": [
                    {
                        "id": "ch4",
                        "kind": "chapter",
                        "title": "基本条項",
                        "children": [
                            {
                                "id": "ch4_s1",
                                "kind": "section",
                                "title": "契約手続と義務",
                                "children": [extract_sample()],
                            }
                        ],
                    }
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    for name in ("30_ch4.json", "80_appendix.json"):
        (content / "parts" / name).unlink()
    doc = json.loads((content / "doc.json").read_text(encoding="utf-8"))
    # **前文と記名押印欄は残す**。契約書の骨格（L20）はサンプル 1 条とは無関係に要る。
    doc["parts"] = [
        "10_terms.json",
        "05_preamble.json",
        "20_ch1.json",
        "95_signature.json",
        "90_back.json",
    ]
    (content / "doc.json").write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")

    # サンプルは 1 条だけの断片なので、文書全体を見る規則は外す。
    # L12 も外す：用語の枠は残したまま本文だけ差し替えるので「使われていない語」が必ず出る。
    findings = lint_content(content, exclude=["L04", "L09", "L12", "L15", "L16"])
    assert findings == [], "\n".join(f.format() for f in findings)


#: 契約書で使う記法を一通り。**`{party:}` を必ず含める**——当事者の直書きを避ける機構であり、
#: 契約書の記法サンプルがこれを見せないなら見本の意味が無い（docs/schema.md §5.10）。
@pytest.mark.parametrize(
    "token",
    [
        "{party:discloser}",
        "{party:receiver}",
        "{term:confidential}",
        "{const:survival_years}",
        "{fn:1}",
        "{ref:ch4_s1_a2_p1}",
        "{auto_label}",
    ],
)
def test_サンプルが記法の見本になっている(token: str) -> None:
    assert token in json.dumps(extract_sample(), ensure_ascii=False)
