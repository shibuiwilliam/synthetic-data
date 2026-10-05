"""style の `chars_per_page_estimate` を較正する（docs/rendering.md §6.10）。

    uv run python scripts/calibrate_styles.py                  # 実コーパスから較正して表示
    uv run python scripts/calibrate_styles.py --write          # styles/*.yaml に書き戻す
    uv run python scripts/calibrate_styles.py --synthetic      # 地の文を流し込む旧方式

**既定は実コーパスからの較正**（`--from-dataset` 相当）。`dataset/<doc_id>/layout.json` の
実ページ数に L09 の見積りが合うような値を、style ごとに二分法で解く。
L09 の他の係数（表 1.25 倍・図 0.24 ページ…）は実文書で当ててあるので、
**基準となる字数だけを同じ土俵で合わせる**のが筋。

`--synthetic`（旧方式）は地の文を流し込んで 1 ページ目の文字数を数える。
**この方式は版面が違っても同じ値を返すことがある**（docs/remaining_issues.md R6）。
原因は `.para { break-inside: avoid }` で段落が分割されないこと。
1 ページの容量が**段落単位で量子化**されるため、段落 1 つぶん（2 行前後）より細かく測れず、
別の版面が同じ段落数に着地すると同値になる。新しい style を足した直後など、
まだ 1 文書も描いていないときだけ使う。
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from keiyaku.fonts import font_face_css  # noqa: E402
from keiyaku.styles import STYLES_DIR, available_styles, load_style  # noqa: E402

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
    from keiyaku.render.html import build_css

    class _Meta:
        form_code = "Ｄ００００００"
        digit_style = "fullwidth"
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


def corpus_samples(dataset_dir: Path) -> dict[str, list[tuple[Path, int]]]:
    """style_id → [(content ディレクトリ, 実ページ数)]。"""
    import json

    out: dict[str, list[tuple[Path, int]]] = {}
    for layout_path in sorted(dataset_dir.glob("*/layout.json")):
        layout = json.loads(layout_path.read_text(encoding="utf-8"))
        content_dir = Path("content") / layout["content_id"]
        if content_dir.is_dir():
            out.setdefault(layout["style_id"], []).append((content_dir, int(layout["page_count"])))
    return out


def fit_from_corpus(samples: list[tuple[Path, int]], *, low: int = 300, high: int = 4000) -> int:
    """実ページ数に L09 の見積りが合う `chars_per_page` を二分法で解く。

    見積りは `chars_per_page` について単調減少なので、二分法で足りる。
    """
    from keiyaku.blueprints import load_blueprint
    from keiyaku.compose import load_draft
    from keiyaku.lint.budget import estimate_pages

    drafts = []
    for content_dir, actual in samples:
        draft = load_draft(content_dir)
        drafts.append((draft, load_blueprint(draft.doctype), actual))

    def residual(cpp: int) -> float:
        """予測 − 実測 の合計（正なら予測が大きい＝ cpp を増やすべき）。"""
        return sum(estimate_pages(d, b, chars_per_page=cpp).pages - a for d, b, a in drafts)

    lo, hi = low, high
    for _ in range(40):
        mid = (lo + hi) // 2
        if residual(mid) > 0:
            lo = mid + 1
        else:
            hi = mid
        if lo >= hi:
            break
    return lo


def main(argv: list[str]) -> int:
    write = "--write" in argv
    synthetic = "--synthetic" in argv
    dataset_dir = Path("dataset")
    samples = {} if synthetic else corpus_samples(dataset_dir)

    print(f"{'style_id':26} {'現在値':>8} {'較正値':>8} {'文書':>4}  方式")
    for style_id in available_styles():
        current = load_style(style_id).chars_per_page_estimate
        rows = samples.get(style_id, [])
        if rows:
            measured, how, count = fit_from_corpus(rows), "コーパス", len(rows)
        else:
            measured, how, count = measure(style_id), "合成（粗い）", 0
        mark = "" if abs(measured - current) <= current * 0.02 else "  ← 更新"
        print(f"{style_id:26} {current:8} {measured:8} {count:4}  {how}{mark}")
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
