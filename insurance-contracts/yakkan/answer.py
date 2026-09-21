"""`answer.json` の組み立て（docs/schema.md §5.8）。

`source.json`（内容と意味）と `layout.json`（描画結果）を束ね、評価に直接使う派生を足す。

- `pages[].text`：**読み順**の本文。欄外注と表を含み、ヘッダ／フッタとページ番号は含まない。
- `pages[].text_with_furniture`：ヘッダ／フッタも含めた、そのページに実際に出る全文字列。
- `outline[]`：見出しツリー（id・深さ・ラベル・文言・開始ページ）。

繰り返し表頭（`repeated: true`）は `text` に**1 回だけ**入れる。
PDF のテキスト層には各ページに出るが、正解として二重に数えると CER が歪むため
（CLAUDE.md §14「表頭繰り返し・ヘッダ/フッタは PDF テキスト層に同じ文字列が複数回出る」）。
"""

from __future__ import annotations

from yakkan.models import Answer, AnswerPage, Layout, OutlineEntry, Source

#: `pages[].text` に入れる region。図の中の文字は SVG 側にあり text_lines には出ない。
BODY_REGIONS = ("body", "table", "margin_note")


def _repeated_boxes(layout: Layout) -> dict[int, list[tuple[float, float, float, float]]]:
    """ページごとの「繰り返し表頭として描かれた領域」。

    繰り返しは **同じページの中でも起きる**（2 段組で表が段をまたぐと、右段の頭に表頭が再掲される）。
    ページ単位で id を弾くと段内の再掲を取りこぼすので、**fragment の bbox で判定する**。

    判定に使うのは `repeated` フラグだけ。「同じ id が複数ページに出たら 2 ページ目以降は再掲」
    という推測を足すと、ページをまたぐ**容れ物**（章・別表のノード）まで対象になり、
    そのページの中身が丸ごと落ちる（実際に 3 ページ目が空になった）。
    """
    out: dict[int, list[tuple[float, float, float, float]]] = {p.number: [] for p in layout.pages}
    for element in layout.elements.values():
        for fragment in element.fragments:
            if fragment.repeated:
                out.setdefault(fragment.page, []).append(tuple(fragment.bbox))
    return out


def _inside(box: tuple[float, float, float, float], bbox: list[float]) -> bool:
    """行が繰り返し領域の中にあるか（中心点で判定する）。"""
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    return box[0] - 0.5 <= cx <= box[2] + 0.5 and box[1] - 0.5 <= cy <= box[3] + 0.5


def _page_texts(layout: Layout) -> list[AnswerPage]:
    repeated = _repeated_boxes(layout)
    pages: list[AnswerPage] = []
    for page in layout.pages:
        boxes = repeated.get(page.number, [])
        body_parts: list[str] = []
        all_parts: list[str] = []
        for line in page.text_lines:
            all_parts.append(line.text)
            if line.region not in BODY_REGIONS:
                continue
            if any(_inside(box, line.bbox) for box in boxes):
                continue  # 繰り返し表頭は正解として二重に数えない
            body_parts.append(line.text)
        header = page.header.text if page.header else ""
        footer = page.footer.text if page.footer else ""
        body = "".join(body_parts)
        pages.append(
            AnswerPage(
                number=page.number,
                text=body,
                text_with_furniture=header + "".join(all_parts) + footer,
                chars=len(body),
            )
        )
    return pages


def _outline(source: Source, layout: Layout) -> list[OutlineEntry]:
    entries: list[OutlineEntry] = []

    def walk(nodes: list, depth: int) -> None:
        for node in nodes:
            info = source.derived.labels.get(node.id)
            element = layout.elements.get(node.id)
            page = min((f.page for f in element.fragments), default=0) if element else 0
            if info is not None:
                entries.append(
                    OutlineEntry(
                        id=node.id,
                        depth=depth,
                        label=info.label,
                        title=info.title or "",
                        heading_text=info.heading_text,
                        page=page,
                    )
                )
            walk(node.children or [], depth + 1)

    walk(source.body, 0)
    walk(source.appendices, 0)
    return entries


def build_answer(source: Source, layout: Layout) -> Answer:
    """`source` ＋ `layout` → `answer.json` の中身。"""
    return Answer(
        doc_id=layout.doc_id,
        source=source,
        layout=layout,
        pages=_page_texts(layout),
        outline=_outline(source, layout),
    )
