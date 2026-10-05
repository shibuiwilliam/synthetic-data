"""評価用 QA の自動生成（CLAUDE.md §9、docs/schema.md §5.9）。

`answer.json`（source ＋ layout ＋ 派生）だけを入力にして、**答えが機械的に一意に決まる**
問いを作る。答えの根拠は必ず `evidence`（要素 id）で示し、`page_hint` に描画ページを入れる。

10 種別：

| type | 問いの形 | 答えの出どころ |
|---|---|---|
| `locate` | 「…は何ページにありますか」 | `layout.elements[].fragments[].page` |
| `extract` | 「…の見出しは何ですか」「…の(1)には何と書かれていますか」 | `derived.plain_text` |
| `definition` | 「『…』とは何ですか」 | 定義表のセル |
| `table_lookup` | 「表Nの行A・列Bの値は」 | `derived.tables[].header_path` |
| `table_reason` | 「表Nで…が最も大きいのはどれですか」 | 数値列の比較 |
| `figure_path` | 「図Nで『X』の次は何ですか」 | `derived.figures[].paths` / diagram の辺 |
| `figure_fact` | 「次の記述は図Nと合っていますか」 | `figure.facts` |
| `crossref` | 「…が参照しているのはどの条ですか」 | `derived.refs` |
| `count` | 「第N章には条がいくつありますか」 | ツリー |
| `negative` | 「第99条はありますか」「表Nに行Xはありますか」 | 存在しないもの |

**種別の偏りを避ける**：まず種別ごとに候補を作り、種別を順に回しながら 1 問ずつ取る
（`_round_robin`）。候補が尽きた種別は飛ばすので、materialize できる種別が少ない文書
（図が 1 点しかない定款など）でも 30 問に届く。
"""

from __future__ import annotations

import random
import re
from collections.abc import Iterator
from typing import Any

from keiyaku.models import QA, Answer, Figure, QASet, Table

#: 1 文書あたりの既定の生成数（CLAUDE.md §15）
DEFAULT_COUNT = 30

#: 数値として比較できるセルか（「１００％」「3,000円」「20日」など）
_NUMERIC = re.compile(r"^[^\d０-９]*([\d０-９][\d０-９,，.．]*)\s*(％|%|円|日|年|月|倍|等級|万円)?")

_ZEN = str.maketrans("０１２３４５６７８９，．", "0123456789,.")


def _as_number(text: str) -> float | None:
    """セルの文字列から比較用の数値を取り出す。取れなければ None。"""
    match = _NUMERIC.match(text.strip())
    if not match:
        return None
    body = match.group(1).translate(_ZEN).replace(",", "")
    try:
        return float(body)
    except ValueError:
        return None


def _iter_blocks(answer: Answer) -> Iterator[tuple[Any, str]]:
    """source の全ブロックを (block, 所属ノード id) で返す。"""

    def walk(obj: Any, owner: str) -> Iterator[tuple[Any, str]]:
        if isinstance(obj, list):
            for item in obj:
                yield from walk(item, owner)
            return
        node_id = getattr(obj, "id", None)
        kind = getattr(obj, "kind", None)
        if kind is not None and isinstance(node_id, str):
            owner = node_id
        for block in getattr(obj, "blocks", None) or []:
            yield block, owner
            yield from walk(block, owner)
        for child in getattr(obj, "children", None) or []:
            yield from walk(child, owner)

    yield from walk(answer.source.body, "")
    yield from walk(answer.source.appendices, "")
    front = answer.source.front_matter
    for name in ("preface",):
        value = getattr(front, name, None)
        if value:
            yield from walk(value, "front_matter")


def _page_of(answer: Answer, element_id: str) -> list[int]:
    element = answer.layout.elements.get(element_id)
    if element is None:
        return []
    return sorted({f.page for f in element.fragments})


