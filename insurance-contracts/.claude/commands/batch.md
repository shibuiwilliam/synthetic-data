---
description: バッチ生成と失敗の切り分け（CLAUDE.md §11）。引数は spec ファイル
argument-hint: <specs/batch_v1.yaml>
---

# /batch $ARGUMENTS

1. spec を読み、生成する content × style × seed の組を確認して件数を報告する。
2. `uv run yakkan batch <spec>` を実行する。
3. 失敗した文書を **原因の種類ごとに** まとめる。
   - lint 落ち → どのルールか（content の問題。執筆で直す）
   - ページ数超過 → `yakkan render --report` で章ごとの使用ページを見て、削る場所を示す
   - 描画の崩れ・描画漏れ → `render-debugger` に委譲
   - `RenderLayoutError` → WeasyPrint のページ分割不具合。内容を数十字増減するか style を変える
     （docs/gotchas.md。**自動でレイアウトをずらす回避はしない**）
4. `uv run yakkan manifest update` で manifest を更新する。
5. `docs/progress.md` に失敗率と原因の内訳を記録する。

報告は「成功／失敗の件数 ／ 原因の内訳 ／ 次に直すもの」の順で。
