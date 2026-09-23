# CLAUDE.md — yakkan-synth：日本語保険約款 合成データ生成プロジェクト

> 本ファイルは Claude Code が毎セッション読み込む「プロジェクト憲章 兼 仕様書」である。
> 設計判断・規約・作業手順はここに集約し、実装と食い違ったら **実装ではなく本ファイル（または docs/）を先に直す**。
> 記法：`MUST`＝必須、`SHOULD`＝原則、`MAY`＝任意、`要probe`＝実装前に小さな検証スクリプトで挙動確認が必要。

## 0. 最初に読むこと（Claude Code への指示）

### 0.1 一行要約
「本物そっくりだが完全に架空の日本語保険約款」を **正解JSON → PDF** の順で生成し、ドキュメント読み取り（テキスト／章節項構造／表／図の構造と意味）の開発検証用データセットを作る。1文書 **20ページ以下**。JSON が唯一の真実（single source of truth）であり、PDF はその決定論的な描画結果である。

### 0.2 セッション開始時の手順
1. 本ファイルを読む。次に `docs/decisions.md`（設計変更履歴）と `docs/progress.md`（進捗・次の一手）を読む。存在しなければ §12 の P0 から着手する。**`HITL_TODO.md` に人間待ちの項目がある場合、そこに挙がった判断を AI が代わりに下さない**（push・公開・架空性や転載の最終確認など）。
2. `uv run yakkan doctor` で環境（Python・WeasyPrint・フォント・poppler）を確認する（P0 完了後）。
3. 作業は §12 のフェーズ順。フェーズをまたぐ設計変更は `docs/decisions.md` に「日付／変更／理由／影響」を追記してから行う。
4. 終了前に `make check`（lint + pytest）を通し、`docs/progress.md` を更新する。
5. 触る領域に対応する `docs/*.md`（§0.3 の表）を着手前に読む。読まずに実装しない。

### 0.3 本ファイルの運用ルール
- 詳細仕様は 2026-09-21 に `docs/` へ分割した。本ファイルには要約とパス参照だけを残す。**該当領域を触る作業では、着手前に必ず対応する docs を読む。**

  | 触るもの | 先に読む |
  |---|---|
  | `yakkan/models.py` `build.py` `richtext.py` `schema/` `content/` `dataset/` | `docs/schema.md` |
  | `yakkan/render/` `layout/` `verify/` `numbering.py` `styles/css/` | `docs/rendering.md` |
  | `content/` の執筆・`library/clauses/`・QA 執筆 | `docs/style_guide.md` ＋ `docs/authoring_checklist.md` |
  | `blueprints/` `styles/` `yakkan/scaffold.py` `compose.py` | `docs/blueprints.md` |
  | 構造分析・参考URL の扱い | `docs/reference_structures.md` |
  | ファイル新規作成・配置 | `docs/repo_layout.md` |
  | 評価ハーネス・予測 JSON の形 | `docs/evaluation.md` ＋ `docs/eval_dataset_plan.md` |
  | lint ルールの詳細・検査ロジック | `docs/lint_rules.md` |
  | 設計変更／進捗／環境の癖 | `docs/decisions.md` `docs/progress.md` `docs/gotchas.md` |

- **`@docs/...` の import は使わない。** import されたファイルは launch 時に全文がコンテキストへ展開され、分割の目的（毎セッションのコンテキスト削減）が失われる（Claude Code memory 仕様、2026-09-21 に公式ドキュメントで確認）。参照は必ずバッククォート付きのパス表記で書く。
- 小さな恒常ルールは `.claude/rules/*.md` に置く。frontmatter の `paths:` で対象を限定すると、一致するファイルを読んだときだけ読み込まれる（現行仕様で利用可、同日確認）。`paths:` の無いルールは毎セッション読み込まれるので、常時必要なものに限る。
- 同じ修正指示を2回受けたら、その内容を本ファイルか `.claude/rules/` に追記する。
- 環境固有の発見（ライブラリの癖、コマンドの落とし穴）は auto memory に任せず `docs/gotchas.md` に書く。
- 本ファイルは**250行以内**とする（2026-09-23 に再分割・確認）。超えそうなら docs へ移す。ただし §0・§2・§8・§11・§12・§14 は要約せずに残す。

