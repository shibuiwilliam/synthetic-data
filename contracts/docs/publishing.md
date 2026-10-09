# docs/publishing.md — データセットの公開（Hugging Face Hub）の仕様

> `dataset/` を **Hugging Face Hub のデータセットリポジトリとしてそのまま公開できる形**に整える層の仕様。
> 実装は `keiyaku/publish.py`、宣言は **`specs/publish.yaml`**、CLI は `keiyaku publish [update|check]`、
> アップロードは `scripts/upload_hf.py`、テストは `tests/unit/test_publish.py`。
>
> - 版: 1.1（2026-10-08。**検索評価セットを別のデータセットに分けた**。§12）
> - 読む順：本ファイル → `docs/data_card.md`（カードの中身）→ `docs/evaluation.md`（正解の形）
> - **ライセンスと公開可否は人間の決定事項**（`CLAUDE.md` §0.2-1）。AI は `specs/publish.yaml` の
>   `license.id` を勝手に埋めない。未決のまま `publish update` は通るが、**アップロードは拒否される**（§7）。
> - ライセンス: **CC BY 4.0**（2026-10-06 に人間が決定。H13 を閉じた）
> - **上げ先は 2 つ**：文書のデータセット（`dataset/`。`search/` を除く）と
>   検索評価セットのデータセット（`dataset/search/` がそのルート）。§12
> - **AI モデルの学習・蒸留は不可**（§10。ライセンス条件ではなく告知として書く）

---

## 1. 何を解く層か

`dataset/` は評価ハーネス向けの置き場で、そのままでは Hub に出せない。足りないものは 5 つある。

| 欠けているもの | なぜ要るか | この層の対応 |
|---|---|---|
| カード（`README.md`）の **YAML frontmatter** | Hub は**リポジトリ直下の `README.md` をデータセットカード**として読む。`license` / `language` / `configs` が無いと、検索にも Dataset Viewer にも出ない | `keiyaku publish` が frontmatter 付きで `dataset/README.md` を生成する（§3） |
| **平らな表形式の面** | Viewer と `load_dataset()` が読めるのは jsonl / csv / parquet。`source.json` のような入れ子 1 文書 1 ファイルは読めない | `dataset/views/*.jsonl` を生成する（§4）。**一次資料は変えない** |
| **LFS の指定** | PDF・PNG は Git LFS に入れる。指定が無いと通常の git オブジェクトになり、clone が重くなる | `dataset/.gitattributes` を生成する（§5） |
| **配布しないものの除外** | `render.html` はデバッグ用で配布対象外（`CLAUDE.md` §1.1）。`.DS_Store` も要らない | `dataset/.gitignore` と アップロード時の `ignore_patterns`（§5・§7） |
| **ライセンスと帰属** | PDF には Noto フォントのサブセットが埋め込まれている（SIL OFL 1.1 は再配布時に著作権表示とライセンス本文の同梱を求める） | `dataset/LICENSE`・`dataset/licenses/`（§6） |

**この層は `dataset/` の一次資料（`source.json` / `layout.json` / `answer.json` / `qa.json` /
`elements.jsonl` / `doc.pdf` / `pages/*.png`）を 1 バイトも書き換えない。** 足すだけである。

## 2. 絶対条件

1. **生成物である。** `dataset/` 直下に手で置いたファイルは次の `publish update` で消えるか上書きされる
   （`CLAUDE.md` §0.4-3）。公開の判断・文言は `specs/publish.yaml` と `docs/` に書く。
2. **数値を焼き込まない。** カードに出る数は `dataset/` の実測（`keiyaku.datacard.collect`）から取る
   （`docs/data_card.md` §2-1）。
3. **決定論。** 同じ `dataset/` と同じ `specs/publish.yaml` なら、生成物はバイト単位で同一
   （`datetime.now()` を入れない。自分自身を SHA256 の対象にしない）。
4. **人間の決定を AI が代行しない。** `license.id` が `undecided` のときは、カードに
   「配布条件は未決」と書き、`SHA256SUMS` も views も作るが、**アップロードは実行しない**。
