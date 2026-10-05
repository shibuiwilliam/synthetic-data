# plan.md — 実行計画とタスク分解（WBS）

> CLAUDE.md §12（マイルストーンと DoD）の詳細版。各フェーズの具体タスク・依存・リスク・完了条件を持つ。
> フェーズ完了時に本ファイルのチェックボックスと `docs/progress.md` を更新する。
> 所要感と落とし穴は yakkan-synth の実績（P0〜P6 ＋残課題 7 次ループ）から引いている。

## 全体像

```
P0 移植（yakkan → keiyaku。挙動不変）
 └ P1 構造分析（samples を読む。コード変更なし）── P2 と並行可
     └ P2 契約書化（doctype・{party:}・新 kind/Block・numbering・lint・verify・style）
         ├ P3 条文型（nda / outsourcing / delegation / consulting）
         ├ P4 別紙・目録型（purchase / lease / license）
         └ P5 様式型・長文型（employment / contracting / sysdev）＋ commentary
             └ P6 データセット v1（2〜3 本目・batch・QA・export・自己評価）
                 └ P7 検証・硬化（規則ベース → VLM → 盲検 → HITL）
                     └ P8 拡張（A3 縦・doctype 追加・docsynth への切り出し検討）
```

- **P3〜P5 は骨格類型ごとに直列**。1 類型ずつ「blueprint → style → 執筆 1 本 → review」を完了させてから次へ。
  並行すると共有コード（CSS・テンプレート）の変更で互いの描画が壊れる（yakkan の教訓：
  **サブエージェント作業中は共有コードを触らない**）。
- 規模の目安（v1）：10 doctype × 2–3 content × 1–2 style ≈ **40–60 文書**。
- 執筆が最大の律速（yakkan 実績：**1 文書 20〜50 分/エージェント**。part 並列より 1 文書 1 体が整合する）。

## P0 移植 — yakkan のコードと資産を挙動不変で取り込む

**DoD**：`make check` が通り、smoke PDF のテキスト層が yakkan と一致。棚卸し表
（`docs/architecture.md` §5）が埋まり、P2 の作業リストが確定している。

> **2026-09-26 完了。** テキスト層だけでなく fragments・PNG・**PDF のバイトまで一致**した。
> 保険資産に依存する 6 テストモジュールはデータ駆動でスキップ（`docs/decisions.md` 27）。
> P2 の作業リストは `docs/progress.md`「P2 に持ち込む宿題」。

- [x] `uv init`（Python 3.12・**weasyprint==70.0**・jinja2・pydantic v2・typer・pyyaml・pdfplumber・
      pypdfium2・fonttools・pillow・apted・ruff・pytest）。`pyproject.toml` の版指定は yakkan から写す。
- [x] Makefile を移植（`setup` / `check` / `fmt` / `lint` / `test` / `manifest-check` / `doctor` / `smoke` /
      `probe` / `doc` / `batch` / `clean`）。**`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` の export を残す。**
- [x] `../insurance-contracts/yakkan/` → `keiyaku/` へコピー＆リネーム（import と CLI 名のみ変更）。
      **`answer.py` / `export.py` / `export_models.py` / `search_set.py` / `figure_graph.py` /
      `eval/`（harness・metrics・oracle・search）/ `manifest.py` / `batch.py` / `fonts.py` を含める。**
- [x] `tests/`（unit・golden・render_smoke）・`scripts/`（probe 群・calibrate_styles・fill_records・
      authoring・baseline_reader・analyze_reference_pdf・otf_to_ttf・smoke_render）・
      `.claude/`（commands / agents / rules / hooks / settings）を移植。
- [x] `assets/fonts/`：**`.ttf`（TrueType 輪郭）版**を実体ごとコピー。`.otf` は出典検証用に併置し
      `SOURCES.md` を必ず持ってくる（変換はバイト非決定論なので手順の再現に頼らない）。
- [x] `.gitignore` を整える（`dataset/` `scratch/` `.venv/` `samples/*`＋`!samples/SOURCES.md`。
      **親リポジトリの `parts/` 除外を `!parts/` `!content/**/parts/` で打ち消す**——`git check-ignore -v` で確認）。
- [x] `make doctor` / `make smoke` を通し、**smoke PDF のテキスト層が yakkan と一致**することを確認。
- [x] 棚卸し：モジュールごとに「そのまま／要改造（直書き箇所）／捨てる」を `docs/architecture.md` §5 に記入。
- [x] 保険固有の資産（`blueprints/*.yaml` 10 件・`styles/*.yaml` 13 件・`library/clauses/`・`content/`・
      `specs/`）は**移植しない**。空ディレクトリと `.gitkeep` だけ用意する。
