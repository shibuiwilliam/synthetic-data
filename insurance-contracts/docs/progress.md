# progress.md — 進捗と次の一手

CLAUDE.md §0.2-1 でセッション開始時に読み、§0.2-4 で終了時に更新するファイル。
各フェーズに「完了／未完／次にやる3タスク／落とし穴」を書く。フェーズの DoD は CLAUDE.md §12。

**現在地：P5 完了（28データセット・402ページ・1,262問が ready、tag dataset-v1）。次は P6。直近セッション：2026-09-22。**

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

### 次にやる3タスク

1. 読み取り側（LLM/VLM）の**実物の予測**を通し、`yakkan eval` の出力が意思決定に使えるかを見る。
   素朴な読み取り器で契約は確かめたが、モデルの出力の癖（表の結合セル、図の読み取り）は未知。
2. `dataset-v3` を配布するかを決める（タグは切ってあるが push していない）。
3. 読み取り側からの報告を待って、スキャン風画像（T6）や style の追加を判断する。

---

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