### 0.4 絶対に守ること（Hard rules）
1. **転載禁止**：参考URL（§3.2）の実在約款の文章を、部分的にも、語順を変えただけでも、リポジトリに入れない。参考にするのは **構造・要素の種類・レイアウト慣行のみ**。生成文はすべてオリジナルに書く。
2. **完全架空**：会社名・商品名・連絡先・URL・様式番号・人物名は架空。実在保険会社名は `yakkan/lint/denylist.txt` で検出し lint で落とす。URL は `example.jp` / `example.co.jp` / `example.com` のみ。電話番号は `0120-000-000` 形式のゼロ埋めのみ。
3. **JSON が真実**：PDF に現れる文字列（ヘッダ・フッタ・ページ番号・目次のページ番号・図中の文字を含む）は、すべて `source.json` から機械的に導出できなければならない。PDF や HTML の手編集は禁止。`dataset/` 配下は生成物であり手で書き換えない。
4. **決定論**：同じ `content_id`・`style_id`・`seed`・依存バージョンなら、バイト単位で同一の JSON と同一のテキスト層を持つ PDF を再生成できること（PDF のメタデータ日時は固定値を埋める）。
5. **ページ上限**：表紙を含め 20 ページ以下。超えたら生成失敗として扱う（`docs/rendering.md`）。
6. **正解の完全性**：レンダリング後、PDF のテキスト層と JSON の期待テキストは正規化後に一致すること（`docs/rendering.md`）。一致しない文書はデータセットに入れない。
7. **検証は視覚でも行う**：新ジャンル・新スタイルの初回は必ずページ PNG を自分の目で確認する（§11 `review`）。ページ数と lint が通っても崩れていることはある。
8. 秘密情報・API キーをコミットしない。ネットワーク取得は参考URLと公式パッケージのみ。

## 1. プロジェクト概要（成果物・制約）

ドキュメント読み取りシステム（OCR/レイアウト解析/VLM/構造化抽出）の開発では、実在の約款は著作権・正解データ不在・ページ数過多の問題がある。そこで実在約款の **構造的特徴を忠実に再現した合成文書** と **完全な正解データ** を対で生成し、テキスト／章節項構造／表／図／参照関係／質問応答の6観点を検証可能にする（観点ごとの正解表は `docs/schema.md` 冒頭）。

成果物（1文書あたり、`dataset/<doc_id>/` 配下）：`source.json`（執筆内容＋構造＋意味。derivedはbuildが付与）／`layout.json`（bbox・読み順・ヘッダ/フッタ文字列）／`answer.json`（ページ別テキスト＋アウトライン）／`qa.json`（評価用問答）／`doc.pdf`（テキスト層あり）／`pages/page-*.png`（150dpi）／`render.html`（デバッグ用・配布対象外）。全文書の一覧は `dataset/manifest.json`。

制約：1文書20ページ以下（§0.4-5）。日本語横書きのみ（縦書きはv1対象外、§14）。生成はClaude Codeセッション内で完結（外部LLM APIは使わない）。
非目標（v1）：スキャン劣化画像の生成（P6任意）、実在商品の再現・比較、読み取りモデル自体の実装。

## 2. 設計原則

