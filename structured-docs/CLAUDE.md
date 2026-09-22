# CLAUDE.md — docsynth：構造化ドキュメント 合成データ生成プロジェクト

> 本ファイルは Claude Code が毎セッション読み込む「プロジェクト憲章 兼 仕様書」である。
> 設計判断・規約・作業手順はここに集約し、実装と食い違ったら **実装ではなく本ファイル（または docs/）を先に直す**。
> 記法：`MUST`＝必須、`SHOULD`＝原則、`MAY`＝任意、`要probe`＝実装前に小さな検証スクリプトで挙動確認が必要。
> 先行プロジェクト：`../insurance-contracts/`（yakkan-synth）。本プロジェクトはその汎用化である。
> **先行プロジェクトで実証済みの設計・実測結果は再検証せず継承する**（§2-1、docs/architecture.md）。

---

## 0. 最初に読むこと（Claude Code への指示）

### 0.1 一行要約
「本物そっくりだが完全に架空の構造化ドキュメント」（契約書・Webサービス利用規約・社内規程・保険約款 等）を
**正解JSON → PDF** の順で生成し、ドキュメント読み取り（テキスト／章条項構造／表／図／参照関係／QA）の
開発検証用データセットを作る。JSON が唯一の真実（single source of truth）であり、PDF はその決定論的な描画結果である。
ドメイン知識は**ファミリー**（§4）としてプラグイン化し、コアはドメイン非依存に保つ。

### 0.2 セッション開始時の手順
1. 本ファイルを読む。次に `docs/decisions.md`（設計変更履歴）と `docs/progress.md`（進捗・次の一手）を読む。存在しなければ §12 の P0 から着手する。
2. `uv run docsynth doctor` で環境（Python・WeasyPrint・フォント・pdfium）を確認する（P0 完了後）。
3. 作業は §12 のフェーズ順。フェーズをまたぐ設計変更は `docs/decisions.md` に「日付／変更／理由／影響」を追記してから行う。
4. 終了前に `make check`（lint + pytest）を通し、`docs/progress.md` を更新する。
5. 触る領域に対応する `docs/*.md`（§0.3 の表）を着手前に読む。読まずに実装しない。

### 0.3 本ファイルの運用ルール
- 詳細仕様は `docs/` に分割してある。**該当領域を触る作業では、着手前に必ず対応する docs を読む。**

  | 触るもの | 先に読む |
  |---|---|
  | コア／ファミリーの分離、yakkan からの移植 | `docs/architecture.md` |
  | `docsynth/models.py` `build.py` `richtext.py` `schema/` `content/` `dataset/` | `docs/schema.md` |
  | `families/` 配下すべて（family.yaml・numbering・blueprint） | `docs/families.md` |
  | `docsynth/render/` `layout/` `verify/` `numbering.py` `styles` | `docs/rendering.md` |
  | 執筆・条文ライブラリ・QA 執筆 | `docs/style_guide.md` ＋ 対象ファミリーの `families/<f>/docs/` |
  | 実在文書の構造分析・参考URL の扱い | `docs/reference_structures.md` |
  | ファイル新規作成・配置 | `docs/repo_layout.md` |
  | 設計変更／進捗／環境の癖 | `docs/decisions.md` `docs/progress.md` `docs/gotchas.md` |

- **`@docs/...` の import は使わない**（import は launch 時に全文展開され、分割の目的が失われる。yakkan-synth 2026-09-21 確認）。参照はバッククォート付きパス表記で書く。
- 小さな恒常ルールは `.claude/rules/*.md` に置き、frontmatter の `paths:` で対象を限定する。
- 同じ修正指示を2回受けたら、本ファイルか `.claude/rules/` に追記する。
- 環境固有の発見は `docs/gotchas.md` に書く。**yakkan-synth の `../insurance-contracts/docs/gotchas.md` は本プロジェクトでも全項目有効**として扱う（§14）。
- 本ファイルは**250行以内を目安**とする。超えそうなら docs へ移す。

