# yakkan-synth — 日本語保険約款の合成データ生成基盤

実在の保険約款そっくりだが **完全に架空** の日本語文書（PDF）と、その **完全な正解データ**（JSON）を
対で生成する。ドキュメント読み取りシステム（OCR / レイアウト解析 / VLM / 構造化抽出）の開発検証用。

- 正解 JSON が唯一の真実で、PDF はその決定論的な描画結果（JSON → HTML → PDF）。
- 1 文書 20 ページ以下。テキスト・章節項構造・表・図・参照関係・QA を正解として持つ。
- 仕様は `CLAUDE.md`（憲章）と `docs/`（詳細）。**実装と食い違ったら仕様側を先に直す。**

## セットアップ

必要なもの：Python 3.12（uv が入れる）、[uv](https://docs.astral.sh/uv/)、Pango。

```bash
# macOS
brew install pango
# Ubuntu
sudo apt install libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz0b libffi-dev

uv sync            # 依存の導入（= make setup）
make doctor        # 環境の検査（Python / WeasyPrint / Pango / フォント / pypdfium2）
make check         # ruff + pytest
make smoke         # 動作確認用の PDF と PNG を scratch/smoke/ に生成
```

### macOS の注意

Homebrew の dylib は dyld の既定検索パスに無いため、素の `uv run` では WeasyPrint の import が失敗する。
`make` 経由なら `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が自動で渡る。直接叩くときは自分で付ける。

```bash
DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib uv run yakkan doctor
```

詳細と他の落とし穴は `docs/gotchas.md`。

## ディレクトリ

| パス | 中身 |
|---|---|
| `CLAUDE.md` | プロジェクト憲章（ハードルール・設計原則・lint 一覧・マイルストーン） |
| `docs/` | 詳細仕様（schema / rendering / style_guide / blueprints / repo_layout）と運用ログ（decisions / progress / gotchas） |
| `yakkan/` | Python パッケージ（モデル・番号付け・描画・レイアウト抽出・検証・QA・CLI） |
| `blueprints/` `styles/` `library/` | ジャンル定義・スタイル・条文ライブラリ（宣言） |
| `content/<content_id>/` | 執筆成果（コミットする） |
| `dataset/<doc_id>/` | 生成物（コミットしない。`specs/` から再生成する。**手編集禁止**） |
| `assets/fonts/` | 同梱フォント（OFL / IPA ライセンス。出典は `SOURCES.md`） |

## 主なコマンド

```bash
make help                              # ターゲット一覧
uv run yakkan doctor                   # 環境検査
make doc CONTENT=auto-0001 STYLE=nl-a4-2col-mincho   # 1 文書の生成（P2 以降）
make batch SPEC=specs/batch_v1.yaml    # バッチ生成（P5 以降）
```

## ライセンスと架空性

生成される文書の会社名・商品名・連絡先・様式番号はすべて架空で、実在の保険会社・商品とは関係がない。
参考にした実在約款は **構造のみ**（見出し階層・表の列構成・図の種別）で、文章は一切引用していない。
同梱フォントのライセンスは `assets/fonts/SOURCES.md` を参照。
