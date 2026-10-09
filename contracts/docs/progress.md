# progress.md — 進捗と次の一手

> セッション終了前に必ず更新する（CLAUDE.md §0.2-4）。
> 形式：現在地＋「次の 3 タスク」＋フェーズ状態＋記録。**新しい記録を上に足す。**

## 現在地

- **2026-10-05 現在：50 content / 10 doctype / 100 文書。** 全 50 content が
  `lint --similarity` で error 0・warn 0、全 100 文書が ready、`manifest check` 一致、
  `eval --all --oracle` は全指標満点。
- 全契約の日本語・条項間整合・架空名称を再レビューし、20 content（39 style）を修正・再生成した。
  修正ページは両レイアウトを目視し、文字切れ・表崩れ・条文欠落がないことを確認した。
- 本体は `ruff format --check`、`ruff check`、`pytest` が全緑（**533 passed**）。
  `contracts-calculation` の関連テストは **21 passed**。`make check` 全体には、本件より前からある
  `contracts-calculation/DESIGN.md` と `examples/*/calc/programs/*.py` の formatting 違反だけが残る。
- HITL の依頼中は **H12・H14・H15・H16・H17**（H9・H13 は決定済み）。
- **2026-10-05：`dataset/` を Hugging Face Hub で公開できる形に整えた**（T15。`docs/publishing.md`・
  `keiyaku/publish.py`・`specs/publish.yaml`）。**アップロードは未実施**——配布条件（**H13**）が未決で、
  リポジトリ名・可視性・実行者（**H15**）と名義（**H16**）も人間の判断待ち。
  `uv run keiyaku publish check` と `uv run python scripts/upload_hf.py`（既定 dry-run）で状態が見える。
- **2026-10-08：検索評価セット（`dataset/search/`）を本体とは別の Hugging Face データセットに分けた**
  （ユーザー指示。`docs/publishing.md` §12・`docs/decisions.md` 160〜163）。上げ先は 2 つになり、
  本体の `configs`・`SHA256SUMS`・アップロードから `search/` が外れ、検索側は自分のカード・`LICENSE`・
  `SHA256SUMS` を持つ（`dataset/search/` がそのリポジトリのルート）。**生成の場所と `keiyaku eval
  --search-run` のパスは変えていない。** 検索側のリポジトリ名は **H17** で判断待ち（仮置きで動く）。
  pytest **555 passed**。
- **2026-10-05：`contracts/` 本体を git に載せた**（H9 の決定。`contracts-calculation/` は含めず別扱い・
  タグは打たない）。公開に向けて整理した内容は `docs/decisions.md` 147〜151。
  `make check` は**本体だけを見るようになり全緑**——`pyproject.toml` の ruff に
  `extend-exclude = ["contracts-calculation"]` を足し、それまで残っていた
  `contracts-calculation/` 側の formatting 違反（生成物の計算プログラム 4 ファイル）を
  本体の検査から外した（整形はサブの生成器の責務）。

### 次の 3 タスク

1. **H15・H17**（2 つのデータセットのリポジトリ名・可視性・実行者）の決定を仰ぐ。決まれば
   `specs/publish.yaml` の 2 行＋`keiyaku publish update`＋`scripts/upload_hf.py --yes` で公開できる。
2. **H14**（拡張で増えた `apply` QA 60 問の算出値）の決定を仰ぐ。材料は `HITL_apply_review.md` の
   「検算メモの無い 60 件」。
3. **`contracts-calculation/` のコミット**（本体とは別に。サブの `HITL.md` HC-1 により人間の操作）。

### 旧 v1 スナップショット（履歴）

- フェーズ：**P0〜P6 完了。P7 に着手（V-C＝規則ベースの読み取りまで完了）**。
  10 doctype × 2 content × 2 style（`lic-0001` のみ 3 style）＝ **41 文書**（＋ `sample_min`）で v1 の目標 40–60 に到達。
- `make check` 緑（**513 passed / skip 0**）。`make doctor` 全項目 OK。
- **`keiyaku batch specs/batch_v1.yaml` が ready 41/41。** manifest check 一致（`dataset/` は 41 ディレクトリ）。
- **20 content / 10 doctype（各 2 本）。** lint（`--similarity` 含む）・verify・QA すべて error 0 / warn 0。
  **全ページを目視済み。** `eval --oracle` は全指標で満点。
- **HITL は H1〜H4・H6〜H8 が決定済み**（2026-09-27）。残るは H5（`apply` の算出値 41 問）。

  | doctype | content | 備考 |
  |---|---|---|
  | nda | `nda-0001` / **`nda-0002`** | 相互開示 ↔ **一方向の開示**（preset も違う） |
  | outsourcing | `ots-0001` / **`ots-0002`** | 物流の代行 ↔ **演奏会の運営**（委託者が公益社団法人） |
  | license | `lic-0001` / `lic-0002` | 特許の実施許諾 ↔ **商標の使用許諾＋逐条解説** |
  | delegation | `dlg-0001` / **`dlg-0002`** | 計装盤の配線設計助勢 ↔ **学園の図書室の運営**（preset も違う） |
  | consulting | `csl-0001` / **`csl-0002`** | 食品会社の仕入と在庫 ↔ **石材加工業の事業承継と原価**（preset も違う） |
  | purchase | `pur-0001` / **`pur-0002`** | 自治体が買う流量計測装置 ↔ **食品会社が買う急速凍結設備＋据付工事**（preset も違う） |
  | lease | `lea-0001` / **`lea-0002`** | 事務所・**3 者**（保証業者つき） ↔ **店舗・2 者**（菓子の製造販売） |
  | employment | `emp-0001` / **`emp-0002`** | 製菓工場・**有期・月給** ↔ **介護の事業所・無期・時間給・交替制** |
  | contracting | `con-0001` / **`con-0002`** | 町発注の土木工事 ↔ **医療法人の診療所の増築**（preset も違う） |
  | sysdev | `sys-0001` / **`sys-0002`** | 信用組合の勘定系（工程型） ↔ **物流の倉庫システム（反復型）** |

- 検索評価セット：content ごとに 1 style ＝ 20 文書をコーパスにしている。
- lint は **L00〜L26**、verify は **V01〜V11**、numbering は 3 方式。
- **P7-1（V-C）完了**：規則ベースの読み取りを全 41 文書で完走。契約の穴 3 件を採点側に落とした
  （`docs/validation_plan.md` §2・`docs/decisions.md` 119）。`eval --all --oracle` は満点のまま。
- **P7-2（V-D）完了**（条文型・様式型・頭書型・約款型の 4 骨格）。**契約の穴 6 件**を docs・採点側・
  **正解データ**へ（decisions 120〜123）。直した後は CER 0.00〜0.11・見出し F1 0.97〜1.00・
  citation 0.98〜1.00・TEDS 1.00・列挙 1.00。
- **P7-3（V-E 盲検）完了**（条文型・逐条解説つき・頭書型・様式型・長文型の **5 本**）。
  点はほぼ満点（CER 0.000〜0.008・citation 0.98〜1.00）だが、「仕様に書いていない」が
  **1 巡目 16 件・2 巡目 12 件**報告され、すべて `docs/evaluation.md` §4.8・§4.9 に決めた
  （decisions 126〜130）。採点側の穴も 1 件（表の対応づけ）直した。
- **単調性の検査に図の多い文書ができた**：`sys-0002` に図を 2 点足して 3 点（ノード 24・辺 24・経路 9）。
  これまで全文書が図 1 点で、図の指標は「反応を要求しない」扱いだった（`docs/evaluation.md` §6 の条件 2）。

## 2026-10-08 検索評価セットを別の Hugging Face データセットに分けた

**指示**：「`dataset/search/` を Hugging Face 登録時に新しいデータセットへ移す」。

**やったこと**（`docs/decisions.md` 160〜163・`docs/publishing.md` §12）：

- `specs/publish.yaml` に **`search_dataset`** を新設（`enabled` / `dir` / `hub` / `pretty_name` /
  `pretty_name_ja` / `task_categories` / `task_ids` / `tags`）。**公開の決定は宣言だけに置く。**
- `keiyaku/publish.py`：`CONFIGS` を本体 4 件（`documents` / `pages` / `qa` / `elements`）と
  `SEARCH_CONFIGS` 3 件に分け、`main_configs()` が切り出しの有無で出すものを変える。
  検索側のカード（`render_search_card()` / `search_frontmatter()` / `write_search_card()`）、
  配布一覧とチェックサム（`search_distributed_files()` / `search_checksums()`）を追加。
  `distributed_files()` は切り出した `search/` を**ディレクトリごと**外す。
- `scripts/upload_hf.py` は 2 リポジトリを上げる（`--only main|search`）。本体の `upload_folder` には
  `search/` を `ignore_patterns` で渡す——**`dataset/` を丸ごと上げると二重に入る。**
- `blockers()` に「検索評価セットの公開先が無い」を追加。**本体に入れないと決めたのに公開先が無いと、
  検索評価セットがどこにも出ない。**
- 実測：本体 **1,367 ファイル・365.8 MiB**／検索側 **5 ファイル・2.9 MiB**。
  `publish check` は両方の鮮度を見て緑。pytest **555 passed**。

**踏んだこと**：

- **検索側の `LICENSE` に `licenses/NOTICE.md` を案内してはいけない。** あちらのリポジトリに PDF は
  無く、フォントのライセンス本文も入らない（存在しないファイルを指す案内になる）。
  `write_license_file(..., fonts=False)` で分けた。
- **`SHA256SUMS` のパスは自分のルートからの相対**にする（`search/passages.jsonl` ではなく
  `passages.jsonl`）。別リポジトリとして clone した人が `sha256sum -c` を使えなくなる。
- **grade 1 の打ち切りの説明が本体のカードから消える。** 検索側のカードに移し、
  **英語面（`## Caveats`）にも出した**——検索の利用者は英語面しか読まないことが多く、
  キャップを知らずに Recall@k を読むと誤解する。
- `tests/unit/test_export.py` の 2 本は「本体のカードがクエリ数を実測する」ことを縛っていたが、
  その数は検索側のカードへ移った。**検査を緩めず**、同梱設定（`enabled: false`）で縛り直し、
  切り出し時は「公開先への案内が出ていること」を別に縛った。

## 2026-10-05 データセットを Hugging Face で公開できる形に整えた（T15）

ユーザー指示は「`contracts` の `dataset/` を Hugging Face で公開し提供したい。そのために必要な対応を
計画し、実行せよ。アップロードはまだ不要」。**ライセンスは AI が決めない**ので、そこだけ宣言から読む形にして
依存しない作業をすべて進めた。

**何が足りなかったか**（`docs/publishing.md` §1）。`dataset/` は評価ハーネス向けの置き場で、Hub に出すには
5 つ欠けていた：**カードの YAML frontmatter**（Hub は直下の `README.md` をカードとして読み、`license` /
`configs` が無いと検索にも Dataset Viewer にも出ない）／**平らな表形式の面**（Viewer と `load_dataset()` は
jsonl・csv・parquet しか読めず、入れ子 1 文書 1 ファイルの `source.json` は読めない）／**LFS の指定**／
**配布しないものの除外**（`render.html` はデバッグ用で配布対象外）／**ライセンスと帰属**（PDF には Noto の
サブセットが埋め込まれており、OFL 1.1 は再配布時に本文の同梱を求める）。

**足したもの 6 点**（`keiyaku publish update`。一次資料は 1 バイトも変えない）：

| 生成物 | 中身 |
|---|---|
| `README.md` | **= Hub のデータセットカード**。frontmatter（7 つの config・タスク分類・タグ・規模）＋英語の要約・用途・非用途・config の表・引用（BibTeX）＋日本語のファイルの読み方（旧 README の本文） |
| `views/{documents,pages,qa}.jsonl` | 一次資料の**射影**（100 行 / 656 行 / 4,500 行）。`elements` は `*/elements.jsonl` の glob、検索評価セットは `search/*.jsonl` をそのまま config にした（**重複を作らない**） |
| `.gitattributes` | `*.pdf` `*.png` を LFS。jsonl / json は入れない（1 ファイルが小さく diff が見えるほうが価値が高い） |
| `licenses/` | **実測した**埋め込みフォント（`Noto-Sans-JP` `Noto-Serif-JP` 各 Regular・Bold）の本文 ＋ NOTICE。同梱してあるだけの IPAex は**入れない** |
| `SHA256SUMS` | 配布する 1,369 ファイルのハッシュ（`manifest.json` の checksums は 1 文書 5 ファイルぶんしか無く PNG と jsonl を覆っていない） |
| `.gitignore` | `render.html`・`.DS_Store`・`*.log`（アップロード側の `ignore_patterns` も同じ宣言から作る） |

