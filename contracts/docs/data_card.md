# docs/data_card.md — データカード（`dataset/data-card.md`）の仕様と自動更新

> `dataset/data-card.md` は **データセットの利用者が最初に読む 1 枚**である。
> 「何が・どれだけ・どうやって作られ・何に使えて・何に使えないか」を実測値で示す。
> **このファイル（docs/）が仕様の正本**で、`dataset/data-card.md` は `keiyaku datacard update`
> （および `keiyaku export`）が生成する**生成物**である（CLAUDE.md §0.4-3。手編集禁止）。
>
> - 版: 1.0（2026-10-04 新設）
> - 実装: `keiyaku/datacard.py`、CLI `keiyaku datacard [update|check]`、テスト `tests/unit/test_datacard.py`

---

## 1. なぜ要るか（`dataset/README.md` との分担）

`dataset/README.md` は**ファイルの読み方**（どの成果物に何が入っているか・座標系・注意点）を書く
「使用説明書」である。これに対しデータカードは**データの素性**（規模・構成・作り方・品質保証・
制限・偏り・ライセンス）を書く「成分表示」で、読者も目的も違う。

| | `README.md` | `data-card.md` |
|---|---|---|
| 読者 | これから評価コードを書く人 | 使うかどうかを判断する人・引用する人 |
| 中身 | ファイル構成・スキーマ・座標系・採点コマンド | 規模の実測・内訳・生成方法・検証の結果・制限と偏り・ライセンス |
| 重複の扱い | ファイル構成は README が正本 | **カードは README を参照し、構成の表を再掲しない** |

**どちらも固定文字列に統計値を焼き込まない**（`docs/decisions.md` 105・131 の再発防止）。

## 2. 絶対条件

1. **カードに出る数値はすべて `dataset/` の実ファイルから測る。** 仕様書・`TASK.md`・
   過去のセッションの記憶を数値の出典にしない（`TASK.md` §1.2 の検索評価セットの数は
   実際に古くなっていた——クエリ 778 と書いてあったが実測 1,170）。
2. **文書を足したら更新される。** 更新しないままデータが増えたら `make check` が赤くなる（§5）。
3. **人間の判断が要る欄を AI が埋めない。** ライセンス・配布条件は決定が無ければ「未決」と書き、
   `HITL_TODO.md` に起票する（CLAUDE.md §0.2-1）。
4. **母数の小さい観点を黙って隠さない。** 1〜2 content しか覆っていない観点は、カード自身が
   「この観点で精度を語るには母数が足りない」と明記する（§4.3）。
5. 生成は決定論。同じ `dataset/` なら同じカードが出る（自分自身のファイルサイズは数えない。§4.1）。

## 3. 構成（節と、各節の数値の出所）

