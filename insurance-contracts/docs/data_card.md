# docs/data_card.md — データカード（`dataset/data-card.md`）の仕様と自動更新

> `dataset/data-card.md` は **データセットの利用者が最初に読む 1 枚**である。
> 「何が・どれだけ・どうやって作られ・何に使えて・何に使えないか」を実測値で示す。
> **このファイル（docs/）が仕様の正本**で、`dataset/data-card.md` は
> `yakkan datacard update`（および `yakkan export`）が生成する**生成物**である
> （CLAUDE.md §0.4-3。手編集禁止）。
>
> - 版: 1.0（2026-10-04 新設）
> - 実装: `yakkan/datacard.py`、CLI `yakkan datacard [update|check]`、
>   テスト `tests/unit/test_datacard.py`、測り方の検算 `scripts/verify_data_card.py`

---

## 1. なぜ要るか（`dataset/README.md` との分担）

`dataset/` の説明ファイルは **2 枚**で、役割が重ならない。

| | `README.md` | `data-card.md`（本件） |
|---|---|---|
| 生成 | `yakkan export` | **`yakkan datacard update`** |
| 形式 | **Hugging Face のデータセットカード**（YAML frontmatter つき） | 自由記述 |
| 読者 | HF でカードを眺める人・これから評価コードを書く人 | **使うかどうかを判断する人・引用する人** |
| 中身 | 1 画面ぶんの要約（規模・架空性・限界・ライセンス・引用）＋ ファイル構成・スキーマ・座標系・採点コマンド・検索ベースライン | **規模の実測・内訳の全件・生成方法・検証の結果・制限と偏り** |
| 重複の扱い | ファイル構成と要約は README が正本 | **カードは README を参照し、構成の表とベースライン表を再掲しない** |

**2026-10-05 に `DATASET_CARD.md` を廃止し `README.md` に統合した。**
HF はリポジトリ直下の `README.md` だけをデータセットカードとして読むので、
別名のカードを置いても配布先には出ず、2 枚あると数値が食い違いうる
（`docs/distribution.md` §2-1・`docs/decisions.md` 2026-10-05）。
`README.md` は配布面向けに**短く**保つ。本カードは**長くて構わない**——
文書ごと・ジャンルごと・観点ごとの全件表を載せ、「この観点は母数が足りない」まで書く。

**どれも固定文字列に統計値を焼き込まない**（`docs/decisions.md` 2026-10-04
「`dataset/README.md` の生成ロジックが統計値を固定文字列で焼き込んでいた」の再発防止）。

## 2. 絶対条件

1. **カードに出る数値はすべて `dataset/` の実ファイルから測る。** 仕様書・`TASK.md`・
   `docs/progress.md`・過去のセッションの記憶を数値の出典にしない。
2. **文書を足したら更新される。** 更新しないままデータが増えたら `make check` が赤くなる（§5）。
3. **人間の判断が要る欄を AI が埋めない。** ライセンス・配布条件は決定が無ければ「未決」と書き、
   `TASK.md` T11 / `HITL_TODO.md` H13 を指す（CLAUDE.md §0.2-1）。
   **2026-10-05 に `TASK.md` T11 でライセンスが CC BY 4.0 に決まった**ので、
   現行のカードは「未決」ではなく決定値を出す。出典は `yakkan/export.py` の
   `LICENSE_ID`（1 か所）で、カード側は固定文字列を持たない。
4. **母数の小さい観点を黙って隠さない。** 1〜2 content しか覆っていない観点は、カード自身が
   「この観点で精度を語るには母数が足りない」と明記する（§4.3）。
5. **不合格の文書と余計なファイルを隠さない。** `status: failed` はその理由（`manifest.errors`）を
   そのまま載せ、成果物の一覧に無いファイル（調査の痕跡など）が `dataset/` に残っていれば申告する。
