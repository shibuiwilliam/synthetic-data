# progress.md — 進捗と次の一手

CLAUDE.md §0.2-1 でセッション開始時に読み、§0.2-4 で終了時に更新するファイル。
各フェーズに「完了／未完／次にやる3タスク／落とし穴」を書く。フェーズの DoD は CLAUDE.md §12。

**現在地：P6 進行中（**113/113 ready**・100 content・5,085問）。直近セッション：2026-10-09（**検索評価セットの公開面を姉妹プロジェクト `contracts/` と揃えた**＝カードを英語面＋日本語面の二層に・`SHA256SUMS` 追加・frontmatter のキー構成。配布先は `cvusk/japanese-insurance-document-understanding` と `cvusk/japanese-insurance-document-understanding-retrieval` の 2 つ、ライセンスは両方 **CC BY 4.0**。**コミット・push・アップロードは人間が行う**＝T13・T14）。**

---

## P0 環境 — **完了**（DoD 達成）

DoD：`make check` が通る／日本語 A4 2 段組の smoke PDF が出る／WeasyPrint・Pango・フォントの版が
`docs/gotchas.md` にある。**3 つとも満たした。**

**完了したもの**
- リポジトリ運用：親 `synthetic-data` リポジトリを使用、`.gitignore`（親の `parts/` 打ち消し）、`docs/` 雛形、
  `.claude/rules/` 4 本、CLAUDE.md の分割（739 → 291 行）。
- uv プロジェクト：`yakkan-synth` / Python 3.12.9 / 依存 11 本 + dev 2 本を `pyproject.toml` に固定、`uv.lock`。
  WeasyPrint は **`==70.0`** で固定（最新安定版）。
- OS 依存：Pango 1.56.4 / HarfBuzz 11.3.3（Homebrew 導入済みを確認）。cffi 2.1.1 で libffi 動作。
- フォント同梱（36MB・全て OFL / IPA）：Noto Serif JP・Noto Sans JP（各 Regular/Bold）、IPAex明朝・ゴシック、
  Noto Sans Symbols・Symbols 2。出典 URL・版・SHA256 を `assets/fonts/SOURCES.md` に記録。BIZ UD 系は未取得（代替あり）。
- §10 のディレクトリ骨格、`README.md`、`Makefile`（setup / check / fmt / lint / test / doctor / smoke / doc / batch / clean）。
- `yakkan doctor`：Python・WeasyPrint・Pango・HarfBuzz・cffi・各パッケージ・pypdfium2 のラスタライズ・
  フォントの存在と代表文字 20 字の cmap 被覆を表で出す。NG があれば exit 1。
- `scripts/smoke_render.py`：A4・2 段組・@page ヘッダ/フッタ・結合セル表・インライン SVG・丸数字/黒丸数字の
  1 ページ PDF → 150dpi PNG。PNG を目視確認済み（崩れなし）。
- `yakkan/layout/extract.py`（box ツリー → element bbox）と `yakkan/verify/normalize.py`（読み順と正規化）の最小版。
- `tests/`：15 件（フォント被覆・正規化・読み順・往復一致・ヘッダ/フッタ分離・SVG テキスト・
  フォント混入なし・決定論・PNG 解像度）。`make check` で全通過。
- `.claude/settings.json`：許可リスト（uv / make / pytest / ruff / git 読み取り系）、
  `env` で `DYLD_FALLBACK_LIBRARY_PATH`、`dataset/` 手編集の拒否（`Edit(/dataset/**)` + PreToolUse フック）。

**前倒しで済んだもの（本来 P2）**
- **`scripts/probe_weasy.py` 相当の probe は完了**。box ツリーから element id → bbox が取れることを実証し、
  renderer を WeasyPrint で確定（`docs/decisions.md`）。`column-span: all` も動作確認済み。

**未完（P2 に送る）**
- `target-counter`（目次ページ番号）・`leader()`・`float: footnote`・`<ruby>` の probe。
- 複数ページでの表頭繰り返し（`thead`）の実挙動確認。
- PDF のメタデータ日時の固定（現状テキスト層の一致までは確認、バイナリ一致は未確認）。
- `yakkan doctor` に poppler 相当の確認は入れていない（pypdfium2 で足りるため不要と判断）。

---

## P1 モデル — **完了**（DoD 達成）

DoD：pydantic モデルと JSON Schema、numbering、richtext、lint L01–L03 / L07 / L08 / L13 が実装され、
単体テストと golden テストが通る／docs/schema.md のサンプル（旧 §5.10）が lint を通る。**すべて満たした。**

**完了したもの**
- `yakkan/models.py`：Source / Node / Block（9 種）/ Table / Cell / Figure / Diagram（6 種）/ Formula /
  TermDef / Layout / QA を pydantic v2 で定義。列挙は `Literal`、判別共用体は discriminator 付き。
  **執筆物 `SourceDraft`（derived なし）と build 後の `Source`（derived あり）を型で分離**し、
  執筆物に `derived` を書くと `extra="forbid"` で落ちる → lint L00。
- `schema/{source_draft,source,layout,qa}.schema.json`（JSON Schema 2020-12）を `yakkan schema export` で生成。
- `yakkan/ids.py`：ノード id（親を接頭辞に持つ）・ブロック id 接頭辞・セル/図ノード id の組み立てと検査。
- `yakkan/numbering.py`：nonlife / life / teikan の 3 方式、全角半角、丸数字の上限（⑳超は括弧数字＋警告）、
  単項無番号、teikan の第 1 項無番号、別紙の独立体系、`{ref:}` の解決（relative / short / full）。
- `yakkan/richtext.py`：9 種のトークンの再帰下降パーサと AST、平文化（参照解決・ラベル付き/なし）、
  エスケープ、未知トークンのエラー（位置つき）。
- `yakkan/compose.py`：`content/<cid>/doc.json` ＋ `parts/*.json` の読み込み（docs/schema.md §5.11 で新規に定義）。
- `yakkan/lint/`：ルール登録基盤（code・severity・element_id・path、`--quick`、`--only`）と
  **L00 / L01 / L02 / L03 / L07 / L08 / L12（部分）/ L13**。`denylist.txt` は損保・生保・共済 約90 語。
- `tests/golden/sample_min/`：オリジナル文の最小 content（2 章・別表・表 4 点・図 1 点・脚注・欄外注）。
  lint が error 0 / warn 0。ラベルと参照解決を golden JSON で固定（`--update-golden` で更新）。
- docs/schema.md を実装に合わせて更新（§5.2 Cover・constants・number_override_reason、§5.3 const/auto_label、
  §5.4 blocks_side_by_side・MergedInto、§5.11 parts 形式を新設）。乖離の判断は decisions.md に 13 行。

**未完（後続フェーズ）**
- lint L04（blueprint 必須要素）・L05（表）・L06（図）・L09（ページ数）・L10（文体）・L11（数値整合）・
  L14（QA）・L15（類似度）。L05/L06 は P2/P3、L04/L09 は blueprint と描画が要る。
- L12 の後半（定義されたが使われない語）は P4。
- `{ref:}` の表・図への参照は P2（キャプション採番と同時）。現状は L01 でエラーにして明示している。
- `yakkan/build.py`（derived の付与）は P2 の入口で作る。`scaffold.py` は P4。

## P2 レンダラ — **完了**（DoD 達成）

DoD：3 ページ相当のサンプルで PDF 生成・目次ページ番号の一致・テキスト往復一致・決定論を確認し、
renderer の確定を decisions.md に記録する。**すべて満たした**（`tests/golden/test_render.py`、`yakkan verify` が error 0 / warn 0）。

**完了したもの**
- `scripts/probe_weasy.py`（`make probe`）：22 項目を実測。結果表は decisions.md の付録。
  **renderer を WeasyPrint 70.0 で確定**（判断基準にあった pdfplumber 主経路化・ReportLab 切替は不要）。
- `yakkan/build.py`：parts 結合 → 番号・参照の解決 → 平文（ラベル有無）→ 目次 → 表の header_path・
  列挙表の自動ラベル → 図の経路 → `derived` 付与 → `source.json`。
- `styles/nl-a4-2col-mincho.yaml` ＋ `styles/css/*.css.j2`（Jinja テンプレート）、`yakkan/styles.py`。
- `yakkan/render/`：`html.py`（Source → HTML。全要素に id と data-kind、見出しはラベル span と文言 span を分離、
  項・号は CSS grid のぶら下げ）、`inline.py`（RichText → HTML。平文と同じ解決を使う）、
  `weasy.py`（HTML → render → layout 抽出 → PDF（メタデータ固定）→ PNG 150dpi）、`templates/document.html.j2`。
- `yakkan/layout/extract.py`：`layout.json` 全体（fragments・repeated 表頭・header/footer 分離・
  text_lines（LineBox 単位・region 付き）・reading_order（本文 → 欄外注））。
- `yakkan/layout/fallback_align.py`：pdfplumber の文字列を期待テキストに difflib で整列して bbox を復元。
- `yakkan/verify/checks.py`：V01 ページ数 / V02 フォント / V03 テキスト往復（JSON→PDF と box→pdfplumber の 2 方向）/
  V04 目次ページ一致 / V05 fragment 存在 / V06 はみ出し / V07 重なり / V08 bbox 突合 / V09 決定論。
- CLI：`yakkan build` / `render`（`--style` `--report` `--png/--no-png`）/ `verify`。
- `tests/golden/test_render.py`：layout.json（bbox 許容 0.5pt）と PDF テキスト層（完全一致）を golden 固定。
  サンプルは `sample_min`（3 ページ・表 4 点・脚注・欄外注・目次・別表）を流用し、内容を二重に持たない。

**probe で分かった非対応と代替（decisions.md に詳細）**
- `column-span: all` は `<table>` 直接では効かない → `<figure>` でくるむ。
- `float: footnote` 非対応 → 欄外注は条末に囲みで置く。
- `<ruby>` 非対応 → inline-block 積みで代替（実測で読みが上に出ることを確認）。
- box ツリーの y は pdfplumber の文字上端と 4〜5pt ずれる → IoU ではなく内包判定にした。

**未完（P3 以降）**
- **図の SVG 描画は P3**。いまは枠だけの placeholder を出し、render が note で知らせる。
  `layout.figures` も空のまま。
- lint L04 / L05 / L06 / L09〜L11（blueprint・表・図・ページ数見積り・文体・数値整合）。
- 2 段組でぶら下げ段落が段の境界で割れるとラベルだけ残る（gotchas に記録。見た目の調整は P6）。
- style は 1 種類のみ。付録A の残り 6 種は P6。

---

## P3 図 — **完了**（DoD 達成）

DoD：6 種の Diagram と Formula を JSON → SVG に変換でき、`figure_layout`（ノード id → bbox）が返り、
`layout.json` の `figures` にページ座標で統合される。各種 1 点のサンプルが PNG で崩れなく描ける。**すべて満たした。**

**完了したもの**
- `yakkan/render/diagrams/base.py`：文字幅見積り（全角 1.0em / ASCII 0.55em / 半角カナ 0.5em、
  `unicodedata.east_asian_width` で判定）、折返し、SVG 組立て（rect / polygon / line / polyline /
  text / text_block）、矢頭マーカー（id は図ごと）、`DiagramStyle.from_style`。
- 6 種：`flowchart`（格子・直交エッジ・菱形分岐・エッジラベル・書類形）／`tree`（lines / bracket / nested）／
  `steps`（LR は矢羽根、TB は枠＋下向き矢印、detail / asks / docs の小枠）／
  `timeline`（レーン・区間バー・イベント旗・目盛）／`annotated_mock`（証券の模式図＋バッジ＋凡例）／
  `matrix`（格子＋記号＋凡例）。
- `yakkan/render/formula.py`：`inline_boxes` と `fraction`（HTML/CSS で組む）。
- lint **L06**：エッジ端点の存在・格子座標の重複・最小複雑度（flowchart 5 ノード＋分岐 1／tree 3 階層／
  steps 4／timeline 4 要素／matrix 4×3）・`alt` と `facts` の非空・バッジと凡例の対応・
  matrix の行列数一致・timeline の目盛整合（warn）。
- `layout.figures`：`<svg>` の実寸と viewBox から倍率を求め、ノード bbox をページ座標（pt）へ変換。
  実測で倍率はちょうど 0.75（px→pt）。計算は `tests/unit/test_figure_layout.py` で数値検証。
- verify **V10**：図のノード座標が空でないこと、ラベルが PDF のテキスト層から読めること。
- `tests/fixtures/diagrams/`：6 種のサンプル（架空商品の手続き・補償構成・契約期間）。
  `scripts/preview_diagrams.py` で 1 枚にまとめて PNG 目視確認した。
