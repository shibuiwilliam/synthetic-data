# architecture.md — yakkan-synth からの移植方針とモジュール構成

> `../insurance-contracts/`（yakkan-synth）からのコード移植、`keiyaku/` のモジュール構成、
> 「コード／宣言」の境界を触る作業では、**着手前に必ず本ファイルを読む**こと。
> 境界の変更（Python にドメイン知識を足す・YAML へ責務を移す）は `docs/decisions.md` に記録してから行う。

## 1. 全体像

```
┌──────────────────── keiyaku（Python：機構。契約書の「知識」は置かない） ────────────────────┐
│ models（Node/Block/Table/Figure/RichText/Layout/Answer/QA/ExportRow/Prediction）           │
│ richtext（トークンのパース・解決：{ref:} {party:} {term:} {const:} {fn:} …）                │
│ numbering（numbering/*.yaml の解釈器）   scaffold / compose / build（派生値の導出）          │
│ lint（L00–L21 の実行器）   render（Jinja2→HTML→WeasyPrint）   layout（bbox 抽出）            │
│ verify   qa（自動QA・検証）   answer / export / search_set / figure_graph                    │
│ eval（harness・metrics・oracle・search）   manifest / batch   doctypes（レジストリ）   cli   │
└─────────────────────────────────────────────────────────────────────────────────────────────┘
        ↑ 宣言（YAML）だけで接続。Python は doctype 名で分岐しない（§2）
┌── blueprints/<doctype>.yaml ──┐┌── numbering/<scheme>.yaml ──┐┌── styles/<style_id>.yaml ──┐
│ 骨組み・必須要素・分量・       ││ 階層ごとのラベル書式・       ││ 判型・段組・フォント・      │
│ variants・page_limit・        ││ カウンタ・参照解決規則       ││ 罫線・palette・            │
│ authored_qa の配分            ││（contract-standard / -form） ││ chars_per_page_estimate    │
└───────────────────────────────┘└─────────────────────────────┘└────────────────────────────┘
┌── library/clauses/<doctype>/ ──┐┌── keiyaku/lint/denylist.txt ──┐
│ 一般条項のオリジナル文の型     ││ 実在名の検出語                 │
└────────────────────────────────┘└────────────────────────────────┘
```

## 2. コードと宣言の境界

迷ったら「**新しい doctype を足すとき、この Python を書き換える必要があるか？**」を問う。
書き換えが必要なら宣言（YAML）に追い出す。

| 責務 | 置き場所 | 例 |
|---|---|---|
| 文書の機構（木構造・表・図・参照・脚注・当事者解決） | Python | `Node`, `Table.grid`, `{ref:}` / `{party:}` の解決アルゴリズム |
| 番号方式の**解釈器**（counter 群：arabic / circled / katakana / paren_katakana / roman） | Python | 「counter 書式＋接頭辞＋全角化」を YAML から組み立てる |
| 番号方式の**定義** | YAML | 「条は『第N条』、項は 2 から表示」＝ `numbering/contract-standard.yaml` |
| 意味種別の語彙 | Python（定数表）| コア共通＋契約書登録語彙（`docs/schema.md` §6）。**追加は表に 1 行足すだけ**にする |
| 必須要素・分量・文体・variants | YAML | `blueprints/<doctype>.yaml` |
| lint の**実行器**とルール本体 | Python | `keiyaku/lint/`。ルールは doctype 名で分岐せず blueprint の宣言を読む |
| CSS の基礎（ページ・表・見出し・リストの機構） | Python 側テンプレート | `keiyaku/render/templates/` |
| 見た目のプリセット | YAML＋CSS | `styles/<style_id>.yaml` ＋ `styles/css/<style_id>.css.j2` |
| 評価の指標・突合規則・export の形 | Python | `keiyaku/eval/`・`export_models.py`（全 doctype 共通の契約） |

- **Python に `if doctype == "employment"` を書かない。** 様式型の違いは
  `numbering: contract-form` と blueprint の `skeleton` で表現する。どうしても宣言で書けない例外が出たら、
  `numbering/<scheme>.yaml` の表現力を拡張するか、理由を `docs/decisions.md` に記録したうえで
  1 箇所に閉じた分岐を置く（2 doctype 以上で同型になったら宣言へ昇格させる）。
