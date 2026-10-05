---
description: 1文書を執筆する（CLAUDE.md §7 の執筆プロトコル）。引数は content_id、未作成なら --doctype で新規 scaffold
argument-hint: <content_id> [--doctype <doctype>] [--seed <n>]
---

# /author $ARGUMENTS

CLAUDE.md §7 の執筆プロトコルを進めます。詳しい指示文は `PROMPT.md` §5（P3-2 / P3-3）。

1. `docs/style_guide.md` と `docs/authoring_checklist.md`、`blueprints/<doctype>.yaml` を読む。
2. `content/<content_id>/` が無ければ
   `uv run keiyaku scaffold --doctype <doctype> --content-id <content_id> --seed <n>`。
3. `content/<content_id>/parts/*.json` を **1 part ずつ** 埋める。
   part が 3 つ以上あれば `author` サブエージェントに part 単位で委譲してよい（並列可）。
   委譲するときは「どの part か」「その doctype の必須要素」「既に決まっている用語・当事者・数値」を渡す。
   **委譲中は共有コード（CSS・テンプレート・`keiyaku/`）を触らない。**
4. `uv run keiyaku lint content/<content_id>` を error 0 / warn 0 にする。
5. `uv run python scripts/fill_records.py content/<content_id> --write`（結合セルのある表は手で書く）。
6. `uv run keiyaku build content/<content_id>`。

**守ること**：番号ラベル・当事者呼称・表図番号・別紙番号を直書きしない（build / `{party:}` / `{ref:}` が
解決する）／転載しない／固有名詞は架空／`_todo` は埋めたら消す。

終わったら「埋めた part ／ lint の結果 ／ 残った TODO ／ 当事者の義務配分を確認したか」を報告してください。