### 0.4 絶対に守ること（Hard rules）
1. **転載禁止**：参考にした実在文書（契約書ひな型・実在サービスの利用規約・実在規程・約款）の文章を、部分的にも、語順を変えただけでも、リポジトリに入れない。参考にするのは**構造・要素の種類・レイアウト慣行のみ**。生成文はすべてオリジナルに書く。市販・公開の「ひな型」も著作物として同様に扱う。
2. **完全架空**：会社名・サービス名・商品名・人物名・住所・連絡先・URL・様式番号は架空。実在名は `families/<f>/denylist.txt` で検出し lint で落とす。URL は `example.jp` / `example.co.jp` / `example.com` のみ。電話番号はゼロ埋め（`0120-000-000` `03-0000-0000`）のみ。実在の法令・裁判所は**名称のみ**引用可、法令の条番号は書かない（§15）。
3. **JSON が真実**：PDF に現れる文字列（ヘッダ・フッタ・ページ番号・目次・図中の文字・署名欄を含む）は、すべて `source.json` から機械的に導出できること。PDF/HTML の手編集禁止。`dataset/` は生成物であり手で書き換えない。
4. **決定論**：同じ `content_id`・`style_id`・`seed`・依存バージョンなら、バイト単位で同一の JSON と同一のテキスト層を持つ PDF を再生成できること（PDF メタデータ日時は固定値）。
5. **ページ上限**：ファミリーの blueprint が定める上限（既定 20 ページ）以下。超えたら生成失敗として扱う。フォント縮小や自動省略で押し込まない。
6. **正解の完全性**：レンダリング後、PDF のテキスト層と JSON の期待テキストは正規化後に一致すること。一致しない文書はデータセットに入れない。
7. **検証は視覚でも行う**：新ファミリー・新 doctype・新スタイルの初回は必ずページ PNG を自分の目で確認する。ページ数と lint が通っても崩れていることはある。
8. **コアにドメイン知識を入れない**：「甲・乙」「約款」「利用規約」等の語彙・番号方式・必須要素をコアのコードに直書きしない。すべて `families/` の宣言（YAML）または family フックに置く（§2-2）。
9. 秘密情報・API キーをコミットしない。ネットワーク取得は参考URLと公式パッケージのみ。

---

## 1. プロジェクト概要

ドキュメント読み取りシステム（OCR/レイアウト解析/VLM/構造化抽出）の開発では、実在の契約書・規約・規程は
著作権・機密性・正解データ不在の問題がある。yakkan-synth は保険約款についてこれを解決した。
本プロジェクトはその基盤を汎用化し、**複数ドメインの構造化ドキュメント**を同一のコア・同一の正解スキーマで生成する。
検証観点（テキスト／章条項構造／表／図／参照関係／QA）と正解表現は yakkan-synth と互換（`docs/schema.md`）。

### 1.2 成果物（1文書あたり。yakkan-synth と同一形式）
```
dataset/<doc_id>/            # doc_id = <content_id>--<style_id>
  source.json                # 執筆内容＋構造＋意味（レイアウト非依存）＋ build の派生値
  layout.json                # ページ・要素ごとの bbox・読み順・ヘッダ/フッタ
  answer.json                # source + layout + ページ別期待テキスト + アウトライン（評価はこれ1つ）
  qa.json                    # 評価用問答（自動生成＋執筆）
  doc.pdf  pages/page-NNN.png  render.html
dataset/manifest.json        # 全文書一覧（doc_id, family, doctype, style, pages, seed, status）
```

### 1.3 制約
- 日本語（横書き）。縦書きは対象外。生成は Claude Code セッション内で完結（執筆は Claude、骨組み・検証・描画は Python）。外部 LLM API は使わない。
- 本物らしさ：読者が「実在の契約書／規約／規程だ」と感じる語彙・密度・体裁（各ファミリーの docs）。

### 1.4 非目標（v1）
- スキャン劣化画像・押印画像（印影）の描画・手書き署名の再現。
- 実在文書の再現・比較、法的に有効な文書の作成（生成物は読み取り検証専用）。
- 読み取りモデル自体の実装。評価ハーネスは正解JSONの妥当性検証を主目的とし最小に留める。

