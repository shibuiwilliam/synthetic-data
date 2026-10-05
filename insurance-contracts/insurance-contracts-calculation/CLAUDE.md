# insurance-contracts-calculation

<!--
保守メモ（このコメントは Claude には渡らない）
- 置き場所: insurance-contracts/insurance-contracts-calculation/CLAUDE.md
- 220行以内に保つ（2026-10-05 に実態へ合わせた。承認済み例外と「現状」の節で伸びた）。
  一部のディレクトリだけに効く規則は .claude/rules/ へ、長い手順は skill へ移す。
- 「現状」の節は、段階が進むたびに書き直す。古い記述を残さない。
- 設計・計画・人間判断を記した内部文書は GitHub にコミットしないため、本ファイルと
  README.md からは参照しない（2026-10-05 にユーザー判断で確定）。
-->

約款合成データ生成 `insurance-contracts`（親ディレクトリ。以下「本体」）の拡張。
既定の約款JSONに計算・判定の規定（条・表・算式・図）を足し、その正解プログラム（Python）と
ユニットテスト用の評価データを、同じ計算仕様から同時に生成する。

モジュール名とコマンドは版で動くので、使う前に実物を確かめる。データカード
（`dataset/data-card.md`）の節と測り方は `docs/data_card.md` を見る。

## 守ること

破ると、データセットの正しさを保証できなくなる。迷ったら作業を止めて質問する。

1. **計算仕様が唯一の正。** 約款の文言、正解プログラム、テストの期待値は、同じ仕様から機械的に作る。文言とプログラムを別々に書かない。
2. **生成物を手で直さない。** `examples/` 以下、`calc/programs/`、`cases.jsonl`、追加後の `policy.json` は出力である。直すのはパターン、組立、コンパイラの側。
3. **決定的に生成する。** 乱数は引数で渡された `random.Random` だけを使う。モジュール関数の `random.*`、時刻、`uuid`、`hash()`、集合の反復順に依存しない。同じ入力と seed から同じバイト列を出す。
4. **手がかりを漏らさない。** 追加するノードID・ブロックID・定数名は本体の命名規則に従い、拡張由来と分かる語（`calc` など）を入れない。正解に関する情報を `policy.json` に書かない。
5. **数値は1箇所にだけ書く。** 値は `meta.constants`（表記の文字列）と表のセルに置き、本文は `{const:キー}` で参照する。仕様は `from_const` と `from_block` で指す。式に数値を直書きしない（0以外の数値リテラルには `note` が必須）。
6. **金額は整数の円。** `float` を使わない。割合は `muldiv` で計算し、端数処理の方向を必ず指定する。
7. **不明は `None`。** 入力が `None` で結果を確定できなければ `None` を返す。真偽は三値。意味論の正本は `spec/interp.py`。
8. **一義に読める文言だけを出す。** 適用順、端数処理、以上・超える、起算日、0円の下限を必ず文にする。
9. **検証を弱めない。** 検証器、ゲート、テストが落ちたら、生成側を直す。検査を外さない。期待値を書き換えない。`examples/wrong_impl.py` を「修正」しない。
10. **本体を変更しない。** このディレクトリの外のファイルは読むだけにする。本体を呼ぶコードは `base_adapter.py` だけに置く。本体の仕様が分からないときは、推測で実装せず質問する。
    - **例外（人が承認済み）。** 次の 5 つに限り本体を変更してよい。これ以外は従来どおり禁止で、
      必要に見えたら実装せずに人に確認する。
      (1) `yakkan/lint/walk.py` の `_ARTICLE_CACHE`（`id(draft)` キーの取り違え）、
      (2) `styles/css/_base.css.j2` の `.footnotes`（段の境目で脚注が PDF から落ちる）、
      (3) `content/` の**曖昧な計算規定の文言**（`icc lint-base` が挙げるものだけ。実績 109 件。ほかの文は触らない）、
      (4) `yakkan/lint/parts_index.py`（新設の L19：`doc.json` の `parts` に載っていない
      足場ファイルの検出）と、それに伴う `content/` の足場ファイル 60 件の削除、
      (5) 上記に伴う `dataset/` の再生成（**コマンドで作り直す。手編集はフックが拒否する**）。
    - 本体を変更したら、**本体の `docs/decisions.md` に「日付／変更／理由／影響」を記録してから**
      再レンダリングする（本体 CLAUDE.md §7 の規約）。本体の `make check` を通すまでが 1 単位。
    - **本体には並行して別の作業が入る。** 拡張が入れた文言が気づかないうちに上書きされた
      実例がある。本体 `content/` を触る作業は、**前後に必ず**次を回す。
      差分が出たら、自分の変更か他の作業の変更かを確かめるまで先に進まない。

      ```bash
      PYTHONPATH=src python scripts/check_base.py --save   # 着手前：基準を保存
      PYTHONPATH=src python scripts/check_base.py --diff   # 作業後：基準と比べる
      ```
