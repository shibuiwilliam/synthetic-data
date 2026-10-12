# distribution.md — `dataset/` の配布（Hugging Face / GitHub）

> `TASK.md` **T7**（配布手段）・**T11**（ライセンス）の実施手順。
> **配布物を触る作業では着手前に本ファイルを読む。** 配布の判断と実行は人間が持ち、
> AI は**生成と検査**だけを行う（CLAUDE.md §0.2）。
>
> - 版: 1.1（2026-10-05 新設 / **2026-10-08 検索評価セットを別データセットに分離**）
> - 配布先: Hugging Face Datasets の **2 つのリポジトリ**
>   - 文書本体 `cvusk/japanese-insurance-document-understanding`
>   - 検索評価セット `cvusk/japanese-insurance-document-understanding-retrieval`（`dataset/search/` の中身）
> - ライセンス: **CC BY 4.0**（`TASK.md` T11 で 2026-10-05 に決定）。**両方に同じ条件**
> - **AI モデルの学習・蒸留は不可**（§7。ライセンス条件ではなく告知として書く）
> - 実装: `yakkan/export.py`（`write_card` / `write_license` / `write_gitattributes` /
>   `write_search_card` / `write_search_license` / `write_search_gitattributes` /
>   `write_qa_jsonl` / `write_documents_jsonl` / `remove_retired`）、テスト `tests/unit/test_export.py`

---

## 1. 何を配るか（**2 つのデータセット**）

**`dataset/` を文書本体のリポジトリに、`dataset/search/` を検索評価セットのリポジトリにする**
（2026-10-08 決定。理由は §2-8）。どちらも配布物は `yakkan export` ＋ `manifest update` ＋
`datacard update` の出力だけで、**手で足すファイルは 1 つも無い**（CLAUDE.md §0.4-3）。

| | ローカル | HF リポジトリ | 大きさ |
|---|---|---|---:|
| 文書本体 | `dataset/`（`search/` と `*/render.html` を除く） | `cvusk/japanese-insurance-document-understanding` | 845.8 MiB / 2,235 ファイル |
| 検索評価セット | `dataset/search/` | `cvusk/japanese-insurance-document-understanding-retrieval` | 18.9 MiB / 7 ファイル |

### 1.1 文書本体

| 内訳 | 実測 | 件数 |
|---|---:|---:|
| `*/pages/*.png`（150dpi ページ画像） | 613.7 MiB | 1,437 |
| `*/layout.json` | 62.9 MiB | 113 |
| `*/elements.jsonl` | 60.2 MiB | 113 |
| `*/source.json` | 47.0 MiB | 113 |
| `*/doc.pdf` | 33.3 MiB | 113 |
| `*/answer.json` | 14.0 MiB | 113 |
| `*/passages.jsonl` | 9.9 MiB | 113 |
| 直下（カード・LICENSE・manifest・jsonl） | 2.6 MiB | 7 |
| `*/qa.json` | 2.0 MiB | 113 |
| **配布する実体** | **845.8 MiB** | **2,235** |
| ~~`search/`~~ **別リポジトリへ** | 18.9 MiB | 7 |
| ~~`*/render.html`~~ **配布しない** | 14.7 MiB | 113 |

**`render.html` は配布しない。** デバッグ用の中間 HTML で、正解でもなく入力でもない
（`dataset/README.md` にも「配布対象外」と書いてある）。`manifest.json` の `artifacts` には
載っているので**消さず、アップロード時に除外する**（§4）。
**`search/` も同じく「消さずに除外する」**——正本はローカルの `dataset/search/` 1 か所で、
`yakkan eval --search-run` の既定パスもそこを見る。

直下のファイル：