- テスト 53 件追加（文字幅・折返し・6 種の描画・font-family 必須・bbox が viewBox 内・決定論・
  装飾なし・算式・L06 の 10 ケース・ページ座標の数値）。合計 178 件。

**目視で見つけて直した 3 件**
- flowchart：分岐エッジが本線と重なり、ラベルも衝突していた → 横の辺から出す経路に変更。
- steps：小枠の高さが 1 行ぶん足りず最終行が枠外にはみ出していた。
- timeline：右端のイベント旗が viewBox から切れていた → 内側に寄せる。

**未完（P4 以降）**
- `tree` の `bracket` / `nested` と `steps` の TB、`annotated_mock` の `claim_form` / `app_screen` は
  実装済みだが **fixture が無く目視未確認**。使う文書が出た時点で確認する。
- lint L04（blueprint 必須要素）・L05（表）・L09〜L11・L14・L15。
- style は 1 種類のみ。図の配色は palette に追従するので style 追加時は再確認する。

---

## P4 コンテンツ — a/b 完了、c（執筆）が残り

### P4-a 構造分析 — 完了
参考URL 8 件すべてを取得して構造分析し、`docs/reference_structures.md` を完成させた。
#5 は「リスク細分型海外旅行保険」と判明。blueprint 提案 B-1〜B-9 を提出。

### P4-b 骨組み — **完了**

- **blueprints 7 種**（`blueprints/*.yaml`）：必須要素と最小件数、章の入替許容範囲、特約プール、
  数値表記の variants、字数 budget。`yakkan/blueprints.py` が型として検査する。
- **styles 8 種**（付録A の 7 種 ＋ 素組みの `nl-a4-1col-plain`）。CSS は
  `styles/css/_base.css.j2` ＋ スタイル差分。`chars_per_page_estimate` は
  `scripts/calibrate_styles.py` で**実測較正**（当初の見積りは最大 1.6 倍ずれていた）。
- **条文ライブラリ 41 条・本文 8,765 字**（`library/clauses/{nonlife,life,teikan}/`）。
  すべてオリジナル。params（`constants`）と言い換え（`variants`）を持つ。
- **`yakkan/scaffold.py`**：blueprint ＋ seed → `doc.json` ＋ `parts/*.json`。
  見出し候補・TODO・必須要素・推定字数・安定 id を埋め、定型条は本文まで展開する。
- **`yakkan/compose.py`**：`_todo` を落として `SourceDraft` にする／残 TODO を数える。
- **lint L04 L05 L09 L10 L11 L12 L15 を追加**（L12 は完全版に差し替え）。`--skip` で断片を検査できる。
- **`.claude/agents/`**（author / reviewer / render-debugger）と
  **`.claude/commands/`**（/author /review /batch）。
- テスト 113 件追加（合計 291 件）。`tests/golden/test_pipeline.py` が 5 段の疎通を固定。

**疎通確認**：`auto` の空スケルトンで scaffold → lint → build → render(7 ページ) → verify が
端から端まで走る。全 7 ジャンルで scaffold → build を確認。
空スケルトンでは lint が「未執筆」を、verify が「描画漏れ」を指摘するのが正しい挙動で、
**空の項に 40 字入れると描画漏れが消えることをテストで固定**してある。

**この作業で見つけた不具合（すべて記録済み）**
- **段組の中に 1 ページを超える段またぎ要素があると、以降の内容が黙って消える**（WeasyPrint 70.0）。
  目次で踏んだ。テンプレートで目次を段組の外に出して解消。verify V05 だけが気づけた。
- **ページ分割の内部アサーションで落ちることがある**（内容の高さ次第。単調でない）。
  `RenderLayoutError` として明示的に失敗させる。自動回避はしない。
- `{auto_label}` が `exclusions` 表で採番されず stub が空になっていた（build と lint の両方を修正）。
- `sample_min` が `digit_style: fullwidth` なのに半角数字を使っていた（L10 が検出）。

### P4-c 執筆 — **完了**（7文書 8データセットが ready）

| content_id | style | ページ | 表 | 図 | 脚注 | 欄外注 | 参照 | reviewer 採点（修正前） |
|---|---|---|---|---|---|---|---|---|
| auto-0001 | nl-a4-2col-mincho | 16 | 16 | 5 | 20 | 4 | 78 | 3/5 |
| oneday-0001 | nl-a4-1col-plain | 13 | 15 | 3 | 21 | 3 | 38 | 3/5 |
| quake-0001 | nl-b5-2col-dense | 11 | 11 | 4 | 24 | 5 | 49 | 3/5 |
| quake-0001 | nl-a4-1col-gothic | 14 | 〃 | 〃 | 〃 | 〃 | 〃 | （2スタイル目） |
| health-0001 | nl-a4-2col-mincho | 14 | 12 | 4 | 25 | 6 | 69 | 2/5 |
| life-0001 | life-b5-1col-mincho | 18 | 12 | 3 | 20 | 2 | 28 | 2/5 |
| teikan-0001 | teikan-a4-1col-mincho | 12 | 5 | 1 | 0 | 0 | 21 | 3/5 |
| travel-0001 | travel-a4-1col-gothic | 14 | 11 | 4 | 27 | 5 | 58 | 3/5 |

全 8 データセットが **lint error 0 / verify error 0 / warn 0**、`manifest` は ready 8/8。`make check` 通過（291 テスト）。

**所要**：1文書あたり author サブエージェント1体で 20〜50 分（ツール呼び出し 48〜166 回）。
part 単位の並列委譲より、1文書を1体に任せるほうが整合性が取れた（part 間の数値・定義語の食い違いを本人が直せる）。
reviewer → 修正 の 2 周目で品質が大きく上がった。**reviewer を通さない初稿は公開できる状態ではなかった。**

**失敗**：quake の修正エージェントが 600 秒無反応で停止（stalled）。指摘12件は反映済みだったので親側で描画だけ仕上げた。
長時間タスクは途中成果がファイルに残る形で進めさせるのが安全。

### P4-c で見つかった、lint では検出できない問題の分類

1. **§0.4-1（転載禁止）の違反が5文書で同じ形をとって再発した。**
   auto の後遺障害等級表（支払割合 100/89/78…％と法令別表の逐語文言）、quake の支払割合・家財の損害割合・流失70％、
   health の等級表12個すべて一致＋むち打ち症条項、life の高度障害状態表6項目と入院の定義、travel の72時間と食中毒 carve-out。
   → **模倣は文章より「数値の列」と「列挙の順序」と「別表特有の語形」に出る。**
   golden fixture 自身も同じ違反をしていた。執筆時のチェックリストに「別表の数値列は必ず実物からずらす」を入れること。
2. **正解データ（gold）自体の誤り**：図の `facts` が本文と食い違う（auto「基本条項は四つの節」→実際は6節、travel「四つの部分」→実際は5章）。
   facts は QA の正解そのものなので、間違っていると評価が壊れる。
3. **章順の逆転**：`doc.json` の `parts` がファイル名順でそのまま章順になり、車両補償が賠償責任より前に来ていた。
   根本原因は `blueprints/auto.yaml` の `variants.order_shuffle`。ジャンルによっては章順に制約が要る。
4. **表・図が導入文より前に描画される**：表を「条直下の blocks」に置くか「項の blocks」に置くかで読み順が変わる。
5. **`meta.constants` の値の衝突**：auto は 30日が4概念、60日が3概念。数値 QA の弁別力が無い。
6. **一覧表が掲げる保険金に条文が無い**（oneday で2件）。表と条文の対応が空振りする。
7. **業法・実務との不整合**：teikan の剰余金処分を取締役会決議にしていた（相互会社では総代会決議）。

### P4-c で直した基盤側の欠陥

- **verify V05 が表・図の丸ごと欠落を検出できていなかった**（ノードしか照合していなかった）。quake で表2つが verify 通過のまま消えていた。
- **段またぎ要素がページ境界で以降の内容を全部捨てる**（最重要）。章見出しを段内に戻し、`render` が欠落を検出したら停止するようにした。
- **L09 の計量が二重に間違っていた**：生の RichText を数えていた（`{term:...}` を丁寧に使う文書ほど不利）＋係数が未較正（最大 +28%／−11%）。
  平文で数え、7文書の実測で較正し直した（最大相対誤差 5.6%）。恒常的に出て無視される warn を解消。
- **`records` が全文書の表で null**（§2-4 の二重表現違反）。`scripts/fill_records.py` で35表を機械導出し、lint L05 に検査を追加。
- **fragment が自分の text_lines を覆っていないことがあった**（段またぎの脚注）。抽出側で包含関係を保つようにした。
- ヘッダの章名が1ページ先行／別表見出しの孤立／表紙のペットネーム未描画／古い PNG の残留／
  L05 の records 突合が `{ref:}` を空文字に解決するバグ。

### 次にやる3タスク
1. `docs/shared_fixes.md` の残り（特約の独立番号体系が最大。4文書が独立に同じ指摘を出した）。P6 送りも含めて判断する。
2. P5：自動 QA・執筆 QA・`specs/batch_v1.yaml`（7 genre × 3 content ≈ 30 文書）。
   **content は 7 ジャンル × 1 本しか無い**ので、各ジャンルあと2本ずつ執筆する必要がある。
3. 同一ジャンル 3 文書になると L15（類似度）が実際に効く。定型条ライブラリ由来の文の扱いを確認する。

**落とし穴（P5 で効くもの）**
- 「レンダリングが成功した」は「内容が全部載った」を意味しない。`render` の欠落検査と verify V05 を必ず見る。
- `RenderLayoutError` は字数の増減では通らない形がある（構造を変えると通る）。quake は A4 2段では通らず、2スタイル目を A4 1段に変えた。
- **サブエージェント作業中に共有コードを触ると彼らが幻の失敗を追う。** 今回2回やってしまった。
  verify の強化だけは描画結果を変えないので例外的に安全。

## P5 QA・バッチ — **完了**（28データセット・1,262問・DoD 達成）

### 成果

| | 値 |
|---|---|
| content | **21 本**（7 ジャンル × 3 本） |
| データセット | **28**（各ジャンルの content 1 と oneday-0002 が 2 スタイル） |
| ページ | 402（1 文書 11〜19。上限 20 以内） |
| 字数 | 365,363（平文基準） |
| 表 / 図 | 360 / 103 |
| QA | **1,262 問**（自動 840 ＋ 執筆 422） |
| `yakkan batch` | **ready 28/28・失敗 0** |
| lint / verify / qa | 全 content・全データセットで error 0 |

QA の種別分布（自動／執筆）：extract 93/57・table_lookup 81/74・figure_fact 88/59・
table_reason 72/67・negative 85/44・figure_path 88/33・count 94/30・crossref 94/26・
definition 57/23・locate 88/9。**執筆 QA は自動生成が苦手な型（table_lookup・table_reason・
figure_fact）に寄っており、狙いどおり補完関係になっている。**

### 実装

- **`yakkan/answer.py`**：`answer.json`（source ＋ layout ＋ ページ別テキスト ＋ outline）。
  繰り返し表頭は `pages[].text` に 1 回だけ入れる。
- **`yakkan/qa/auto.py`**：10 種別。種別ごとに候補を作ってからラウンドロビンで取るので、
  図が 1 点しかない定款でも偏らず 30 問に届く。
- **`yakkan/qa/validate.py`**：L14。型整合・evidence の存在と描画・extract 系の包含・
  **図の答えが実在するラベルか**・page_hint・重複。
- **`yakkan/batch.py` ＋ `specs/batch_v1.yaml`**：失敗しても止まらず、段別・原因別に集計する。
- **`yakkan clean`**：生成物の掃除もコマンドで行う（手で `rm` すると §0.4-3 と区別がつかない）。
- 執筆 QA は **`content/<cid>/qa_authored.json`**。`page_hint` と `locate` の答えは
  スタイル依存なので evidence から機械的に付け直す。

### 同一ジャンルの重複率（L15・Jaccard・21 組）

**最大 16.4%**（teikan-0002/0003）、最小 3.0%（auto-0001/0003）。閾値 30% に対して十分な余裕。
差別化は商品設計のレベルで効いた：

| ジャンル | 0001 | 0002 | 0003 |
|---|---|---|---|
| auto | ノンフリート等級 | 運転者限定・年齢条件 | 使用目的＋走行距離区分 |
| oneday | 24時間×最長7日・3プラン | 12時間＋延長・2プラン | 予約制・カフェテリア方式 |
| quake | 建物の構成割合 | 調査部位の配点 | 区分所有建物（棟＋室内を 65:35 で合成） |
| health | 日額型 | 定額一時金型 | 実損てん補型 |
| life | 終身保険（相互） | 収入保障保険（株式） | こども保険（相互） |
| teikan | 生保相互会社 | 損保株式会社（監査役会） | 生保株式会社（指名委員会等設置） |
| travel | 海外旅行 | 国内旅行 | 団体旅行 |

