"""検索エンジンの評価セットを作る（docs/eval_dataset_plan.md P8）。

全文検索・ベクトル検索・ハイブリッド・ランク学習のいずれも、必要なのは
**(1) 登録する単位（パッセージ）** と **(2) クエリ** と **(3) 適合判定（qrels）** の 3 つ。
QA は「1 つの答え」を採点するもので、「このクエリにどのパッセージが適合するか」という
多対多の判定ではないので、別に作る。

パッセージの単位：
- **条（article）が 1 パッセージ**。長い条は項ごとに割る（`MAX_CHARS`）。
- **表は 1 表 1 パッセージ**（キャプション＋行ごとの「見出し：値」＋表注）。
- **図は 1 図 1 パッセージ**（キャプション＋ alt ＋ facts）。
- **定義語は定義表の 1 行 1 パッセージ**（項目検索の主役）。
  `defined_terms` は `{term:}` 解決用のメタデータで**描画されていない**ので、
  そのままパッセージにすると紙面に存在しない正解になる（`docs/search_query_plan.md` W4）。
  実際に印字される定義表（`semantic_type: definitions`）の行を単位にし、
  紙面に定義文が出ない語はコーパスに入れない。
- 前付け・奥付など、条に属さない本文も拾う。

適合度（grade）は 3 段階：**2 = 答えがそこにある / 1 = 関連する（同じ条の別の項など） / 0 = 非適合**。
qrels には grade 1 以上だけを書く（書かれていないものは 0）。
"""

from __future__ import annotations

import hashlib
import random
import re
import unicodedata
from collections.abc import Iterable
from typing import Any

from yakkan.export_models import Passage, Qrel, Query
from yakkan.models import Answer, Figure, Table

#: 1 パッセージの目安の長さ。これを超える条は項ごとに割る
MAX_CHARS = 600


def normalize(text: str) -> str:
    return re.sub(r"\s+", "", unicodedata.normalize("NFKC", text))


# --- パッセージ ---------------------------------------------------------------


def _iter_blocks(answer: Answer) -> Iterable[tuple[Any, str]]:
    from yakkan.lint.walk import iter_blocks

    for block, owner_id, _article in iter_blocks(answer.source):
        yield block, owner_id


def _pages_of(answer: Answer, element_ids: list[str]) -> list[int]:
    pages: set[int] = set()
    for element_id in element_ids:
        element = answer.layout.elements.get(element_id)
        if element:
            pages.update(f.page for f in element.fragments)
    return sorted(pages)


def _passage(
    answer: Answer,
    passage_id: str,
    kind: str,
    title: str,
    text: str,
    element_ids: list[str],
    citation: str,
) -> Passage:
    product = answer.source.meta.product_name
    issuer = answer.source.meta.issuer.name
    header = "　／　".join(x for x in (product, issuer, citation) if x)
    return Passage(
        passage_id=f"{answer.doc_id}::{passage_id}",
        doc_id=answer.doc_id,
        content_id=answer.source.content_id,
        genre=answer.source.genre,
        product_name=product,
        issuer=issuer,
        context_header=header,
        kind=kind,
        title=title,
        citation=citation,
        text=text,
        element_ids=element_ids,
        pages=_pages_of(answer, element_ids),
        # qrels の部分適合（grade 1）を機械的に導くための関係。**derived に実在するものだけ**。
        terms_used=sorted(
            {u.term_id for u in answer.source.derived.term_uses if u.in_id in set(element_ids)}
        ),
        refs_to=sorted({r.to_id for r in answer.source.derived.refs if r.from_id in set(element_ids)}),
    )


def _text_of(answer: Answer, element_id: str, *, with_label: bool = True) -> str:
    entry = answer.source.derived.plain_text.get(element_id)
    if entry is None:
        return ""
    return entry.with_label if with_label else entry.without_label


def _table_text(answer: Answer, table: Table) -> str:
    """表を検索できる平文にする。行ごとに「行見出し：セル」を並べる。"""
    derived = answer.source.derived.tables.get(table.id)
    lines: list[str] = []
    if table.caption:
        prefix = f"{derived.caption_label}　" if derived and derived.caption_label else ""
        lines.append(f"{prefix}{table.caption}")
    for row in table.grid:
        cells = [c for c in row if hasattr(c, "id")]
        values = [_text_of(answer, c.id, with_label=False) for c in cells]
        values = [v for v in values if v]
        if values:
            lines.append("　".join(values))
    for i, _note in enumerate(table.notes):
        lines.append(_text_of(answer, f"{table.id}__note{i}", with_label=False))
    return "\n".join(x for x in lines if x)


#: 定義表と判定する `semantic_type`
DEFINITION_TABLE_TYPE = "definitions"


def _definition_rows(answer: Answer) -> Iterable[tuple[Table, int, str, list[str]]]:
    """定義表の行を返す（表・行番号・用語・その行のセル id）。

    用語は行見出し（`role: stub`）のセル、無ければ先頭の本文セルから採る。
    `header_rows` の行は飛ばす。
    """
    for block, _owner_id in _iter_blocks(answer):
        if not isinstance(block, Table) or block.semantic_type != DEFINITION_TABLE_TYPE:
            continue
        header_rows = block.layout.header_rows or 0
        for row_index, row in enumerate(block.grid):
            if row_index < header_rows:
                continue
            cells = [c for c in row if hasattr(c, "id")]
            if len(cells) < 2:
                continue  # 用語と定義の 2 列が無い行は飛ばす
            stubs = [c for c in cells if c.role == "stub"]
            # 行見出しが複数ある表（五十音の索引列＋用語の列）では**最後**が用語
            term_cell = stubs[-1] if stubs else cells[0]
            term = _text_of(answer, term_cell.id, with_label=False).strip()
            if not term:
                continue
            # 用語のセルから後ろを返す。前にあるのは索引列なので定義文ではない
            start = cells.index(term_cell)
            yield block, row_index, term, [c.id for c in cells[start:]]


