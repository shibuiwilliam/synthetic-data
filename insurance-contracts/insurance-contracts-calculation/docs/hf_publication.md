# Hugging Face での公開（T16・`HITL.md` H11）

- 日付: 2026-10-05
- 決定: `HITL.md` H11「`dataset/` を Hugging Face で公開する」（利用者の指示）
- 実装: `src/insurance_contracts_calculation/export/huggingface.py`、
  CLI `icc package <dataset> --format hf`、テスト `tests/unit/test_huggingface.py`
- **AI は組むところまでをやる。アップロードは人が行う**（`HITL.md` H4-b の後半は今も効いている）

## 1. 何をしたか

`dataset/`（生成物。手で直さない）から、**Hugging Face に上げられる形のリポジトリを組む**
仕掛けを作った。`dataset/` そのものを上げるのではない。理由は 3 つある。

1. `render.html`（42MB）は本体が「デバッグ用・**配布対象外**」と定めている。
2. 描画ごとの `source.json`（135MB）は同じ文書の `policy.json` と**バイト単位で同一**な重複である。
3. `dataset/` は `icc batch` の作業用の出力先で、`icc datacard check` がそこを測る。
   リポジトリの付属物（`.gitattributes`・`views/`・HF 用の `README.md`）を混ぜると、
   カードの測り方と衝突する。

## 2. 組み方

```bash
cd insurance-contracts-calculation
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib

PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli \
    package dataset --format hf --out dist/hf --version v2.3 \
    --license cc-by-4.0 --repo-id cvusk/japanese-insurance-document-understanding-calculation
```

| 引数 | 既定 | 意味 |
|---|---|---|
| `--license` | `cc-by-4.0`（**仮決め**） | データセットカードの `license:` タグと `LICENSE` の中身 |
| `--repo-id` | `cvusk/japanese-insurance-document-understanding-calculation` | カードの `load_dataset()` の例文に出る |
| `--no-png` | （付けない） | ページ画像を外す。**2,064MB → 341MB** |
| `--version` | `v2.0` | 配布物の版。カードと `index.json` に出る |

`dist/` は `.gitignore` 済みである（`dataset/` から作り直せる生成物）。

## 3. 出来るもの

```
dist/hf/
├── README.md                 # データセットカード（YAML frontmatter つき）
├── LICENSE                   # 選んだライセンス＋フォントと架空性の断り書き
├── .gitattributes            # LFS（PDF と PNG だけ）
├── data-card.md              # 詳しいデータカード（dataset/ から複写）
├── index.json                # 文書の一覧・合計・カナリア・全ファイルのハッシュ
├── _run_report.json          # 生成時の記録（作れなかった組も載っている）
├── licenses-fonts/           # 埋め込みフォントのライセンス本文＋対応表
├── views/                    # 機械可読ビュー（JSONL）
│   ├── documents.jsonl       # ← HF の既定の config
│   ├── pages.jsonl
│   ├── rules.jsonl
│   ├── tasks.jsonl
│   └── cases.jsonl           # ★正解（既定にしない）
└── documents/<doc_id>/       # 原本（policy.json・PDF・layout.json・pages・calc）
```

## 4. HF の作法で引っかかったところ

**「ファイルを置く」だけでは足りない。** 実装で踏んだ落とし穴を残す。

| 落とし穴 | どうなるか | 対処 |
|---|---|---|
| frontmatter が無い | ライセンスが `unknown` と表示され、言語・課題の索引に載らない | `_frontmatter()` が書く |
| `configs` が無い | `load_dataset()` が入れ子の木を読もうとして失敗する | `views/*.jsonl` を宣言する |
| **`configs` を名前で並べる** | 先頭が既定の config になるので、**`cases`（正解）が既定になる** | `VIEW_ORDER` で順序を固定し、`documents` に `default: true` を付ける |
| `pretty_name` にコロンがある | **YAML が壊れる**（`mapping values are not allowed here`） | 値を必ず引用する（`_yaml()`） |
| JSON を LFS に入れる | データセットビューアが中身を見せられなくなる | LFS は `*.pdf` と `*.png` だけ。実測で 10MB 超のファイルは 1 件も無い |
| `expected` を素の列にする | 真偽・整数・日付・`None` が混ざり、`datasets` の型推論が壊れる | `expected_json` の文字列にする。元の型は `calc/cases.jsonl` に残す |
| `index.json` 自身をハッシュする | 書き込んだ時点で中身が変わり、**記録が嘘になる** | `skip=("index.json",)` |

## 5. 公開前に確かめたこと（実測・2026-10-05）

### 5.1 架空性（公開を止める要因は無い）