---

## 2. 設計原則

yakkan-synth の 8 原則（Content/Layout 分離、番号は計算する、ラベルと文言の分離保持、表の二重表現、
図は自前SVG、in-flow のみ、失敗は早く明示的に、架空でも一貫）を**そのまま継承**する。追加原則：

1. **実証済みは再検証しない**：renderer（WeasyPrint 70.0 固定）、bbox 抽出（`_page_box` 走査）、
   probe 実測結果、gotchas は yakkan-synth の結論を継承する。挙動が疑わしいときだけ probe を書く。
2. **コア＝機構、ファミリー＝知識**：コアは Node ツリー・RichText・表・図・描画・検証という「機構」だけを持つ。
   番号方式・必須要素・文体・denylist・意味種別という「知識」はファミリーが宣言する。宣言（YAML）で表現できない
   ものだけ family フック（Python）に書く。**宣言優先、コード逃げ道**。
3. **同等性で守る**：汎用化のリグレッションは insurance ファミリー（yakkan からの移植）で検出する。
   yakkan-synth の既存 content を新コアで再生成し、answer.json が一致することを CI で保つ（§12 P2）。
4. **ファミリー間で正解形式を変えない**：`source/layout/answer/qa` のスキーマは全ファミリー共通。
   ファミリー固有の意味は `semantic_type`・`kind` の登録語彙と `meta.family_ext`（自由領域）で表現する。

---

## 3. 対象ドキュメントの特徴（実在文書の構造分析）

ファミリーごとに「読み取り課題カタログ」を作る。**書式・記号体系（A〜F 群）は yakkan-synth の
`../insurance-contracts/docs/reference_structures.md` を踏襲**し、本プロジェクトの進め方と
ファミリー横断で共通の課題群は `docs/reference_structures.md` に、ファミリー固有のカタログは
`families/<family>/docs/structures.md` に置く。**構造設計・執筆・描画のいずれでも着手前に必ず読む。**

ファミリー横断で共通する構造要素（コアが直接サポートする）：
- 階層見出し（章／条／項／号／細目）、前文、附則・別紙・別表、目次、定義（語・条いずれの形も）
- 条項間参照・脚注・注記、改定履歴、当事者表示と署名欄（契約書・規程で使用）
- 表（定義表・列挙表・料金表・比較表・手続表・履歴表）、図（フロー・ツリー・タイムライン・ステップ・マトリクス・注釈付き模式図）

---

## 4. ファミリーと doctype

`families/<family>/` がドメイン知識一式（family.yaml・numbering・blueprints・styles・library・denylist・docs）を持つ。
doctype は旧 yakkan の genre に相当し、`blueprints/<doctype>.yaml` が骨組み・必須要素・分量・バリエーションを宣言する。
**詳細仕様と各ファミリーのカタログは `docs/families.md`。** v1 の対象：

| family | doctype（v1） | 目標ページ | 特徴 | 文体 |
|---|---|---|---|---|
| `contract` 契約書 | `outsourcing`（業務委託）`nda`（秘密保持）`sales`（売買）`lease`（賃貸借） | 3–10 | 前文・甲乙表記・別紙・後文と記名押印欄 | 常体 |
| `terms` 利用規約等 | `tos`（利用規約）`privacy`（プライバシーポリシー） | 4–10 | 運営者単独名義・改定条項・箇条書き多用・表は少なめ | 敬体 |
| `regulations` 規程 | `shugyo`（就業規則）`kitei`（一般規程） | 6–16 | 章-条-項-号・附則・改正履歴表・別表（賃金表等） | 常体 |
| `insurance` 約款 | yakkan の 7 genre から移植（まず `oneday` `teikan`） | 8–20 | yakkan-synth と同等（同等性検証用、§2-3） | 敬体/常体 |

- 番号方式は宣言的な `families/<f>/numbering/<scheme>.yaml`（階層ごとのカウンタ書式・参照解決規則）で定義し、
  宣言で書けない例外だけ family フックで実装する。
