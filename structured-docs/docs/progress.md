# progress.md — 進捗と次の一手

> セッション終了前に必ず更新する（CLAUDE.md §0.2-4）。
> 形式：フェーズごとの状態＋「次の 3 タスク」。新しい記録を上に足す。

## 現在地

- フェーズ：**P0（移植）未着手**。仕様（CLAUDE.md・docs/）のみ執筆済み（2026-09-22）。
- コード・families/・content/ はまだ無い。

## 次の 3 タスク（P0）

1. `uv init` でプロジェクト初期化（Python 3.12・ruff・pytest・typer・pydantic v2・WeasyPrint 70.0 固定・
   pdfplumber・pypdfium2・fontTools・Jinja2・PyYAML）。Makefile（setup/check/doctor/smoke）を yakkan から移植。
2. `../insurance-contracts/yakkan/` → `docsynth/` へコピー＆リネーム（挙動不変）。tests・scripts・
   `.claude/`・`assets/fonts/`（SOURCES.md 込み）も移植し、`make check` と smoke を通す。
   smoke 出力が yakkan-synth と同一であることを確認。
3. 棚卸し：モジュールごとのドメイン直書き箇所を `docs/architecture.md` §5 の表に記入し、
   P1 の作業リストを確定する。

## フェーズ状態

| フェーズ | 状態 | メモ |
|---|---|---|
| P0 移植 | 未着手 | |
| P1 コア汎用化 | 未着手 | numbering YAML golden が最初の山 |
| P2 同等性（insurance） | 未着手 | oneday・teikan から |
| P3 contract | 未着手 | 着手前に families/contract/docs/structures.md の分析が必要 |
| P4 terms | 未着手 | |
| P5 regulations | 未着手 | |
| P6 データセット v1 | 未着手 | |
| P7 拡張・手順書検証 | 未着手 | |

## 記録

### 2026-09-22
- プロジェクト発足。CLAUDE.md と docs/ 一式（architecture / schema / families / rendering /
  style_guide / reference_structures / repo_layout / decisions / progress / gotchas）を執筆。
- 初期決定 10 件を `docs/decisions.md` に記録（コピー方式・スキーマ互換・v1 ファミリー4種ほか）。