6. 生成は決定論。同じ `dataset/` なら同じカードが出る（`datetime.now()` を入れない。
   自分自身のファイルサイズは数えない。§4.1）。

## 3. 構成（節と、各節の数値の出所）

| 節 | 中身 | 数値の出所 |
|---|---|---|
| 1 概要 | 一行説明。**版・生成日時は書かない**（決定論。CLAUDE.md §13） | 固定文＋`manifest.json` |
| 2 想定する用途／想定しない用途 | 読み取り・構造抽出・表／図・参照・QA・レイアウト頑健性・検索の評価。**実務利用と保険商品としての参照は対象外** | 固定文 |
| 3 規模 | 文書・content・genre・style・ページ・文字・表／セル・図／ノード／辺／経路・参照・列挙・定義語・用語参照・定数・脚注・算式・QA・要素索引・パッセージ・容量 | `manifest.json`・`source.json`・`answer.json`・`*.jsonl`・ファイルサイズ |
| 4 内訳 | genre 別／style 別（実測フォントつき）／文書別（**全件**）の表と、**骨格・体裁の覆い** | `manifest.json`＋`source.json`＋`doc.pdf` |
| 5 正解の中身 | 構造（ノード種別）・ブロック種別・表の意味種別・図の種別・QA（種別／出所／答えの型）・定義語と用語参照・番号方式と発行体と体裁の宣言 | `source.json` の `derived`＋本体、`qa.json` |
| 6 版面 | 判型・段数・領域別の行数・renderer と版・PNG の dpi・**PDF に実際に埋め込まれていたフォント**（`layout.renderer.fonts` は描画に登録した候補で、使われたものとは違う） | `layout.json` ＋ `doc.pdf`（フォント資源を実測） |
| 7 検索評価セット | パッセージ（種別別）・クエリ（種別別・`filters` つき・`hard_negatives`・`no_answer`）・qrels（grade 別）・打ち切りクエリ・コーパスの鮮度 | `dataset/search/*.jsonl` |
| 8 どう作ったか | blueprint → scaffold → 執筆 → lint → build → render → verify → qa → export。決定論・seed・**外部 LLM API を使わないこと** | 固定文＋`layout.json` の renderer |
| 9 架空性と転載 | ハードルール（架空・転載禁止・法令の条番号を書かない）・奥付の disclaimer | 固定文＋`source.json` の `meta.disclaimer` |
| 10 品質保証 | lint（L00–L19）・verify（V01–V10）・`manifest check`・`eval --oracle`・検証の階段・**不合格文書の理由** | 固定文＋`manifest.json` の `status` / `errors` |
| 11 制限と既知の偏り | 日本語横書き・縦書きとルビなし・スキャン劣化なし・tagged PDF でない等（固定）＋**母数の小さい観点の自動検出**（§4.3）＋**宣言はあるが使用 0 の観点** | 固定文＋実測 |
| 12 ライセンスと配布 | 生成物の扱い（**未決**）・**実測した埋め込みフォント**のライセンス（Noto → SIL OFL 1.1／IPAex → IPA FL v1.0）・同梱しているが使われていないフォント | 固定文＋§6 の実測 |
| 13 更新のしかた | 生成物であること・`yakkan datacard update`・鮮度検査 | 固定文 |

## 4. 実装の決め

### 4.1 測り方

- 入力は `dataset/` 配下だけ。`manifest.json` は `yakkan.manifest.Manifest`、
  `source.json` は `yakkan.models.Source`、`layout.json` は `Layout` で**モデルとして読む**
  （CLAUDE.md §13「dict を裸で回さない」）。`answer.json` / `qa.json` / `*.jsonl` は
  件数と文字数だけなので素の JSON で読む。
- 容量は `dataset/` の全ファイルを拡張子ごとに合計する。**`data-card.md` 自身は数えない**
  （数えると書き出すたびに数が動き、鮮度検査が収束しない）。ドットファイルも数えない。
