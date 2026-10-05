# CLAUDE.md — keiyaku-synth：日本語ビジネス契約書 合成データ生成プロジェクト

> 本ファイルは Claude Code が毎セッション読み込む「プロジェクト憲章 兼 仕様書」である。
> 設計判断・規約・作業手順はここに集約し、実装と食い違ったら **実装ではなく本ファイル（または docs/）を先に直す**。
> 記法：`MUST`＝必須、`SHOULD`＝原則、`MAY`＝任意、`要probe`＝実装前に小さな検証スクリプトで挙動確認が必要。
>
> 姉妹プロジェクト（いずれも `../` にある。本プロジェクトから書き換えない）：
> - `../insurance-contracts/`（yakkan-synth）＝保険約款専用・**実装完済**。**本プロジェクトのコード供給元**。
>   評価ハーネス・盲検読み取り検証まで到達済み。実証済みの設計・実測結果は**再検証せず継承する**。
> - `../structured-docs/`（docsynth）＝その汎用化・**仕様のみ**。`contract` ファミリーの設計
>   （`{party:}`・signature・別紙・課題カタログ G1〜G13・lint L19・評価/検証計画）は**仕様として取り込む**。
>   正解スキーマは docsynth 互換に保ち、将来 `families/contract` として切り出せる形を崩さない（§15）。

---

## 0. 最初に読むこと（Claude Code への指示）

### 0.1 一行要約
「本物そっくりだが完全に架空の日本語ビジネス契約書」（秘密保持・業務委託・売買・賃貸借・ライセンス・
請負・雇用 ほか **10 doctype**）を **正解JSON → PDF** の順で生成し、ドキュメント読み取り
（テキスト／条項構造／表／図／参照関係／当事者／QA）の開発検証用データセットを作る。
JSON が唯一の真実（single source of truth）であり、PDF はその決定論的な描画結果である。

### 0.2 セッション開始時の手順
1. 本ファイルを読む。次に **`TASK.md`（`contracts/` 全体の計画と残作業の入口）**・
   `docs/decisions.md`（設計変更履歴）・`docs/progress.md`（進捗）を読む。
   **`HITL_TODO.md` に依頼中の項目がある場合、そこに挙がった判断を AI が代わりに下さない**
   （コミット・公開・範囲の決めごと・架空性や転載の最終確認など）。
   判断待ちでも、依存しない作業（`TASK.md` §2.2）は進めてよい。
2. `uv run keiyaku doctor` で環境（Python・WeasyPrint・Pango・フォント・pdfium）を確認する（P0 完了後）。
3. 作業は §12 のフェーズ順。フェーズをまたぐ設計変更は `docs/decisions.md` に「日付／変更／理由／影響／状態」を
   追記してから行う。
4. 終了前に `make check`（ruff + pytest + manifest 鮮度）を通し、`docs/progress.md` を更新する。
5. 触る領域に対応する `docs/*.md`（§0.3 の表）を着手前に読む。**読まずに実装しない。**

### 0.3 本ファイルの運用ルール
- 詳細仕様は `docs/` に分割してある。**該当領域を触る作業では、着手前に必ず対応する docs を読む。**

  | 触るもの | 先に読む |
  |---|---|
  | yakkan からの移植・モジュール構成・境界 | `docs/architecture.md` |
  | `keiyaku/models.py` `build.py` `richtext.py` `schema/` `content/` `dataset/` | `docs/schema.md` |
  | `blueprints/` `numbering/` `styles/` `keiyaku/scaffold.py` `compose.py` | `docs/doctypes.md` |
  | `keiyaku/render/` `layout/` `verify/` `numbering.py` `styles/css/` | `docs/rendering.md` |
  | `content/` の執筆・`library/clauses/`・QA 執筆 | `docs/style_guide.md` ＋ `docs/authoring_checklist.md` |
  | `samples/` の構造分析・参考文書の扱い | `docs/reference_structures.md` |
  | `keiyaku/eval/` `export.py` `search_set.py` 予測 JSON | `docs/evaluation.md` |
  | データセットの検証・硬化（読み取り検証・HITL） | `docs/validation_plan.md` |
  | **データカード（`dataset/data-card.md`）の生成・節の追加** | **`docs/data_card.md`** |
  | **データセットの公開（Hugging Face）・`keiyaku/publish.py`・`specs/publish.yaml`** | **`docs/publishing.md`** |
  | **何を次にやるか・残作業の状態** | **`TASK.md`**（`contracts/` 全体。サブプロジェクトの細目は `contracts-calculation/TASK.md`） |
  | **人間の判断が要ること** | **`HITL_TODO.md`**（依頼・記録・管理。サブ固有は `contracts-calculation/HITL.md`） |
  | フェーズの詳細タスク・依存 | `docs/plan.md` |
  | lint ルールの実装位置・検査ロジック | `docs/lint_rules.md` |
  | ファイル新規作成・配置 | `docs/repo_layout.md` |
  | 設計変更／進捗／環境の癖 | `docs/decisions.md` `docs/progress.md` `docs/gotchas.md` |

