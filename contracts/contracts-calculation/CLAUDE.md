# contracts-calculation

<!--
保守メモ（このコメントは Claude には渡らない）
- 置き場所: contracts/contracts-calculation/CLAUDE.md
- 200行以内に保つ。一部のディレクトリだけに効く規則は .claude/rules/ へ、長い手順は skill へ移す。
- 「現状と最初の作業」「コマンド」の節は、段階が進むたびに書き直す。古い記述を残さない。
-->

契約書合成データ生成 `contracts`（親ディレクトリ。以下「本体」）の拡張。
既定の契約書JSONに対して、計算や判定を要する条項（本文・頭書・別紙の表・図）を追加または紐づけし、
その正解プログラム（Python）とユニットテスト用の評価データを、同じ計算仕様から同時に生成する。

入口は `README.md`（何を作るか・本体への依存・コマンド・計算パックの構成・制限と注意）。
設計の正本は `DESIGN.md`（2026-10-03 に実物照合済み。§7 の構成木は 2026-10-05 に実装へ再照合）。実装は `src/contracts_calculation/`、進捗は「現状と最初の作業」を見る。

作業の前に、DESIGN.md の該当する節を読む。

| 作業 | 読む節 |
|---|---|
| 本体の調査、接続、能力の宣言 | §3.1、§9.5、§17 |
| 追加と付与の使い分け、バインディング | §6 |
| パターンの追加・変更 | §8、§9.4 |
| 文言・頭書・別紙・図への展開 | §9 |
| 日付、営業日、期間 | §10、付録A、付録B |
| 計算仕様、演算、意味論、出力の形式 | §12 |
| 正解プログラム、テストケース、採点 | §13 |
| 検証ゲート | §14 |
| 構成、段階と完了条件 | §7、§16 |
| **データカード（`dataset/data-card.md`）の生成・節の追加** | **`docs/data_card.md`**（本サブの仕様の正本） |
| **Hugging Face への公開形の組み立て** | **`docs/hf_publish.md`**（許可リスト・公開前ゲート P1〜P6・ライセンス） |

設計と違う実装が必要になったら、黙って実装だけを変えない。先に DESIGN.md の修正を提案する。

作業の順序・状態・完了条件は `TASK.md` で管理する。着手前に該当タスクの状態と依存を確認し、終えたら状態と進捗ログを更新する。
開発を進めるための指示文は `PROMPT.md` にある。人間が貼るものなので、本ファイルから import せず参照にとどめる。

## 守ること

破ると、データセットの正しさを保証できなくなる。迷ったら作業を止めて質問する。

1. **計算仕様が唯一の正。** 契約書の文言、正解プログラム、テストの期待値は、同じ仕様から機械的に作る。文言とプログラムを別々に書かない。
2. **生成物を手で直さない。** `examples/` 以下、`calc/programs/`、`cases.jsonl`、追加後の `contract.json` は出力である。直すのは生成する側。
3. **決定的に生成する。** 乱数は引数で渡された `random.Random` だけを使い、文書ごと・ルールごとに独立した乱数列にする。モジュール関数の `random.*`、現在時刻、`uuid`、`hash()`、集合の反復順に依存しない。
4. **手がかりを漏らさない。** 追加するノードID・定数名・別紙番号は本体の命名規則に従い、拡張由来と分かる語を入れない。正解に関する情報を `contract.json` に書かない。
5. **数値は1箇所にだけ書く。** 本文・頭書・別紙のどれか1つに置き、仕様はその場所を指す。式に数値を直書きしない。
6. **金額は整数の円。** `float` を使わない。割合は分子と分母で持つ。割り算は `muldiv` だけで、丸めの方向を必ず指定する。割合どうしの比較は掛け算に直す。
7. **`None` は「不明」だけを意味する。** 「通知がない」「定めがない」は、真偽の入力か、`optional` の入力と `coalesce` で表す。
8. **一義に読める文言だけを出す。** DESIGN.md §9.4 の事項を必ず文にする。
9. **足すだけにする。** 既存の文言を書き換えない。既定の契約書に同じ事項の条項があれば、追加せず、付与の対象にする。
10. **検証を弱めない。** 検証器、ゲート、テストが落ちたら、生成する側を直す。検査を外さない。期待値を書き換えない。
11. **本体を変更しない。** このディレクトリの外のファイルは、読むだけにする。本体を呼ぶコードは `base_adapter.py` だけに置く。
12. **自己完結させる。** `contracts` リポジトリの外にあるコード、データ、文書を参照しない。他のプロジェクトのコードや文書を、複製もしない。実行時は標準ライブラリだけを使う。依存を足す前に確認する。
13. **生成の経路でLLMを呼ばない。**