| ファイル | 役目 | 生成 |
|---|---|---|
| `README.md` | **Hugging Face のデータセットカード**（YAML frontmatter ＋ 本文） | `yakkan export` |
| `LICENSE` | CC BY 4.0 の表示・帰属の書き方・**学習と蒸留の禁止（§7）**・埋め込みフォントの扱い | `yakkan export` |
| `.gitattributes` | `*.png` と `*.pdf` を Git LFS で追跡 | `yakkan export` |
| `data-card.md` | 規模・内訳・検証結果・制限と偏りの実測（長い版） | `yakkan datacard update` |
| `manifest.json` | 全文書の一覧（**正本**） | `yakkan manifest update` |
| `documents.jsonl` | `manifest.json` を 1 行 1 文書に平らにしたもの | `yakkan export` |
| `qa.jsonl` | 全文書の QA を 1 行 1 問に平らにしたもの | `yakkan export` |

### 1.2 検索評価セット（`dataset/search/`）

**このディレクトリがそのまま別リポジトリの直下になる。** だからカード・LICENSE・
`.gitattributes` もこの中にある（`yakkan export` が書く）。

| ファイル | 役目 |
|---|---|
| `README.md` | **検索評価セット側のデータセットカード**（`write_search_card`。英語面＋日本語面） |
| `LICENSE` | **本体より短い専用の本文**（`SEARCH_LICENSE_NOTICE`）。CC BY 4.0 ＋ 学習禁止の告知。**フォントの節は無い**（PDF が無い） |
| `SHA256SUMS` | このリポジトリで配布するファイルの SHA256（**自分のルートからの相対パス**） |
| `passages.jsonl` | 検索に登録する単位（コーパス全体。content ごとに 1 スタイル） |
| `queries.jsonl` | クエリ 10 種 |
| `qrels.jsonl` | 適合判定（grade 2 / 1） |
| `id_map.json` | 旧 id → 新 id（v6 以前との対応） |

**`.gitattributes` は置かない。** LFS に入れる対象が無いリポジトリに置いても意味が無い
（姉妹プロジェクト contracts と同じ。2026-10-09 に廃止し、`RETIRED_SEARCH_ARTIFACTS` で
生成器が古いファイルを片付ける）。配布物の一覧は `SHA256SUMS` が兼ねる。

**設計・ベースライン・読むときの注意点は、こちらのカードが持つ**（本体のカードから移した）。
本体のカードには件数と分け先へのリンクだけが残る。

## 2. なぜこの形か（設計上の決めごと）

1. **カードは `README.md` 1 枚。** HF はリポジトリ直下の `README.md` だけを
   データセットカードとして読む。以前は `README.md`（読み方）と `DATASET_CARD.md`
   （HF 形式の要約）に分かれていたが、**HF 側は後者を見ない**うえ 2 枚あると数値が
   食い違いうるので統合した。`DATASET_CARD.md` は `remove_retired()` が消す。
2. **`configs:` を frontmatter で明示する。** 宣言しないと HF は 2,239 ファイルから
   データ構成を推測しようとして、データセットビューアが動かない。
   表形式で読める 5 つだけを config にしてある（§3）。
3. **`qa.jsonl` と `documents.jsonl` は平らな派生。** `qa.json` は 1 文書 1 オブジェクト
   （`{doc_id, items[]}`）、`manifest.json` は 1 個の巨大オブジェクトなので、
   どちらも「1 行 1 レコード」ではなくビューアが読めない。**正本はもとのファイル**で、
   平らな版は閲覧と `load_dataset` の便宜のために足した。
4. **`qa.jsonl` の `answer` は 3 列に分ける。** `qa.json` の `answer` は
   `string`（3,641）/ `number`（1,107）/ `list`（337）の 3 型をとる。Arrow は 1 列に
   文字列と数値と配列を混ぜられないので、`answer_text`（表示用）・`answer_number`・
   `answer_list` に分けた。**`qa.json` 側は `answer` 1 本のまま**で、採点はそちらを使う。
5. **PNG と PDF は LFS。** 合わせて 647 MiB。LFS に入れないと HF Hub の
   pre-receive フックが弾く。JSON/JSONL/Markdown は差分が読めるよう LFS に入れない。