### P5 で見つけて直した欠陥

**QA 生成側**：定義表の用語を五十音インデックスから拾っていた／`crossref` の参照元が「(2)」だけ／
timeline のレーンをまたいだ隣接を聞いていた／**`figure_fact` の答えが常に「はい」で図を読まずに全問正解できた**／
`count`・`negative` の evidence と page_hint の不一致。

**answer.json**：**段内で繰り返される表頭を除外できていなかった**（ページ単位で id を弾いていたため。
health の B5 で 45 字の二重計上）。bbox 判定に直す途中で「複数ページに出たら 2 ページ目以降は再掲」
という推測を入れたら、ページをまたぐ容れ物まで対象になって 3 ページ目が空になった。

**描画**：`render_source` が `source.json` を書いておらず batch で 5 件落ちた／
**ヘッダの編と章が別々の string で噛み合わなかった**（`data-headerpath` で 1 本にして解消）。

**lint**：`--similarity` が CLI に無かった／未執筆 content が比較対象に入って幻の重複（79〜100%）が出た／
**`colspan`（2段ヘッダ）が作れなかった**（原因は L05 の列数計算だけで、他は最初から対応していた）／
**キャプションの無い列挙表が表番号を消費して番号が飛んでいた**（4 人が独立に報告）。

**自分の誤り**：travel-0003 の執筆 QA で図に存在しないノード名を答えに書き、L14 を素通りした
→ `figure_path` の答えが実在するラベルかを検査するルールを足した。

### 残課題（P6 候補）→ **2026-09-22 に shared_fixes を全部やった**

P5 の終わりに挙げた 6 件は、A1・A5 を含め **すべて決着した**（`docs/shared_fixes.md` 参照）。
残っているのは「測ったうえで現状が最善」と判断した 3 件だけで、直すべきものは無い。

## shared_fixes 一掃 — **完了**（2026-09-22）

`docs/shared_fixes.md` の A〜D を優先度・依存で並べ替えて片づけた。4 コミット。

| 段 | 項目 | やったこと |
|---|---|---|
| 1 | B2 B3 B4 B5 B6 D3 D4 D5 | 表紙の余白物を消す／ページ番号を全角に／`page_break` 実装／timeline と matrix の描画／QA に `apply`／別表の要件を構造だけにする |
| 2 | C1 C2 C3 C4 D1 A3 | 定款の号を（１）に／通し番号方式では `{ref:}` に章を冠さない／附則は項番号で起こす／附則内参照に「附則」を冠す／`kind_label`／表・図を `{ref:}` の参照先にできるように |
| 3 | A2 | 図と算式の中のトークンを build が解決し、描画・QA・verify がそれを当てる。既存 21 content の図の数値を `{const:}` に寄せた（解決後の文字列が変わらないことを機械で確認） |
| 4 | B1 | 表題を `<caption>`（表の中）へ。段・ページでの分離が 23/320 → 0/320 |
| 5 | A4 | 特約を `kind: "rider"` に。番号を持たず、条は特約ごとに第１条から。38 本を移した |

- **測って「直さない」と決めたもの**：A1（条末脚注の欠落＝現行コードでは再現しない。3 文書 55 通りで 0 件）、
  A5（rowspan の継続セル＝紙面と正解が一致しており読み取り課題として妥当）、
  D2（`RenderLayoutError` は 48 字幅の「帯」。内容の長さをずらして外す）。
- 各段の終わりに `yakkan batch specs/batch_v1.yaml` を回して 28/28 ready、`make check` 緑を確認した。
  ページ数は 402 ページのまま変わっていない。
- 新しい probe：`scripts/probe_figure_tokens.py`（図のトークンが PDF のテキスト層まで通るか）、
  `scripts/probe_table_caption.py`（表題と表が離れる回数）。
  新しい道具：`scripts/figure_consts.py`（図の数値を `{const:}` に寄せる）、
  `scripts/figure_strings_snapshot.py`（置換が無害かを確かめる）。

## 参考URL #9〜#14 と 3 ジャンルの追加 — **完了**（2026-09-22）

ユーザーが参考URLを 6 件追加し、「追加した文書形式も生成できるように」と指示した。
6 件を構造分析して `docs/reference_structures.md` §3.2 に追記し、3 ジャンルを足した。

| genre | 参考 | 文書 | ページ | 本文 | QA |
|---|---|---|---|---|---|
| `golf` | #11 | 賠償責任保険 約款集（ゴルファー保険） | 12 / 10 | 10,075 字 | 45 |
| `group` | #12〜#14 | 団体定期保険 普通保険約款＋特約条項 | 16 / 11 | 10,286 字 | 45 |
| `jyusetsu` | #9・#10 | 重要事項等説明書（**条を持たない**） | 8 / 9 | 7,605 字 | 45 |

仕組みとして足したもの（いずれも既存 7 ジャンルには影響しない）：

- 番号方式 2 種（`group`：項＝丸数字・号＝「１．」・細目＝(ｱ)／`jyusetsu`：条を使わない）
- `meta.article_heading`（`inline` / `above` / `plain`）と `LabelInfo.run_in_label`
- `meta.footnote_style`（`inline` / `remarks_box`＝黒丸数字と「第N条　備考」の枠）
- `Node.badges`（「契約概要」「注意喚起情報」）と blueprint の `kind: badge` 要件
- `style.page_number`（`plain` / `dashed`）
- 第1項が無番号の方式での参照の書き下し（「第1項第4号」）。L01 に「空文字に解決される参照」を追加
- style 4 種（`nl-wide-2col-plain` `grp-a4-1col-mincho` `grp-a4land-2col-plain` `jys-a4-1col-gothic`）

データセットは **28 → 34**（468 ページ・1,532 問）。`yakkan batch` で 34/34 ready。

途中で見つけて直した欠陥：
- `analyze_reference_pdf.py` が MediaBox の原点が (0,0) でない PDF で落ちる（#11）
- `calibrate_styles.py` のスタブが古く `digit_style` を持たず落ちる
- バッジの CSS を `inline-block` にすると box ツリーが同じ文字を 2 回拾う（V03）
- 枠つきの備考が段またぎで割れると続きが版面の外に出る（V03。`break-inside: avoid` で解消）
- `group` の無番号の第1項を指す参照が**空文字**に解決されていた（18 件）

## 評価データセット化 — **完了**（2026-09-22）

ユーザーが 4 つの利用目的（LLM/VLM の読み取り精度／構造解析／予測 JSON の採点／
検索エンジンの評価）を示したので、34 文書を実測でレビューし、欠落 11 件を埋めた。
レビューと計画は `docs/eval_dataset_plan.md`、使い方は `docs/evaluation.md`。

| 直したもの | 前 | 後 |
|---|---|---|
| 図の経路（`paths`）を持つ図 | 21/111（flowchart のみ） | **111/111**（6 種共通の正規化グラフ） |
| `layout.elements[].kind` の内部クラス名 | 396/1059 | **0** |
| 読み順に出る本文ノード | 11/90 | **90/90** |
| 構造位置（citation・kind・parent_id・path_ids） | 無し | `labels` / `outline` / `toc` に付与 |
| 列挙の親子 | 無し | `derived.enumerations`（表・号・箇条書き） |
| 要素インデックス | 無し | `elements.jsonl`（28,787 行） |
| 検索評価セット | 無し | パッセージ 2,391／クエリ 1,549／qrels 2,654 |
| 評価ハーネス | 空パッケージ | `yakkan eval`（読み取り 13 指標＋検索 7 指標） |

**自己評価**：`yakkan eval --oracle` を **全 34 文書**で回して全指標が満点、
崩した予測では下がることを確認した（`tests/unit/test_eval.py` で固定）。
検索も満点の並びで nDCG@1/5/10 = 1.0。

## 残課題 R1〜R6 の解消 — **完了**（2026-09-22）

`docs/remaining_issues.md` に記録した 6 件をすべて片づけた。

| # | 内容 | 結果 |
|---|---|---|
| R1 | 検索 qrels の部分適合が薄い | grade 1 が 317 → 3,805。適合 1 件だけのクエリ 69% → 32% |
| R2 | 新ジャンルの content が各 1 本 | 6 文書を執筆し **40 データセット・543 ページ・1,802 問** |
| R3 | `answer.json` の二重持ち | `source`/`layout` を外し **42MB → 5.3MB**。`load_answer()` で結合 |
| R4 | 階層つき表番号 | `meta.caption_numbering: chapter`（「表1-1」）。group-0002 で使用 |
| R5 | 古いタグ | `dataset-v2` を打った |
| R6 | 較正値が同値になる | 原因は `.para { break-inside: avoid }` による段落単位の量子化。実コーパス基準に変え L09 の誤差 3.8% → 2.3% |

**自己評価**：40 文書すべてで `yakkan eval --oracle` が全 13 指標満点、検索も nDCG 1.0。

### 残課題 S1〜S9 を解消（2026-09-22）

`docs/remaining_issues.md` の第2次（S1〜S7）と第3次（S8・S9）をすべて片付けた。

| # | 内容 | 結果 |
|---|---|---|
| S1 | 執筆 QA の配りが守られていない（13 content） | **L16** で強制。13 content を書き直し、全 content で error 0 |
| S2 | 「表1-1」と「表1」の同居 | chapter 採番では章の外に番号を振らない。L01 を番号の有無で判定 |
| S3 | docs の数値が陳腐化 | `docs/eval_dataset_plan.md` に §5「いまの実測」を追加 |
| S4 | 執筆ヘルパが scratchpad にしかない | `scripts/authoring.py` に格納し、checklist から参照 |
| S5 | qrels の grade 1 が黙って切られる | `related_truncated` / `n_related_total` を出し、切り方を文書横断で均等に |
| S6 | 自己評価が循環している | **`misread()`** を追加。崩しの強さに対する**単調性**をテストで固定 |
| S7 | 満点の予測で `outline.page_acc` が 0.39 | 見出しの突合に出現回数を混ぜた。**40 文書すべてで全指標が満点に** |
| S8 | manifest が黙って陳腐化する | `yakkan manifest check` を追加し `make check` に入れた |
| S9 | 評価向け成果物にスキーマが無い | `export_models.py`＋`schema/{element,passage,query,qrel}` |

**最終の実測**：40 データセット・543 ページ・QA 1,800 問・ready 40/40。
検索はパッセージ 2,894／クエリ 1,944／qrels 6,781（grade 2 が 2,976・grade 1 が 3,805）。
自己評価は読み取り・検索とも満点（検索の recall@10 が 0.976 なのは、適合が 10 件を超える
クエリがあるため）。テスト 414 件が通る。

### 残課題 T1〜T9 を解消（2026-09-23）

`docs/remaining_issues.md` の第4次。**外から使ったときに本当に使えるか**を確かめる回。

| # | 内容 | 結果 |
|---|---|---|
| T1 | 実物の予測でハーネスを回していない | `scripts/baseline_reader.py`（doc.pdf だけを見る素朴な読み取り器）を 40 文書に通し、**契約の穴 3 件**を発見 |
| T7 | outline に紙面に出ない節点が 13.9% | 除いた。見出し F1 が「出せないもの」に支配されなくなった |
| T8 | 列挙に番号を含めるか未定 | どちらでも正解にする（NFKC の前に落とす） |
| T9 | 構造位置の突合が全文一致だけ | 包含での対応づけを併記 |
| T2 | Recall@k が解釈できない | `recall_ceiling@k` を併記 |
| T3 | タグが古い | `dataset-v3` を切った（push はしていない） |
| T4 | 縦組み見出し・style 追加 | 回転は**実測して不採用**。素組み 2 段組 style を 1 本追加 |
| T5 | ルビ | **実測して不採用**（ルビにならず、読みがテキスト層に混ざる） |
| T6 | スキャン風画像 | **見送り**（正解が増えず、劣化の根拠も無い） |

**最終の実測**：41 データセット・560 ページ・QA 1,845 問・ready 41/41・style 13 種。
検索はパッセージ 2,894／クエリ 1,944／qrels 6,781。
満点の予測は **41 文書すべてで全指標満点**。テスト 420 件。

素朴な読み取り器の 40 文書平均（ハーネスが外からの予測をどう採点するかの実例）：
CER 0.061／見出し F1 0.353／構造位置 coverage_contains 0.232／表 TEDS 0.254／
図ノード F1 0.261／読み順 τ 0.975／bbox IoU 0.525。

### 残課題 W1〜W6 を解消（2026-09-23）

`docs/remaining_issues.md` の第5次。**VLM で実際に読んで採点した**回。