def _plain(answer: Answer, element_id: str, *, with_label: bool = False) -> str | None:
    entry = answer.source.derived.plain_text.get(element_id)
    if entry is None:
        return None
    return entry.with_label if with_label else entry.without_label


def _drawn(answer: Answer, element_id: str) -> bool:
    """描画されている要素か（evidence は必ず PDF 上に存在するものにする）。"""
    return element_id in answer.layout.elements


# --- 種別ごとの候補づくり ----------------------------------------------------


def _locate(answer: Answer) -> list[QA]:
    out: list[QA] = []
    for entry in answer.outline:
        if entry.page <= 0 or not entry.heading_text:
            continue
        out.append(
            QA(
                id="",
                type="locate",
                question=f"「{entry.heading_text}」は何ページにありますか。",
                answer=float(entry.page),
                answer_type="number",
                evidence=[entry.id],
                page_hint=[entry.page],
                source="auto",
            )
        )
    return out


def _extract(answer: Answer) -> list[QA]:
    out: list[QA] = []
    labels = answer.source.derived.labels
    for node_id, info in labels.items():
        if not _drawn(answer, node_id):
            continue
        # 条の見出し文言
        if info.title and info.label and info.label.endswith("条"):
            out.append(
                QA(
                    id="",
                    type="extract",
                    question=f"{info.label}の見出しは何ですか。",
                    answer=info.title,
                    answer_type="string",
                    evidence=[node_id],
                    page_hint=_page_of(answer, node_id),
                    source="auto",
                )
            )
    # 項の本文をそのまま問う（ラベルを含まない平文が答え）
    for node_id, info in labels.items():
        if info.label and re.fullmatch(r"[（(][0-9０-９]+[）)]|[0-9０-９]+．", info.label or ""):
            text = _plain(answer, node_id)
            if text and 20 <= len(text) <= 120 and _drawn(answer, node_id):
                parent = info.path[-1] if info.path else ""
                where = f"{parent}の{info.label}" if parent else info.label
                out.append(
                    QA(
                        id="",
                        type="extract",
                        question=f"{where}には何と書かれていますか。",
                        answer=text,
                        answer_type="string",
                        evidence=[node_id],
                        page_hint=_page_of(answer, node_id),
                        source="auto",
                    )
                )
    return out


def _definition_table(answer: Answer) -> Table | None:
    for block, _owner in _iter_blocks(answer):
        if isinstance(block, Table) and block.semantic_type == "definitions":
            return block
    return None


def _term_of(row_headers: list[str]) -> str:
    """定義表の行見出しから用語を選ぶ。

    五十音インデックス列（「ア」「カ」…の 1 文字）は見出しの見出しであって用語ではないので、
    それを避けて最も長いものを採る。すべてが 1 文字なら用語が取れていないので空を返す。
    """
    candidates = [h for h in row_headers if len(h) > 1]
    if not candidates:
        return ""
    return max(candidates, key=len)


def _definition(answer: Answer) -> list[QA]:
    """定義表から「『X』とは何ですか」を作る。

    用語の列は `header_cols` の外（`role: "stub"` の本文セル）にあることが多いので、
    `header_path` ではなく **grid を直接読む**。列見出しに「用語」「定義」を含む列を探し、
    同じ行のセルを対にする。
    """
    table = _definition_table(answer)
    if table is None or not table.grid:
        return []
    header = [(_cell_text(answer, c), i) for i, c in enumerate(table.grid[0])]
    term_col = next((i for text, i in header if "用語" in text), None)
    def_col = next((i for text, i in header if "定義" in text), None)
    if term_col is None or def_col is None:
        return []
    out: list[QA] = []
    for row in table.grid[1:]:
        if len(row) <= max(term_col, def_col):
            continue
        term = _cell_text(answer, row[term_col])
        cell = row[def_col]
        text = _plain(answer, getattr(cell, "id", "") or "")
        cell_id = getattr(cell, "id", "") or ""
        if not term or not text or not _drawn(answer, cell_id):
            continue
        out.append(
            QA(
                id="",
                type="definition",
                question=f"この契約書において「{term}」とは何ですか。",
                answer=text,
                answer_type="string",
                evidence=[cell_id],
                page_hint=_page_of(answer, cell_id),
                source="auto",
            )
        )
    return out


