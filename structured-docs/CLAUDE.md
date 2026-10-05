# CLAUDE.md — docsynth：構造化ドキュメント 合成データ生成プロジェクト

> 本ファイルは Claude Code が毎セッション読み込む「プロジェクト憲章 兼 仕様書」である。
> 設計判断・規約・作業手順はここに集約し、実装と食い違ったら **実装ではなく本ファイル（または docs/）を先に直す**。
> 記法：`MUST`＝必須、`SHOULD`＝原則、`MAY`＝任意、`要probe`＝実装前に小さな検証スクリプトで挙動確認が必要。
>
> **姉妹プロジェクト（いずれも `../` にある。本プロジェクトから書き換えない）**：
> - `../insurance-contracts/`（yakkan-synth）＝保険約款専用・**完済**。`dataset_version: v7`（10 genre・
>   100 content・114 文書・1,458 ページ・QA 5,085）。評価ハーネス・検索評価セットの全面改修・
>   データカード・配布（Hugging Face / CC BY 4.0）まで到達。**本プロジェクトの基底仕様**。
> - `../contracts/`（keiyaku-synth）＝契約書専用・**データセット v1 完成**（10 doctype・50 content・
>   100 文書・657 ページ・QA 4,500）。yakkan を移植したうえで **`family`+`doctype`・宣言的 numbering・
>   `{party:}`・lint L19–L26・verify V01–V11・データカードを実装済み**。本プロジェクトの
>   **コード供給元の第一候補かつ contract ファミリーの参照実装**（`docs/architecture.md` §4・§6）。
>
> **両姉妹で実証済みの設計・実測結果は再検証せず継承する**（§2-1）。疑わしいときだけ probe を書く。

---

## 0. 最初に読むこと（Claude Code への指示）

### 0.1 一行要約
「本物そっくりだが完全に架空の構造化ドキュメント」（契約書・Webサービス利用規約・社内規程・法令・保険約款 等）を
**正解JSON → PDF** の順で生成し、ドキュメント読み取り（テキスト／章条項構造／表／図／参照関係／QA）の
開発検証用データセットを作る。JSON が唯一の真実（single source of truth）であり、PDF はその決定論的な描画結果である。
ドメイン知識は**ファミリー**（§4）としてプラグイン化し、コアはドメイン非依存に保つ。

### 0.2 セッション開始時の手順
1. 本ファイルを読む。次に `docs/decisions.md`（設計変更履歴）と `docs/progress.md`（進捗・次の一手）を読む。
   計画の正本は `docs/plan.md`。
   **コード基盤の切替・push・公開・配布条件・架空性や転載の最終確認など、人間が決めるべき事項は
   AI が代わりに決めない。** 判断待ちの事項に依存しない作業は、それを待たずに進めてよい。
2. `uv run docsynth doctor` で環境（Python・WeasyPrint・Pango・フォント・pdfium）を確認する（P0 完了後）。
3. 作業は §12 のフェーズ順。フェーズをまたぐ設計変更は `docs/decisions.md` に「日付／変更／理由／影響／状態」を
   追記してから行う。
4. 終了前に `make check`（lint ＋ pytest ＋ manifest 鮮度 ＋ データカード鮮度）を通し、`docs/progress.md` を更新する。
5. 触る領域に対応する `docs/*.md`（§0.3 の表）を着手前に読む。**読まずに実装しない。**

### 0.3 本ファイルの運用ルール
- 詳細仕様は `docs/` に分割してある。**該当領域を触る作業では、着手前に必ず対応する docs を読む。**

  | 触るもの | 先に読む |
  |---|---|
  | コア／ファミリーの分離、姉妹からの移植 | `docs/architecture.md` |
  | `docsynth/models.py` `build.py` `richtext.py` `schema/` `content/` `dataset/` | `docs/schema.md` |
  | `families/` 配下すべて（family.yaml・numbering・blueprint・styles） | `docs/families.md` |
  | `docsynth/render/` `layout/` `verify/` `numbering.py` `styles` | `docs/rendering.md` |
  | `docsynth/eval/` `export.py` `search_set.py` 予測 JSON・検索評価セット | `docs/evaluation.md` |
  | **データカード（`dataset/data-card.md`）の生成・節の追加** | **`docs/data_card.md`** |
  | lint 各規則の実装位置と検査ロジック | **`docs/lint_rules.md`** |
  | データセットの検証・硬化（読み取り検証・HITL） | `docs/validation_plan.md` |
  | 執筆・条文ライブラリ・QA 執筆 | `docs/style_guide.md` ＋ **`docs/authoring_checklist.md`** ＋ 対象ファミリーの `families/<f>/docs/` |
  | 実在文書の構造分析・参考URL の扱い | `docs/reference_structures.md` |
  | **生成物の配布・ライセンス表示** | **`docs/distribution.md`**（判断と実行は人間。AI は生成と検査だけ） |
  | フェーズの詳細タスク・依存 | `docs/plan.md` |
  | ファイル新規作成・配置 | `docs/repo_layout.md` |
  | 設計変更／進捗／環境の癖 | `docs/decisions.md` `docs/progress.md` `docs/gotchas.md` |