**Arrow の罠を 1 つ潰した**：`qa.json` の `answer` は **float / str / list が混在する**（`answer_type` で
決まる）ため、そのまま jsonl にすると Viewer の parquet 変換が落ちる。views では型ごとの列
（`answer_text` / `answer_number` / `answer_list`）に分け、**生の値を `answer_json` で失わないように**した。
**採点に使う正本は各文書の `qa.json`** のままである。`scripts/verify_views.py` が全列の型を走査し
（型混在・全行 null の列を検出）、`pyarrow` があれば実際に parquet へ変換する——実測で **6 ファイル＋
`*/elements.jsonl`（100 ファイル・42,789 行・23 列）がすべて落ちた**。

**人間の決定を代行しない設計**：`specs/publish.yaml` の `license.id` が `undecided` のあいだ、
frontmatter に `license` キーを出さず（嘘のタグを出さない）、`dataset/LICENSE` を作らず、カードと
データカード §12 に「未決」と書き、`scripts/upload_hf.py` は**終了コード 1 で拒否する**。
決定が入れば**宣言 1 行＋`keiyaku publish update`** でカード・frontmatter・`LICENSE`・NOTICE がそろう
（実測済み）。アップロードは既定 dry-run で、`--yes` を付けても未決なら上げない。

**ついでに直した 3 件**：

| 直したもの | 何が起きていたか |
|---|---|
| `export` が書く README の表題 | **「生成した約款データセットの読み方」**——yakkan（保険約款）の名残が、契約書のデータセットの配布物に残っていた |
| `keiyaku clean --stale` | 「doc_id の一覧に無い `dataset/` 直下のディレクトリ」を消す実装で、**`search/` を消す**潜在不具合があった（`views/` `licenses/` を足すと被害が広がる）。`PROTECTED_DIRS` を新設し、`publish.PROTECTED_HINT` との整合をテストで縛った |
| データカードの容量集計 | 公開用の包みを数えるため、カードのサイズ → `SHA256SUMS` → カード…と相互参照になり **1 回の `export` では鮮度検査が収束しなかった**（実際に `datacard check` が赤になった）。`SIZE_EXCLUDE_DIRS` で外し、カードに但し書きを出した |

**実測**：`publish update` を 2 回でバイト一致（決定論）／`export` 1 回で `manifest check`・
`datacard check`・`publish check` の 3 つが緑／配布 **1,369 ファイル・368.6 MiB**（`render.html` 100 件と
`.DS_Store` を除外）／`make check` 緑（pytest **545 passed**・新規 12 本）。

**`specs/publish.yaml` は `.gitignore` の例外として追跡する**（決定 157）。決定 152 で `specs/` を外したが、
公開の宣言は**人間の決定の記録**であり公開物を作るコードの入力でもある。ディレクトリ単位の除外では
配下を再包含できないため `specs/*` ＋ `!specs/publish.yaml` に書き換えた（`parts/` と同じ罠）。
宣言が無い環境でも `keiyaku export` は止まらない（既定に落ち、公開だけがふさがる）。

**次の 3 タスク**

1. **H13**（配布条件）の決定を受けて `specs/publish.yaml` の `license.id` を直し、`keiyaku publish update`。
2. **H15**（リポジトリ名・private → public の段取り・実行者）の決定を受けてアップロード。
3. **H16**（名義）の決定を受けて `citation.authors` と `license.holder` を直す。

## 次の 3 タスク

1. **H13**（生成物の配布条件＝ライセンス）の人間判断を待つ。決定後は `specs/publish.yaml` の
   `license.id` を 1 行直して `keiyaku publish update` → `keiyaku publish check`（公開の準備は完了済み）。
2. **H15**（Hugging Face のリポジトリ名・private → public の段取り・アップロードの実行者）と
   **H16**（公開時の名義）の判断を待つ。決まれば宣言の書き換えだけで追従する。
3. **H14**（拡張で増えた `apply` QA 60 問の算出規則）の人間判断を待つ。決定後、必要なら
   `qa_authored.json` → batch → manifest/export → eval の順で反映する。
   **H12**（legacy golden の去就）は整理のときに決める。

## v1 の受け入れ条件（`docs/evaluation.md` §6）— 2026-10-03 時点

| # | 条件 | 状態 |
|---|---|---|
| 1 | `eval --all --oracle` が**全文書・全指標で満点** | **満たした**（41 文書 × 18 指標。満点でない指標 0 件） |
| 2 | `--misread` で**単調に悪化**（図 3 点以上の文書で） | **満たした**（`sys-0002` 図 3 点・ノード 24・辺 24・経路 9。テストで固定） |
| 3 | **規則ベースの読み取り器**で全文書を採点でき、点が 0〜1 で動く | **満たした**（41 文書完走。doctype で差が出る。`docs/validation_plan.md` §2） |
| 4 | **盲検読み取り**を骨格類型ごとに 1 本以上、穴をすべて解消 | **満たした**（5 本。契約の穴 28 件・採点側 1 件を解消。§4 の記録） |
| 5 | `manifest check` 一致・`make check` 緑 | **満たした**（519 passed・`doctor` すべて OK） |

**`docs/plan.md` の P7 DoD には「`HITL_TODO.md` の全項目に人間の決定」も入る。
残るのは H5 だけで、これが v1 タグの最後の 1 件。**

## フェーズ状態（`docs/plan.md` の WBS に対応）

| フェーズ | 状態 | メモ |
|---|---|---|
| P0 移植 | **完了**（2026-09-26） | smoke が yakkan とバイト一致 |
| P1 構造分析 | **完了**（2026-09-27） | 39 件計測・10 カテゴリ目視。CT1〜CT25 確定。§2 の誤り 5 点を訂正 |
| P2 契約書化 | **完了**（2026-09-26） | doctype・numbering 宣言化・`{party:}`・新 kind/Block・probe 3 件・lint L19–L21・style 3 種・契約書 sample_min |
| P3 条文型 | **完了**（2026-09-27） | 4 doctype × 1 content が ready 9/9。lint/verify/QA すべて緑、全ページ目視済み |
| P4 別紙・目録型 | **完了**（2026-09-27） | `purchase` `lease` `license` が ready。頭書の設計は probe で確定 |
| P5 様式型・長文型 | **完了**（2026-09-27） | `employment` `contracting` `sysdev` ＋ `commentary`（`lic-0002`） | `employment`（`contract-form` は実装済み）・`contracting`・`commentary`（型は実装済み・描画は P5） |
| P6 データセット v1 | **完了**（2026-09-28） | 10 doctype × 2 content × 2 style（`lic-0001` のみ 3 style）＝ 41 文書。batch ready 41/41・`eval --all --oracle` 全満点 |
| P7 検証・硬化 | **進行中** | V-A/V-B 常時緑。**V-C（規則ベース）完了**——契約の穴 3 件を採点側へ。次は V-D（自セッション VLM）→ V-E（盲検）。H5 以外の HITL は決定済み |
| P8 拡張 | 未着手 | A3 縦 style・doctype 追加・docsynth 切り出しの判断 |

## 残っている宿題

| # | 内容 | 状態 |
|---|---|---|
| 1 | **H5（`apply` QA の算出値 47 問）の人間の決定** | **v1 タグの最後の 1 件**。材料は `HITL_apply_review.md` |
| 2 | `tests/golden/numbering_legacy.json`（616KB）は P2-2 の検証用の過渡的資産 | 保険方式の宣言を捨てる判断をしたら一緒に消す（P8） |
| 3 | P8：doctype 追加・`../structured-docs/` への切り出しの判断 | v1 の後（**A3 横の style は 2026-10-03 に実装済み**） |

**片づいた宿題**（2026-10-03 時点）：`tests/` の skip は **0 件**（15 件は doctype・style が揃って自動的に解消）／
`commentary` の描画（`lic-0002` で確定）／`head_matter` の描画（`purchase` `lease` で確定）／
`figures.path_f1` の単調性（`sys-0002` が経路 9 本を持つので反応を要求できる）／
`chars_per_page_estimate` の較正（**2026-10-03 に実コーパス 41 文書で較正し直した**。
form 1293→1296・gothic 922→925・mincho 745→742。ずれは 0.3% 以内）／10 doctype の blueprint。

## 記録

### 2026-09-26（5）P2 完了：probe・style 3 種・契約書ブロックの描画・blueprint・条文ライブラリ

- **P2-5 要 probe 3 件（完了）**：`scripts/probe_signature.py` を書いて実測した。
  - 「印」の丸枠＝`inline-block`＋`border-radius: 50%` で 1 断片・34.8×34.8pt・行の内側・文字はテキスト層に載る
  - `signature_layout: horizontal`＝`flex` で左右に並び、**読み順は DOM 順と一致**（段組と違う扱いが要らない）
  - `− N −` 型フッタ＝`@bottom-center` の MarginBox として判定でき、テキスト層に載る
  - **probe 自体で 1 度踏んだ**：素朴な helper で測ると `inline-block` が「1 要素 3 断片」に見える。
    本番の抽出器は `TextBox`/`LineBox` を除外するので実際は 1 断片。**probe は本番と同じ規則で測る**
    （`docs/decisions.md` 44・`docs/gotchas.md`）。
- **P2-7 style 3 種（完了）**：`ct-a4-1col-mincho`（既定・無ヘッダ・`− N −`）／`-gothic`（下線見出し・
  横並び記名欄）／`-form`（様式型・太罫線）。`Style` に `header` / `parties_style` / `signature_layout` /
  `table.border: form` を追加。較正値は**暫定と明記**（P3 で実測する）。
- **契約書ブロックの描画**：`parties` / `signature`（後文・契約日・記名欄・収入印紙欄）/ `revision_history` /
  `commentary`。`{party:}` を inline レンダラにも通した（**これが無く、最初の verify で本文 11 件が
  PDF から読めなかった**）。`page.html` の構造は変えていない。
- **`blueprints/nda.yaml`＋条文ライブラリ 7 本**（協議・合意管轄・通知・存続・反社・譲渡禁止・可分性）を
  **オリジナル文**で用意。`keiyaku scaffold --doctype nda` が通る。
- **目視レビューで verify が検出できない欠陥を 3 件見つけた**（CLAUDE.md §0.4-7 のとおり）：
  1. **図の辺ラベルが版面の外で切れていた**（`col: -1` にしたため）。→ L06 に「格子座標が負なら error」を追加。
  2. **表題が表の中にあってもページ境界で離れた**（caption が p2・全行が p3）。
     yakkan の「中に置けば離れない」は 2 段組での経験で、1 段組では成り立たなかった。
     → `table > caption { break-after: avoid }`。内容欠落が無いことを実測で確認。
  3. **項ラベル欄が保険の「（１）」幅（3.6em）で固定**され、契約書の「２」で間延びした。
     → `label_widths()` が `derived.labels` から算出する（`docs/rendering.md` §2 の規約に実装を合わせた）。
- **`keiyaku review` を実装**（docs にあって実装が無かった。D-7 の食い違い）。
- **lint が実際に欠陥を見つけた 3 件**：L20 が「記名押印欄が無い」、L10 が「定義文が敬体」「章要約が敬体」、
  L08 が**当事者名の実在社名を素通りしていた**（`iter_texts` が `meta` を見ていなかった）。
  → `iter_texts` に `meta` を追加し、副作用（L19 が呼称の宣言を拾う／L10 が ISO 日付を数える）も直した。
- **L04 の silent pass を潰した**：`node` / `enumeration` / `ref` の数え方が未実装で、
  blueprint に宣言しても黙って通っていた。
- P2 の宿題を消化：CLI の説明文・denylist（契約書用に全面差し替え）・`qa/auto.py` の質問文言・
  `mock.py` の見本種別・`export`/`search_set` の `product_name` 依存（→ `doc_title` と `parties`）。
- `docs/decisions.md` に 41〜55、`docs/gotchas.md` に 4 件、`docs/rendering.md` §7 の probe 表を更新。

### 2026-09-26（4）P2-2 / P2-4 / P2-6：numbering の宣言化・契約書の kind・lint L19–L21

