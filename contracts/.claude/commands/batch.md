---
description: バッチ生成と失敗の切り分け（CLAUDE.md §11）。引数は spec ファイル
argument-hint: <specs/batch_v1.yaml>
---

# /batch $ARGUMENTS

1. spec を読み、生成する content × style × seed の組を確認して件数を報告する。
   **2 style 目は「版面が最も遠いもの」を選んでいるか**を確かめる（同系を重ねても頑健性の検証にならない）。
2. `uv run keiyaku batch <spec>` を実行する。
3. 失敗した文書を **原因の種類ごとに** まとめる。
   - lint 落ち → どのルールか（content の問題。執筆で直す）
   - 内容欠落 → `PROMPT.md` §9 の D-3。**検出を無効化して進めない**
   - ページ数超過 → `keiyaku render --report` で章ごとの使用ページを見て、削る場所を示す
   - 描画の崩れ・描画漏れ → `render-debugger` に委譲
   - `RenderLayoutError` → WeasyPrint のページ分割不具合。内容を数十字増減するか style を変える
     （docs/gotchas.md。**自動でレイアウトをずらす回避はしない**）
4. `uv run keiyaku manifest update` で manifest を更新する。
5. `docs/progress.md` に失敗率と原因の内訳を記録する。

詳しい指示文は `PROMPT.md` §6（P6-1）。

報告は「成功／失敗の件数 ／ 原因の内訳 ／ 次に直すもの」の順で。
