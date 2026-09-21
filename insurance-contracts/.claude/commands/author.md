---
description: 1文書を執筆する（CLAUDE.md §7.2 の 1〜4）。引数は content_id、未作成なら --genre で新規 scaffold
argument-hint: <content_id> [--genre <genre>] [--seed <n>]
---

# /author $ARGUMENTS

CLAUDE.md §7.2 の執筆プロトコルを進めます。

1. `docs/style_guide.md` と `blueprints/<genre>.yaml` を読む。
2. `content/<content_id>/` が無ければ `uv run yakkan scaffold --genre <genre> --content-id <content_id> --seed <n>`。
3. `content/<content_id>/parts/*.json` を **1 part ずつ** 埋める。
   part が 3 つ以上あれば `author` サブエージェントに part 単位で委譲してよい（並列可）。
   委譲するときは「どの part か」「そのジャンルの必須要素」「既に決まっている用語と数値」を渡す。
4. `uv run yakkan lint content/<content_id>` を通す。error 0 になるまで直す。
5. `uv run yakkan build content/<content_id>`。

**守ること**：番号ラベルを書かない／転載しない／固有名詞は架空／`_todo` は埋めたら消す。

終わったら「埋めた part ／ lint の結果 ／ 残った TODO」を報告してください。