- **P2-2 宣言的 numbering（最初の山・完了）**
  - `keiyaku/numbering_spec.py`（解釈器）と `numbering/contract-standard.yaml` / `contract-form.yaml` を新設。
    `keiyaku/numbering.py` から 5 つの `_label_*` 関数と 3 つの直書き定数を削除した。
  - **手順**：置き換える前に `scripts/capture_numbering_golden.py` で現在の挙動を総当たりで捕獲
    （ラベル 2,170／別表 90／脚注 60／見出し 27／参照 5,880／citation ＝ **8,227 データ点**）。
    そのうえで yakkan の 5 方式を宣言で書き下し、同一出力を `tests/unit/test_numbering_spec.py` が固定。
  - **結果：45 テストが初回で全パス。5 方式すべてが宣言で表現でき、hooks への逃げ道は 1 つも要らなかった**
    （必要だった宣言項目は `skip_first` / `skip_when_single` / `unsupported` /
    `appendix.bare_when_first` / `appendix_levels` / `footnote.inline` / `paragraph_ref_style` の 7 つ）。
    宣言スキーマの表現力が足りているという実地の裏付けが取れた。
- **P2-4 新 kind / Block**：`preamble` / `head_matter` / `signature` / `schedule` / `supplement` と
  `parties` / `revision_history` / `commentary`。`back_matter.signature` と compose の
  `signature` target、`DocumentIndex` の `back_matter` 引数も追加した。
  - **走査の集約**：`body + appendices` と書いた箇所が 10 個あり、記名押印欄が**平文化から漏れた**
    （`derived.plain_text` に `sig_p1` が入らず KeyError）。`document_nodes(draft)` に集約して直した
    （`docs/decisions.md` 38）。
- **P2-6 lint L19–L21**：`keiyaku/lint/parties.py` に 3 ルール。テスト 14 本。
  - **L19 の直書き検出でつまずいた**：`\b`（語境界）は日本語で使えない——`\w` に漢字も仮名も入るので
    「甲は」と「甲板」を区別できない。**呼称の連なりを取り出し、1 文字なら直後の漢字で除外、
    2 文字以上なら拾う**方式にした（「甲板」「乙種」を通し、「甲乙間」を拾う）。
    拾えない範囲（「甲側」「乙宛」）は docstring と `docs/lint_rules.md` に明記し、目視の担当に回した。
  - **L20 は実際に欠陥を見つけた**：`sample_min` に記名押印欄が無いことを指摘し、前文・当事者表示・
    記名押印欄を足すきっかけになった。
- 予測語彙（`NodeKindName`）を `NodeKind` の包含形にし、差分（`commentary`）を
  `PREDICTION_ONLY_KINDS` に明示（`docs/decisions.md` 40）。
- `meta.numbering_scheme` を Literal から `str` に（宣言の存在が正本）。
- `docs/lint_rules.md`・`docs/decisions.md`（35〜40）を更新。

### 2026-09-26（3）P2 を着手：doctype・`{party:}`・契約書 sample_min

- **P2-1 doctype**：`genre`（10 値の Literal）を `family`（固定値 `contract`）＋ `doctype`（**enum にしない**。
  `blueprints/<doctype>.yaml` が正本）に置き換え、`schema_version` を `"2.0"` に上げた。
  13 モジュール（models・blueprints・library・scaffold・batch・manifest・export・search_set・cli・
  lint/structure・lint/similarity ほか）を更新。
- **`keiyaku doctypes` コマンドと `keiyaku/doctypes.py` を新設**：doctype 名を Python に持たないぶん、
  宣言どうしの食い違い（ファイル名と `doctype:` の不一致・`numbering/<scheme>.yaml` と
  `styles/<style_id>.yaml` の不在・名前の衝突）を機械で検査する。L00 にも doctype の存在検証を足した。
  **「検証できていない」ことの可視化は `keiyaku doctypes` の担当**にし、lint の warn では言わない
  （情報提供で warn を埋めると規律が効かなくなる）。
- **P2-3 `{party:}`**：`PartyDef`（key / alias / name / address / representative / role_label）、
  RichText の `Party` トークン（4 modifier）、build の解決、`derived.party_uses[]` を実装。
  `sample_min` で 13 箇所が解決されることを確認した。
- **Meta を契約書化**：`parties`（必須・2 者以上）・`contract_date`・`effective_date`・`contract_number`・
  `copies`・`stamp_duty` を追加し、保険の `issuer`（必須→任意）・`product_name`・`pet_name`・
  `edition_date` を削除。`SemanticType` をコア共通 9 種＋契約書 6 種に、`front_matter` の
  `cover`/`toc` を任意にし、保険の前付け 3 種をモデルとテンプレートから削除した。
- **P2-8 契約書の `sample_min`**：Meta の変更で保険 fixture が 50 テストを落としたため前倒しした。
  NDA の最小形（2 当事者・2 章・章-節-条-項・列挙表 2・キャプション付き表 2・図 1（flowchart）・
  脚注 2・欄外注 1・別紙 1・奥付）を**オリジナル文**で執筆。lint error 0 / build 通過。
- **lint を契約書に合わせた**：L10（全 doctype 常体。**欄外注・前付け・奥付は判定対象外**）、
  L13（必須は title と disclaimer、当事者の非空、日付形式）。
  **L10 は私の執筆ミス（定義文を敬体で書いた・章要約が敬体）を実際に検出した**——規律が効いている。
- 事故と対処：作業ディレクトリの持ち越しで `insurance-contracts/` の fixture を 1 ファイル書き換えた。
  `git checkout --` で復元し、`docs/gotchas.md` に「姉妹プロジェクトを誤って書き換えた」として記録した。

### 2026-10-03（27）HITL_TODO.md を「未決のものだけ」に整理した

`HITL_TODO.md` が、決定済みの 7 件・未決の 1 件・47 問ぶんの計算過程・起票の手順を
1 ファイルに抱えて 370 行になっていた。**人間が見るべきもの（＝未決の項目）が埋もれる**ので分けた。

| 移したもの | 行き先 | 理由 |
|---|---|---|
| H1〜H4・H6〜H8 の決定と**作業への反映** | `docs/validation_plan.md` §5「決定済みの項目」 | HITL の設計上の位置づけはもともと §5。決定の意味と波及をそこで一覧できる |
| H5-1〜H5-19 の**計算過程**と「あわせて見てほしいこと」 | `specs/apply_notes.yaml` → **`HITL_apply_review.md`**（生成） | 検算に要るものが**問い・答え・根拠と同じ 1 枚**に並ぶ。生成物を手で編集しない原則も守れる |
| 記名押印欄の順序の根拠（判断不要の参考） | `docs/decisions.md` の補足節 | 人間の判断を仰ぐ項目ではない |

`HITL_TODO.md` は **49 行**になり、未決の H5 だけを置く。`scripts/apply_review.py` は
`specs/apply_notes.yaml` を読んで検算メモを流し込むようにした（**47 問すべてにメモあり**を
生成時に確かめ、欠けていれば冒頭に警告を出す）。シートは 602 行で、再生成しても同じ内容になる。

過去の記録（この下の各回）にある「`HITL_TODO.md` H5-8」などの参照は、**当時の事実**として残してある。
現在の所在は `HITL_apply_review.md`。

### 2026-10-03（26）P8-1 — A3 横の style（`ct-a3-landscape-form`）を実装した

`docs/plan.md` の P8 の 1 件目。**先に判型の食い違いを直した**：plan.md は「A3 縦 1 枚物
（`ct-a3-1col-form`）」だったが、`docs/reference_structures.md` §4.1 の訂正表（2026-09-27）では
実測は **A3 横 1191×842pt**で、style 名も `ct-a3-landscape-*` と決めてあった。plan.md が訂正前のまま
取り残されていたので、plan.md・doctypes.md・reference_structures.md の 3 本を実測に合わせた。

実装：`styles/ct-a3-landscape-form.yaml` ＋ `styles/css/ct-a3-landscape-form.css.j2`
（`ct-a4-1col-form` を `{% include %}` して差分だけ）。実物が **1 枚を左右 2 面に使う**ので
**2 段組**にした（doctypes.md の表は「1 段」と書いてあったので、実装に合わせて訂正）。
`pur-0001` を描くと **A4 縦 6 ページ → A3 横 2 ページ**で、左面に当事者表示・頭書・第1〜3条・表1、
右面に第4〜6条・図1 が載る。verify 0/0、内容欠落なし、**全ページを目視**した。

- `chars_per_page_estimate` は暫定 2600 → 実測で **2638** に較正（一時的に `dataset/` へ置いて
  `calibrate_styles.py --write` → 消す。`dataset/` は汚さない）。
- **受け入れ条件（既存文書の再生成で `answer.json` に差分が出ない）を満たした**
  （batch ready 41/41・3 文書を直接 diff して差分なし・`manifest check` 一致）。
- 手順書（`docs/doctypes.md` §7）に、**新 style で足りなかった 3 点**を追記した：
  style ごとの CSS テンプレートが必須（無いと `TemplateNotFound`）／較正の手順／
  2 段の style では段またぎ要素を置かない。

v1 のデータセット（41 文書）には**加えていない**。H5 が決まって v1 を切ってから、
この style を使う文書を足すか判断する。

### 2026-10-03（25）宿題の棚卸し — `chars_per_page_estimate` を実コーパスで較正し直した

`docs/progress.md` の「残っている宿題」が古かったので、1 件ずつ実物で確かめて書き直した。
**片づいていたのに残っていた** 6 件（skip 15 件／`commentary` の描画／`head_matter` の描画／
`figures.path_f1` の単調性／10 doctype の blueprint／較正）を落とし、残りを 3 件にした。

- `scripts/calibrate_styles.py` を**実コーパス 41 文書**で回し直した（form 1293→1296・
  gothic 922→925・mincho 745→742）。**ずれは 0.3% 以内**で、L09 の見積りは実ページ数に合っている。
- `apply` QA 47 問を**独立に検算し直した**（1 回目は執筆時）。食い違いなし。
  ただし**人間の確認を代替しない**——計算の前提の置き方そのものが H5 の判断対象なので、
  各問の「あわせて見てほしいこと」を残したまま H5 を待つ。

### 2026-10-03（24）v1 の受け入れ条件を確認し、H5 の検算シートを用意した

`docs/evaluation.md` §6 の 5 条件を 1 つずつ確かめ、**5 件すべて満たしている**ことを記録した（上の表）。
条件 1 は JSON を開いて 41 文書 × 18 指標を機械的に突き合わせ、**満点でない指標が 0 件**であることを確認。

**残るのは H5（`apply` QA の算出値 47 問）だけ**。人間が検算するほかない項目なので、
`scripts/apply_review.py` を書いて **`HITL_apply_review.md`**（問い・答え・**根拠の条文の紙面の文字列と
ページ**を 1 枚にまとめた 426 行）を生成した。PDF を開かずに検算できる。
計算の過程は従来どおり `HITL_apply_review.md` にある。

v1 タグと push（H1 で可と決定済み）は、この 1 件が決まってから行う。

### 2026-10-03（23）P7-3 完了 — 盲検 5 本。採点側の穴 1 件、契約の穴 12 件

2 巡目は**頭書型・様式型・長文型**の 3 本（§4.8 を足した後の仕様で読ませた）。

| 文書 | CER | 見出し F1 | citation | カバー率 | TEDS | セル | 図ノード | bbox 当たり |
|---|---|---|---|---|---|---|---|---|
| `lea-0002` form（頭書型） | 0.002 | 0.96 | 1.00 | 0.93 | 1.00 | 1.00 | 1.00 | 1.00 |
| `emp-0001` form（様式型） | 0.008 | 0.99 | 0.98 | 0.90 | 1.00 | 1.00 | 1.00 | 1.00 |
| `sys-0001` form（長文型・目次つき） | 0.003 | 1.00 | 1.00 | 0.99 | **0.97** | 0.88 | 1.00 | 0.99 |

**採点側の穴（decisions 129）**：`sys-0001` の読み手が、罫線で囲まれた当事者表示を「表」として
1 つ余分に出した。表を**位置**で対応づけていたため以降がすべてずれ、**TEDS が 0.36** まで落ちた。
「キャプション → 中身 → 位置」の 3 段で 1 対 1 に割り当てるよう直し、**0.97**（セル F1 0.55 → 0.88）。
oracle は 1.00 のまま。回帰テストつき。

**契約の穴（decisions 130）**：3 本が**そろって**「仕様と、配った実例（正解から出した満点予測）が
食い違う」と報告した。実測すると、採点は 3 層に分かれていた：

1. **構造位置**（カバー率・citation・種別）＝ 本文の項・号だけ
2. **bbox** ＝ `plain_text` に入るものすべて（表のセル・title・図のノード・解説も）
3. **`pages[].text`** ＝ 紙面どおり（奥付も入る。柱・ノンブル・図の中の文字・繰り返しのヘッダは入らない）