- yakkan は `Genre` enum・`NumberingScheme` enum・`CONTINUOUS_ARTICLE_SCHEMES` 等を Python に直書きしている。
  P2（契約書化）でこれらを宣言に追い出すのが主作業（§5 の表）。

## 3. yakkan からの移植方針（P0）

- **コピーして改名する**（`yakkan/` → `keiyaku/`、CLI 名 `yakkan` → `keiyaku`）。git submodule や
  ライブラリ依存にはしない。理由：yakkan-synth は完成品として凍結し、本プロジェクトで自由に
  リファクタリングするため（`docs/decisions.md` 2026-09-26）。
- **P0 ではリネーム以外の挙動変更をしない。** 改名後に smoke PDF のテキスト層が yakkan と一致することを
  確認してから P2 に入る。**「移植」と「契約書化」のコミットを混ぜない。**
- **評価基盤（answer / export / export_models / search_set / figure_graph / eval / manifest / batch）も
  P0 で丸ごと移植する。** 38 件の残課題ループと盲検読み取りを経て固まった資産であり、削って再発明しない。
- **フォントは `.ttf`（TrueType 輪郭）版を同梱する。** yakkan 2026-09-26 の実測：Noto の `.otf`（CFF）を
  WeasyPrint 70.0 が埋め込むと、pdfplumber / pdfium / poppler では読めるのに macOS の Preview / Quick Look で
  本文が描画されない（41 文書中 26 文書）。変換済み `.ttf` と `assets/fonts/SOURCES.md` を**実体ごと**
  持ってくる（変換はバイト非決定論なので、生成手順の再現に頼らず固定資産にする）。
- テスト・`scripts/`（probe 群・calibrate_styles・fill_records・authoring・baseline_reader・
  analyze_reference_pdf・otf_to_ttf）・`.claude/`（commands / agents / rules / hooks / settings）・
  `Makefile`・`pyproject.toml`（依存の版）も同時に移植する。
- 移植時の棚卸し：モジュールごとに「そのまま使える／契約書化が必要（ドメイン知識が直書き）／捨てる」を
  §5 の表に記録する。**直書き箇所が P2 の作業リストになる。**
- yakkan 由来のコメント・docstring に残る「約款」「保険金」等の語は、機構の説明として意味が変わらない限り
  P0 では直さない（挙動不変を守るため）。P2 でまとめて言い換える。

## 4. 保険約款から契約書へ——効く差分

| 観点 | yakkan（約款） | keiyaku（契約書） | 影響 |
|---|---|---|---|
| 当事者 | 単独名義（保険会社が発行） | **2〜4 者**が対等に並ぶ（甲乙丙・連帯保証人・保証会社） | `meta.parties`・`{party:}`・L19・記名押印欄 |
| 前付け | 表紙・目的別もくじ・特約一覧 | **表紙・目次なしが普通**（長い契約だけ目次あり） | `front_matter.cover` を MAY に。verify V-P3 |
| 後付け | 奥付 | **後文＋記名押印欄＋収入印紙欄** | `kind: signature`・L20 |
| 別表 | 別表・付表（等級表・料率表） | **別紙・別表・様式**（仕様書・物件目録・料金表） | `kind: schedule`＋`kind_label` ごとの独立採番 |
| 表の意味 | 保険金一覧・等級表 | 報酬表・成果物一覧・物件目録・**頭書**・**記入欄** | semantic_type の登録語彙（`docs/schema.md` §6） |
| 図 | 5〜8 点（流れ図・タイムライン） | **1〜2 点**（検収フロー・承認フロー・契約期間） | 執筆 QA の図要求を 3 → 2 に（L16） |
| 文体 | 敬体（ジャンルにより常体） | **全 doctype 常体**。様式型は体言止め | L10 |
| 条を持たない文書 | 重要事項説明書（`jyusetsu`） | 労働条件通知書（`contract-form`） | **yakkan の `jyusetsu` 機構を再利用できる** |
| 逐条解説 | なし | モデル契約書に**解説枠**が交互に入る | `Block: commentary`・L21（P5） |
| ページ数 | 8–20 | **2–18**（大半は 10 以下） | blueprint の `page_limit`・較正 |

**再利用が効くところ**：`jyusetsu`（条を持たない 3 階層）は `employment` の様式型に、
`group` の `article_heading: above` と `footnote_style: remarks_box` は約款型の体裁に、
`rider`（番号を持たず題名で `{ref:}` 解決する種別）は `head_matter` と `schedule` の機構にそのまま使える。
**新しい機構を作る前に、yakkan の既存機構で表現できないかを必ず確かめる。**

