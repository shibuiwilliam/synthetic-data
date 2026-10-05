# insurance-contracts-calculation

約款合成データ生成 [`insurance-contracts`](..)（以下「本体」）の拡張。
既定の約款JSONに**計算・判定の規定**（条・表・算式・図）を足し、その**正解プログラム**（Python）と
**ユニットテスト用の評価データ**を、同じ計算仕様から同時に生成します。

文言とプログラムを別々に書かないので、両者は構成上ずれません。そのうえで機械検査（検証ゲート
G1〜G12）を全部通った文書だけを出力します。

| 読むもの | 内容 |
|---|---|
| `CLAUDE.md` | 守る規律（Claude Code が毎セッション読む） |
| `docs/` | 実測の記録（図の上限・G12 解答可能性・本体の不具合・データカードの仕様・**HF 公開の手順**） |

## 前提

**単体では動かない。** 本体 `insurance-contracts` のチェックアウトと、その venv が要る。

- Python 3.12（本体の `uv sync` が入れる）、[uv](https://docs.astral.sh/uv/)、Pango（WeasyPrint が使う）
- 本体の `content/` に執筆済みの約款があること（規定を足す土台になる）
- macOS では `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`（本体 `docs/gotchas.md`）

```bash
cd insurance-contracts && uv sync && make doctor   # 本体の環境を整える
```

対象は 8 種目（auto・quake・health・oneday・travel・golf・group・life）。`teikan` と `jyusetsu` は
計算規定が無い／条を持たないため対象外です。

## できること

| 生成物 | 内容 |
|---|---|
| `policy.json` | 計算規定を足した約款JSON（本体が `derived` を再計算） |
| `<doc_id>/doc.pdf` ほか | 本体が描画したPDF・`layout.json`・PNG |
| `calc/spec.json` | 計算仕様（CalcSpec v0.2。唯一の正） |
| `calc/programs/calc_*.py` | 正解プログラム（標準ライブラリだけで動く） |
| `calc/cases.jsonl` + `calc/tests/` | テストケースと pytest |
| `calc/tasks*.jsonl` | 出題用のタスクカード（ヒント H0/H1/H2） |
| `calc/answer_key.json` | 正解表（どの単位がどのルールの根拠か） |
| `calc/manifest.json` | 版・seed・ハッシュ・検証ゲートの結果 |
| `<出力先>/data-card.md` | **データカード**（規模・内訳・正解の中身・検証の結果・制限と偏りの実測。利用者が最初に読む 1 枚） |

## 使い方

本体の venv に同居させます（本体の `pyproject.toml` は変更しません）。

```bash
cd insurance-contracts-calculation
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib   # macOS で WeasyPrint が要る

# 1 文書を生成する（--base は content/<id>/ でも dataset/*/source.json でもよい）
PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli \
    generate --base ../content/auto-0001 --out out --seed 1

# 生成したテストを正解プログラムで実行する（全件合格が正しい）
uv run --project .. python -m pytest out/auto-0001-c1/calc/tests -q

# わざと誤らせた実装で実行する（不合格が出るのが正しい）
uv run --project .. python -m pytest examples/auto-0001-c1/calc/tests \
    --impl examples/wrong_impl.py -q

# 提出プログラムを採点する（軸ごとの集計が出る）
PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli \
    eval --submission examples/wrong_impl.py --data examples/auto-0001-c1

# まとめて生成する（8 種目 × 各 5 文書）
PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli \
    batch --genres auto quake health oneday travel golf group life \
          --per-genre 5 --min-slack 1.8 --out out/v1
```

出力先は `out/` でも、拡張自身の `dataset/` でもよい（どちらも git 無視）。書き込みを拒むのは
**本体の** `dataset/` だけです（本体の `manifest check` が壊れるため）。
`dataset/` の内訳は **`dataset/data-card.md`**（実測のデータカード）と `dataset/_run_report.json`
（生成時の記録）にあります。

```bash
# データカード（データを足したら自動で更新される。鮮度は make check が見る）
PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli \
    datacard update dataset
```

`make check` で lint（ruff）・生成器自身のテスト・データカードの鮮度を見ます。seed を広く振る
確認まで含めるなら `make test-all`、本体を壊していないことは `cd .. && make check` で確かめます。

## 中身

| パス | 内容 |
|---|---|
| `src/.../base_adapter.py` | 本体を呼ぶ**唯一の場所**（読み込み・パッチ適用・`derived`・描画・lint・verify） |
| `src/.../spec/` | 計算仕様 v0.2（型・検査・参照インタプリタ・明示性の要件） |
| `src/.../patterns/` | 計算パターン 18 種（P01〜P18） |
| `src/.../planning/` | 文脈の読取・パターンの選択・配置（条・別表・特約）・表現手段・難所 |
| `src/.../realize/` | 文型（日本語）・ノードとブロックの組立・図・設例・パッチ |
| `src/.../codegen/` | 正解プログラムの生成 |
| `src/.../testgen/` | 境界値・不明値・変異・タスクカード・pytest |
| `src/.../verify/` | 検証ゲート・発見可能性・解答可能性・既定の約款の点検 |
| `src/.../evalkit/` | 提出の隔離実行・発見の採点・集計レポート |
| `src/.../export/` | 出力の配置・公開パッケージ・配布物・**データカード**（`datacard.py`） |
| `packs/` | 8 種目の語彙と値域（YAML）。値をコードに直書きしない |
| `tests/` | 生成器自身のテスト（回帰・決定性・規律・seed の sweep） |
| `scripts/` | 本体の並行変更の検出（`check_base.py`）・データカードの別経路での検算 |
| `examples/` | 回帰の基準（seed 4）と、わざと誤らせた実装。描画結果（PDF・PNG）は入れない（`make examples` で作り直す） |

## 約束ごと

- **計算仕様が唯一の正**。約款の文言・正解プログラム・テストの期待値は、すべて仕様から作ります。
- **生成物を手で直さない**。直すのはパターン・組立・コンパイラの側です。
- **決定的**。同じ既定の約款・同じ seed・同じ生成器の版なら、同じバイト列を出します。
- **検証を弱めない**。ゲートが落ちたら生成側を直します。
- 約款はすべて**架空**です。会社名・商品名・連絡先は実在しません。

## 配布と利用

- **このリポジトリに入るのは生成器（`src/`）と回帰の基準 1 文書（`examples/`）だけ**です。
  データセット本体（`out/`・`dataset/`。約 2.2GB の PDF・PNG・`layout.json`）はコミットしません
  （上記の `generate` / `batch` コマンドで再生成できます）。`examples/` も描画結果は持たず、
  比較に使う `policy.json` と `calc/` だけを置いています。
- **Hugging Face での公開を準備しています。** 公開用のリポジトリは次のコマンドで組みます。
  **組むだけで、push もアップロードもしません**（実行は人の作業）。
  手順と確認項目は `docs/hf_publication.md` にあります。

  ```bash
  PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli \
      package dataset --format hf --out dist/hf --version v2.3 \
      --license cc-by-4.0 --repo-id <account>/yakkan-calc
  ```

  **ライセンスは仮決め（`cc-by-4.0`）です。** 公開前に確定してください。
- 生成したデータを評価に使うときは、正解を学習に混ぜないでください。何を渡し何を渡さないかの
  線引きは `icc export` が機械的に分けます。