§4.9 を新設してこの 3 層を書き、§4.3 の「記名行ごとに 1 要素で出す」（採点されない項目への過剰な指示）と
§4.8 の 2 行（表題・条見出しの扱い）を実測に合わせて訂正した。2 巡目で新たに出た 12 件
（目次・繰り返しヘッダ・当事者表示の表・前文の番号・`timeline` の `paths`・citation の正規化ほか）も
§4.8 の表に追加（累計 **28 件**）。

**これで `docs/evaluation.md` §6 の DoD 条件 4（骨格類型ごとに盲検 1 本以上）を満たした。**

### 2026-10-03（22）盲検の指摘から L26 — 番号を持つ表・図は `{ref:}` で指す

盲検の読み手が「同じ表を一方では『下表』、他方では『表1』と呼んでいる」と報告した。調べると
**20 content のうち 15 content・計 32 箇所**で、番号を持つ表・図を「下表」で指していた。

- 「下表」は**版面が変われば嘘になる**（実際に別紙の表が次ページへ送られ、導入の文だけ前ページに残った）。
- 番号を持たない列挙表（L18 が caption を禁じる）は対象外。`{ref:}` は解決できないので「下表」でよい。

L26（warn）を新設し、32 箇所を `{ref:}` に直した。`tests/golden/sample_min` も同じ規約に合わせ、
golden を更新（テキスト層・layout・参照解決の 3 本）。`make check` 518 passed、batch ready 41/41、
`eval --all --oracle` 満点。

**この回の盲検 3 本（頭書型・様式型・長文型）は、この修正の前に撮ったページ画像を読んでいる**ので、
採点では「下表 → 表N」の箇所だけ差が出る。報告時に切り分ける。

### 2026-10-02（21）P7-3（V-E 盲検）2 本 — 点は満点、**契約の未記載が 16 件**

構築経緯を持たない**素の Agent** 2 体に、次だけを渡して読ませた（渡したものの一覧は
`docs/validation_plan.md` §4）：ページ画像（**リポジトリの外へコピー**）、`docs/evaluation.md`、
`schema/prediction.schema.json`、**別文書**の予測 1 本、そして「リポジトリを読まない」禁止。

| 文書 | CER | 見出し F1 | 種別 | citation | TEDS | セル | 図ノード | 図エッジ | 列挙 | bbox 当たり |
|---|---|---|---|---|---|---|---|---|---|---|
| `nda-0002` mincho（条文型） | **0.000** | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.82 | 1.00 | 0.98 |
| `lic-0002` mincho（逐条解説つき） | **0.000** | 1.00 | 0.95 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |

**点が出たのは読み手が正しく推測できたからで、契約が十分だったからではない。**
2 体が挙げた「仕様を読んでも分からなかった」は合わせて **16 件**：逐条解説の `citation`、
解説枠の見出し行、解説を `outline` に出すか、別表の中の番号の `kind`、別表の citation 表記、
表題・図題の行、条見出しの行、奥付、当事者表示の `kind`、`pages[].text` の番号、CER の正規化、
`bbox` の矩形の取り方、`nodes[].role` の語彙、`timeline` のエッジ 3 系統、`steps` の小枠の見出し、
`cells` の行見出し列。**すべて gold の実測に合わせて `docs/evaluation.md` §4.8 に決めた**。

**配布物の欠陥も 1 件**：形式の実例として配った手書きの予測が `pages[].text` の項番号を落としており、
仕様と食い違っていた。`keiyaku eval <doc> --oracle --dump-pred <path>` で**正解から満点の予測を
書き出せる**ようにし、実例がずれる余地を無くした（decisions 126）。

### 2026-10-02（20）P7-2 完了 — 約款型の自読で**正解データの欠陥**を 1 件見つけた

V-D の 4 本目として約款型（`con-0002` form・8 ページ・漢数字の条番号）を自読した。

| 観点 | 値 |
|---|---|
| 本文 CER | 0.040 |
| 見出し F1 | **1.000** |
| 構造位置 citation | 0.718 → **1.000**（下記の修正後） |
| 表 TEDS / セル F1 | 1.00 / 1.00 |
| 図ノード・エッジ | 1.00 / 1.00 |
| bbox 当たり率 | 0.98 |

**見つけた欠陥（正解データ側）**：`article_heading: above`（条見出しを条番号の上に置く体裁）では、
条ラベルが第1項の本文の先頭へ走り込む。**これは描画の都合**なのに `citation` にも混ぜていたため、
号の位置づけが「**第三条 第三条 (1)**」と条番号が二重になっていた。
外から読んだ予測では決して再現できない正解で、**該当は `contracting` の 4 文書**。
`citation` から `run_in_label` を外し（decisions 123）、`dataset/` を作り直して citation 正解率 **1.00**。

漢数字の条番号（`第二十四条`）そのものは、紙面どおり書き起こせばそのまま突合できた。
これで **V-D は 4 骨格すべて完了**。`eval --all --oracle` は満点のまま、`make check` 514 passed。

### 2026-10-02（19）P7-2（V-D）— 自読で「契約の未記載」を 5 件つぶした

骨格類型ごとに 1 文書を、**`pages/*.png` だけ**を見て読み、予測 JSON を書いて採点した
（正解ファイルは開かない。外部 API も使わない。H8 の決定）。詳細は `docs/validation_plan.md` §3。

| 文書（骨格） | CER | 見出し F1 | citation | TEDS | セル F1 | 図ノード | 列挙 | bbox 当たり |
|---|---|---|---|---|---|---|---|---|
| `dlg-0002` form（条文型） | 0.108 | 0.993 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.65 |
| `emp-0002` form（様式型） | **0.000** | 0.974 | 0.98 | 1.00 | 1.00 | 1.00 | 1.00 | 0.70 |
| `pur-0002` form（頭書型） | 0.065 | 0.992 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 0.82 |

**点が出なかった観点は 3 つとも「読み取りの力不足」ではなく「契約の未記載」だった**。

1. `outline` に条だけを出したら 0.32。gold は**項・号も含む**（73 件中、条は 13 件）→ §4.1 に明記して 0.99。
2. 本文を先に並べ見出しと表を後ろにまとめたら CER 0.63。gold は**紙面の読み順**で、
   表のセルと奥付は入り、**図の中の文字と柱・ノンブルは入らない** → §4.5 に表で明記して **0.00**。
3. `steps` 図は**小枠の各行もノード**（「前月の10日前まで」も）→ §4.6 に種別ごとの粒度表を置いて 1.00。

採点側の穴も 2 件：**`nodes[].id` が必須**で、省くと全ノードが 1 件に潰れた（0.29 → 1.00。decisions 120）。
表・図の `page`/`bbox`、辺の `label` が `extra=forbid` で弾かれていた（decisions 121）。

**契約書で特に見たかった 4 点はそのまま採点できた**：甲乙の呼称（紙面の文字どおり）、
頭書（`頭書 1` で citation 1.00）、チェックボックス（`■ 無し` をセルの文字として TEDS 1.00）、
記名押印欄（記名行ごとに 1 要素で bbox 当たり 0.82）。

### 2026-09-28（18）P7-1 完了 — 規則ベースの読み取りで契約の穴を 3 件見つけた

`scripts/baseline_reader.py` を全 41 文書で回し、`keiyaku eval --all --pred-dir` で採点した
（**外部サービスは使わない**。H8 の決定）。**41 文書すべて完走**。詳細は
`docs/validation_plan.md` §2 の「実施の記録」。

**切り分け**（読み取り器の力不足か、契約の穴か）：

- **力不足** 2 件：様式型（条が無い）と約款型（条見出しが条番号の上）で見出しが拾えない。
  → 直さず docstring の限界に追記（素朴さを保つのがこの器の目的）。漢数字の条番号だけは読めるようにした。
- **契約の穴** 3 件：
  1. 読み取り器が語彙に無い `kind: "caption"` を出し、採点側に弾かれていた。
     **表題をどう出すか**が契約に書かれていなかった → 「当てられない種別は `null`」を明記して修正。
  2. **条番号を外すと、列挙を完全に読めていても 0**（`con-0001` は 6 列挙すべて正しいのに coverage 0）。
     指標が測るもの（順番の保持）と突合の鍵（citation）がずれていた → **中身での突合**を追加。
  3. 同じ citation に複数の予測が当たると **coverage が 1 を超えた**（実測 1.67）→ gold 1 件につき 1 回。

2 と 3 は指標の定義を変える判断なので **H6（承認済み）**に当たる。変更前後の平均は
**列挙 0.560 → 0.680、他の指標は不変**（`eval --all --oracle` は全文書・全指標で満点のまま）。
`docs/decisions.md` 119 に記録した。

### 2026-09-28（17）P6 の執筆完了 — `sys-0002` で 10 doctype すべてに 2 本目

`sysdev` の 2 本目（`sys-0002`：倉庫の入出庫システム）。1 本目（信用組合の勘定系・**工程型**）に対し
**反復型（アジャイル）**にしたことで、章の構成そのものが変わった。

| | 1 本目 | 2 本目 |
|---|---|---|
| 進め方 | 要件定義 → 設計 → 実装 → 検収の**工程** | **{const:iteration_weeks} の反復を 12 回**（要求一覧を随時見直す） |
| 章 | 総則／業務の遂行／権利および義務／一般条項 | 総則／反復による開発／成果物および権利／**対価および支払**／一般条項（5 章） |
| 個別契約 | 工程ごと。**みなし承諾あり** | 反復ごと。**みなし承諾を置かない**（諾否がなければ不成立） |
| 検収 | 納入 → 検査 → 検収（flowchart） | 反復レビュー → 受入れの判断（**timeline**）。通知 4 日／みなし受入れ 10 日 |
| 対価 | 工程ごとの見積り | **1 反復あたりの単価**（リリース物を作る反復は加算） |

27 条・様式1・別紙1・mincho 12 ページ / form 8 ページ。目次はページ番号つき（章 → 条の 2 階層）。
`lint --similarity` 警告なし、verify 0/0、QA 45 問・`eval --oracle` 満点、batch **ready 41/41**。

**これで P6 の執筆は完了**：10 doctype × 2 content × 2 style（`lic-0001` のみ 3 style）＝ **41 文書**（＋ `sample_min`）で、
v1 の目標 40–60 文書に到達した。次は P7（規則ベース → 自セッション VLM → 盲検 → v1 タグ）。

### 2026-09-27（16）P6 — `con-0002`（約款型の 2 本目）

`contracting` の 2 本目（`con-0002`：医療法人の診療所の増築工事）。1 本目（町発注の土木工事）との違い：

- 当事者のプリセット（orderer/builder ↔ principal/builder2）で、**呼称が「発注者・受注者」から「甲・乙」**に変わる。
- **民間工事**なので前払・部分払の組み方を変えた（前払 2 割＋部分払 4 回で累計 90 パーセント、
  残りは引渡し後の精算。**留保 4 パーセント**を別に置く）。別紙2 の累計とちょうど噛み合わせてある。
- **診療を続けながらの工事**という条件を全体に効かせた（騒音の時間帯・粉じん・患者情報の保護・部分引渡し）。
  1 本目にない条として「契約の保証」「工事の記録および報告」「安全および近隣への配慮」「秘密および個人情報の保護」。
- 図は 1 本目の `timeline`（工期と支払）に対し **`flowchart`**（出来高検査から部分払まで。差戻しの輪つき）。

執筆中の指摘：`{const:}` の値が表の中の別の値の**部分文字列**になっていて L11 が鳴った
（`5パーセント` ⊂ `25パーセント`、`4回` ⊂ `第4回`）。**定数の値は紙面の他の値と部分一致しない形に選ぶ**
のが実務的（`4パーセント`・`合計4回` に変えた）。

24 条・別紙 2 点・mincho 13 ページ / form 8 ページ。`lint --similarity` 警告なし、verify 0/0、
QA 45 問・`eval --oracle` 満点、batch **ready 38/38**。

### 2026-09-27（15）P6 — `emp-0002`（様式型の 2 本目）

`employment` の 2 本目（`emp-0002`：介護の事業所の短時間勤務）。1 本目（製菓工場・**有期・月給**）に対し
**無期・時間給・交替制**にし、様式の項目の並びも変えた（用語 → 期間 → 場所と業務 → 勤務の時間 → 休日 →
賃金 → 退職 → 保険 → 窓口）。表は 4 点（用語・期間・勤務の別と時間帯・賃金 14 行）、図は勤務表の組み方（`steps`）。

- **mincho で WeasyPrint の帯に入った**ので、`docs/gotchas.md` の手順どおり本文を 1 項ぶん足して抜けた
  （レイアウトを自動でずらす回避はしない）。form は初回から通った。