11. **生成の経路でLLMを呼ばない。** 言い換えなどのLLM利用はまだ入れない。
    検証（G12 解答可能性）でセッション内サブエージェントに解かせるのは**経路外なので可**
    （人が承認済み）。解かせた結果をもって生成物の文言を直す判断はしない。

## コマンド

本体の venv に同居させる。`--base` は `content/<id>/` でも `dataset/*/source.json` でもよい。

```bash
cd insurance-contracts-calculation
export DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib

# 生成（追加 → 仕様 → 検証ゲート → 正解プログラム → テスト → 描画）
PYTHONPATH=src uv run --project .. python -m insurance_contracts_calculation.cli \
    generate --base ../content/auto-0001 --out out --seed 1

# 生成されたテストを正解プログラムで実行する（全件合格が正しい）
uv run --project .. python -m pytest out/auto-0001-c1/calc/tests -q

# わざと誤らせた実装で実行する（不合格が出るのが正しい）
uv run --project .. python -m pytest examples/auto-0001-c1/calc/tests \
    --impl examples/wrong_impl.py -q

# ほかのコマンド
... cli verify out/auto-0001-c1                 # 検証ゲートだけ再実行
... cli eval --submission impl.py --data out/auto-0001-c1
... cli batch --genres auto quake health --per-genre 5 --out out/v1
... cli lint-base ../content/auto-0001          # 既定の約款の計算規定を一覧にする
... cli export out/auto-0001-c1 --out public/   # 公開パッケージ（正解は入らない）
... cli package dataset --format hf --out dist/hf   # HF 公開用（正解を含む。**上げるのは人**）
... cli datacard update dataset                 # データカード（dataset/data-card.md）を書き出す
... cli datacard check dataset                  # カードが現在の dataset/ と合っているか（make check に入っている）
```

## 変更したら必ず確かめること

```bash
make check          # ruff + 生成器自身のテスト（slow を除く）＋ データカードの鮮度
make test-all       # seed 1〜20 の sweep も含める
cd .. && make check # 本体を壊していないこと
```

1. `examples/` の差分が意図どおりであること。意図して出力を変えたときは `generate.py` の
   `GENERATOR_VERSION` を上げ、差分の理由をコミットメッセージに書く。
2. `calc/manifest.json` の `gates.survivors` が空であること。残るときは、検出できる入力を足すか、
   等価である理由を記録する（検査を外さない）。
3. 新しい表現（図・表）を入れたら、**ページ PNG を自分の目で見る**。lint とページ数が通っても崩れる。
4. `dataset/` に文書を足したら `dataset/data-card.md` が追従していること（`make check` の
   `datacard-check` が見る）。カードは生成物なので手で直さない。測り方を変えたら
   `PYTHONPATH=src python scripts/verify_datacard.py dataset` で別経路と突き合わせる。

## 現状