6. **ライセンスの法文は転記しない。** CC BY 4.0 の legalcode は 7,000 語超あり、
   手で写すと誤記が入りうる。誤記のあるライセンス本文は参照リンクより害が大きいので、
   CC 自身が推奨する「表示＋正式な法文への参照」の形を採る。
7. **学習・蒸留の禁止は「告知」として書き、ライセンス条件にはしない。** 理由と文面は §7。
8. **検索評価セットは別のデータセットにする**（2026-10-08）。理由は 3 つ。
   (a) 本体は PDF とページ画像で 846 MiB あり、**検索だけ試す人にそれを引かせる理由が無い**
   （評価セットは JSONL 4 本・18.9 MiB）。(b) 1 枚のカードに「読み取りの説明」と「検索の説明」が
   同居して長く、どちらの利用者にも読みにくい。(c) HF のデータセットビューアと `task_categories`・
   `tags` が**リポジトリ単位**なので、分けたほうが検索で見つかる。
   **ローカルの置き場所は `dataset/search/` のまま**にした——`yakkan eval --search-run` の既定パス、
   `docs/evaluation.md`・`docs/search_query_plan.md` の参照、`datacard` の §7 がすべてそこを見ており、
   動かす利得が無い（`dataset/search/` を「別リポジトリの作業コピー」と見なす）。
9. **カードは英語面＋日本語面の二層にする**（2026-10-09。姉妹プロジェクト
   `contracts/`（`cvusk/japanese-contract-document-understanding`）の公開面と設計を揃えた）。
   HF の閲覧者は日本語話者に限らないので、**英語面を先に置き、日本語面（読み方）を続ける**。
   `pretty_name` と `LICENSE` の見出しと BibTeX の `title` は英語名（`PRETTY_NAME_EN` /
   `SEARCH_PRETTY_NAME_EN`）、帰属の最小形は日本語名（`PRETTY_NAME`）を使う。
   frontmatter も contracts と同じキー構成（`multilinguality` / `annotations_creators` /
   **`source_datasets`**。検索側は `extended|<本体の repo_id>` で派生元を申告する）。
   揃えていないのは次の 3 点で、いずれも意図的である。
   (a) **`default: true`** を既定 config に付ける（contracts には無いが HF 仕様で有効）。
   (b) **素朴な検索器 3 系統のベースライン表**（`How hard is it?`）は insurance 側だけが持つ。
   (c) 検索側の `LICENSE` に **`NOT A REAL INSURANCE POLICY`** を残す（実在の約款と
   誤解されると害が大きいため。contracts の検索側 LICENSE には無い）。

## 3. データセットビューアで読める config

各リポジトリのカード（`dataset/README.md` と `dataset/search/README.md`）の frontmatter で
宣言している。**`datasets` で実際に読めることを確認済み**
（2026-10-05・datasets 5.0.1 / pyarrow 25.0.1。2026-10-08 に分離後の 2 枚で再確認）。

文書本体（`cvusk/japanese-insurance-document-understanding`）：

| config | ファイル | 行数 | 列数 |
|---|---|---:|---:|
| `documents`（既定） | `documents.jsonl` | 113 | 14 |
| `qa` | `qa.jsonl` | 5,085 | 14 |

検索評価セット（`cvusk/japanese-insurance-document-understanding-retrieval`）：

| config | ファイル | 行数 | 列数 |
|---|---|---:|---:|
| `passages`（既定） | `passages.jsonl` | 9,456 | 15 |
| `queries` | `queries.jsonl` | 8,824 | 13 |
| `qrels` | `qrels.jsonl` | 25,435 | 3 |

**config の `path` はそのリポジトリ内の相対パスである。** 分離前は本体のカードが
`search/passages.jsonl` を宣言していたが、**本体には上げないファイル**なので
config ごと壊れる。`tests/unit/test_export.py` の
`test_cardは検索評価セットを別データセットとして案内する` がこれを固定している。