1. **Content / Layout の分離**：`source.json` はスタイル非依存（A4/B5、段組、フォントを変えても不変）。`layout.json` はレンダリングごとに再生成。同一 `content_id` を複数 `style_id` で描画し、レイアウト頑健性のデータを安価に増やす。
2. **番号は書かせず、計算する**：「第１条」「（２）」「①」などのラベルは執筆者（Claude）が書かず、ツリー位置と番号方式から build 時に導出する。条項間参照は `{ref:ID}` トークンで書き、解決文字列は build が生成する。これで通し番号のずれ・参照切れを構造的に排除する。
3. **見出しラベルと文言を分離保持**：正解では「第１条」（label）と「告知義務」（title）と「第１条（告知義務）」（heading_text）をすべて持つ。読み取り側の粒度差を評価可能にする。
4. **表は論理グリッド＋意味の二重表現**：`grid`（結合セル込みの見た目構造）と `records`／`header_path`（意味）を両方持つ。
5. **図は自前レイアウトの SVG**：外部レイアウトエンジン（Graphviz 等）を使わず、JSON に格子座標を持たせて決定論的に SVG 化。ノード座標が正解として自明に得られる。
6. **In-flow レイアウトのみ**：float・絶対配置を本文に使わない（欄外注は例外）。文書順＝読み順を保証する。
7. **失敗は早く・明示的に**：lint → build → render → verify の各段で停止。黙って縮小・省略しない。
8. **架空でも一貫**：金額・日数・等級・別表番号は文書内で矛盾しない（§8）。

## 3. 対象ドキュメントの特徴（実在約款の構造分析）

実在約款から抽出した「読み取り課題カタログ」を A〜F の6群に整理してある。**詳細は `docs/reference_structures.md`。構造設計・執筆・描画のいずれの作業でも着手前に必ず読む。**

- **A 前付け**：表紙／目的別もくじ／特約一覧表／ペットネーム対応表 等　**B 本文の階層**：最大7階層、条末脚注、欄外解説、側注の用語解説、別紙・別表の独立番号体系
- **C 表**：定義表／保険金一覧（算式入り）／免責列挙／等級表／プラン比較マトリクス／2段ヘッダ　**D 図**：構成ツリー／対応ステップ／受取りまでの流れ／タイムライン／手続きフロー
- **E 装飾**：2段組、左右異ヘッダ、丸数字・記号、囲み注意書き、商品名バッジ　**F 体裁**：F1素組み／F2標準／F3解説冊子。**生成ではF1とF2のみ再現し、F3のイラストは作らない**

参考URLの一覧・**転載禁止**の運用・分析ログは `docs/reference_structures.md` §3.2。読んでよいのは構造把握のためだけで、文章はメモにも残さない（§0.4-1）。

## 4. ジャンル定義と設計図（blueprint）

`blueprints/<genre>.yaml` に各ジャンルの骨組み・必須要素・分量・番号方式・バリエーション候補を宣言し、`yakkan scaffold` がそこから執筆用スケルトンを生成する。

| genre | 名称 | 目標ページ | 段組（既定） | 番号方式 | 文体 |
|---|---|---|---|---|---|
| `auto` | 総合自動車保険 約款（しおり抜粋付き） | 14–20 | 2段 | nonlife | 敬体 |
| `oneday` | 1日型自動車保険 約款 | 8–12 | 1段/2段 | nonlife | 敬体 |
| `quake` | 地震保険 約款 | 10–14 | 2段 | nonlife | 敬体 |
| `health` | 傷害・疾病保険（からだの保険）約款 | 14–20 | 2段 | nonlife | 敬体 |
| `life` | 生命保険 ご契約のしおり＋約款 | 16–20 | 1段 | life | 敬体 |
| `teikan` | 保険会社 定款 | 6–10 | 1段 | teikan | 常体 |
| `travel` | 海外旅行保険 約款 | 10–16 | 1段/2段 | nonlife | 敬体 |
| `golf` | 賠償責任保険 約款集（ゴルファー保険） | 12–18 | 2段（横長小型判） | nonlife | 敬体 |
| `group` | 団体保険 普通保険約款＋特約条項 | 12–18 | 1段／横向きA4 2段 | group | 敬体 |
| `jyusetsu` | 重要事項説明書（**条を持たない**） | 8–12 | 1段 | jyusetsu | 敬体 |

ジャンルごとの必須要素・番号方式の細目・条見出し／条末脚注の体裁・`variants`・style プリセット7種の全仕様は **`docs/blueprints.md`**（旧付録A/B含む）。blueprint・style・scaffold を触る作業では着手前に必ず読む。

