# 本体 lint の `id(draft)` キャッシュで、実在する条が「所属先が無い」と出る

- 日付: 2026-10-03
- 影響: 本体 lint の L02 が**間欠的に**誤った error を出し、拡張の生成が落ちる
- **状態: 直した（2026-10-03・S10-1）。** `HITL.md` H6 (c) で人が承認したので本体を変更した。
  本体 `yakkan/lint/walk.py` の `_ARTICLE_CACHE` を廃止し、条の種別表を走査ごとにローカルで作る。
  本体 `docs/decisions.md` に記録済み。**拡張側の実行時回避（`_clear_stale_lint_cache`）は削除した。**
- 確認: 再現スクリプトで `_ARTICLE_CACHE` が無いこと・id の再利用（60 回中 24 回）が影響しないことを確認。
  本体 `ruff` 緑・`pytest` 433 件緑。拡張 `pytest tests` を **5 回連続**で 228 件緑

## 現象

脚注を持つ条を足した文書で、`yakkan.lint.runner.lint_draft` が次を報告することがある。
**同じ入力でも、報告されるときとされないときがある。**

```
[error] L02 <ch3_a8_p2.text>: {fn:1} の所属先が無い（脚注は条または別表の末尾に置く）
[error] L02 <ch3_a8>: 脚注 1 が本文から参照されていない
```

その文書の構造は正しい。`ch3_a8_p2`（項）は `ch3_a8`（条）の子で、`ch3_a8` は
`{"type": "footnotes", "id": "fn_ch3_a8"}` を持つ。既定の約款にある脚注（`fn_ch1_a1` など）と同じ形である。

## 原因

`yakkan/lint/walk.py`:

```python
_ARTICLE_CACHE: dict[int, dict[str, str]] = {}


def _nearest_article(ancestors, draft):
    kinds = _ARTICLE_CACHE.setdefault(id(draft), {})  # ← キーが id(draft)
    if not kinds:
        for node, _ in iter_nodes(draft.body + draft.appendices):
            kinds[node.id] = node.kind
    ...
```

キーが **`id(draft)`（オブジェクトのアドレス）** で、キャッシュは一度も消されない。
Python は回収したオブジェクトのアドレスを**再利用する**ので、1 つのプロセスで文書をいくつも
lint すると、**別の文書のために作られた対応表**が当たる。古い表に無い条（＝拡張が足した条）は
「条ではない」と判定され、その中の `{fn:n}` が「所属先が無い」になる。

## 再現

```python
import gc
from pathlib import Path
from yakkan.compose import load_draft
from yakkan.lint import walk

seen, collisions = {}, 0
for i in range(60):
    d = load_draft(Path("content/auto-0001"))
    walk._nearest_article(("ch3",), d)  # この draft のキャッシュを作る
    if id(d) in seen:
        collisions += 1
    seen[id(d)] = i
    del d
    gc.collect()
print(collisions, "回 id が再利用された /", len(walk._ARTICLE_CACHE), "件がキャッシュに残っている")
# → 27 回 id が再利用された / 33 件がキャッシュに残っている（draft は 1 つも生きていない）
```

## どう直したか（2026-10-03・S10-1）

キャッシュを**持たない**ことにした。`_nearest_article` は対応表を引数で受け取り、
`iter_blocks` と `iter_texts` が走査の冒頭で `_node_kinds(draft)` を 1 回作る。

```python
def _node_kinds(draft: SourceDraft) -> dict[str, str]:
    return {node.id: node.kind for node, _ in iter_nodes(draft.body + draft.appendices)}


def _nearest_article(ancestors: tuple[str, ...], kinds: dict[str, str]) -> str | None:
    for ancestor in reversed(ancestors):
        if kinds.get(ancestor) in FOOTNOTE_OWNER_KINDS:
            return ancestor
    return None
```

`WeakKeyDictionary` や `LintContext` でも直せるが、**両関数はもともと全ノードを走査している**ので、
都度作っても計算量は変わらない。状態を持たないのがいちばん安全である。

## 拡張側の対処（**削除済み**）

直す前は `base_adapter.lint` が本体 lint を呼ぶ直前に `walk._ARTICLE_CACHE` を空にしていた。
本体を直したので**この回避は不要になり、削除した**。`base_adapter.lint` は本体をそのまま呼ぶだけである。
`base_adapter` 以外から本体を触らない決まり（`tests/unit/test_discipline.py`）はそのまま守っている。
