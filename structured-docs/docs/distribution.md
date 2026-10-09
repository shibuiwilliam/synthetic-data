# distribution.md — 生成物（`dataset/`）の配布とライセンス表示

> 配布物を触る作業では**着手前に本ファイルを読む**こと。
> **配布の判断と実行は人間が持ち、AI は「生成」と「検査」だけを行う**（CLAUDE.md §0.2・§0.4-10）。
> 基底：`../insurance-contracts/docs/distribution.md`（2026-10-05 に Hugging Face ＋ CC BY 4.0 で
> 配布する決定を得ている先例）。
>
> - 版: 1.0（2026-10-05 新設）
> - **本プロジェクトの配布条件は未決**（`HITL_TODO.md` D2）。コードのライセンスも未決（同 D3）。
>   **決まるまで外部に出さない。** 本ファイルは「決まったら何をどうやるか」と「決まる前にやっておける検査」。
> - **ただし「AI モデルの学習・蒸留には使えない」は配布条件と独立に決まっている**（§6。
>   本文の執筆者が Claude であることに由来し、どのライセンスを選んでも消えない）。

## 1. 何を配るか（決まったときの既定形）

`dataset/` を**そのまま**データセットリポジトリにする。配布物は
`docsynth export` ＋ `manifest update` ＋ `datacard update` の出力だけで、
**手で足すファイルは 1 つも無い**（CLAUDE.md §0.4-3）。

| 内訳 | 役目 |
|---|---|
| `<doc_id>/doc.pdf` | 生成 PDF（テキスト層あり・フォント埋め込み・タグ無し） |
| `<doc_id>/pages/page-*.png` | 150dpi のページ画像 |
| `<doc_id>/source.json` `layout.json` `answer.json` `qa.json` `elements.jsonl` | 正解 |
| `search/passages.jsonl` `queries.jsonl` `qrels.jsonl` | 検索評価セット |
| `manifest.json` | 全文書一覧＋checksums |
| `README.md` | 読み方（配布先のデータセットカード本体にもなる） |
| `data-card.md` | データカード（素性。`docs/data_card.md`） |
| `LICENSE` | 決定したライセンスの全文＋帰属の書き方＋埋め込みフォントの扱い＋**学習と蒸留の禁止（§6）** |
| ~~`<doc_id>/render.html`~~ | **配布しない**（デバッグ用の中間 HTML。正解でも入力でもない） |

`render.html` は `manifest.json` の `artifacts` に載っているので**消さず、アップロード時に除外する**。

## 2. 決まる前にやっておける検査（AI の担当）

- [ ] `docsynth manifest check` と `docsynth datacard check` が通る（鮮度）。
- [ ] `dataset/` に**手編集の痕跡が無い**（checksum 一致）。
- [ ] **埋め込みフォントを実測**して、同梱ライセンス（SIL OFL 1.1 / IPA FL v1.0）と一致することを確認する
      （`layout.renderer.fonts` は「描画に登録した候補」であり、**実際に埋め込まれたものとは違う**。
      `doc.pdf` を pdfplumber で読む）。`CID Type 0C`（CFF）が無いことも併せて確認（V-P4）。
- [ ] 各文書の奥付に disclaimer がある（L13）。**「法的に有効な文書ではない」旨が配布物の
      README とデータカードの両方にある。**
- [ ] **「AI モデルの学習・蒸留には使えない」が `LICENSE`・カード・データカードに出ている**（§6）。
      **「評価は学習ではない」が同じ場所に併記されている**こと。両姉妹はこれをテストで固定している
      （`../insurance-contracts/tests/unit/test_export.py` ・`../contracts/tests/unit/test_publish.py`
      の `-k 学習`）。移植時に一緒に持ってくる。
- [ ] denylist 検査（L08）が全 content で error 0。**ただし「実在しないこと」は機械で保証できない**
      ——架空性の最終確認は人間（`HITL_TODO.md` D5）。
- [ ] 容量と件数をデータカードから拾って配布先の制限と突き合わせる（`pages/*.png` が最大の重量物。
      yakkan の実績では 864.6 MiB のうち 613.7 MiB が PNG）。

## 3. 決まったあとに人間がやること

- 配布先リポジトリの作成とアップロード（AI は実行しない）。
- タグ付け（AI は `manifest.json` と `dataset/README.md` の `dataset_version` で版を表すところまで）。
- ライセンス表示の最終確認（**コード側と生成物側でライセンスが違う**ことを明記する）。