- **`@docs/...` の import は使わない**（import は launch 時に全文展開され、分割の目的が失われる。yakkan-synth 2026-09-21 確認）。参照はバッククォート付きパス表記で書く。
- 小さな恒常ルールは `.claude/rules/*.md` に置き、frontmatter の `paths:` で対象を限定する。
- 同じ修正指示を2回受けたら、本ファイルか `.claude/rules/` に追記する。
- 環境固有の発見は `docs/gotchas.md` に書く。**姉妹の `../insurance-contracts/docs/gotchas.md` と
  `../contracts/docs/gotchas.md` は本プロジェクトでも全項目有効**として扱う（§14）。
- 本ファイルは**360 行／36KB 以内を目安**とする（ファミリー 5・doctype 26・lint 27 規則で §4・§8・
  §12・§15 の表が伸びるため。yakkan 240 行・keiyaku 350 行）。超えそうなら docs へ移す。

### 0.4 絶対に守ること（Hard rules）
1. **転載禁止**：参考にした実在文書（契約書ひな型・実在サービスの利用規約・実在規程・実在法令・約款）の文章を、部分的にも、語順を変えただけでも、リポジトリに入れない。参考にするのは**構造・要素の種類・レイアウト慣行のみ**。生成文はすべてオリジナルに書く。市販・公開の「ひな型」も著作物として同様に扱い、**「公的機関のひな型だから著作権はない」と判断しない**。法令の条文は著作権の対象外だが同じ規約で扱う（模倣は文章より「数値の列・列挙の順序・別表特有の語形」に出る——`docs/style_guide.md` §2）。参考 PDF は**リポジトリにコミットしない**（出典一覧だけ残す。`docs/reference_structures.md` §0）。
2. **完全架空**：会社名・サービス名・商品名・人物名・住所・連絡先・URL・様式番号・法令題名・自治体名は架空。実在名は `families/<f>/denylist.txt`＋コア共通 denylist で検出し lint で落とす。URL は `example.jp` / `example.co.jp` / `example.com` のみ。電話番号はゼロ埋め（`0120-000-000` `03-0000-0000`）のみ。実在の法令・裁判所は**名称のみ**引用可、法令の条番号は書かない（§15）。
3. **JSON が真実**：PDF に現れる文字列（ヘッダ・フッタ・ページ番号・目次・図中の文字・頭書・署名欄・公布番号を含む）は、すべて `source.json` から機械的に導出できること。PDF/HTML の手編集禁止。`dataset/` は生成物であり手で書き換えない（掃除も `docsynth clean` で行う）。**`dataset/README.md` と `dataset/data-card.md` の統計値も固定文字列に焼き込まず、export が実測して埋める**（両姉妹で焼き込みの事故あり）。
4. **決定論**：同じ `content_id`・`style_id`・`seed`・依存バージョンなら、バイト単位で同一の JSON と同一のテキスト層を持つ PDF を再生成できること（PDF メタデータ日時は固定値）。
5. **ページ上限**：ファミリーの blueprint が定める上限（contract 既定 12・絶対上限 20）以下。超えたら生成失敗として扱う。フォント縮小や自動省略で押し込まない。
6. **正解の完全性**：レンダリング後、PDF のテキスト層と JSON の期待テキストは正規化後に一致すること。一致しない文書はデータセットに入れない。**「レンダリング成功」は「内容が全部載った」を意味しない**——内容欠落検出を無効化しない（§14）。
7. **検証は視覚でも行う**：新ファミリー・新 doctype・新スタイルの初回は必ずページ PNG を自分の目で確認する。ページ数と lint が通っても崩れていることはある（verify で検出できない欠陥が実在する。yakkan X4）。
8. **コアにドメイン知識を入れない**：「甲・乙」「約款」「利用規約」等の語彙・番号方式・必須要素をコアのコードに直書きしない。すべて `families/` の宣言（YAML）または family フックに置く（§2-2）。
9. **番号と当事者呼称は書かせず計算する**：「第1条」「(1)」「甲」を本文に直書きしない。`{ref:}` `{party:}` 等のトークンで書き、build が解決する（§5・L03・L19）。
10. 秘密情報・API キーをコミットしない。ネットワーク取得は参考URLと公式パッケージのみ。**生成物を外部サービス（商用 OCR / VLM API）へ送らない**（§15。方針を変える場合は人間の判断を仰ぐ）。

