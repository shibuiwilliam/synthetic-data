"""契約書固有の描画を実測する probe（docs/rendering.md §7 の P2 冒頭 3 件）。

    uv run python scripts/probe_signature.py

**設計より先にこれを走らせる。** 結果は `docs/decisions.md` と `docs/gotchas.md` に転記する
（CLAUDE.md §14「憶測で実装しない」）。

測るもの：

1. **記名押印欄の「印」丸枠**：`border-radius` の円と文字の重ね（inline-block 積み）が
   bbox 抽出で 1 要素に収まるか。印影画像は作らないので、枠は CSS の円で描く（CLAUDE.md §15）。
2. **`signature_layout: horizontal`**：2 者を左右に並べたとき読み順が「左→右」で取れるか。
   縦並び（`vertical`）との差も見る。
3. **`- 1 -` 型フッタ**：yakkan の `page_number: dashed` がそのまま使えるか（移植確認）。
   ページ番号がテキスト層に載り、`@page` の MarginBox として判定できるかを確かめる。
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.probe_weasy import (  # noqa: E402
    PX_TO_PT,
    Result,
    render,
    walk_boxes,
)

#: 本番の抽出器（`keiyaku/layout/extract.py` の `_walk`）が bbox の対象から外す box 種別。
#: probe もここを揃えないと「1 要素が 3 断片に見える」という実際には起きない結果になる。
_NOT_A_FRAGMENT = ("TextBox", "LineBox")


def production_fragments(document) -> dict[str, list[tuple[int, tuple[float, float, float, float], str]]]:
    """本番の抽出器と同じ規則で id → 断片を集める。

    - `TextBox` / `LineBox` は除く（本番の除外規則）
    - 同じ `(id, page, x, y)` は 1 つに畳む（本番の重複除去）
    """
    out: dict[str, list[tuple[int, tuple[float, float, float, float], str]]] = {}
    for page_number, box in walk_boxes(document):
        element = getattr(box, "element", None)
        if element is None or not hasattr(element, "get"):
            continue
        element_id = element.get("id")
        kind = type(box).__name__
        if not element_id or kind in _NOT_A_FRAGMENT:
            continue
        x = box.border_box_x() * PX_TO_PT
        y = box.border_box_y() * PX_TO_PT
        bbox = (x, y, x + box.border_width() * PX_TO_PT, y + box.border_height() * PX_TO_PT)
        got = out.setdefault(element_id, [])
        if not any(p == page_number and abs(b[0] - x) < 0.01 and abs(b[1] - y) < 0.01 for p, b, _ in got):
            got.append((page_number, bbox, kind))
    return out


# --- 1. 記名押印欄の「印」丸枠 -------------------------------------------------

#: 「印」の丸枠。border-radius の円の中に文字を置く。画像は使わない。
SEAL_CSS = """
.seal {
  display: inline-block;
  width: 12mm; height: 12mm;
  border: 0.4pt solid #000;
  border-radius: 50%;
  text-align: center;
  line-height: 12mm;
  font-size: 8pt;
}
.sig-line { margin: 0 0 2mm 0; }
"""


def probe_seal() -> list[Result]:
    body = """
    <div id="sig">
      <p id="sig_close" class="sig-line">本契約の成立を証するため、本書２通を作成する。</p>
      <p id="sig_date" class="sig-line">２０２６年４月１日</p>
      <div id="sig_a">
        <p id="sig_a_addr" class="sig-line">住所　東京都千代田区丸窓町一丁目1番1号</p>
        <p id="sig_a_name" class="sig-line">名称　株式会社青葉システムズ</p>
        <p id="sig_a_rep" class="sig-line">代表取締役　相馬　和之
          <span id="sig_a_seal" class="seal">印</span></p>
      </div>
    </div>"""
    doc = render(body, SEAL_CSS)
    found = production_fragments(doc)

    seal = found.get("sig_a_seal", [])
    rep = found.get("sig_a_rep", [])
    results = [
        Result(
            "印: 丸枠が 1 要素の box として取れる",
            len(seal) == 1,
            f"sig_a_seal の断片 = {len(seal)} 個（box 種別 {[k for _p, _b, k in seal]}）",
            [
                f"bbox(pt) = {tuple(round(v, 1) for v in seal[0][1])}" if seal else "box が無い",
                "inline-block は InlineBlockBox / LineBox / TextBox の 3 box を作るが、"
                "本番は後者 2 つを除外するので 1 断片になる",
            ],
        )
    ]
    if seal and rep:
        sx0, sy0, sx1, sy1 = seal[0][1]
        rx0, ry0, rx1, ry1 = rep[0][1]
        inside = rx0 <= sx0 and sx1 <= rx1 + 0.5 and ry0 - 0.5 <= sy0 and sy1 <= ry1 + 0.5
        results.append(
            Result(
                "印: 丸枠が代表者行の内側に収まる",
                inside,
                f"seal={tuple(round(v, 1) for v in seal[0][1])} / "
                f"rep={tuple(round(v, 1) for v in rep[0][1])}",
                [
                    "収まっていれば行の高さが 12mm に押し広げられている（想定どおり）"
                    if inside
                    else "行からはみ出す → 枠の寸法か line-height を見直す"
                ],
            )
        )
        results.append(
            Result(
                "印: 丸枠は正方形（円に見える）",
                abs((sx1 - sx0) - (sy1 - sy0)) < 0.5,
                f"幅 {sx1 - sx0:.1f}pt × 高さ {sy1 - sy0:.1f}pt",
            )
        )

    # テキスト層に「印」の文字が載るか（読み取り正解に含めるため）
    text = _text_layer(doc)
    results.append(
        Result(
            "印: 文字がテキスト層に載る",
            "印" in text,
            f"テキスト層に「印」{'あり' if '印' in text else 'なし'}",
            ["丸枠は border なので、文字だけがテキスト層に出るのが正しい"],
        )
    )
    return results


# --- 2. signature_layout: horizontal -----------------------------------------

HORIZONTAL_CSS = (
    SEAL_CSS
    + """