- **あるもの**（2026-10-05 時点）
  - `base_adapter.py`：本体を呼ぶ唯一の場所。`derived` は本体の `build` が再計算する
  - `spec/`：計算仕様 v0.2（名前つきの手順・日付型・`round_to`・明示性の要件）
  - `patterns/`：P01〜P18（18 種）。`registry.py` に登録する
  - `planning/`：文脈・選択・**配置（条・別表・特約）**・表現手段・難所（challenge）
  - `realize/`：文型（`lexicon_ja.py`）・組立・図・設例・パッチ
  - `codegen/python.py`：手順名を変数名にした正解プログラム
  - `testgen/`：境界値・日付の境界・不明値・変異・タスクカード・pytest
  - `verify/gates.py`：G1〜G11（題は `GATE_TITLES` が唯一の正）。**G12 は `solvability.py` で実測済み**
    （**8 種目・1,244/1,244**。v2.1 時点の実測で、v2.2 以降では測り直していない。`docs/solvability_run.md`）
  - `evalkit/`：隔離実行・発見の採点・軸ごとの集計レポート
  - `packs/`：8 種目（auto・quake・health・oneday・travel・golf・group・life）の語彙と値域
  - `export/datacard.py`：`dataset/data-card.md`（利用者向けデータカード）。実ファイルだけを測る
  - `export/huggingface.py`：**HF 公開用のリポジトリ**を組む（`--format hf`。`docs/hf_publication.md`）。**組むだけで、push もアップロードもしない**
  - `tests/`：生成器自身のテスト（回帰・決定性・規律・seed 1〜20 の sweep）
- **ないもの**：LLM による言い換え、SQL の正解プログラム、スキャン風画像、
  `teikan`・`jyusetsu` への対応（計算規定が無い／条を持たない）。
- `core/compile_sql.py` は `codegen/sql.py` に移したが、SQL の出力は範囲外。頼まれない限り触らない。
- 乱数は**ルールごとに独立**（`Random(f"{cid}:{seed}:{subject}:{pattern}")`）。
  パターンを足しても、ほかのルールの出力は変わらない。
- 配置は 3 通り（条の追加・別表への分離・特約への分離）。但し書き（端数処理・下限0）の行き先は
  さらに 3 通り（次の項・条末脚注・別の条）。プロファイルの `scatter` が割合を決める。
- 同じ内容を**複数のスタイルで描ける**（`--styles` / `--multi-style`）。正解は 1 組で共通。
- 文書IDは `<既定のID>-c1`。同じ既定の約款から 2 本目を作るときは `--variant 2` で `-c2` になる
  （`generate.doc_suffix`）。**番号は乱数に入らない**ので、種を変えないと中身が同じ本になる。
  `batch` は `--variant` に応じて種を `VARIANT_SEED_STEP`（1000）ずつずらし、
  先に作った本と規定の顔ぶれが同じなら種を変えて組み直す。
- 出力先は `out/` か `dataset/`（どちらも git 無視）、回帰基準は `examples/`。
  書き込みを止めるのは**本体の** `dataset/` だけである（`export/layout.py` の `check_out_dir`）。
  `examples/` に描画結果（PDF・PNG・`layout.json`）は入れない。比較に使うのは
  `policy.json` と `calc/` だけで、必要なら `make examples` で作り直す。

## 約款JSONを組み立てるときの決まり

- ノードとブロックは `realize/blocks.py` と `realize/figures.py` の組立関数で作る。辞書を手書きしない。
- 本体に既にあるノード種別・ブロック種別だけを使う。算式は `box` `op` `fraction` を並べた1行。
- 既存の文言を書き換えない。足すだけにする。パッチは `realize/patch.py` の操作で記録する。
  定数名・保険金名・ID が既定の約款と衝突したら、その題材を外す（文書ごと落とさない）。
- 条のIDは `realize/patch.py` の `next_article_id()` で払い出す。
- 追加したノードへの `{ref:}` は**使ってよい**（本体の `build` が `derived` を再計算する）。
  別表に分けた表は本文から `{ref:appN}` で指す。
- **プレースホルダの表示文字列を自分で決め打ちしない。** 根拠の引用は本体が描いたとおりでなければ
  G2 が落ちる。`{fn:n}` は `meta` の `digit_style`・`numbering_scheme`・`footnote_style` で変わり
  （`（*1）`／`（*１）`／`（注1）`／❶）、`{ref:}` は引用元から見た相対表記に条の見出し文言が付く
  （`labels[..].citation` の「第4章 第7条」ではなく「第7条（買替費用保険金）」）。
  解決は `core/docindex.py` の `Doc.resolve(raw, from_id=...)` に任せる。`{ref:}` は本体が
  `derived.refs` に残した結果を引く。本体の規則を写すと、版が変わったときに静かにずれる。
  目的別もくじ・特約一覧への行追加は `planning/placement.py` が行う。