## 5. データモデル（正解JSON）→ 詳細は `docs/schema.md`

**`yakkan/models.py` `build.py` `richtext.py` `schema/` `content/` を触る作業では、着手前に必ず読む。**

- 3層＋QA：`source.json`（執筆内容・スタイル非依存）／`layout.json`（bbox・読み順）／`answer.json`（ページ別期待テキスト＋outline。source/layoutは内包しない）／`qa.json`。`Node` は `title` のみ持ち番号ラベルは持たない。
- RichText の許可トークンは `{ref:}` `{fn:n}` `{term:}` `{b:}` `{u:}` `{ruby:}` `{br}` のみ。未知トークン・番号ラベル直書きは lint エラー。
- 表は `grid`（見た目）と `records`／`header_path`（意味）の二重表現。図は6種の `Diagram` ＋ `alt` ＋ `facts`。`derived` は build が付与し執筆時は書かない。
- QA は11種別（`apply`＝場面適用を含む）。bbox は pt・原点左上を主とし、正規化 [0,1] を併記する。

## 6. レンダリングパイプライン → 詳細は `docs/rendering.md`

**`yakkan/render/` `layout/` `verify/` `numbering.py` `styles/` を触る作業では、着手前に必ず読む。**

- Jinja2 → HTML → **WeasyPrint（>=62・版固定）** → PDF。検証は pdfplumber＋pypdfium2（PyMuPDFはAGPLのため不使用）。図は自前Python→インラインSVG。
- 正解要素には `id`／`data-kind` を付け、box ツリー（私的API・要probe）から bbox を取る（CSS px→pt ×0.75、原点左上）。
- `target-counter`・`leader()`・`column-span: all`・`float: footnote` は要probe。**`<ruby>` と `transform` 回転は実測済み＝使わない**（§14）。
- verify：ページ数≤20／フォント被覆／テキスト往復一致／目次ページ一致／はみ出し・重なり無し／決定論。**超過・はみ出しは失敗として停止**する。

## 7. コンテンツ生成（執筆）→ 詳細は `docs/style_guide.md`

**執筆・`library/clauses/`・QA 作成の作業では、着手前に必ず `docs/style_guide.md` ＋ `docs/authoring_checklist.md` を読む。**

- 役割分担：Python が骨組み・番号・参照・目次・ヘッダ経路・lint・描画・検証・自動QA、Claude が条文本文・定義・表の中身・図のノード・脚注・欄外注・alt/facts・執筆QA。
- 執筆プロトコル：`scaffold` → part ごとに執筆 → `lint` → `build` → `render` → `verify` → `review`（PNG を目視）→ `qa` → `manifest update`。CSS/テンプレート修正は全文書に影響するため `docs/decisions.md` に記録してから再レンダリングする。
- 文体：nonlife は敬体、life はしおり部が平易な敬体＋Q見出し・約款部が条文体、teikan は常体。
- 架空化：会社名・商品名・連絡先・様式番号・人物名は架空（§0.4-2）。法令は名称のみ引用し条番号は書かない。奥付に disclaimer を必ず入れる（ページごとには入れない）。
- 条文ライブラリの文もオリジナル。同一ジャンル3文書以上では題材を変え、`lint --similarity` で重複率30%超を警告する。
- **`docs/authoring_checklist.md`**：P4-c で7文書をreviewerに通して得た「lintが通っても残る欠陥」の一覧（転載の指紋・goldの誤り・表と条文の空振り・定数の衝突ほか）。新ジャンル・新スタイルの初回は全ページを目視する。