- **`keiyaku qa` を batch より前に走らせる手順に戻した**。`qa_auth_002` の答え（「締切は毎月15日、
  支払の日は翌月5日」）が **evidence 1 セルの平文に含まれず L14 で落ちた**——lint は通っていた。
  L14 は `source` と `layout` が要るので lint では見られない。**文書ごとに `keiyaku qa` を挟む**のが正しい。

`lint --similarity` 警告なし、verify 0/0、QA 45 問・`eval --oracle` 満点、batch **ready 36/36**。

### 2026-09-27（14）HITL の決定 7 件を受け取り、計画へ反映した

利用者が `HITL_TODO.md` の H1〜H4・H6〜H8 に決定を記入した。受け止めと反映：

| # | 決定 | これで変わること |
|---|---|---|
| H1 | **push 可** | v1 の区切りで `contracts/` **だけ**を commit・push する（他ディレクトリの未コミット変更は混ぜない。decisions 117） |
| H2 H3 H4 H7 | **確認済み**（架空性・転載なし・版面・disclaimer） | 17 content 時点への確認として受け取る。**以後の文書にも同じ規約と手順を続ける**（decisions 118） |
| H6 | **承認**（評価定義の変更） | 変えるときは変更前後の `eval --all --oracle` を添えて記録する |
| H8 | **不可**（外部サービスへの送信） | **商用 OCR / VLM API での検証は行わない**。V-C〜V-E はリポジトリとこのセッションの中で完結させる（decisions 116。`docs/validation_plan.md` の当該記述を取り下げ） |

**H5（`apply` の算出値・38 問）だけが未決**。文書を増やす作業はこれに依存しないので進める。
決定で答えが変わったときの波及は `qa_authored.json` → `batch` → `manifest update` → `eval` に閉じる。

### 2026-09-27（13）P6 — `lea-0002` と、宣言・実装の二重定義を 2 件つぶす

`lease` の 2 本目（`lea-0002`：菓子の製造販売の店舗）を書いた。1 本目（事務所・**3 者**）に対し
**2 者**（保証業者なし）とし、頭書の表も「当事者」ではなく**特約事項**（営業の時間・看板・排気・駐車）に
差し替えた。図は 1 本目の `timeline` に対し `steps`（更新の手続きの順序）。18 条・別表 1・10 ページ。

**見つかった穴 3 件**（いずれも宣言と実装、または約款の語の持ち越し）：

- **頭書の中の段落に番号が付いていた**（decisions 113）。`head_matter_levels` に `paragraph` の宣言が
  無く本文の規則に落ちていたため、注記（※ 修繕の費用の負担は別表1による）が「2 ※ …」と採番。
  `lea-0001` も同じ状態だった（1 本目を書いたときは気づけなかった）。
- **L16 が blueprint の `authored_qa` を読んでいなかった**（decisions 114）。契約書は図 2・apply 2 と
  宣言しているのに、lint は実装の定数 3/3/1 で判定していた。**宣言を読むように変え、apply の下限も
  宣言どおり 2 に上がった**（既存 16 content はいずれも影響なし）。
- **`steps` 図の小枠に約款の言い回しが残っていた**（decisions 115）。「お願い」「書類例」は yakkan の語。
  既存の contents は `detail` しか使っていなかったので表に出ず、`asks`・`docs` を初めて使って発覚した。

あわせて `source_is_stale` の対象に `numbering/*.yaml` を足した（番号方式の宣言も build の入力。
直しても「新しい」と判定され、頭書の修正が描画に反映されなかった）。

`lint --similarity` 警告なし、verify 0/0、QA 45 問・`eval --oracle` 満点、batch **ready 34/34**、
`make check` 512 passed。

### 2026-09-27（12）P6 — `pur-0002`（頭書型の 2 本目）

`purchase` の 2 本目（`pur-0002`：食品会社が買う急速凍結設備）を書いた。1 本目（自治体が買う
流量計測装置）との違い：

- 当事者のプリセット（purchaser/vendor ↔ buyer/seller）と、買主が**自治体ではなく株式会社**。
- 頭書の項目を変えた（契約保証金 → **据付工事の完了期限**・**支払の方法**）。
  「契約金額の 1 割を契約不適合責任の期間の満了まで留保する」を頭書に書き、本文と噛み合わせた。
- **売買に据付工事と性能確認試験が付く**型にした。1 本目の「検査 → 引取り」に対し、
  こちらは「据付 → 試験 → 判定 →（不合格なら手直しして再試験）→ 引取り」。
  図も 1 本目の `steps` に対して `flowchart`（差戻しの輪を持つ）に変えている。
- 目録の表は 7 行 5 列（品名・規格・数量・単価・金額）で、合計の行を持つ。

前回入れた**横エッジのラベルの逃がし**がさっそく効いた（「再試験」が箱に重ならず上へ出た）。
版面では記名押印欄が 2 ページに割れていたので、解除の条に 1 項足して両当事者を同じページに収めた
（`.signature { break-inside: avoid }` は WeasyPrint の帯に入るので使えない。`docs/gotchas.md`）。

`lint --similarity` 警告なし、verify 0/0、QA 45 問・`eval --oracle` 満点、batch **ready 32/32**。

### 2026-09-27（11）P6 — `csl-0002` と、flowchart の経路・ラベルの穴

`consulting` の 2 本目（`csl-0002`：石材加工業の事業承継と原価の管理）を書いた。1 本目（食品会社の
仕入と在庫）とは題材・当事者のプリセット（company/advisor ↔ client/consultant）・数値をすべて変え、
**定義を条の号ではなく表に持たせた**（表1＝用語の意味・表2＝報酬の 3 段）。図は更新拒絶の流れ図で、
1 本目の timeline とは種別から変えている。`lint --similarity` 警告なし、verify 0/0、
`eval --oracle` 満点、batch **ready 30/30**。

**目視で見つけた描画の穴 2 件**（どちらも機械化した。`make check` 509 passed）：

- **戻り経路が判断のひし形を真上に貫いていた**（decisions 111）。L 字の経路は横の脚しか当たり判定を
  していなかった。縦の脚も見て、塞がっているときは**相手の行のすぐ手前の隙間**を走らせる。
  隣の行どうしなら座標は従来と同じなので、**既存 31 文書の図はすべて無変化**（実測で確認）。
- **横エッジのラベルが両側の箱に重なっていた**（decisions 112）。列の隙間は 18px しかない。
  収まらない長さなら箱の上へ逃がす。

図そのものも配置を直した（更新後のノードを判断の行から 1 つ上げ、戻り経路を横 1 本にした）。
**線の重なりは lint も verify も見ていない**ので、図を直したら PNG を見ること（`docs/gotchas.md`）。

版面では、報酬の表が 1 行だけ前ページに残る割れ方をしていたので、前の条に 1 項足して表を次ページへ
まとめた。表がページをまたぐこと自体は（見出し行が繰り返されるので）読み取り課題として残してよい。

### 2026-09-27（10）P6 — `dlg-0002` と、図のトークン・build の鮮度の穴

`delegation` の 2 本目（`dlg-0002`：学園の図書室の運営）を書いた。1 本目とは題材・当事者の
プリセット（mandator/mandatary ↔ client/contractor）・条の構成・数値をすべて変えてある。
別紙の表は「費用の項目 × 甲乙 × 備考」（7 行）、図は月次の報告と改善の繰り返し。
`lint --similarity` 警告なし、verify 0/0、QA 45 問・`eval --oracle` 満点、batch **ready 28/28**。

**執筆中に見つけた実装の穴 2 件**（どちらも目視で気づき、機械化した）：

- **図の中に `{party:}` を書くと生のまま SVG に出た**（decisions 109）。図で使ってよいトークンを
  `{ref:} {term:} {const:}` に限っていたが、当事者の呼称は L19 で直書きを禁じているので、
  **図のノードで当事者に触れる手段が無い**状態だった。`{party:}` も値を差し込むだけなので許可に
  加え、L06 を「許可の一覧に無いトークンはすべてエラー」に変えた（次に token を足しても漏れない）。
- **`render` が古い `source.json` をそのまま描いていた**（decisions 110）。図の位置を直して
  render しても版面が変わらず、原因の特定に時間を使った。**実装を直したときも同じ**で、
  `{party:}` を解けるようにした直後に旧 `source.json` が使われた。執筆物と実装の更新時刻を見て
  古ければ黙って build し直す。

**目視で直した版面の不具合**：図を導く項が前ページの末尾に残り、図だけが次ページに送られていた
（図を条の 2 項目に繰り上げて解消）。別紙の「表に掲げない費用は〜」の一文が表と別ページに落ちて
いたので、導入の項に畳み込み、参照も「下表」から `{ref:tbl_cost}`（＝表1）に変えた。

### 2026-09-27（9）P6 — 2 本目（`nda-0002` `ots-0002`）

`PROMPT.md` P3-5「似せない」に従い、**題材・当事者・条構成・数値をすべて変えた**2 本目を書いた。

| | 1 本目 | 2 本目 |
|---|---|---|
| `nda` | 検査装置の共同設計・**相互開示**（partyA/partyB） | 医療機器の稼働記録・**一方向の開示**（discloser/receiver） |
| `outsourcing` | 日用品の保管と出荷の代行・法人どうし | 演奏会の運営・**公益社団法人が委託者** |

- 条の構成も変えた。`nda-0002` は「目的と期間の限定 → 受領情報の範囲 → 取扱い → 複製と保管 →
  従事者の管理 → 返還 → 期間 → 違反した場合の措置」で、1 本目の並びと重ならない。
- **`lint --similarity` は 13 content すべてで警告なし**（同じ doctype の 2 本目でも 30% 未満）。
- `keiyaku batch` は **ready 26/26**。`eval --all --oracle` は全 27 文書で満点のまま。
- **L04 の新しい TODO 検査がさっそく効いた**（`nda-0002` `ots-0002` の scaffold 直後に検出）。
  前回までは `keiyaku batch` まで気づけなかった。

### 2026-09-27（8）P6 — バッチ生成と自己評価

**P6-1：`specs/batch_v1.yaml` と `keiyaku batch`**

- 11 content × 2 style ＝ 22 件。**2 style 目は「版面が最も遠いもの」**の規約どおり
  `ct-a4-1col-form` を組にした（`gothic` は mincho と同系なので外した）。
- 1 回目は **10 件が「TODO が残っている」で落ちた**。`keiyaku lint` は緑だったのに batch だけが
  捕まえた——`_todo` は pydantic の検証で捨てられるので lint からは見えていなかった（decisions 106）。
  `docs/lint_rules.md` は L04 が見ると書いていたので、実装を合わせた。
  **11 content すべての `doc.json` に `_todo` が残っていた**（part 側だけ消していた）。
- **`keiyaku clean --stale` が batch の出力 9 件をその場で消した**（decisions 107）。
  `--stale` は manifest ではなく **blueprint の `variants.styles`** を基準にするので、
  宣言が `gothic` のままだと `form` の成果物が「宣言外」として消える。blueprint を揃えた。
- 残った 2 件の `RenderLayoutError` は D-1 どおり probe で帯を測ってから外した：
  - `emp-0001` × mincho：帯 48 字 → 意味のある記載を 1 項足して外れた。
  - `lic-0002` × form：**496 字増減しても抜けられない**＝帯ではなく構造的な相性（decisions 108）。
    `PROMPT.md` P6-1 の「別の style で描く」を採り、`license` だけ `gothic` を組にした。
- 結果：**ready 22/22**、manifest check 一致。

**P6-3：export と自己評価**

- **`dataset/README.md` に保険の語「事故」が焼き込まれていた**（decisions 105）。
  件数は実測していたが、打ち切られたクエリの**例だけ**が固定文字列だった。
  `PROMPT.md` P6-3 が「固定文字列が焼き込まれていないか」を確かめよと書いているとおりの不具合で、
  実測から出すように直した（いまは「個別契約」と出る）。
- `eval --all --oracle`：**全 23 文書・全指標で満点**。
- `--misread 0.0/0.1/0.3/0.5`：**全指標が単調に悪化**（上の表）。recall 基準で見ている。

### 2026-09-27（7）P5 完了 — 逐条解説（`commentary`）

**probe を先に取った**（`PROMPT.md` P5-2 の指示どおり）

`scripts/probe_commentary.py` で 6 / 20 / 40 / 70 行の解説を描いた結果、
**ページをまたいでも内容欠落もはみ出しも起きなかった**（decisions 100）。
yakkan の「枠つきブロックが割れると続きが版面の外に出る」は **2 段組の話**で、
1 段組の契約書では再現しない。「長い解説は複数ブロックに分ける」方針は必須ではないと確定した。

**配線が途中で止まっていた**

HTML の描画と L21 はあったが、次がすべて未実装だった（decisions 101）：