| # | 内容 | 結果 |
|---|---|---|
| W1 | VLM の予測で採点していない | `jyusetsu-0001` の 8 ページを**画像として読み**、正解を見ずに予測を作って採点。**欠陥 2 件を発見** |
| W6 | 目次のリーダー罫が「.」としてテキスト層に入る | 点線の**下線**に替えた。VLM の CER **0.0973 → 0.0004** |
| W5 | 予測に使う語彙が未定義 | `docs/evaluation.md` §3 に明記。同じ予測の見出し種別正解率 **0.0 → 1.0** |
| W3 | 予測スキーマだけ手書き | `Prediction` / `SearchRun` をモデル化。`--pred` は形の違いを警告する |
| W2 | 全文書を 1 コマンドで採点できない | `yakkan eval --all [--oracle / --pred-dir]` |
| W4 | 図のエッジ・経路が外部予測で未採点 | W1 で採点（エッジ F1 0.429・経路 F1 1.0） |

**VLM の実測**（`scripts/vlm_reading/`）：本文 CER 0.0004（8 ページ中 7 ページが 0.0000）・
見出し F1 0.795（precision 1.0）・見出しの page/citation/kind 正解率とも 1.0・
構造位置 coverage 0.808（当たったものは citation 正解率 1.0）・表 TEDS 1.0・
図 経路 F1 1.0・列挙 1.0・読み順 τ 1.0。

**W6 の副産物**：リーダー罫を `border-bottom` で描いたら行が 0.4pt 高くなり、
golf-0001 の 2 スタイルで条末脚注が消えた。**V03 が自動で捕まえた**ので、
box の大きさを変えない下線に替えた（`docs/gotchas.md` に追記）。

### 残課題 X1〜X4 を解消（2026-09-23）

`docs/remaining_issues.md` の第6次。**2 段組でも VLM で読み、表の意味座標と bbox も出した**回。

| # | 内容 | 結果 |
|---|---|---|
| X1 | VLM 予測に `cells` と `bbox` が無い | 表セル F1 **0.0 → 1.0**、bbox IoU 0.631（当たり率 0.75） |
| X2 | VLM 読み取りが 1 ジャンル・1 段組のみ | **2 段組の約款（10 ページ）で CER 0.0000・構造位置 coverage 1.0** |
| X3 | X1・X2 で出た契約と正解の欠陥 | **4 件**（下記）をすべて修正 |
| X4 | 図の辺ラベルが重なる | `Svg.edge_label()` で回避（ずらす・白地・最後に描く） |

X3 の 4 件：

1. **列挙として組んだ表が「表」として二重に数えられていた** → TEDS 0.2663 → 1.0
2. **`outline` に番号のある項を入れることが未記載** → 見出し F1 0.5778 → 0.9841
3. **キャプションの突合が正規化されていなかった**（「表１」と「表1」） → 正規化した
4. **`header_cols` の宣言漏れ**（272 表中 23 表）→ lint **L17** を新設して 13 content を修正。
   表セル F1 0.6792 → 0.8212

**2 段組は読み取り器の限界であって版面の難しさではなかった。** 規則ベースの読み取り器（T1）は
2 段組で構造位置のカバー率 0.062 だったが、VLM は 1.0。

### 残課題 Y1〜Y3 を解消（2026-09-23）

`docs/remaining_issues.md` の第7次。**3 ジャンル目（生保のしおり）を VLM で読み**、
表セル F1 の残差を切り分けた回。

| # | 内容 | 結果 |
|---|---|---|
| Y1 | 表セル F1 0.8212 の残差 | **`header_cols` の宣言漏れ**が 1 表残っていた。L17 を「0 そのものを error」に強化し、外れ値 2 表を修正 |
| Y2 | `life` が VLM で未検証 | **CER 0.0008・見出し F1 1.0・構造位置 1.0/1.0・TEDS 1.0** |
| Y3 | Y1・Y2 で出る欠陥 | 1 件（Y1）。**`life` からは新しい欠陥は出なかった** |

**3 ジャンル・3 版面の VLM 読み取り**（`scripts/vlm_reading/`）：

| 指標 | jyusetsu（1段組・重説） | golf（2段組・約款集） | life（1段組・しおり＋約款） |
|---|---|---|---|
| 本文 CER | 0.0004 | 0.0000 | 0.0008 |
| 見出し F1 | 0.7945 | 0.9841 | 1.0 |
| 構造位置 coverage / citation | 0.808 / 1.0 | 1.0 / 1.0 | 1.0 / 1.0 |
| 表 TEDS / セル F1 | 1.0 / 1.0 | 1.0 / **1.0** | 1.0 / 0.9767 |
| 図 ノード / エッジ / 経路 | 0.5 / 0.429 / 1.0 | 1.0 / 0.929 / 1.0 | 1.0 / 0.878 / 1.0 |

**本文 CER はどの版面でも 0.001 未満。** ハーネスと正解データは外から使える状態にある。

### 次にやる3タスク

1. `dataset-v6` を配布するかを決める（タグは切ってあるが push していない）。
2. 読み取り側の**実サービスの予測**を通して、指標が運用の判断に足りるかを見る
   （ここまでは我々自身が読み手を務めた）。
3. 報告を待って、スキャン風画像（T6）や style の追加を判断する。

---

---

## P6 追加分 — content を 20 本足す（2026-09-27）

ユーザーの依頼「保険約款を追加で20点生成し、`dataset/` に適切に保存せよ」に対し、
**新規 content を 20 本（10 ジャンル × 2 本）執筆**した（既存 content の別スタイル描画ではない。
選択の経緯は `docs/decisions.md` 2026-09-27）。

### 成果

| | 追加分 | 合計 |
|---|---|---|
| content | **20 本** | 50 本 |
| データセット | **21**（travel-0005 のみ 2 style） | 62 |
| ページ | 246 | 806 |
| 字数（平文） | 209,486 | — |
| 表 / 図 | 161 / 40 | — |
| QA | 945 問（自動 630 ＋ 執筆 315） | 2,790 問 |
| lint / verify / qa | 全 20 content・全 21 データセットで **error 0 / warn 0** | — |

### 題材（既存 3 本と重ならないものを選んだ）

| genre | -0004 | -0005 |
|---|---|---|
| auto | 大鷹フリート自動車保険（法人フリート・運行記録） | 桜坂くらしの自動車保険（個人・ノンフリート等級） |
| oneday | 蒼井時間単位自動車保険（6時間単位・スマホ申込） | 木曽路帰省ドライブ1日保険（借用自動車・事前予約） |
| quake | 塩屋崎店舗併用住宅地震保険（住宅部分と店舗部分を別に認定） | 六花家財地震保険（家財のみ・品目区分で認定） |
| health | 陽向丘がん診断費用保険（診断一時金・先進医療） | 峰岸介護一時金保険（要介護状態の判定・介護年金） |
| life | 青麦定期保険（更新型・余命給付特約） | 瀬戸あかり養老保険（満期保険金・生存給付金） |
| teikan | 片瀬野損害保険相互会社（総代会・基金・監査役会） | 銀杏坂少額短期保険株式会社（監査等委員会設置会社） |
| travel | 東雲留学保険（長期滞在・就学中断費用） | 銀河橋ビジネス出張保険（法人・包括契約） |
| golf | 楓が丘 自転車保険約款集 | 汐見台 ペット飼育者総合保険約款集 |
| group | 鶴見野 団体就業不能保障保険 | 常陸みどり 団体医療保険 |
| jyusetsu | 白南風 海外旅行総合保険の重要事項説明書 | 甲斐路 賃貸住宅入居者総合保険の重要事項説明書 |

### 執筆の進め方

- `scripts/authoring.py` のヘルパ（`art` / `enum_table` / `table` / `kana_table`）で parts を組み、
  1 content = 1 スクリプトにした。lint の指摘（L11 の定数衝突・L04 の必須要素・L09 の字数）を
  スクリプト側で直して再生成する往復で仕上げている。
- 会社名 20・商品名 20・ペットネームはすべて新規の架空名。denylist に当たらないことを lint で確認。
- `lint --similarity` の 30% 超えは group-0005（34%）と travel-0005（31%）で 1 回ずつ出た。
  いずれも基本条項の定型部分だったので、**言い回しを書き換えて 30% 未満に下げた**（写しの指紋を残さない）。

### 詰まった点

- **WeasyPrint 70.0 のページ分割 AssertionError**（§14 の既知事象）を group-0004 と travel-0004/0005 で踏んだ。
  本文を数十字ずつ増減させる回避は travel では効いたが、group-0004 では 3 通り試しても効かず、
  別 style（`grp-a4land-2col-plain`）で描いた。**render が失敗した直後の verify は前回の成果物を見て通ってしまう**ので、
  render の成否を必ず確認してから verify する必要がある。
- L11（数値整合）は**部分文字列一致**なので、「５万円」が「２５万円」に、「１年」が「２０２１年」に当たる。
  定数の値は他の数値の部分文字列にならないものを選ぶ（または定数にしない）。
- `kana_table` の行順は五十音ではなく**引数の順**なので、QA の evidence セル id は
  `source.json` の `derived.plain_text` を見て確かめてから書く。

### 残っていること

- `dataset/group-0004--grp-a4-1col-mincho/` が**空ディレクトリとして残っている**
  （render が落ちた時に作られたもの。`dataset/` への `rm` は権限で止まるため消せていない）。
  manifest には載っていないが、`ls` すると 63 件に見える。**人手で削除が必要**。
- タグは切っていない（v1 系の tag 運用に合わせるなら `dataset-v7` 相当を切るかの判断が要る）。

---

## P6 追加分（2回目） — content をさらに 20 本足す（2026-10-03）

ユーザーの依頼「保険約款を追加で20点生成し、`dataset/` に適切に保存せよ」の再度の指示に対し、
2026-09-27 と同じ方針で **新規 content を 20 本（10 ジャンル × 2 本）執筆**した
（`<genre>-0006` と `<genre>-0007`。選択の経緯は `docs/decisions.md` 2026-10-03）。

### 成果

| | 追加分 | 合計 |
|---|---|---|
| content | **20 本** | 70 本 |
| データセット | **21**（auto-0007 のみ 2 style） | 83 |
| ページ | 254 | 1,060 |
| 字数（平文） | 216,977 | — |
| 表 / 図 | 154 / 42 | — |
| 条末脚注 | 502 | — |
| QA | 945 問（自動 630 ＋ 執筆 315） | 3,735 問 |
| lint / verify / qa | 全 20 content・全 21 データセットで **error 0 / warn 0** | — |

### 題材（既存 5 本と重ならないものを選んだ）

| genre | -0006 | -0007 |
|---|---|---|
| auto | 月ヶ瀬福祉車両総合保険〈やわらぎ〉（昇降装置・車椅子の固定装具） | 伊吹野カーシェア自動車保険（共同利用・会員制・NOC） |
| oneday | 砂山はじめてドライブ1日保険（初心者向け・24時間単位） | 栃の木キャンピングカー1日保険（レンタル車両・車中泊） |
| quake | 浅間台二世帯住宅地震保険（区分ごとの認定） | 錦川地震危険上乗せ補償保険（主契約への上乗せ） |
| health | 小春日女性疾病入院保険〈こはるび〉（女性特定疾病の加算） | 岩倉台スポーツ傷害保険（運動起因疾病の区分表） |
| life | 玉響低解約返戻金型終身保険（返戻金の抑制期間） | 五十鈴引受基準緩和型医療保険（告知3項目） |
| teikan | 相互会社の定款（総代会・社員配当） | 株式会社の定款（指名委員会等設置会社） |
| travel | 遠野原ワーキングホリデー保険〈はたらくたび〉（就労中の事故） | 梓川国内ツアー参加者保険（募集型企画旅行・団体扱い） |
| golf | 風見ヶ丘ドローン操縦者賠償責任保険（飛行の記録・機体損害） | 雪代スキー・スノーボード保険〈ゆきしろガード〉（コース外滑走） |
| group | 岬みらい団体傷害保険（日常生活動作による後遺障害区分） | 立花野拠出型企業年金保険（積立金・運用の方法の変更） |
| jyusetsu | ペット医療費用保険の重要事項説明書 | 個人年金保険の重要事項説明書 |

### 執筆の進め方（前回と同じ）

- `scripts/authoring.py` のヘルパで parts を組み、1 content = 1 スクリプト。
  lint → build → render → verify → qa を回し、指摘をスクリプト側で直して再生成する。
- `rider_index`（6 列・2 段ヘッダ）は毎回手で組むと長いので、スクラッチパッドに
  `rider_index_table()` を置いて auto の 2 本で共用した。恒常的に要るなら
  `scripts/authoring.py` に移すとよい。