## 8. 整合性ルール（`yakkan lint`）
| # | ルール | 重大度 |
|---|---|---|
| L00 | スキーマ検証（型・未知フィールド・**執筆物への `derived` 混入**） | error |
| L01 | id 一意、`{ref:}`/`anchor`/`evidence` の参照先存在 | error |
| L02 | `{fn:n}` と同一条の `footnotes.n` の双方向対応、未使用脚注なし | error |
| L03 | 見出し・本文に番号ラベル直書き（`第[0-9０-９]+条`、行頭の `（[0-9０-９]+）`、`^[①-⑳]`）なし | error |
| L04 | blueprint の必須要素・最小件数を満たす | error |
| L05 | 表：全行の列数（結合展開後）が一致、`header_rows/cols` が grid 内、`records` の値が grid に出現 | error |
| L06 | 図：edges の端点存在、格子座標重複なし、最小複雑度、alt・facts 非空 | error |
| L07 | フォント被覆（cmap） | error |
| L08 | denylist 語句、`example` 以外のドメイン、ゼロ埋め以外の電話番号 | error |
| L09 | 推定ページ数 ≤ 19（目標超過は warning、20 超は error） | error/warn |
| L10 | 文体：genre の敬体/常体一致（文末形の統計で判定）、`digit_style` 違反（全角半角混在） | warn |
| L11 | 数値整合：同一の限度額・日数・等級が本文・表・図で一致（`meta.constants` に宣言し `{const:key}` で参照させると強制可） | warn |
| L12 | 定義語：`defined_terms` に無い `{term:}`、定義されたが一度も使われない語 | warn |
| L13 | 奥付 disclaimer 存在、meta 必須項目 | error |
| L14 | QA：型と answer の整合、evidence の存在、extract 系の answer が evidence テキストに含まれる | error |
| L15 | 類似度：既存 content との文単位重複 > 30% | warn |
| L16 | 執筆 QA の件数と観点の配り方（15 問・表 3・図 3・apply 1 以上） | error |
| L17 | 表の `header_cols` が行見出し（`role: stub`）の列を覆っている | error |
| L18 | 列挙用に組んだ表（`semantic_type: enumeration/exclusions`）に `caption` を付けない | error |

各ルールの検査ロジック・実装上の注意点は `docs/lint_rules.md`。

## 9. 評価用QAと評価ハーネス → 詳細は `docs/evaluation.md`

**評価データとしての充足性のレビューと改修の経緯は `docs/eval_dataset_plan.md`。**

- `yakkan eval dataset/<doc_id> --pred pred.json`：読み取りの採点。予測 JSON の形は `schema/prediction.schema.json`。突合は中身で行う（予測に内部 id は無い前提）。
- 指標：ページ別 CER、outline の F1、構造位置 citation の正解率、表 TEDS・セル F1、図のノード/エッジ/経路 F1、読み順の Kendall τ、QA の完全/部分一致。
- `yakkan eval --search-run run.json`：検索の採点（nDCG@k・Recall@k・MRR）。`--oracle` で自己評価。
- `yakkan export`：評価向けの派生成果物を書き出す（`elements.jsonl`・`passages.jsonl`・`dataset/search/*`）。

## 10. リポジトリ構成 → 詳細は `docs/repo_layout.md`

**ファイルを新規作成・移動する作業では、着手前に必ず読む。** 要点だけ：仕様は `CLAUDE.md` ＋ `docs/`、宣言は `blueprints/` `styles/` `library/clauses/`、実装は `yakkan/`。執筆成果 `content/<content_id>/` は**コミットする**。生成物 `dataset/<doc_id>/` はコミットせず `specs/` から再生成する。Claude Code 用設定は `.claude/`。