| 求められていたこと（`docs/schema.md` §11.3） | 実装前 |
|---|---|
| `region` が `commentary` になる | `body` のまま |
| 検索パッセージが `kind: commentary` の別パッセージ | 本文に混ざる |
| `pages[].text` に含める | region が body なので結果的に入っていた |
| 解説を QA の根拠にできる | `derived.plain_text` に無く**指定できなかった** |

さらに **`iter_texts` が解説の文を歩いていなかった**（decisions 102）。
解説は紙面に描かれるのに、**架空性（L08）・文体（L10）・定数の直書き（L11）が素通り**していた。
decisions 45（`meta` の文字列が L08 から漏れていた）と同じ種類の穴。

**`lic-0002`（商標使用許諾契約書・逐条解説つき）**

- `license` の 2 本目。題材・当事者・条構成・数値をすべて変え、`lic-0001` との類似度は 30% 未満。
- 解説 7 枠・31 行。**条を指す解説と項を指す解説の両方**を使った（L21 を decisions 61 どおりに拡張）。
- 解説を根拠にした QA を 2 問書いた（「解説によれば〜」型）。`plain_text` に入れたことで書けるようになった。

### 2026-09-27（6）P5 — `sysdev` で 10 doctype がそろった

**`sys-0001`（ソフトウェア開発基本契約書・章立て）**

- **章 → 条**の 2 階層で条は全編通し番号。**目次を持つ最初の文書**（26 条・13 ページ）。
  2 パス描画でページ番号が一致し、V04（目次のページ一致）が実際に効いた。
- 個別契約は `kind: appendix`（`kind_label: 様式`）で表せ、**入れ子の契約という機構は要らなかった**
  （`docs/schema.md` §11.4 を確定に変えた）。
- blueprint の skeleton に前文を入れ忘れ、L04 が「node/preamble が 0/1 件」で捕まえた。
  **宣言と required の食い違いを lint が拾う**ことの確認になった。

**目次まわりで 2 件直した**

- **ラベルも見出しも持たない節点が目次に入っていた**（decisions 97）。前文がリーダー罫とページ番号だけの
  空行として目次の先頭に出た。`docs/schema.md` §8 は outline についてそう定めていたのに、
  `build_toc` に同じ判定が無かった。
- **テンプレートに「もくじ」が直書きされていた**（decisions 98）。保険約款はそれでよいが契約書は「目次」。
  `Style.toc_heading` の宣言に追い出した。

### 2026-09-27（5）P5 — 様式型（`employment`）と約款型（`contracting`）

**P5 の前提を先に片付けた**

- **L20 を blueprint の `signature` 宣言に従わせた**（decisions 92。65 の実装）。
  様式型は記名押印欄を持たないので、いままではどう書いても error だった。
- **scaffold も宣言に従うようにした**（decisions 95）。雛形が規則に反するものを出していた。

**probe：選択欄の記号**（`scripts/probe_checkbox.py`）

| 記号 | L07 | 埋め込みフォント |
|---|---|---|
| `☑` / `□` | **warn**（本文フォントに無い） | 記号フォントが 1 本増える |
| `■` / `□` | 指摘なし | 本文フォントだけ |
| `〇` / `－` | 指摘なし | 本文フォントだけ |

`☑`（U+2611）は `Noto Sans Symbols 2` にしか無い。描画自体は通る（V02／V03／V08 は指摘なし）が、
L07 が warn を出す。**P1 の実測では実物の様式は `☑` を使わない**ので、`■` / `□` を採った（decisions 91）。

**`emp-0001`（労働条件通知書・様式型）**

- 条を 1 つも持たず、`1` → `(1)` → `①` → `ｱ` の 4 階層。記名押印欄なし。4 / 5 ページ。
- 見出しが「（1）（用語）」と**括弧が二重**になったので `article_heading: plain` にした（実物は「(1)　用語」）。
- **V-P3（目次検査のスキップを明記）が実装されていなかった**（decisions 96）。
  仕様は「黙って通さない」と定めているのに黙って返っていた。`info` 重大度を足して実装した。

**`con-0001`（工事請負契約約款・約款型）**

- **`kanji` カウンタを実装**（decisions 94）。`COUNTERS` から除外されていたので宣言に書けなかった。
  「第一条」「第二十条」「第二百三十三条」を法令の流儀で出す。17 件のテストで固定。
- 章を持たない 27 条・13 ページ。条見出しは条の上（`article_heading: above`）。
- **条見出しに `{party:}` を書けないことが分かった**（decisions 93）。`node.title` は RichText ではないので、
  呼称が役割名（「発注者」）だと「（発注者の解除権）」が必ず L19 に当たる。
  alias を甲乙にし、役割名は `role_label` で持つ形に落とした。

**HITL へ回したもの**：`apply` 4 問（`HITL_TODO.md` H5-8・H5-9）。

### 2026-09-27（4）P4 完了 — `license`、記法サンプル、skip の解消

**`lic-0001`（特許実施許諾）**：条文型＋別表 2 点（対象権利・実施料の料率）。8 / 7 ページ。
料率は**売上区分 × 料率の階層表**（CT9）で、`apply` QA が区分ごとの按分計算になる。

- **検算で執筆 QA の答えの誤りを自分で見つけた**：正味販売価格 1 億 2000 万円のランニング実施料を
  「640 万円」と書いていたが、区分ごとに分けて計算すると 200 ＋ 150 ＋ 40 ＝ **390 万円**。
  L14 は包含しか見ないので**機械では落ちない**（`PROMPT.md` P6-2 の検算が効いた例）。
- **L11 が日付の一部を期間と誤検出していた**（decisions 88）。「２０２７年６月２１日」の「２１日」が
  定数の「２１日」に当たっていた。素の部分一致だったのを、日付の境界を見る形に直した。

**`docs/schema.md` §5.10（記法サンプル）**（decisions 89）

- 保険の語彙を期待したまま **7 件の skip が 1 年近く残る形**になっていた。
  契約書の記法（`{party:}` を含む 6 種）を 1 条に収めた見本を書き、テストの期待も差し替えた。

**skip が 0 になった**

- `keiyaku export` を回して検索評価セット（パッセージ 220・クエリ 403・qrels 1010）を作り、
  残り 8 件の skip も解消した。`eval --all --oracle` は**全 15 文書で満点**。
- 打ち切りの印の検査だけは、**コーパスが上限に届くまで起きない**ので条件付きに緩めた（decisions 90）。

**HITL へ回したもの**：`apply` 2 問（`HITL_TODO.md` H5-7）。

### 2026-09-27（3）P4 — 頭書の設計確定と `purchase` `lease`

**P4-1：頭書（`head_matter`）の設計を probe で確定**

`scripts/probe_head_matter.py` を新しく書き、A4 1 段での挙動を実測した：

| 測ったもの | 結果 | 対応 |
|---|---|---|
| 繰返し表頭 | 2 ページ目にも出て、**2 回目以降に `repeated: true`** が付く | そのまま使える |
| 列数 | **15 列までは収まり、16 列ではみ出す** | 実物の最大は 14 列なので A4 縦で足りる |
| rowspan のページ跨ぎ | **継続ページのその列が空欄になる** | **verify V11 を新設**して落とす |

- 仕様（`docs/schema.md` §11.1）に「`{ref:head}` →「頭書」と解決する」と**書いてあっただけ**で、
  `numbering.py` には分岐が無く**空文字に解決されていた**（decisions 84）。実装した。
- 頭書の中の号は、実物では**括弧なしの算用数字**。`in_appendix`（真偽値）を
  `scope`（body / appendix / head_matter）に一般化し、`head_matter_levels` を宣言できるようにした
  （decisions 85）。**Python に分岐を書かず宣言で切り替える**原則どおり。

**P4-2：`pur-0001`（物品購入・頭書＝項目の羅列）と `lea-0001`（建物賃貸借・頭書＝表の連なり）**

- 頭書の 2 つの型が、どちらも `kind: head_matter` の**中身の違い**で表せることを実装で確認した。
- **3 者契約（CT15）を初めて通した**。`meta.parties` 3 件・当事者表示 3 行・記名欄 3 ブロックが
  既存の機構のまま動き、L19／L20 も通った（decisions 87）。
- 目視で直したもの：目録表の金額列が狭く数値が折り返していた（単位列を数量に畳んで解消）。

**HITL へ回したもの**：`apply` 4 問（`HITL_TODO.md` H5-5・H5-6）。

### 2026-09-27（2）P3 完了 — `delegation` と `consulting` を 1 本ずつ

**成果**：`dlg-0001`（準委任・7/6 ページ）と `csl-0001`（顧問・6/5 ページ）。
条文型 4 doctype がそろい、**P3 の DoD（4 文書が lint/verify/review を通り manifest に ready）を満たした**。

**途中で直したもの**
- **号の下の説明段落が版面の左端まで戻っていた**（decisions 75）。HTML は親子を**兄弟として**並べるので、
  CSS の子孫セレクタでは深さを表せない。`_under_class()` で親の字下げを引き継ぐクラスを付けた。
- **同じ条の 2 つ目の列挙が `(7)` から始まった**（decisions 78）→ **L23 を新設**。
  号を導入文の `children` に移せば numbering が親ごとに数え直す。**目視でだけ**見つかった。
- **`RenderLayoutError` の帯を 3 回連続で踏んだ**。D-1 どおり probe を取ったら、
  **帯の幅は style ごとに違う**（mincho 32 字 / gothic 96 字）と分かった（decisions 77）。
  yakkan の 2 段組で測った 48 字をそのまま当てていたのが間違い。
- **記名押印欄が甲と乙でページに割れた**。`.signature` に `break-inside: avoid` を入れたが、
  **帯を安定して踏む**ので撤回した（decisions 76）。当事者ブロック単位の avoid は効く。
- **eval のテストが痩せたデータセットを掴んでいた**（decisions 80）。表と図がいちばん多い文書を選ぶようにした。
  合わせて `degrade` が 1 つも落とさないことがある問題も直した（decisions 79）。

**HITL へ回したもの**：`apply` 4 問の算出値（`HITL_TODO.md` H5-3・H5-4）。

### 2026-09-27 P1（構造分析）完了、P3-1/P3-2 で `outsourcing` を 1 本

**P1：`samples/` 39 ファイルの構造分析**（コード変更なし）

- `scripts/analyze_reference_pdf.py` が本文を出力しないことをコードで確認してから全 39 件を計測
  （生ログは `scratch/p1/`。リポジトリには入れない）。10 カテゴリ各 2〜3 件を目視。
- `docs/reference_structures.md` §4 に分析ログ 10 本、§4.1 に**§2 との食い違い 5 点**、
  §3 に CT カタログの確定版（CT1〜CT16 の検証＋CT17〜CT25 の新設）を書いた。
- **食い違い**：purchase の A3 は**縦ではなく横**／文体は全 doctype 常体ではなく**敬体の実物が 5 件**／
  contracting の約款型は**章を持たない**（章立ては sysdev だけ）／**契約書本体の図は 39 件中 0 件**
  （図は逐条解説側にしか出ない）／`delegation_01` と `sysdev_01` は同一ファイル。
- **再現対象から外した**：右余白の注釈帯（CT17）／同一条番号の A 案 B 案併記（CT25）／縦書きラベル。
- schema・lint への提案 4 件を起票（`docs/decisions.md` 60〜63・65）。**P1 ではコードを変えない**。

**P3-1：残り 3 doctype の blueprint**（`outsourcing` `delegation` `consulting`）

- P1 の実測を反映：本文に表を置かず別紙へ寄せる／図は最小限／`consulting` だけは本文に報酬表を持つ。
- `Requirement.min_items` が**モデルに無い**のに docs の例が使っていたので実装（decisions 67）。

**P3-2：`ots-0001`（業務委託契約書）を 1 本**

- 15 part・13 条＋定義条・別紙 2 点・表 2・図 1・脚注 1・参照 30 超。mincho 8 ページ / gothic 7 ページ。
- 途中で直したもの：
  - **`NodeKind` の `schedule` が死んでいた**（採番されずラベルが空。decisions 66）→ `appendix` に一本化。
  - **脚注が参照より前に描かれた** → content を直し、**L02 に配置検査**（decisions 71）。
  - **flowchart の差戻し経路が他のノードの箱を貫通**（目視のみで発覚）→ 描画を修正（decisions 70）。
  - **別紙に「第1」だけの空見出し** → `skip_when_single`（decisions 69）。
  - **後文・記名押印欄が別紙のあとに出ていた** → 実物を見て順序を反転（decisions 68）。
  - **定義文が紙面に出ない**（2 度目）→ 定義条を足し、**L12 に在処の検査**（decisions 72）。
    この検査が nda-0001 の `confidential` の**正解データと紙面の食い違い**も掘り出した。
  - `RenderLayoutError` の帯に 1 回入り、D-1 どおり**内容を足して**外した（検査の基準を定める項）。
  - **`id(draft)` をキーにしたキャッシュが別文書の表を引いていた**（decisions 74）。
    テストを足して初めて再現した。`keiyaku batch`（複数文書を 1 プロセス）では必ず踏む種類の不具合。