- style プリセットはファミリーごとに 2〜4 種（判型×段組×フォント×罫線）。1 content を1〜3 style で描画する。

---

## 5. データモデル（正解JSON）→ 詳細は `docs/schema.md`

**`docsynth/models.py` `build.py` `richtext.py` `schema/` `content/` を触る作業では、着手前に必ず `docs/schema.md` を読む。**

- yakkan-synth の 3層＋QA（`source/layout/answer/qa`）・`Node`・`Block`・RichText トークン・表の二重表現
  （grid＋records/header_path）・図6種＋alt/facts・`derived` の設計を**そのまま継承**する。
- 汎用化差分：`genre` → `family`+`doctype`。Node.kind に `preamble`（前文）`signature`（後文・記名押印欄）
  `schedule`（別紙）`supplement`（附則）を追加。Block に `parties`（当事者表示）`revision_history`（改定履歴）を追加。
  表の `semantic_type` は「コア共通語彙＋ファミリー登録語彙」の2層。
- RichText 追加トークン：`{party:<key>}`（甲・乙等の当事者参照。呼称は `meta.parties` で宣言し build が解決）。
  既存トークン（`{ref:}` `{fn:}` `{term:}` `{const:}` `{b:}` `{u:}` `{br}` 等）は不変。
- QA は yakkan の 11 種別を継承（`apply` は執筆専用のまま）。bbox は pt・原点左上＋正規化 [0,1] 併記。

---

## 6. レンダリングパイプライン → 詳細は `docs/rendering.md`

**`docsynth/render/` `layout/` `verify/` `numbering.py` と各ファミリーの styles を触る作業では、着手前に必ず `docs/rendering.md` を読む。**

- Jinja2 → HTML → **WeasyPrint 70.0（版固定）** → PDF。検証は pdfplumber＋pypdfium2（PyMuPDF は AGPL のため不使用）。
  図は自前 Python → インライン SVG。**技術選定・CSS 規約・bbox 抽出・verify の各仕様は yakkan-synth の結論を継承**し、
  `docs/rendering.md` には差分（署名欄・当事者表示・改定履歴の描画、ファミリー別テンプレート選択）だけを書く。
- 番号付けは numbering YAML から導出。`{ref:}` は最小共通祖先からの相対表記（yakkan と同じ規則）。
- verify：ページ数上限／フォント被覆／テキスト往復一致／目次ページ一致／全要素 ≥1 fragment／はみ出し・重なり無し／決定論。
- **段またぎ要素による内容欠落**（yakkan-synth で実害あり）を含め、render は内容欠落を検出したら停止する。

---

## 7. コンテンツ生成（執筆）→ 詳細は `docs/style_guide.md`

**執筆・`families/<f>/library/`・QA 作成の作業では、着手前に必ず `docs/style_guide.md` と対象ファミリーの `families/<f>/docs/style.md` を読む。**

- 役割分担：Python が骨組み・番号・参照・目次・lint・描画・検証・自動QA。Claude が条文本文・定義・表の中身・図のノード・脚注・alt/facts・執筆QA。
- 執筆プロトコル：`scaffold` → part ごとに執筆 → `lint` → `build` → `render` → `verify` → `review`（PNG 目視）→ `qa` → `manifest update`。
- 架空化・当事者表記・法令引用・doctype ごとの文体は `docs/style_guide.md` §2–4。奥付（または末尾）に架空である旨の disclaimer を必ず入れる。
- 同一 doctype 3 文書以上では構成・当事者・数値・題材を変え、`lint --similarity` で文単位重複率 30% 超を警告する。
- **yakkan-synth の `../insurance-contracts/docs/authoring_checklist.md`（lint が通っても残る欠陥の一覧）を執筆前に必ず読む。**本プロジェクトで見つけた同種の欠陥は `docs/style_guide.md` 末尾の checklist に追記する。

---

## 8. 整合性ルール（`docsynth lint`）

yakkan の L00–L15 を汎用化して継承する。番号・重大度は同じ（詳細規則は `docs/schema.md` 末尾）。