- 数値の整形は `{:,}`。容量は MiB 小数 1 桁（1 MiB 未満は KiB 整数）。
- **表は `front_matter` のものも数える。** `purpose_index`（目的別もくじ）・`rider_index`
  （特約一覧表）・`petname_table`（ペットネーム対応表）は `Node.blocks` の外にあるが、
  紙面に出る表であり `derived.tables` にも入る。本文の木だけを走ると
  **`semantic_type: purpose_index` が「使用 0」に見える**（実測 14 文書で使用中）。
- **PDF の埋め込みフォントはページのフォント資源（`/BaseFont`）から測る。**
  全文字を走査する方法（`page.chars`）と同じ結果になることを
  `scripts/verify_data_card.py` が別経路で突合する。114 文書で約 2 分 → 約 2 秒になる。
- **`status: failed` の文書は `answer.json` / `qa.json` / `*.jsonl` を持たない。**
  欠けていても落ちず、その文書ぶんを 0 として数える。

### 4.2 検索評価セットの鮮度

`search/` は `yakkan export` の出力なので、文書を足して export を回していないと
**カードの検索の数だけが古い**という状態が起こりうる。カードは
`search/passages.jsonl` に出てくる `content_id` と `dataset/` の content を突き合わせ、
欠けているものがあれば §7 に**警告行を出す**（黙って古い数を載せない）。

### 4.3 母数の小さい観点の自動検出

次の観点について「それを含む content の数」を数え、**閾値（既定 3 content）未満**なら
§11 に「母数が足りない」として列挙する。観点を増やしたら自動で検査対象になる。

- **骨格**：表紙・前文（preface）・目的別もくじ・特約一覧表・ペットネーム対応表・目次・
  部（part）・章（chapter）・節（section）・特約（rider）・条（article）・項・号・細目・
  別表／別紙（appendix）・**条文型／丸数字型**
- 条文型と丸数字型の別は**条ラベルの形**（`第◯条` で始まるか）で見る。**ノード種別では
  分かれない**——`jyusetsu`（重要事項説明書）は blueprint で「条を持たない」と宣言している
  のに、実装は他のジャンルと同じ `kind: "article"` のノードを使い、番号方式が「①」と振る
  だけである（2026-10-04 に実測して発覚）
- **体裁**：脚注・欄外注（`box: margin_note`）・注意枠（`note` / `caution` / `example`）・
  算式（formula）・箇条書き（list の各 style）・Q 見出し（qa_heading）・結合セル・
  繰り返し表頭・段またぎ表（`span_columns`）・縦書きセル（`vertical_text`）・
  強制改ページ・番号の例外（`number_override`）・商品名バッジ・ペットネーム・
  発行体の種別（株式会社／相互会社）・用語集（`defined_terms`）
- **要素**：表の意味種別（15 種）・図の種別（6 種）
- **宣言**：genre（10 種）・numbering scheme（5 種）・style（13 種）・`digit_style`・
  `article_heading`・`caption_numbering`・`footnote_style`

**観点名は `yakkan/datacard.py` の `SKELETON_FEATURES` / `FORMAT_FEATURES` が正本**で、
`_features()`（測る側）と `_universe()`（宣言の全体）の両方がこれを使う。**片方にしか無い観点は、
使用 0 のときに「未使用」の表に出ず黙って消える**——実際に 1 度そうなった（ペットネーム対応表・
細目・`qa_heading`・`page_break`・`number_override`・縦書きセルの 6 件が消えていた）。
ずれは `tests/unit/test_datacard.py` が検出する。

**使っていない宣言（content が 0 のもの）は「未使用」として別に挙げる**
（2026-10-04 の実測で 13 件。縦書きセル・`page_break` は P6 の任意項目で未使用。CLAUDE.md §15）。

### 4.4 成果物でないファイルの申告