def _definition_passages(answer: Answer) -> list[Passage]:
    """定義表の行を 1 パッセージにする。

    `defined_terms`（`{term:}` 解決用のメタデータ）は描画されていないので使わない。
    紙面に印字される行だけが検索の単位になる（`docs/search_query_plan.md` W4）。
    """
    derived = answer.source.derived
    out: list[Passage] = []
    for table, row_index, term, cell_ids in _definition_rows(answer):
        # 本文は**定義の列だけ**。五十音の索引列（`ア`・`カ`）は定義文ではないので入れない
        values = [_text_of(answer, cell_id, with_label=False) for cell_id in cell_ids[1:]]
        body = "　".join(v for v in values if v and v != term)
        info = derived.labels.get(_owner_of(answer, table.id) or "")
        out.append(
            _passage(
                answer,
                f"{table.id}__r{row_index}",
                "definition",
                term,
                f"{term}\n{body}",
                cell_ids,
                info.citation if info else "",
            )
        )
    return out


def _owner_of(answer: Answer, block_id: str) -> str | None:
    for block, owner_id in _iter_blocks(answer):
        if getattr(block, "id", None) == block_id:
            return owner_id
    return None


def _figure_text(answer: Answer, figure: Figure) -> str:
    derived = answer.source.derived.figures.get(figure.id)
    labels = derived.resolved_labels if derived else {}

    def resolve(value: str) -> str:
        return labels.get(value, value)

    lines: list[str] = []
    if figure.caption:
        prefix = f"{derived.caption_label}　" if derived and derived.caption_label else ""
        lines.append(f"{prefix}{resolve(figure.caption)}")
    lines.append(resolve(figure.alt))
    lines.extend(resolve(f) for f in figure.facts)
    if derived:
        lines.extend("　→　".join(path) for path in derived.paths[:8])
    return "\n".join(x for x in lines if x)


def build_passages(answer: Answer) -> list[Passage]:  # noqa: C901 - 単位ごとの分岐が本質
    """1 文書ぶんのパッセージ。**検索エンジンに登録する単位**。"""
    derived = answer.source.derived
    out: list[Passage] = []
    covered: set[str] = set()

    # 条（長い条は項ごとに割る）
    def walk(nodes: list) -> None:
        for node in nodes:
            if node.kind == "article":
                info = derived.labels.get(node.id)
                citation = info.citation if info else ""
                title = info.heading_text if info else (node.title or "")
                parts = [(c.id, _text_of(answer, c.id)) for c in node.children]
                parts = [(i, t) for i, t in parts if t]
                total = sum(len(t) for _i, t in parts)
                if total <= MAX_CHARS or len(parts) <= 1:
                    ids = [node.id, *[i for i, _t in parts]]
                    out.append(
                        _passage(
                            answer,
                            node.id,
                            "article",
                            title,
                            "\n".join([title, *[t for _i, t in parts]]),
                            ids,
                            citation,
                        )
                    )
                    covered.update(ids)
                else:
                    for child_id, text in parts:
                        child = derived.labels.get(child_id)
                        out.append(
                            _passage(
                                answer,
                                child_id,
                                "paragraph",
                                title,
                                f"{title}\n{text}",
                                [child_id],
                                child.citation if child else citation,
                            )
                        )
                        covered.add(child_id)
                    covered.add(node.id)
            walk(node.children or [])

    walk(answer.source.body)
    walk(answer.source.appendices)

    # 表・図
    for block, owner_id in _iter_blocks(answer):
        if isinstance(block, Table):
            info = derived.labels.get(owner_id)
            out.append(
                _passage(
                    answer,
                    block.id,
                    "table",
                    block.caption or (info.heading_text if info else ""),
                    _table_text(answer, block),
                    [block.id],
                    info.citation if info else "",
                )
            )
        elif isinstance(block, Figure):
            info = derived.labels.get(owner_id)
            out.append(
                _passage(
                    answer,
                    block.id,
                    "figure",
                    block.caption or (info.heading_text if info else ""),
                    _figure_text(answer, block),
                    [block.id],
                    info.citation if info else "",
                )
            )

    # 定義語（定義表の行。紙面に出ない `defined_terms` はパッセージにしない）
    out.extend(_definition_passages(answer))

    # 条に属さない本文（前付け・奥付・囲み）
    for element_id, plain in derived.plain_text.items():
        if element_id in covered or not plain.without_label.strip():
            continue
        element = answer.layout.elements.get(element_id)
        if element is None or element.kind not in ("paragraph", "list_item", "footnote"):
            continue
        if element_id.startswith(("tbl_", "fig_")):
            continue
        info = derived.labels.get(element_id)
        out.append(
            _passage(
                answer,
                element_id,
                "other",
                "",
                plain.with_label,
                [element_id],
                info.citation if info else "",
            )
        )
    return out


# --- クエリと qrels -----------------------------------------------------------

#: 適合度。2 = 答えがそこにある / 1 = 関連する
GRADE_EXACT = 2
GRADE_RELATED = 1


def _element_index(passages: list[Passage]) -> dict[str, dict[str, str]]:
    """`doc_id` → 要素 id → パッセージ id。

    **要素 id は文書内でしか一意でない。** `ch2_a1` は 80 文書に、`par_colophon_1` は
    89 文書にある（計 1,517 種が衝突）。コーパス全体で 1 本の索引を張ると、
    `qa` の evidence が別の文書のパッセージに解決される（実測 2,916/3,819 ＝ 76%）。
    文書ごとに分けて持つ（`docs/search_query_plan.md` W1）。
    """
    out: dict[str, dict[str, str]] = {}
    for passage in passages:
        per_doc = out.setdefault(passage.doc_id, {})
        for element_id in passage.element_ids:
            per_doc.setdefault(element_id, passage.passage_id)
    # 表のセル（`<table>__r1c2`）と表注は、その表のパッセージに寄せる。
    # 定義表の行パッセージが先にセル id を取っているので、表本体は上書きしない
    for passage in passages:
        if passage.kind in ("table", "figure"):
            base = passage.element_ids[0] if passage.element_ids else ""
            if base:
                out.setdefault(passage.doc_id, {}).setdefault(base, passage.passage_id)
    return out