## 5. 棚卸し表（2026-09-26 の P0 で実測して確定）

「予想」は本ドキュメント執筆時の読み、「実測」は移植後に `keiyaku/` を測った結果。
**食い違いは消さずに残す**（P2 の見積り精度の検証になる）。
件数は「保険ドメイン語（保険・約款・被保険・特約・genre・方式名）の出現行数」。

| モジュール | 予想 | 実測 | 直書き箇所（P2 の作業リスト） |
|---|---|---|---|
| `models.py` | 要改造 | **要改造**（35 行） | `Genre`（10 値）・`NumberingScheme`（5 値）・`SemanticType`（15 値のうち `benefit_schedule` `rider_index` `coefficient` `grade_schedule` `surgery_schedule` が保険固有）・`Issuer.kind`（stock/mutual）・`meta.product_name` / `pet_name`・`annotated_mock.subject`（policy_certificate / claim_form / app_screen） |
| `numbering.py` | 要改造 | **要改造**（46 行・最多） | `_label_nonlife` / `_life` / `_group` / `_jyusetsu` / `_teikan` の 5 関数・`CONTINUOUS_ARTICLE_SCHEMES`・`PARAGRAPH_REF_SCHEMES`・`APPENDIX_KIND_LABEL`（方式→「別表」/「附則」の辞書）・`footnote_marker` の life 分岐・`match ctx.scheme` のディスパッチ |
| `richtext.py` | ほぼそのまま | **そのまま**（0 行） | 無し。`{party:}` の追加のみ（予想どおり） |
| `ids.py` / `env.py` / `fonts.py` | そのまま | **そのまま**（0–1 行） | 無し（`fonts.py` の 1 行は docstring） |
| `blueprints.py` | 要改造 | **要改造**（9 行） | `BLUEPRINTS_DIR`・`load_blueprint(genre)` の引数名・`available_genres()`・Blueprint モデルの `genre` フィールド |
| `scaffold.py` | 要改造 | **要改造**（19 行） | `scaffold(genre, ...)` の引数・前付けの genre 別分岐・`library` の scheme ディレクトリ参照 |
| `compose.py` | 要改造 | 要改造 | `doc.json` の `genre` フィールド（models 経由） |
| `build.py` | 要改造 | **要改造**（17 行） | ラベル導出の numbering 呼び出し・`AUTO_LABEL_TYPES`・caption 採番・**当事者解決の追加**（新規） |
| `library.py` | 分割 | **要改造**（9 行） | `LIBRARY_DIR / scheme /` のディレクトリ規約（方式名でディレクトリを切っている） |
| `styles.py` | 分割 | **そのまま**（0 行） | 無し。YAML 側が保険固有だったのみ（機構は流用できる） |
| `lint/rules.py` | 要改造 | **要改造**（10 行） | `denylist.txt`（**179 行すべて保険会社・共済名**＝全面差し替え）・L03 の検出正規表現・L13 の meta 必須項目 |
| `lint/quality.py` | 要改造 | **要改造**（5 行） | `POLITE_SCHEMES`（方式→敬体/常体）・`scheme == "teikan"` の分岐 → 契約書は全 doctype 常体 |
| `lint/structure.py` | 要改造 | 要改造（4 行） | L04 の blueprint `required` 解釈・L09 の上限 |
| `lint/budget.py` | 要改造 | 要改造（3 行） | `chars_per_page` の既定 1500・`blueprint.default_style` 参照 |
| `lint/qa_authored.py` | 要改造 | 要改造 | L16 の要求値（15 問・表 3・**図 3**）→ 契約書は図 2・apply 2 |
| `lint/{table_headers,similarity,walk,base,runner}.py` | — | **ほぼそのまま**（0–4 行） | 無し（`similarity.py` の 4 行は docstring） |
| `render/html.py` | 一部改造 | **要改造**（19 行） | 前付けの `purpose_index` / `rider_index` / `petname_table`（保険固有。契約書では削除）・`CSS_DIR` がモジュール定数（**テストから差し替えられない**＝P0 のスキップ判断の原因。decisions 27） |
| `render/weasy.py` / `inline.py` / `formula.py` | 一部改造 | ほぼそのまま（0–2 行） | 無し |
| `render/diagrams/*.py`（6 種） | 一部改造 | **`mock.py` のみ要改造**（3 行） | `SUBJECT_TITLE`（保険証券・保険金請求書・お申込み画面）→ 契約書の見本（注文書・請求書 等）に差し替え |
| `layout/extract.py` / `fallback_align.py` | そのまま | **そのまま**（0–1 行） | **無し（実測済みの核心。触らない）** |
| `verify/checks.py` / `normalize.py` | ほぼそのまま | **そのまま**（0 行） | 無し。V-P1〜V-P5 の追加のみ |
| `qa/auto.py` | 要改造 | **要改造**（23 行・うち実害 2 行） | 質問文言の「この**約款**において」「**約款**中の表記で」の 2 箇所 → doctype 語に差し替え。残り 21 行は docstring |
| `qa/validate.py` | 要改造 | ほぼそのまま | 無し |
| `answer.py` / `figure_graph.py` | そのまま | **そのまま**（0 行） | 無し |
| `export.py` / `export_models.py` / `search_set.py` | ほぼそのまま | **要改造**（12/2/3 行） | `Passage.genre` / `Passage.product_name` / `ElementRow.genre` の列名 → `doctype` / `title`。`search_set.py` の scoped クエリ生成が `product_name` に依存 |
| `eval/*.py`（harness・metrics・oracle・search） | ほぼそのまま | **そのまま**（0–1 行） | 無し。列挙番号の除去パターンに契約書の「ア イ ウ」が含まれるか要確認 |
| `manifest.py` / `batch.py` / `cli.py` | ほぼそのまま | 要改造（4/12/21 行） | `genre` 列・CLI の `--genre` オプション・ヘルプ文の「約款」→ `--doctype`・`doctypes` コマンドの追加 |