- 会社名 20・商品名 20 はすべて新規の架空名。`lint --similarity` の 30% 超えは
  oneday-0007（37%）・life-0006（38%）・travel-0006（32%）・health-0007（33%）・auto-0007（32%）で出た。
  いずれも**基本条項の定型部分**なので、文体の階層（「…するものとします」／「…します」／
  「…いたします」／「…でございます」）を content ごとに振り分けて書き換えた。

### 詰まった点

- **条末脚注が PDF から落ちる（verify V03）** が 4 文書で出た（golf-0007・health-0006・health-0007・auto-0007）。
  box ツリーには出るのに PDF のテキスト層に無い、という形で、段・ページの境界に脚注が来た場合に起きる。
  該当条の本文か脚注の文言を 20〜60 字伸ばすと解消した（`docs/decisions.md` 2026-10-03）。
- **ページ分割の AssertionError** は golf-0006・group-0006・travel-0006 で踏んだ。
  数十字の増減では効かないことがあり、**条を 1 本足す**のが確実だった。
- `render` が失敗しても `verify` は**前回の成果物**を見て通るので、render の出力行
  （「render 完了 … / N ページ」）を必ず確認する。前回も同じ点で時間を使っている。
- L09 の下限（auto 13,000 字・health 14,000 字・golf/group 9,000 字）は積み増しに手間がかかる。
  **条末脚注の文言は字数に数えられない**ので、不足分は項の本文に足す。
- `index_kana` に使えるのは `ア カ サ タ ナ ハ マ ヤ ラ ワ` の 10 行だけ。`ウ`・`ミ` などを
  書くと L00 で落ちる（前回と同じ踏み方をした）。
- `timeline` 図の `unit` は `day` / `month` / `year` / `label` のみ。`hour` は L00 で落ちる。
- 自動 QA は timeline の `spans` の端点をラベルとして拾うので、**端点は `axis.ticks` に載せる**
  （載せないと「図に存在しないラベルを答えにしている」で L14 が落ちる。group-0007 で 1 件）。

### 残っていること

- 前回からの繰り越し：`dataset/group-0004--grp-a4-1col-mincho/` の空ディレクトリは**まだ残っている**
  （`dataset/` への `rm` は hook で止まるため消せない）。**人手で削除が必要**。
  今回も `dataset/auto-0007--nl-a4-1col-gothic/` が同じ経緯で残ったが、こちらは
  **2 スタイル目として作り直して正規のデータセットにした**（manifest に ready で載っている）。
- `content/<genre>-0006` `-0007` の 20 ディレクトリは**未コミット**。
- タグは切っていない（`dataset-v7` 相当を切るかはユーザーの判断）。

---

## P6 追加分（3回目） — content をさらに 20 本足す（2026-10-03）

ユーザーから 3 度目の「保険約款を追加で20点生成し、`dataset/` に保存せよ」。
2026-09-27 の決定（「20点」＝新規 content 20 本の執筆）をそのまま踏襲し、
10 ジャンル × 2 本 = **20 content を新規に執筆**した（`<genre>-0008` / `-0009`）。

- 題材は既存 7 本と重ならないものを選んだ。auto：電気自動車（駆動用電池・充電設備）／軽貨物配送（受託貨物賠償・休車損害）、oneday：レンタカー補償／1時間単位のまちのり、quake：沿岸住宅（津波）／マンション共用部分、health：こども医療／シニア骨折、life：介護保障終身／就業不能保障、teikan：少額短期保険株式会社／生命保険相互会社、travel：クルーズ／シニア国内旅行、golf：つり・ボート／キャンプ、group：団体がん保障／団体介護保障、jyusetsu：ゴルファー総合保険／学校団体傷害保険。
- 文体は同ジャンルの既存 content と段を変えた（auto の例：-0006「します」／-0007 口語寄り／-0008「ものとします」／-0009「いたします」）。`lint --similarity` の 30% 判定は、この段のずらしで通している。
- 全 20 本で lint error 0・warn 0、verify error 0・warn 0、QA 45 問（自動 30＋執筆 15）error 0。
- バッチ仕様は `specs/batch_v4.yaml`。

| doc_id | genre | ページ | 字数 | 表 | 図 | 脚注 | QA |
|---|---|---|---|---|---|---|---|
| `auto-0008--nl-a4-2col-mincho` | auto | 15 | 15,778 | 14 | 4 | 35 | 45 |
| `auto-0009--nl-b5-2col-dense` | auto | 15 | 15,929 | 13 | 4 | 38 | 45 |
| `golf-0008--nl-wide-2col-plain` | golf | 13 | 11,176 | 9 | 2 | 27 | 45 |
| `golf-0009--nl-a4-2col-mincho` | golf | 11 | 10,953 | 9 | 2 | 29 | 45 |
| `group-0008--grp-a4-1col-mincho` | group | 18 | 11,230 | 4 | 1 | 29 | 45 |
| `group-0009--grp-a4land-2col-plain` | group | 12 | 11,336 | 3 | 1 | 29 | 45 |
| `health-0008--nl-a4-2col-mincho` | health | 14 | 16,454 | 9 | 2 | 36 | 45 |
| `health-0009--nl-b5-2col-dense` | health | 15 | 16,470 | 9 | 2 | 42 | 45 |
| `jyusetsu-0008--jys-a4-1col-gothic` | jyusetsu | 9 | 8,353 | 8 | 1 | 20 | 45 |
| `jyusetsu-0009--nl-a4-1col-gothic` | jyusetsu | 10 | 8,292 | 8 | 1 | 21 | 45 |
| `life-0008--life-b5-1col-mincho` | life | 17 | 10,825 | 7 | 2 | 17 | 45 |
| `life-0009--life-a4-1col-gothic` | life | 15 | 10,790 | 7 | 2 | 18 | 45 |
| `oneday-0008--nl-a4-1col-plain` | oneday | 9 | 6,784 | 5 | 2 | 16 | 45 |
| `oneday-0009--nl-a4-1col-gothic` | oneday | 9 | 5,769 | 5 | 2 | 17 | 45 |
| `quake-0008--nl-b5-2col-dense` | quake | 10 | 10,259 | 8 | 2 | 25 | 45 |
| `quake-0009--nl-a4-1col-gothic` | quake | 13 | 9,466 | 7 | 2 | 25 | 45 |
| `teikan-0008--teikan-a4-1col-mincho` | teikan | 9 | 4,603 | 5 | 1 | 0 | 45 |
| `teikan-0009--teikan-a4-1col-mincho` | teikan | 10 | 4,834 | 5 | 1 | 0 | 45 |
| `travel-0008--travel-a4-1col-gothic` | travel | 11 | 9,364 | 7 | 2 | 23 | 45 |
| `travel-0009--nl-a4-1col-gothic` | travel | 11 | 9,361 | 7 | 2 | 22 | 45 |

合計：**20 データセット・246 ページ・208,026 字・表 149・図 38・脚注 469・QA 900 問**。
`dataset/manifest.json` は **ready 103 / 104 件**（1 件は下記の失敗分）、全体で 1,306 ページ・4,635 問。
検索評価セットはパッセージ 8,561／クエリ 5,610／qrels 18,166 件（コーパスは content ごとに 1 style ＝ 90 文書）。

### 残件：`dataset/auto-0009--nl-a4-1col-gothic`（21 ページ・failed）

auto-0009 を `nl-a4-1col-gothic` でも描こうとしたが **21 ページ**になり、
CLAUDE.md §0.4-5 のページ上限に反するため採用していない（採用は `nl-b5-2col-dense`・15 ページ）。
L09 の下限（auto は 13,000 字）があるため本文を削って 20 ページに収めることはできない。
render が先にディレクトリを書き出すため生成物が残っており、`dataset/` 保護フックのため AI 側では削除できない。
**人間による `rm -rf dataset/auto-0009--nl-a4-1col-gothic` が必要**（`HITL_TODO.md` H9）。
削除後に `yakkan manifest update` を回せば ready 103/103 になる。

### 次の 3 タスク

**検索クエリ改修（AA 群）と `life` の用語集（AA10）はどちらも完了した**
（`docs/search_query_plan.md` W0〜W26）。`TASK.md` T1〜T11 はすべて回答済みで判断待ちは無い。

1. **`TASK.md` T5 の削除を人間に実施してもらう**（承認済みだが `dataset/` 保護フックが AI の
   `rm` を拒否した）。実行後に `yakkan manifest update` で ready 103/103 になる。
2. **AA12：盲検レビュー**（計画 R-C）。構築経緯を継承しない独立エージェントに
   `dataset/search/` と公開済みの契約だけを渡し、クエリが解けるかを外から確かめる。
   **サブエージェントを使うのでユーザーの指示を待つ**（Z1 では 3 本のうち 2 本で契約の穴が出た）。
3. 配布（`TASK.md` T7）に向けて、**T11（ライセンス）の回答**と、追加 60 content に対する
   H2・H3（架空性・転載なし）の確認を人間にお願いする。

---

## P6 追加分（4回目） — content を 10 本足して **合計 100 本**にする（2026-10-04）

ユーザーの依頼「`dataset/` に保存されている保険約款を合計で100点になる生成し、`dataset/` に
適切に保存せよ」に対し、**新規 content を 10 本（10 ジャンル × 1 本）執筆**した（`<genre>-0010`）。
「点」の単位を 1 content とする読みの根拠は `docs/decisions.md` 2026-10-04。
**content は 90 → 100 本**、データセットは 104 → 114（ready 113）になった。

### 成果

| | 追加分 | 合計 |
|---|---|---|
| content | **10 本** | **100 本** |
| データセット | 10 | 114（ready 113） |
| ページ | 121 | 1,458 |
| 字数（平文） | 102,376 | — |
| 表 / 図 | 73 / 19 | — |
| 条末脚注 | 183 | — |
| QA | 450 問（自動 300 ＋ 執筆 150） | 5,085 問 |
| lint / verify / qa | 全 10 content・全 10 データセットで **error 0 / warn 0** | — |
| 検索評価セット | — | パッセージ 9,456／クエリ 8,824／qrels 25,435（コーパス **100 文書**） |

### 題材（既存 9 本と商品設計のレベルで重ならないものを選んだ）

| genre | -0010 | ページ | 字数 |
|---|---|---|---|
| auto | 鈴懸二輪車総合保険〈かぜまち〉（二輪車・盗難・保護帽・同乗者） | 14 | 15,378 |
| oneday | 霜月スノードライブ1日保険（冬季限定・最長3日・冬用タイヤの装着が条件） | 9 | 6,485 |
| quake | 鳶尾火山地域地震保険（噴火・火山灰の堆積・地盤の液状化） | 9 | 9,031 |
| health | 柑子日帰り手術保険〈てのひら〉（日帰り手術・放射線治療・通院） | 15 | 16,877 |
| life | 宵待個人年金保険〈ゆたかな季〉（据置・確定年金／終身年金・繰下げ） | 16 | 10,383 |
| teikan | 海道再保険株式会社 定款（再保険専業・保有の限度・異常危険準備金） | 10 | 5,251 |
| travel | 白嶺トレッキング旅行保険（山域の行程・捜索救助費用・高度障害） | 10 | 8,891 |
| golf | 駒形乗馬総合保険約款集（乗馬の賠償・傷害・用具・競技会の入賞費用） | 13 | 10,918 |
| group | 団体終身保険（退職後も続く保障・個人契約への移行・払済保険） | 17 | 10,990 |
| jyusetsu | 青竹サイクル保険の重要事項説明書（自転車・条例への対応） | 8 | 8,172 |

バッチ仕様は `specs/batch_v5.yaml`。`yakkan batch` で **ready 10/10**。

### 執筆の進め方（前回までと同じ）

- `scripts/authoring.py` のヘルパ（`art` / `table` / `enum_table` / `kana_table`）＋
  スクラッチパッドの共通ヘルパ（2 段ヘッダの `h2table`、`box`、`formula`、`terms`）で parts を組み、
  1 content = 1 スクリプトにした。lint の指摘をスクリプト側で直して再生成する往復で仕上げている。
- 会社名 10・商品名 10 はすべて新規の架空名。`lint --similarity` の 30% 超えは **1 件も出なかった**
  （題材を商品設計のレベルで変えたため。文体も既存と段をずらしている）。
- 別表の数値列（後遺障害の区分と割合・地震の損害割合・手術の給付倍率）はすべて自作し、
  実在の基準の数列を用いていない（`docs/authoring_checklist.md` §1）。

### 詰まった点

- **L09 の下限が重い**（auto 13,000 字・health 14,000 字）。初稿は 8,000〜12,000 字で止まるので、
  条を足して積み増す往復が要る。**条末脚注の文言は字数に数えられない**ので、不足分は項の本文に足す。