- 別表のIDは blueprint が予約しているもの（`app1`〜）を避ける。予約IDで作ると
  「その別表の中に◯行以上の表が要る」という必須要素（本体 lint L04）に当たる。
- 根拠の引用は、本文に書いた文そのものから作る（`discourse.py` が `sources` に積む）。同じ文を2回書かない。
- 図だけに書く規定の根拠は、図のノード単位（`<図のID>__<ノードID>`）を指す。
  図の `alt` と `facts` は、図の構造から機械的に作る。
- 図の大きさは `realize/figures.py` の `LIMITS`（上限・実測）と `MINIMUMS`（本体 lint L06 の下限）に従う。
  **本体の `verify` は図の大きさを見ない**（`docs/figure_limits.md`）。
- 数値の表記は `core/numbers_ja.py` で作る。表記を増やすときは、`core/docindex.py` の
  `parse_quantity` で読み戻せることをテストする。
- 表のキーと値は、`spec/validate.py` の `_parse_cell` が読める書式にする
  （`12か月まで`、`第3級`、`30%`、金額）。参照表には `records`（意味）も付ける（本体 lint L05）。
- 囲みの設例の数値は、仕様から計算した値を使う（`realize/examples.py`）。
  **既定の定数の表記と重なる数値は使わない**（本体 lint L11 は部分文字列で当たる）。

## 約款の文言

- です・ます調。主語は「当会社は、」。定義語は `{term:ID}`、数値は `{const:キー}` で書く。
- 既定の約款の言い回しに合わせる。例：「…を差し引いた額とします。」「…を限度とします。」「…を乗じて得た額」。
- 文型の変種は、同じ意味のものに限る。変種ごとに、仕様どおりの結果になるテストを付ける。

## パターンを足す手順

1. 計算パターンの型（P01〜P18 のどれにあたるか）を決め、既定の約款に必要な章・用語・特約があるかを調べる。
2. パラメータの候補と制約を決める（例：免責金額 < 限度額）。
3. 文・表・図と、仕様（式、入力、根拠、性質、設例）を、同じ値から作る。
4. 生成し、整合検査（`RuleSet.validate()`）のエラーと警告が0であることを確かめる。
5. 「変更したら必ず確かめること」を実行する。

## 演算や型を足すとき

まず台帳（`spec/ops.py`）に 1 行足し、次を同時に直して参照インタプリタと生成Pythonが一致する
テストを足す。`tests/unit/test_ops_coverage.py` が台帳との照合で直し忘れを落とす。

- `spec/interp.py`（意味論の正本）
- `codegen/python.py`（Python生成）
- `spec/validate.py`（型・単位・根拠の検査。表のセルを読む `_parse_cell` もここ）
- `testgen/cases.py` と `testgen/mutation.py`（境界値と変異）
- `realize/explain.py`（日本語への逆翻訳）

## コーディング規約

- Python 3.12。**生成物**（`calc/programs/`・`calc/tests/`）は標準ライブラリだけで動く。
  生成器自身は本体の venv に同居し、`pyyaml`（パックの読み込み）と、`base_adapter.py` 経由で
  `yakkan`（pydantic・WeasyPrint）を使う。CLI は標準ライブラリの `argparse`（本体の `typer` は使わない）。
  テストは pytest。
- 型ヒントを付ける。データは `dataclass` で持つ。
- コメント、docstring、利用者向けのメッセージ、文書は日本語。識別子は英語。
- JSON は `ensure_ascii=False` で書く。キーとリストの順序を安定させる。
- pytest が作る `__pycache__` と `.pytest_cache` はコミットしない。
- コミットとブランチの運用は、本体のリポジトリに従う。分からなければ確認する。