**config にしていないもの**：`*/elements.jsonl`（1 行 1 要素だが bbox が入れ子で列の型が
深く、ビューアの型推論を通す価値より壊れる危険が大きい）、`*/source.json`・`layout.json`・
`answer.json`（入れ子が深く表形式にならない）。いずれも**ファイルとしては配布している**ので
`huggingface_hub.snapshot_download` で取れる。

`queries` の `filters` は、行ごとにキーの組み合わせが 3 通りある
（空 / `issuer`+`product_name` / `genre`+`issuer`+`product_name`）ため
`datasets` が `Json` 型と推論する。読めるが構造化列にはならない。
**`search/queries.jsonl` は採点の入力でもあるので、見え方のためにスキーマを変えない。**

### 検証のしかた

`datasets` は本体の依存に入れていない（配布の検査にしか使わない）。使い捨ての venv で確かめる。

```bash
uv venv /tmp/hfcheck --python 3.12
VIRTUAL_ENV=/tmp/hfcheck uv pip install "datasets>=3"
/tmp/hfcheck/bin/python - <<'PY'
from datasets import get_dataset_config_names, load_dataset
for root in ("dataset", "dataset/search"):        # 2 つのリポジトリぶん
    names = get_dataset_config_names(root)        # README の configs を解釈させる
    print(root, names)
    for n in names:
        print(" ", n, len(load_dataset(root, n, split="train")))
PY
```

## 4. 公開の手順（人間が実行）

### 4.1 事前条件

**上から順に、すべて満たしてから公開する。**

| # | 条件 | 確かめ方 |
|---|---|---|
| 1 | `make check` が通る | `make check`（ruff ＋ pytest ＋ manifest ＋ データカードの鮮度） |
| 2 | `ready` が全件 | `uv run yakkan manifest check` → `ready 113/113` |
| 3 | カードが現状と合っている | `uv run yakkan datacard check` |
| 4 | **架空性の最終確認**（`HITL_TODO.md` H2） | **人間**。機械検査は `TASK.md` §7.1。30 content 時点の確認以降に足した 70 content は未確認 |
| 5 | **非転載の最終確認**（`HITL_TODO.md` H3） | **人間**。同上 |
| 6 | ライセンスが決まっている | CC BY 4.0（`TASK.md` T11・2026-10-05 決定）。`dataset/LICENSE` に出ている |
| 7 | **学習・蒸留の禁止が成果物に出ている** | `uv run pytest tests/unit/test_export.py -k 学習` が緑（§7）。`dataset/LICENSE` と `dataset/README.md` の両方に出る |
| 8 | **検索評価セット側の配布物が揃っている** | `dataset/search/` に `README.md`・`LICENSE`・`SHA256SUMS` がある（`yakkan export` が書く） |

**4 と 5 は AI が代わりに判断しない。** 公開は取り消しが効かない（削除してもキャッシュ・
フォーク・索引に残りうる）ので、ここを飛ばさない。

### 4.2 リポジトリを作る（**2 つ**）

```bash
pip install -U "huggingface_hub[cli]"
hf auth login                                   # 書き込み権のあるトークン

hf repo create cvusk/japanese-insurance-document-understanding --repo-type dataset --private
hf repo create cvusk/japanese-insurance-document-understanding-retrieval    --repo-type dataset --private
```

**コマンド名は `huggingface_hub` の `hf` CLI（旧 `huggingface-cli`）**。
本ファイルの `hf ...` は 2026-10-05 に `hf <command> --help` で実物を確認した
（`repo` は `repos` の別名、`--repo-type` は `--type` の別名）。

**まず private で作る。** ビューアとカードの見え方を確認してから public にする（§4.5）。

### 4.3 アップロード（本体は **2 段に分ける**）