- **WeasyPrint 70.0 のページ分割 AssertionError** を health-0010 で踏んだ。数十字の増減では通らず、
  **条を 1 本足して**解消した（§14 の既知事象。前回までと同じ）。
  このとき `render` が失敗しても `verify` は**前回の成果物**を見て通ってしまうので、
  render の出力行（「render 完了 … / N ページ」）を必ず確認する必要がある。**3 回続けて同じ点で時間を使っている。**
- **L11（数値整合）は部分文字列一致**なので、「１０年」が「１０年以上」に、「0円」が「5,100円」に当たる。
  定数の値は他の数値の部分文字列にならないものを選ぶ（または定数にしない）。
- **crossref の gold は解決後の文字列を確かめてから書く。** 章をまたぐ参照は「第２章第６条」のように
  **題名を伴わない**形に解決されるので、「第６条（灰の取片づけの費用）」と書くと gold が間違う
  （quake-0010 で 1 件。`source.json` の `derived.refs` を見て直した）。
- scaffold の書きかけ part が残ると L19 が出る。共通ヘルパの `save_doc()` で
  `doc.json` の `parts` に無いファイルを消すようにした。

### 検証

- 全 10 content で lint error 0 / warn 0（`--similarity` 含む）、全 10 データセットで verify error 0 / warn 0、
  QA 45 問（自動 30 ＋ 執筆 15）で error 0。
- `yakkan export` を回し直し、検索評価セットを **100 文書**のコーパスで作り直した。
- `yakkan eval --oracle` を auto-0010・jyusetsu-0010・life-0010 で回し、**全 15 指標が満点**。
- `uv run pytest -q` 471 件通過、`ruff check` 通過、`manifest check` は「実ファイルと一致」。
- PNG を目視（auto-0010 p2 の目的別もくじ＋2 段ヘッダの特約一覧、group-0010 p7 の備考枠＋timeline、
  jyusetsu-0010 p3 のバッジ＋○×マトリクス、quake-0010 p5 の 2 段組＋flowchart＋算式、
  life-0010 p6 の timeline＋税制表）。崩れなし。

### 残っていること（前回からの繰り越し）

- `dataset/group-0004--grp-a4-1col-mincho/`（空ディレクトリ）と
  `dataset/auto-0009--nl-a4-1col-gothic/`（21 ページで不採用）は**まだ残っている**。
  `dataset/` への `rm` は hook で止まるため AI 側では消せない。**人手で削除が必要**（`HITL_TODO.md` H9）。
  削除後に `yakkan manifest update` を回せば ready 113/113 になる。
- `content/<genre>-0010` の 10 ディレクトリは**未コミット**（`TASK.md` T1 により AI はコミットしない）。

## P6 追加分（5回目） — 利用者向けデータカードの新設（2026-10-04）

計画と仕様は **`docs/data_card.md`**（タスク D1〜D9）。ユーザーの依頼は
「`dataset/` を網羅的に正確に把握してデータカードを書き、**データを追加したら更新されるように
改善する**」。参考にしたのは隣の `contracts/dataset/data-card.md`（契約書プロジェクト）。

### 作ったもの

| パス | 役目 |
|---|---|
| `docs/data_card.md` | 仕様の正本（節と「数値の出所」の対応表・測り方の決め・自動更新の 3 重・D1〜D9） |
| `yakkan/datacard.py` | `collect()` → `render_card()` → `write_card()` / `check()`。1,093 行の参考実装を約款向けに作り直した |
| `yakkan/cli.py` | `yakkan datacard [update\|check]`。`export` の末尾で `write_card()` を呼ぶ |
| `yakkan/manifest.py` | `corpus_artifacts` に `data-card.md` を足す |
| `Makefile` | `check` に `datacard-check`、`batch` に `datacard update` |
| `tests/unit/test_datacard.py` | 13 件（焼き込み禁止・鮮度検出・母数検出・決定論・failed 耐性ほか） |
| `scripts/verify_data_card.py` | **測り方そのものの検算。** `yakkan/datacard.py` を一切使わず別経路で再計算する |
| `dataset/data-card.md` | 生成物（13 節・約 615 行） |

### 生成されたカード（実測）

114 文書（ready 113 / failed 1）・100 content・10 genre・13 style・1,458 ページ・
本文 1,290,210 字・紙面 2,046,886 字・表 1,013（セル 19,787・結合 1,150）・
図 269（ノード 3,251・辺 3,209・経路 893）・算式 66・参照 2,059・列挙 455（項目 2,229）・
定義語 1,585（`{term:}` 18,521）・定数 2,205・脚注 2,574・QA 5,085・
要素索引 97,242 行・容量 899.9 MiB / 2,414 ファイル。

### 開発中に実測で見つけたこと（カードを書く前には分からなかった）

- **`jyusetsu` は「条を持たない」と宣言しているが、実装は `kind: "article"` を使っている。**
  番号方式が「第◯条」ではなく「①」と振るだけだった。当初 `"article" not in kinds` で
  「条を持たない文書」を数えようとして**全 114 文書が条文型**になった。
  **条ラベルの形**（`第` で始まるか）で見るのが正しい（実測：条文型 90 content、丸数字型 10 content）。
- **`front_matter` の表を数え落としていた。** `purpose_index` / `rider_index` / `petname_table` は
  `Node.blocks` の外にあり、本文の木だけを走ると表が 970 件（manifest は 1,013）になり、
  `semantic_type: purpose_index` が「宣言はあるが使用 0」に**誤って**見えた。
- **PDF の埋め込みフォントは全文字走査だと 114 文書で約 2 分かかる。** ページのフォント資源
  （`/BaseFont`）から読むと約 2 秒で、**114 文書すべてで同じ結果**になることを検算で実測してから
  速い方を採用した（検算側は別経路である価値のため全文字走査のまま）。
- **本文の文字数（1,290,210）と紙面の文字数（2,046,886）が 1.6 倍違う。** `derived.plain_text` は
  **表紙・目次・計算した番号ラベル**を含まない（いずれも別の要素として描かれる）。
  カードに両方を載せ、違いの理由を明記した。
- **`dataset/` に成果物でない `render.pdf` が 41 件残っている**（2026-09-26 の OTF→TTF 調査の痕跡）。
  manifest の `artifacts` には出ないので今まで気づかなかった。カードが申告するようにした。
- **`unverified` を「不合格」と呼ぶと嘘になる。** `manifest update --no-verify` の manifest では
  status が決まらないので、`failed` と分けて数えるようにした。
- **使用 0 の観点が 6 件、黙って消えていた。** 観点名を「測る側」にしか持っていなかったため、
  ペットネーム対応表・細目・`qa_heading`・`page_break`・`number_override`・縦書きセルが
  カードの「未使用」の表に出ていなかった。観点名を 1 か所（`SKELETON_FEATURES` /
  `FORMAT_FEATURES`）に集めて両側から使うようにし、**使用 0 が 7 → 13 件**になった。
  ずれはテストで検出する。
- `blueprints/travel.yaml` の `description` が「（仮案）」のまま残っていた（CLAUDE.md §15 では
  2026-09-21 に確定済み）。カードが宣言をジャンル名として出すので外した。

### 検証

- **`scripts/verify_data_card.py` で 164 項目を突合**（スカラ 22・容量 7・分布 16・文書の全件 114 行・
  検索 3・disclaimer 1）→ **すべて一致**。pydantic を通さない素の dict 走査・フォントは全文字走査・
  カードの Markdown の表から読み戻す、の 3 点で別経路を担保した。
  この検算自身のバグも 1 件見つけた（「項目」見出しの表を節で切らずに拾い、§7 の代わりに §3 を読んでいた）。
- **文書を足す／削る実測**：3 文書の小さな `dataset/` で (1) 1 本足して `manifest update` だけ回すと
  `datacard check` が exit 1 で古さを検出（「行数が違う（425 → 466）」「文書（PDF） 2 → 3」）、
  (2) `datacard update` で追従して通る、(3) 1 本削っても同じ、(4) 2 回書いて **md5 一致**（決定論）。
- `uv run pytest -q` **486 件**通過（471 ＋ 新規 15）、`ruff format --check` / `ruff check` 通過。
- カードを目で通して 10 件の表示上の欠陥を直した（genre 別の題名欄が 10 商品名で潰れる→
  blueprint の名称と目標ページに置き換え・style 別の判型と段組が最後の 1 文書で上書きされる・
  「ジャンプごとに」の誤字ほか）。

### 残っていること

- **ライセンスと配布条件は未決のまま**カードに「未決」と書いた（`TASK.md` T11・`HITL_TODO.md` H13）。
  **AI は決めない。** 決定が入ったら §12 の固定文を書き換える。
- `render.pdf` 41 件と前回からの繰り越し 2 件（空ディレクトリ・21 ページの不採用文書）の削除は
  **人手が必要**（`dataset/` への `rm` は hook で止まる。`HITL_TODO.md` H9）。
  消せばカードの容量と `status: failed` の節が自動で追従する。

## セッション記録