5. **一次資料とカードで値が食い違わない。** カードの数値は `data-card.md` と同じ `collect()` から出す
   （2 か所で別に数えない）。
6. **学習・蒸留の禁止を必ず出し、かつライセンス条件にはしない。** 理由と文面は §10。
   `license.id` が決まっている限り `LICENSE`・カード（英語面・日本語面）・`licenses/NOTICE.md` の
   4 か所に出る。**「評価は学習ではない」を同じ場所に併記する。**

## 3. `dataset/README.md`（= Hugging Face データセットカード）

**README.md の所有者は `keiyaku/publish.py` である**（以前は `keiyaku/export.py` が持っていた。
`keiyaku export` は `publish.write_readme()` を呼ぶだけになった）。構成：

| 位置 | 中身 | 出所 |
|---|---|---|
| frontmatter | `license` / `language` / `pretty_name` / `task_categories` / `task_ids` / `tags` / `size_categories` / `annotations_creators` / `source_datasets` / `multilinguality` / **`configs`** | `specs/publish.yaml` ＋ 実測（`size_categories` は文書数から出す）。`configs` は `keiyaku/publish.py` の `main_configs()`（**4 件**。検索の 3 件は別データセットに出す。§12）が正本で、**`publish update` が同じ実行でその 4 件を作る／既に在ることを保証する** |
| 英語の節 | 要約・用途と非用途・構成・4 つの config の表・**検索評価セットの公開先への案内**・ライセンス・引用 | 固定文 ＋ 実測 |
| 日本語の節 | ファイルの読み方（旧 `dataset/README.md` の本文）・座標系・注意点・採点コマンド | 固定文 ＋ 実測 |
| 末尾 | `data-card.md` への案内（規模・内訳・制限と偏りの全文） | 固定文 |

- **カードとデータカードの分担は変えない**（`docs/data_card.md` §1）。README は「読み方」、
  `data-card.md` は「成分表示」。README は内訳の表を再掲せず、`data-card.md` を指す。
- frontmatter の `license` は、`license.id` が `undecided` のときは **キー自体を出さない**
  （嘘のタグを出さない）。代わりに本文に「配布条件は未決」の節を立て、`publish check` が警告する。

## 4. `dataset/views/*.jsonl`（Viewer と `load_dataset()` のための平らな面）

一次資料から機械的に導出する。**正解の正本は一次資料側**で、views はその射影である。

| ファイル | 1 行 | 行数（100 文書時） | 出所 |
|---|---|---|---|
| `views/documents.jsonl` | 1 文書 | 100 | `manifest.json` ＋ `source.json` の `meta`・`layout.json` の `page_size_pt` |
| `views/pages.jsonl` | 1 ページ | 656 | `answer.json` の `pages[]` ＋ `layout.json`（判型・dpi）＋ PNG の相対パス |
| `views/qa.jsonl` | 1 問 | 4,500 | `qa.json` の `items[]` |

**Arrow（parquet）に落とせる形に正規化する。** これは Viewer の要件で、守らないと列の型が混ざって
Viewer が落ちる。

- `qa.json` の `answer` は **float / str / list[str] が混在する**（`answer_type` で決まる）。
  views では型ごとに列を分け、**生の値は `answer_json`（JSON 文字列）で失わずに持つ**：
  `answer_text` / `answer_number` / `answer_list` / `answer_json`。
  **採点に使う正本は `qa.json` の `answer`** であり、views は閲覧と絞り込みのためにある。
- `null` を取りうる列は、全行で同じ型か null に揃える（`contract_date` など）。
- 画像は **相対パス文字列**（`image` 列）で持つ。jsonl では Hub が `Image` 型に自動変換しない
  （パスはリポジトリ直下からの相対で、読む側の作業ディレクトリとは無関係）。カードには
  **`snapshot_download()` の戻り値と結合する**例を載せる（§3 の英語節）。`cast_column("image", Image())`
  は**ローカルに実体がある場合だけ**効くので、単独では案内しない。

