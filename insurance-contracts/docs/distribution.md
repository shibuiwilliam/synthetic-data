# distribution.md — `dataset/` の配布（Hugging Face / GitHub）

> `TASK.md` **T7**（配布手段）・**T11**（ライセンス）の実施手順。
> **配布物を触る作業では着手前に本ファイルを読む。** 配布の判断と実行は人間が持ち、
> AI は**生成と検査**だけを行う（CLAUDE.md §0.2）。
>
> - 版: 1.0（2026-10-05 新設）
> - 配布先: Hugging Face Datasets `cvusk/synthetic-japanese-insurance-documents`
> - ライセンス: **CC BY 4.0**（`TASK.md` T11 で 2026-10-05 に決定）
> - 実装: `yakkan/export.py`（`write_card` / `write_license` / `write_gitattributes` /
>   `write_qa_jsonl` / `write_documents_jsonl` / `remove_retired`）、テスト `tests/unit/test_export.py`

---

## 1. 何を配るか

`dataset/` を**そのまま** Hugging Face のデータセットリポジトリにする。
配布物は `yakkan export` ＋ `manifest update` ＋ `datacard update` の出力だけで、
**手で足すファイルは 1 つも無い**（CLAUDE.md §0.4-3）。

| 内訳 | 実測 | 件数 |
|---|---:|---:|
| `*/pages/*.png`（150dpi ページ画像） | 613.7 MiB | 1,437 |
| `*/layout.json` | 62.9 MiB | 113 |
| `*/elements.jsonl` | 60.2 MiB | 113 |
| `*/source.json` | 47.0 MiB | 113 |
| `*/doc.pdf` | 33.3 MiB | 113 |
| `search/`（検索評価セット） | 18.9 MiB | 4 |
| `*/answer.json` | 14.0 MiB | 113 |
| `*/passages.jsonl` | 9.9 MiB | 113 |
| 直下（カード・LICENSE・manifest・jsonl） | 2.6 MiB | 7 |
| `*/qa.json` | 2.0 MiB | 113 |
| **配布する実体** | **864.6 MiB** | **2,239** |
| ~~`*/render.html`~~ **配布しない** | 14.7 MiB | 113 |

**`render.html` は配布しない。** デバッグ用の中間 HTML で、正解でもなく入力でもない
（`dataset/README.md` にも「配布対象外」と書いてある）。`manifest.json` の `artifacts` には
載っているので**消さず、アップロード時に除外する**（§4）。

### 直下のファイル

| ファイル | 役目 | 生成 |
|---|---|---|
| `README.md` | **Hugging Face のデータセットカード**（YAML frontmatter ＋ 本文） | `yakkan export` |
| `LICENSE` | CC BY 4.0 の表示・帰属の書き方・埋め込みフォントの扱い | `yakkan export` |
| `.gitattributes` | `*.png` と `*.pdf` を Git LFS で追跡 | `yakkan export` |
| `data-card.md` | 規模・内訳・検証結果・制限と偏りの実測（長い版） | `yakkan datacard update` |
| `manifest.json` | 全文書の一覧（**正本**） | `yakkan manifest update` |
| `documents.jsonl` | `manifest.json` を 1 行 1 文書に平らにしたもの | `yakkan export` |
| `qa.jsonl` | 全文書の QA を 1 行 1 問に平らにしたもの | `yakkan export` |

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

## 3. データセットビューアで読める config

`dataset/README.md` の frontmatter で宣言している。**`datasets` で実際に読めることを
確認済み**（2026-10-05・datasets 5.0.1 / pyarrow 25.0.1）。

| config | ファイル | 行数 | 列数 |
|---|---|---:|---:|
| `documents`（既定） | `documents.jsonl` | 113 | 14 |
| `qa` | `qa.jsonl` | 5,085 | 14 |
| `search-passages` | `search/passages.jsonl` | 9,456 | 15 |
| `search-queries` | `search/queries.jsonl` | 8,824 | 13 |
| `search-qrels` | `search/qrels.jsonl` | 25,435 | 3 |

**config にしていないもの**：`*/elements.jsonl`（1 行 1 要素だが bbox が入れ子で列の型が
深く、ビューアの型推論を通す価値より壊れる危険が大きい）、`*/source.json`・`layout.json`・
`answer.json`（入れ子が深く表形式にならない）。いずれも**ファイルとしては配布している**ので
`huggingface_hub.snapshot_download` で取れる。