| 節 | 中身 | 数値の出所 |
|---|---|---|
| 1 概要 | 一行説明・版・生成日時を**書かない**（決定論。CLAUDE.md §13） | 固定文 |
| 2 想定する用途／想定しない用途 | 読み取り・レイアウト頑健性・構造抽出・検索の評価。**実務利用と法的利用は対象外** | 固定文 |
| 3 規模 | 文書・content・doctype・style・ページ・文字・QA・要素・パッセージ・容量 | `manifest.json`・`elements.jsonl`・ファイルサイズ |
| 4 内訳 | doctype 別／style 別（実測フォントつき）／文書別（**全件**）の表と、**骨格・体裁の覆い**（条文型・様式型・頭書・章立て・目次・逐条解説ほか） | `manifest.json`＋`source.json`＋`doc.pdf` |
| 5 正解の中身 | 構造（ノード種別）・表（意味種別・セル数）・図（種別・ノード・辺・経路）・参照・定義語・QA（種別／出所／答えの型） | `source.json` の `derived`＋本体、`qa.json` |
| 6 版面 | 判型・段数・領域別の行数・renderer と版・PNG の dpi・**PDF に実際に埋め込まれていたフォント**（`layout.renderer.fonts` は描画に登録した候補で、使われたものとは違う） | `layout.json` ＋ `doc.pdf`（pdfplumber で実測） |
| 7 検索評価セット | パッセージ（種別別）・クエリ（種別別）・qrels（grade 別）・打ち切りクエリ・**配布は別データセット**（`docs/publishing.md` §12） | `dataset/search/*.jsonl` ＋ `specs/publish.yaml` の `search_dataset` |
| 8 生成方法 | JSON→HTML→PDF・決定論・seed・執筆の役割分担・外部 LLM API を使わないこと | 固定文＋`layout.json` の renderer |
| 9 架空性と転載 | ハードルール（架空・転載禁止・法令の条番号を書かない）・奥付の disclaimer | 固定文＋`source.json` の `meta.disclaimer` |
| 10 品質保証 | lint（L00–L26）・verify・`manifest check`・`eval --all --oracle`・検証の階段 V-A〜V-F | 固定文＋`manifest.json` の `status` |
| 11 制限と既知の偏り | 日本語横書き・1 段組のみ・スキャン劣化なし・印影なし等（固定）＋**母数の小さい観点の自動検出**（§4.3） | 固定文＋実測 |
| 12 ライセンスと配布 | 生成物の扱い（**`specs/publish.yaml` の `license` から書く**。未決なら未決と書き、決まれば識別子と公開先 URL を出す）・**実測した埋め込みフォント**のライセンス（Noto → SIL OFL 1.1／IPAex → IPA FL v1.0）・同梱しているが使われていないフォント | `specs/publish.yaml`＋§6 の実測 |
| 13 更新のしかた | 生成物であること・`keiyaku datacard update`・鮮度検査 | 固定文 |

## 4. 実装の決め

### 4.1 測り方

- 入力は `dataset/` 配下だけ。`manifest.json` は `keiyaku.manifest.Manifest`、
  `source.json` は `keiyaku.models.Source`、`layout.json` は `Layout` で**モデルとして読む**
  （CLAUDE.md §13「dict を裸で回さない」）。
- 容量は `dataset/` の全ファイルを拡張子ごとに合計する。**`data-card.md` 自身は数えない**
  （数えると書き出すたびに数が動き、鮮度検査が収束しない）。ドットファイルも数えない。
  **公開用の包み（`README.md`・`SHA256SUMS`・`LICENSE`・`views/`・`licenses/`）も数えない**
  ——`keiyaku publish` の生成物であり、カードのサイズ → `SHA256SUMS` → カード…と
  相互参照になって収束しない（`keiyaku/datacard.py` の `SIZE_EXCLUDE` / `SIZE_EXCLUDE_DIRS`。
  `docs/publishing.md` §3）。カードは「データの中身」を測るものと割り切る。
- 数値の整形は `{:,}`。容量は MiB 小数 1 桁。

### 4.2 検索評価セットの鮮度

`search/` は `keiyaku export` の出力なので、文書を足して export を回していないと
**カードの検索の数だけが古い**という状態が起こりうる。カードは
`search/passages.jsonl` に出てくる `content_id` と `dataset/` の content を突き合わせ、
欠けているものがあれば §7 に**警告行を出す**（黙って古い数を載せない）。

### 4.3 母数の小さい観点の自動検出

次の観点について「それを含む content の数」を数え、**閾値（既定 3 content）未満**なら
§11 に「母数が足りない」として列挙する。観点を増やしたら自動で検査対象になる。

- 骨格・体裁：頭書（`head_matter`）・目次・逐条解説（`commentary`）・脚注・当事者 3 者以上・
  章立て・附則・`number_override`・**条文型／様式型**
  （**`kind: "article"` の有無では分かれない**——様式型も `article` ノードを使い、番号方式が
  「（１）」と振るだけである。**条ラベルの形**（`第◯条` か）で見る。`docs/decisions.md` 141）