def _cell_text(answer: Answer, cell: Any) -> str:
    """セルの平文。結合セル（MergedCell）は文字列を持たないので空を返す。"""
    cell_id = getattr(cell, "id", None)
    if not isinstance(cell_id, str):
        return ""
    return _plain(answer, cell_id) or getattr(cell, "text", "") or ""


def _table_lookup(answer: Answer) -> list[QA]:
    out: list[QA] = []
    definitions = _definition_table(answer)
    skip = definitions.id if definitions else None
    for table_id, derived in answer.source.derived.tables.items():
        if table_id == skip:
            continue  # 定義表は definition 側で扱う
        caption = _plain(answer, f"{table_id}__caption") or ""
        label = derived.caption_label or ""
        for cell_id, path in derived.header_path.items():
            if not path.row_headers or not path.col_headers:
                continue
            text = _plain(answer, cell_id)
            if not text or not _drawn(answer, cell_id) or len(text) > 80:
                continue
            row = "・".join(path.row_headers)
            col = "・".join(path.col_headers)
            where = f"{label}「{caption}」" if caption else label or table_id
            out.append(
                QA(
                    id="",
                    type="table_lookup",
                    question=f"{where}で、「{row}」の「{col}」は何ですか。",
                    answer=text,
                    answer_type="string",
                    evidence=[cell_id],
                    page_hint=_page_of(answer, cell_id),
                    source="auto",
                )
            )
    return out


def _table_reason(answer: Answer) -> list[QA]:
    """数値列の最大・最小を問う（表を読んだうえで比較する必要がある）。"""
    out: list[QA] = []
    for table_id, derived in answer.source.derived.tables.items():
        caption = _plain(answer, f"{table_id}__caption") or ""
        label = derived.caption_label or ""
        # 列見出しごとに (行見出し, 数値, セルid) を集める
        by_col: dict[str, list[tuple[str, float, str]]] = {}
        for cell_id, path in derived.header_path.items():
            if not path.row_headers or not path.col_headers:
                continue
            text = _plain(answer, cell_id)
            if text is None or not _drawn(answer, cell_id):
                continue
            value = _as_number(text)
            if value is None:
                continue
            by_col.setdefault("・".join(path.col_headers), []).append(
                ("・".join(path.row_headers), value, cell_id)
            )
        for col, rows in by_col.items():
            if len(rows) < 3:
                continue
            values = [v for _r, v, _c in rows]
            if len(set(values)) < len(values):
                continue  # 同値があると答えが一意にならない
            where = f"{label}「{caption}」" if caption else label or table_id
            top = max(rows, key=lambda r: r[1])
            bottom = min(rows, key=lambda r: r[1])
            for extreme, word in ((top, "最も大きい"), (bottom, "最も小さい")):
                out.append(
                    QA(
                        id="",
                        type="table_reason",
                        question=(
                            f"{where}で、「{col}」が{word}のはどの行ですか。行の見出しで答えてください。"
                        ),
                        answer=extreme[0],
                        answer_type="string",
                        evidence=[extreme[2]],
                        page_hint=_page_of(answer, extreme[2]),
                        source="auto",
                    )
                )
            # 2 行を比べる（表を引いたうえで大小を判断する必要がある）
            ordered = sorted(rows, key=lambda r: r[1])
            for a, b in zip(ordered, ordered[1:], strict=False):
                out.append(
                    QA(
                        id="",
                        type="table_reason",
                        question=(f"{where}で、「{a[0]}」と「{b[0]}」では「{col}」はどちらが大きいですか。"),
                        answer=b[0],
                        answer_type="string",
                        evidence=[a[2], b[2]],
                        page_hint=sorted(set(_page_of(answer, a[2]) + _page_of(answer, b[2]))),
                        source="auto",
                    )
                )
    return out