def _resolve_evidence(evidence: str, index: dict[str, str]) -> str | None:
    if evidence in index:
        return index[evidence]
    # 表のセル・表注・脚注は接頭辞で寄せる
    for sep in ("__",):
        if sep in evidence:
            base = evidence.split(sep)[0]
            if base in index:
                return index[base]
    return None


#: 見出し文言の先頭に印字される番号ラベル。クエリに混ぜない（CLAUDE.md §2-2）。
#: lint L03（`yakkan/lint/rules.py` の `_LITERAL_*`）と似ているが**役割が違うので共有しない**
#: ——L03 は「執筆者がラベルを直書きしていないか」を本文のどこでも検出する規則、
#: こちらは「見出しの先頭にある印字済みのラベルを落とす」変換である（語彙も違う：
#: L03 は参照のための `項号編` を含み、こちらは見出しに出る `款` と序数 `1.` を含む）
HEADING_LABEL_RE = re.compile(
    r"^(?:[\u2460-\u2473]|第[0-9０-９]+[条章節款]|（[0-9０-９]+）|\([0-9]+\)|[0-9０-９]+[.．])\s*"
)
#: 見出し名として採る最小の長さ
MIN_HEADING_NAME = 3


def _heading_name(title: str) -> str | None:
    """条見出しから**文言だけ**を採る。番号ラベルは落とす。

    `第3条（告知義務）` → `告知義務`、`① お引受けの判断` → `お引受けの判断`。
    括弧を持たないしおり部の見出しは `title` 全体が来るので、丸数字を落とす
    （落とさないと「①　お引受けの判断」がそのままクエリになる。実測 173 件）。
    残りが短すぎるものはクエリにしない。
    """
    matched = re.search(r"（(.+)）$", title) or re.search(r"\((.+)\)$", title)
    name = matched.group(1) if matched else title
    previous = None
    while name != previous:
        previous = name
        name = HEADING_LABEL_RE.sub("", name).strip().strip("\u3000")
    return name if len(name) >= MIN_HEADING_NAME else None


#: `query_id` のハッシュの桁数
QUERY_ID_DIGEST = 10


def query_id(kind: str, key: str) -> str:
    """`kind` と生成キーから決まる安定した id。

    通し番号（`q_term_0001`）だと **content が 1 本増えるだけで全 id がずれる**
    （クエリが 1,944 → 5,610 件に増えた時点で過去の id はすべて別のクエリを指している）。
    版をまたいでスコアを比較できるようにハッシュにする（`docs/search_query_plan.md` W11）。
    """
    digest = hashlib.sha1(f"{kind}\u0000{normalize(key)}".encode()).hexdigest()
    return f"q_{kind}_{digest[:QUERY_ID_DIGEST]}"


#: 1 クエリあたりの grade 1 の上限。増えすぎると評価が緩くなる
MAX_RELATED = 20


def _spread(related: dict[str, int], limit: int) -> dict[str, int]:
    """grade 1 を上限まで間引く。**文書をまたいで均等に**取る。

    `passage_id` 順に先頭から切ると、doc_id が辞書順で前にある文書の
    パッセージばかりが残り、後ろの文書の関連パッセージが「非適合」と同じ
    扱いになる（docs/remaining_issues.md S5）。文書ごとの列を作って
    順番に 1 件ずつ拾えば、どの文書からも同じだけ残る。
    """
    if len(related) <= limit:
        return dict(sorted(related.items()))
    columns: dict[str, list[str]] = {}
    for passage_id in sorted(related):
        columns.setdefault(passage_id.split("::", 1)[0], []).append(passage_id)
    kept: list[str] = []
    while len(kept) < limit:
        added = False
        for doc_id in sorted(columns):
            queue = columns[doc_id]
            if not queue:
                continue
            kept.append(queue.pop(0))
            added = True
            if len(kept) >= limit:
                break
        if not added:
            break
    return {passage_id: related[passage_id] for passage_id in sorted(kept)}


def _under(citation: str, prefix: str) -> bool:
    """`citation` が `prefix` の配下か（「第2章 第1条 (1)」は「第2章 第1条」の配下）。"""
    if not prefix or not citation:
        return False
    return citation == prefix or citation.startswith(prefix + " ")


# --- 出現文書数（df）による振り分け（docs/search_query_plan.md W6） --------------

#: 字面がこれ以上の文書に散る語は、順位を競わせるクエリにしない（`enumeration` に回す）。
#: コーパス 90 文書の約 1/9 ＝ 1 ジャンルぶん。`scripts/probe_search_queries.py` と同じ値
WIDE_DF_DOCS = 10
#: 素のクエリとして出す上限（これを超えて字面が散るなら絞り込みが要る）
PLAIN_DF_LITERAL = 3
#: ハードネガティブとして列挙する件数の上限
MAX_HARD_NEGATIVES = 10
#: `no_answer` クエリの件数（seed で決定論的に抽出する）
NO_ANSWER_QUERIES = 200
#: `definition_masked` でクエリと gold の字面重複がこれを超えたら出さない
MAX_SURFACE_OVERLAP = 0.5
#: `definition_masked` を 1 文書あたり何件まで出すか（(条文 × 用語) の組は 6,000 を超える）
MAX_CLOZE_PER_DOC = 12
#: 短すぎて情報量が無いクエリは出さない
MIN_QUERY_CHARS = 20


def _one_line(text: str) -> str:
    """クエリ文を 1 行にする。改行や連続空白は検索器に渡す文として不要。"""
    return re.sub(r"[\s\u3000]+", " ", text).strip()


def _bigrams(text: str) -> set[str]:
    s = normalize(text)
    return {s[i : i + 2] for i in range(len(s) - 1)} or ({s} if s else set())


def _surface_overlap(query: str, target: str) -> float:
    """クエリと gold の字面の重なり（文字 2-gram の Jaccard 風。クエリ側を母数にする）。"""
    a, b = _bigrams(query), _bigrams(target)
    return len(a & b) / len(a) if a else 0.0