---

## 1. プロジェクト概要

実在の契約書・規約・規程・法令は著作権・機密性・正解データ不在の問題がある。yakkan-synth は保険約款で、
keiyaku-synth は契約書でこれを解決し、**外部の読み手（規則ベース・VLM・盲検エージェント）で使えることまで
実証した**（両者とも `eval --all --oracle` 全満点・盲検読み取り通過）。
本プロジェクトはその基盤を汎用化し、**複数ドメインの構造化ドキュメント**を同一のコア・同一の正解スキーマで生成する。
検証観点（テキスト／章条項構造／表／図／参照関係／QA）と正解表現は両姉妹と互換（`docs/schema.md`）。

### 1.2 成果物（1文書あたり。両姉妹の最終形と同一）
`dataset/<doc_id>/`（doc_id = `<content_id>--<style_id>`）に `source.json`（内容＋構造＋derived）／
`layout.json`（bbox・読み順・ヘッダ/フッタ）／`answer.json`（ページ別期待テキスト＋outline。
source/layout は内包せず `load_answer` で結合）／`qa.json`／`elements.jsonl`（1 行 1 要素の平索引）／
`doc.pdf`・`pages/*.png`（150dpi）・`render.html`（デバッグ用・配布対象外）。
全体では `dataset/manifest.json`（checksums 付き）・`dataset/search/`（passages/queries/qrels）・
`dataset/README.md`（読み方）・**`dataset/data-card.md`（データカード＝規模・内訳・作り方・品質保証・
制限と偏り・ライセンス。`docs/data_card.md`）**。後 2 つは export が実測値を埋めて生成する。

### 1.3 制約と非目標（v1）
日本語（横書き）のみ。生成は Claude Code セッション内で完結（執筆は Claude、骨組み・検証・描画は Python）。
**外部 LLM API は使わない。** 本物らしさ＝読者が「実在の契約書／規約／規程／法令だ」と感じる語彙・密度・体裁
（各ファミリーの docs）。非目標：スキャン劣化画像・印影・手書き署名／縦書き・ルビ（yakkan で実測のうえ
不採用）／実在文書の再現／**法的に有効な文書**（生成物は読み取り検証用のダミー）／読み取りモデル自体の実装
（検証用の読み取りは `docs/validation_plan.md` の範囲のみ）。

---

## 2. 設計原則

yakkan-synth の 8 原則（Content/Layout 分離、番号は計算する、ラベルと文言の分離保持、表の二重表現、
図は自前SVG、in-flow のみ、失敗は早く明示的に、架空でも一貫）を**そのまま継承**する。追加原則：

1. **実証済みは再検証しない**：renderer（WeasyPrint 70.0 固定）・bbox 抽出・probe 実測・gotchas・
   描画規約は**両姉妹の結論**を継承する。挙動が疑わしいときだけ probe を書く。
2. **コア＝機構、ファミリー＝知識**：コアは Node ツリー・RichText・表・図・描画・検証・評価という「機構」だけ。
   番号方式・必須要素・文体・denylist・意味種別はファミリーが宣言する。**宣言優先、コード逃げ道**。
3. **同等性で守る**：汎用化のリグレッションは**既に完成している 2 ドメイン**で検出する。insurance（yakkan）と
   contract（keiyaku）の既存 content を新コアで再生成し、`answer.json` が一致することを CI で保つ（§12 P2）。
4. **ファミリー間で正解形式を変えない**：`source/layout/answer/qa` と評価向け成果物のスキーマは全ファミリー共通。
   固有の意味は `semantic_type`・`kind` の登録語彙と `meta.family_ext` で表現する。
5. **基準は機械に落とす**：文章で書いただけの品質基準は守られない（yakkan S1：30 content のうち 13 が違反）。
   執筆・正解の要件は可能な限り lint / verify / テストにする（keiyaku の L22〜L26 はすべて
   「目視でしか見つからなかった欠陥」から生まれた）。
6. **検証は文脈を持たない読み手まで**：自セッションの読み取りでは踏まない契約の穴がある（yakkan Z2・keiyaku V-E）。
   ファミリーごとに盲検読み取りを通す（`docs/validation_plan.md`）。
