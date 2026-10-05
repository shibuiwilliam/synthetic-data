"""最小サンプル（tests/golden/sample_min）の golden テスト。

固定するもの
- lint が error / warn ともに 0 件であること
- 全ノードの label / heading_text / path（番号付けの回帰検知）
- `{ref:}` の解決結果（参照表記の回帰検知）

更新は `uv run pytest --update-golden` で行い、差分の理由をコミットメッセージに書く。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from keiyaku.compose import load_draft
from keiyaku.lint.runner import lint_content
from keiyaku.numbering import DocumentIndex, NumberingContext, resolve_ref
from keiyaku.richtext import Ref, iter_tokens, parse

SAMPLE = Path(__file__).parent / "sample_min"
GOLDEN_LABELS = Path(__file__).parent / "sample_min.labels.json"
GOLDEN_REFS = Path(__file__).parent / "sample_min.refs.json"


@pytest.fixture(scope="module")
def draft():
    return load_draft(SAMPLE)


@pytest.fixture(scope="module")
def index(draft) -> DocumentIndex:
    ctx = NumberingContext(draft.meta.numbering_scheme, draft.meta.digit_style)
    return DocumentIndex(ctx, draft.body, draft.appendices)


def _compare(actual: dict, golden_path: Path, update: bool) -> None:
    text = json.dumps(actual, ensure_ascii=False, indent=2) + "\n"
    if update or not golden_path.exists():
        golden_path.write_text(text, encoding="utf-8")
        if not update:
            pytest.fail(f"golden が無かったので作成した: {golden_path}（内容を確認してコミットする）")
        return
    expected = json.loads(golden_path.read_text(encoding="utf-8"))
    assert actual == expected, f"{golden_path.name} と一致しない（意図した変更なら --update-golden）"


def test_lintが通る() -> None:
    """sample_min は描画検証用の 3 ページ抜粋なので、文書全体の規則（L04/L09/L15/L16）は外す。"""
    findings = lint_content(SAMPLE, exclude=["L04", "L09", "L15", "L16"])
    assert findings == [], "\n".join(f.format() for f in findings)


def test_ラベルのgolden(index: DocumentIndex, update_golden: bool) -> None:
    actual = {
        node_id: {
            "label": info.label,
            "title": info.title,
            "heading_text": info.heading_text,
            "path": info.path,
            "depth": info.depth,
        }
        for node_id, info in index.labels().items()
    }
    _compare(actual, GOLDEN_LABELS, update_golden)


def test_参照解決のgolden(draft, index: DocumentIndex, update_golden: bool) -> None:
    """ノードの参照（numbering.py）と表・図の参照（build の採番）の両方を固定する。

    `{ref:tbl_x}` `{ref:fig_x}` は `DocumentIndex` に載らない——採番するのは
    `assign_caption_labels` のほうなので、build と同じ順で 2 段に引く。
    """
    from keiyaku.build import assign_caption_labels
    from keiyaku.lint.walk import iter_texts

    captions = assign_caption_labels(draft, index.ctx)
    actual: dict[str, str] = {}
    for owned in iter_texts(draft):
        if not owned.rich:
            continue
        for token in iter_tokens(parse(owned.text)):
            if not isinstance(token, Ref):
                continue
            key = f"{owned.owner_id} -> {token.target} [{token.mode}]"
            if token.target in index:
                actual[key] = resolve_ref(index, owned.owner_id, token.target, token.mode)
            else:
                actual[key] = captions[token.target]
    assert actual, "サンプルに {ref:} が 1 つも無い"
    assert any(" -> fig_" in k or " -> tbl_" in k for k in actual), "表・図の参照が 1 つも無い"
    _compare(actual, GOLDEN_REFS, update_golden)


def test_番号付けの警告が出ない(draft, index: DocumentIndex) -> None:
    assert index.ctx.warnings == []