- **`@docs/...` の import は使わない。** import されたファイルは launch 時に全文がコンテキストへ展開され、
  分割の目的（毎セッションのコンテキスト削減）が失われる（yakkan-synth 2026-09-21 に公式ドキュメントで確認）。
  参照は必ずバッククォート付きのパス表記で書く。
- 開発を進めるための指示文（フェーズ別・デバッグ別・サブエージェント用）は `PROMPT.md` にある。
  **人間が貼るものなので本ファイルから import せず、参照だけにとどめる。**
- 小さな恒常ルールは `.claude/rules/*.md` に置き、frontmatter の `paths:` で対象を限定する。
- 同じ修正指示を2回受けたら、その内容を本ファイルか `.claude/rules/` に追記する。
- 環境固有の発見（ライブラリの癖、コマンドの落とし穴）は auto memory に任せず `docs/gotchas.md` に書く。
  **`../insurance-contracts/docs/gotchas.md` の全項目は本プロジェクトでも有効**として扱う（§14）。
- 本ファイルは **350 行／35KB 以内を目安**とする（yakkan 240 行・28KB、docsynth 288 行・27KB。本プロジェクトは
  doctype が 10 種あり §4・§8・§15 の表が長い）。超えそうなら docs へ移す。ただし §0・§2・§8・§12・§15 は
  要約せずに残す。**現状は 390 行・36KB で目安を超えている**（`docs/decisions.md` 26）。
  次に足すときは §8 の lint 表を `docs/lint_rules.md` へ全面移送して戻す。

### 0.4 絶対に守ること（Hard rules）
1. **転載禁止**：`samples/` に集めた実在のひな型・標準契約書・モデル契約書の文章を、部分的にも、語順を変えた
   だけでも、リポジトリに入れない。参考にしてよいのは **構造・要素の種類・レイアウト慣行のみ**。生成文はすべて
   オリジナルに書く。**「公的機関のひな型だから著作権はない」と判断しない。** 模倣は文章より先に
   「**数値の列・列挙の順序・別表特有の語形**」に出る（`docs/style_guide.md` §2）。
2. **完全架空**：会社名・屋号・商品名・人物名・住所・連絡先・URL・契約書番号・様式番号・物件名は架空。実在名は
   `keiyaku/lint/denylist.txt` で検出し lint で落とす。URL は `example.jp` / `example.co.jp` / `example.com`
   のみ。電話番号はゼロ埋め（`0120-000-000` `03-0000-0000`）のみ。実在の法令・裁判所・官公庁は**名称のみ**
   引用可、**法令の条番号は書かない**（§15）。
3. **JSON が真実**：PDF に現れる文字列（ヘッダ・フッタ・ページ番号・目次・図中の文字・頭書・記名押印欄・収入
   印紙欄の文字を含む）は、すべて `source.json` から機械的に導出できること。PDF/HTML の手編集禁止。
   `dataset/` は生成物であり手で書き換えない（掃除も `keiyaku clean` で行う）。
4. **決定論**：同じ `content_id`・`style_id`・`seed`・依存バージョンなら、バイト単位で同一の JSON と同一の
   テキスト層を持つ PDF を再生成できること（PDF メタデータ日時は固定値を埋める）。
5. **ページ上限**：doctype の blueprint が定める上限（既定 12・絶対上限 20）以下。超えたら生成失敗として扱う。
   **フォント縮小・自動省略で押し込まない。**
6. **正解の完全性**：PDF のテキスト層と JSON の期待テキストは正規化後に一致すること。一致しない文書はデータ
   セットに入れない。**「レンダリング成功」は「内容が全部載った」を意味しない**——内容欠落検出を無効化しない（§14）。
7. **検証は視覚でも行う**：新 doctype・新スタイルの初回は必ず全ページの PNG を自分の目で確認する
   （`keiyaku review`）。ページ数と lint が通っても崩れていることはある。
8. **当事者は書かせず計算する**：「甲」「乙」「委託者」等の呼称を本文に直書きしない。`{party:}` トークンで書き、
   build が解決する（番号ラベルと同じ原則。§5・L19）。
9. 秘密情報・API キーをコミットしない。ネットワーク取得は参考URLと公式パッケージのみ。

---

## 1. プロジェクト概要

背景（実在の契約書が抱える著作権・機密性・正解データ不在の問題）は `README.md`。

