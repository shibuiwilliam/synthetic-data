# docs/hf_publish.md — Hugging Face 公開形の仕様

`dataset/`（生成物）を Hugging Face のデータセットとして配布するための**公開形**を、
実測だけから決定的に組み立てる仕様。実装は `src/contracts_calculation/export/hf.py`、
CLI は `contracts-calc publish`、テストは `tests/test_hf_publish.py`。

> **`dataset/` を直接アップロードしてはいけない。** 公開してはいけないものが入っている（§2）。
> 公開形は別ディレクトリ（既定 `dist/hf/`）に**許可リスト方式**で組み立てる。

---

## 1. なぜ別ディレクトリに組み立てるか

`dataset/` は生成物であり、手で直さない（CLAUDE.md 規則 2）。一方、公開してよいファイルの集合は
作業用データセットと**一致しない**。除外を「アップロード時のオプション」に頼ると、漏れが
事故になる（§2 の 1 は個人情報の漏洩）。そこで、

- **許可リストに挙げたものだけをコピーする**（既定は「出さない」）。
- 組み立てたあとに**公開前ゲート**（§5）を全ファイルに掛け、1 件でも引っかかったら失敗させる。
- 同じ入力なら同じ出力になる（決定的）。`dataset/` は読むだけで、書き換えない。

## 2. 公開しないもの（実測した理由つき）

| 対象 | 実測 | 理由 |
|---|---|---|
| `*/_render/*/render.html` | 102 ファイル・8.2 MB | **全ファイルにローカルの絶対パスとユーザー名が入る**（`@font-face` の `src`）。本体でも「デバッグ用・配布対象外」 |
| `_work/` | 34.6 MB | パッチ済み content の中間生成物。消費者には使い道がなく、本体 `content/` の重複でもある |
| `*/__pycache__/*.pyc` | 200 ファイル・2.1 MB | 実行時の副産物。Python の版に依存する |
| `*/_render/*/source.json` | 100 ファイル・22.3 MB | `contract.json` と**バイト単位で同一**（検査済み）。重複 |
| `*/_render/*/doc.pdf` | 102 ファイル・18.0 MB | 文書直下の `<cid>--<style>.pdf` と**バイト単位で同一**。重複 |

除外の合計は約 85 MB。公開形は約 76 MB になる。

## 3. 公開するもの

出題に渡すもの（`inputs/`）と正解（`answers/`）を**構造で分ける**。評価対象システムに何を渡し、
何を渡さないかは `dataset/README.md` が定めており、その切り分けを公開形でもそのまま見せる。

```
<out>/
├── README.md              # HF データセットカード（YAML frontmatter ＋ 本文）
├── NOTICE.md              # 埋め込みフォントのライセンス表示・架空性・免責
├── .gitattributes         # *.pdf を Git LFS に送る
├── data/                  # load_dataset() 用の平索引（frontmatter の configs で宣言）
│   ├── documents.jsonl    # 1 行 1 文書
│   ├── rules.jsonl        # 1 行 1 ルール
│   ├── tasks.jsonl        # 1 行 1 タスクカード（出題）
│   └── cases.jsonl        # 1 行 1 テストケース（正解。--no-answers では出さない）
├── inputs/<cid>/
│   ├── contract.json      # 契約書（本体スキーマ・`derived` つき）
│   ├── <cid>--<style>.pdf # 紙面
│   ├── layout.json        # bbox・読み順・ページ数（紙面の読み取り正解。計算の答えは含まない）
│   ├── calendar.json      # その文書が使う祝日の固定版
│   └── tasks.jsonl        # 関数名と入出力の契約（出題）
└── answers/<cid>/         # --no-answers で丸ごと省ける
    ├── spec.json          # 計算仕様（唯一の正）
    ├── answer_key.json    # ルールと根拠単位の対応・表現手段・難易度
    ├── patch.json         # 既定の契約書に対して行った追加操作
    ├── manifest.json      # 生成の記録・ゲートの結果・ハッシュ
    ├── cases.jsonl        # テストケース（入力と期待値）
    ├── programs/          # 正解プログラム
    └── tests/             # 同梱 pytest（--impl で提出実装に差し替えられる）
```

