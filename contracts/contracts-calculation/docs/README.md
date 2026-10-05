# docs/ — contracts-calculation の文書索引

ルートの 4 文書が正本、本ディレクトリは調査・レビュー・決定の記録を置く。

## ルート（正本。場所を動かさない）

| 文書 | 役割 |
|---|---|
| `../README.md` | **入口**。何を作るか・本体への依存・コマンド・計算パックの構成・制限と注意 |
| `../CLAUDE.md` | プロジェクト憲章。守ること（規則1〜13）・現状・コマンド |
| `../DESIGN.md` | 設計の正本（CalcSpec・演算語彙 §12.2・意味論 §12.3・ゲート・パターン） |
| `../TASK.md` | タスク台帳と進捗ログ（§8 は追記のみ） |
| `../PROMPT.md` | 開発を進めるためのプロンプト集（人間が貼る） |
| `../HITL.md` | **人間の意思決定の依頼と記録**（依頼中／親側残作業／決定済み） |

## docs/（記録。新しい決定は `decisions.md` に 1 行足す）

| 文書 | 内容 |
|---|---|
| `decisions.md` | **決定の記録の一元台帳**（日付／決定／決め手／反映先） |
| `data_card.md` | **データカードの仕様・計画・タスク**（`<data>/data-card.md` の正本。節と数値の出所・母数検出・自動更新） |
| `hf_publish.md` | **Hugging Face 公開形の仕様**（何を出さないか・許可リスト・公開前ゲート P1〜P6・ライセンス） |
| `milestones_archive.md` | 完了済みマイルストーン（M0〜M6・MH5）のタスク詳細表（TASK.md 0.1 版から移設） |
| `m0_survey.md` | M0 調査の所見（DESIGN §3.1 前提 7 件・§17 事項 1〜9 の実物照合） |
| `m2_review.md` | 生成文書の PNG 目視レビュー（T2.9）と改善余地のその後 |
| `dataset_review.md` | **`dataset/` 100文書の全文・意味・名称レビュー**（2026-10-05。修正事項と最終検証） |
| `m4_bindings.md` | 付与モードの調査（本体 20 件の 4 条項の実態）とバインディングの決定 |
| `h5_handoff.md` | H5（apply 47 問の検算）の人間判断への引き渡しと決定の記録（承認済み） |
| `h5_report.md` | H5 検算の判定レポート（**生成物**。手で編集しない） |
| `h5_inventory.json` | H5 の 47 問の棚卸し＋機械判定（**生成物**） |

## コードに隣接する文書・生成物

- `../src/contracts_calculation/h5/` — H5 検算の実体：`specs.py`（47 問の CalcSpec の正本）・
  `verify.py`（検算器）。再生成は
  `PYTHONPATH=src uv run --project .. python -m contracts_calculation.h5.verify`
  （→ `h5_report.md`・`h5_inventory.json` を本ディレクトリに書き出す）。
- `../examples/` — 回帰基準 3 文書（生成物。`scripts/update_examples.py` で更新）。
- `../data/<profile>/`・`../data_bind/` — v1 データセット（HITL HC-2 の構成：4 プロファイル × 20 base ＝
  80 文書＋付与のみ 20 件。生成物。コミットしない＝`.gitignore` 済み）。
- `<data>/README.md`（datasheet）と `<data>/data-card.md`（データカード）— どちらも実測から生成する。
  仕様は `data_card.md`、実装は `../src/contracts_calculation/export/`（`datasheet.py`・`datacard.py`）、
  測り方の独立検算は `../scripts/verify_data_card.py`。**手で編集しない。**
- `../dataset/` — ユーザー指示の 100 件セット（standard29・hard29・challenge20・basic22、seed1〜6。
  生成物。コミットしない）。