**`.gitattributes` を先に単独で上げる。** `hf upload` は LFS に入れるかどうかを自分で
決めず、ファイルのパス・サイズ・先頭サンプルを Hub の `preupload` エンドポイントに送って
**Hub に判定させる**（`huggingface_hub/_commit_api.py` の `_fetch_upload_modes`。
`.gitignore` は payload で送られるが **`.gitattributes` は送られない**）。つまり
Hub はその時点でリポジトリに載っている `.gitattributes` を見るので、
データと同じコミットで初めて上げると**その回の判定には間に合わない**。
HF が新規リポジトリに置く既定の `.gitattributes` は `*.png` / `*.pdf` を含まない。

```bash
cd insurance-contracts

# ① LFS の宣言とカードだけを先に上げる
hf upload cvusk/japanese-insurance-document-understanding \
  dataset . \
  --repo-type dataset \
  --include ".gitattributes" "README.md" "LICENSE" \
  --commit-message "LFS の宣言とデータセットカード"

# ② 残りを全部上げる（render.html と search/ は除外）
hf upload cvusk/japanese-insurance-document-understanding \
  dataset . \
  --repo-type dataset \
  --exclude "*/render.html" "search/*" \
  --commit-message "yakkan-synth v7: 113 docs / 1,437 pages / 5,085 QA"
```

- 第 1 引数が**ローカルの** `dataset/`、第 2 引数が**リポジトリ内の**配置先（`.` = 直下）。
- ② は 845.8 MiB・2,235 ファイル。LFS 対象は **PNG 1,437 件と PDF 113 件**（計 647 MiB）。
- **`--exclude "search/*"` を忘れない。** 入れてしまうと本体に評価セットの重複が載り、
  本体のカードが宣言していない config のファイルが混ざる（消すには別コミットが要る）。
- 失敗したら同じコマンドを再実行する（アップロード済みは飛ばされる）。
- 上げたあと `hf repo ls` の storage 欄で LFS に乗ったかを確かめる。
  regular blob のまま入っていたら `.gitattributes` が先に載っていない。

次に**検索評価セットを別のリポジトリへ**上げる。`dataset/search/` の直下がそのまま
リポジトリの直下になる。LFS 対象が無いので 2 段に分ける必要は無い。

```bash
hf upload cvusk/japanese-insurance-document-understanding-retrieval \
  dataset/search . \
  --repo-type dataset \
  --commit-message "yakkan-synth search v7: 9,456 passages / 8,824 queries / 25,435 qrels"
```

除外が効いているかは、アップロード前にローカルで確かめられる（実際に `upload` が使う関数）。

```python
from huggingface_hub.utils import filter_repo_objects
from pathlib import Path

root = Path("dataset")
rel = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
kept = list(filter_repo_objects(rel, ignore_patterns=["*/render.html", "search/*"]))
print(len(rel), "→", len(kept))  # render.html 113 件と search/ 7 件だけが落ちる
```

### 4.4 版を上げるとき

`dataset_version`（`yakkan/manifest.py` の `DATASET_VERSION`）を上げ、
`export` → `manifest update` → `datacard update` を回してから同じ `upload` を実行する。
**2 つのリポジトリは同じ版で揃える**（両方のカードが同じ `dataset_version` を出す）。
**HF 側にリビジョンのタグを打つ**と利用者が版を固定できる。

```bash
hf repo tag create cvusk/japanese-insurance-document-understanding v7 --repo-type dataset
hf repo tag create cvusk/japanese-insurance-document-understanding-retrieval    v7 --repo-type dataset
```

ローカル git のタグ（`dataset-v7`）は別物で、こちらも**人間が打つ**（`TASK.md` T8）。

### 4.5 公開後の確認

1. カードが崩れずに出ているか（frontmatter が本文に漏れていないか）。**両方のリポジトリ。**
2. **データセットビューアが全 config で動くか**（本体 2 件・検索 3 件）。動かない config が
   あれば `configs:` の `path` と実ファイルを突き合わせる。
