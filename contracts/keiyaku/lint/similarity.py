"""文単位の重複率（L15）。

同じジャンルで何文書も作ると条文が似通う。**文を n-gram 集合に落として Jaccard で測り**、
30% を超えたら警告する（CLAUDE.md §8 L15）。

定型条ライブラリ由来の文は意図的に共通なので、比較対象から外す。
"""

from __future__ import annotations

import contextlib
import json
import re
from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from keiyaku.lint.walk import iter_texts
from keiyaku.models import SourceDraft
from keiyaku.richtext import RichTextError, parse, raw_text

CONTENT_DIR = Path.cwd() / "content"
LIBRARY_DIR = Path(__file__).resolve().parents[2] / "library" / "clauses"
#: 重複とみなす閾値
THRESHOLD = 0.30
#: n-gram の長さ（文字）
NGRAM = 12
#: 比較する最小文長
MIN_SENTENCE = 16

_SPLIT = re.compile(r"[。．\n]")


def sentences(draft: SourceDraft) -> list[str]:
    out: list[str] = []
    for owned in iter_texts(draft):
        text = owned.text
        if owned.rich:
            with contextlib.suppress(RichTextError):
                text = raw_text(parse(text))
        for sentence in _SPLIT.split(text):
            cleaned = sentence.strip()
            if len(cleaned) >= MIN_SENTENCE:
                out.append(cleaned)
    return out


def ngrams(texts: list[str], n: int = NGRAM) -> set[str]:
    out: set[str] = set()
    for text in texts:
        for i in range(max(len(text) - n + 1, 1)):
            out.add(text[i : i + n])
    return out


@lru_cache(maxsize=1)
def library_ngrams() -> frozenset[str]:
    """定型条ライブラリ由来の n-gram（共通なのが当然なので比較から外す）。"""
    texts: list[str] = []
    for path in LIBRARY_DIR.rglob("*.json"):
        data = json.loads(path.read_text(encoding="utf-8"))
        for variant in data.get("variants", []):
            for paragraph in variant.get("paragraphs", []):
                texts.append(paragraph.get("text", ""))
    return frozenset(ngrams(texts))


def jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    return len(a & b) / len(a | b)


def _unfinished(content_dir: Path) -> bool:
    """まだ TODO が残っている（＝執筆途中の）content か。"""
    from keiyaku.compose import count_todos, raw_document

    try:
        return count_todos(raw_document(content_dir)) > 0
    except Exception:  # noqa: BLE001 — 読めない content は比較対象から外すだけ
        return True


def compare_with_existing(
    draft: SourceDraft, content_dir: Path | None = None
) -> Iterator[tuple[str, float, list[str]]]:
    """同じジャンルの既存 content と比べ、閾値を超えたものを返す。"""
    from keiyaku.compose import load_draft_or_errors

    base = content_dir or CONTENT_DIR
    if not base.is_dir():
        return
    mine_sentences = sentences(draft)
    mine = ngrams(mine_sentences) - library_ngrams()
    if not mine:
        return
    for other_dir in sorted(base.iterdir()):
        if not other_dir.is_dir() or other_dir.name == draft.content_id:
            continue
        other, errors = load_draft_or_errors(other_dir)
        if other is None or errors or other.doctype != draft.doctype:
            continue
        if _unfinished(other_dir):
            # 未執筆の content（scaffold のまま）は比較対象にしない。
            # 骨組みの文言が同じなので必ず高い重複率が出て、執筆者が幻の重複を追うことになる
            # （実測：未執筆どうしは 100%、執筆済み × 未執筆で 79〜86%。
            #  執筆済みどうしは 8.8〜26.3% だった）。
            continue
        other_sentences = sentences(other)
        theirs = ngrams(other_sentences) - library_ngrams()
        ratio = jaccard(mine, theirs)
        if ratio > THRESHOLD:
            shared = [s for s in mine_sentences if s in other_sentences]
            yield other_dir.name, ratio, shared