### 1.1 成果物（1文書あたり。`dataset/<doc_id>/`、`doc_id` = `<content_id>--<style_id>`）
`source.json`（内容＋構造＋意味。`derived` は build が付与）／`layout.json`（bbox・読み順・ヘッダ/フッタ）／
`answer.json`（ページ別期待テキスト＋outline。source/layout は内包せず `load_answer` で結合）／`qa.json`／
`elements.jsonl`（1 行 1 要素の平索引）／`doc.pdf`（テキスト層あり）／`pages/page-*.png`（150dpi）／
`render.html`（デバッグ用・配布対象外）。全体では `dataset/manifest.json`・`dataset/search/`
（passages/queries/qrels）・`dataset/README.md`（読み方 ＝ **Hugging Face のデータセットカード**。
frontmatter つき）・`dataset/views/*.jsonl`（Viewer 用の平らな射影）・`dataset/licenses/`・
`dataset/SHA256SUMS`（以上は `keiyaku publish` の生成物。`docs/publishing.md`）・**`dataset/data-card.md`**
（データカード＝規模・内訳・作り方・品質保証・制限と偏り・ライセンス）。**後 2 つは export が
実測値を埋め込んで生成する**——固定文字列に統計値を焼き込まない（`docs/data_card.md`）。

### 1.2 制約と非目標（v1）
- 日本語横書きのみ。生成は Claude Code セッション内で完結（骨組み・検証・描画は Python、本文の執筆は Claude）。
  **外部 LLM API は使わない。**
- 非目標：印影・手書き署名・スキャン劣化画像／縦書き・ルビ（yakkan で実測のうえ不採用）／
  実在ひな型の再現／**法的に有効な契約書**（生成物は読み取り検証用のダミーであり、実務に使えない）／
  読み取りモデル自体の実装（検証用の読み取りは `docs/validation_plan.md` の範囲のみ）。

---

## 2. 設計原則

yakkan-synth の 8 原則を**そのまま継承**する：
(1) Content / Layout の分離（`source.json` はスタイル非依存）、(2) **番号は書かせず計算する**、
(3) 見出しラベルと文言を分離保持（`第1条` / `秘密保持` / `第1条（秘密保持）`）、
(4) 表は論理グリッド＋意味の二重表現（`grid` と `records`／`header_path`）、
(5) 図は自前レイアウトのインライン SVG、(6) In-flow レイアウトのみ（文書順＝読み順）、
(7) 失敗は早く・明示的に（lint → build → render → verify の各段で停止。黙って縮小・省略しない）、
(8) 架空でも一貫（金額・期間・当事者・別紙番号が文書内で矛盾しない）。

追加原則：

1. **実証済みは再検証しない**：renderer（WeasyPrint 70.0 固定）・bbox 抽出・probe 実測 22 項目・gotchas は
   yakkan の結論を継承する。挙動が疑わしいときだけ probe を書く。
2. **当事者も「計算する」**：呼称（甲/乙/委託者…）は `meta.parties` に宣言し、本文は `{party:}` で書く。
   呼称の揺れ・取り違えを構造的に排除する（§5・L19）。
3. **契約書固有の知識も宣言に置く**：doctype ごとの必須要素・番号方式・文体・意味種別は `blueprints/`・
   `numbering/`・`styles/` の YAML に宣言し Python に書かない。**将来 docsynth の `families/contract/` として
   切り出せる形を保つ**（§15）。正解形式（`source/layout/answer/qa`・評価向け成果物）も
   `../structured-docs/docs/schema.md` に合わせ、読み取り側が同じローダで扱えるようにする。
4. **基準は機械に落とす**：文章で書いただけの品質基準は守られない（yakkan では 30 content のうち 13 が執筆 QA
   基準に違反していた）。執筆・正解の要件は可能な限り lint / verify / テストにする。
5. **検証は文脈を持たない読み手まで**：自セッションの読み取りでは踏まない「契約の穴」がある
   （yakkan：自読 3 本では 0 件、盲検 3 本では 2 本で発見）。doctype 群ごとに盲検読み取りを通す。

---

## 3. 対象ドキュメントの特徴（実在契約書の構造分析）

`samples/`（公的機関・業界団体・法律事務所が公開する 36 種・39 ファイル。出典は `samples/SOURCES.md`）を
**構造だけ**分析し、「読み取り課題カタログ」（CT1〜）として `docs/reference_structures.md` にまとめる。
**構造設計・執筆・描画のいずれの作業でも着手前に必ず読む。** 判明している大枠：

- 版面は **A4 縦がほぼ全数**（実測 39 ファイル中 38）。例外は国交省の物品購入契約書様式の **A3 縦**（297×420mm）1 件。
- ページ数は **2〜66**（大半は 10 以下。逐条解説つきモデル契約が 24〜33、IPA アジャイル版が 66。
  経産省モデル契約書は 205＝複数の契約書と解説の合本）。**生成対象は「契約書本体」**であり、
  解説書全体ではない（§4 の目標ページ）。
- 骨格は 5 類型に落ちる：**条文型**（大多数）／**頭書型**（冒頭に当事者・目的物・金額の一覧表）／
  **様式型**（条を持たず記入欄が本体。労働条件通知書）／**約款型**（章立て・長文・公共工事標準請負契約約款）／
  **逐条解説型**（条文＋解説枠が交互。特許庁・INPIT のモデル契約）。