| # | ルール（汎用化後の要点） | 重大度 |
|---|---|---|
| L00–L03 | スキーマ検証（derived 混入検出含む）／id・参照の存在／脚注対応／**番号ラベル直書き禁止**（検出パターンは numbering YAML から生成） | error |
| L04–L06 | blueprint 必須要素／表の格子整合・records 整合／図の端点・座標・最小複雑度・alt/facts | error |
| L07–L09 | フォント被覆／denylist・ドメイン・電話番号／推定ページ数（上限は blueprint から） | error（L09 目標超過は warn） |
| L10–L12 | 文体（敬体/常体・digit_style）／数値整合（`{const:}`）／定義語の未定義使用・未使用定義 | warn |
| L13–L15 | disclaimer・meta 必須／QA 整合（evidence 存在・answer 包含）／類似度 >30% | error / error / warn |
| L16 | **当事者整合**：`{party:}` が `meta.parties` に存在、当事者表示・本文・署名欄で呼称と名称が一致 | error |
| FLxx | ファミリー定義の追加 lint（family.yaml の `lint:` で宣言、またはフックで実装） | family 定義 |

---

## 9. 評価用QAと評価ハーネス（最小）
yakkan の `eval` を継承：ページ別 CER、outline F1、表 TEDS＋セル値 F1（header_path 経由）、
図ノード/エッジ F1、QA 一致、読み順 Kendall τ。正解JSONが評価に耐えることの確認が目的で、拡張は要件が来てから。

---

## 10. リポジトリ構成 → 詳細は `docs/repo_layout.md`

**ファイルを新規作成・移動する作業では、着手前に必ず `docs/repo_layout.md` を読む。** 要点：

- 仕様は `CLAUDE.md`＋`docs/`。コアは `docsynth/`（models・numbering・richtext・scaffold・compose・build・lint・render・layout・verify・qa・eval・families・cli）。
- ドメイン知識は `families/<family>/`（family.yaml・numbering/・blueprints/・styles/・library/・denylist.txt・docs/・hooks.py）。
- 執筆成果 `content/<content_id>/` は**コミットする**。生成物 `dataset/` はコミットせず `specs/` から再生成する。

---

## 11. コマンドとワークフロー
```
uv sync                                   # 依存導入
uv run docsynth doctor                    # 環境チェック
uv run docsynth families                  # 導入済みファミリー・doctype の一覧
uv run docsynth schema export             # schema/*.schema.json
uv run docsynth scaffold --family <f> --doctype <d> --content-id <cid> --seed <n>
uv run docsynth lint content/<cid> [--similarity]
uv run docsynth build content/<cid>
uv run docsynth render content/<cid> --style <sid> [--report]   # → dataset/<cid>--<sid>/
uv run docsynth verify dataset/<doc_id>
uv run docsynth review dataset/<doc_id>   # pages/*.png 出力（Claude が画像を開いて確認）
uv run docsynth qa dataset/<doc_id> [--validate]
uv run docsynth batch specs/<spec>.yaml
uv run docsynth manifest update
uv run pytest -q ; uv run ruff check . ; make check
```
- スラッシュコマンド・subagent（author / reviewer / render-debugger）・hooks は yakkan-synth の
  `.claude/` 構成を流用する（P0 で移植）。

---