## 11. コマンドとワークフロー
```
uv sync                                   # 依存導入
uv run yakkan doctor                      # 環境チェック（Pango, fonts, poppler 不要, pdfium）
uv run yakkan schema export               # schema/*.schema.json
uv run yakkan scaffold --genre <g> --content-id <cid> --seed <n>
uv run yakkan lint content/<cid> [--similarity]
uv run yakkan build content/<cid>
uv run yakkan render content/<cid> --style <sid> [--report]   # → dataset/<cid>--<sid>/
uv run yakkan verify dataset/<doc_id>
uv run yakkan review dataset/<doc_id>     # pages/*.png 出力（Claude が画像を開いて確認）
uv run yakkan qa dataset/<doc_id> [--validate]
uv run yakkan batch specs/batch_v1.yaml   # 上記を一括（失敗文書は manifest に failed として記録）
uv run yakkan export                      # elements.jsonl / passages.jsonl / dataset/search/*
uv run yakkan eval dataset/<doc_id> --pred pred.json   # 読み取りの採点（--oracle で自己評価）
uv run yakkan eval --search-run run.json  # 検索の採点
uv run yakkan manifest update
uv run yakkan manifest check          # manifest が実ファイルと合っているか（make check にも入っている）
uv run pytest -q ; uv run ruff check . ; make check
```
- スラッシュコマンド `/author <content_id>`：§7 の執筆プロトコルを対話的に進める。`/review <doc_id>`：PNG を開き `docs/authoring_checklist.md` で採点、修正案を parts に反映。`/batch <spec>`：バッチ生成と失敗の切り分け。
- subagent：`author`（part 執筆、文体ガイドと blueprint を読み込む）、`reviewer`（本物らしさ・整合性を採点、写し疑いを指摘）、`render-debugger`（WeasyPrint の崩れを最小再現 HTML で切り分け）。
- hooks（`.claude/settings.json`）：`*.json` 保存後に `yakkan lint --quick`、`rm -rf dataset` 等の破壊操作は確認、`dataset/` の手編集を禁止する PreToolUse。

## 12. マイルストーンと完了条件（DoD）
| フェーズ | 内容 | DoD |
|---|---|---|
| **P0 環境** | uv 初期化、依存固定、フォント同梱、`doctor`、日本語 A4 2段組 1ページの smoke PDF | `make check` が通る。`docs/gotchas.md` に WeasyPrint の版・Pango の版を記録 |
| **P1 モデル** | pydantic モデル、JSON Schema、numbering、richtext、lint L01–L03/L07/L08/L13 | 単体テスト。サンプルが lint を通り、ラベル解決の golden テストあり |
| **P2 レンダラ** | テンプレート・CSS、表（結合・表頭繰返し）、目次（target-counter）、ヘッダ/フッタ、脚注、bbox 抽出、verify | 手書きの小サンプル（3ページ）で往復一致・目次ページ一致・決定論を確認。`docs/decisions.md` に renderer 確定を記録 |
| **P3 図** | 6種の Diagram → SVG、figure_layout、最小複雑度 lint | 各種 1 点ずつのサンプル図が PNG で崩れなく描ける |
| **P4 コンテンツ** | blueprints 7 種、条文ライブラリ、scaffold/compose、`docs/reference_structures.md`、**各ジャンル 1 文書**を執筆 | 7 文書が verify/review を通り manifest に ready |
| **P5 QA・バッチ** | 自動 QA、執筆 QA、manifest、`specs/batch_v1.yaml`（7 genre × 3 content × 1–2 style ≈ 30 文書） | 全文書 ready。失敗率と原因を `docs/progress.md` に記録 |
| **P6 拡張** | style 追加、ルビ・縦書きセル・欄外注ページ下配置、スキャン風画像（任意）、eval ハーネス | 各機能に verify とテスト。データセット v1 を tag |

各フェーズの終了時に `docs/progress.md` を更新し、次フェーズの最初の 3 タスクを書いておく。

## 13. コーディング規約・テスト
- Python 3.12、`ruff`（format + lint）、型ヒント必須、`pydantic` モデル外で dict を裸で回さない。乱数は `random.Random(seed)` を明示的に受け渡す。`datetime.now()` を生成物に入れない。
- テスト：`tests/unit`（numbering・richtext・lint・header_path・diagram layout）、`tests/golden`（許容誤差 0.5pt で比較、PDF テキスト層の一致）、`tests/render_smoke`（各 style で 1 ページ）。golden 更新は `--update-golden` を明示し、差分理由をコミットメッセージに書く。
- コミット単位：フェーズ内の機能単位。生成物 `dataset/` はコミット対象外（`specs/` から再生成可能にする）。`content/` はコミットする。