- 参考文書の取り扱い（**転載禁止**の運用・分析ログの型・`samples/` をコミットしない理由）は
  `docs/reference_structures.md` §0。読んでよいのは構造把握のためだけで、**文章はメモにも残さない**。

---

## 4. doctype（契約書の種類）

`blueprints/<doctype>.yaml` が骨組み・必須要素・分量・番号方式・バリエーション候補を宣言し、
`keiyaku scaffold` がそこから執筆用スケルトンを生成する。**全 10 doctype が v1 のスコープ**。
必須要素・variants・style 割当の全仕様は **`docs/doctypes.md`**。

| doctype | 名称 | 参考 | 骨格 | 目標ページ | 番号方式 |
|---|---|---|---|---|---|
| `nda` | 秘密保持契約書 | `samples/nda/` | 条文型（最小） | 3–6 | contract-standard |
| `outsourcing` | 業務委託契約書 | `samples/outsourcing/` | 条文型＋別紙 | 5–10 | contract-standard |
| `delegation` | 準委任・作業委任契約書 | `samples/work_delegation/` | 条文型 | 4–8 | contract-standard |
| `consulting` | コンサルティング・顧問契約書 | `samples/consulting/` | 条文型 | 4–8 | contract-standard |
| `purchase` | 売買・物品購入契約書 | `samples/purchase/` | 条文型＋目録（**頭書** variant・A3横は P8） | 3–8 | contract-standard |
| `lease` | 建物賃貸借契約書 | `samples/lease/` | **頭書型**＋別表 | 8–14 | contract-standard |
| `license` | ライセンス契約書（特許・商標・ノウハウ） | `samples/license/` | 条文型＋実施料表（**逐条解説** variant） | 6–12 | contract-standard |
| `sysdev` | システム開発（基本）契約書 | `samples/system_development/` | 章立て・基本契約＋個別契約 | 8–16 | contract-standard |
| `contracting` | 工事・製造請負契約書 | `samples/contracting/` | **約款型**（**章なし**・長文・漢数字） | 10–18 | contract-kanji |
| `employment` | 雇用契約書・労働条件通知書 | `samples/employment/` | **様式型**（条を持たない・**記名押印欄なし**） | 2–6 | contract-form |

- 文体は blueprint の `tone` が宣言する。**既定は常体**だが、`license` `purchase` `employment` は**敬体**も実在する
  （P1 の実測。`docs/decisions.md` 63）。`employment` の様式型は体言止め・名詞句が主体。L10 は宣言に従って判定する。
- 番号方式は宣言的な `numbering/<scheme>.yaml`（階層ごとのカウンタ書式・参照解決規則）で定義する。
  v1 は 3 方式：`contract-standard`（条「第1条（見出し）」・**全編通し番号**／項は算用数字・第1項無番号／
  号「(1)」／細目「ア」）、`contract-form`（**条を持たない**。項目「1」→「(1)」→「(ア)」の 3 階層）、
  `contract-kanji`（約款型。**条番号が漢数字**「第一条」。CT23。**実装済み**。枝番 CT24 は P8）。
- style プリセットは初期 3 種（`docs/doctypes.md` §7）。1 content を 1〜2 style で描画する。

---

## 5. データモデル（正解JSON）→ 詳細は `docs/schema.md`

**`keiyaku/models.py` `build.py` `richtext.py` `schema/` `content/` を触る作業では、着手前に必ず読む。**

- yakkan-synth の 3層＋QA・`Node`・`Block`・RichText・表の二重表現・図 6 種＋正規化グラフ・`derived` を
  継承し、`genre` → `family`（固定値 `contract`）＋`doctype` に置き換える（`schema_version: "2.0"`）。
- 契約書のための追加：`Node.kind` に `preamble`（前文）・`head_matter`（頭書）・`signature`（後文＋記名押印欄）・
  `schedule`（別紙・別表・様式）・`supplement`（附則）。`Block` に `parties`（当事者表示）・
  `revision_history`（改定履歴）・`commentary`（逐条解説）。
- RichText 追加トークン **`{party:<key>}`**（`|name` 正式名称・`|full`「株式会社◯◯（以下「甲」という。）」型・
  `|role` 役割名）。
  既存トークン（`{ref:}` `{fn:n}` `{term:}` `{const:}` `{b:}` `{u:}` `{br}` `{auto_label}`）は不変。
- 表の `semantic_type` は「コア共通語彙 ＋ 契約書登録語彙」（`fee_schedule` `deliverables` `inventory`
  `head_matter` `form_fields` `allocation`）の 2 層。**列挙用の表に `caption` を付けない**（L18）。
- QA は yakkan の 11 種別を継承（`apply` は執筆専用）。bbox は pt・原点左上を主とし、正規化 [0,1] を併記。

---

## 6. レンダリングパイプライン → 詳細は `docs/rendering.md`

**`keiyaku/render/` `layout/` `verify/` `numbering.py` `styles/` を触る作業では、着手前に必ず読む。**