7. **数えた値だけを配る**：規模・内訳・品質の数値は実ファイルから測って成果物に書く。
   仕様書・記憶を数値の出典にしない（`docs/data_card.md` §2）。

---

## 3. 対象ドキュメントの特徴（実在文書の構造分析）

ファミリーごとに「読み取り課題カタログ」を作る。**書式・記号体系は姉妹のカタログを踏襲**する——
yakkan の A〜F 群と keiyaku の **CT1〜CT25**（契約書 36 種・39 ファイルの実測。各
`docs/reference_structures.md`）。進め方とファミリー横断の課題群（G1〜G13：当事者・署名欄・別紙・附則・
深い入れ子リスト・漢数字/イロハ・枝番・条範囲つき目次・関係条つき別表・公布情報・読替え表 ほか。
**実証済みか未実証かを明記してある**）は `docs/reference_structures.md` に、ファミリー固有のカタログは
`families/<family>/docs/structures.md` に置く。**構造設計・執筆・描画のいずれでも着手前に必ず読む。**

---

## 4. ファミリーと doctype

`families/<family>/` がドメイン知識一式（family.yaml・numbering・blueprints・styles・library・denylist・docs）を持つ。
doctype は旧 yakkan の genre に相当し、`blueprints/<doctype>.yaml` が骨組み・必須要素・分量・バリエーションを宣言する。
**詳細仕様と各ファミリーのカタログは `docs/families.md`。** v1 の対象：

| family | doctype（v1） | 目標ページ | 特徴 | 文体 |
|---|---|---|---|---|
| `contract` 契約書 | **10 種**：`nda` `outsourcing` `delegation` `consulting` `purchase` `lease` `license` `sysdev` `contracting` `employment`（keiyaku から family 化） | 2–18（既定上限 12） | 骨格 **5 類型**（条文型・頭書型・様式型・約款型・逐条解説型）・甲乙表記・別紙・記名押印欄 | 常体（一部敬体） |
| `terms` 利用規約等 | `tos`（利用規約）`privacy`（プライバシーポリシー） | 4–10 | 運営者単独名義・改定条項・箇条書き多用・表は少なめ | 敬体 |
| `regulations` 規程 | `shugyo`（就業規則）`kitei`（一般規程） | 6–16 | 章-条-項-号・附則・改正履歴表・別表（賃金表等） | 常体 |
| `statute` 法令 | `law`（法律風）`jorei`（条例） | 4–14 | 漢数字・イロハ・枝番・条範囲つき目次・（第◯条関係）別表・公布情報。**姉妹に先例が無い** | 常体 |
| `insurance` 約款 | yakkan の 10 genre から移植（まず `oneday` `teikan`） | 8–20 | yakkan-synth と同等（同等性検証用、§2-3） | 敬体/常体 |

- 番号方式は宣言的な `families/<f>/numbering/<scheme>.yaml`（階層ごとのカウンタ書式・参照解決規則）で定義し、
  宣言で書けない例外だけ family フックで実装する。counter に `kanji`・`iroha` を含む（`docs/schema.md` §7）。
  **keiyaku で 3 方式（`contract-standard` / `contract-form`＝条を持たない / `contract-kanji`＝漢数字）が
  宣言で書けることが実証済み**。
- style プリセットはファミリーごとに 2〜4 種（判型×段組×フォント×罫線）。1 content を 1〜2 style で描画し、
  **2 style 目は「版面が最も遠いもの」を選ぶ**（同系を重ねてもレイアウト頑健性の検証にならない）。

---

## 5. データモデル（正解JSON）→ 詳細は `docs/schema.md`

**`docsynth/models.py` `build.py` `richtext.py` `schema/` `content/` を触る作業では、着手前に必ず `docs/schema.md` を読む。**

- yakkan-synth の 3層＋QA・`Node`・`Block`・RichText・表の二重表現・図6種＋正規化グラフ・`derived` を
  **そのまま継承**。**基底仕様の確定後に yakkan へ入った拡張（rider・badges・article_heading・
  caption_numbering・citation 系・enumerations・answer スリム化ほか）と、keiyaku が契約書で実装した拡張も
  初期仕様に含む**（`docs/schema.md` §1.1）。