## 現状と最初の作業

**M0（本体の確認と文書モデル）と M1（計算の中核）は完了**（2026-10-03。TASK.md §5 の進捗ログ）。
あるもの：`base_adapter`（能力宣言・build/render 呼出・書込防護）、`docmodel/`（index・numbers_ja）、
`spec/`（model・schema・validate・interp・calendar）、`codegen/python.py`、テスト 159 件。
DESIGN.md §3.1・§17 は実物照合済み。§17 の 10〜13 はユーザー決定済み（別番号帯・実在祝日固定版・
不明値は評価に含める・20 content×3〜6 ルール）。

**MH5（H5 カバー）も完了**：47 問全問で算出値が親の答えと一致（一致 32・読み幅あり 15・不一致 0）。
仕様は `src/contracts_calculation/h5/specs.py`、検算は同 `h5/verify.py`（→ `docs/h5_report.md`・`docs/h5_inventory.json`）、回帰は `tests/test_h5.py`。
引き渡しと決定の記録は `docs/h5_handoff.md`（決定は親 `HITL_TODO.md` H5 の決定欄へ）。

**M2（追加モード）も完了**：16 パターン（K01〜K05・K07・K08・K11〜K14・K17・K18・K20・K23・K25）、
planning / realize / patch / gates（G1〜G6・G9・G10。G7/G8/G11 は明示 skip）、CLI。
20 base 全部が全ゲート＋本体 lint/build/render を通過（`data/` に 20 文書の計算パック）。
packs は JSON（規則12 と両立。DESIGN §7 注記）。目視レビューは `docs/m2_review.md`。

**M3（テスト生成と評価キット）も完了**：cases（境界値・日付4類型・不明値・乱数）、mutation（G7 全検出・G8）、
タスクカード（H0〜H2）、パック同梱 pytest（--impl 差替）、evalkit（隔離 runner・discovery・集計）、CLI eval。
オラクル検査は 20 文書・73 関数・1,996 ケース満点。判定ルールは三値論理で codegen（生成器 0.2.0）。

**M4（付与モード）も完了**：lint-base・bindings 4 種。親 content 改稿後の内訳は
**bound 26 件／除外 3 件**。遅延損害金は起算・分母・端数処理が明示された8件を include し、
起算が一義でない2件を除外する。ほかに nda-0001 の更新1件を定数化不足で除外する。
固定テスト tests/test_bindings.py、調査とレビュー観点は `docs/m4_bindings.md`。

**M5（表現手段と難易度）も完了**：プロファイル 4 種（basic/standard/hard/challenge）、段階表の別紙分離、
計算例の箱（G5 検算つき）、K13 の時間軸図（説明）、challenge（欠落・異例）、G11、datasheet。生成器 0.4.0。

**M6（残りの型）も完了＝全マイルストーン完了**：全 31 パターン（K28 の図だけが規範の流れ図を含む）。
分岐を含むルールは None 伝播で codegen（三値の意味論を正実装）。
オラクル検査は 20 文書・100 関数・3,003 ケース満点。生成器 0.5.0。

**2026-10-04 追補：DESIGN との残差を解消（当時の生成器 0.8.2）**：
頭書への分離（add_header_row。value_location=header_sheet）・challenge 矛盾型・CLI `bind`・
**分散**（営業日の定義を独立の条へ。definition_units が機能し、二重掲載を構造的に防止）・
**文型の変種**（§9.3。丸め・K17/K11/K14 に各 2 変種、意味等価をテストで固定）。
add_term だけは必要になるまで未実装（TASK 記録）。

人間の意思決定は **`HITL.md`** で依頼・記録する（**依頼中：HC-3 生成物の配布条件**。HC-1〜2 は決定済み。
依頼中の判断を AI が代行しない）。残作業は **TASK.md §2**。
調査・レビュー・決定の記録は `docs/` に集約した（索引 `docs/README.md`。設計に影響する決定は `docs/decisions.md` に 1 行足す）。

