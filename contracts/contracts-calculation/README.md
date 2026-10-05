# contracts-calculation — 計算・判定条項と正解プログラムの同時生成

日本語ビジネス契約書の合成データ生成基盤 [`contracts`](../)（keiyaku-synth。以下「本体」）の拡張。
既定の契約書 JSON に **計算や判定を要する条項**（本文・頭書・別紙の表・図）を追加または紐づけし、
その **正解プログラム（Python）** と **ユニットテスト用の評価データ** を、同じ計算仕様から同時に生成する。

用途は、契約書から「計算式・判定式が必要な条項を見つけ、実装し、テストする」システム（以下、評価対象
システム）を採点するための正解データづくりである。読み取り評価そのものを強化する目的も兼ねる。

**計算仕様（CalcSpec）が唯一の正**であり、文言・プログラム・テストはそこから機械的に作る。文言と式を
別々に書かないので三者は構成上ずれず、出力前に機械検査で一致を確かめる。

```
計算仕様 ──┬─▶ 契約書 JSON への追加（条・項・号、頭書の行、別紙の表、図）──▶ 本体で索引の再計算・PDF 化
（唯一の正）├─▶ 正解プログラム（Python）
           ├─▶ テストケース（入力と期待値）＋ pytest
           └─▶ 正解表（どの単位がどのルールの根拠か）
```

運用規則は [`CLAUDE.md`](CLAUDE.md)。

## 本体への依存（重要）

このディレクトリは**単体では動かない**。本体 `contracts/` の直下に置かれていることを前提に、

- 既定の契約書を本体の `../content/<content_id>/` から読む（**読むだけ**。本体は変更しない）、
- lint・索引の再計算・PDF 描画は本体の `keiyaku` CLI を呼ぶ（呼び出しは `base_adapter.py` だけに閉じる）、
- Python 環境も本体の uv プロジェクトを借りる（`uv run --project ..`）。

生成器自身の実行時依存は**標準ライブラリだけ**である（`pyproject.toml` の `dependencies` は空）。
本体を呼ぶのは PDF 化・lint の工程だけで、そこだけ WeasyPrint などの本体の依存が要る。

## セットアップ

本体の手順（`../README.md`）で `uv sync` と Pango の導入を済ませてから、

```bash
cd contracts/contracts-calculation
uv run --project .. python -m pytest -q     # 生成器自身のテスト（約 90 秒）
uv run --project .. ruff check src tests scripts
```

macOS で本体の描画を呼ぶときは `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が要る。
`base_adapter` が自動で付けるので、素手で `uv run keiyaku render` を叩くときだけ注意する。

## コマンド

コンソールスクリプトは登録していない。`python -m contracts_calculation.cli`（表示名 `contracts-calc`）で呼ぶ。

```bash
cd contracts/contracts-calculation
export PYTHONPATH=src

# 追加モード：既定の契約書に計算条項を足して「計算パック」を作る
uv run --project .. python -m contracts_calculation.cli generate \
    --base ../content/ots-0001 --calc-seed 1 --profile standard --out data --png
uv run --project .. python -m contracts_calculation.cli generate \
    --all-bases --calc-seed 1 --profile standard --out data/standard

# 付与モード：既定の契約書にある計算条項へ仕様を紐づける（追加はしない）
uv run --project .. python -m contracts_calculation.cli bind --all-bases --out data_bind --no-render

# 検証・採点・点検
uv run --project .. python -m contracts_calculation.cli verify data/ots-0101
uv run --project .. python -m contracts_calculation.cli eval --data data --oracle   # 満点になることの検査
uv run --project .. python -m contracts_calculation.cli lint-base                   # 既定の契約書の計算条項を点検

# データセットの説明書とデータカード（実測だけから生成する。手で書かない）
uv run --project .. python -m contracts_calculation.cli datasheet --data dataset
uv run --project .. python -m contracts_calculation.cli datacard check --data dataset
uv run --project .. python scripts/verify_data_card.py --data dataset   # 測り方の独立検算