- 汎用化差分：`genre` → `family`+`doctype`（`schema_version: "2.0"`）。Node.kind に `preamble`
  **`head_matter`（頭書）** `signature` `schedule` `supplement`、Block に `parties` `revision_history`
  **`commentary`（逐条解説）** を追加。semantic_type は「コア共通＋ファミリー登録」の2層。
  statute 向けに `meta.promulgation`・`Node.relation_refs`・目次の条範囲を追加（`docs/schema.md` §11）。
- RichText 追加トークン：`{party:<key>}`（`|name` 正式名称・`|full` 導入形・`|role` 役割名。呼称は
  `meta.parties` で宣言し build が解決）。既存トークンは不変。
- QA は yakkan の 11 種別を継承（`apply` は執筆専用のまま。答えは**機械検算 → 読み幅の明示 → 人間の承認**で確定する）。
  bbox は pt・原点左上＋正規化 [0,1] 併記。

---

## 6. レンダリングパイプライン → 詳細は `docs/rendering.md`

**`docsynth/render/` `layout/` `verify/` `numbering.py` と各ファミリーの styles を触る作業では、着手前に必ず `docs/rendering.md` を読む。**

- Jinja2 → HTML → **WeasyPrint 70.0（版固定）** → PDF。検証は pdfplumber＋pypdfium2（PyMuPDF は AGPL のため不使用）。
  図は自前 Python → インライン SVG。**技術選定・CSS 規約・bbox 抽出・verify は姉妹の結論を継承**し、
  `docs/rendering.md` には差分と**実害から確定した描画規約**（`.ttf` フォント・リーダー罫・2 パス目次・
  caption は表の中・`string(chapter, first)`・選択欄は `■`/`□`・2 段 style に段またぎ要素を置かない ほか）を書く。
- verify **V01–V11**：テキスト往復一致／豆腐（U+FFFD）／目次ページ一致（**目次が無い文書ではスキップした旨を
  レポートに明記**）／全要素 ≥1 fragment／はみ出し・重なり／決定論／図の座標／**V11 結合セルがページ境界を
  またがない**。追加 V-P1〜V-P5（記名欄と `meta.parties` の一致・page_limit・目次なし明記・CFF 埋め込み無し・
  `{party:}` の解決結果が紙面に出る）。
- **段またぎ要素による内容欠落**（両姉妹で実害あり）を含め、render は内容欠落を検出したら停止する。

---

## 7. コンテンツ生成（執筆）→ 詳細は `docs/style_guide.md`

**執筆・`families/<f>/library/`・QA 作成の作業では、着手前に必ず `docs/style_guide.md` と
`docs/authoring_checklist.md`、対象ファミリーの `families/<f>/docs/style.md` を読む。**

- 役割分担：Python が骨組み・番号・当事者呼称・参照・目次・lint・描画・検証・自動QA。Claude が条文本文・定義・
  表の中身・図のノード・脚注・逐条解説・alt/facts・執筆QA。組み立ては `scripts/authoring.py`（**検証はしないので
  書いたら必ず lint**）。
- 執筆プロトコル：`scaffold` → part ごとに執筆 → `lint` → `fill_records` → `build` → `render` → `verify` →
  `review`（全ページ PNG を目視）→ `qa` → `manifest update`。架空化・文体は `docs/style_guide.md` §2–3。末尾に disclaimer 必須。