### 2026-09-26（4）P3-2 `nda-0001` を 1 本通した

`PROMPT.md` §5 の P3-2 を完走。受け入れ条件（verify error 0 / warn 0・manifest に ready・目視で崩れ無し）を満たした。

**成果**
- 14 part・10 条・表 4・図 1・脚注 1・参照 21・3,523 字。3 style で 5 / 4 / 3 ページ。
- 執筆 QA 15 問（表 4・図 3・apply 2・definition 1・extract 2・crossref 1・count 1・negative 1）。
- `chars_per_page_estimate` を実測から較正（mincho 802 / gothic 1030 / form 1439）。

**途中で直したもの（blueprint / style / docs / コードに跳ね返ったもの）**
- **`{party:}` がインライン描画に配線されていなかった**。verify V03 が「期待テキストが PDF から読めない」11 件で
  露呈。`render/inline.py` に `Party` の分岐と `InlineContext.resolve_party` を足した。
- **入れ子 `LineBox` の二重取り**（`inline-block` の押印欄で「印」が box ツリーに 2 回出る）。
  `layout/extract.py` に `in_line` フラグ。
- **L08 が `meta.parties[].name` を見ていなかった**（`docs/decisions.md` 45）。
- **L04 が `node` / `enumeration` / `ref` を黙って通していた**（同 52）。
- **`FRONT_MATTER_PAGES = 3.0`（保険の表紙＋目次）が較正を天井に張り付かせていた**。
  表紙・目次の有無から計算する形に変えた（`lint/budget.py`）。
- **図の配置が `docs/style_guide.md` §4 に違反していた**（`article` 直下 → 第1項より前に描画）。
  自分の content と golden サンプルの**両方**が破っていたので **L22 を新設**（同 56）。
- **定義語 `term_staff` の根拠が紙面に無かった**（L14 が検出）。定義条（第2条）と用語表を足した。
  用語列が 4 字で折り返していたので `col_widths` を指定。
- **目視でしか見つからなかったもの 2 件**：timeline の連結線が span ラベルを貫いていた（描画順を変更）／
  収入印紙欄が実物の 1.5 倍（`box-sizing` 未指定で padding が高さに加算）。
  **verify も lint も通ったまま**だったので、CLAUDE.md §0.4-7（目視必須）の裏付けになる。
- **eval のテストが保険の版面を焼き込んでいた** 2 件（同 58・59）。

**HITL へ回したもの**：`apply` 2 問の算出値（`HITL_TODO.md` H5-1）。

### 2026-09-26（2）P0 移植を完了

- `uv init` 相当（`pyproject.toml`・`.python-version`・`Makefile`）。依存は yakkan から版ごと写した
  （**weasyprint==70.0 固定**）。`uv.lock` は写さず本プロジェクトで解決（`docs/decisions.md` 29）。
- `../insurance-contracts/yakkan/` → `keiyaku/` をコピーし、**88 ファイル・411 箇所**の `yakkan` を
  `keiyaku` にリネーム。ロジックは変更なし。`tests/`（44 件）・`scripts/`（18 件）・`.claude/`・
  `assets/`（フォント 8 本＋ライセンス）も移植。
- `scripts/vlm_reading/`（保険 3 文書の VLM 予測実例）を削除（`docs/decisions.md` 28）。
- `keiyaku schema export` で `schema/*.schema.json` 11 件を生成。
- **保険資産に依存する 6 テストモジュールにデータ駆動のスキップガードを入れた**
  （`docs/decisions.md` 27）。CSS テンプレートの探索元がモジュール定数のため、fixture ディレクトリへ
  逃がすにはコード変更が要り、P0 の「挙動不変」に反すると判断した。
- ruff の指摘 1 件（import 順）はリネームの機械的帰結（`keiyaku` が `scripts` より前に来る）なので修正。
- **P0-4 の同一性検証**：yakkan と smoke を突き合わせ、テキスト層・fragments 122 件・PNG・
  **PDF のバイトまで一致**。`pdffonts` で CFF 0 本を確認。依存の版差（pytest 9 / ruff 0.16）は
  生成物に影響しないことを実測で確認した（`docs/decisions.md` 29 の裏付け）。
- `.gitignore` を実測検証：`content/**/parts/` は追跡可（親の `parts/` を打ち消せている）、
  `samples/*.pdf` は除外、`samples/SOURCES.md` は追跡可、`scratch/` は除外。追跡候補 189 ファイル。
- `.claude/` を契約書向けに適応：`agents/author.md` と `reviewer.md` を `PROMPT.md` §11 の契約書版に
  差し替え、`render-debugger.md` は基底 gotchas への参照を追加。`commands/`・`rules/` も適応。
- **棚卸し表を実測で確定**（`docs/architecture.md` §5）。予想と食い違ったのは 3 件
  （`styles.py` は改造不要だった／`export.py`・`search_set.py` は予想より重い／
  `render/html.py` に `CSS_DIR` の制約を発見）。

### 2026-09-26 プロジェクト発足
- `../structured-docs/`（docsynth。CLAUDE.md ＋ docs 14 本）と `../insurance-contracts/`（yakkan-synth。
  実装完済）を読み込み、契約書専用プロジェクトとして `contracts/` を起こした。
- 利用者の選択：**コード基盤は yakkan をコピーして特化**／**v1 スコープは 10 doctype 全部**／
  **CLI 名は `keiyaku`**（`docs/decisions.md` 2026-09-26 の 1〜3）。
- `samples/` 39 ファイルの判型とページ数を `pdfinfo` で実測し、
  「A4 縦がほぼ全数（39 中 38）」「ページ数は 3〜9 と 20 超の二峰性」「骨格は 5 類型」を
  設計の出発点にした（`docs/reference_structures.md` §2）。
- `CLAUDE.md`・`README.md`・`docs/` 13 本・`HITL_TODO.md`・`.gitignore` を執筆。
  初期決定 26 件と未決 5 件を `docs/decisions.md` に記録。
- yakkan から継承した「実害から確定した規約」を最初から仕様に入れた：`.ttf` フォント／
  目次リーダー罫（`leader('.')` 禁止）／2 パス目次／表題は `<table>` の `<caption>`／
  `string(chapter, first)`／内容欠落検出／`chars_per_page_estimate` は実コーパス較正／
  「レンダリング成功≠内容が全部載った」。

### 2026-10-04 計画と判断の台帳を分離（`TASK.md` 新設・`HITL_TODO.md` 2.0 版）

残作業が本体・`contracts-calculation`・`HITL_TODO.md` の 3 か所に分散し、どれが最新か分からなくなっていた
（`CURRENT_STATUS.md` は H5 を「未決」と書いたまま古くなっていた）。役割を分けた。

- **`TASK.md`（新設）**＝ `contracts/` 全体（本体＋サブプロジェクト）の**計画・作業の順序・状態・完了条件**。
  現状の実測、残作業（人間の決定待ち T1〜T4／決定不要 T5〜T7／保留 T8〜T11）、依存関係、
  横断の品質保証、リスク R1〜R7、進捗ログを 1 枚に統合した。
- **`HITL_TODO.md`（2.0 版）**＝ **人間の意思決定の依頼・記録・管理**に専念。
  各項目に〈背景／いまの状態／判断してほしいこと／判断材料／AI の推奨／止まるもの〉を添える形にした。

**H5 を決定済みとして記録した。** 2026-10-04 にユーザーが「読み幅あり 15 問の読みを承認」と決定しており
（`contracts-calculation` のセッション）、親側の記入だけが残っていた（サブの HP-1）。
`HITL_TODO.md` §3 → `docs/validation_plan.md` §5 → `docs/decisions.md` 132 の順に反映した。
**計算は 47 問全問一致（不一致 0）だったため `qa_authored.json` の修正は発生していない。**
これで `docs/plan.md` P7 の DoD「`HITL_TODO.md` の全項目に人間の決定」が満たされた。

**新しい判断を 4 件起票した**（いずれも範囲・実施者の決めごとで、AI が決めるべきでないもの）。

| # | 件名 | なぜ人間か |
|---|---|---|
| **H9** | v1 の区切りの付け方（コミット・タグ） | **H1（2026-09-27「push 可・AI が実施」）とサブの HC-1（2026-10-04「Git 操作は全て人間」）が食い違う。** `contracts/` は発足以来丸ごと未追跡（追跡候補 816 ファイル・`assets/` のフォント 60MB を含む）で、どちらを適用するかで実施者が変わる |
| **H10** | P8 をどこまでやるか | 範囲の決めごと。`ct-a3-landscape-form` は**実装済みだが使う文書が 0**、doctype 追加は用途次第、docsynth 切り出しは先方の進捗が前提 |
| **H11** | 遅延損害金条項 10 件の明示性を直すか | 直すと本体 10 content の文言変更・再描画・サブの binding に波及する。サブ側の「記録つき除外を維持」は**サブの扱い**の決定で、本体の文言を直すかは未決だった |
| **H12** | `tests/golden/numbering_legacy.json`（616KB）の去就 | 保険方式の宣言を将来も再現するかに依存する |

**実測で確かめたこと**（2026-10-04）：本体 pytest **521 passed**・`manifest check` 一致（41/41 ready・275 ページ・
QA 1,845 問）、サブ pytest **223 passed**。`CURRENT_STATUS.md`・`docs/plan.md`・`CLAUDE.md` §0.2・§0.3 と、
サブの `TASK.md` §2.3・`HITL.md` HP-1 を実態に合わせた。

## 2026-10-04（続き）H11「遅延損害金条項の明示性を直す」の実施

**ユーザー決定＝直す。** 遅延損害金・遅延利息の 10 条項は、年あたり日数（日割の分母）と端数処理が
書かれておらず、円単位で一義に計算できなかった（サブの `lint-base` が 2026-10-03 に検出）。

- `meta.constants` に **`year_days`**（`365日` 7 件／`360日` 3 件。digit_style に合わせて全角・半角）を足し、
  各条項に「年{const:year_days}の日割り…」「円未満の端数は切り捨てる」を 1 文追記した。
  文末の言い回しは 10 件とも変えてある（`lint --similarity` 緑）。
- 率を**直書き**していた 4 件（`lic-0001` `lic-0002` `ots-0001` `ots-0002`）を `{const:late_rate}` に定数化した。
  副産物として `ots-0002` の「年3パーセント」（半角）が `digit_style: fullwidth` と食い違っていたのが直った。
- 影響した 10 content → `dataset/` **21 文書**を再 build・render・verify・qa して再生成。
  **ページ数の増減は無し**。lint 0/0・verify 0/0・qa 0/0、`eval --all --oracle` 全指標満点、
  `manifest check` 41/41 一致。該当ページは目視でも確認した（H4 の約束）。
- サブ側（`contracts-calculation`）は本体の改稿を受けて再照合し、`late_interest.simple` が **8 件 include**
  になった（全体は include 26・exclude 3）。`TASK.md` T11（サブ TR7）はこれで解けた。

**残った欠落（H11 の範囲外）**：`con-0001` `con-0002` の 2 件は「遅延の日数に応じ」としか書いておらず、
**起算日と終算日**が明示されていない。分母・端数は足したが一義には計算できないままで、サブ側は
この 2 件を記録つきで除外している。直すかどうかは H11 の決定（分母・端数）に含まれないので、
必要なら別途の判断とする。

**既知の未修正（H11 と無関係・先行して存在）**：
- `ruff format --check` / `ruff check` が `contracts-calculation/examples/*/calc/programs/*.py`（生成物）と
  `tests/test_bindings.py` で落ちる（5 件）。そのため `make check` は赤。本体 `pytest` は 521 passed。
- サブの pytest は**実行順・生成物ディレクトリの残りに依存して結果が変わる**（同じ木で 3 回動かすと
  3 failed → 225 passed → 4 failed）。`test_h5.py` が `nda-0001:qa_auth_009` の逐語照合で落ちることがある。
  いずれも H11 の変更前から再現する。

## 2026-10-04（続き）データカード `dataset/data-card.md` の新設と自動更新（TASK.md T12）