class _Literal:
    """字面がどの文書・どのパッセージに出るかを引く転置索引。

    素朴な全走査は O(パッセージ × 語) で、`probe` の実測で 19 秒かかる。
    文字 2-gram の転置索引で候補を絞ってから部分文字列を確かめる
    （`docs/search_query_plan.md` §6 R-5）。
    """

    def __init__(self, passages: list[Passage]) -> None:
        self._text = {p.passage_id: normalize(p.text) for p in passages}
        self._doc = {p.passage_id: p.doc_id for p in passages}
        self._index: dict[str, set[str]] = {}
        for passage_id, text in self._text.items():
            for i in range(len(text) - 1):
                self._index.setdefault(text[i : i + 2], set()).add(passage_id)

    def passages(self, word: str) -> set[str]:
        needle = normalize(word)
        if not needle:
            return set()
        if len(needle) == 1:
            return {pid for pid, text in self._text.items() if needle in text}
        grams = [needle[i : i + 2] for i in range(len(needle) - 1)]
        candidates: set[str] | None = None
        for gram in grams:
            hits = self._index.get(gram, set())
            candidates = hits.copy() if candidates is None else (candidates & hits)
            if not candidates:
                return set()
        return {pid for pid in (candidates or set()) if needle in self._text[pid]}

    def docs(self, word: str) -> set[str]:
        return {self._doc[pid] for pid in self.passages(word)}


