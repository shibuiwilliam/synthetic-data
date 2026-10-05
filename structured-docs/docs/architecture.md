# architecture.md — コア／ファミリーの分離と姉妹プロジェクトからの移植方針

> コアとファミリーの境界、および姉妹プロジェクト（`../contracts/`・`../insurance-contracts/`）からの
> コード移植を触る作業では、**着手前に必ず本ファイルを読む**。
> 境界の変更（コアに新しい概念を足す・ファミリーへ責務を移す）は `docs/decisions.md` に記録してから行う。
>
> **2026-10-05 更新**：姉妹が 2 本になったことに追随し、移植方針（§4）を「keiyaku ベース（既定）／
> yakkan ベース」の 2 案に書き換え、棚卸し表（§5）を keiyaku の実装実績で埋めた。
> 基盤の選択は人間の判断待ち（`HITL_TODO.md` D1）。

## 1. 全体像

```
┌──────────────────────── docsynth（コア：ドメイン非依存） ────────────────────────┐
│ models（Node/Block/Table/Figure/RichText/Layout/Answer/QA/ExportRow/Prediction）  │
│ richtext（トークンのパース・解決）    numbering（YAML 宣言の解釈＋フック呼出）      │
│ scaffold / compose / build（派生値）  lint（L00–L26 ＋ family lint の実行器）      │
│ render（Jinja2→HTML→WeasyPrint）     layout（bbox 抽出）  verify（V01–V11）  qa   │
│ answer / export / search_set / figure_graph / eval（harness・metrics・oracle）     │
│ manifest / datacard / batch    families（レジストリ）    cli                       │
└──────────────────────────────────────────────────────────────────────────────────┘
              ↑ 宣言（YAML）とフック（Python）だけで接続。コアはファミリー名を知らない
┌─ families/contract ─┐ ┌─ terms ─┐ ┌─ regulations ─┐ ┌─ statute ─┐ ┌─ insurance ───────┐
│ keiyaku からの移植   │ │ 新規    │ │ 新規          │ │ 新規      │ │ yakkan からの移植   │
│ 10 doctype・3 方式   │ │         │ │               │ │（先例なし）│ │ 10 genre・5 方式    │
│ family.yaml          │ │ …       │ │ …             │ │ …         │ │ （同等性検証を兼ねる）│
│ numbering/*.yaml     │ │         │ │               │ │           │ │                    │
│ blueprints/*.yaml    │ │         │ │               │ │           │ │                    │
│ styles/*.yaml + css  │ │         │ │               │ │           │ │                    │
│ library/  denylist   │ │         │ │               │ │           │ │                    │
│ docs/  hooks.py(MAY) │ │         │ │               │ │           │ │                    │
└──────────────────────┘ └─────────┘ └───────────────┘ └───────────┘ └────────────────────┘
```

## 2. 境界の規則

コアに置いてよいもの／いけないものの判定基準。迷ったら「**新しいファミリーを追加するとき、
このコードを書き換える必要があるか？**」を問う。書き換えが必要ならコアに置いてはいけない。