データセットの素性を 1 枚で示すものが無かった。`dataset/README.md` は**ファイルの読み方**であって
成分表示ではなく、「規模・内訳・どう作ったか・品質保証・制限と偏り・ライセンス」を読む場所が無い。
**手で書けば必ず古くなる**——実際に `TASK.md` §1.2 の検索評価セットの数は古くなっていた
（クエリ 778 と書いてあったが実測 1,170・qrels 1,884 → 2,858・パッセージ 448 → 692）。
そこで**生成物**にした。

- 仕様 `docs/data_card.md`（節ごとに「数値の出所」を表で縛る。出所の無い数値を書かない）。
- 実装 `keiyaku/datacard.py`：`collect()` が `dataset/` の実ファイルだけを測り、`render_card()` が
  Markdown を組み立て、`check()` が**書き換えずに**古さを報告する（`manifest check` と同じ流儀）。
- CLI `keiyaku datacard [update|check]`。`keiyaku export` の最後にも書き出す。
- **3 重の自動更新**：`export`（既存の流れ）／`make batch`（`batch` → `manifest update` →
  **`export`** → `datacard check`）／**`make check` に `datacard-check`**（忘れたら赤くなる）。
  ついでに `make batch` に `keiyaku export` を足した——**バッチで文書を足しても検索評価セットが
  更新されない穴**があった。

**カードが自分で挙げるもの**（散文で書くと文書を足したときに嘘になるため）

| 自動検出 | 現行コーパスでの結果 |
|---|---|
| 母数の小さい観点（content が 3 本未満） | **27 件**。逐条解説 1・当事者 3 者以上 1・`margin_note` 枠 1・目次 2・脚注 2・表の意味種別 5 種・図 `tree` 1・宣言 16 件 |
| 宣言はあるが使用 0 の観点 | **5 件**。`history` `plan_matrix`（表）・`annotated_mock` `matrix`（図）・`ct-a3-landscape-form`（style） |
| 検索コーパスに入っていない content | 0 件（入っていなければ content を名指しして警告行を出す） |

**実測で確かめたこと**

1. **独立計算との突合**（**`scripts/verify_data_card.py`**。pydantic を通さず json を生で読む別経路。
   `datacard check` が「生成器を回し直して同じか（鮮度）」を見るのに対し、こちらは
   「**測り方が正しいか**」を見る）。スカラ **31 項目** ＋ 分布 **11 種**（意味種別・図種別・
   ノード種別・ブロック種別・QA 3 種・region・呼称・番号方式・**埋め込みフォント**）＋
   style ごとのフォント 3 件 ＋ **文書の全件 41 行**が、すべてカードの記載と一致した。
2. **足したら追従する**（D8）。`dataset/` の写しから 1 文書を外して 40 文書のカードを作り、
   その文書を**戻した**ところ、`datacard check` が「古い（8 件）」と行番号つきで報告して終了コード 1、
   `datacard update` で 40 → 41 文書・268 → 275 ページ・1,800 → 1,845 問に追従した。
3. **決定論**。2 回書き出してバイト一致。`data-card.md` 自身を容量集計から外してあるので
   鮮度検査が収束する（外さないと書き出すたびに数が動く）。
4. `keiyaku export` 再実行で `search/*.jsonl` と `README.md` は**不変**（md5 一致）。
5. pytest **532 passed**（新規 11 本）・`manifest check` 一致・`eval --all --oracle` 全指標満点（CER 0.000）。

**レビューで自分の間違いを 2 件直した**（どちらもカードを書いて初めて見えたもの）。

| 直したもの | 中身 |
|---|---|
| **フォントは「候補」ではなく「実測」を載せる** | `layout.renderer.fonts` を「使ったフォント」として載せていたが、これは**描画に登録した候補**の一覧だった。PDF を実測すると入っているのは **Noto Sans JP / Noto Serif JP の 4 種だけ**で、同梱してある **IPAex は 1 文書にも埋め込まれていない**。§4.2 に style ごとの実測、§6 に「実測」と「登録した候補」を並べ、**§12 のライセンスの記述も実測から書く**ようにした（IPA フォントライセンスは現行コーパスの PDF には関わらない）。`HITL_TODO.md` H13 の判断材料も直した |
| **条文型と様式型はノード種別では分かれない** | 「`kind: "article"` を持つか」で分類したところ「**全 20 content が条文型**」という誤った表が出た。様式型（労働条件通知書）も `article` ノードを使い、番号方式が「（１）」と振るだけである。**条ラベルの形**（`第◯条` か）で見るよう直し、条文型 18・様式型 2 になった（`docs/doctypes.md` と一致）。回帰テストを 1 本足した |

**現行カードの要点**（2026-10-04 実測）：41 文書 ready / 41・20 content・10 doctype・3 style・
275 ページ・本文 218,600 字・紙面 249,596 字・表 104（セル 2,145）・図 45（ノード 366・辺 386・経路 78）・
参照 1,564・列挙 172（項目 755）・定義語 215・定数 526・当事者呼称 4,131・QA 1,845・
`elements.jsonl` 16,838 行・152.0 MiB / 608 ファイル。

**人間の判断を 1 件起票した**：**H13 データセットの配布条件（ライセンス）**。`pyproject.toml` の
`Proprietary` は**コードの宣言**で、生成物（PDF・JSON・PNG）の再配布条件ではない。カードは
「未決。決定が入るまで外部配布しない」と書いて出る。**PDF にはフォントが埋め込まれている**
（IPA フォントライセンス v1.0・SIL OFL）ので、配布を決めるときは PDF と JSON／PNG を分けて考える。

**既知の未修正（本件と無関係・先行して存在）**：`ruff format --check` / `ruff check` が
`contracts-calculation/` の生成物（`examples/*/calc/programs/*.py`）とサブの `scripts/`・`tests/` で
落ちるため `make check` は赤のまま。**本体（`keiyaku/` `tests/` `scripts/`）は 115 ファイル全緑**。

## 2026-10-05 全 50 契約本文を再レビューし、矛盾・日本語・架空名称を修正した

`content/` の 50 本（`dataset/` 100 文書の単一ソース）を、条文間の参照、期間・金額・所有権・
返還／保管、署名部、当事者・商品名の観点で再読した。自動 lint が見落としていた問題を 20 content で修正し、
39 style を batch で再生成した。主な修正は、遅延損害金式、最低実施料の日割り、試用期間中の時給算定、
週所定労働時間、委託物の所有権と危険負担、個人情報消去と素材保管、返還・廃棄、手付金を含む返金、
許認可条項、鍵返却の重複、作成通数である。

実在名称の確認では、全当事者名・署名者名を完全一致で検索し、実在する会社・団体との一致は見つからなかった。
商標候補の「ユキノハラ」は実在商品の名称と一致したため、「雪綴菓」「ユキツヅリ」「雪綴農園の図形」
「ゆきつづり」へ置換した。健康保険の交付物は、現行制度に合わせて「資格情報のお知らせ、資格確認書その他」へ改めた。

再発防止として、署名を要する文書で `meta.copies` と当事者数が異なる場合を L20 error にし、単体テストと
authoring checklist を追加した。全 50 content の `lint --similarity` は error 0・warn 0、全 39 style の
verify/QA は各 45 問で error 0、manifest は 100/100 一致、datacard は current、検索 export は
passage 1,691・query 2,664・qrels 6,584、`eval --all --oracle` は 100 文書すべて全指標満点だった。
本体テストは 533 passed、計算サブプロジェクトの関連テストは 21 passed。修正箇所 55 ページを目視し、
文字切れ・表崩れ・条文欠落がないことを確認した。

## 2026-10-05 データセットを 100 文書へ拡張した（P8・H10）

**ユーザー指示**「`dataset/` の件数が 100 件になるまで生成せよ」を受け、**H10（P8 の範囲）の決定**として
データセットを **41 → 100 文書**に増やした。採った方針は `docs/decisions.md` 143〜146。

**同じ content を 3 style・4 style で描いて数を稼ぐ案は採らなかった。**
`docs/doctypes.md` §7 が「同系の style を重ねてもレイアウト頑健性の検証にならない」と決めており、
題材・当事者・条構成・数値の多様性（`docs/style_guide.md` §4）も増えないため。
代わりに **content を 30 本書き足し**（各 doctype を 2 本 → 5 本に）、1 content を 1〜2 style で描いた。
30 content × 2 style － 1（`lic-0005` は逐条解説のため mincho 単独）＝ **59 文書**を追加。

ついでに、データカードが挙げていた**偏りを 2 つ閉じた**（`docs/decisions.md` 138 の自己申告）：

- **`ct-a3-landscape-form` を使う文書が 0** → `pur-0004` の 2 style 目に採用（A4 縦 6 ページ → **A3 横 2 ページ**。
  1 枚目は左面が頭書・第1〜2条・目録、右面が第3〜4条と流れ図、2 枚目は左面が第5〜7条、右面が第8〜10条と
  記名押印欄という並びになり、実物の「1 枚を左右 2 面に使う」構えが出た。全ページを目視で確かめた）。
- **逐条解説が `lic-0002` の 1 本だけ** → `lic-0005`（商標の使用許諾）に `commentary` を 7 か所置いて 2 本にした。
  解説枠は**条の最後の項に付ける**（条ノードの `blocks` に置くと第1項より前に描かれる。`lic-0002` と同じ形）。

**実測（2026-10-05）**：`manifest check` **100/100 一致**／`eval --all --oracle` **100 文書 × 18 指標すべて満点**
（CER 0.000）／全 50 content が `lint --similarity` 込みで **error 0・warn 0**／全 100 文書が verify・qa とも
**error 0**／657 ページ・本文 525,876 字・表 247（セル 4,896）・図 104（ノード 933・辺 994・経路 165）・
QA 4,500・検索クエリ 2,664・qrels 6,562・パッセージ 1,691・`elements.jsonl` 42,795 行・369.9 MiB / 1,462 ファイル。

### 書いていて踏んだこと（次に書く人へ）

- **L09（字数の下限）が最後まで残る。** トークン（`{party:}` `{term:}`）は解決後の短い文字列で数えるので、
  JSON の見かけの長さの半分ほどにしかならない。**条を足すより項を足すほうが早い**。
- **定数どうしの「部分文字列」衝突**（L11）が頻発する。`４５日` は `５日` を含み、`１１０日` は `１０日` を含む。
  値を決める時点で**互いに部分文字列にならないか**を確かめる（`docs/style_guide.md` §2 の警告のとおり）。
- **`caption_numbering: chapter`（sysdev）では、章の外にある表を `{ref:tbl_*}` で指せない。**
  別紙の中の表は `{ref:sch1}`（別紙そのもの）で指す。
- **L03 は「特許第9870001号」のような架空の登録番号も番号ラベルとして弾く。**
  `lic-0001` と同じく**整理番号**（`ST-P-01`）の列にするのが通る形。
- **様式型の記入欄を空（全角空白）のままにしない。** 自動 QA が拾って「answer が空」で落ちる
  （`docs/style_guide.md` §3.4 が既に求めていた）。記入例を入れた。
- **WeasyPrint の「帯」は相変わらず出る。** 字数の増減で抜けないときは、**別紙に 1 項足して版面をずらす**と抜けた
  （`dlg-0003` `sys-0003` `sys-0004`）。
- **L15（文単位 30%）は 12 文字 n-gram の Jaccard。** 一般条項を書き写すと同じ doctype の 2 本目で必ず鳴る。
  **doctype ごとに言い回しを 3 通り用意する**（「〜する」「〜するものとする」「〜しなければならない」＋語彙の差し替え）。

**人間の判断を 1 件起票した**：**H14 拡張で増えた `apply` QA 60 問の算出値**。H5 と同じく機械では落ちない
（L14 の包含検査にも `eval` にも引っかからない）ので、H5 で承認された 3 つの読み（応当日・「前まで」は当日含む・
「以内」は翌日起算）をそのまま適用してよいかを仰ぐ。

**テストを 1 か所直した**（`docs/decisions.md` 146）：`tests/unit/test_eval.py` が指標を試す題材を
「表＋図の数」で選んでいたため、拡張後に**表 6 つ・4 ページの様式型**を掴み、`reading_order` が
強い崩しに反応せず 2 つの seed で落ちた。**検査は緩めず**、題材の選び方に**ページ数**を足した
（`misread` の段組の取り違えはページごとに当たりを引くため）。pytest は **532 passed** のまま。

**既知の未修正（本件と無関係・先行して存在）**：`ruff format --check` / `ruff check` が
`contracts-calculation/examples/*/calc/programs/*.py` と `contracts-calculation/DESIGN.md` で落ちるため
`make check` は赤のまま。**本体（`keiyaku/` `tests/` `scripts/`）は全緑**で、pytest・manifest・datacard も緑。