def build_search_set(  # noqa: C901 - クエリ種別ごとの分岐が本質
    passages: list[Passage],
    qa_by_doc: dict[str, list[dict[str, Any]]],
    terms_by_doc: dict[str, dict[str, str]] | None = None,
) -> tuple[list[Query], list[Qrel]]:
    """コーパス全体のクエリと qrels を作る（`docs/search_query_plan.md` 段 2・段 3）。

    クエリは 10 系統。**出現文書数（df）で素のクエリ・絞り込み・網羅に振り分ける**のが要点で、
    「被保険者」「告知義務」のような広く使われる語は素のクエリにしない
    （どの文書を返すべきかがクエリから決まらないため）。

    | kind | 作り方 | gold |
    |---|---|---|
    | `term` | `df_docs == 1` の定義語 | その語の定義行 |
    | `heading` | `df_docs == 1` の条見出しの文言 | 同名の条 |
    | `scoped` | 「会社名＋商品名＋見出し」 | その文書の条だけ |
    | `filtered` | 見出しの文言のみ＋`filters` | 同上（絞り込みはメタデータで渡す） |
    | `enumeration` | 頻出語の網羅要求 | 全文書のその語の定義行（**grade 2 のみ**） |
    | `qa` | 既存 QA の問い | evidence のパッセージ |
    | `definition_masked` | 定義本文から見出し語を隠したもの | その語の定義行 |
    | `multi_hop` | 参照元の文言 | **参照先**の条 |
    | `situational` | 執筆 QA の `apply` の場面記述 | 根拠の条 |
    | `no_answer` | その文書に無い見出し・用語 | **空集合**（返さないのが正解） |

    **適合度は捏造しない。** grade は `derived` に実在する関係（用語の使用・条項間参照・
    同じ条に属すること）と、宣言した字面の規則からだけ導く。
    """
    terms_by_doc = terms_by_doc or {}
    by_id = {p.passage_id: p for p in passages}
    element_index = _element_index(passages)
    literal = _Literal(passages)
    by_doc: dict[str, list[Passage]] = {}
    for passage in passages:
        by_doc.setdefault(passage.doc_id, []).append(passage)
    queries: list[Query] = []
    qrels: list[Qrel] = []

    def add(
        kind: str,
        key: str,
        text: str,
        hits: dict[str, int],
        *,
        note: str = "",
        rule: str = "",
        filters: dict[str, str] | None = None,
        facet_in_text: bool = False,
        negatives: list[str] | None = None,
        allow_empty: bool = False,
        truncate: bool = True,
    ) -> None:
        exact = {p: g for p, g in hits.items() if p in by_id and g == GRADE_EXACT}
        related = {p: g for p, g in hits.items() if p in by_id and g == GRADE_RELATED and p not in exact}
        if not exact and not allow_empty:
            return
        trimmed = _spread(related, MAX_RELATED) if truncate else dict(sorted(related.items()))
        merged = exact | trimmed
        queries.append(
            Query(
                query_id=query_id(kind, key),
                kind=kind,
                query=text,
                note=note,
                n_relevant=len(merged),
                n_exact=len(exact),
                n_related=len(trimmed),
                # 上限で切った分は qrels に出ないので、**Recall を誤解しないための印**を残す
                n_related_total=len(related),
                related_truncated=len(related) > len(trimmed),
                relevance_rule=rule,
                filters=filters or {},
                facet_in_text=facet_in_text,
                hard_negatives=(negatives or [])[:MAX_HARD_NEGATIVES],
            )
        )
        for passage_id, grade in sorted(merged.items()):
            qrels.append(Qrel(query_id=query_id(kind, key), passage_id=passage_id, grade=grade))

    def related_of_article(article: Passage) -> dict[str, int]:
        """条に対する「関連する」パッセージ：その条に属する表・図と、その条を参照する条。"""
        out: dict[str, int] = {}
        citation = article.citation
        element_ids = set(article.element_ids)
        for passage in by_doc.get(article.doc_id, []):
            if passage.passage_id == article.passage_id:
                continue
            owns_block = passage.kind in ("table", "figure") and _under(passage.citation, citation)
            cites_it = bool(element_ids & set(passage.refs_to))
            if owns_block or cites_it:
                out[passage.passage_id] = GRADE_RELATED
        return out

    def negatives_for(word: str, gold: dict[str, int]) -> list[str]:
        """字面は一致するが非適合なパッセージ。**紛らわしいと宣言された 0**。"""
        return sorted(pid for pid in literal.passages(word) if pid not in gold)

    def term_uses(doc_id: str, word: str) -> dict[str, int]:
        """その文書でその語を使っている条（grade 1）。

        **`term_id` は文書をまたいで一意でない**（70/502 の id が別の語に使い回され、
        `pet` は 11 語に使われている）。文書ごとに `term_id → 語` を引いて、
        **その文書でその語に割り当てられた id** だけを見る（`docs/search_query_plan.md` W3）。
        """
        names = terms_by_doc.get(doc_id, {})
        wanted = {term_id for term_id, name in names.items() if name == word}
        if not wanted:
            return {}
        return {
            p.passage_id: GRADE_RELATED
            for p in by_doc.get(doc_id, [])
            if p.kind != "definition" and wanted & set(p.terms_used)
        }

    # --- 語・見出しを集めて df で振り分ける --------------------------------------
    definitions: dict[str, list[Passage]] = {}
    for passage in passages:
        if passage.kind == "definition" and passage.title:
            definitions.setdefault(passage.title, []).append(passage)
    headings: dict[str, list[Passage]] = {}
    for passage in passages:
        if passage.kind != "article":
            continue
        name = _heading_name(passage.title)
        if name:
            headings.setdefault(name, []).append(passage)

    def route(name: str, hits: list[Passage]) -> str:
        """`plain` / `scoped` / `enumeration` のどれにするか。"""
        if len(literal.docs(name)) >= WIDE_DF_DOCS:
            return "enumeration"
        docs = {p.doc_id for p in hits}
        if len(docs) == 1 and len(literal.docs(name)) <= PLAIN_DF_LITERAL:
            return "plain"
        return "scoped"

    # --- term（素） -----------------------------------------------------------
    for word, hits in sorted(definitions.items()):
        lane = route(word, hits)
        if lane != "plain":
            continue
        grades = {p.passage_id: GRADE_EXACT for p in hits}
        for hit in hits:
            grades.update(term_uses(hit.doc_id, word))
        add(
            "term",
            word,
            word,
            grades,
            note="用語の定義を引く項目検索（この語を定義しているのは 1 文書だけ）",
            rule="grade 2 はその語の定義行、grade 1 は同じ文書でその語を使っている条",
            negatives=negatives_for(word, grades),
        )

    # --- heading（素） --------------------------------------------------------
    for name, hits in sorted(headings.items()):
        if route(name, hits) != "plain":
            continue
        grades = {p.passage_id: GRADE_EXACT for p in hits}
        for hit in hits:
            for passage_id, grade in related_of_article(hit).items():
                grades.setdefault(passage_id, grade)
        add(
            "heading",
            name,
            name,
            grades,
            note="見出しの項目検索（同名の条を持つのは 1 文書だけ）",
            rule="grade 2 は同名の条、grade 1 はその条に属する表・図とその条を参照する条",
            negatives=negatives_for(name, grades),
        )

    # --- enumeration（頻出語の網羅） -------------------------------------------
    # grade 2 だけ。「定義している箇所をすべて挙げよ」に対して使用箇所は答えではない。
    # 字面一致で grade 1 を作ると 1 語あたり平均 115 件に膨れる（W7）
    for word, hits in sorted(definitions.items()):
        if route(word, hits) != "enumeration":
            continue
        grades = {p.passage_id: GRADE_EXACT for p in hits}
        add(
            "enumeration",
            word,
            f"この約款集で「{word}」を定義している箇所をすべて挙げてください。",
            grades,
            note=f"網羅を測るクエリ（{len(hits)} 文書が定義している頻出語）",
            rule="grade 2 は全文書のその語の定義行。grade 1 は作らない",
            truncate=False,
        )
    for name, hits in sorted(headings.items()):
        if route(name, hits) != "enumeration":
            continue
        grades = {p.passage_id: GRADE_EXACT for p in hits}
        add(
            "enumeration",
            f"heading:{name}",
            f"この約款集で「{name}」を定める条をすべて挙げてください。",
            grades,
            note=f"網羅を測るクエリ（{len(hits)} 文書に同名の条がある）",
            rule="grade 2 は全文書の同名の条。grade 1 は作らない",
            truncate=False,
        )

    # --- scoped / filtered（絞り込み） ------------------------------------------
    # 商品名は実質メタデータで本文にほぼ出ない（gold 309 件中 3 件）。
    # 自然文に facet を入れた `scoped` と、`filters` で渡す `filtered` の 2 変種を出して
    # 「テキストで絞れるか」と「メタデータを索引しているか」を切り分ける（W8）
    for name, hits in sorted(headings.items()):
        if route(name, hits) != "scoped":
            continue
        # **1 つの文書に同名の条が複数あることがある**（特約ごとの「この特約に定めのない
        # 事項の取扱い」など、1 文書に 3 本）。クエリは文書単位なので、その文書の同名の条を
        # **すべて grade 2 にして 1 クエリにまとめる**（分けると同じ入力に別の正解ができる）
        per_doc_hits: dict[str, list[Passage]] = {}
        for hit in hits:
            per_doc_hits.setdefault(hit.doc_id, []).append(hit)
        for doc_id, doc_hits in sorted(per_doc_hits.items()):
            hit = sorted(doc_hits, key=lambda p: p.passage_id)[0]
            grades = {h.passage_id: GRADE_EXACT for h in doc_hits}
            for h in doc_hits:
                for passage_id, grade in related_of_article(h).items():
                    grades.setdefault(passage_id, grade)
            facets = {"issuer": hit.issuer, "product_name": hit.product_name, "genre": hit.genre}
            others = [p.passage_id for p in hits if p.doc_id != doc_id]
            add(
                "scoped",
                f"{doc_id}|{name}",
                f"{hit.issuer}の{hit.product_name}の{name}",
                grades,
                note=f"商品名で絞り込む項目検索（同名の条が {len(hits)} 文書にある）",
                rule="grade 2 はその文書の同名の条すべて。facet はクエリ文に含まれる",
                facet_in_text=True,
                negatives=others,
            )
            add(
                "filtered",
                f"{doc_id}|{name}",
                name,
                grades,
                note="メタデータで絞り込む項目検索（クエリ文は見出しの文言だけ）",
                rule="grade 2 はその文書の同名の条すべて。絞り込みは filters で与える",
                filters=facets,
                negatives=others,
            )

    # --- definition_masked（条文の文脈から用語の定義を引く） ---------------------
    # **定義本文そのものをクエリにしても循環は断てない**——見出し語だけ隠しても
    # 本文は gold の字面そのままなので、素朴な BM25 で nDCG@1 0.938 が出た（実測）。
    # そこで向きを変える：**その語を使っている条文**を文脈として与え、語を隠して
    # 「この〔用語〕の定義はどこか」を聞く。クエリは gold とは別のパッセージの文なので
    # 字面が重ならず、意味で結びつけないと解けない（`docs/search_query_plan.md` W12）。
    definition_by_doc: dict[tuple[str, str], Passage] = {}
    for word, hits in definitions.items():
        for hit in hits:
            definition_by_doc.setdefault((hit.doc_id, word), hit)
    cloze: dict[tuple[str, str], tuple[Passage, Passage, str]] = {}
    for passage in passages:
        if passage.kind == "definition" or not passage.terms_used:
            continue
        names = terms_by_doc.get(passage.doc_id, {})
        body = passage.text.split("\n", 1)[-1].strip()
        for term_id in sorted(set(passage.terms_used)):
            word = names.get(term_id)
            target = definition_by_doc.get((passage.doc_id, word or ""))
            if not word or target is None or word not in body:
                continue
            masked = body.replace(word, "〔用語〕")
            if len(normalize(masked)) < MIN_QUERY_CHARS:
                continue
            if _surface_overlap(masked, target.text) > MAX_SURFACE_OVERLAP:
                continue  # 文脈が定義文とほぼ同じなら、字面で解けてしまう
            # **クエリ文そのもので重複を見る。** 長い条文は切り詰めるので、
            # 先頭が同じ 2 つの条文が同じクエリ文になりうる（自己検査 V-S4 が検出した）
            text = f"次の条文の〔用語〕にあたる語の定義はどこにありますか。「{_one_line(masked)[:200]}」"
            cloze.setdefault((passage.doc_id, normalize(text)), (passage, target, text))
    # 1 文書あたりの件数を絞る。(条文 × 用語) の組は全体で 6,000 を超え、
    # これだけで評価セットの半分を占めてしまう。**用語ごとに 1 本ずつ**拾って
    # 用語の偏りを避けつつ、文書あたり `MAX_CLOZE_PER_DOC` 件で打ち切る
    per_doc: dict[str, list[tuple[Passage, Passage, str]]] = {}
    seen_terms: dict[str, set[str]] = {}
    for (doc_id, _key), item in sorted(cloze.items()):
        kept = per_doc.setdefault(doc_id, [])
        terms_seen = seen_terms.setdefault(doc_id, set())
        if len(kept) >= MAX_CLOZE_PER_DOC or item[1].passage_id in terms_seen:
            continue
        terms_seen.add(item[1].passage_id)
        kept.append(item)
    for doc_id, items in sorted(per_doc.items()):
        for source, target, text in items:
            # 出題に使った条文は **grade 1**（その語を実際に使っている箇所なので関連する）。
            # クエリ文がその条文の引用なので字面では必ず 1 位に来る——非適合にすると
            # どの字面ベースの検索器も nDCG@1 が 0.000 に張り付き、勾配が消える（実測）。
            # **grade 2（定義行）を引けたかは `exact_recall@k` で別に見る。**
            grades = {target.passage_id: GRADE_EXACT, source.passage_id: GRADE_RELATED}
            add(
                "definition_masked",
                f"{doc_id}|{source.passage_id}|{target.passage_id}",
                text,
                grades,
                note=f"条文の文脈から用語の定義を引く意味検索（{doc_id}）",
                rule="grade 2 はその語の定義行、grade 1 は出題に使った条文（語の使用箇所）",
                filters={"issuer": source.issuer, "product_name": source.product_name},
            )

    # --- multi_hop（参照先にしか答えが無い） -------------------------------------
    articles_by_element: dict[str, dict[str, Passage]] = {}
    for passage in passages:
        if passage.kind == "article":
            for element_id in passage.element_ids:
                articles_by_element.setdefault(passage.doc_id, {}).setdefault(element_id, passage)
    for passage in passages:
        targets = {
            target.passage_id: target
            for to_id in sorted(set(passage.refs_to))
            if (target := articles_by_element.get(passage.doc_id, {}).get(to_id)) is not None
            and target.passage_id != passage.passage_id
        }
        # **参照先が 2 つ以上ある条はクエリにしない。** 同じ文言から複数の条を指すので
        # 「どれを返すべきか」がクエリから決まらない（自己検査 V-S4 が実際に検出した）
        if len(targets) != 1:
            continue
        for to_id in sorted(set(passage.refs_to)):
            target = articles_by_element.get(passage.doc_id, {}).get(to_id)
            if target is None or target.passage_id == passage.passage_id:
                continue
            source_text = _one_line(passage.text.split("\n", 1)[-1])
            # 前付け・奥付のパッセージは本文にラベルを含む（「第３条当会社は…」）。
            # クエリに版面由来の番号を混ぜない（CLAUDE.md §2-2）
            source_text = HEADING_LABEL_RE.sub("", source_text).strip()
            if len(normalize(source_text)) < MIN_QUERY_CHARS:
                continue
            # 参照先の見出しをクエリに書かない（書くと字面で解けてしまう）
            if normalize(target.title) and normalize(target.title) in normalize(source_text):
                continue
            grades = {target.passage_id: GRADE_EXACT, passage.passage_id: GRADE_RELATED}
            add(
                "multi_hop",
                f"{passage.doc_id}|{passage.passage_id}|{to_id}",
                f"次の定めが参照している条はどれですか。「{source_text[:160]}」",
                grades,
                note="参照を辿らないと答えが出ないクエリ",
                rule="grade 2 は参照先の条、grade 1 は参照元",
                filters={"issuer": passage.issuer, "product_name": passage.product_name},
            )

    # --- qa / situational -------------------------------------------------------
    for doc_id, items in sorted(qa_by_doc.items()):
        # **文書内に閉じた索引を使う。** 要素 id は文書内でしか一意でない（W1）
        index = element_index.get(doc_id, {})
        for item in items:
            evidence = [e for e in item.get("evidence", []) if e]
            if not evidence:
                continue
            grades: dict[str, int] = {}
            for element_id in evidence:
                passage_id = _resolve_evidence(f"{element_id}", index)
                if passage_id:
                    grades[passage_id] = GRADE_EXACT
            if not grades:
                continue
            citations = {by_id[pid].citation for pid in list(grades) if by_id[pid].citation}
            for passage in by_doc.get(doc_id, []):
                if passage.passage_id in grades:
                    continue
                if any(_under(passage.citation, c) or _under(c, passage.citation) for c in citations):
                    grades[passage.passage_id] = GRADE_RELATED
            for passage_id in [p for p, g in grades.items() if g == GRADE_EXACT]:
                article = by_id.get(passage_id)
                if article and article.kind == "article":
                    for related_id, grade in related_of_article(article).items():
                        grades.setdefault(related_id, grade)
            question = item["question"]
            head = by_doc[doc_id][0]
            facets = {"issuer": head.issuer, "product_name": head.product_name}
            add(
                "qa",
                f"{doc_id}|{question}",
                question,
                grades,
                note=f"{item['type']} の問い（{doc_id}）",
                rule="grade 2 は evidence を含むパッセージ、grade 1 は同じ条の別のパッセージ",
                # **問いは必ず特定の文書についてのもの。** 「「(4)」は何ページにありますか」は
                # 20 文書で同じ文字列になり、文書を絞らないと答えが決まらない
                # （qa の 56% が「第N条」「表N」のような文書ローカルな番号だけを手がかりにしている）
                filters=facets,
            )
            # 場面適用の問いは、問いかけを落として**場面の記述だけ**を意味検索のクエリにする
            if item["type"] == "apply":
                scene = _scene_of(question)
                if scene and len(normalize(scene)) >= MIN_QUERY_CHARS:
                    add(
                        "situational",
                        f"{doc_id}|{question}",
                        scene,
                        grades,
                        note=f"場面適用の意味検索（{doc_id}）",
                        rule="grade 2 は根拠の条、grade 1 は同じ条の別のパッセージ",
                        filters=facets,
                    )

    # --- no_answer（根拠が無いときに黙れるか） ----------------------------------
    queries.extend(_no_answer_queries(by_doc, definitions, headings))
    return queries, qrels