def _figures(answer: Answer) -> list[tuple[Figure, str]]:
    """図はトークンを解決してから使う。`facts` もラベルも QA の答えそのものなので、
    生の `{const:...}` を残すと問いと答えが壊れる（docs/shared_fixes.md A2）。"""
    from keiyaku.build import resolve_strings

    figures = answer.source.derived.figures
    out: list[tuple[Figure, str]] = []
    for block, owner in _iter_blocks(answer):
        if not isinstance(block, Figure):
            continue
        derived = figures.get(block.id)
        out.append((resolve_strings(block, derived.resolved_labels if derived else {}), owner))
    return out


def _node_labels(figure: Figure) -> dict[str, str]:
    """diagram のノード id → 表示ラベル。"""
    labels: dict[str, str] = {}

    def walk(obj: Any) -> None:
        if isinstance(obj, list):
            for item in obj:
                walk(item)
            return
        node_id = getattr(obj, "id", None)
        label = getattr(obj, "label", None) or getattr(obj, "text", None)
        if isinstance(node_id, str) and isinstance(label, str) and label:
            labels.setdefault(node_id, label)
        for name in ("nodes", "children", "steps", "events", "spans", "rows", "cols", "fields"):
            value = getattr(obj, name, None)
            if value:
                walk(value)

    walk(figure.diagram)
    return labels


def _figure_path(answer: Answer) -> list[QA]:
    out: list[QA] = []
    for figure, _owner in _figures(answer):
        derived = answer.source.derived.figures.get(figure.id)
        if derived is None:
            continue
        caption = _plain(answer, f"{figure.id}__caption") or ""
        label = derived.caption_label or figure.id
        where = f"{label}「{caption}」" if caption else label
        labels = _node_labels(figure)
        # 1) flowchart：開始から終了までの経路
        for path in derived.paths[:2]:
            names = [labels.get(n, n) for n in path]
            if len(names) < 2:
                continue
            out.append(
                QA(
                    id="",
                    type="figure_path",
                    question=f"{where}で、開始から終了までの経路を順に挙げてください。",
                    answer=names,
                    answer_type="list",
                    evidence=[figure.id],
                    page_hint=_page_of(answer, figure.id),
                    source="auto",
                )
            )
        # 2) 隣接：**順序に意味がある図だけ**で「次は何か」を聞く。
        #    timeline は複数のレーンを重ねるので node_order の隣接は意味を持たない
        #    （「10等級」の次が別レーンの「責任開始」になってしまう）。
        kind = getattr(figure.diagram, "kind", "")
        if kind == "steps":
            steps = list(getattr(figure.diagram, "steps", []))
            for a, b in zip(steps, steps[1:], strict=False):
                out.append(
                    QA(
                        id="",
                        type="figure_path",
                        question=f"{where}で、「{a.title}」の次の手順は何ですか。",
                        answer=b.title,
                        answer_type="string",
                        evidence=[figure.id],
                        page_hint=_page_of(answer, figure.id),
                        source="auto",
                    )
                )
        elif kind == "flowchart":
            nodes = {n.id: n.label for n in getattr(figure.diagram, "nodes", [])}
            for edge in getattr(figure.diagram, "edges", []):
                if edge.from_ not in nodes or edge.to not in nodes:
                    continue
                cond = f"（{edge.label}の場合）" if getattr(edge, "label", None) else ""
                out.append(
                    QA(
                        id="",
                        type="figure_path",
                        question=f"{where}で、「{nodes[edge.from_]}」の次{cond}は何ですか。",
                        answer=nodes[edge.to],
                        answer_type="string",
                        evidence=[figure.id],
                        page_hint=_page_of(answer, figure.id),
                        source="auto",
                    )
                )
        elif kind == "tree":
            root = getattr(figure.diagram, "root", None)
            for parent in _tree_nodes(root):
                if not parent.children:
                    continue
                out.append(
                    QA(
                        id="",
                        type="figure_path",
                        question=f"{where}で、「{parent.label}」の下にあるものをすべて挙げてください。",
                        answer=[c.label for c in parent.children],
                        answer_type="list",
                        evidence=[figure.id],
                        page_hint=_page_of(answer, figure.id),
                        source="auto",
                    )
                )
        elif kind == "timeline":
            spans = list(getattr(figure.diagram, "spans", []))
            for span in spans:
                label_text = getattr(span, "label", None)
                if not label_text:
                    continue
                out.append(
                    QA(
                        id="",
                        type="figure_path",
                        question=f"{where}で、「{label_text}」はどの区間を指していますか。始点と終点で答えてください。",
                        answer=[str(span.from_), str(span.to)],
                        answer_type="list",
                        evidence=[figure.id],
                        page_hint=_page_of(answer, figure.id),
                        source="auto",
                    )
                )
    return out