## 12. マイルストーンと完了条件（DoD）
| フェーズ | 内容 | DoD |
|---|---|---|
| **P0 移植** | リポジトリ初期化、yakkan コードの棚卸しとコピー（`yakkan/`→`docsynth/`、リネームのみ・挙動不変）、フォント同梱、doctor、smoke PDF | `make check` が通り、smoke が yakkan と同一出力。棚卸し結果を `docs/architecture.md` に記録 |
| **P1 コア汎用化** | family/doctype 導入、宣言的 numbering、semantic registry、新 kind/Block、`{party:}`、lint 汎用化（L16 含む） | 単体テスト。numbering YAML 3 方式（nonlife/life/teikan）が yakkan の numbering.py と同一ラベルを出す golden |
| **P2 同等性** | insurance ファミリー（まず oneday・teikan）を family 化し、yakkan の既存 content を再生成 | answer.json が yakkan-synth の生成物と一致（許容差は decisions.md に記録）。CI に組込み |
| **P3 contract** | contract ファミリー（4 doctype の blueprint・styles 2種・当事者/署名欄の描画）、各 doctype 1 文書執筆 | 4 文書が verify/review を通り manifest に ready |
| **P4 terms** | terms ファミリー（tos/privacy、改定履歴・箇条書き主体のテンプレート）、各 1 文書 | 同上 |
| **P5 regulations** | regulations ファミリー（shugyo/kitei、附則・改正履歴・別表）、各 1 文書 | 同上 |
| **P6 データセット v1** | 自動QA・執筆QA・batch spec（全ファミリー × doctype × 2–3 content × 1–2 style） | 全文書 ready。失敗率と原因を `docs/progress.md` に記録。v1 を tag |
| **P7 拡張** | 新ファミリー追加手順の文書化検証（1 ファミリーを手順書だけで追加）、style 追加、eval 拡張 | 手順書 `docs/families.md` §5 のとおりに第三者（別セッション）が追加できる |

各フェーズ終了時に `docs/progress.md` を更新し、次フェーズの最初の 3 タスクを書いておく。

---

## 13. コーディング規約・テスト
- Python 3.12、uv、`ruff`（format + lint）、型ヒント必須、pydantic モデル外で dict を裸で回さない。
- 識別子は英語、コメント・docstring・ユーザー向け文字列は日本語可。ログは `logging`、CLI は typer。
- 乱数は `random.Random(seed)` を明示的に受け渡す。`datetime.now()` を生成物に入れない。
- テスト：`tests/unit`（numbering・richtext・lint・header_path・diagram layout）、`tests/golden`
  （小サンプル比較・許容誤差 0.5pt、**P2 の yakkan 同等性 golden を含む**）、`tests/render_smoke`（各 style 1 ページ）。
  golden 更新は `--update-golden` を明示し、差分理由をコミットメッセージに書く。
- `content/` はコミットする。`dataset/` はコミットしない（`specs/` から再生成）。

---

## 14. 既知の落とし穴（Gotchas）
**`../insurance-contracts/docs/gotchas.md` の全項目（WeasyPrint 私的API・単位系・繰返し表頭・
段組 fragments・column-span の内容欠落・SVG フォント明示・macOS の DYLD パス等）は本プロジェクトでも有効。**
render/layout/verify を触る前に必ず読む。本プロジェクト固有の発見は `docs/gotchas.md` に追記する。
特に：**この renderer では「レンダリング成功」は「内容が全部載った」を意味しない**（内容欠落検出を必ず有効に保つ）。

---

## 15. 決定事項（2026-09-22 初期決定。経緯と仮決めは `docs/decisions.md`）

| 項目 | 決定 | 状態 |
|---|---|---|
| コード基盤 | yakkan のコードを**コピーして改名**し本リポジトリで発展させる。`insurance-contracts/` は凍結された参照実装 | 仮決め |
| 正解スキーマ | yakkan-synth と互換（`genre`→`family`+`doctype` 等の差分のみ。`docs/schema.md`） | 仮決め |
| renderer | WeasyPrint 70.0 固定（yakkan の probe 結果を継承） | 確定 |
| ページ上限 | ファミリー既定：contract 10／terms 10／regulations 16／insurance 20 | 仮決め |
| 法令引用 | 実在法令・裁判所は名称のみ。法令の条番号は書かない（yakkan 踏襲。契約書で不自然なら再検討） | 仮決め |
| 印影・手書き | 描画しない。署名欄は枠と「印」の文字のみ | 仮決め |
| 縦書き・ルビ・スキャン劣化 | v1 対象外 | 確定 |
| v1 規模 | 4 ファミリー・10 doctype × 2–3 content × 1–2 style ≈ 40–60 文書 | 仮決め |
| Python／パッケージ管理 | Python 3.12／uv | 確定 |

新たな未決事項が出たら既定値で進めたうえで `docs/decisions.md` に「仮決め」として記録する。