`elements.jsonl` と `search/*.jsonl` は**すでに平らなので views に写さない**（重複を作らない）。
`configs` から直接 glob で指す（§3）。**ただし `search/*.jsonl` は本体の `configs` に出さない**
——別のデータセットとして公開するので、本体のリポジトリには入らない（§12）。

## 5. `.gitattributes` / `.gitignore`

- `.gitattributes`：`*.pdf` `*.png` を LFS に入れる。`*.jsonl` `*.json` は LFS に入れない
  （1 ファイル最大 1.5 MiB で、diff が見えるほうが価値が高い）。`*.md` は `-text` にしない。
- `.gitignore`：`render.html`・`.DS_Store`・`*.log`。**`render.html` は配布しない**
  （`CLAUDE.md` §1.1「デバッグ用・配布対象外」）。
- アップロード側（`scripts/upload_hf.py`）も同じ一覧を `ignore_patterns` に渡す。
  **2 か所に書くが、正本は `specs/publish.yaml` の `exclude`** で、両方そこから生成する。

## 6. ライセンスと帰属のファイル

| ファイル | 中身 | 条件 |
|---|---|---|
| `dataset/LICENSE` | 生成物（PDF・JSON・PNG）のライセンス本文への案内と著作権表示、**学習と蒸留の禁止（§10）** | `license.id` が決まっているときだけ作る |
| `dataset/licenses/LICENSE-NotoSansJP.txt`・`LICENSE-NotoSerifJP.txt` | 同梱フォントのライセンス本文（`assets/fonts/` からコピー） | **PDF に実際に埋め込まれていたフォント**だけ入れる（`datacard.embedded_fonts()` の実測） |
| `dataset/licenses/NOTICE.md` | 「PDF には次のフォントのサブセットが埋め込まれている／本体の文章は全文オリジナルで、実在のひな型を転載していない／**AI モデルの学習・蒸留には使えない**」 | 常に作る |
| `dataset/SHA256SUMS` | 配布するファイルの SHA256（`exclude` に当たるものと自分自身を除く。**切り出した `search/` は数えない**） | 常に作る |
| `dataset/search/LICENSE`・`dataset/search/SHA256SUMS` | 検索評価セットのリポジトリ**自身のぶん**（フォントの案内は入れない——PDF が無い） | `search_dataset.enabled` のときだけ（§12） |

`manifest.json` の `checksums` は 1 文書 5 ファイルぶんしか無く、PNG と jsonl を覆っていない。
ダウンロード側が全量を検証できるように `SHA256SUMS` を別に作る。

## 7. 手順（公開するとき）

```
uv run keiyaku export              # 一次資料と検索評価セットとデータカードを最新にする
uv run keiyaku publish update      # README（カード）・views・.gitattributes・licenses・SHA256SUMS
uv run keiyaku publish check       # 鮮度と、公開をふさいでいる条件（未決のライセンス等）を報告する
uv run python scripts/upload_hf.py               # 何が上がるかを数えるだけ（**既定。通信しない**）
uv run python scripts/upload_hf.py --yes         # 実際に上げる（HF_TOKEN が必要。**2 リポジトリ**）
uv run python scripts/upload_hf.py --yes --public  # public で作る（**人間が明示したときだけ**）
uv run python scripts/upload_hf.py --only search   # 検索評価セットのリポジトリだけ（main も可）
```

- `scripts/upload_hf.py` は **`license.id` が `undecided` なら実行を拒否する**。
  `publish check` が鮮度の食い違いを報告している場合も拒否する。
- **引数なしが dry-run**（`--yes` を明示しない限り通信しない。`huggingface_hub` も import しない）。
  アップロードには `uv sync --group publish` が要る（既定の `uv sync` には入らない）。
- 既定の可視性は `specs/publish.yaml` の `hub.private`。**最初は private で上げ、
  人が Hub 上で中身を見てから public にする**（取り消せない外向き操作を一段に分ける）。
- 再公開（2 回目以降）は同じコマンドで差分だけが上がる。`hub.revision` にタグ名を入れると
  そのリビジョンに上げる。
