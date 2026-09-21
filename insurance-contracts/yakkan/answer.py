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


def _repeated_cell_ids(layout: Layout) -> dict[int, set[str]]:
    """ページごとの「繰り返し表頭として描かれたセル」の id。

    同じセルが複数ページに出るとき、最初のページ以外は繰り返し表頭とみなす。
    `ElementFragment.repeated` が立っているものに加え、同一 id が複数ページに
    現れる場合の 2 ページ目以降も対象にする。
    """
    out: dict[int, set[str]] = {page.number: set() for page in layout.pages}
    for element_id, element in layout.elements.items():
        pages = sorted({f.page for f in element.fragments})
        if len(pages) <= 1:
            continue
        first = pages[0]
        for fragment in element.fragments:
            if fragment.repeated or fragment.page != first:
                out.setdefault(fragment.page, set()).add(element_id)
    return out


def _page_texts(layout: Layout) -> list[AnswerPage]:
    repeated = _repeated_cell_ids(layout)
    pages: list[AnswerPage] = []
    for page in layout.pages:
        skip = repeated.get(page.number, set())
        body_parts: list[str] = []
        all_parts: list[str] = []
        for line in page.text_lines:
            all_parts.append(line.text)
            if line.region not in BODY_REGIONS:
                continue
            if line.element_id and line.element_id in skip:
                continue  # 繰り返し表頭は 1 回だけ数える
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
