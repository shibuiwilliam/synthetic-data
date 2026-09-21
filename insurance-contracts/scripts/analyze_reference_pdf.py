"""参考 PDF の**構造だけ**を測る（CLAUDE.md §0.4-1・docs/reference_structures.md）。

    uv run python scripts/analyze_reference_pdf.py <pdf> [...]

**このスクリプトは本文を一切出力しない。** 出すのは件数・パターン・座標統計だけで、
実在約款の文章がリポジトリや報告に混ざらないようにするための道具。

測るもの：ページ数・判型・段組数・見出し記号の出現数・番号方式・脚注記号・
表の件数と列数の分布・ヘッダ/フッタの有無・図（ベクタ描画）の密度。
"""

from __future__ import annotations

import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

#: 見出し・番号の記号パターン（本文は取り出さず、**一致した件数だけ**数える）
PATTERNS: dict[str, re.Pattern[str]] = {
    "第N編": re.compile(r"第[0-9０-９一二三四五六七八九十]+編"),
    "第N部": re.compile(r"第[0-9０-９一二三四五六七八九十]+部"),
    "第N章": re.compile(r"第[0-9０-９一二三四五六七八九十]+章"),
    "第N節": re.compile(r"第[0-9０-９一二三四五六七八九十]+節"),
    "第N条": re.compile(r"第[0-9０-９一二三四五六七八九十]+条"),
    "全角括弧数字（N）": re.compile(r"（[0-9０-９]+）"),
    "半角括弧数字(N)": re.compile(r"\([0-9]+\)"),
    "丸数字①": re.compile(r"[①-⑳]"),
    "黒丸数字❶": re.compile(r"[❶-❿⓫-⓴]"),
    "半角カナ ｱ.": re.compile(r"[ｱ-ﾝ][.．]"),
    "括弧カナ (ｱ)": re.compile(r"[（(][ｱ-ﾝ][）)]"),
    "ローマ数字ⅰ": re.compile(r"[ⅰ-ⅹⅠ-Ⅹ]"),
    "脚注（*N）": re.compile(r"[（(]\s*[*＊][0-9０-９]+\s*[）)]"),
    "脚注（注N）": re.compile(r"[（(]注[0-9０-９]*[）)]"),
    "※": re.compile(r"※"),
    "別表N": re.compile(r"別表[0-9０-９一二三四五六七八九十]+"),
    "付表N": re.compile(r"付表[0-9０-９一二三四五六七八九十]+"),
    "別紙": re.compile(r"別紙"),
    "附則": re.compile(r"附則"),
    "特約": re.compile(r"特約"),
    "〈欄外注〉": re.compile(r"〈[^〉]{1,40}〉"),
    "リーダー罫": re.compile(r"[.．・]{6,}"),
}

#: 文体の判定（文末形の出現数だけを数える）
STYLE_PATTERNS: dict[str, re.Pattern[str]] = {
    "敬体（ます・です）": re.compile(r"(ます|です)[。、]"),
    "常体（する・とする）": re.compile(r"(する|とする|できる)。"),
}


@dataclass
class PageStat:
    number: int
    width: float
    height: float
    lines: int
    columns: int
    tables: int
    table_cols: list[int] = field(default_factory=list)
    rects: int = 0
    curves: int = 0
    has_header: bool = False
    has_footer: bool = False


def detect_columns(chars, width: float) -> int:
    """x 座標のヒストグラムの谷から段組数を推定する。"""
    if not chars:
        return 0
    bins = [0] * 20
    for c in chars:
        bins[min(int(c["x0"] / width * 20), 19)] += 1
    total = sum(bins)
    if total < 200:
        return 1
    # 中央付近（8〜11 番目のビン）がほぼ空なら 2 段組
    middle = sum(bins[9:11])
    return 2 if middle < total * 0.012 else 1


