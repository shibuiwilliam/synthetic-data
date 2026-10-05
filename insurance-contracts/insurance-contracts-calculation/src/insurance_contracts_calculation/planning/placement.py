"""追加する場所の決定と、前付けの索引への反映（DESIGN.md §8.5）。

| 配置 | 内容 | 難しさ |
|---|---|---|
| `article` | 関連する章の末尾に条を足す | 低 |
| `appendix` | 参照表を別表に置き、本文から `{ref:}` で指す | 中 |
| `rider` | 特約として足す（条は第1条から始まる） | 中 |

目次は本体が本文から作るので手を入れない。**目的別もくじ・特約一覧は手書きの表**なので、
足した条を載せるには行の追加が要る（`DESIGN.md` §8.5）。
"""

from __future__ import annotations

import random
from collections.abc import Sequence
from dataclasses import dataclass

from ..patterns.base import RuleDraft
from ..realize import patch as patch_ops

#: 目的別もくじの「こんなときは」欄に書く言い回し
PURPOSE_PHRASE = "{benefit}がどのような場合に支払われるか知りたい"


@dataclass
class Placement:
    """1 つのルール群をどこに置くか。"""

    kind: str  # article / appendix / rider
    article_id: str
    #: 条を足す親（章のID、または特約のID）
    parent_id: str | None
    #: 本文から参照する別表（`appendix` のときだけ）
    appendix_id: str | None = None
    #: 足す特約（`rider` のときだけ）
    rider_id: str | None = None
    rider_title: str = ""
    #: 但し書き（端数処理・下限0）の行き先。`paragraph`（次の項）／`footnote`（条末脚注）／
    #: `article`（別の条。本文からは `{ref:}` で指す）。分散の軸（DESIGN.md §8.5）
    proviso: str = "paragraph"
    #: 但し書きを置く条のID（`proviso == "article"` のときだけ）
    proviso_article_id: str | None = None

    @property
    def footnote(self) -> bool:
        """但し書きを条末脚注に割るか。"""
        return self.proviso == "footnote"

    @property
    def table_where(self) -> str:
        """表の在りか。本文の文型が「下表」と書くか「別表◯」と書くかを決める。"""
        return f"{{ref:{self.appendix_id}}}" if self.appendix_id else "下表"


#: 表を持つルールを分散させるとき、別表に分ける割合（残りは特約にする）。
#: 別表は「本文から離れた表を引く」という読み取りの難しさを作るので、やや多めにする。
APPENDIX_SHARE = 0.65


#: 分散させるとき、但し書きを条末脚注に置く割合（残りは別の条に置く）。
#: 脚注のほうを多めにする。別の条に分けると条が 1 本増え、ページの予算を食うためである。
FOOTNOTE_SHARE = 0.6


def choose_proviso(drafts: Sequence[RuleDraft], rng: random.Random, scatter: float) -> str:
    """但し書きの行き先を選ぶ。`paragraph` / `footnote` / `article`。

    `article`（別の条に分ける）が DESIGN.md §8.5 の「分散」で、根拠が条をまたぐので最も難しい。

    行き先を持てるのは、別の項に送る但し書き（端数処理・下限0）があるルールだけである。
    **群のどれか 1 つでも但し書きを持てばよい**（以前は先頭のルールだけを見ていたため、
    判定のルールが先頭に来る群は分散しなかった）。分散させる割合は `choose()` と同じく
    `scatter` そのものにする（かつて `scatter × 0.5` にしていたのは二重の割り引きだった）。
    """
    if not _has_proviso(drafts):
        return "paragraph"
    if rng.random() >= scatter:
        return "paragraph"
    return "footnote" if rng.random() < FOOTNOTE_SHARE else "article"


def _has_proviso(drafts: Sequence[RuleDraft]) -> bool:
    return any(s.hint.get("own_paragraph") for d in drafts for s in d.steps)


def choose(draft: RuleDraft, rng: random.Random, scatter: float, can_rider: bool) -> str:
    """配置を選ぶ。`scatter` はプロファイルが決める分散の割合（DESIGN.md §9.2）。"""
    if rng.random() >= scatter:
        return "article"
    has_table = draft.table is not None
    if has_table and (not can_rider or rng.random() < APPENDIX_SHARE):
        return "appendix"
    return "rider" if can_rider else "article"


def appendix_node(
    appendix_id: str,
    title: str,
    section_title: str,
    kind_label: str | None,
    table_block: dict,
    lead: str,
) -> dict:
    """別表のノード（本体と同じ形: appendix → appendix_section → paragraph → 表）。

    別表の見出しと節の見出しは変える（既定の約款もそうなっている。
    例: 「別表1 後遺障害等級表」の中が「第1 等級と支払割合」）。
    """
    from ..realize import blocks as bk

    section = bk.node(
        f"{appendix_id}_s1",
        "appendix_section",
        title=section_title,
        children=[bk.node(f"{appendix_id}_s1_p1", "paragraph", text=lead, blocks=[table_block])],
    )
    return bk.node(appendix_id, "appendix", title=title, children=[section], kind_label=kind_label)


def rider_node(rider_id: str, title: str, scope_article: dict, body_articles: list[dict]) -> dict:
    """特約のノード。条は特約ごとに第1条から始まる（本体の `rider` 種別）。"""
    from ..realize import blocks as bk

    return bk.node(rider_id, "rider", title=title, children=[scope_article, *body_articles])


def index_rows(
    data: dict,
    drafts: list[RuleDraft],
    article_ids: list[str],
    chapters: list[str] | None = None,
) -> list[dict]:
    """目的別もくじに足す行（表が無ければ何も足さない）。"""
    fm = data.get("front_matter") or {}
    table = fm.get("purpose_index")
    if not isinstance(table, dict) or table.get("type") != "table":
        return []
    header = [c.get("text", "") for c in table["grid"][0]]
    out = []
    titles = chapters or [_chapter_title(data, aid) for aid in article_ids]
    for draft, aid, chapter in zip(drafts, article_ids, titles, strict=True):
        row = []
        for i, _name in enumerate(header):
            if i == 0:
                row.append(PURPOSE_PHRASE.format(benefit=draft.benefit))
            elif i == len(header) - 1:
                row.append(f"{{ref:{aid}}}")
            else:
                row.append(f"{chapter} {draft.benefit}".strip())
        out.append(patch_ops.add_index_row("front_matter.purpose_index", row))
    return out


def rider_index_rows(data: dict, placements: list[Placement], drafts: list[RuleDraft]) -> list[dict]:
    """特約一覧に足す行（表が無ければ何も足さない）。

    欄の名前は文書によって違うので、既定の約款の 1 行目を写して埋める。
    """
    fm = data.get("front_matter") or {}
    table = fm.get("rider_index")
    if not isinstance(table, dict) or table.get("type") != "table" or len(table["grid"]) < 2:
        return []
    sample = [c.get("text", "") for c in table["grid"][1]]
    out = []
    for place, draft in zip(placements, drafts, strict=True):
        if place.kind != "rider":
            continue
        row = list(sample)
        row[0] = place.rider_title
        if len(row) > 2:
            row[2] = draft.benefit
        out.append(patch_ops.add_index_row("front_matter.rider_index", row))
    return out


def _chapter_title(data: dict, article_id: str) -> str:
    for ch in patch_ops.chapters(data):
        if any(c["id"] == article_id for c in ch.get("children") or []):
            return ch.get("title") or ""
    return ""
