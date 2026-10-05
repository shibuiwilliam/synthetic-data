---
description: 生成済み文書をレビューする（CLAUDE.md §7・docs/authoring_checklist.md）。引数は doc_id
argument-hint: <doc_id>
---

# /review $ARGUMENTS

`dataset/<doc_id>/` を点検します。詳しい指示文は `PROMPT.md` §5（P3-4）。

1. `uv run keiyaku verify dataset/<doc_id>` を実行し、error と warn を**すべて読む**（warn を残して次に進まない）。
2. `dataset/<doc_id>/pages/*.png` を **全ページ自分で開いて** 見る。
   `docs/authoring_checklist.md` §5〜§7・§12 の観点：当事者の取り違え／記名押印欄と当事者表示の一致／
   頭書と本文の値／別紙の空振り／後文と記名欄の分離／様式型の選択欄／disclaimer／
   表の列幅・結合・はみ出し／図の重なり／記号の豆腐。
3. `reviewer` サブエージェントに `source.json`（あれば PNG も）を渡し、整合性・本物らしさ・**写し疑い**を採点させる。
4. 崩れがあれば `render-debugger` サブエージェントに切り分けさせる。**憶測で CSS を触らない。**
5. 直すときは **原則 content（parts）を直す**。CSS やテンプレートを直す場合は全文書に影響するので、
   `docs/decisions.md` に理由を記録してから再レンダリングする。

報告は「verify の結果 ／ 目視で見つけたもの ／ reviewer の指摘のうち採ったもの・採らなかったもの（理由） ／
直したもの ／ 残課題」の順で。