def _tree_nodes(root: Any) -> list[Any]:
    """tree のノードを深さ優先で列挙する。"""
    if root is None:
        return []
    out = [root]
    for child in getattr(root, "children", []) or []:
        out.extend(_tree_nodes(child))
    return out


def _figure_fact(answer: Answer) -> list[QA]:
    out: list[QA] = []
    for figure, _owner in _figures(answer):
        derived = answer.source.derived.figures.get(figure.id)
        caption = _plain(answer, f"{figure.id}__caption") or ""
        label = (derived.caption_label if derived else None) or figure.id
        where = f"{label}「{caption}」" if caption else label
        for fact in figure.facts:
            out.append(
                QA(
                    id="",
                    type="figure_fact",
                    question=f"{where}について、次の記述は正しいですか。「{fact}」",
                    answer="はい",
                    answer_type="string",
                    evidence=[figure.id],
                    page_hint=_page_of(answer, figure.id),
                    source="auto",
                )
            )
        # 偽の記述も作る。答えが「はい」だけだと、図を読まずに全問正解できてしまう。
        # 機械的に偽と分かる形（実在しない隣接）だけを使い、facts の文をいじらない。
        labels = _node_labels(figure)
        wrong = _wrong_adjacency(figure, labels)
        for source_label, wrong_label in wrong:
            out.append(
                QA(
                    id="",
                    type="figure_fact",
                    question=(
                        f"{where}について、次の記述は正しいですか。"
                        f"「「{source_label}」の次に来るのは「{wrong_label}」である。」"
                    ),
                    answer="いいえ",
                    answer_type="string",
                    evidence=[figure.id],
                    page_hint=_page_of(answer, figure.id),
                    source="auto",
                )
            )
    return out


def _qualified(info: Any, fallback: str) -> str:
    """「(2)」のような裸のラベルに祖先を足して、どこの (2) かを一意にする。"""
    if info is None:
        return fallback
    if info.heading_text and len(info.heading_text) > 4:
        return info.heading_text
    parent = info.path[-1] if info.path else ""
    label = info.label or info.heading_text or fallback
    return f"{parent}の{label}" if parent else label


def _wrong_adjacency(figure: Figure, labels: dict[str, str]) -> list[tuple[str, str]]:
    """図の中に**存在しない**隣接の組を作る（figure_fact の「いいえ」用）。

    実在する辺・手順の並びを集めてから、その補集合から選ぶので、
    偶然正しい記述になることがない。
    """
    kind = getattr(figure.diagram, "kind", "")
    real: set[tuple[str, str]] = set()
    order: list[str] = []
    if kind == "flowchart":
        order = [n.id for n in getattr(figure.diagram, "nodes", [])]
        real = {(e.from_, e.to) for e in getattr(figure.diagram, "edges", [])}
    elif kind == "steps":
        steps = list(getattr(figure.diagram, "steps", []))
        order = [s.id for s in steps]
        real = set(zip(order, order[1:], strict=False))
        labels = {s.id: s.title for s in steps}
    else:
        return []
    out: list[tuple[tuple[str, str], tuple[str, str]]] = []
    for a in order:
        for b in order:
            if a == b or (a, b) in real or (b, a) in real:
                continue
            if a not in labels or b not in labels:
                continue
            out.append(((a, b), (labels[a], labels[b])))
    return [pair for _ids, pair in out]