## 14. 既知の落とし穴（Gotchas）— 発見したら `docs/gotchas.md` へ追記
- WeasyPrint の box ツリー（`_page_box`、`box.element`）は私的 API。版を固定し、`scripts/probe_weasy.py` で `element id → bbox` が取れることを確認してから設計を確定する。
- 単位：WeasyPrint は CSS px、PDF は pt（×0.75）。PNG は dpi/72 倍。原点は左上に統一（pdfplumber の `top` 系を使う）。
- 表頭繰り返し・ヘッダ/フッタは PDF テキスト層に同じ文字列が複数回出る。正解側で `repeated`／`header/footer` として区別し、往復比較の前に除外する。
- 2段組では 1 要素が 2 fragments に割れる。段の境界は `layout.pages[].columns` と bbox から判定。
- `column-span: all`、`leader()`、`float: footnote`、`target-counter` はいずれも要probe。非対応なら代替（段組コンテナ分割、点線罫、条末配置、二段階レンダリング）に切り替え、`docs/decisions.md` に記録。`<ruby>` は実測済みで**使わない**（読みがテキスト層に混ざりルビにもならない）。
- 縦書き（`writing-mode: vertical-*`）は WeasyPrint 非対応。**`transform` での回転も入れない**（`scripts/probe_rotate.py` で実測：box が縮まず字がセルの外に出る。`docs/decisions.md`）。
- 丸数字・黒丸数字・☞ などの記号はフォントによって欠ける。L07 のフォント被覆検査を render 前に必ず実行。
- 長い欧文（URL、型式番号）だけが段からはみ出す。`overflow-wrap: break-word` をそれらの span に限定適用。
- SVG 内テキストのフォント指定漏れでフォールバックフォントに変わり、幅見積りと実描画がずれる。SVG `<text>` には常に `font-family`/`font-size` を明示。
- 表が段幅より広いと WeasyPrint は黙ってはみ出す。verify のはみ出し検査で検出し、`span_columns` か列数削減で対処。
- **段組の中に収まらない段またぎ要素（`column-span: all` の見出し・`span_columns: true` の表）があると、WeasyPrint は「それ以降の内容」を黙って捨てる。** 60字の加筆で16→11ページになり第5章以降が全部消えた実例がある。対処として (1) 章見出し・別表見出しを `column-span: none` にし、(2) `render` が内容欠落を検出したら停止するようにした。**この renderer に対しては「レンダリングが成功した」は「内容が全部載った」を意味しない。**
- PDF の再現性：`write_pdf` のメタデータ（CreationDate 等）を固定しないとバイト差分が出る。テキスト層一致を必須、バイナリ一致を目標とする。

## 15. 決定事項（確定）

- データセット規模（v1）：約30文書。7ジャンル × 3 content、うち各ジャンル1 contentは2スタイルで描画
- `travel` の題材：海外旅行保険（参考URL #5 の実物で確認済み）
- 縦書き：v1対象外。P6で表見出しの回転のみ
- ルビ：作らない（`scripts/probe_ruby.py` で実測。ルビとして組まれず読みがテキスト層に混ざる）
- スキャン風劣化画像：P6の任意項目。v1では作らない
- PDFのタグ付け（tagged PDF）：作らない
- QAの言語・件数：日本語、自動生成30問＋執筆15問／文書
- 正解bboxの座標系：pt・原点左上を主とし、正規化[0,1]を併記
- 配布形式：`dataset/` ディレクトリ ＋ `manifest.json`
- 実在法令：法令名のみ引用し、条番号は書かない
- Python／パッケージ管理：Python 3.12／uv

未決・仮決めの経緯、決定に至った実測結果は `docs/decisions.md` を見る。新たな未決事項が出たら既定値で進めたうえで同ファイルに「仮決め」として記録する。

## 付録

style プリセット・blueprint YAML の形は `docs/blueprints.md`、lint 個別ルールの実装詳細は `docs/lint_rules.md` に移設した。
