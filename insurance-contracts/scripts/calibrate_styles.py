"""style の `chars_per_page_estimate` を実測で較正する（docs/rendering.md §6.10）。

    uv run python scripts/calibrate_styles.py            # 全スタイルを測って表示
    uv run python scripts/calibrate_styles.py --write    # styles/*.yaml に書き戻す

地の文だけを大量に流し込み、**2 ページ目の先頭に何文字目が来たか**から 1 ページあたりの
字数を求める。表・図が入るとこれより減るので、lint L09 は表を 0.6 倍・図を固定高で見積もる。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from yakkan.fonts import font_face_css  # noqa: E402
from yakkan.styles import STYLES_DIR, available_styles, load_style  # noqa: E402

#: 較正用の地の文（このファイルで書き下ろしたオリジナル文。約款らしい語と文長に寄せてある）
SAMPLE_SENTENCES = (
    "当会社は、被保険者がこの条項に定める事由により損害を被った場合に、この約款に従い保険金を支払います。",
    "保険契約者または被保険者は、当会社が書面等で確認を求めた事項について、遅滞なく事実を通知しなければなりません。",
    "前項の通知が行われなかった場合において、当会社は、その事実が保険金の支払に影響を及ぼす限度において、"
    "支払うべき保険金の額を減額することがあります。",
    "ただし、その事実が生じたことについて保険契約者および被保険者に責任がないときは、この限りではありません。",
    "当会社は、保険金の請求を受けた場合は、必要な確認を行ったうえで、所定の期間内に保険金を支払います。",
)


def sample_text(repeat: int) -> list[str]:
    return [SAMPLE_SENTENCES[i % len(SAMPLE_SENTENCES)] for i in range(repeat)]


def build_html(style, paragraphs: list[str]) -> str:
    from yakkan.render.html import build_css

    class _Meta:
        form_code = "Ｄ００００００"
        constants: dict[str, str] = {}

    class _Source:
        meta = _Meta()

    css = build_css(style, _Source())
    body = "\n".join(
        f'<div class="para no-label" id="p{i}" data-kind="paragraph">{text}</div>'
        for i, text in enumerate(paragraphs)
    )
    return (
        "<!DOCTYPE html><html lang='ja'><head><meta charset='utf-8'>"
        f"<style>{font_face_css()}\n{css}</style></head>"
        f'<body><div class="cols" id="doc_body">{body}</div></body></html>'
    )


def measure(style_id: str) -> int:
    """1 ページに収まる地の文の字数を測る。

    段落単位で数えると分解能が粗く、別のスタイルが同じ値になってしまう。
    **1 ページ目に実際に描かれた文字数**（box ツリーの TextBox の合計）で数える。
    """
    from weasyprint import HTML
    from weasyprint.text.fonts import FontConfiguration

    style = load_style(style_id)
    html = build_html(style, sample_text(200))
    document = HTML(string=html, base_url=str(ROOT)).render(font_config=FontConfiguration())

    def text_length(box) -> int:
        if type(box).__name__ == "TextBox":
            return len(box.text or "")
        return sum(text_length(child) for child in getattr(box, "children", []))

    return text_length(document.pages[0]._page_box)


def main(argv: list[str]) -> int:
    write = "--write" in argv
    print(f"{'style_id':26} {'現在値':>8} {'実測':>8}  差")
    for style_id in available_styles():
        current = load_style(style_id).chars_per_page_estimate
        measured = measure(style_id)
        mark = "" if abs(measured - current) <= current * 0.05 else "  ← 更新"
        print(f"{style_id:26} {current:8} {measured:8}{mark}")
        if write:
            path = STYLES_DIR / f"{style_id}.yaml"
            text = path.read_text(encoding="utf-8")
            path.write_text(
                re.sub(r"chars_per_page_estimate: \d+", f"chars_per_page_estimate: {measured}", text),
                encoding="utf-8",
            )
    if write:
        print("\nstyles/*.yaml に書き戻した")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