def analyze(path: Path, sample: int = 0) -> None:
    import pdfplumber

    counts: Counter[str] = Counter()
    style: Counter[str] = Counter()
    pages: list[PageStat] = []
    top_lines: Counter[str] = Counter()
    bottom_lines: Counter[str] = Counter()

    with pdfplumber.open(path) as pdf:
        total = len(pdf.pages)
        indexes = (
            range(total)
            if not sample
            else sorted({int(i * (total - 1) / (sample - 1)) for i in range(sample)})
        )
        for i in indexes:
            page = pdf.pages[i]
            text = page.extract_text() or ""
            # 和文 PDF は字送りを個別に持つことが多く、extract_text が字間に空白を入れる。
            # 空白を潰してから数えないと「第 １ 条」のような行を取りこぼす。
            packed = re.sub(r"[\s\u3000]+", "", text)
            for name, pattern in PATTERNS.items():
                counts[name] += len(pattern.findall(packed))
            for name, pattern in STYLE_PATTERNS.items():
                style[name] += len(pattern.findall(packed))
            lines = text.splitlines()
            tables = page.find_tables()
            stat = PageStat(
                number=i + 1,
                width=round(page.width, 1),
                height=round(page.height, 1),
                lines=len(lines),
                columns=detect_columns(page.chars, page.width),
                tables=len(tables),
                table_cols=[len(t.columns) - 1 for t in tables if t.columns],
                rects=len(page.rects),
                curves=len(page.curves),
            )
            # ヘッダ／フッタは「同じ位置に繰り返し出る短い行」の有無だけを見る（内容は記録しない）
            if lines:
                stat.has_header = bool(page.crop((0, 0, page.width, page.height * 0.07)).chars)
                stat.has_footer = bool(page.crop((0, page.height * 0.93, page.width, page.height)).chars)
                top_lines[_shape(lines[0])] += 1
                bottom_lines[_shape(lines[-1])] += 1
            pages.append(stat)

    _report(path, total, pages, counts, style, top_lines, bottom_lines)


def _shape(line: str) -> str:
    """行を「文字種の並び」に潰す（本文を残さないため）。"""
    out = []
    for char in line[:24]:
        if char.isdigit():
            out.append("9")
        elif "０" <= char <= "９":
            out.append("９")
        elif char.isascii() and char.isalpha():
            out.append("A")
        elif char.isspace():
            out.append("_")
        elif ord(char) > 0x3000:
            out.append("字")
        else:
            out.append("記")
    return "".join(out)


def _report(path, total, pages, counts, style, top_lines, bottom_lines) -> None:
    sampled = len(pages)
    sizes = Counter((p.width, p.height) for p in pages)
    columns = Counter(p.columns for p in pages)
    all_cols = [c for p in pages for c in p.table_cols]
    print(f"\n=== {path.name} ===")
    print(f"総ページ数: {total}（解析 {sampled} ページ）")
    for (w, h), n in sizes.most_common(3):
        print(f"  判型: {w}×{h}pt  {n} ページ")
    print(f"  段組の分布: {dict(columns)}")
    print(
        f"  表があるページ: {sum(1 for p in pages if p.tables)} / {sampled}"
        f"  表の総数: {sum(p.tables for p in pages)}"
    )
    if all_cols:
        print(f"  表の列数の分布: {dict(Counter(all_cols).most_common())}")
    print(
        f"  ヘッダ帯に文字があるページ: {sum(p.has_header for p in pages)}"
        f" / フッタ帯: {sum(p.has_footer for p in pages)}"
    )
    print(
        f"  矩形の多いページ（図表の目安）: {sum(1 for p in pages if p.rects > 40)}"
        f" / 曲線のあるページ: {sum(1 for p in pages if p.curves > 4)}"
    )
    print("  記号・番号の出現数:")
    for name, n in counts.most_common():
        if n:
            print(f"    {name:20} {n}")
    print(f"  文末形: {dict(style)}")
    print(f"  先頭行の形（上位3）: {[s for s, _ in top_lines.most_common(3)]}")
    print(f"  末尾行の形（上位3）: {[s for s, _ in bottom_lines.most_common(3)]}")


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    sample = 0
    paths = []
    for arg in argv:
        if arg.startswith("--sample="):
            sample = int(arg.split("=")[1])
        else:
            paths.append(Path(arg))
    for path in paths:
        analyze(path, sample=sample)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