def _crossref(answer: Answer) -> list[QA]:
    out: list[QA] = []
    labels = answer.source.derived.labels
    for ref in answer.source.derived.refs:
        info = labels.get(ref.from_id)
        target = labels.get(ref.to_id)
        if info is None or target is None or not ref.rendered:
            continue
        if not _drawn(answer, ref.from_id) or not _drawn(answer, ref.to_id):
            continue
        where = _qualified(info, ref.from_id)
        out.append(
            QA(
                id="",
                type="crossref",
                question=f"「{where}」が参照しているのはどこですか。契約書中の表記で答えてください。",
                answer=ref.rendered,
                answer_type="string",
                evidence=[ref.from_id, ref.to_id],
                page_hint=sorted(set(_page_of(answer, ref.from_id) + _page_of(answer, ref.to_id))),
                source="auto",
            )
        )
    return out


def _count(answer: Answer) -> list[QA]:
    out: list[QA] = []

    def walk(nodes: list) -> None:
        for node in nodes:
            info = answer.source.derived.labels.get(node.id)
            children = node.children or []
            articles = [c for c in children if c.kind == "article"]
            if info and articles and _drawn(answer, node.id):
                out.append(
                    QA(
                        id="",
                        type="count",
                        question=f"「{info.heading_text}」には条がいくつありますか。",
                        answer=float(len(articles)),
                        answer_type="number",
                        evidence=[node.id] + [c.id for c in articles],
                        page_hint=_page_of(answer, node.id),
                        source="auto",
                    )
                )
            walk(children)

    walk(answer.source.body)
    walk(answer.source.appendices)
    # 表の行数・図のノード数も count の材料になる
    for table_id, derived in answer.source.derived.tables.items():
        caption = _plain(answer, f"{table_id}__caption")
        rows = {p.row_headers[-1] for p in derived.header_path.values() if p.row_headers}
        if caption and len(rows) >= 2:
            out.append(
                QA(
                    id="",
                    type="count",
                    question=(
                        f"{derived.caption_label or ''}「{caption}」には何行ありますか。"
                        "表頭の行は数えません。"
                    ),
                    answer=float(len(rows)),
                    answer_type="number",
                    evidence=_table_evidence(answer, table_id),
                    page_hint=_table_pages(answer, table_id),
                    source="auto",
                )
            )
    return out


def _table_evidence(answer: Answer, table_id: str) -> list[str]:
    """表の evidence。caption が別ページに落ちることがあるので、あれば caption も入れる。"""
    caption_id = f"{table_id}__caption"
    ids = [table_id]
    if _drawn(answer, caption_id):
        ids.append(caption_id)
    return ids


def _table_pages(answer: Answer, table_id: str) -> list[int]:
    pages = set(_page_of(answer, table_id)) | set(_page_of(answer, f"{table_id}__caption"))
    return sorted(pages)