# Hugging Face 公開形を組み立てる（dataset/ は読むだけ。アップロードはしない）
uv run --project .. python -m contracts_calculation.cli publish --data dataset --out dist/hf
```

**`dataset/` をそのままアップロードしてはいけない。** `_render/*/render.html` の全 102 ファイルに
ローカルの絶対パスと実行ユーザー名が入っており、ほかに中間生成物と重複が約 85 MB ある。`publish` が
許可リスト方式で公開形を組み立て、公開前ゲート P1〜P6（絶対パスの漏れ・副産物・実在名称・
カードの妥当性）を全ファイルに掛ける。仕様は `docs/hf_publish.md`。

プロファイルは難易度の軸ごとの出現割合で、`basic` / `standard` / `hard` / `challenge` の 4 種
（`config.py`。`challenge` は欠落・異例をわざと含む）。

## 1 文書の出力（計算パック）

```
<out>/
├── README.md                  # データセットの説明書（datasheet。実測から生成）
├── data-card.md               # データカード（実測から生成）
├── oracle_report.json         # 正解プログラムを提出とみなした採点結果（満点であること）
└── <content_id>/              # 計算パック 1 文書ぶん
    ├── contract.json          # 計算条項を足した契約書（本体スキーマ。PDF の元）
    ├── <content_id>--<style_id>.pdf
    ├── _render/               # 本体の描画の生成物（source.json・layout.json・render.html・doc.pdf）
    └── calc/
        ├── spec.json          # 計算仕様（唯一の正）
        ├── patch.json         # 既定の契約書に対して行った追加操作
        ├── answer_key.json    # 正解表：ルールと根拠単位の対応・表現手段・難易度
        ├── manifest.json      # 生成の記録・選んだパターン・ゲートの結果・ハッシュ
        ├── calendar.json      # その文書が使う祝日の固定版
        ├── cases.jsonl        # テストケース（入力と期待値）
        ├── tasks.jsonl        # 評価対象システムへの出題（関数名と入出力の契約）
        ├── programs/calc_<cid>.py   # 正解プログラム
        └── tests/             # 同梱 pytest（`--impl` で提出実装に差し替えられる）
```

## 検証

生成した文書は**全ゲートを通ったものだけ**を出す。

| | 検査 |
|---|---|
| G1–G2 | 仕様のスキーマ・型・単位。仕様の引用が契約書の単位に逐語で存在する |
| G3–G4 | 明示すべき事項に対応する文がある。本文・頭書・別紙から読み直した値が仕様と一致する |
| G5–G6 | 契約書に書いた計算例が参照インタプリタと一致する。参照インタプリタと正解プログラムが全ケースで一致する |
| G7–G8 | 生成したテストが変異をすべて検出する。日付を扱うルールに暦の境界ケースが入っている |
| G9–G10 | 既存の条項・定数・定義語・別紙番号と衝突しない。本体の lint・索引再計算・描画が成功する |
| G11–G12 | 根拠単位が言い回しと構造で発見できる。同じ seed で再生成してハッシュが一致する |
| G13 | （任意）基準となるシステムが H2 のヒントで合格する。2026-10-04 に見送り決定 |

意味論の正本は `spec/interp.py`（参照インタプリタ）で、生成した Python との一致を G6 と
`eval --oracle` が全ケースで確かめる。

## ディレクトリ

```
src/contracts_calculation/   # 生成器本体
packs/                       # パラメータ候補・入力概念の語彙・祝日の固定版（JSON）
tests/                       # 生成器自身のテスト
examples/                    # 回帰基準の 3 文書（生成物。scripts/update_examples.py で更新）
docs/                        # 調査・レビュー・決定の記録（索引は docs/README.md）
scripts/                     # 祝日の作成・examples の更新・データカードの独立検算
```

生成したデータセット（`data/`・`data_bind/`・`dataset/`）は**コミットしない**。決定的に再生成できる。

## 文書

| 文書 | 役割 |
|---|---|
| [`CLAUDE.md`](CLAUDE.md) | プロジェクト憲章。守ること（規則 1〜13）・現状・コマンド |
| [`docs/hf_publish.md`](docs/hf_publish.md) | Hugging Face 公開形の仕様（許可リスト・公開前ゲート） |
| [`docs/data_card.md`](docs/data_card.md) | データカードの生成仕様 |
| [`docs/README.md`](docs/README.md) | 調査・レビュー・決定の記録の索引 |

実装と文書が食い違ったら、**実装ではなく文書を先に直す**。

## 現況

開発フェーズ（M0〜M6）は完了し、運用モードにある。計算・判定のパターンは **K01〜K31 の 31 種**。
生成物は用途によって 2 系統ある：**v1**（`data/<profile>/<cid>/`。4 プロファイル × 20 基準契約）と、
Hugging Face 公開用に積んだ**100 文書セット**（`dataset/`。standard・hard・basic・challenge の混成、
calc_seed 1〜6）。

規模・内訳・品質保証・制限と偏りは、各生成物側の **`<data>/data-card.md`（データカード）** を見る。
データカードと説明書は実測だけから生成するので、データを足せば自動で更新される（固定文字列に統計値を
焼き込まない）。

## 制限と注意

- 生成物は**完全に架空**の契約書である。会社名・人物名・金額・日付はすべて合成で、実在のひな型の文章は
  一切含まない。**法的に有効な契約書ではなく、実務に使えない**。
- 税率・法定利率・祝日は法令の実装ではない。契約書に書かれた値か、外部からの入力として扱う。
- 祝日は 2026〜2033 年の固定版（`packs/calendar/holidays_jp.json`）。実行時に外部へ取りに行かない。
- 生成の経路で LLM を呼ばない。生成は決定的である（同じ seed なら同じ出力）。

## ライセンス

コード（`src/`・`scripts/`・`tests/`）はリポジトリ直下の [`LICENSE`](../../LICENSE)（MIT）に従う。

生成物（契約書 JSON・PDF・仕様・正解プログラム・テスト）の**配布条件は未決**である（本体プロジェクトの
決定に従属する）。決まるまで外部配布はしない。Hugging Face 公開形（`publish` の出力）は組み上げ済みで
公開前ゲートも通っているが、`license: other`／`undecided` のままカードに出力され、アップロードの実行は
人間が行う。