- 要素：表の意味種別（16 種）・図の種別（6 種）・数式・結合セル・欄外注
- 宣言：doctype（10 種）・numbering scheme（3 種）・style（4 種）・`digit_style`・`article_heading`

**使っていない宣言（content が 0 のもの）は「未使用」として別に挙げる**
（`ct-a3-landscape-form` は実装済みで使用 0。`TASK.md` の H10）。

## 5. 自動更新をどう担保するか（3 重）

| 層 | 仕組み | 効き方 |
|---|---|---|
| 生成 | `keiyaku export` の最後に `write_card()` を呼ぶ | 既存の「足したら export」の流れで更新される |
| 生成 | `make batch`（`keiyaku batch` → `manifest update` → **`datacard update`**） | バッチで足したら更新される |
| 検査 | **`make check` に `datacard-check` を足す** | 更新を忘れたらコミット前に赤くなる |

`keiyaku datacard check` は `manifest check` と同じ流儀で、**書き換えずに**食い違いを報告する
（終了コード 1）。`dataset/` が無ければ飛ばす。

**2 つの検査は別物である。**

| 検査 | 問い |
|---|---|
| `keiyaku datacard check` | カードは**いまの `dataset/` から生成したもの**か（鮮度） |
| `uv run python scripts/verify_data_card.py` | **測り方そのもの**が正しいか（pydantic を通さない別経路で再計算して突合） |

前者は `make check` に入っている。後者は測り方を変えたとき（節や項目を足したとき）に手で回す。

## 6. タスクと完了条件

| # | タスク | DoD | 状態 |
|---|---|---|---|
| D1 | `dataset/` の全数調査（何を測れるかの確定） | 本ファイル §3 の表が埋まっている | 完了（2026-10-04） |
| D2 | 本ファイル（仕様）と `TASK.md` への起票 | 仕様と計画が文書にある | 完了（2026-10-04） |
| D3 | `keiyaku/datacard.py`（collect / render / write / check） | 固定文字列に数値を焼き込んでいない | 完了（2026-10-04） |
| D4 | CLI `keiyaku datacard [update\|check]`・`export` への組み込み | `uv run keiyaku datacard check` が動く | 完了（2026-10-04） |
| D5 | `make check` への鮮度検査の追加・`make batch` への更新の追加 | カードが古いと `make check` が赤 | 完了（2026-10-04） |
| D6 | `tests/unit/test_datacard.py` | 焼き込み禁止・鮮度検出・母数検出・決定論を検査 | 完了（2026-10-04） |
| D7 | 41 文書で生成して内容をレビュー（数値を独立に再計算して突合。**`scripts/verify_data_card.py`**＝pydantic を通さない別経路） | スカラ 31 項目＋分布 10 種＋全件 41 行が一致 | 完了（2026-10-04） |
| D8 | 文書を足して（または削って）更新されることの実測 | 文書を 1 本増やした dataset で数値が追従し、`check` が古さを検出 | 完了（2026-10-04） |
| D9 | `docs/decisions.md`・`docs/progress.md`・`CLAUDE.md` §0.3・§1.1 への記録 | 記録済み | 完了（2026-10-04） |

## 7. 変えるときの注意

- **節を増やすときは「数値の出所」を §3 の表に書いてから実装する。** 出所の無い数値を
  カードに書かない。
- 固定文に数値を書きたくなったら、それは `DataCardStats` に足すべき項目である。
- 人間の判断が要る欄（ライセンス・配布・引用のしかた）は、決定が `HITL_TODO.md` §3 に
  入ってから固定文を書き換える。**AI が決めない。** §12 は固定文ではなく
  **`specs/publish.yaml` の `license` を読む**ので、決定が入れば 1 行の変更で追従する
  （`keiyaku/datacard.py` の `_license_paragraph()`）。
