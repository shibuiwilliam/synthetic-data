"""番号付けの現在の挙動を golden として書き出す（P2-2 の同一性検証の土台）。

`keiyaku/numbering.py` を宣言（`numbering/<scheme>.yaml` ＋ 解釈器）に置き換えるとき、
**置き換え前の出力**と突き合わせられないと「壊していないこと」を言えない。
このスクリプトは、ラベル・別表ラベル・脚注マーカー・見出し文字列・`{ref:}` 解決を
総当たりで JSON に落とす。

    uv run python scripts/capture_numbering_golden.py            # 書き出し
    uv run python scripts/capture_numbering_golden.py --check    # 現在の実装と一致するか

出力：`tests/golden/numbering_legacy.json`（yakkan から移植した実装の挙動）。
`tests/unit/test_numbering_spec.py` が、YAML 解釈器がこれを再現することを固定する。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from keiyaku.models import Node  # noqa: E402
from keiyaku.numbering import (  # noqa: E402
    DocumentIndex,
    NumberingContext,
    appendix_label,
    footnote_marker,
    heading_text,
    label_for,
    resolve_ref,
)

OUT = ROOT / "tests" / "golden" / "numbering_legacy.json"

SCHEMES = ("nonlife", "life", "teikan", "group", "jyusetsu")
KINDS = (
    "part",
    "chapter",
    "section",
    "article",
    "paragraph",
    "item",
    "subitem",
    "subsubitem",
    "appendix_section",
)
DIGITS = ("fullwidth", "halfwidth")
#: 丸数字の上限（⑳）越え・カタカナの端も踏むように選ぶ
INDEXES = (1, 2, 3, 10, 12, 21)
SIBLINGS = (1, 3)


def _tree() -> tuple[list[Node], list[Node]]:
    """参照解決の検査に使う木。章 2 つ・節・条・項・号・別表を持つ。"""
    body = [
        Node(
            id="ch1",
            kind="chapter",
            title="第一の章",
            children=[
                Node(
                    id="ch1_a1",
                    kind="article",
                    title="目的",
                    children=[
                        Node(id="ch1_a1_p1", kind="paragraph", text="本文一。"),
                        Node(id="ch1_a1_p2", kind="paragraph", text="本文二。"),
                    ],
                ),
                Node(
                    id="ch1_a2",
                    kind="article",
                    title="定義",
                    children=[
                        Node(
                            id="ch1_a2_p1",
                            kind="paragraph",
                            text="本文三。",
                            children=[
                                Node(id="ch1_a2_p1_i1", kind="item", text="号一。"),
                                Node(id="ch1_a2_p1_i2", kind="item", text="号二。"),
                            ],
                        )
                    ],
                ),
            ],
        ),
        Node(
            id="ch2",
            kind="chapter",
            title="第二の章",
            children=[
                Node(
                    id="ch2_s1",
                    kind="section",
                    title="第一の節",
                    children=[
                        Node(
                            id="ch2_s1_a1",
                            kind="article",
                            title="通知",
                            children=[Node(id="ch2_s1_a1_p1", kind="paragraph", text="本文四。")],
                        )
                    ],
                )
            ],
        ),
    ]
    appendices = [
        Node(
            id="app1",
            kind="appendix",
            title="別表の一",
            children=[
                Node(
                    id="app1_s1",
                    kind="appendix_section",
                    title="区分",
                    children=[Node(id="app1_s1_p1", kind="paragraph", text="別表の本文。")],
                )
            ],
        )
    ]
    return body, appendices


def capture() -> dict:
    out: dict = {"labels": {}, "appendix_labels": {}, "footnotes": {}, "headings": {}, "refs": {}}

    for scheme in SCHEMES:
        for digit in DIGITS:
            for kind in KINDS:
                for n in INDEXES:
                    for siblings in SIBLINGS:
                        for in_appendix in (False, True):
                            ctx = NumberingContext(scheme=scheme, digit_style=digit)  # type: ignore[arg-type]
                            key = f"{scheme}|{digit}|{kind}|{n}|{siblings}|{int(in_appendix)}"
                            label = label_for(
                                ctx,
                                kind,  # type: ignore[arg-type]
                                n,
                                node_id="x",
                                siblings=siblings,
                                scope="appendix" if in_appendix else "body",
                            )
                            out["labels"][key] = {
                                "label": label,
                                "warnings": [w.message for w in ctx.warnings],
                            }

            for index in (1, 2, 3):
                for kind_label in (None, "付表", "別紙"):
                    ctx = NumberingContext(scheme=scheme, digit_style=digit)  # type: ignore[arg-type]
                    key = f"{scheme}|{digit}|{index}|{kind_label or '-'}"
                    out["appendix_labels"][key] = appendix_label(ctx, index, kind_label)

            for style in ("inline", "remarks_box"):
                for n in (1, 2, 11):
                    ctx = NumberingContext(
                        scheme=scheme,  # type: ignore[arg-type]
                        digit_style=digit,  # type: ignore[arg-type]
                        footnote_style=style,  # type: ignore[arg-type]
                    )
                    out["footnotes"][f"{scheme}|{digit}|{style}|{n}"] = footnote_marker(ctx, n)

    for kind in ("chapter", "article", "item"):
        for article_heading in ("inline", "above", "plain"):
            for label, title in (("第１条", "目的"), ("", "目的"), ("第１条", None)):
                key = f"{kind}|{article_heading}|{label or '-'}|{title or '-'}"
                out["headings"][key] = heading_text(kind, label, title, article_heading)  # type: ignore[arg-type]

    body, appendices = _tree()
    ids = [
        "ch1",
        "ch1_a1",
        "ch1_a1_p1",
        "ch1_a1_p2",
        "ch1_a2",
        "ch1_a2_p1",
        "ch1_a2_p1_i1",
        "ch2",
        "ch2_s1",
        "ch2_s1_a1",
        "ch2_s1_a1_p1",
        "app1",
        "app1_s1",
        "app1_s1_p1",
    ]
    for scheme in SCHEMES:
        for digit in DIGITS:
            ctx = NumberingContext(scheme=scheme, digit_style=digit)  # type: ignore[arg-type]
            index = DocumentIndex(ctx, body, appendices)
            for from_id in ids:
                for to_id in ids:
                    for mode in ("relative", "short", "full"):
                        key = f"{scheme}|{digit}|{from_id}->{to_id}|{mode}"
                        try:
                            out["refs"][key] = resolve_ref(index, from_id, to_id, mode)  # type: ignore[arg-type]
                        except KeyError:
                            out["refs"][key] = None
            out["labels"][f"citation|{scheme}|{digit}"] = {
                node_id: index.citation(node_id) for node_id in ids
            }
    return out


def main() -> int:
    data = capture()
    text = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if "--check" in sys.argv:
        if not OUT.is_file():
            print(f"golden が無い: {OUT}")
            return 1
        same = OUT.read_text(encoding="utf-8") == text
        print("一致" if same else f"不一致（{OUT} を更新するか実装を直す）")
        return 0 if same else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    counts = {k: len(v) for k, v in data.items()}
    print(f"書き出し: {OUT}")
    print("  " + " / ".join(f"{k} {n}" for k, n in counts.items()))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