- リスク：yakkan のテストは保険用 fixture に依存している。**P0 では fixture も一緒に移植して緑にし**、
  P2 で契約書の fixture に差し替える（テストを最初から落としたまま進めない）。

## P1 構造分析 — samples から骨格と課題を取り出す（コード変更なし）

**DoD**：`docs/reference_structures.md` §4 に 36 種ぶんの分析ログ。CT カタログ（§3）が確定し、
10 doctype の骨格類型・必須要素の草案が `docs/doctypes.md` に反映されている。
コアで表現できない構造が `docs/decisions.md` に起票されている。

- [ ] `scripts/analyze_reference_pdf.py` で全 39 ファイルの構造を測る（**本文を出力しない**ことを確認してから）。
- [ ] カテゴリごとに代表 2〜3 ファイルを**目視**し、`docs/reference_structures.md` §1-3 の観点で書き出す。
      1 文書 10〜20 行。**文章の引用は一切しない。**
- [ ] 逐条解説つきモデル契約（`license` `nda_03` `sysdev_02`）は「契約書本体だけのページ数」を別に数える。
- [ ] CT カタログを確定（CT1〜。仮説の CT16 に追加・削除を加える）。各 CT を blueprint の `required` へ写像。
- [ ] `docs/doctypes.md` の各 doctype の「固有の必須要素」を実測に合わせて更新（**仮説の修正を恐れない**）。
- リスク：**読むうちに文章を覚えてしまう。** 分析は構造の観点だけに絞り、長時間の通読をしない。
  数値の列・項目の並びをログに書き写さない（`docs/reference_structures.md` §0）。

## P2 契約書化 — ドメイン知識を宣言に追い出し、契約書の要素を足す

**DoD**：単体テスト通過。numbering 2 方式の golden（全 kind × 位置のラベルと `{ref:}` 解決）。
`keiyaku doctypes` が動く。style 3 種で smoke が描ける。**「移植」と別コミットになっている。**

> **2026-09-26 完了。** `make check` 緑（349 passed / 22 skipped）。numbering の宣言化は
> 保険 5 方式を 8,227 データ点で再現して表現力を確かめた（hooks への逃げ道は不要だった）。
> probe 3 件・style 3 種・契約書ブロックの描画・`blueprints/nda.yaml`・条文ライブラリ 7 本まで完了。
> **目視レビューで verify が検出できない欠陥を 3 件**見つけ、うち 1 件（負の格子座標）は lint に落とした。

- [x] `family` / `doctype` の導入（`genre` の置換。`schema_version: "2.0"`、`keiyaku doctypes` コマンド）。
- [x] **宣言的 numbering**（`docs/schema.md` §7）：`contract-standard` と `contract-form` を YAML で書き、
      解釈器を実装。`continuous_articles` / `paragraph_ref_style` / `no_chapter_prefix` を宣言項目にする。
      **検証**：yakkan の `nonlife` を YAML に書き下し、yakkan の `numbering.py` と同一出力になることを確認
      （**解釈器の表現力の実地検証**。書けなければ宣言スキーマが足りていない）。
- [x] semantic_type の 2 層化（コア共通＋契約書登録語彙。L00 検証）。
- [x] 新 kind（`preamble` / `head_matter` / `signature` / `schedule` / `supplement`）と
      新 Block（`parties` / `revision_history` / `commentary`）をモデル・build・テンプレートに追加。
      **`rider` の「番号を持たず題名で `{ref:}` 解決する」機構を再利用する**（新機構を作る前に確認）。
- [x] **`{party:}` トークン**（parse → build 解決（4 modifier）→ `derived.party_uses`）。
- [x] 要 probe 3 件（`docs/rendering.md` §7）：記名押印欄の丸枠・`signature_layout: horizontal` の読み順・
      `- 1 -` 型フッタ。**結論を decisions と gotchas に記録してから**描画を確定する。
- [x] テンプレート整理：保険固有の前付け（表紙・目的別もくじ・特約一覧・ペットネーム表）を外し、
      `parts/preamble.html` `parties.html` `signature.html` を足す。
- [x] style 3 種（`ct-a4-1col-mincho` / `ct-a4-1col-gothic` / `ct-a4-1col-form`）の YAML と CSS。
      **`chars_per_page_estimate` は P3 で 1 本描いてから較正する**（初期値は暫定と明記）。
- [x] lint 再編：L00–L18 を互換で維持、**L19（当事者整合）・L20（骨格）・L21（逐条解説）を新設**、
      L03 の検出パターンを numbering YAML＋party alias から生成、denylist を契約書用に書き直す。