- Jinja2 → HTML → **WeasyPrint 70.0（版固定）** → PDF。検証は pdfplumber＋pypdfium2（PyMuPDF は AGPL のため
  不使用）。図は自前 Python → インライン SVG。
- **yakkan で実害から確定した描画規約を最初から採用する**（`.ttf` フォント同梱／目次リーダー罫は `leader(' ')`＋
  点線下線・**`leader('.')` と `border-bottom` は禁止**／目次は 2 パス描画／表題は `<table>` の `<caption>`／
  ヘッダの章名は `string(chapter, first)`／`page_number: dashed` ほか）。
- 契約書固有の描画：当事者表示・記名押印欄（枠と「印」の文字のみ。**印影画像は作らない**）・収入印紙欄・頭書の
  大型表・様式型のチェックボックス（☑ □ は L07 の被覆検査対象）・逐条解説枠。
- verify：ページ数上限／フォント被覆（＋**CFF 埋め込み無し**）／テキスト往復一致／目次ページ一致／全要素 ≥1
  fragment／はみ出し・重なり無し／決定論／記名欄と `meta.parties` の一致（V-P1）／**目次を持たない文書では
  目次検査をスキップした旨をレポートに明記**（V-P3。黙って通さない）／**結合セルがページ境界をまたがない**
  （V11。またぐと継続ページの列が空欄になり、正解データのほうが誤りになる。`docs/gotchas.md`）。

---

## 7. コンテンツ生成（執筆）→ 詳細は `docs/style_guide.md`

**執筆・`library/clauses/`・QA 作成の作業では、着手前に必ず `docs/style_guide.md` ＋
`docs/authoring_checklist.md` を読む。**

- 役割分担：Python が骨組み・番号・当事者呼称・参照・目次・ヘッダ経路・lint・描画・検証・自動QA、Claude が
  条文本文・定義・表の中身・図のノード・脚注・逐条解説・alt/facts・執筆QA。組み立ては `scripts/authoring.py`
  （**検証はしないので書いたら必ず lint**）。
- 執筆プロトコル：`scaffold` → part ごとに執筆 → `lint` → `fill_records` → `build` → `render` → `verify` →
  `review`（全ページ PNG を目視）→ `qa` → `manifest update`。CSS/テンプレート修正は全文書に影響するため
  `docs/decisions.md` に記録してから再レンダリングする。
- 執筆者が**書いてはいけないもの**：番号ラベル（「第1条」「(1)」「①」）、当事者呼称（「甲」→`{party:client}`）、
  表・図番号（「表2」→`{ref:tbl_x}`）、別紙番号（「別紙1」→`{ref:sch1}`）、`derived`、目次、ページ番号。
- 架空化・転載の指紋・文体・密度要件・QA の型の選び方は `docs/style_guide.md` §2〜§5。奥付に disclaimer を必ず
  入れる（ページごとには入れない）。同一 doctype の複数文書では題材・当事者・章構成・数値を変え、
  `lint --similarity`（文単位重複 30% 超で警告）を執筆完了ごとに実行する。

---

## 8. 整合性ルール（`keiyaku lint`）

**yakkan の最終形 L00–L18 を番号・意味とも互換で継承し、L19〜L21 を新設**（実装位置は `docs/lint_rules.md`）。

