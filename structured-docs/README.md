# structured-docs (docsynth) — 構造化ドキュメントの合成データ生成基盤

契約書・Webサービス利用規約・社内規程・保険約款などの「本物そっくりだが**完全に架空**」の
日本語文書（PDF）と、その**完全な正解データ**（JSON）を対で生成する。
ドキュメント読み取りシステム（OCR / レイアウト解析 / VLM / 構造化抽出）の開発検証用。

- 正解 JSON が唯一の真実で、PDF はその決定論的な描画結果（JSON → HTML → PDF）。
- コア（`docsynth/`）はドメイン非依存。ドメイン知識は**ファミリー**（`families/`）としてプラグイン化。
- 先行プロジェクト [`../insurance-contracts/`](../insurance-contracts/)（yakkan-synth）の汎用化。
  実証済みの設計・実測結果を継承し、insurance ファミリーの同等性テストで整合を守る。
- 仕様は `CLAUDE.md`（憲章）と `docs/`（詳細）。**実装と食い違ったら仕様側を先に直す。**

## 状態

仕様策定済み・実装は P0（yakkan からの移植）から。現在地は `docs/progress.md`。

## ドキュメント

| ファイル | 中身 |
|---|---|
| `CLAUDE.md` | 憲章：ハードルール・設計原則・ファミリー一覧・lint・マイルストーン |
| `docs/architecture.md` | コア／ファミリーの境界、yakkan 移植方針 |
| `docs/schema.md` | 正解 JSON のデータモデル（yakkan 基底仕様への差分） |
| `docs/families.md` | ファミリー定義仕様と contract / terms / regulations / insurance のカタログ |
| `docs/rendering.md` | レンダリングと検証（WeasyPrint、基底仕様への差分） |
| `docs/style_guide.md` | 執筆ガイド（架空化・文体・チェックリスト） |
| `docs/reference_structures.md` | 実在文書の構造分析の進め方（転載禁止） |
| `docs/repo_layout.md` | ディレクトリ構成 |
| `docs/decisions.md` `progress.md` `gotchas.md` | 運用ログ |

## セットアップ（P0 完了後に有効）

必要なもの：Python 3.12、[uv](https://docs.astral.sh/uv/)、Pango（`brew install pango` / `apt install libpango-1.0-0 …`）。

```bash
uv sync
make doctor        # 環境検査
make check         # ruff + pytest
```

macOS では `make` 経由で `DYLD_FALLBACK_LIBRARY_PATH` が自動で付く（詳細は `docs/gotchas.md`）。

## ライセンスと架空性

生成される文書の会社名・サービス名・人物名・住所・連絡先はすべて架空。
参考にした実在文書は**構造のみ**で、文章は一切引用していない。各文書末尾に架空である旨を明記する。