3. `README.md` のライセンス表示が `cc-by-4.0` になっているか（両方）。
4. `load_dataset("cvusk/japanese-insurance-document-understanding", "qa")` と
   `load_dataset("cvusk/japanese-insurance-document-understanding-retrieval", "queries")` が通るか。
5. **互いへのリンクが生きているか**（本体 → 検索、検索 → 本体）。
   片方だけ public にするとリンクが 404 になるので、**public にするのは 2 つ同時**。
6. 本体に `search/` が混ざっていないか（`hf repo ls` で確認）。
7. 問題がなければ public にする。

```bash
hf repo settings cvusk/japanese-insurance-document-understanding --repo-type dataset --no-private
hf repo settings cvusk/japanese-insurance-document-understanding-retrieval    --repo-type dataset --no-private
```

## 5. GitHub での配布（`TASK.md` T7 のもう半分）

`dataset/` は**リポジトリにはコミットしない**（`.gitignore` 済み・`specs/batch_*.yaml` から
再生成できる）。GitHub で渡すなら **Releases に添付**する。

```bash
cd insurance-contracts
tar --exclude='*/render.html' -czf ../yakkan-synth-v7.tar.gz dataset
# 参考：PNG を除くと 251 MiB、PNG だけで 614 MiB
gh release create dataset-v7 ../yakkan-synth-v7.tar.gz \
  --title "yakkan-synth dataset v7" \
  --notes "113 docs / 1,437 pages / 5,085 QA。詳細は dataset/data-card.md。CC BY 4.0。"
```

GitHub Releases の添付は 1 ファイル 2 GiB まで。864.6 MiB は gzip で収まるが、
**正本は Hugging Face 側**とし、GitHub は控えとして扱う（ビューアも版管理も HF のほうが強い）。

**控えは 1 つの tar にまとめる**（`dataset/search/` も入る）。HF では 2 つのリポジトリに
分けているが、控えは「ローカルの `dataset/` をそのまま固める」ものなので分けない。

## 6. やらないこと

- **AI はアップロードもタグ付けもしない**（`TASK.md` T1・T7）。
- **本体のリポジトリに `search/` を上げない**（§4.3。カードが宣言していない config になる）。
- **ローカルの `dataset/search/` を別の場所へ動かさない**（§2-8）。
- `dataset/` を手で編集しない。配布物の文面を直すときは
  `yakkan/export.py` のテンプレートを直して `export` を回す。
- ライセンスの法文を手で転記しない（§2-6）。
- **学習・蒸留の禁止を CC BY 4.0 の「条件」として書かない**（§7.2。書くと CC BY 違反になる）。
- **ライセンスを CC BY 4.0 以外に差し替えない**（人間の決定事項。§7.2 の注記）。
- `search/queries.jsonl` のスキーマをビューアの見え方のために変えない（§3）。

## 7. 学習・蒸留の禁止の書き方

### 7.1 なぜ書くか

**本データセットの文章・QA・図の説明は Claude（Anthropic）の Output である。**
生成は Claude Code セッション内で完結しており（CLAUDE.md §1「外部 LLM API は使わない」）、
Anthropic の Usage Policy は次を禁じている。

> "Utilization of inputs and outputs to train an AI model (e.g., "model scraping" or
> "model distillation") **without prior authorization from Anthropic**"
> — <https://www.anthropic.com/legal/aup>（2025-09-15 発効）

「競合モデルに限る」という限定が**付いていない**のが要点で、用途が読み取り専用の小さなモデルでも
文面上は許可の対象に入る。受領者がこれを知らずに学習に使う事故を防ぐため、成果物に明記する。

### 7.2 なぜ「告知」であって「ライセンス条件」ではないか

**CC BY 4.0 は下流の受領者に追加の制限を課すことを禁じている**（第 2 条(a)(5)(B)
「No downstream restrictions」）。したがって `license: cc-by-4.0` を宣言したまま
「学習禁止」を**付与条件として**書くと、それ自体が CC BY 違反になる。