- [x] verify 差分 V-P1〜V-P5（`docs/rendering.md` §6）。
- [x] 自動 QA の質問文言から保険語を抜き、doctype の語に差し替わるテンプレートにする。
- [x] `tests/golden/sample_min/`（最小の契約書 content。2 者・前文・3 条・表 1・図 1・記名欄）を作る。
- リスク：**L03 のパターン自動生成が過検出する**（「第N条」を含む定義文、「甲」を含む一般語）。
  yakkan の「`{ref:}` 解決後の文字列は対象外」の除外規則を必ず引き継ぎ、当事者 alias は**単独出現のみ**を見る。

## P3 条文型 — nda / outsourcing / delegation / consulting

**DoD**：4 doctype の blueprint と各 1 文書が lint / verify / review を通り manifest に ready。
執筆 QA 15 問 × 4。`chars_per_page_estimate` が実測で較正済み。

- [ ] `blueprints/nda.yaml` を最初に書き、**1 本通して**（scaffold → 執筆 → lint → build → render → verify →
      review → qa）パイプライン全体を検証する。**ここで詰まったものは全 doctype で詰まる。**
- [ ] `library/clauses/common/`（協議・合意管轄・通知・存続・反社・譲渡禁止・可分性）を
      **オリジナル文で**用意。文言は文書ごとに変える前提の「型」として書く。
- [ ] 残り 3 doctype の blueprint と執筆。**題材・当事者・数値を互いに変える**。
- [ ] 各文書に `apply` QA 2 問（検収期限・通知期限の逆算・存続期間）。**算出値を自分で検算**し H5 に起票。
- [ ] `scripts/calibrate_styles.py` で 3 style の較正値を実測から更新。
- リスク：`{party:}` を使っても**論理の取り違え**（甲乙逆転）は機械検出できない。
  reviewer サブエージェントの観点に「**条ごとの主語の妥当性**」を必ず入れる。

## P4 別紙・目録型 — purchase / lease / license

**DoD**：3 doctype 各 1 文書が ready。`head_matter` の描画と `{ref:head}` の解決が確定
（decisions に記録）。頭書 ↔ 本文の値が `{const:}`（L11）で縛れている。

- [ ] 要 probe：頭書の大型表（10 行 × 5 列以上）がページをまたぐときの繰返し表頭と rowspan の継続。
- [ ] `head_matter` の `{ref:}` 解決方式を確定（`docs/schema.md` §11.1）。
- [ ] `inventory` / `fee_schedule` の `records` を `scripts/fill_records.py` で埋める
      （**結合セルのある表は手で書く**）。合計値と本文の整合を `{const:}` で縛る。
- [ ] `lease` の 3 者版（家賃債務保証業者つき）variant で `meta.parties` 3 件・記名欄 3 ブロックを検証。
- [ ] 別紙（`schedule`）の 3 系統採番（別紙／別表／様式）を 1 文書で同時に使い、L01 と採番を確認。
- リスク：**別表の数値が転載の指紋になりやすい**（料率の段・負担区分の項目の並び）。
  `docs/style_guide.md` §2.1 のとおり自分で作り直し、端数を混ぜる。

## P5 様式型・長文型 — employment / contracting / sysdev ＋ commentary

**DoD**：3 doctype 各 1 文書が ready。`contract-form`（条なし）で verify が目次検査のスキップを
明記して通る。`commentary` が `license` の variant 1 本で動く。

- [ ] 要 probe：☑ □ のフォント被覆（無ければ代替記号を決めて decisions に記録）。
- [ ] `employment`：`contract-form` の numbering・`ct-a4-1col-form` style・`form_fields` 表 3 つ以上。
      **選択欄の `records` 表現**を確定。空欄を残さない。
- [ ] `contracting`：章立て＋**目次あり**。2 パス目次・リーダー罫の規約・ヘッダ章名
      （`string(chapter, first)`）を長文で検証。工程タイムラインを描く。
- [ ] `sysdev`：基本契約＋個別契約（様式を `schedule` に）。`{ref:}` が様式へ飛ぶことを確認。
      **単調性検査用に図を 3 点以上持たせる**（`docs/validation_plan.md` §1）。
- [ ] `commentary` Block の実装（`anchor` 必須・`region: commentary`・L21）と `license` variant 1 本。
- [ ] 予測語彙に `head_matter` / `commentary` を追記（`docs/evaluation.md` §4）。
- リスク：**枠つきブロックが段／ページ境界で割れると続きが版面の外に出る**（yakkan で実害）。
  `commentary` は `break-inside: avoid` を基本にし、長い解説は分割して複数ブロックにする。