| 検査 | 範囲 | 結果 |
|---|---|---|
| 実在の保険会社・ブランド名 | `dataset/` の全テキストファイル **5,991 件** × 本体 `denylist.txt` **154 語** | **0 件** |
| URL のドメイン | `policy.json` 100 件 | `example.jp`・`www.example.jp`・`example.co.jp`・`www.example.co.jp`・`mypage.example.jp`・`members.example.co.jp`・`group.example.jp` のみ（すべて予約済みの例示ドメイン） |
| 電話番号 | 同上 | `0120-000-000` のみ（275 件） |
| メールアドレス | 同上 | **0 件** |

再現:

```bash
grep -v '^#' ../yakkan/lint/denylist.txt | grep -v '^[[:space:]]*$' > /tmp/dl.txt
find dataset -type f \( -name '*.json' -o -name '*.jsonl' -o -name '*.py' -o -name '*.md' -o -name '*.html' \) \
  -print0 | xargs -0 grep -l -F -f /tmp/dl.txt | wc -l      # 0 であること
grep -ohE 'https?://[A-Za-z0-9.-]+' dataset/*/policy.json | sort -u
grep -ohE '0[0-9]{1,4}-[0-9]{1,4}-[0-9]{3,4}' dataset/*/policy.json | sort -u
```

### 5.2 フォントのライセンス（**義務がある**）

PDF には**フォントがサブセットで埋め込まれている**（`pdfplumber` で `ABCDEF+Noto-Serif-JP` の
形の名前を確認した）。PDF を配るなら条件に従う義務がある。

| フォント | ライセンス | 埋め込みと再配布 |
|---|---|---|
| Noto Sans JP / Noto Serif JP | SIL Open Font License 1.1 | 文書への埋め込みと、その文書の再配布を許す |
| IPAex ゴシック／明朝 | IPA フォントライセンス v1.0 | 「デジタル・ドキュメント・ファイル」への埋め込みと再配布を許す |

本文は `licenses-fonts/` に同梱する（本体の `assets/fonts/` から複写。本体は変更しない）。
PNG はラスタライズ済みでフォントのデータを含まない。

### 5.3 容量とファイル数

| 構成 | 容量 | 備考 |
|---|---|---|
| `dataset/` そのまま | 2,241MB / 5,991 ファイル | — |
| 公開用（既定） | **2,064MB** | `render.html` 42MB と `source.json` 135MB を外した |
| 公開用（`--no-png`） | **341MB** | PNG は PDF から `pdftoppm -r 150 -png` で作り直せる |

10MB を超えるファイルは **1 件も無い**（最大 1.11MB の `layout.json`）。

## 6. 人がやること（AI はやらない）

1. **ライセンスを確定する**（`HITL.md` §1 の H11-a）。既定の `cc-by-4.0` は**仮決め**である。
   変えるなら `--license <タグ>` を付けて組み直す（数分）。
2. **公開形態を決める。** 正解を同梱するので、HF の **gated**（規約同意の上で配る）も選べる。
   これはリポジトリの中身とは独立に HF の設定画面で切り替えられる。
3. **アップロードする。**

```bash
hf auth login
hf upload cvusk/japanese-insurance-document-understanding-calculation dist/hf --repo-type dataset
# もしくは private で先に作ってから中身を確かめる
hf repo create cvusk/japanese-insurance-document-understanding-calculation --repo-type dataset --private
hf upload cvusk/japanese-insurance-document-understanding-calculation dist/hf --repo-type dataset
```

4. **上げたあとに確かめる。**

```python
from datasets import load_dataset

load_dataset("cvusk/japanese-insurance-document-understanding-calculation")  # documents が既定で読める
load_dataset("cvusk/japanese-insurance-document-understanding-calculation", "cases")  # 正解のビュー
```

## 7. 正解を公開することの扱い

`HITL.md` H4 (c) で「**正解も含めて配る**」と決まっている。そのうえで入れたもの:

- カード冒頭の警告（「学習データに使わないでください」）。
- **カナリア文字列**。内容から決める決定的な値で（`uuid` も時刻も使わない）、
  学習データを grep すればこのデータセットの混入が分かる。版ごとに変わる。
- 採点時に渡す範囲を機械的に絞る手順（`icc export`。`DESIGN.md` §10.3 軸 A）。
- 作り直し方（各文書の `calc/manifest.json` の `seed` と `profile`）。
- `cases`（正解）を**既定の config にしない**こと。

## 8. 作り直すとき

```bash
make check                                  # ruff + テスト + データカードの鮮度
PYTHONPATH=src uv run --project .. python -m pytest tests/unit/test_huggingface.py -q
```

`dataset/` に文書を足したら、**データカードを更新してから**組み直す
（公開用リポジトリは `dataset/data-card.md` を複写するだけなので、古いカードが混ざる）。

```bash
PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli datacard update dataset
PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli \
    package dataset --format hf --out dist/hf --version <版>
```