`search-queries` の `filters` は、行ごとにキーの組み合わせが 3 通りある
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
names = get_dataset_config_names("dataset")        # README の configs を解釈させる
print(names)
for n in names:
    print(n, len(load_dataset("dataset", n, split="train")))
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

**4 と 5 は AI が代わりに判断しない。** 公開は取り消しが効かない（削除してもキャッシュ・
フォーク・索引に残りうる）ので、ここを飛ばさない。

### 4.2 リポジトリを作る

```bash
pip install -U "huggingface_hub[cli]"
hf auth login                                   # 書き込み権のあるトークン

hf repo create cvusk/synthetic-japanese-insurance-documents --repo-type dataset --private
```

**コマンド名は `huggingface_hub` の `hf` CLI（旧 `huggingface-cli`）**。
本ファイルの `hf ...` は 2026-10-05 に `hf <command> --help` で実物を確認した
（`repo` は `repos` の別名、`--repo-type` は `--type` の別名）。

**まず private で作る。** ビューアとカードの見え方を確認してから public にする（§4.5）。

### 4.3 アップロード（**2 段に分ける**）

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
hf upload cvusk/synthetic-japanese-insurance-documents \
  dataset . \
  --repo-type dataset \
  --include ".gitattributes" "README.md" "LICENSE" \
  --commit-message "LFS の宣言とデータセットカード"

# ② 残りを全部上げる（render.html は除外）
hf upload cvusk/synthetic-japanese-insurance-documents \
  dataset . \
  --repo-type dataset \
  --exclude "*/render.html" \
  --commit-message "yakkan-synth v7: 113 docs / 1,437 pages / 5,085 QA / 8,824 queries"
```

- 第 1 引数が**ローカルの** `dataset/`、第 2 引数が**リポジトリ内の**配置先（`.` = 直下）。
- ② は 864.6 MiB・2,239 ファイル。LFS 対象は **PNG 1,437 件と PDF 113 件**（計 647 MiB）。
- 失敗したら同じコマンドを再実行する（アップロード済みは飛ばされる）。
- 上げたあと `hf repo ls` の storage 欄で LFS に乗ったかを確かめる。
  regular blob のまま入っていたら `.gitattributes` が先に載っていない。

除外が効いているかは、アップロード前にローカルで確かめられる（実際に `upload` が使う関数）。

```python
from huggingface_hub.utils import filter_repo_objects
from pathlib import Path

root = Path("dataset")
rel = sorted(str(p.relative_to(root)) for p in root.rglob("*") if p.is_file())
kept = list(filter_repo_objects(rel, ignore_patterns=["*/render.html"]))
print(len(rel), "→", len(kept))  # 2352 → 2239（render.html 113 件だけが落ちる）
```

### 4.4 版を上げるとき

`dataset_version`（`yakkan/manifest.py` の `DATASET_VERSION`）を上げ、
`export` → `manifest update` → `datacard update` を回してから同じ `upload` を実行する。
**HF 側にリビジョンのタグを打つ**と利用者が版を固定できる。

```bash
hf repo tag create cvusk/synthetic-japanese-insurance-documents v7 --repo-type dataset
```

ローカル git のタグ（`dataset-v7`）は別物で、こちらも**人間が打つ**（`TASK.md` T8）。

### 4.5 公開後の確認

1. カードが崩れずに出ているか（frontmatter が本文に漏れていないか）。
2. **データセットビューアが 5 つの config すべてで動くか。** 動かない config があれば
   `configs:` の `path` と実ファイルを突き合わせる。
3. `README.md` のライセンス表示が `cc-by-4.0` になっているか。
4. `load_dataset("cvusk/synthetic-japanese-insurance-documents", "qa")` が通るか。
5. 問題がなければ public にする。

```bash
hf repo settings cvusk/synthetic-japanese-insurance-documents --repo-type dataset --no-private
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

## 6. やらないこと

- **AI はアップロードもタグ付けもしない**（`TASK.md` T1・T7）。
- `dataset/` を手で編集しない。配布物の文面を直すときは
  `yakkan/export.py` のテンプレートを直して `export` を回す。
- ライセンスの法文を手で転記しない（§2-6）。
- `search/queries.jsonl` のスキーマをビューアの見え方のために変えない（§3）。