def _negative(answer: Answer, rng: random.Random) -> list[QA]:
    """存在しないものを問う。答えは常に「いいえ」または「該当なし」。"""
    out: list[QA] = []
    labels = answer.source.derived.labels
    # 1) 存在しない条番号
    chapters = [
        (nid, info)
        for nid, info in labels.items()
        if info.depth == 0 and info.label.endswith("章") and _drawn(answer, nid)
    ]
    for nid, info in chapters:
        node = _find_node(answer, nid)
        count = len([c for c in (node.children or []) if c.kind == "article"]) if node else 0
        if count == 0:
            continue
        missing = count + rng.randint(3, 9)
        out.append(
            QA(
                id="",
                type="negative",
                question=f"「{info.heading_text}」に第{missing}条はありますか。",
                answer="いいえ",
                answer_type="string",
                evidence=[nid],
                page_hint=_page_of(answer, nid),
                source="auto",
            )
        )
    # 2) 表に存在しない行見出し
    for table_id, derived in answer.source.derived.tables.items():
        caption = _plain(answer, f"{table_id}__caption")
        rows = sorted({p.row_headers[-1] for p in derived.header_path.values() if p.row_headers})
        if not caption or len(rows) < 2:
            continue
        bogus = f"{rows[0]}および{rows[-1]}"
        if bogus in rows:
            continue
        out.append(
            QA(
                id="",
                type="negative",
                question=f"{derived.caption_label or ''}「{caption}」に「{bogus}」という行はありますか。",
                answer="いいえ",
                answer_type="string",
                evidence=_table_evidence(answer, table_id),
                page_hint=_table_pages(answer, table_id),
                source="auto",
            )
        )
    return out


def _find_node(answer: Answer, node_id: str) -> Any:
    def walk(nodes: list) -> Any:
        for node in nodes:
            if node.id == node_id:
                return node
            found = walk(node.children or [])
            if found is not None:
                return found
        return None

    return walk(answer.source.body) or walk(answer.source.appendices)


# --- 組み立て ----------------------------------------------------------------


def _round_robin(pools: dict[str, list[QA]], count: int, rng: random.Random) -> list[QA]:
    """種別を順に回しながら 1 問ずつ取る（種別の偏りを避ける）。"""
    for items in pools.values():
        rng.shuffle(items)
    order = sorted(pools)
    picked: list[QA] = []
    seen: set[str] = set()
    while len(picked) < count:
        progressed = False
        for key in order:
            if len(picked) >= count:
                break
            pool = pools[key]
            while pool:
                item = pool.pop()
                if item.question in seen:
                    continue
                seen.add(item.question)
                picked.append(item)
                progressed = True
                break
        if not progressed:
            break  # すべての種別が尽きた
    return picked


def generate(answer: Answer, *, count: int = DEFAULT_COUNT, seed: int = 0) -> QASet:
    """`answer.json` から自動 QA を作る。同じ入力・同じ seed なら同じ結果になる。"""
    rng = random.Random(seed)
    pools: dict[str, list[QA]] = {
        "locate": _locate(answer),
        "extract": _extract(answer),
        "definition": _definition(answer),
        "table_lookup": _table_lookup(answer),
        "table_reason": _table_reason(answer),
        "figure_path": _figure_path(answer),
        "figure_fact": _figure_fact(answer),
        "crossref": _crossref(answer),
        "count": _count(answer),
        "negative": _negative(answer, rng),
    }
    picked = _round_robin(pools, count, rng)
    for index, item in enumerate(picked, start=1):
        item.id = f"qa_auto_{index:03d}"
    return QASet(doc_id=answer.doc_id, items=picked)


def pool_sizes(answer: Answer, *, seed: int = 0) -> dict[str, int]:
    """種別ごとに作れる候補の数（`keiyaku qa --report` 用）。"""
    rng = random.Random(seed)
    return {
        "locate": len(_locate(answer)),
        "extract": len(_extract(answer)),
        "definition": len(_definition(answer)),
        "table_lookup": len(_table_lookup(answer)),
        "table_reason": len(_table_reason(answer)),
        "figure_path": len(_figure_path(answer)),
        "figure_fact": len(_figure_fact(answer)),
        "crossref": len(_crossref(answer)),
        "count": len(_count(answer)),
        "negative": len(_negative(answer, rng)),
    }