## 4. 未決事項（`HITL_TODO.md`）

| # | 内容 | 先例 |
|---|---|---|
| D2 | 生成物の配布先とライセンス。**5 ファミリーを 1 データセットで配るか、ドメインごとに分けるか**も判断対象 | yakkan・keiyaku とも Hugging Face Datasets ＋ **CC BY 4.0**（keiyaku は 2026-10-06 に決定）。**どちらも学習・蒸留の禁止を告知として併記している**（§6） |
| D3 | コードのライセンス（`pyproject.toml` と親リポジトリ直下 `LICENSE` の食い違い） | keiyaku も同じ食い違いを抱えている（未決） |

## 5. 配らないもの

- 参考にした実在文書（PDF・スクリーンショット・本文メモ）。**そもそもリポジトリに入れない**
  （`docs/reference_structures.md` §0）。配布物に混ざる余地を作らない。
- `content/`（執筆物）を配るかは D2 の一部。**正解 JSON があれば再生成できる**ので、
  既定は「配らない」（リポジトリにはコミットする）。
- `scratch/`・`render.html`・`.venv`。

## 6. AI モデルの学習・蒸留には使えない（配布条件と独立）

**両姉妹で 2026-10-06 に確定した方針。docsynth も同じ形を継承する**
（`../insurance-contracts/docs/distribution.md` §7 ／ `../contracts/docs/publishing.md` §10）。

### 6.1 根拠

生成物の本文・表・図の説明・QA は、Claude Code セッション内で **Claude（Anthropic）が書いた
Output** である（CLAUDE.md §1.3「外部 LLM API は使わない」）。Anthropic の Usage Policy は
次を禁じている。

> "Utilization of inputs and outputs to train an AI model (e.g., "model scraping" or
> "model distillation") **without prior authorization from Anthropic**"
> — <https://www.anthropic.com/legal/aup>（2025-09-15 発効）

**「競合モデルに限る」という限定が付いていない**のが要点で、用途が読み取り専用の小さなモデルでも
文面上は許可の対象に入る。**この制約は配布ライセンス（D2）の選択とは独立で、どれを選んでも消えない。**

### 6.2 「告知」として書き、ライセンス条件にはしない

CC BY 系は下流の受領者に追加の制限を課すことを禁じている（**CC BY 4.0 第 2 条(a)(5)(B)**
「No downstream restrictions」）。`license: cc-by-4.0` のまま禁止を**付与条件として**書くと
それ自体が CC BY 違反になるため、両姉妹は次の形を採っている。

| | 書き方 |
|---|---|
| ライセンス | CC BY 4.0 のまま。条件を足さない |
| 禁止 | **告知**。「Anthropic Usage Policy 由来の制限であり、同ポリシーの適用を受ける者を縛る」と出どころを明示し、「これはライセンス条件ではない」と明記する |

拘束力のある条件にしたい場合は、CC BY をやめて独自ライセンス（`license: other` ＋
`license_name` / `license_link`）に差し替えるしかない。**これは人間の決定事項**で、
D2 を決めるときに**併せて判断する**（既定は両姉妹に揃えて「CC BY 4.0 ＋ 告知」）。

### 6.3 必ず併記すること

**「評価は学習ではない」を同じ節に書く。** 落とすと、このデータセットが作られた目的
（読み取り・検索・エージェントの評価）まで禁じられたように読める。対象外であることを明記するのは
評価・ベンチマーク・採点／テストフィクスチャ・回帰データ／few-shot の実例／推論時の検索コーパス（RAG）。
**除かれるのはモデルの重みを更新する用途だけ**である。

### 6.4 実装するときの置き場所

P0 で姉妹から移植するときに、**文面の定数とテストも一緒に持ってくる**。

| 出力 | 正本 |
|---|---|
| `dataset/LICENSE` | `docsynth/export.py`（または `publish.py`）の `NO_TRAINING_EN` |
| `dataset/README.md`（カード） | 同 `NO_TRAINING_JA`。見出しは**ライセンスの案内より前**に置く |
| `dataset/data-card.md` | `docsynth/datacard.py` の「ライセンスと配布」節 |
| リンク先 URL | `AUP_URL` の 1 か所に置き、全出力へ流す |