.sig-row { display: flex; gap: 8mm; }
.sig-col { flex: 1 1 0; }
"""
)


def _sig_block(key: str, name: str) -> str:
    return f"""
      <div id="sig_{key}" class="sig-col">
        <p id="sig_{key}_addr" class="sig-line">住所　架空の住所{key}</p>
        <p id="sig_{key}_name" class="sig-line">名称　{name}</p>
        <p id="sig_{key}_rep" class="sig-line">代表者　氏名{key}
          <span id="sig_{key}_seal" class="seal">印</span></p>
      </div>"""


def probe_signature_layout() -> list[Result]:
    horizontal = (
        '<div id="sig_row" class="sig-row">'
        + _sig_block("a", "株式会社青葉システムズ")
        + _sig_block("b", "みなと技研株式会社")
        + "</div>"
    )
    doc = render(horizontal, HORIZONTAL_CSS)
    found = production_fragments(doc)

    a = found.get("sig_a", [])
    b = found.get("sig_b", [])
    results: list[Result] = []
    if a and b:
        ax0, ay0, _ax1, _ay1 = a[0][1]
        bx0, by0, _bx1, _by1 = b[0][1]
        results.append(
            Result(
                "横並び: flex で 2 者が左右に並ぶ",
                ax0 < bx0 and abs(ay0 - by0) < 1.0,
                f"甲 x0={ax0:.1f} / 乙 x0={bx0:.1f}（y0 差 {abs(ay0 - by0):.2f}pt）",
            )
        )
    else:
        results.append(Result("横並び: flex で 2 者が左右に並ぶ", False, "box が取れない"))

    # 読み順：行の並びではなく「左→右」で取れるか。LineBox の x0 で判定する
    order = _line_order(doc)
    a_first = [t for t in order if "架空の住所a" in t]
    b_first = [t for t in order if "架空の住所b" in t]
    if a_first and b_first:
        results.append(
            Result(
                "横並び: 読み順が左→右になる",
                order.index(a_first[0]) < order.index(b_first[0]),
                f"文書順の並び: {[t[:12] for t in order[:6]]}",
                [
                    "flex の視覚順と文書順が一致（DOM 順が左→右）。"
                    "reading_order は文書順で組むので、段組と違う扱いは要らない"
                ],
            )
        )

    # 縦並びとの比較（既定の vertical）
    vertical = _sig_block("c", "株式会社青葉システムズ") + _sig_block("d", "みなと技研株式会社")
    doc2 = render(vertical, SEAL_CSS)
    found2 = production_fragments(doc2)
    c, d = found2.get("sig_c", []), found2.get("sig_d", [])
    if c and d:
        results.append(
            Result(
                "縦並び: 2 者が上下に並ぶ（既定）",
                c[0][1][1] < d[0][1][1],
                f"丙 y0={c[0][1][1]:.1f} / 丁 y0={d[0][1][1]:.1f}",
            )
        )
    return results


# --- 3. `- 1 -` 型フッタ -------------------------------------------------------

DASHED_CSS = """
@page {
  @bottom-center {
    content: "− " counter(page) " −";
    font-family: 'Noto Serif JP', serif;
    font-size: 8.5pt;
  }
}
"""


def probe_dashed_footer() -> list[Result]:
    filler = "<p id='p%d'>契約書の本文を検証のために並べた段落である。</p>"
    body = "".join(filler % i for i in range(60))
    doc = render(body, DASHED_CSS)

    # MarginBox の at_keyword でフッタを判定できるか（y 座標では判定しない規約）
    margin_boxes: list[tuple[int, str, str]] = []
    for page_number, box in walk_boxes(doc):
        at_keyword = getattr(box, "at_keyword", None)
        if at_keyword:
            text = _box_text(box)
            margin_boxes.append((page_number, at_keyword, text))

    results = [
        Result(
            "フッタ: MarginBox の at_keyword で判定できる",
            any(k == "@bottom-center" for _p, k, _t in margin_boxes),
            f"MarginBox {len(margin_boxes)} 個: {sorted({k for _p, k, _t in margin_boxes})}",
        )
    ]
    texts = [t for _p, k, t in margin_boxes if k == "@bottom-center"]
    results.append(
        Result(
            "フッタ: `− N −` の形で出る",
            bool(texts) and texts[0].strip().startswith("−") and texts[0].strip().endswith("−"),
            f"1 ページ目のフッタ = {texts[0]!r}" if texts else "フッタが無い",
            [f"2 ページ目 = {texts[1]!r}" if len(texts) > 1 else "1 ページしか無い"],
        )
    )
    text = _text_layer(doc)
    results.append(
        Result(
            "フッタ: ページ番号がテキスト層に載る",
            "− 1 −" in text.replace("  ", " ") or "−1−" in text.replace(" ", ""),
            "テキスト層にダッシュ付きページ番号が見つかった" if "−" in text else "テキスト層にダッシュが無い",
            ["往復比較では header/footer として除外する（docs/rendering.md §5）"],
        )
    )
    return results


# --- 補助 ---------------------------------------------------------------------


def _box_text(box) -> str:
    out: list[str] = []

    def visit(b) -> None:
        if hasattr(b, "text") and isinstance(getattr(b, "text", None), str):
            out.append(b.text)
        for child in getattr(b, "children", []):
            visit(child)

    visit(box)
    return "".join(out)


def _line_order(doc) -> list[str]:
    """LineBox のテキストを文書順に返す。"""
    out: list[str] = []
    for _page, box in walk_boxes(doc):
        if type(box).__name__ == "LineBox":
            text = _box_text(box).strip()
            if text:
                out.append(text)
    return out


def _text_layer(doc) -> str:
    """PDF のテキスト層（pdfplumber で抽出）。"""
    import io

    import pdfplumber

    buffer = io.BytesIO()
    doc.write_pdf(target=buffer)
    buffer.seek(0)
    with pdfplumber.open(buffer) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


PROBES = (
    ("記名押印欄の「印」丸枠", probe_seal),
    ("signature_layout: horizontal", probe_signature_layout),
    ("`− N −` 型フッタ（page_number: dashed）", probe_dashed_footer),
)


def main() -> int:
    from rich.console import Console
    from rich.table import Table

    console = Console()
    all_ok = True
    for title, probe in PROBES:
        console.print(f"\n[bold]{title}[/bold]")
        table = Table(show_header=True, header_style="bold")
        table.add_column("判定", justify="center")
        table.add_column("検査", justify="left")
        table.add_column("実測", justify="left")
        for result in probe():
            mark = "OK" if result.ok else ("—" if result.ok is None else "NG")
            color = {"OK": "green", "NG": "red", "—": "yellow"}[mark]
            if result.ok is False:
                all_ok = False
            table.add_row(f"[{color}]{mark}[/{color}]", result.name, result.summary)
            for note in result.notes:
                table.add_row("", "", f"[dim]{note}[/dim]")
        console.print(table)
    console.print(
        "\n[green]すべて OK[/green]" if all_ok else "\n[red]NG がある。設計を確定する前に対処する[/red]"
    )
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
