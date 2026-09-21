---
paths:
  - "yakkan/render/**"
  - "yakkan/layout/**"
  - "yakkan/verify/**"
  - "yakkan/numbering.py"
  - "styles/**"
  - "scripts/probe_*.py"
---

# 描画・レイアウト抽出のルール

- 着手前に `docs/rendering.md`（旧 CLAUDE.md §6）を読む。
- CLAUDE.md §14 と `docs/rendering.md` で「要probe」と書かれた挙動は、必ず `scripts/probe_*.py` で実測してから設計を確定し、結果を `docs/decisions.md` と `docs/gotchas.md` に記録する。憶測で実装しない。
- 単位：WeasyPrint は CSS px、PDF は pt（×0.75）、PNG は dpi/72 倍。**原点は常に左上**。
- 正解に出る要素にはすべて `id` と `data-kind` を付ける。見出しは label span と title span を分離する。
- SVG の `<text>` には `font-family` と `font-size` を必ず明示する（省略するとフォールバックで幅見積りがずれる）。
- 失敗は黙って縮めない。ページ超過・はみ出し・描画漏れは例外を投げて止める。