| 責務 | 置き場所 | 例 |
|---|---|---|
| 文書の機構（木構造・表・図・参照・脚注） | コア | `Node`, `Table.grid`, `{ref:}` の解決アルゴリズム |
| 番号方式の**解釈器**（counter 群：arabic/circled/katakana/roman/**kanji/iroha**…） | コア | 「counter 書式＋接頭辞＋全角化」を YAML から組み立てる |
| 番号方式の**定義** | ファミリー | 「条は『第Ｎ条』、項は 2 から表示」＝ `numbering/*.yaml` |
| 当事者の機構（`{party:}` の解決・`derived.party_uses`） | コア | 呼称の語彙（甲乙／委託者）はファミリー・content 側 |
| 意味種別の**語彙** | 2層 | コア共通（definitions/enumeration/…）＋ファミリー登録（fee_schedule 等） |
| 必須要素・分量・文体 | ファミリー | `blueprints/<doctype>.yaml` |
| 架空化の検出語 | 2層 | コア共通 `denylist_common.txt`＋ファミリー `denylist.txt` |
| lint の**実行器** | コア | ルールの走査・報告の仕組み |
| lint の**追加規則** | ファミリー | family.yaml の `lint:` 宣言、複雑なものは hooks.py |
| lint の**要件値**（必須ブロック・QA 配分・tone・page_limit） | ファミリー | L04・L10・L13・L16・L20 はコアが検査し、**何を要求するかはファミリーが宣言** |
| CSS の基礎（ページ・段組・表・見出しの機構） | コア | `docsynth/render/templates/base/` |
| 見た目のプリセット | ファミリー | `styles/<style_id>.yaml` ＋ css |
| 評価の指標・突合規則・export の形・データカードの節 | コア | `eval/`・`export_models.py`・`datacard.py`（全ファミリー共通の契約） |
| 自動 QA の質問文言のうちドメイン語 | 要注意 | 「保険金」「約款」「委託業務」等を含む定型文はテンプレート化してファミリーが差し替える（P1 棚卸しで確定） |

**フック（`families/<f>/hooks.py`）は逃げ道であり、常設の置き場ではない。**
フックに書いた処理が 2 ファミリー以上で同型になったら、宣言（YAML スキーマの拡張）としてコアに吸収し、
`docs/decisions.md` に記録する。

## 3. family.yaml の形（P1 で確定させるたたき台）

```yaml
family: contract
display_name: 契約書
doctypes: [nda, outsourcing, delegation, consulting, purchase,
           lease, license, sysdev, contracting, employment]   # blueprints/<doctype>.yaml が存在すること
numbering_schemes: [contract-standard, contract-form, contract-kanji]
default_page_limit: 12                            # 絶対上限 20 はコアが持つ
tone: dearu                                       # dearu（常体）| desumasu（敬体）。lint L10 が使う
authored_qa: { count: 15, table_min: 3, figure_min: 2, apply_min: 2 }   # L16 の要求値（省略時は既定）
skeleton:                                         # L20 が検査する骨格の要件（ファミリーが宣言する）
  preamble: { required: true, position: body_head, except_doctypes: [employment] }
  signature: { required: true, position: back_matter, cover_all_parties: true }
semantic_types:                                   # 表のファミリー登録語彙（コア共通語彙に追加）
  - fee_schedule        # 料金・報酬表
  - deliverables        # 成果物・仕様一覧
  - inventory           # 目録
  - head_matter         # 頭書
  - form_fields         # 様式の記入欄
  - allocation          # 分担表
lint:                                             # 宣言的な追加 lint（FLxx）
  - id: FL01
    rule: require_block                           # コアが提供する宣言ルールの種類
    block: parties
    severity: error
    message: 契約書には当事者表示（parties ブロック）が必須
hooks: hooks.py                                   # MAY。宣言で書けない lint・番号例外のみ
```

## 4. 移植方針（P0）

**どちらの姉妹を基盤にするかは人間の判断待ち**（`HITL_TODO.md` D1）。既定は A案。
どちらでも共通の規律：**P0 ではリネーム以外の挙動変更をしない。** 改名後に供給元の smoke と同一出力に
なることを確認してから P1 の汎用化に入る。**「移植」と「汎用化」のコミットを混ぜない。**

### A案（既定）：keiyaku ベース

- `../contracts/keiyaku/` → `docsynth/`（CLI 名 `keiyaku` → `docsynth`）をコピー＆改名する。
- 同時に持ってくる：`tests/`（532 件）・`scripts/`（24 本。probe 群・`baseline_reader.py`・
  `calibrate_styles.py`・`fill_records.py`・`authoring.py`・`apply_review.py`）・`.claude/`・`Makefile`・
  `assets/fonts/`（**`.ttf` 版**＋`SOURCES.md`）・`schema/`。
- keiyaku に入っている**契約書固有の判断**を P1 で剥がす（§5 の「要汎用化」列）。剥がす前に
  同等性 golden（§6）を立てる。
- insurance の資産（`blueprints/` `styles/` `library/` `numbering` 5 方式・`content/`）は
  **yakkan から**持ってきて `families/insurance/` に置く。
- 得：`family`+`doctype`・宣言的 numbering・`{party:}`・`head_matter`・`commentary`・lint L19–L26・
  verify V01–V11・`datacard`・contract の 10 doctype と 50 content が**すでに動いている**。
- 損：`family: "contract"` 固定値・契約書向け denylist・tone 既定・`authored_qa` の既定値（表 3・図 2・apply 2）が
  コードに入っているため、レジストリ化の作業が P1 に乗る。

### B案：yakkan ベース（発足時の仮決め）

- `../insurance-contracts/yakkan/` → `docsynth/` をコピー＆改名する。
- **keiyaku が実害から確定した資産（lint L19–L26・verify V11・`head_matter`・`commentary`・
  宣言的 numbering・データカード・検索クエリ 10 種）を手で取り込み直す必要がある。**
  取り込み忘れが最大のリスクなので、採る場合は §5 の「keiyaku 由来」行をチェックリストとして使う。

### どちらでも必須

- **評価基盤（answer / export / export_models / search_set / figure_graph / eval / manifest / datacard /
  batch）も丸ごと移植する。** 旧方針の「eval は最小に」は撤回済み（`docs/decisions.md` 2026-09-26）。
  2 本の姉妹で残課題ループ（yakkan 38 件＋AA 群 9 件、keiyaku の V-A〜V-F）を経て固まった資産であり、
  削って再発明しない。
- **フォントは `.ttf`（TrueType 輪郭）版を同梱する。** `.otf`（CFF）埋め込みは macOS の
  Preview/Quick Look で本文が描画されない（yakkan で 41 文書中 26 文書に発生）。変換はバイト非決定論なので
  **実体をコミットして固定資産**にする（生成手順の再現に頼らない）。
- 移植時の棚卸し：モジュールごとに「そのまま使える／汎用化が必要（ドメイン知識が直書き）／捨てる」を
  §5 の表に**実測で**記録する。ドメイン直書き箇所が P1 の作業リストになる。

## 5. 棚卸し表（keiyaku を基盤にする場合。**判定は keiyaku の実装を読んで記入**する）

keiyaku 実装の規模：**62 ファイル・15,919 行**（`keiyaku/`）、テスト 532 件。
「keiyaku 由来」列が ✓ の行は、**B案を採る場合に手で取り込み直す必要がある**ものである。

| モジュール | 判定 | 残るドメイン直書き（P1 の作業） | keiyaku 由来 |
|---|---|---|---|
| models.py | 要汎用化 | `family` が固定値 `contract`／semantic_type の契約書語彙がコア側に居る／meta の `parties` 必須 | ✓（`head_matter`・`commentary`・`{party:}`・2.0） |
| numbering.py | ほぼそのまま | スキーム探索パスがリポジトリ直下 `numbering/` 固定 → `families/<f>/numbering/` に。**宣言の解釈器は完成**（kanji counter 実装済み。iroha は未実装＝statute で足す） | ✓（宣言化） |
| richtext.py | そのまま | 無し（`{party:}` 実装済み） | ✓ |
| ids.py / env.py / fonts.py | そのまま | 無し | |
| compose.py / scaffold.py / blueprints.py | 要汎用化 | blueprint の探索パスと `doctype` の既定値解決をファミリー経由に | |
| build.py | ほぼそのまま | `AUTO_LABEL_TYPES`・caption 採番・頭書の `{ref:head}` 解決はコア機構として残す | ✓（頭書解決・party_uses） |
| lint/（rules・structure・quality・budget・qa_authored・table_headers・similarity・parties・walk） | 要汎用化 | denylist パス／L04 の `required` スキーマ／L10 の tone 既定／L13 の meta 必須／L16 の配分既定／**L20 の骨格要件**を family.yaml から読む | ✓（L19–L26・`lint/parties.py`） |
| render/（html・inline・weasy・formula・templates・diagrams 6 種） | 一部汎用化 | 契約書固有の部分テンプレート（parties・head_matter・signature・form_fields・commentary）を `families/contract/styles/templates/` へ。ページ骨格は base/ に残す | ✓（頭書・記名押印欄・様式・解説枠） |
| layout/（extract・fallback_align） | そのまま | 無し（実測済みの核心。触らない） | |
| verify/（checks・normalize） | ほぼそのまま | V-P1（記名欄）・V-P5（`{party:}` の紙面一致）をファミリー条件付きに | ✓（**V11 結合セルのページまたぎ**・V-P3 の明記・V-P5） |
| qa/（auto・validate） | 要汎用化 | 自動 QA の質問文言のドメイン語 → テンプレート化 | |
| answer.py / figure_graph.py | そのまま | 無し | |
| export.py / export_models.py / search_set.py | 要汎用化 | Passage の `doctype` 列に `family` を併記／パッセージ種別に `commentary` を持つ | ✓（commentary パッセージ） |
| **datacard.py** | ほぼそのまま | 節 4・11 の観点リストを「ファミリー横断」に広げる（`docs/data_card.md` §4.3） | ✓ |
| eval/（harness・metrics・oracle・search） | ほぼそのまま | 列挙番号の除去パターンに漢数字・イロハを追加（statute）。**検索クエリ 10 種は yakkan 側が正**——keiyaku は 4 系統のままなので、**yakkan から取り込む**（`docs/evaluation.md` §7） | 一部 |
| manifest.py / batch.py / cli.py | ほぼそのまま | `doctype` 列に `family` を併記 | |
| styles.py ＋ styles/*.yaml | 分割 | yaml はファミリー側へ、機構（読み込み・css 生成）はコアへ。`parties_style`・`signature_layout` はファミリー拡張として宣言 | ✓ |
| library.py ＋ library/clauses/ | 分割 | 条文はファミリー側へ | |

### 予想と食い違いやすいところ（姉妹の実績から）

- **検索評価セットは keiyaku より yakkan が進んでいる**（クエリ 10 種・自己検査 V-S1〜V-S9・
  `exact_recall@k`・`doc@1`・`confusion@k`・`false_positive_rate`）。基盤をどちらにしても
  **検索まわりは yakkan から取る**のが正しい。
- `numbering.py` は「宣言の解釈器」としては完成しているが、**iroha counter は未実装**（statute で必要）。
- keiyaku の `tests/golden/numbering_legacy.json`（616KB）は yakkan 互換性のための固定物で、
  keiyaku 側でも去就が未決（`../contracts/HITL_TODO.md` H12）。**移植時に持ってくるかを P0 で判断**し、
  持ってこない場合は P2 の同等性 golden で代替する。

## 6. 姉妹プロジェクトとの関係と同等性

- `../insurance-contracts/`（yakkan-synth）＝**基底仕様かつ凍結された参照実装**。実装の意図が分からなく
  なったら、まず `docs/decisions.md` / `gotchas.md` / `remaining_issues.md` / `search_query_plan.md` を読む
  （実害と対処が全部残っている）。
- `../contracts/`（keiyaku-synth）＝**契約書の参照実装かつコード供給元の第一候補**。
  `docs/decisions.md`（151 件）・`authoring_checklist.md`・`lint_rules.md`・`data_card.md` が
  本プロジェクトの同名ファイルの基底になっている。**keiyaku 側は「docsynth と食い違う判断をするときは
  decisions に『docsynth との差分』として明記する」方針**なので、食い違いはそこに出る。
- **どちらも本プロジェクトから書き換えない。** 読み取り専用の参照であり、`content/` を相対パスで
  読むのは同等性テストだけ（存在しない環境ではスキップ）。

### 同等性テスト（P2）

目的は 2 つ：(1) 汎用化のリグレッション検出、(2) 「既存ドメインをファミリーとして表現できるか」の実証。

| ファミリー | 対象 content | 供給元 |
|---|---|---|
| insurance | `oneday`・`teikan` 各 3 本（nonlife と teikan の 2 方式・素組みと標準の 2 体裁） | `../insurance-contracts/content/` |
| contract | `nda`（条文型）・`lease`（頭書型）・`employment`（様式型・条を持たない） | `../contracts/content/` |

- 許容差：id・テキスト・ラベル・grid・records は完全一致。bbox は 0.5pt。
- 一致させられない差分が出たら「新コアのバグ」として扱うのが既定。仕様として差分を受け入れる場合は
  `docs/decisions.md` に記録する。
- contract 側を同等性に入れるのは、**骨格 5 類型のうち 3 類型が一度に守れる**ため
  （条文型・頭書型・様式型。約款型＝`contracting` と逐条解説型＝`license` は P3 で足す）。