**データカード（2026-10-04 追加）**：`dataset/data-card.md` は `contracts-calc datacard update` の**生成物**
（手で編集しない）。仕様の正本は `docs/data_card.md`、実装は `src/contracts_calculation/export/datacard.py`、
テストは `tests/test_datacard.py`、測り方の独立検算は `scripts/verify_data_card.py`。
`generate` / `bind` / `datasheet` の出口で README と対で書き直すので、**データを足せば自動で更新される**。
更新を忘れたら `datacard check` が落ちる。配布条件は未決（HITL **HC-3**。親 H13 に従属）。

**現在の状態：v1 完成・運用モード**（2026-10-05 全文再レビュー済み。配布条件 HC-3 だけ依頼中）

- 決定済み：(1) H5 の読み幅あり15問の読みを承認、(2) 遅延損害金は一義に読める8件を include、
  起算が曖昧な2件を記録つき除外、(3) G13 は見送り（評価対象システムが現れたら eval CLI で測る）。
- 成果物＝**v1 データセット（HC-2 決定の構成）**：`data/<profile>/<cid>/`（basic/standard/hard/challenge ×
  20 base × calc_seed 1 ＝ 80 文書。各プロファイルに datasheet・oracle_report 同梱）・`data_bind/`（付与のみ
  20 件）・`examples/`（回帰基準 3 文書）。オラクル検査は 4 プロファイルとも満点（計 413 関数・11,957 ケース）。
  ほかにユーザー指示の 100 件セット `dataset/`（standard29・hard29・challenge20・basic22、seed1〜6。
  オラクル 558 関数/16,689 ケース満点）。生成器 0.8.3。既知の実在名称との衝突はコピー後の生成前処理で
  合成名へ置換し、禁止名称の全量回帰検査を行う。examples と H5 検算も現行の親 content に再基準化済み。
  全文・意味・名称レビューの記録は `docs/dataset_review.md`。固定回帰と `--all-bases` はHC-2で決定した
  `V1_BASE_CONTENT_IDS` 20件を使い、増加し続ける親 content の全件列挙とは分離する。
  **Git 操作は全て人間が行う**（HC-1。AI はコミットしない。`.gitignore` 整備済み）。
- 変更するときは PROMPT.md の該当プロンプト（P-OP-ADD・P-DESIGN-CHANGE・P-COMMIT 等）に従う。

## コマンド

テストは本体の uv 環境で実行する（システムの python3 に pytest が無い）。

```bash
cd contracts-calculation && uv run --project .. python -m pytest -q   # 生成器自身のテスト（約 15 秒）
uv run --project .. ruff check src tests scripts                     # lint（全緑を保つ）

# 生成（contracts-calc 相当。cd contracts-calculation で実行）
# v1 データセット（HC-2 の構成）は 4 プロファイルを data/<profile>/ に生成する
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli generate --all-bases --calc-seed 1 --profile standard --out data/standard
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli generate --base ../content/ots-0001 --calc-seed 1 --out data --png
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli verify data/ots-0101
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli eval --data data --oracle   # 満点の検査
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli bind --all-bases --out data_bind --no-render  # 付与のみ
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli lint-base    # 既定の契約書の計算条項の点検

# データセットの説明書とデータカード（dataset/ の実測だけから作る。手で書かない）
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli datasheet --data dataset       # README と data-card.md を対で
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli datacard update --data dataset
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli datacard check  --data dataset # 鮮度（古ければ終了コード 1）
uv run --project .. python scripts/verify_data_card.py --data dataset                                 # 測り方の独立検算

# H5 検算のやり直し／examples の作り直し（意図した変更のときだけ）
PYTHONPATH=src uv run --project .. python -m contracts_calculation.h5.verify
PYTHONPATH=src uv run --project .. python scripts/update_examples.py

# Hugging Face 公開形（dataset/ を読むだけ。アップロードはしない。docs/hf_publish.md）
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli publish --data dataset --out dist/hf
PYTHONPATH=src uv run --project .. python -m contracts_calculation.cli publish --data dataset --out dist/hf --license cc-by-4.0 --repo-id <owner>/<name>
```