- 執筆者が**書いてはいけないもの**：番号ラベル（「第1条」「(1)」「①」「第二条」「イ」）、当事者呼称（「甲」→`{party:}`）、
  表・図番号（「表2」→`{ref:}`）、別紙番号、位置で指す言い方（「下表」→`{ref:}`。L26）、
  Markdown 記法（`**` `__` `` ` ``。そのまま紙面に印字される。L25）、`derived`、目次、ページ番号。
- 同一 doctype 3 文書以上では構成・当事者・数値・題材を変える（`lint --similarity` 30% 超で警告）。
- **`docs/authoring_checklist.md`（lint が通っても残る欠陥の一覧）を執筆前に必ず読む。**
  同種の欠陥を見つけたら同ファイルに追記し、機械化できるものは lint / verify に落とす。

---

## 8. 整合性ルール（`docsynth lint`）

**姉妹の最終形 L00–L26 を番号・意味とも互換で継承する**（yakkan L00–L18 ＋ keiyaku L19–L26）。
**本プロジェクトの新設は L27 以降**、ファミリー固有は FLxx。実装位置は `docs/lint_rules.md`、
規則の意味は `docs/schema.md` §9。

| # | ルール（汎用化後の要点） | 重大度 |
|---|---|---|
| L00–L03 | スキーマ検証（derived 混入・family/doctype・family_ext）／id・参照の存在（空文字解決も error）／脚注の対応と**配置**／**番号ラベル・当事者呼称の直書き禁止**（検出パターンは numbering YAML＋party alias から生成） | error |
| L04–L06 | blueprint 必須要素（**構造のみで縛る**）／表の格子整合・records 整合／図の端点・座標・最小複雑度・alt/facts | error |
| L07–L09 | フォント被覆（`■ □ ㎡ ○△×` を含む）／denylist・ドメイン・電話番号／推定ページ数（上限は blueprint、較正は実コーパス） | error（L09 目標超過は warn） |
| L10–L12 | 文体（敬体/常体・digit_style）／数値整合（`{const:}`）／定義語の未定義使用・未使用定義・**定義文が紙面に現れない** | warn |
| L13–L15 | disclaimer・meta 必須／QA 整合（evidence 存在・answer 包含・図の答えの実在）／類似度 >30% | error / error / warn |
| L16–L18 | 執筆 QA の件数と観点の配分（family.yaml で宣言）／表の `header_cols` が行見出しを覆う（**0 も error**）／列挙用の表に `caption` を付けない | error |
| L19 | **当事者整合**：`{party:}` が `meta.parties` に存在、当事者表示・本文・記名押印欄で呼称と名称が一致 | error |
| L20 | **文書の骨格**：`preamble` が body 先頭に 1 つ、`signature` が back_matter に 1 つ、記名欄が全当事者を覆う（要件はファミリーが宣言） | error |
| L21 | **逐条解説**：`commentary` は対象条の `anchor` を持ち、対象が実在する（本文との文の重複は warn） | error/warn |
| L22 | **表・図の配置**：`table`/`figure`/`formula` は**導入文を持つ項**の `blocks` に付ける（条直下は第1項より前に描かれる） | error |
| L23 | **列挙の入れ子**：同じ親の下に号の並びが 2 組以上あるなら、号は**導入する項の `children`** に入れる | error |
| L24 | **置き去りの part**：`parts/*.json` はすべて `doc.json` の `parts` から参照されていること | error |
| L25 | **Markdown の名残**：本文に `**` `__` `` ` `` を書かない（強調は `{b:}` `{u:}`） | error |
| L26 | **位置で指す言い方**：番号を持つ表・図は `{ref:}` で指す（「下表」は版面が変われば嘘になる） | warn |
| L27– | 本プロジェクトの新設枠（空。statute・terms の横断規則が出たらここから） | — |
| FLxx | ファミリー定義の追加 lint（family.yaml の `lint:` で宣言、またはフックで実装） | family 定義 |

---

## 9. 評価用QAと評価ハーネス → 詳細は `docs/evaluation.md`

**姉妹の完成形を P0 で丸ごと移植する**（削って再発明しない）：読み取り **13 指標**・検索 **8 指標**
（nDCG@k・Recall@k・`exact_recall@k`・`r_precision`・MRR・`doc@1`・`confusion@k`・`false_positive_rate`
＋`recall_ceiling@k` の併記）・`elements.jsonl`・検索評価セット（**クエリ 10 種**）・予測/検索スキーマ・
oracle/misread（単調性検査）・`eval --all`・`manifest check`・`datacard check`。
**予測に使う語彙を文書化する**（採点は完全一致——語彙が無いと当てようがない）。
**検索評価セットは生成時に自己検査する（V-S1〜V-S9）**：gold の字面コピーで飽和させない・
素のクエリは `df_docs == 1`・同一文字列のクエリが gold を食い違わせない 等。
合格条件は `docs/evaluation.md` §8、検証の階段は `docs/validation_plan.md`。

---

## 10. リポジトリ構成 → 詳細は `docs/repo_layout.md`

**ファイルを新規作成・移動する作業では、着手前に必ず `docs/repo_layout.md` を読む。** 要点：

- 仕様は `CLAUDE.md`＋`docs/`。コアは `docsynth/`（models・numbering・richtext・scaffold・compose・build・
  lint・render・layout・verify・qa・answer・export・search_set・figure_graph・eval・manifest・batch・
  datacard・families・cli）。
- ドメイン知識は `families/<family>/`（family.yaml・numbering/・blueprints/・styles/・library/・denylist.txt・docs/・hooks.py）。
- 執筆成果 `content/<content_id>/` は**コミットする**。生成物 `dataset/` はコミットせず `specs/` から再生成する。

---

## 11. コマンドとワークフロー
```
uv sync ; uv run docsynth doctor ; uv run docsynth families ; uv run docsynth schema export
uv run docsynth scaffold --family <f> --doctype <d> --content-id <cid> --seed <n>
uv run docsynth lint content/<cid> [--similarity] [--quick] ; uv run docsynth build content/<cid>
uv run docsynth render content/<cid> --style <sid> [--report]   # → dataset/<cid>--<sid>/
uv run docsynth verify dataset/<doc_id> ; uv run docsynth review dataset/<doc_id>  # PNG を目視
uv run docsynth qa dataset/<doc_id> [--validate] ; uv run docsynth batch specs/<spec>.yaml
uv run docsynth export                    # elements.jsonl / passages / search / README / data-card.md
uv run docsynth eval dataset/<doc_id> --pred pred.json   # 採点（--oracle / --misread / --all）
uv run docsynth eval --oracle --dump-pred <out>          # 正解から「予測の実例」を出す（配る実例はこれで作る）
uv run docsynth eval --search-run run.json               # 検索の採点
uv run docsynth manifest update|check ; uv run docsynth datacard update|check
uv run docsynth clean --stale ; make check               # check は manifest とデータカードの鮮度も見る
```
- スラッシュコマンド・subagent（author / reviewer / render-debugger）・hooks は姉妹の `.claude/` 構成を流用する（P0 で移植）。
- **サブエージェントに執筆を任せている間は共有コード（CSS・テンプレート）を触らない**（両姉妹の教訓）。

---

## 12. マイルストーンと完了条件（DoD）→ 詳細タスクは `docs/plan.md`

| フェーズ | 内容 | DoD |
|---|---|---|
| **P0 移植** | **`../contracts/keiyaku/` → `docsynth/`** をコピー＆改名（リネームのみ・挙動不変）。評価基盤・データカード・`.ttf` フォント・tests・scripts・`.claude/` を含む（基盤の選択は人間の判断待ち） | `make check` が通り、smoke が keiyaku と同一出力。棚卸しを `docs/architecture.md` §5 に記録 |
| **P1 コア汎用化** | family レジストリ（`contract` 固定値をレジストリに開く）、宣言的 numbering の一般化（counter kanji/iroha 含む）、semantic registry、lint の family 対応（L04/L10/L13/L16/L20 の要件をファミリー宣言から読む） | 単体テスト。numbering YAML **8 方式**（contract 3 ＋ insurance 5）が姉妹の実装と同一ラベル・同一参照解決を出す golden |
| **P2 同等性** | insurance（yakkan の oneday・teikan）と contract（keiyaku の nda・lease・employment）を family として再生成 | `answer.json` が姉妹の生成物と一致（許容差は decisions.md）。CI に組込み |
| **P3 contract 完成** | keiyaku の 10 doctype・3 numbering・4 style・50 content を `families/contract/` へ移し切る | 全 doctype が verify/review を通り manifest に ready |
| **P4 terms** | tos/privacy、改定履歴・深い入れ子リスト、各 1 文書 | 2 文書が ready（lint/verify/review/qa とも error 0） |
| **P5 regulations** | shugyo/kitei、附則・改正履歴・別表、各 1 文書 | 同上 |
| **P6 statute** | law/jorei、漢数字/イロハ・枝番・条範囲つき目次・関係条つき別表・公布情報、各 1 文書。**要probe 2 件（条見出し 2 行構成・漢数字ラベル幅）を先に実施** | 同上＋`docs/schema.md` §11 の設計課題を decisions で確定 |
| **P7 データセット v1** | 自動QA・執筆QA・batch（5 ファミリー × doctype × content × 1–2 style）・export・データカード | 全文書 ready。`eval --all --oracle` 全満点。検索評価セットが V-S1〜V-S9 を通る。baseline_reader が全文書で完走 |
| **P8 検証・硬化** | 規則ベース → VLM → 盲検読み取り → HITL（`docs/validation_plan.md` の V-A〜V-F） | `docs/evaluation.md` §8 の 6 条件。人間の判断待ち事項すべてに決定が下りている。v1 タグ（打つのは人間） |
| **P9 拡張** | 新ファミリー追加手順の文書化検証（1 ファミリーを手順書だけで追加）、style 追加、insurance 残 8 genre、配布（`docs/distribution.md`） | 手順書 `docs/families.md` §7 のとおりに第三者（別セッション）が追加できる |

各フェーズ終了時に `docs/progress.md` を更新し、次フェーズの最初の 3 タスクを書いておく。

---

## 13. コーディング規約・テスト
- Python 3.12、uv、`ruff`（format + lint、line-length 110）、型ヒント必須、pydantic モデル外で dict を裸で
  回さない（評価向け成果物・予測スキーマも pydantic → schema export）。識別子は英語、コメント・
  ユーザー向け文字列は日本語可。ログは `logging`、CLI は typer。乱数は `random.Random(seed)` を明示的に
  受け渡す。**`datetime.now()` を生成物に入れない。**
- テスト：`tests/unit`（numbering・richtext・lint・当事者解決・eval 単調性ほか）、`tests/golden`
  （許容誤差 0.5pt、**P2 の姉妹同等性 golden を含む**）、`tests/render_smoke`（各 style 1 ページ）。
  golden 更新は `--update-golden` を明示し、差分理由をコミットメッセージに書く。
- コミット単位：フェーズ内の機能単位。**「移植」と「汎用化」のコミットを混ぜない**（P0/P1）。
  `content/` はコミットする。`dataset/` はコミットしない（`specs/` から再生成）。

---

## 14. 既知の落とし穴（Gotchas）
**姉妹 2 本の `docs/gotchas.md` の全項目**（WeasyPrint 私的API・単位系・繰返し表頭・段組 fragments・
column-span の内容欠落・SVG フォント明示・リーダー罫・CFF フォント・`RenderLayoutError` の「帯」・
macOS の DYLD パス等）**は本プロジェクトでも有効。** render/layout/verify を触る前に必ず読み、
本プロジェクト固有の発見は `docs/gotchas.md`（要点の再掲つき）に追記する。とくに：
**「レンダリング成功」≠「内容が全部載った」**（内容欠落検出を無効化しない）／**結合セルをページ境界に
またがせない**（継続ページの列が空欄になり、正解データのほうが誤りになる。V11）／フォントは `.ttf`
（CFF は macOS Preview で本文が不可視）。

---

## 15. 決定事項（経緯と仮決めは `docs/decisions.md`）

| 項目 | 決定 | 状態 |
|---|---|---|
| コード基盤 | **`../contracts/keiyaku/`（keiyaku-synth）をコピーして改名**し本リポジトリで発展させる。insurance の資産は yakkan から持ち込む。両姉妹は凍結された参照実装 | **仮決め**（人間の判断待ち） |
| 正解スキーマ | 両姉妹と互換（`genre`→`family`+`doctype` 等の差分＋基底確定後の拡張。`schema_version: "2.0"`。`docs/schema.md`） | 確定 |
| renderer | WeasyPrint 70.0 固定（姉妹の probe 実測 22 項目を継承・再実測しない） | 確定 |
| フォント | `.ttf`（TrueType 輪郭）版を同梱（CFF は macOS Preview で不可視） | 確定 |
| 評価基盤 | 姉妹の完成形を P0 で丸ごと移植（読み取り 13 指標・検索 8 指標・クエリ 10 種・データカード） | 確定 |
| v1 ファミリー | contract / terms / regulations / statute / insurance の 5 つ | 確定 |
| doctype 数 | contract 10・terms 2・regulations 2・statute 2・insurance 10（移植は段階的） | 確定 |
| ページ上限 | contract 既定 12（絶対 20）／terms 10／regulations 16／statute 14／insurance 20 | 仮決め |
| 法令引用 | 実在法令・裁判所・官公庁は名称のみ。法令の条番号は書かない（statute の生成文書内でも同じ） | 仮決め |
| 印影・手書き | 描画しない。記名押印欄は枠と「印」の文字のみ | 仮決め |
| 様式型の選択欄 | `■`（選択）/`□`（未選択）。`☑`（U+2611）は使わない | 確定 |
| 縦書き・ルビ・スキャン劣化 | 対象外（ルビ・縦組み見出しは yakkan が実測のうえ不採用） | 確定 |
| v1 規模 | 5 ファミリー・26 doctype。**content を足して増やし、style を重ねて数を増やさない** | 仮決め |
| `apply` QA の確定手順 | 機械検算 → 読み幅の明示 → 人間の承認（keiyaku H5 の手順） | 確定 |
| 外部サービスへの送信 | しない（商用 OCR / VLM API を使わない） | 仮決め |
| 生成物の配布条件 | **未決**。先例は yakkan の Hugging Face ＋ CC BY 4.0（`docs/distribution.md`） | 未決（人間の判断待ち） |
| Python／パッケージ管理 | Python 3.12／uv | 確定 |

新たな未決事項が出たら既定値で進めたうえで `docs/decisions.md` に「仮決め」として記録する。
**人間が決めるべきものは明示したうえで人間の判断を待ち、AI が代わりに決めない。**