| 日付 | やったこと | 次の一手 |
|---|---|---|
| 2026-09-21 | §15 確定、docs/ 雛形、CLAUDE.md 分割（739→291行）、.gitignore、.claude/rules | P0：Python 3.12 化 → uv sync → doctor → probe_weasy |
| 2026-09-21 | P0 完了（uv・フォント同梱・doctor・smoke PDF・往復検証・settings/hook）。box ツリー probe 成功で renderer 確定 | P1：models / numbering / richtext / lint L01–L03 |
| 2026-09-21 | P1 完了（models・schema export・ids・numbering・richtext・compose・lint 8 規則・golden sample）。仕様の欠落 5 件を docs/schema.md に追記 | P2：build.py → テンプレート/CSS → 目次まわりの probe |
| 2026-09-21 | P2 完了（probe 22 項目 → renderer 確定、build・style・テンプレート・layout 抽出・verify 9 種・golden）。3 ページのサンプルで verify が error 0 / warn 0 | P3：図の SVG 6 種と lint L06 |
| 2026-09-21 | P3 完了（図 6 種＋算式、lint L06、layout.figures のページ座標、verify V10、fixture 6 点を目視確認）。テスト 178 件 | P4：reference_structures → blueprints・scaffold → auto を 1 文書 |
| 2026-09-21 | P4-a 完了（参考URL 8 件の構造分析、travel の商品種別を特定、blueprint 提案 B-1〜B-9） | 回答待ち 3 件を確認 → blueprints 7 種と scaffold |
| 2026-09-21 | P4-b 完了（blueprint 7・style 8・条文ライブラリ 41 条・scaffold/compose・lint 7 規則追加・agents/commands）。5 段の疎通確認。WeasyPrint の内容欠落バグを発見し修正 | P4-c：auto を 1 文書執筆 → review → 残り 6 ジャンル |
| 2026-09-22 | `docs/shared_fixes.md` を一掃（C1–C4・D1・A3 → A2 → B1 → A4 の 4 コミット）。28/28 ready・402 ページ・1,262 問を維持 | P6：`yakkan eval` / style 追加 / `dataset-v1` の打ち直しを決める |
| 2026-09-22 | 参考URL #9〜#14 を追加・分析し、golf / group / jyusetsu の 3 ジャンルを実装。34/34 ready・468 ページ・1,532 問 | 新ジャンルの content 2〜3 本目 / 階層つき表番号 / `yakkan eval` |
| 2026-09-22 | 評価データセット化（欠落 11 件を実測でレビューし P1〜P10 を実施）。elements.jsonl・検索評価セット・`yakkan eval` を追加し、全 34 文書で自己評価が満点 | grade 1 の拡充 / 新ジャンルの content 2〜3 本目 |
| 2026-09-22 | 残課題 R1〜R6 を解消。新ジャンルの content を 3 本ずつにし（40 データセット）、qrels の部分適合を拡充、answer.json の二重持ちを解消、較正の原因を究明 | データセット v2 の配布 / 読み取り側からのフィードバック |
| 2026-09-22 | 残課題 S1〜S9 を解消。執筆 QA を L16 で強制、chapter 採番の重複解消、misread による単調性検査、**満点の予測が 40 文書すべてで全指標満点に**（見出し突合の取り違えを修正）、manifest の鮮度検査、評価向け成果物の型と JSON Schema | データセット v2 のタグ / 読み取り側の実物の予測で `yakkan eval` を回す |
| 2026-09-23 | 残課題 T1〜T9 を解消。**素朴な読み取り器を書いてハーネスを外から検証**し、契約の穴 3 件（outline に見えない見出し／列挙の番号／全文一致だけの突合）を修正。Recall の上限を併記、素組み style を追加、ルビと縦組み見出しは実測して不採用、`dataset-v3` を切った | 読み取り側の実物の予測で `yakkan eval` を回す / v3 の配布判断 |
| 2026-09-23 | 残課題 W1〜W6 を解消。**VLM（Claude 自身）がページ画像を読んで予測を作り採点**。正解データの欠陥（目次のリーダー罫がテキスト層に「.」として入る）と契約の穴（予測の語彙が未定義）を発見して修正。CER 0.0973→0.0004、見出し種別 0.0→1.0。`yakkan eval --all` と予測スキーマのモデル化も実施 | 他ジャンルでも VLM 読み取りを 1 本通す / 配布判断 |
| 2026-09-23 | 残課題 X1〜X4 を解消。**2 段組の約款を VLM で読み**（CER 0.0000・構造位置 coverage 1.0）、表の意味座標と bbox も出した。契約と正解の欠陥 4 件（列挙表の二重計上・outline の範囲・キャプションの正規化・header_cols の宣言漏れ）と図の辺ラベルの重なりを修正。lint L17 を新設 | 生保のしおりでも VLM 読み取り / 配布判断 |
| 2026-09-23 | 残課題 Y1〜Y3 を解消。**生保のしおり（16 ページ）を VLM で読み**（CER 0.0008・見出し F1 1.0・構造位置 1.0/1.0）、新しい欠陥は出なかった。表セル F1 の残差を切り分け、L17 を「header_cols=0 そのものを error」に強化 | 実サービスの予測で採点 / 配布判断 |
| 2026-09-23 | `HITL_TODO.md` の決定欄をユーザーが記入。**H1〜H6・H8 を実行**：CLAUDE.md を239行に再分割（`docs/lint_rules.md` 新設）、架空性・転載なし・560ページ目視・執筆QA450問（H2〜H5）の確認結果と評価仕様3点（H6）の承認を `docs/decisions.md` に記録、`docs/decisions.md` の仮決め4件（git運用・CLAUDE.md行数・BIZ UDPフォント・travel style）を全て現状維持で確定、**GitHub への push を実行**（`main` 62コミット＋`dataset-v1`〜`v6` の全6タグ。private のまま維持）。**H7（外部サービスでの読み取り採点）は具体的なサービス名・API アクセス手段が無く未着手** | H7：どの読み取りサービスに投げるかの回答待ち |
| 2026-09-23 | 残課題 Z1〜Z3 を解消（H7 の代替実行）。実在の外部サービスへのアクセス手段が無いため、**構築経緯を継承しない独立サブエージェント3体**に `pages/*.png` と公開済みの契約（`docs/evaluation.md`・`schema/`）だけを渡して盲検で読ませた（auto-0001・teikan-0001・group-0001）。teikan は新しい欠陥なし（CER 0.0）。auto・group で**列挙用の表に caption が付き紙面には「表N」と印字されるのに採点から除外される**欠陥を発見し、全 content を機械的に走査したところ 9 箇所（auto-0001×2・quake-0002×6・travel-0003×1）で発生していたと判明。lint **L18** を新設して修正し、影響する4文書を build/render/verify/qa で作り直した。`timeline` 図のエッジ規則が `docs/evaluation.md` に不正確に書かれていた誤りも発見・修正。`make check` は429件全通過。**文字どおりの第三者商用サービスでの検証は、サービス名とアクセス手段の提示があれば別途対応**（`docs/remaining_issues.md` Z1〜Z3） | 文字どおりの外部サービスでの検証（要ユーザー提示）／配布判断 |
| 2026-09-26 | ユーザーから「`doc.pdf`/`render.pdf` が空」と3回にわたり報告された26文書を深く調査し、**根本原因を特定・修正**。pdfplumber・pypdfium2・poppler では正しく読めるのに `pdffonts` で調べると Noto Serif/Sans JP（`.otf`=CFF埋め込み）を使う文書だけが該当し、41文書中1文書の例外もなく該当スタイルの Noto 使用と一致した。WeasyPrint 70.0 の CFF 埋め込みが macOS の Preview/Quick Look で描画されない既知の互換性問題と判定し、`scripts/otf_to_ttf.py`（fontTools）で `.ttf`（TrueType輪郭）に変換（cmap・advance widthは元と完全一致を検証）。影響する26文書を再render・再verify・再QA、`render.pdf` 41件・`elements.jsonl`等も再生成。`make check` 431件全通過、全41文書で CFF 埋め込みゼロを確認（`docs/gotchas.md`・`docs/decisions.md` 2026-09-26） | コミット・配布判断 |
| 2026-09-27 | **content を 20 本追加**（10 ジャンル × 2 本）。新規執筆で会社・商品・題材・数値をすべて書き起こし、lint/build/render/verify/qa を全本で通した（21 データセット・246 ページ・945 問）。`specs/batch_v2.yaml` を新設、export と manifest を再生成（62/62 ready） | 空ディレクトリ 1 件の削除（人手）／タグを切るかの判断 |
| 2026-10-03 | **content をさらに 20 本追加**（10 ジャンル × 2 本・`-0006`/`-0007`）。新規執筆で会社・商品・題材・数値をすべて書き起こし、lint/build/render/verify/qa を全本で通した（21 データセット・254 ページ・945 問）。`specs/batch_v3.yaml` を新設、export と manifest を再生成（83/83 ready） | 空ディレクトリ 1 件の削除（人手）／`content/` のコミット／タグを切るかの判断 |
| 2026-10-03 | 3 度目の「20点追加」。10 ジャンル × 2 本 = 20 content を新規執筆（`<genre>-0008` `-0009`）。20 データセット・246 ページ・900 問を追加し、`specs/batch_v4.yaml`・export・manifest を更新（ready 103/104） | `HITL_TODO.md` H9（21 ページの `auto-0009--nl-a4-1col-gothic` の削除）を人間に依頼 → `manifest update` 再実行 |
| 2026-10-03 | **全90 content・103 ready datasetを文面／内容整合の観点で横断レビューし、32 content・39レイアウトを修正・再生成**。相互会社の特別決議（総代の半数以上出席＋出席議決権の4分の3）、賠償責任の免責（重過失・無免許・酒気帯びを除外しない）、対人賠償の自賠責超過、groupの敬体、誤った尊敬語・不自然な費用負担表現、QA回答・計算を是正。L10もgroup/jyusetsuと脚注直前文末を検査するよう強化。完全lint、変更39レイアウトのrender/verify/QA、全コーパスexport、manifest checkがすべて error 0 / warn 0 | 既知のH9（不採用auto-0009 A4成果物の人手削除）のみ継続 |
| 2026-10-03 | **検索クエリの弁別力を実測し、改修提案を `docs/search_query_design.md` に書いた**（ユーザー指摘：`term`／`heading` のクエリが約款で広く使われる単語で対象を特定できない）。`scripts/probe_search_queries.py` を新設して 6 通りに測定：素朴な文字 2-gram BM25 で term nDCG@1 **0.920**・heading **0.927** と飽和（クエリが gold の `title` の字面コピーだったため）、「保険金」は 80 文書・1,969 パッセージに出るのに grade 2 は 2 文書だけ（不良設定）、`MAX_RELATED` の打ち切りが grade 1 総量の 40%（3,629 件）を黙って非適合にしていた。測定中に **`qa` の gold が 2,916/3,819（76%）誤った文書を指すバグ**（`element_id` が文書内でしか一意でないのにコーパス全体で索引）と見出しクエリへの番号ラベル混入 173 件も発見。施策 AA-1〜AA-14 を Phase 1〜3 に分け、人間の判断が要る 3 件（J1〜J3）を切り出した。**提案のみで実装・データ再生成はしていない** | Phase 1（AA-1 の gold 誤配の修正）に着手するか、J1〜J3 の判断を待つ |
| 2026-10-03 | **人間の判断が要る件を `TASK.md`（新規）と `HITL_TODO.md` に整理した。** `TASK.md` を判断待ちの入口として新設（T1〜T7：未コミット成果のコミット可否・検索クエリ改修の方針・データセット版と `query_id`・`situational` クエリ・採用しない生成物の削除・外部読み取りサービス・`dataset/` の配布手段）。`HITL_TODO.md` に **H10〜H13** を追加（`search_query_design.md` の J1〜J3 ＋ 未コミット成果の扱い）、一覧表に漏れていた H9 を追加、ヘッダの「残課題はすべて解消済み」を AA 群が未着手である旨に訂正、末尾の実測値（41 文書時点）を 103 データセット・8,561 パッセージ・pytest 433 件に更新。**`AA-3`（`MAX_RELATED` の廃止）は H6(c) で承認済みの事項を覆すため、Phase 1 から外して T2 の回答待ちにした**（承認時 28 クエリ・約 1,100 件 → 現在 61 クエリ・3,629 件＝grade 1 総量の 40% に拡大）。CLAUDE.md §0.2 と `docs/repo_layout.md` に `TASK.md` を登録 | `TASK.md` T1・T2 の回答を待つ／回答不要の Phase 1（AA-1・AA-2・AA-4・AA-11）は着手可 |
| 2026-10-03 | **`TASK.md` の人間の決定（T1〜T7）を全ドキュメントに反映し、承認された検索クエリ改修の実施計画 `docs/search_query_plan.md` を作成した**（566 行・作業単位 W0〜W20・テスト T-1〜T-15・レビュー R-A〜R-E・評価計画 §5・リスク §6・DoD §7）。決定：T1 コミットしない／T2 全面改修（素のクエリ 1,482 → 896）／T3 `dataset-v7` を切る／T4 `situational` を入れる／T5 削除 OK（**AI は保護フックに拒否され実行できず**）／T6 外部サービス不要（H7 クローズ）／T7 HF＋GitHub 配布。**計画を具体化する過程で設計の欠陥 3 点を実測で発見し、設計書（AA-4・AA-6・AA-15）を改めた**：`term_id` は文書をまたいで一意でなく（70/502 の id が別の語に使い回され）素朴な文書限定撤廃は grade 1 に 3,601 件（35%）の誤りを入れる／`enumeration` の grade 1 を字面一致で作ると 1 語平均 115 件に膨れる／定義表を `evidence` にする QA が 354 問あり表のパッセージを消せない。**新たな欠陥 2 件も発見**：AA8 `definition` パッセージ 1,230 件（14%）が紙面に存在せず `pages` が空で、実際に印字される定義表の行が grade 0（`term` クエリの 94%）／AA9 `term_id` の衝突による誤ラベル 13 件。あわせて **AA-3（`MAX_RELATED` の廃止）は不要と判明**（df 振り分けで損失が 3,629 → 301 件に減る）。`HITL_TODO.md` に H7〜H13 の決定を記録、`docs/decisions.md` に 9 行追記 | 計画の段 0〜段 1（W0 → T-13 → W1 → W2 → W3 → W4 → W5）に着手する |
| 2026-10-03 | **派生した判断 T8〜T11 の回答を反映**（いずれも AI の既定どおり）：T8 = `dataset_version: v7` で版を表しタグは人間が打つ／T9 = `MAX_RELATED` は**触らない**（H6(c) の承認を維持）／T10 = 既存 `apply` 型 128 問を流用・新規執筆もレビューもしない／**T11 = 配布ライセンスは後日人間が決めるため `dataset/LICENSE` は作らない**（W20-2 を保留し、`DATASET_CARD.md` のライセンス欄は「未定」とする）。T1 は「放棄」ではなく「後日人間がコミットする」として記録を書き直した。`TASK.md` は判断待ちゼロ、`HITL_TODO.md` は H1〜H13 すべて回答済み、`docs/decisions.md` に 3 行追記 | 計画の段 0〜段 1（W0 → T-13 → **W1**）に着手する |
| 2026-10-04 | **検索クエリ改修（AA 群）を計画どおり完遂**（`docs/search_query_plan.md` W0〜W20）。クエリを 4 kind → **10 kind** に再設計し、語の出現文書数で素のクエリ・絞り込み・網羅に振り分けた。**実測：`qa` の gold 誤配 2,916/3,819（76%）→ 0／同じ入力で gold が食い違うクエリ 472 → 0（nDCG@1 の到達上限 0.961 → 1.000）／打ち切りで落ちた grade 1 3,629 件（40%）→ 126 件（1%）／番号ラベル混入 173 → 0／`definition` パッセージの `pages` 空 1,230（14%）→ 0／定義文の二重化による grade 0 475/506（94%）→ 0／`term_id` 取り違え 13 → 0**。新 kind の素朴な BM25 は `definition_masked` 0.323・`multi_hop` 0.319・`situational` 0.388 で意味検索の余地を確保（3 系統のスプレッドも 0.2 以上）。`term`/`heading` は意図的に飽和のまま残し README に印を付けた。**実装中に設計の穴 4 件を自己検査（V-S1〜V-S9）が検出**：定義本文をクエリにしても循環が断てない（0.938）／出題元を非適合にすると全系統 0.000／1 文書に同名の条が複数ある／同文のクエリが 20 文書に出る。いずれも設計を改めて `docs/decisions.md` に記録。`exact_recall@k`・`r_precision`・`doc@1`・`confusion@k`・`false_positive_rate` を指標に追加、`id_map.json`・`DATASET_CARD.md`・`manifest.dataset_version: v7` を出力、`dataset/README.md` に素朴な検索器 3 系統のベースライン表を実測で埋め込む。テスト 433 → **469 件**全通過、`eval --all --oracle` は全 10 kind 満点、`export` は 2 回でバイト一致 | `TASK.md` T5 の削除（人手）／AA10（`life` の定義表）／AA12（盲検レビュー・指示待ち） |
| 2026-10-04 | **`life` の用語集を全 9 content に入れ、ジャンルの偏り（AA10）を解消**（`docs/search_query_plan.md` 段 5・W21〜W26）。原因は blueprint で、**10 ジャンルのうち 8 つが宣言している `{ kind: table, subtype: definitions }` が `life` だけ漏れていた**（`teikan` は定款に用語集が無いので正しい）。`defined_terms` 129 語のうち紙面に出ていたのは 17 語だけだった。blueprint に必須要素を足して**先に L04 の error が出ることを確認**してから、用語集 **115 行**を執筆（新設 6 本・拡張 3 本。しおりの平易な敬体で、content ごとに文末の段を変えて L15 を回避）。10 データセットを build→render→verify→qa で作り直し、**`life` の `definition` パッセージが 17 → 131 件**（他ジャンルは 113〜182）。ページは `life-0003` が 19 → 20（上限と同値・超過なし）。**途中で 2 件踏んだ**：表の grid を組み直すとセル id がずれて執筆 QA の evidence が別の行を指す（**L14 が検出**）、`sorted()` で並べると符号位置順になり日本語として恣意的に見える（**PNG の目視で発見**。verify も lint も通る）。テスト 471 件全通過、`eval --oracle` 満点、`manifest check` 通過 | `TASK.md` T5 の削除（人手）／AA12 盲検レビュー（指示待ち）／配布に向けた T11 と H2・H3 |
| 2026-10-04 | **content を 10 本足して合計 100 本にした**（ユーザーの依頼「合計で100点」。`<genre>-0010` を 10 ジャンル × 1 本）。題材は既存 9 本と商品設計のレベルで重ならないもの（二輪車／雪道1日／噴火・火山灰／日帰り手術／個人年金／再保険専業の定款／トレッキング／乗馬／団体終身／自転車の重説）。別表の数値列はすべて自作。**全 10 content で lint error 0 / warn 0（`--similarity` 含む・30% 超えゼロ）、全 10 データセットで verify error 0 / warn 0、QA 45 問で error 0。** 121 ページ・102,376 字・450 問を追加し、`specs/batch_v5.yaml`・export・manifest を更新（**ready 113/114**、検索コーパスは 100 文書・パッセージ 9,456・クエリ 8,824・qrels 25,435）。`eval --oracle` は 3 文書で全指標満点、pytest 471 件・ruff・`manifest check` 通過 | `HITL_TODO.md` H9（不採用の生成物 2 件の人手削除）→ 削除後に `manifest update` で ready 113/113 |
| 2026-10-05 | **公開可能な状態への棚卸し（コミットは人間）。** ユーザーの指示で `insurance-contracts/` を通読・整理した（`insurance-contracts-calculation/` は対象外）。**機械検査**：`make lint` 違反 0、**pytest 486 件全通過**、全 100 content の `yakkan lint` が error 0 / warn 0、発行体名 100 件すべて一意の架空名、URL ホストは `example.jp` / `example.co.jp` 系のみ（7 種・105 か所）、電話番号は `0120-000-000` と全角版の 2 種のみ（699 か所）、秘密情報なし、40 字以上の引用 0 件。**仕様と実装の食い違いを 3 件発見して仕様を直した**：`CLAUDE.md` §11 と `docs/style_guide.md` が存在しない `yakkan review` を指示していた（PNG は `render` が既定で出す）／hooks の記述（`*.json` 保存後の lint・`rm -rf dataset` の確認）が未実装／`README.md` の QA 型が「10 種別」（列挙は 11 個）。**整理**：`HITL_TODO.md` を `git rm --cached`（`.gitignore` との矛盾を解消）、`.gitignore` を由来つきで書き直し（**行末コメントが効かない罠**も明記）、`tests/unit/test_lint.py` の否定テストのドメインを RFC 2606 の `.invalid` に、`assets/fonts/ipaex*.ttf` の実行ビットを除去、`TASK.md` と `docs/decisions.md` から作業機の絶対パスを除去、`README.md` に現況の規模・`dataset/` 直下のファイル・評価の節・ライセンスの内訳を追記、`docs/repo_layout.md` に`insurance-contracts-calculation/` と無視ディレクトリの扱いを追記。`TASK.md` §7 に検査結果とコミット手順（T13）を残した | 人間：`TASK.md` T13（コミット）→ T5・T12（`dataset/` の不要物削除。**`rm -rf` ではなく `yakkan clean` で消せる**ことが判明）→ T7 配布の前に H2・H3（追加 70 content の架空性・非転載の最終確認） |
| 2026-10-05 | **Hugging Face 配布の準備（公開は人間）。** ユーザーの指示で `dataset/` を HF にそのまま上げられる形にした。**決めてもらった 3 件**：ライセンス＝**CC BY 4.0**（T11 の保留を解除）／アカウント `cvusk`・ID `cvusk/japanese-insurance-document-understanding`（T7）／不要物の削除は両方実行（T5・T12）。**T5・T12 を実施**：`yakkan clean` で不採用の 2 件を削除し **ready 113/113**、成果物でない `render.pdf` 41 件（12.4 MiB）を削除。manifest とデータカードが自動追従。**カードを 1 枚に統合**：`DATASET_CARD.md` を廃止し `dataset/README.md` に統合した（**HF は直下の README.md だけをカードとして読む**ので別名では配布先に出ず、2 枚あると統計値が食い違う）。`dataset/` は手編集禁止でフックが Edit/Write を拒むため、**`export` が古い名前を自分で片付ける**ようにした（`remove_retired()`。実際に `rm` が権限で拒否された）。**新しい配布物**：`LICENSE`（法文は転記せず CC の legalcode を参照＋帰属の書き方＋`doc.pdf` に埋まった字形サブセットの扱い）、`.gitattributes`（PNG 1,437・PDF 113＝647 MiB を LFS へ）、`qa.jsonl` 5,085 行・`documents.jsonl` 113 行（`qa.json` と `manifest.json` は「1 行 1 レコード」でなくビューアが読めない。**正本はもとのファイル**）、frontmatter の `configs` 5 件。**`qa.json` の `answer` は 3 型**（string 3,641／number 1,107／list 337）で Arrow が 1 列に混ぜられないため、`qa.jsonl` では `answer_text`／`answer_number`／`answer_list` に分けた（採点は `qa.json` を使うので eval に影響なし）。**検証**：使い捨て venv（datasets 5.0.1 / pyarrow 25.0.1）で **5 つの config すべてが読める**ことと `get_dataset_config_names` が 5 件返すこと（＝frontmatter が HF のパーサで通る）を実測。`export` は 2 回目でも配布物 8 ファイルがバイト一致。`render.html` の除外は `upload` が実際に使う `filter_repo_objects` で確認（2,352 → **2,239**・落ちたのは render.html 113 件だけ・**864.6 MiB**）。**LFS の順序の罠を発見**：`hf upload` は LFS 判定を Hub に委ね、Hub は**その時点でリポジトリに載っている `.gitattributes`** を見る（`_fetch_upload_modes` を読んで確認。`.gitignore` は送られるが `.gitattributes` は送られない）。そのため手順を **2 段アップロード**にした。手順書 **`docs/distribution.md`**（240 行）を新設し CLAUDE.md §0.3 に登録。**`hf` CLI は実物の `--help` で確認し、記憶で書いた 3 か所の誤りを修正**。`make check` は **492 件通過＋skip 1**（skip は「failed な文書が無い」＝T5 の結果でテストが自分で飛ばす） | 人間：**T14 HF へのアップロード**（`docs/distribution.md` §4）。その前に **H2・H3**（追加 70 content の架空性・非転載の最終確認）。**T13 コミット**。HF のリビジョンタグと git タグ |
| 2026-10-08 | **検索評価セットを別の Hugging Face データセットに分離（公開は人間）。** ユーザーの指示「HF 登録時に `dataset/search/` を新しいデータセットへ移す」。**決めてもらった 2 件**：リポジトリ ID＝`cvusk/japanese-insurance-document-understanding-retrieval`（3 案から選択）／ローカルの置き場所＝`dataset/search/` のまま（`dataset/search/` を「別リポジトリの作業コピー」と見なす。`yakkan eval --search-run` の既定パスと docs の参照を壊さない）。**実装**：`write_search_card`／`write_search_license`／`write_search_gitattributes` を新設し、`dataset/search/` に **README.md（カード）・LICENSE・.gitattributes** を書くようにした。**本体のカードから `search-*` の 3 config を外し**（上げないファイルを宣言するとビューアが壊れる）、検索固有の節（設計・素朴な検索器のベースライン表・読むときの注意点 5 件・`teikan` の `definition` 欠落）を評価セット側のカードへ移した。本体には件数とリンクだけが残る。**架空・学習禁止の告知は `FICTITIOUS_NOTICE`／`NOT_FOR_TRAINING_NOTICE` に出して 2 枚のカードで共有**し、LICENSE は「及ぶ範囲」（`COVERS_DOCUMENTS`／`COVERS_SEARCH`）だけを差し替える形にした（検索側にはフォントの節が無い＝PDF が無いため）。`manifest.json` の `corpus_artifacts` に `search/README.md`・`LICENSE`・`.gitattributes` を追加。**実測**：本体 845.7 MiB / 2,235 ファイル、検索 18.9 MiB / 7 ファイル（分離前は 864.6 MiB / 2,239）。評価セット側のカードに パッセージ 9,456・クエリ 8,824（10 種）・qrels 25,435・ベースライン表が実測で入ることを確認。`docs/distribution.md` を版 1.1 に改訂（2 リポジトリ構成・`--exclude "search/*"`・公開後の確認を両方ぶん・public 化は 2 つ同時） | 人間：**T14 HF へのアップロード（2 リポジトリ）**（`docs/distribution.md` §4）。その前に **H2・H3**（追加 70 content の架空性・非転載の最終確認）。**T13 コミット** |
| 2026-10-09 | **検索評価セットの公開面を姉妹プロジェクト `contracts/` と揃えた（公開は人間）。** ユーザーの指示「`contracts/dataset/search/` の HF 向け設定を確認し、作り方や設計を合わせる」。**決めてもらった 3 件**：リポジトリ ID は `-search` のまま（contracts の `-retrieval` には合わせない）／揃える範囲は**成果物の設計だけ**（`specs/publish.yaml` 相当の宣言層は入れない）／**本体のカードも二層にする**。**実装**：`CARD`・`SEARCH_CARD` を**英語面＋日本語面**に書き換え（英語面＝リード・`⚠ Not for training`・`What it is for` / `not for`・`Configs`・`Fields`・`Caveats`・`Citation`、日本語面＝読み方・並び・実測・注意点・採点）。frontmatter に `multilinguality`・`annotations_creators`・**`source_datasets`**（検索側は `extended|<本体>`）を足し、`pretty_name` を英語名に。`SHA256SUMS` を新設（**自分のルートからの相対パス**・README と LICENSE を数えるため最後に書く）。検索側 `LICENSE` を専用の短縮形にし、`.gitattributes` は廃止して `RETIRED_SEARCH_ARTIFACTS` で生成器が片付ける。`Fields` の列名と種別件数表は**実測**。定数名も contracts に合わせて `NO_TRAINING_EN`／`NO_TRAINING_JA`／`FICTITIOUS_JA` に改名。**揃えなかった 3 点（意図的・`docs/decisions.md` に記録）**：`default: true` は残す／ベースライン表は insurance 側だけ／検索側 `LICENSE` の `NOT A REAL INSURANCE POLICY` は残す。**検証**：`make check` と `datasets` での config 読み込み（本体 2・検索 3）、`export` 2 回のバイト一致を再確認 | 人間：**T14 HF へのアップロード（2 リポジトリ）**。その前に **H2・H3**。**`CODE_REPO` に入れた GitHub の URL が公開リポジトリかの確認**。**T13 コミット** |