| # | ルール | 重大度 |
|---|---|---|
| L00–L09 | スキーマ検証（**執筆物への `derived` 混入**・doctype の存在）／id 一意と `{ref:}`・`anchor`・`evidence` の参照先存在（**空文字に解決される参照も error**）／脚注の双方向対応と**配置**（`{fn:n}` より前に描かれない）／**番号ラベルと当事者呼称の直書き禁止**（検出パターンは numbering YAML＋`meta.parties` の alias から生成）／blueprint の必須要素（**構造で縛り、semantic_type で題材を縛らない**）／表の格子・`records` 整合／図の端点・複雑度・alt/facts／フォント被覆（☑ □ ㎡ を含む）／denylist・ドメイン・電話番号／推定ページ数 ≤ `page_limit` | error（L09 の目標超過のみ warn） |
| L10–L15 | 文体（常体・`digit_style`）／数値整合（金額・日数・期間が本文・表・頭書・図で一致。`meta.constants`＋`{const:}`）／定義語の未定義使用・未使用定義・**定義文が紙面に現れない**／disclaimer と meta 必須／QA 整合（evidence 存在・extract 系の answer 包含・図の答えの実在）／類似度 >30% | warn（L13・L14 は error） |
| L16 | 執筆 QA の件数と観点の配分（15 問・表 3・図 2・apply 2 以上。blueprint で変更可） | error |
| L17 | 表の `header_cols` が行見出し（`role: stub`）の列を覆っている（**`header_cols == 0` も error**） | error |
| L18 | 列挙用に組んだ表（`semantic_type: enumeration/exclusions`）に `caption` を付けない | error |
| **L19** | **当事者整合**：`{party:}` の key が `meta.parties` に存在し、当事者表示・前文・本文・記名押印欄で呼称と名称が一致 | error |
| **L20** | **契約書の骨格**：`preamble` が body 先頭に 1 つ、`signature` が back_matter に 1 つ、記名欄が `meta.parties` の全当事者を覆う、収入印紙欄は `signature` の中だけ | error |
| **L21** | **逐条解説**：`commentary` は対象条の `anchor` を持ち、対象が実在する（anchor 欠落は error／本文との文の重複は warn） | error/warn |
| **L22** | **表・図の配置**：`table` / `figure` / `formula` は**導入文を持つ項**の `blocks` に付ける（`article` や `chapter` の直下に置くと第1項より前に描画される） | error |
| **L23** | **列挙の入れ子**：同じ親の下に号（`item`）の並びが 2 組以上あるなら、号は**導入する項の `children`** に入れる（兄弟に並べると条の中で通し番号になる） | error |
| **L24** | **置き去りの part**：`parts/*.json` はすべて `doc.json` の `parts` から参照されていること（書き直しの置き去りは未執筆のまま誰にも見えない） | error |
| **L25** | **Markdown の名残**：本文に `**` `__` `` ` `` を書かない（強調は `{b:}` `{u:}`。`**` はそのまま紙面に印字される） | error |
| **L26** | **位置で指す言い方**：番号を持つ表・図は `{ref:}` で指す（「下表」は版面が変われば嘘になる。番号の無い列挙表は対象外） | warn |

---

## 9. 評価用QAと評価ハーネス → 詳細は `docs/evaluation.md`

**yakkan の完成形を P0 で丸ごと移植する**（削って再発明しない）：読み取り 13 指標・検索 7 指標
（＋`recall_ceiling@k`）・`elements.jsonl`・検索評価セット・予測/検索スキーマ・oracle/misread（単調性検査）・
`eval --all`・`manifest check`・`export` の README 自動生成。**予測に使う語彙を文書化する**
（採点は完全一致——語彙が無いと当てようがない）。合格条件は `docs/evaluation.md` §6、
検証の階段は `docs/validation_plan.md`。

---

## 10. リポジトリ構成 → 詳細は `docs/repo_layout.md`

**ファイルを新規作成・移動する作業では、着手前に必ず読む。** 要点：仕様は `CLAUDE.md` ＋ `docs/`、
宣言は `blueprints/` `numbering/` `styles/` `library/clauses/`、実装は `keiyaku/`。
執筆成果 `content/<content_id>/` と `specs/`（バッチ定義）は**コミットしない**（2026-10-05 決定。
`docs/decisions.md` 152）。公開後の第三者は、コードと宣言（`keiyaku/` `blueprints/` `numbering/`
`styles/` `library/`）から `content/`・`specs/` を**自分で生成する**前提とする。生成物 `dataset/` も
同様にコミットしない。
参考 PDF `samples/` は**コミットしない**（`samples/SOURCES.md` だけ残す）。
サブプロジェクト `contracts-calculation/` は**本体のコミットに含めない**（別に扱う。`.gitignore` では
意図的に除外していない）。

---

## 11. コマンドとワークフロー
```
uv sync                                    # 依存導入（= make setup）
uv run keiyaku doctor                      # 環境チェック（Python / WeasyPrint / Pango / フォント / pdfium）
uv run keiyaku doctypes                    # 導入済み doctype と numbering / style の一覧・衝突検査
uv run keiyaku schema export               # schema/*.schema.json
uv run keiyaku scaffold --doctype <d> --content-id <cid> --seed <n>
uv run keiyaku lint content/<cid> [--similarity] [--quick]
uv run python scripts/fill_records.py content/<cid> --write
uv run keiyaku build content/<cid>
uv run keiyaku render content/<cid> --style <sid> [--report]   # → dataset/<cid>--<sid>/
uv run keiyaku verify dataset/<doc_id>
uv run keiyaku review dataset/<doc_id>     # pages/*.png 出力（Claude が画像を開いて確認）
uv run keiyaku qa dataset/<doc_id> [--validate]
uv run keiyaku batch specs/batch_v1.yaml   # 一括（失敗文書は manifest に failed として記録）
uv run keiyaku export                      # elements.jsonl / passages / search / README / data-card.md
uv run keiyaku eval dataset/<doc_id> --pred pred.json   # 採点（--oracle / --misread / --all）
uv run keiyaku eval --search-run run.json  # 検索の採点
uv run keiyaku manifest update|check ; uv run keiyaku datacard update|check
uv run keiyaku publish update|check        # 公開用の面（カード・views・LFS・ライセンス・SHA256SUMS）
uv run python scripts/upload_hf.py         # Hub へ上げる（既定 dry-run。未決なら拒否）
uv run keiyaku clean --stale ; make check          # check は manifest とデータカードの鮮度も見る
```
- スラッシュコマンド `/author <content_id>`（§7 の執筆プロトコルを対話的に進める）、`/review <doc_id>`
  （PNG を開き `docs/authoring_checklist.md` で採点）、`/batch <spec>`。
- subagent：`author`（part 執筆）、`reviewer`（本物らしさ・整合性・**当事者の取り違え**を採点、写し疑いを指摘）、
  `render-debugger`（WeasyPrint の崩れを最小再現 HTML で切り分け）。
- hooks（`.claude/settings.json`）：`*.json` 保存後に `keiyaku lint --quick`、`dataset/` の手編集を禁止する
  PreToolUse、破壊操作の確認。
- **サブエージェントに執筆を任せている間は共有コード（CSS・テンプレート）を触らない**（yakkan の教訓）。

---

## 12. マイルストーンと完了条件（DoD）→ 詳細タスクは `docs/plan.md`

| フェーズ | 内容 | DoD |
|---|---|---|
| **P0 移植** | `../insurance-contracts/yakkan/` → `keiyaku/` をコピー＆改名（**挙動不変**）。評価基盤・`.ttf` フォント・tests・scripts・`.claude/`・Makefile を含む | `make check` 緑、smoke のテキスト層が yakkan と一致、棚卸しが `docs/architecture.md` §5 に記入済み |
| **P1 構造分析** | `samples/` 36 種の**構造のみ**分析 → 課題カタログ CT1〜 と 10 doctype の骨格・5 類型の確定。コード変更なし | 全件の分析ログが `docs/reference_structures.md` に。表現できない構造を decisions に起票 |
| **P2 契約書化** | `doctype`・宣言的 numbering 2 方式・新 kind/Block・`{party:}`・semantic 語彙・lint 再編（L19–L21）・verify 差分・style 3 種 | 単体テスト。numbering の golden（全 kind × 位置のラベルと `{ref:}` 解決）。`keiyaku doctypes` が動く |
| **P3 条文型** | `nda` `outsourcing` `delegation` `consulting`：blueprint と各 1 文書 | 4 文書が lint/verify/review を通り manifest に ready |
| **P4 別紙・目録型** | `purchase` `lease`（頭書）`license`（実施料表）：blueprint と各 1 文書。`head_matter` の描画確定 | 3 文書 ready。頭書 ↔ 本文の値が `{const:}`（L11）で縛れている |
| **P5 様式型・長文型** | `employment`（`contract-form`）`contracting`（約款型）`sysdev`（基本＋個別）：各 1 文書。`commentary` 実装 | 3 文書 ready。条なし・目次なし文書で verify がスキップを明記して通る |
| **P6 データセット v1** | 各 doctype の 2〜3 本目・`specs/batch_v1.yaml`（≈ **40–60 文書**）・自動QA・執筆QA・export | 全文書 ready。`eval --all --oracle` 全満点。`baseline_reader` が全文書で完走 |
| **P7 検証・硬化** | 規則ベース → VLM → 盲検読み取り → HITL（`docs/validation_plan.md`） | `docs/evaluation.md` §6 の 5 条件。`HITL_TODO.md` の全項目に人間の決定。~~v1 タグ~~（H9 で「タグは打たない」と決定） |
| **P8 拡張** | A3 縦 style・2 段組・doctype 追加（保証・代理店・フランチャイズ 等）・docsynth への切り出し検討 | 各機能に verify とテスト |

各フェーズ終了時に `docs/progress.md` を更新し、次フェーズの最初の 3 タスクを書いておく。

---

## 13. コーディング規約・テスト
- Python 3.12、uv、`ruff`（format + lint、line-length 110）、型ヒント必須、pydantic モデル外で dict を裸で回さない
  （評価向け成果物・予測スキーマも pydantic → schema export）。
- 識別子は英語、コメント・docstring・ユーザー向け文字列は日本語可。ログは `logging`、CLI は typer。
  乱数は `random.Random(seed)` を明示的に受け渡す。**`datetime.now()` を生成物に入れない。**
- テスト：`tests/unit`（numbering・richtext・lint・当事者解決・eval 単調性ほか）、
  `tests/golden`（許容誤差 0.5pt、PDF テキスト層の一致）、`tests/render_smoke`（各 style 1 ページ）。
  golden 更新は `--update-golden` を明示し、差分理由をコミットメッセージに書く。
- コミット単位：フェーズ内の機能単位。**「移植」と「契約書化」のコミットを混ぜない**（P0/P2）。

---

## 14. 既知の落とし穴（Gotchas）— 発見したら `docs/gotchas.md` へ追記
**`../insurance-contracts/docs/gotchas.md` の全項目（WeasyPrint 私的API・単位系 px→pt ×0.75・
繰返し表頭・段組 fragments・`column-span` の内容欠落・SVG フォント明示・リーダー罫・CFF フォント・
`RenderLayoutError` の「帯」・macOS の `DYLD_FALLBACK_LIBRARY_PATH` 等）は本プロジェクトでも有効。**
render / layout / verify を触る前に必ず読む。とくに：

- **この renderer では「レンダリングが成功した」は「内容が全部載った」を意味しない。**
  段またぎ要素（`column-span` 見出し・`span_columns` 表）があると以降の内容が黙って捨てられる。
  内容欠落検出（全要素 ≥1 fragment）を無効化しない。
- **フォントは `.ttf`（TrueType 輪郭）を同梱・埋め込む。** `.otf`（CFF）は pdfplumber/pdfium では読めるのに
  macOS の Preview/Quick Look で本文が描画されない（yakkan で 41 文書中 26 文書に発生）。
- 記名押印欄・頭書・様式型の罫線表は**版面をはみ出しやすい**。verify のはみ出し検査を必ず見る。

---

## 15. 決定事項（経緯と仮決めは `docs/decisions.md`）

| 項目 | 決定 | 状態 |
|---|---|---|
| プロジェクト名／パッケージ・CLI 名 | `keiyaku-synth` ／ `keiyaku` | 確定 |
| コード基盤 | `../insurance-contracts/yakkan/` を**コピーして改名**し本ディレクトリで発展させる。yakkan は凍結された参照実装 | 確定 |
| 正解スキーマ | `../structured-docs/docs/schema.md` 互換（`schema_version: "2.0"`、`family: "contract"` 固定＋`doctype`）。将来 `families/contract/` として切り出せる形を保つ | 確定 |
| renderer | WeasyPrint 70.0 固定（yakkan の probe 実測 22 項目を継承・再実測しない） | 確定 |
| フォント | `.ttf`（TrueType 輪郭）版を同梱。`.otf` は出典検証用に併置 | 確定 |
| 評価基盤 | yakkan の完成形を P0 で丸ごと移植 | 確定 |
| v1 の doctype | 10 種（§4 の表） | 確定 |
| 番号方式 | `contract-standard` と `contract-form` の 2 方式 | 仮決め |
| ページ上限 | doctype ごと（既定 12・絶対上限 20）。§4 の目標ページ | 仮決め |
| v1 規模 | 10 doctype × 2–3 content × 1–2 style ≈ 40–60 文書（2026-09-28 に 41 文書で達成） | 確定 |
| 拡張後の規模 | **10 doctype × 5 content × 1〜2 style ＝ 100 文書**（2026-10-05。H10 の決定。`docs/decisions.md` 143）。**style を重ねて数を増やさず content を足す**——同系の style を重ねてもレイアウト頑健性の検証にならない（`docs/doctypes.md` §7） | 確定 |
| 執筆 QA の配分 | 15 問／表 3・図 2・apply 2 以上（契約書は図が少ないため yakkan の「図 3」を 2 に下げ、`apply` を 2 に上げる） | 仮決め |
| 法令引用 | 実在法令・裁判所・官公庁は名称のみ。**法令の条番号は書かない** | 仮決め |
| 印影・手書き・収入印紙 | 印影画像と手書きは描画しない。記名押印欄は枠と「印」、収入印紙欄は枠と文字のみ | 仮決め |
| 縦書き・ルビ・スキャン劣化 | 対象外（yakkan が実測のうえ不採用） | 確定 |
| `samples/` の扱い | リポジトリにコミットしない（`.gitignore`）。`samples/SOURCES.md` だけ残す | 確定 |
| リポジトリへの記録 | **`contracts/` 本体を AI がコミットする**（2026-10-05・H9。`contracts-calculation/` は含めず別扱い。**タグは打たない**）。追跡の対象・非対象は `docs/repo_layout.md` | 確定 |
| `content/`・`specs/` のコミット | **コミットしない**（2026-10-05・ユーザー指示。`docs/decisions.md` 152）。公開後の第三者は独自に生成する前提 | 確定 |
| ライセンス | 同梱フォントは OFL 1.1 / IPA FL v1.0（再配布可）。**コードの宣言（`pyproject.toml` の `Proprietary`）が親リポジトリの `LICENSE`（MIT）と食い違っている**。生成物の配布条件とあわせて **H13** で決める | 未決 |
| データセットの公開先 | **Hugging Face Hub**（`specs/publish.yaml` が宣言。2026-10-05 のユーザー指示。アカウント `cvusk`）。`dataset/` をそのまま上げられる形に `keiyaku publish` が整える（`docs/publishing.md`）。**リポジトリ名・可視性・実行者は H15**、**名義は H16** | 準備完了・公開は未実施 |
| 生成物の配布条件 | **未決（H13）**。`specs/publish.yaml` の `license.id` が `undecided` のあいだ、カードは「未決」と書き frontmatter に `license` を出さず、`scripts/upload_hf.py` は**アップロードを拒否する** | 未決 |
| Python／パッケージ管理 | Python 3.12 ／ uv | 確定 |

新たな未決事項が出たら**既定値で進めたうえで** `docs/decisions.md` に「仮決め」として記録する。