- **上げ先は 2 つある**（§12）。本体へのアップロードでは `search/` を `ignore_patterns` で外す
  ——`dataset/` を丸ごと上げると、別リポジトリで配るものが二重に入る。

## 8. `make check` との関係

`publish check` は **`make check` に入れる**が、**落ちるのは鮮度の食い違いだけ**にする。
未決のライセンスで `make check` が赤くなると、公開と無関係な開発が止まるためである
（`docs/data_card.md` §5 と同じ考え方：カードは未決と書いて出る）。

| 状態 | `publish check` | 終了コード |
|---|---|---|
| 生成物が古い（README・views・SHA256SUMS が今の `dataset/` と違う） | 食い違いを列挙する | 1 |
| ライセンスが未決 | 「公開をふさいでいる」として報告する | 0 |
| `dataset/` が無い | 飛ばす | 0 |

## 9. タスクと完了条件

| # | タスク | DoD | 状態 |
|---|---|---|---|
| U1 | 本ファイル（仕様）と `specs/publish.yaml`（宣言） | 置き場所と出所が決まっている | 完了（2026-10-05） |
| U2 | `keiyaku/publish.py`（spec 読み込み・views・frontmatter・カード・licenses・SHA256SUMS） | 固定文字列に数値を焼き込んでいない・決定論 | 完了（2026-10-05） |
| U3 | CLI `keiyaku publish [update\|check]`・`export` からの呼び出し | `uv run keiyaku publish check` が動く | 完了（2026-10-05） |
| U4 | `scripts/upload_hf.py`（既定 dry-run・未決なら拒否） | 通信せずに上がる一覧を出せる | 完了（2026-10-05） |
| U5 | `tests/unit/test_publish.py` | 型混在の検出・未決時の frontmatter・決定論・除外の検査 | 完了（2026-10-05） |
| U6 | views が表形式に落ちることの実測 | config が指す jsonl が parquet に落ちる | 完了（2026-10-05。`scripts/verify_views.py` で **6 ファイル＋`*/elements.jsonl`（100 ファイル・42,789 行・23 列）が pyarrow で parquet 化**。`datasets` 本体での `load_dataset()` は**未実測**——Hub に上げるまで試せない（U8 のときに Viewer で確認する）） |
| U7 | ライセンス（H13）の決定を受けて `specs/publish.yaml` を 1 行直し、`publish update` | カードに条件が出る | 完了（2026-10-06。`license.id: cc-by-4.0`。あわせて学習・蒸留の禁止を §10 の形で 4 か所に入れた） |
| U8 | 実際のアップロード | Hub にデータセットが出る | **U7 のあと**（H15・H17 の判断待ち） |
| U9 | **検索評価セットを別のデータセットに分ける**（§12） | 本体の `configs`・`SHA256SUMS`・アップロードから `search/` が外れ、検索側が自分のカード・LICENSE・`SHA256SUMS` を持つ。`enabled: false` で元に戻せる | 完了（2026-10-08。リポジトリ名は H17 で判断待ち） |

## 10. 学習・蒸留の禁止の書き方

### 10.1 なぜ書くか

**本データセットの条文・表・図の説明・QA は Claude（Anthropic）の Output である。**
生成は Claude Code セッション内で完結しており（`CLAUDE.md` §1.2「外部 LLM API は使わない」）、
Anthropic の Usage Policy は次を禁じている。

> "Utilization of inputs and outputs to train an AI model (e.g., "model scraping" or
> "model distillation") **without prior authorization from Anthropic**"
> — <https://www.anthropic.com/legal/aup>（2025-09-15 発効）

「競合モデルに限る」という限定が**付いていない**のが要点で、用途が読み取り専用の小さなモデルでも
文面上は許可の対象に入る。受領者がこれを知らずに学習に使う事故を防ぐため、成果物に明記する。

### 10.2 なぜ「告知」であって「ライセンス条件」ではないか