## P6 データセット v1 — バッチ・QA・評価向け成果物

**DoD**：40〜60 文書が ready。`keiyaku eval --all --oracle` が全文書・全指標で満点。
`elements.jsonl`・検索評価セット・manifest・`dataset/README.md` が揃い、`baseline_reader` の採点が
全文書で完走する。

- [ ] 各 doctype の 2〜3 本目を執筆（題材・当事者・数値・構成を変える。`lint --similarity` 30% 未満）。
- [ ] `specs/batch_v1.yaml`（content × style × seed）。batch は失敗しても止まらず**段別・原因別に集計**。
- [ ] 自動 QA 30 問＋執筆 QA 15 問／文書（L14・L16）。
- [ ] `keiyaku export`（elements.jsonl・passages/queries/qrels・README 生成）。
- [ ] V-A / V-B / V-C（`docs/validation_plan.md` §1〜2）を通す。`baseline_reader` に契約書の正規表現を足す。
- リスク：`RenderLayoutError` は「**帯**」で起きる——字数を帯の幅**以上**動かす。
  自分の文が悪いと思って探索しすぎない。

## P7 検証・硬化 — 外の読み手で契約の穴を出し切る

**DoD**：`docs/evaluation.md` §6 の 5 条件をすべて満たす。発見欠陥がすべて lint / verify / docs /
採点側の修正に落ちている。`HITL_TODO.md` の全項目に人間の決定が記入されている。~~v1 タグ~~
（**H9（2026-10-05）で「コミットはするがタグは打たない」と決まったため取り下げ**）。

- [x] V-C：規則ベースの読み取りを全 41 文書で完走（2026-09-28）。契約の穴 3 件を採点側へ落とした。
- [x] V-D：骨格類型ごとに 1 文書を VLM（自セッション）で読んだ（2026-10-02・4 骨格）。
      契約の穴 6 件を docs・採点側・**正解データ**へ落とした（decisions 120〜123）。
      **外部の OCR / VLM API は使わない**（H8 は 2026-09-27 に「不可」で決定）。
- [x] V-E：骨格類型ごとに 1 文書を**盲検**（独立エージェント）で読んだ（2026-10-02／10-03・計 5 本）。
      契約の穴 28 件を `docs/evaluation.md` §4.8・§4.9 へ、採点側の穴 1 件を `score_tables` へ。
- [x] 発見欠陥の修正 → 影響文書の再生成 → oracle 満点の再確認、を**ループが涸れるまで**
      （V-C 3 件・V-D 6 件・V-E 29 件をすべて lint / verify / docs / 採点側へ落とし、`eval --all --oracle` は満点を維持）。
- [x] `HITL_TODO.md` **H1〜H8 すべてに人間の決定**（H1〜H4・H6〜H8 は 2026-09-27、**H5 は 2026-10-04**）。
- [x] **`contracts/` 本体を git に載せた**（2026-10-05。`HITL_TODO.md` **H9** の決定＝AI が本体をコミットし、
      `contracts-calculation/` は別扱い、**タグは打たない**）。`.gitignore` / `.gitattributes` /
      `docs/repo_layout.md` / `README.md` を公開可能な状態に整理した（`docs/decisions.md` 147〜151）。
      追跡 1,279 ファイル / 76MB（`dataset/` `samples/` `scratch/` `contracts-calculation/` は除外）。

## P8 拡張

- [x] **`ct-a3-landscape-form`**（A3 横 1191×842pt・2 段。`purchase` の官公庁様式。2026-10-03）。
      判型は `docs/reference_structures.md` §4.1 の訂正どおり **A3 横**（「A3 縦」は誤り）。
- [x] **`ct-a3-landscape-form` を使う文書を足す**（2026-10-05。`pur-0004` の 2 style 目。
      実装済みだが使う文書が 0 だった状態を解消した。全ページを目視で確認済み）。
- [x] **データセットを 100 文書へ拡張**（2026-10-05。H10 の決定。content を 30 本足して 50 content にし、
      1 content を 1〜2 style で描いた。`specs/batch_v2.yaml`・`docs/decisions.md` 143〜146）。
- [ ] doctype 追加の候補：保証契約・代理店契約・フランチャイズ契約・共同研究開発契約・
      株式譲渡契約（`docs/doctypes.md` §8 の手順で）。**H10 では「今回は行わない」と決定**（必要になったら再起票）。
- [ ] `docs/architecture.md` §6 の判断：`families/contract/` として `../structured-docs/` へ切り出すか。
      切り出すなら docsynth 側の P0〜P2 完了が前提。**H10 では「今回は行わない」と決定。**
