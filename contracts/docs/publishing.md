# docs/publishing.md — データセットの公開（Hugging Face Hub）の仕様

> `dataset/` を **Hugging Face Hub のデータセットリポジトリとしてそのまま公開できる形**に整える層の仕様。
> 実装は `keiyaku/publish.py`、宣言は **`specs/publish.yaml`**、CLI は `keiyaku publish [update|check]`、
> アップロードは `scripts/upload_hf.py`、テストは `tests/unit/test_publish.py`。
>
> - 版: 1.0（2026-10-05 新設）
> - 読む順：本ファイル → `docs/data_card.md`（カードの中身）→ `docs/evaluation.md`（正解の形）
> - **ライセンスと公開可否は人間の決定事項**（`CLAUDE.md` §0.2-1）。AI は `specs/publish.yaml` の
>   `license.id` を勝手に埋めない。未決のまま `publish update` は通るが、**アップロードは拒否される**（§7）。

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

## 3. `dataset/README.md`（= Hugging Face データセットカード）

**README.md の所有者は `keiyaku/publish.py` である**（以前は `keiyaku/export.py` が持っていた。
`keiyaku export` は `publish.write_readme()` を呼ぶだけになった）。構成：

| 位置 | 中身 | 出所 |
|---|---|---|
| frontmatter | `license` / `language` / `pretty_name` / `task_categories` / `task_ids` / `tags` / `size_categories` / `annotations_creators` / `source_datasets` / `multilinguality` / **`configs`** | `specs/publish.yaml` ＋ 実測（`size_categories` は文書数から出す）。`configs` は `keiyaku/publish.py` の `CONFIGS`（7 件）が正本で、**`publish update` が同じ実行でその 7 件を作る／既に在ることを保証する** |
| 英語の節 | 要約・用途と非用途・構成・7 つの config の表・ライセンス・引用 | 固定文 ＋ 実測 |
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
`configs` から直接 glob で指す（§3）。

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
| `dataset/LICENSE` | 生成物（PDF・JSON・PNG）のライセンス本文への案内と著作権表示 | `license.id` が決まっているときだけ作る |
| `dataset/licenses/LICENSE-NotoSansJP.txt`・`LICENSE-NotoSerifJP.txt` | 同梱フォントのライセンス本文（`assets/fonts/` からコピー） | **PDF に実際に埋め込まれていたフォント**だけ入れる（`datacard.embedded_fonts()` の実測） |
| `dataset/licenses/NOTICE.md` | 「PDF には次のフォントのサブセットが埋め込まれている／本体の文章は全文オリジナルで、実在のひな型を転載していない」 | 常に作る |
| `dataset/SHA256SUMS` | 配布するファイルの SHA256（`exclude` に当たるものと自分自身を除く） | 常に作る |

`manifest.json` の `checksums` は 1 文書 5 ファイルぶんしか無く、PNG と jsonl を覆っていない。
ダウンロード側が全量を検証できるように `SHA256SUMS` を別に作る。

## 7. 手順（公開するとき）

```
uv run keiyaku export              # 一次資料と検索評価セットとデータカードを最新にする
uv run keiyaku publish update      # README（カード）・views・.gitattributes・licenses・SHA256SUMS
uv run keiyaku publish check       # 鮮度と、公開をふさいでいる条件（未決のライセンス等）を報告する
uv run python scripts/upload_hf.py               # 何が上がるかを数えるだけ（**既定。通信しない**）
uv run python scripts/upload_hf.py --yes         # 実際に上げる（HF_TOKEN が必要）
uv run python scripts/upload_hf.py --yes --public  # public で作る（**人間が明示したときだけ**）
```

- `scripts/upload_hf.py` は **`license.id` が `undecided` なら実行を拒否する**。
  `publish check` が鮮度の食い違いを報告している場合も拒否する。
- **引数なしが dry-run**（`--yes` を明示しない限り通信しない。`huggingface_hub` も import しない）。
  アップロードには `uv sync --group publish` が要る（既定の `uv sync` には入らない）。
- 既定の可視性は `specs/publish.yaml` の `hub.private`。**最初は private で上げ、
  人が Hub 上で中身を見てから public にする**（取り消せない外向き操作を一段に分ける）。
- 再公開（2 回目以降）は同じコマンドで差分だけが上がる。`hub.revision` にタグ名を入れると
  そのリビジョンに上げる。

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
| U7 | ライセンス（H13）の決定を受けて `specs/publish.yaml` を 1 行直し、`publish update` | カードに条件が出る | **人間の判断待ち** |
| U8 | 実際のアップロード | Hub にデータセットが出る | **U7 のあと** |

## 10. 変えるときの注意

- **views に列を足すときは、Arrow の型が混ざらないかを先に確かめる**（§4）。混ざると Viewer が落ちる。
  `scripts/verify_views.py` が全列の型を走査する。
- frontmatter のキーを足すときは Hub の仕様（Dataset Cards / `configs`）に合わせる。
  **`configs` が指すパスは必ず実在を確かめてから書く**（存在しないパスを書くと Viewer が落ちる）。
- `dataset/` に新しいディレクトリを足したら **`keiyaku clean --stale` の保護一覧**
  （`keiyaku/cli.py` の `PROTECTED_DIRS`）に入れる。入れないと掃除で消える。