**CC BY 4.0 は下流の受領者に追加の制限を課すことを禁じている**（第 2 条(a)(5)(B)
「No downstream restrictions」）。したがって `license: cc-by-4.0` を宣言したまま
「学習禁止」を**付与条件として**書くと、それ自体が CC BY 違反になる。

| | 書き方 |
|---|---|
| ライセンス | **CC BY 4.0 のまま**（`specs/publish.yaml` の `license.id`）。条件を足さない |
| 禁止 | **告知**として書く。「Anthropic Usage Policy 由来の制限であり、同ポリシーの適用を受ける者を縛る」と出どころを明示し、「これはライセンス条件ではない」と明記する |

拘束の相手が違うことも押さえておく。Anthropic の規約が縛るのは **Anthropic の顧客**であって、
データセットの受領者そのものではない。受領者が Claude の利用者であればその人に同じ制限がかかるが、
それはその人と Anthropic のあいだの問題である。**告知はその事実を伝えるためにある。**

> 禁止を拘束力のある条件にしたい場合は、CC BY 4.0 をやめて独自ライセンス
> （`license.id: other` ＋ Hub の `license_name` / `license_link`）に差し替えるしかない。
> **これは人間の決定事項**（`CLAUDE.md` §0.2-1）で、2026-10-06 の選択は「CC BY 4.0 ＋ 告知」。

### 10.3 どこに出るか（正本は生成器）

`dataset/` は生成物なので手で書かない（`CLAUDE.md` §0.4-3）。**文面の正本は `keiyaku/publish.py` の
`NO_TRAINING_EN` / `NO_TRAINING_JA`**（リンク先 URL は `AUP_URL` の 1 か所）。

| 出力 | 節 |
|---|---|
| `dataset/LICENSE` | `NOT FOR TRAINING AI MODELS`（`NO_TRAINING_EN` 全文） |
| `dataset/README.md` 英語面 | `## ⚠ Not for training AI models`（**`What it is for` より前**）＋ `What it is not for` の箇条 |
| `dataset/README.md` 日本語面 | `## ⚠ AI モデルの学習・蒸留には使えない`（**読み方の本体「並び」より前**） |
| `dataset/licenses/NOTICE.md` | 末尾に 2 行（日英） |
| `dataset/data-card.md` §12 | `keiyaku/datacard.py` の `_license_paragraph()` の 2 番目の箇条 |

### 10.4 必ず併記すること

**「評価は学習ではない」を同じ節に書く。** これを落とすと、このデータセットが作られた目的
（読み取り・検索・エージェントの評価）まで禁じられたように読める。対象外であることを明記するのは：

- 評価・ベンチマーク・採点
- テストフィクスチャ・回帰データ
- few-shot の実例
- 推論時の検索コーパス（RAG）

**除かれるのはモデルの重みを更新する用途だけ**である。

### 10.5 消えないようにする

文面は `tests/unit/test_publish.py` の 2 件が固定している（`CLAUDE.md` §2「基準は機械に落とす」）。

```bash
uv run pytest tests/unit/test_publish.py -k 学習
```

- `test_LICENSEが学習と蒸留の禁止を明記する`：見出し・TRAIN / FINE-TUNE / DISTILL / LLM / VLM・
  `AUP_URL`・`EVALUATION IS NOT TRAINING`・「告知であって条件ではない」・`2(a)(5)(B)`
- `test_カードが学習と蒸留の禁止を両言語の目立つ節で明記する`：英語面が `What it is for` より前、
  日本語面が「並び」より前にあること。`NOTICE.md` にも出ていること

## 11. 変えるときの注意

- **views に列を足すときは、Arrow の型が混ざらないかを先に確かめる**（§4）。混ざると Viewer が落ちる。
  `scripts/verify_views.py` が全列の型を走査する。
- frontmatter のキーを足すときは Hub の仕様（Dataset Cards / `configs`）に合わせる。
  **`configs` が指すパスは必ず実在を確かめてから書く**（存在しないパスを書くと Viewer が落ちる）。
  本体の `configs` に `search/*.jsonl` を書き戻すときは `search_dataset.enabled: false` と対で直す
  （§12。片方だけ直すと、配らないファイルを指すか、配るのに誰も見つけられないかになる）。