### 予想と食い違ったもの（3 件）

| モジュール | 予想 | 実測 | 意味 |
|---|---|---|---|
| `styles.py` | 「分割」（機構をコアへ、YAML をファミリー側へ） | **そのまま使える** | 機構はすでに `styles_dir` 引数でパラメータ化されている。YAML を差し替えるだけでよい |
| `export.py` / `search_set.py` | 「ほぼそのまま」 | **要改造** | `product_name` が検索クエリ生成（scoped クエリ「商品名＋見出し」）に組み込まれており、列名の改名だけでは済まない。契約書では「文書題名＋見出し」に置き換える設計判断が要る |
| `render/html.py` | 「一部汎用化」 | **要改造＋制約の発見** | `CSS_DIR` がモジュール定数でパラメータ化できず、テストが repo 直下の `styles/css/` を要求する。これが P0 のテストスキップ判断（decisions 27）の直接の原因 |

### 捨てたもの

| パス | 理由 |
|---|---|
| `blueprints/*.yaml`（10 件）・`styles/*.yaml`（13 件）・`library/clauses/`・`content/`（30 件）・`specs/` | 保険固有の資産。契約書のものを P2〜P3 で新規に書く |
| `scripts/vlm_reading/`（3 件・293KB） | 保険 3 文書の VLM 予測実例。契約書の実例は P7 で作る（decisions 28） |
| `assets/icons/` | 中身は `.gitkeep` のみだったが、置き場として残した |

## 6. 姉妹プロジェクトとの関係

- `../insurance-contracts/`（yakkan-synth）＝**コードの供給元かつ凍結された参照実装**。
  本プロジェクトから書き換えない。実装の意図が分からなくなったら、まず
  `../insurance-contracts/docs/` の `decisions.md` / `gotchas.md` / `remaining_issues.md` を読む
  （実害と対処が全部残っている）。
- `../structured-docs/`（docsynth）＝**仕様の供給元**。`contract` ファミリーの設計（`{party:}`・signature・
  schedule・課題カタログ G1〜G13・lint L19・評価/検証計画）はここで一度設計されており、本プロジェクトは
  それを単一ドメインの実装として具体化する。docsynth 側の設計と食い違う判断をするときは
  `docs/decisions.md` に「docsynth との差分」として明記する（将来の統合コストになるため）。
- **将来 `families/contract/` として docsynth へ切り出す可能性を残す**：`blueprints/` `numbering/` `styles/`
  `library/` `denylist.txt` を Python から独立させ、`family: "contract"` を `source.json` に固定値で持たせる
  （`docs/schema.md` §2）。切り出しの是非は v1 完成後に判断する。