`dataset/<doc_id>/` に `yakkan.manifest.ARTIFACT_FILES` ＋ `pages/*.png` 以外の
ファイルが残っていれば、§3 の容量の下に**名前と件数を出す**。
調査の痕跡（`render.pdf` など）が配布物に混ざるのを黙って見逃さないため。

## 5. 自動更新をどう担保するか（3 重）

| 層 | 仕組み | 効き方 |
|---|---|---|
| 生成 | `yakkan export` の最後に `write_card()` を呼ぶ | 既存の「足したら export」の流れで更新される |
| 生成 | `make batch`（`yakkan batch` → `manifest update` → **`datacard update`**） | バッチで足したら更新される |
| 検査 | **`make check` に `datacard-check` を足す** | 更新を忘れたらコミット前に赤くなる |

`yakkan datacard check` は `manifest check` と同じ流儀で、**書き換えずに**食い違いを報告する
（終了コード 1）。`dataset/` が無ければ飛ばす。

**順番がある。`manifest update` → `datacard update` の順で回す。** カードは容量に
`manifest.json` を数えるので、カードを書いたあとに manifest を書き換えるとカードが古くなる
（`make batch` はこの順で並べてある）。逆順で回しても壊れはしない——`datacard check` が
古さを検出するので、もう一度 `datacard update` を回せばよい。

**2 つの検査は別物である。**

| 検査 | 問い |
|---|---|
| `yakkan datacard check` | カードは**いまの `dataset/` から生成したもの**か（鮮度） |
| `uv run python scripts/verify_data_card.py` | **測り方そのもの**が正しいか（pydantic を通さない別経路で再計算して突合） |

前者は `make check` に入っている。後者は測り方を変えたとき（節や項目を足したとき）に手で回す。

## 6. タスクと完了条件

| # | タスク | DoD | 状態 |
|---|---|---|---|
| D1 | `dataset/` の全数調査（何を測れるかの確定） | 本ファイル §3 の表が埋まっている | 完了（2026-10-04） |
| D2 | 本ファイル（仕様と計画）と `docs/progress.md` への起票 | 仕様と計画が文書にある | 完了（2026-10-04） |
| D3 | `yakkan/datacard.py`（collect / render / write / check） | 固定文字列に数値を焼き込んでいない | 完了（2026-10-04） |
| D4 | CLI `yakkan datacard [update\|check]`・`export` への組み込み | `uv run yakkan datacard check` が動く | 完了（2026-10-04） |
| D5 | `make check` への鮮度検査の追加・`make batch` への更新の追加 | カードが古いと `make check` が赤 | 完了（2026-10-04） |
| D6 | `tests/unit/test_datacard.py` | 焼き込み禁止・鮮度検出・母数検出・決定論・failed 文書の欠損耐性を検査 | 完了（2026-10-04） |
| D7 | 114 文書で生成して内容をレビュー（数値を独立に再計算して突合。**`scripts/verify_data_card.py`**＝pydantic を通さない別経路・フォントは全文字走査） | 突合 164 項目（スカラ 22・容量 7・分布 16・全件 114 行・検索 3・disclaimer 1）が一致 | 完了（2026-10-04） |
| D8 | 文書を足して（または削って）更新されることの実測 | 文書を 1 本増減した dataset で数値が追従し、`check` が古さを検出 | 完了（2026-10-04） |
| D9 | `docs/decisions.md`・`docs/progress.md`・`CLAUDE.md` §0.3・§11 への記録 | 記録済み | 完了（2026-10-04） |

## 7. 変えるときの注意

- **節を増やすときは「数値の出所」を §3 の表に書いてから実装する。** 出所の無い数値を
  カードに書かない。
- 固定文に数値を書きたくなったら、それは `DataCardStats` に足すべき項目である。
- 観点（§4.3）を足したら `scripts/verify_data_card.py` の突合表にも足す。
- 人間の判断が要る欄（ライセンス・配布・引用のしかた）は、決定が `TASK.md` に
  入ってから固定文を書き換える。**AI が決めない。**