- `dataset/` に新しいディレクトリを足したら **`keiyaku clean --stale` の保護一覧**
  （`keiyaku/cli.py` の `PROTECTED_DIRS`）に入れる。入れないと掃除で消える。
## 12. 検索評価セットは別のデータセット（2026-10-08）

### 12.1 何を分けたか

| | 文書のデータセット | 検索評価セットのデータセット |
|---|---|---|
| Hub の repo | `specs/publish.yaml` の `hub.repo_id` | `search_dataset.hub.repo_id`（**名前は未決。H17**） |
| 上げるディレクトリ | `dataset/`（**`search/` を除く**） | `dataset/search/`（**これがリポジトリのルート**） |
| configs | `documents` / `pages` / `qa` / `elements` | `passages` / `queries` / `qrels` |
| 1 行の単位 | 1 文書・1 ページ・1 問・1 要素 | 1 パッセージ・1 クエリ・1 適合判定 |
| 中身 | PDF・150dpi の PNG・構造・QA（**365 MiB 級**） | jsonl 3 本（**3 MiB 級**） |
| カード | `dataset/README.md` | `dataset/search/README.md` |
| LICENSE / SHA256SUMS | `dataset/` の 2 本 | `dataset/search/` に**自分のぶん**を持つ |

**なぜ分けるか。** (1) 粒度が違うものを 1 つの Viewer に混ぜると、config を選ばない閲覧者に
「何のデータか」が伝わらない。(2) 検索だけを使う人が 365 MiB の PDF と PNG を取らなくて済む
（`load_dataset()` は config 単位で取るが、`snapshot_download()` と Hub の clone はリポジトリ単位）。
(3) `task_categories` が別になる（本体は QA・OCR・表、検索側は `text-retrieval` だけ）。

**生成の場所は変えない。** `keiyaku export` はこれまでどおり `dataset/search/*.jsonl` を作り、
`keiyaku eval --search-run` も同じパスを読む。**変わるのは公開の面だけ**である。

### 12.2 実装の要点（`keiyaku/publish.py`）

- 宣言は `specs/publish.yaml` の **`search_dataset`**（`enabled` / `dir` / `hub` / `pretty_name` /
  `task_categories` / `task_ids` / `tags`）。`enabled: false` にすれば**元どおり本体に同梱**される
  （`main_configs()` が `search/*.jsonl` を本体の `configs` に戻す）。戻せることをテストで縛っている。
- `distributed_files()` は切り出しているとき **`search/` をディレクトリごと除く**。したがって
  本体の `SHA256SUMS` にも、アップロードの対象にも入らない（二重配布を作らない）。
- 検索側は `search_distributed_files()` / `search_checksums()` が面倒を見る。**`SHA256SUMS` の
  パスは自分のルートからの相対**（`search/passages.jsonl` ではなく `passages.jsonl`）。
- 検索側のカードは `render_search_card()`。数値は `stats.search`（実測）、**列名は jsonl から実測する**
  （`search_fields()`。スキーマを固定文字列で書くと生成器と食い違う）。
- 検索側の `LICENSE` は `write_license_file(..., fonts=False)`。**PDF が無いリポジトリで
  `licenses/NOTICE.md` を案内しない**（存在しないファイルを指さない）。
- 学習・蒸留の禁止（§10）は**両方のカードと両方の `LICENSE` に出す**。片方だけを見た人に伝わらない。
- 両カードは**相互に案内する**。検索側は `passage_id` が `<doc_id>::<element_id>` であることと
  文書側のリポジトリを、本体側は検索側のリポジトリを書く。

### 12.3 `publish check` と blockers

- `check` は**両方のカード・LICENSE・SHA256SUMS の鮮度**を見る（`search/README.md` が古ければ報告する）。
- `blockers()` に「検索評価セットの公開先が無い」を足した。**本体に入れないと決めたのに
  `search_dataset.hub.repo_id` が空だと、検索評価セットがどこにも出ない**ため、アップロードを止める。