#: 問いかけを含む節を見分ける語（これを含む末尾の節を落とす）
_INTERROGATIVE = (
    "いくら",
    "何円",
    "何日",
    "何回",
    "何パーセント",
    "何%",
    "どちら",
    "どれ",
    "どこ",
    "ですか",
    "ますか",
    "でしょうか",
)


def _scene_of(question: str) -> str | None:
    """場面適用の問いから**場面の記述だけ**を採る。

    「人身傷害の補償で、…後遺障害が残った場合、…は何パーセントとして算定されますか。」
    → 「人身傷害の補償で、…後遺障害が残った場合」

    読点で区切った節のうち、**問いかけを含む末尾の節を落とす**だけの決定的な規則で作る。
    新しい文は書かない（`docs/search_query_plan.md` W14・`TASK.md` T10 で
    「既存の `apply` 型をそのまま昇格させ、新規執筆はしない」と決めた）。
    """
    body = question.strip().rstrip("。？?　 ")
    parts = [p for p in body.split("、") if p.strip()]
    while parts and any(word in parts[-1] for word in _INTERROGATIVE):
        parts.pop()
    scene = "、".join(parts).strip("、。 　")
    return _one_line(scene) or None


def _no_answer_queries(
    by_doc: dict[str, list[Passage]],
    definitions: dict[str, list[Passage]],
    headings: dict[str, list[Passage]],
) -> list[Query]:
    """その文書に**無い**見出し・用語を、文書を絞って聞く。gold は空集合。

    「根拠が無いときに何も返さない」能力を測る。qrels には 1 行も出ない（W9）。
    """
    pool: list[tuple[str, str]] = [("用語", w) for w in sorted(definitions)]
    pool += [("見出し", n) for n in sorted(headings)]
    out: list[Query] = []
    rng = random.Random(20261004)
    doc_ids = sorted(by_doc)
    has: dict[str, set[str]] = {
        doc_id: {p.title for p in items if p.kind == "definition"}
        | {name for name, hits in headings.items() if any(h.doc_id == doc_id for h in hits)}
        for doc_id, items in by_doc.items()
    }
    attempts = 0
    seen: set[tuple[str, str]] = set()
    while len(out) < NO_ANSWER_QUERIES and attempts < NO_ANSWER_QUERIES * 50:
        attempts += 1
        doc_id = doc_ids[rng.randrange(len(doc_ids))]
        what, word = pool[rng.randrange(len(pool))]
        if word in has.get(doc_id, set()) or (doc_id, word) in seen:
            continue
        # 字面がその文書に出るなら「無い」と言い切れないので避ける
        if any(normalize(word) in normalize(p.text) for p in by_doc[doc_id]):
            continue
        seen.add((doc_id, word))
        head = by_doc[doc_id][0]
        out.append(
            Query(
                query_id=query_id("no_answer", f"{doc_id}|{word}"),
                kind="no_answer",
                query=f"{head.product_name}で「{word}」を定めているのはどこですか。",
                note=f"この文書にこの{what}は無い（{doc_id}）",
                n_relevant=0,
                n_exact=0,
                n_related=0,
                n_related_total=0,
                relevance_rule="適合するパッセージは無い。**何も返さない**のが正解",
                filters={
                    "issuer": head.issuer,
                    "product_name": head.product_name,
                    "genre": head.genre,
                },
                facet_in_text=True,
            )
        )
    return out


