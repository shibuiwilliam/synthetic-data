---
description: 生成済み文書をレビューする（CLAUDE.md §7.2 の 5〜7）。引数は doc_id
argument-hint: <doc_id>
---

# /review $ARGUMENTS

`dataset/<doc_id>/` を点検します。

1. `uv run yakkan verify dataset/<doc_id>` を実行し、error と warn をすべて読む。
2. `dataset/<doc_id>/pages/*.png` を **全ページ自分で開いて** 見る。
   §7.8 のチェックリスト（見出しのぶら下げ／表の列幅・結合・表頭繰返し・はみ出し／
   図の重なりと矢印／段の高さと孤立行／ヘッダ・フッタ・目次のページ番号／記号の豆腐／情報密度）。
3. `reviewer` サブエージェントに `source.json` を渡し、本物らしさ・整合性・**写し疑い**を採点させる。
4. 崩れがあれば `render-debugger` サブエージェントに切り分けさせる。憶測で CSS を触らない。
5. 直すときは **原則 content（parts）を直す**。CSS やテンプレートを直す場合は全文書に影響するので、
   `docs/decisions.md` に理由を記録してから再レンダリングする。

報告は「verify の結果 ／ 目視で見つけたもの ／ 直したもの ／ 残課題」の順で。