そこで次の形を採る。

| | 書き方 |
|---|---|
| ライセンス | **CC BY 4.0 のまま**（`license: cc-by-4.0`）。条件を足さない |
| 禁止 | **告知**として書く。「Anthropic Usage Policy 由来の制限であり、同ポリシーの適用を受ける者を縛る」と出どころを明示し、「これはライセンス条件ではない」と明記する |

拘束の相手が違うことも押さえておく。Anthropic の規約が縛るのは **Anthropic の顧客**であって、
データセットの受領者そのものではない。受領者が Claude の利用者であればその人に同じ制限がかかるが、
それはその人と Anthropic のあいだの問題である。**告知はその事実を伝えるためにある。**

> 禁止を本当に拘束力のある条件にしたい場合は、CC BY 4.0 をやめて独自ライセンス
> （`license: other` ＋ `license_name` / `license_link`）に差し替えるしかない。
> **これは人間の決定事項**（CLAUDE.md §0.2）で、2026-10-06 時点では「CC BY 4.0 ＋ 告知」を採っている。

### 7.3 どこに書くか（正本は生成器）

`dataset/` は生成物なので手で書かない（CLAUDE.md §0.4-3）。**文面の正本は 5 か所**。

| 出力 | 正本 | 節 |
|---|---|---|
| `dataset/LICENSE` | `yakkan/export.py` の `LICENSE_NOTICE` | `NOT FOR TRAINING AI MODELS`（英語） |
| `dataset/README.md`（HF のカード） | `yakkan/export.py` の `CARD` | 英語面に `## ⚠ Not for training AI models`（**`What it is for` より前**）、日本語面に `## ⚠ AI モデルの学習・蒸留には使えない` |
| `dataset/search/LICENSE` | `yakkan/export.py` の `SEARCH_LICENSE_NOTICE` | 同じ `NOT FOR TRAINING AI MODELS`（短縮形） |
| `dataset/search/README.md`（検索側のカード） | `yakkan/export.py` の `SEARCH_CARD` | 両面に同じ節を同じ位置で置く |
| `dataset/data-card.md` | `yakkan/datacard.py` の §12 | 「ライセンスと配布」の 2 番目の箇条 |

リンク先の URL は `yakkan/export.py` の `AUP_URL` 1 か所に置き、各出力へ流す。
**告知の本文も 1 か所**（`NO_TRAINING_EN` / `NO_TRAINING_JA` / `FICTITIOUS_JA`）で、
2 枚のカードが同じ定数を埋め込む。片方だけ直して食い違う事故を防ぐためである
（定数名は姉妹プロジェクト contracts の `NO_TRAINING_EN` / `NO_TRAINING_JA` に合わせた）。

### 7.4 必ず併記すること

**「評価は学習ではない」を同じ節に書く。** これを落とすと、このデータセットが作られた目的
（読み取り・検索・エージェントの評価）まで禁じられたように読める。対象外であることを明記するのは：

- 評価・ベンチマーク・採点
- テストフィクスチャ・回帰データ
- few-shot の実例
- 推論時の検索コーパス（RAG）

**除かれるのはモデルの重みを更新する用途だけ**である。

### 7.5 消えないようにする

文面は `tests/unit/test_export.py` の 2 件が固定している（CLAUDE.md の「基準は機械に落とす」）。

```bash
uv run pytest tests/unit/test_export.py -k 学習
```

- `test_licenseが学習と蒸留の禁止を明記する`：見出し・TRAIN / FINE-TUNE / DISTILL / LLM / VLM・
  `AUP_URL`・`EVALUATION IS NOT TRAINING`・「告知であって条件ではない」・`2(a)(5)(B)`
- `test_cardが学習と蒸留の禁止を目立つ節で明記する`：見出しが**ライセンス節より前**にあること、
  「評価は学習ではない」「告知であってライセンス条件ではない」が入っていること