# --- 生成時の自己検査（docs/search_query_plan.md W5） --------------------------


def validate_search_set(  # noqa: C901 - 検査項目ごとの分岐が本質
    passages: list[Passage],
    queries: list[Query],
    qrels: list[Qrel],
    *,
    terms_by_doc: dict[str, dict[str, str]] | None = None,
) -> list[str]:
    """クエリと qrels の整合を検査する。1 件でも返ったら `export` は停止する。

    `yakkan eval --oracle`（満点の予測）は**クエリの良し悪しを検出しない**
    ——満点の並びを与えれば必ず満点になる。評価セットの健全性は
    「クエリが解を決定できるか」で決まるので、生成時に機械で確かめる。
    """
    problems: list[str] = []
    by_id = {p.passage_id: p for p in passages}
    by_query: dict[str, dict[str, int]] = {}
    for qrel in qrels:
        by_query.setdefault(qrel.query_id, {})[qrel.passage_id] = qrel.grade
    queries_by_id = {q.query_id: q for q in queries}

    # V-S1 `qa` / `situational` の grade 2 は出題元の文書のパッセージである
    for query in queries:
        if query.kind not in ("qa", "situational"):
            continue
        matched = re.search(r"（([^（）]+)）\s*$", query.note)
        if not matched:
            continue
        owner = matched.group(1)
        golds = {
            pid.split("::", 1)[0] for pid, g in by_query.get(query.query_id, {}).items() if g == GRADE_EXACT
        }
        if golds and owner not in golds:
            problems.append(f"V-S1 {query.query_id}: gold が出題元 {owner} ではなく {sorted(golds)} を指す")

    # V-S2 素の `term` / `heading` は 1 文書にしか gold を持たない（df_docs == 1）
    for query in queries:
        if query.kind not in ("term", "heading"):
            continue
        golds = {
            pid.split("::", 1)[0] for pid, g in by_query.get(query.query_id, {}).items() if g == GRADE_EXACT
        }
        if len(golds) > 1:
            problems.append(
                f"V-S2 {query.query_id}（{query.query}）: 素のクエリなのに gold が {len(golds)} 文書に跨る"
            )

    # V-S3 `enumeration` に grade 1 は無い（＝打ち切りが起きない）
    for query in queries:
        if query.kind == "enumeration" and (query.n_related or query.related_truncated):
            problems.append(f"V-S3 {query.query_id}: enumeration に grade 1 がある（打ち切りが起きる）")

    # V-S4 同じ入力のクエリが gold を食い違わせていない。
    # **入力はクエリ文だけでなく `filters` も含む**——`filtered` は同じ文言を
    # メタデータで絞り込む kind なので、filters が違えば別の入力である
    groups: dict[tuple[str, str, str], list[str]] = {}
    for query in queries:
        facet = "|".join(f"{k}={v}" for k, v in sorted(query.filters.items()))
        groups.setdefault((query.kind, normalize(query.query), facet), []).append(query.query_id)
    for (kind, text, _facet), ids in groups.items():
        golds = {frozenset(p for p, g in by_query.get(i, {}).items() if g == GRADE_EXACT) for i in ids}
        if len(ids) > 1 and len(golds) > 1:
            problems.append(f"V-S4 {kind}「{text[:28]}」: 同じ文字列のクエリ {len(ids)} 件が別の gold を持つ")

    # V-S5 `definition_masked` のクエリと gold の字面重複が閾値以下
    for query in queries:
        if query.kind != "definition_masked":
            continue
        for passage_id, grade in by_query.get(query.query_id, {}).items():
            if grade != GRADE_EXACT:
                continue
            title = by_id[passage_id].title if passage_id in by_id else ""
            if title and _surface_overlap(query.query, title) > MAX_SURFACE_OVERLAP:
                problems.append(f"V-S5 {query.query_id}: gold の見出し「{title}」と字面が重なりすぎる")

    # V-S6 クエリ文に番号ラベルが無い。
    # **クエリ文が見出し・用語そのものである kind に限る**——問いや条文の引用に
    # 「第3条」「(1)」が出るのは正しい（`qa` の 56% は文書ローカルな番号を手がかりにしている）
    for query in queries:
        if query.kind not in ("term", "heading", "scoped", "filtered", "enumeration"):
            continue
        if HEADING_LABEL_RE.match(query.query):
            problems.append(f"V-S6 {query.query_id}: クエリ文が番号ラベルで始まる（{query.query[:20]}）")

    # V-S7 `filters` がコーパスで一意に 1 文書を決める
    docs_by_facet: dict[tuple[str, str], set[str]] = {}
    for passage in passages:
        docs_by_facet.setdefault(("issuer", passage.issuer), set()).add(passage.doc_id)
        docs_by_facet.setdefault(("product_name", passage.product_name), set()).add(passage.doc_id)
    for query in queries:
        if not query.filters:
            continue
        narrowed: set[str] | None = None
        for key in ("issuer", "product_name"):
            value = query.filters.get(key)
            if value is None:
                continue
            docs = docs_by_facet.get((key, value), set())
            narrowed = docs.copy() if narrowed is None else (narrowed & docs)
        if narrowed is not None and len(narrowed) != 1:
            problems.append(f"V-S7 {query.query_id}: filters が {len(narrowed)} 文書を指す（一意でない）")

    # V-S8 `definition` パッセージは紙面上の位置を持つ
    for passage in passages:
        if passage.kind == "definition" and not passage.pages:
            problems.append(
                f"V-S8 {passage.passage_id}: definition パッセージに pages が無い（紙面に存在しない）"
            )

    # V-S9 grade 1 の `term_id` がその文書でその語に割り当てられている
    if terms_by_doc:
        for query in queries:
            if query.kind != "term":
                continue
            for passage_id, grade in by_query.get(query.query_id, {}).items():
                if grade != GRADE_RELATED or passage_id not in by_id:
                    continue
                passage = by_id[passage_id]
                names = terms_by_doc.get(passage.doc_id, {})
                if not any(names.get(t) == query.query for t in passage.terms_used):
                    problems.append(f"V-S9 {query.query_id}: {passage_id} は「{query.query}」を使っていない")

    # qrels がクエリ一覧と整合している
    orphan = sorted(set(by_query) - set(queries_by_id))
    if orphan:
        problems.append(f"qrels に queries.jsonl へ出ていない query_id が {len(orphan)} 件（{orphan[:3]}）")
    duplicated = len(queries) - len({q.query_id for q in queries})
    if duplicated:
        problems.append(f"query_id が {duplicated} 件重複している（生成キーが衝突している）")
    return problems
