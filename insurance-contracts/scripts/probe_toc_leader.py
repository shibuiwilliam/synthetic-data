"""目次のリーダー罫をテキストでなく罫線で描けるかを測る（docs/remaining_issues.md W6）。

現行は `content: leader('.') target-counter(...)`。WeasyPrint はこれを
**本物の「.」の連なり**として描くので、PDF のテキスト層に数千字の点が入り、
`answer.pages[].text` もそれを含む。文字単位で完璧に読んだページが CER 0.775 になった。

代替案を 4 通り試し、次を測る：

1. テキスト層に「.」が何個入るか（0 が目標）
2. ページ番号が右端に出るか（`target-counter` が効いているか）
3. 見出しとページ番号の間が罫でつながって見えるか（描画の確認は PNG で目視）

    uv run python scripts/probe_toc_leader.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

ENTRIES = [
    ("sec1", "1　用語のご説明"),
    ("sec2", "2　契約締結前におけるご確認事項"),
    ("sec3", "3　契約締結後におけるご注意事項"),
]

COMMON = """
@page { size: A4; margin: 20mm; }
body { font-family: "Noto Sans JP", sans-serif; font-size: 10pt; }
.target { page-break-before: always; }
"""

CASES: dict[str, str] = {
    # 現行：leader() が「.」を実際に描く
    "leader": """
nav .line { display: block; }
nav .line a { text-decoration: none; color: inherit; }
nav .line a::after { content: leader('.') target-counter(attr(href), page); }
""",
    # 案1：flex で伸びる罫線を挟む
    "flex_border": """
nav .line { display: flex; align-items: baseline; }
nav .line .rule { flex: 1 1 auto; border-bottom: 0.5pt dotted #666; margin: 0 2pt; }
nav .line a { text-decoration: none; color: inherit; }
nav .line .page::after { content: target-counter(attr(data-href), page); }
""",
    # 案2：見出しを左、ページ番号を右へ float し、行に点線の下罫を引く
    "float_border": """
nav .line { display: block; overflow: hidden; border-bottom: 0.5pt dotted #666; }
nav .line a { text-decoration: none; color: inherit; float: left; background: #fff; padding-right: 2pt; }
nav .line .page { float: right; background: #fff; padding-left: 2pt; }
nav .line .page::after { content: target-counter(attr(data-href), page); }
""",
    # 案3：leader を空白にして、行に点線の下罫を引く
    "leader_space": """
nav .line { display: block; border-bottom: 0.5pt dotted #666; }
nav .line a { text-decoration: none; color: inherit; }
nav .line a::after { content: leader(' ') target-counter(attr(href), page); }
""",
    # 案4：罫を **box に足さない**（下線）。行の高さが変わらないので組版が動かない
    "underline": """
nav .line { display: block; }
nav .line a { text-decoration: none; color: inherit; }
nav .line a::after { content: leader(' ') target-counter(attr(href), page);
                     text-decoration: underline dotted; }
""",
    # 案5：リーダーを引かない（空白だけ）
    "space_only": """
nav .line { display: block; }
nav .line a { text-decoration: none; color: inherit; }
nav .line a::after { content: leader(' ') target-counter(attr(href), page); }
""",
}


def build(case: str) -> str:
    rows = []
    for anchor, title in ENTRIES:
        if case in ("flex_border",):
            rows.append(
                f'<span class="line"><a href="#{anchor}">{title}</a>'
                f'<span class="rule"></span><span class="page" data-href="#{anchor}"></span></span>'
            )
        elif case in ("float_border",):
            rows.append(
                f'<span class="line"><a href="#{anchor}">{title}</a>'
                f'<span class="page" data-href="#{anchor}"></span></span>'
            )
        else:
            rows.append(f'<span class="line"><a href="#{anchor}">{title}</a></span>')
    targets = "".join(f'<h2 class="target" id="{a}">{t}</h2><p>本文。</p>' for a, t in ENTRIES)
    return (
        f"<html><head><meta charset='utf-8'><style>{COMMON}{CASES[case]}</style></head>"
        f"<body><nav>{''.join(rows)}</nav>{targets}</body></html>"
    )


def main() -> int:
    import pdfplumber
    from weasyprint import HTML

    out_dir = ROOT / "scratch" / "probe_toc_leader"
    out_dir.mkdir(parents=True, exist_ok=True)

    print(f"{'case':16} {'「.」の数':>10} {'ページ番号':>12}  1 行目のテキスト層")
    for case in CASES:
        pdf_path = out_dir / f"{case}.pdf"
        HTML(string=build(case)).write_pdf(str(pdf_path))
        with pdfplumber.open(str(pdf_path)) as pdf:
            text = pdf.pages[0].extract_text() or ""
        first = text.splitlines()[0] if text.splitlines() else ""
        dots = text.count(".")
        has_page = "はい" if any(c.isdigit() for c in first) else "いいえ"
        print(f"{case:16} {dots:>10} {has_page:>12}  {first[:46]}")

    print()
    print("判断の材料：「.」が 0 で、ページ番号が出ていて、PNG で罫がつながって見えるものを採る。")
    print(f"PDF: {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