- macOS で本体の render を呼ぶときは `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が要る
  （`base_adapter` が自動で付ける。手で `uv run keiyaku render` するときだけ注意）。
- WeasyPrint 70.0 の既知不具合で既定 style の描画が破綻することがある。generate は
  `ct-a4-1col-form` → `ct-a4-1col-gothic` の順に決定的へフォールバックし、manifest に注記する。

## 変更したら必ず確かめること

1. `uv run --project .. python -m pytest -q` が全件通ること（システムの python3 に pytest は無い）。
2. 生成ができた後は、次もテストとして `tests/` に置き、常に通すこと。
   - 20個以上の seed で生成し、検証ゲートをすべて通る。
   - 同じ seed で2回生成し、全ファイルが一致する。
   - 仕様を1箇所だけ誤らせて作った実装が、生成したテストで不合格になる。
3. `examples/` の差分が意図どおりであること。意図して出力を変えたときは、生成器の版を上げる。
4. データを足したら `datacard check` が通ること（`generate`/`bind`/`datasheet` が自動で書き直す）。
   カードの**測り方**を変えたときは `scripts/verify_data_card.py` を手で 1 回回す。
5. 公開形に関わるものを変えたら `publish` を回し、**公開前ゲート P1〜P6 が全部 ok** であること
   （`docs/hf_publish.md`）。P2 は個人情報の漏洩を止める網なので、落ちたら生成する側を直す。

## 間違えやすい点

- **期間の数え方。** 「Xの日から起算して N 日以内」は、X を1日目に数える（X の N−1 日後まで）。「Xの翌日から起算して」は、X の N 日後まで。
- **満了日と応当日。** 月・年の期間の満了日は `period_end`、「N か月前」「N か月後」の日は `add_months` で求める。混ぜない。
- **暦の関数は付録Aが定義。** 挙動を変えるときは、付録A、付録B、§10 を同時に直す。
- **祝日をコードに書かない。** `holidays` を入力で受け取る。一覧は `packs/calendar/` の固定版を使い、実行時に外部へ取りに行かない。
- **日付のテスト。** 月末（28・29・30・31日）、2月29日、年末年始、土日の前後、祝日の有無を必ず入れる（§10.3）。
- **段階料金。** 全量方式と超過分方式は別の型である。全量方式は境界で金額が下がるので、単調性を性質に宣言しない。
- **対象期間のある上限。** 「直近12か月」は基準日がないと計算できない。基準日を入力にする。
- **金銭の向き。** 仕様に支払う側と受け取る側を持たせ、関数の説明とタスクカードに書く。
- **`spec/calendar.py` は標準ライブラリと同名。** このファイルを直接実行しない。パッケージ経由で import する。

## 契約書JSONを組み立てるときの決まり

置き場所は DESIGN.md §7 のとおり。作った後に守る。

- 本体のスキーマと、`base_adapter` が宣言する能力の範囲だけを使う。図を描画できない本体に、図を足さない。
- ノードとブロックは、組立関数（`realize/blocks.py`）で作る。辞書を手書きしない。
- 索引（条番号、参照、目次）を自作しない。本体の処理で再計算する。
- 根拠の引用は、本文に使ったのと同じ文字列変数から作る。同じ文を2回書かない。
- 数値と日付の表記は `docmodel/numbers_ja.py` で作る。同じモジュールで読み戻せることをテストする。
- 定数名、定義語、別紙番号が既定の契約書と衝突したら、生成を止める。

## 契約書の文言

- 文体、当事者の呼称、条・項・号の書き方は、既定の契約書に合わせる。段階0で実物から確かめる。
- 文型の変種は、同じ意味のものに限る。変種ごとに、仕様どおりの結果になるテストを付ける。

## 演算や型を足すとき

次を同時に直し、参照インタプリタと生成したPythonが一致するテストを足す。

- `spec/interp.py`（意味論の正本）
- `spec/validate.py`（型と単位の検査）
- `codegen/python.py`
- `testgen/cases.py` と `testgen/mutation.py`（境界値と変異）
- `spec/schema/calc_spec.schema.json`
- DESIGN.md §12.2 と §12.3

## コーディング規約

- Python 3.10 以降。実行時は標準ライブラリだけを使う。テストは pytest。
- 型ヒントを付ける。データは `dataclass` で持つ。
- コメント、docstring、利用者向けのメッセージ、文書は日本語。識別子は英語。
- JSON は `ensure_ascii=False` で書く。キーとリストの順序を安定させる。日付は `YYYY-MM-DD`。
- pytest が作る `__pycache__` と `.pytest_cache` はコミットしない。
- コミットとブランチの運用は、本体のリポジトリに従う。分からなければ確認する。