`layout.json` は `inputs/` に置く。`contract.json` が構造をすべて明かしているので、
`layout.json` を渡しても計算の答えは漏れない。紙面の読み取りも併せて評価したい利用者のために置く。

## 4. 平索引（`data/*.jsonl`）の決まり

HF は JSONL を Arrow/Parquet に変換するので、**行ごとに形の変わる入れ子を裸で置かない**。
`inputs` や `expected` のような自由形式の値は **JSON 文字列の列**（`*_json`）として持つ。
列の型が行で変わると変換が落ちるためで、利用者は `json.loads` で復元する。

- `documents.jsonl`：`content_id`・`base_content_id`・`doctype`・`profile`・`calc_seed`・
  `generator_version`・`style_id`・`pages`・`page_size_mm`・`renderer`・`n_rules`・`n_cases`・
  `n_tasks`・`patterns`（文字列の配列）・`challenge_type`・`challenge_rule`・`chars`・
  `contract_file`・`pdf_file`・`layout_file`
- `rules.jsonl`：`content_id`・`rule`・`function`・`pattern`・`origin`・`binding`・`n_units`・
  `value_locations`・`modalities`・`difficulty_json`・`has_examples`
- `tasks.jsonl`：`content_id`・`task_id`・`function`・`title`・`kind`・`task_json`（全文）
- `cases.jsonl`：`content_id`・`case_id`・`function`・`kind`・`inputs_json`・`expected_json`・`tags`

## 5. 公開前ゲート（1 件でも引っかかったら失敗）

| ゲート | 検査 |
|---|---|
| P1 許可リスト | 出力の全ファイルが §3 のどれかに該当する（想定外のファイルが 1 つも無い） |
| P2 パスの漏れ | 全ファイルに絶対パス・ホームディレクトリ・実行ユーザー名が無い |
| P3 副産物 | `__pycache__`・`*.pyc`・`_work`・`render.html` が無い |
| P4 実在名称 | `packs/fictional_names.json` の置換前の名称が 1 件も無い |
| P5 対応 | `inputs/` と（`answers/` があれば）`answers/` の文書集合が `dataset/` と一致する |
| P6 カード | frontmatter が必須キー（`license`・`language`・`configs`）を持ち、`configs` の指す
  ファイルが実在する |
| P7 決定性 | 2 回組み立てて全ファイルが一致する（テストで検査） |

P2 は**個人情報の漏洩を止める最後の網**である。弱めない。

## 6. ライセンス（**未決**）

生成物の配布条件は `HITL.md` **HC-3** で依頼中であり、親プロジェクトの H13 に従属する。
決定が入るまで、

- frontmatter は `license: other` ＋ `license_name: undecided`、
- 本文とカードに「**未決。外部配布しない**」と書く、
- `--license <id>` を渡さない限り、この状態のまま組み立てる。

決定が入ったら `--license cc-by-4.0` のように渡す。`NOTICE.md` には**実測した埋め込みフォント**の
ライセンス表示（Noto 系は SIL Open Font License 1.1）を必ず入れる。フォント名は推測せず
`data-card.md` と同じ実測経路（PDF の `/FontDescriptor`）から採る。

## 7. 作り直し

```
contracts-calc publish --data dataset --out dist/hf                 # 未決のまま組み立てる
contracts-calc publish --data dataset --out dist/hf --license cc-by-4.0 --repo-id cvusk/japanese-contract-document-understanding-calculation
contracts-calc publish --data dataset --out dist/hf --no-answers    # 出題の入力だけ
```

`dist/` はコミットしない（`.gitignore`）。`dataset/` から決定的に作り直せる。
アップロードは人間が行う（`HITL.md` HC-1：Git・公開操作は人間の領分）。
