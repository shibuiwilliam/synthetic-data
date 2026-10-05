# plan.md — 実行計画とタスク分解（WBS）

> CLAUDE.md §12（マイルストーンと DoD）の詳細版。各フェーズの具体タスク・依存・リスク・
> 完了条件を持つ。フェーズの完了時に本ファイルのチェックボックスと `docs/progress.md` を更新する。
> 姉妹 2 本の実績（yakkan の P0〜P6 ＋残課題 8 次ループ、keiyaku の P0〜P7 ＋データセット 100 文書）から
> 所要感と落とし穴を引いている。
>
> **2026-10-05 改訂**：keiyaku-synth がデータセット v1 を完成させ、本プロジェクトの P1（コア汎用化）と
> P3（contract）の大半を契約書ドメインで先に済ませたため、P0〜P3 を「移植と family 化」に組み替えた。
> 基盤の選択は `HITL_TODO.md` D1（既定：keiyaku ベース）。

## 全体像

```
P0 移植（keiyaku → docsynth。挙動不変。既定。B案なら yakkan → docsynth）
 └ P1 コア汎用化（固定値 contract をレジストリに開く・numbering 一般化・lint の要件をファミリー宣言へ）
     └ P2 同等性（insurance と contract の既存 content が姉妹と一致することを CI で固定）
         ├ P3 contract 完成（keiyaku の 10 doctype・50 content を families/contract へ）
         ├ P4 terms   ├ P5 regulations   ├ P6 statute        ← 新ファミリーは順次・独立
         └ P7 データセット v1（QA・バッチ・評価向け成果物・データカード・自己評価）
             └ P8 検証・硬化（規則ベース → VLM → 盲検 → HITL）
                 └ P9 拡張・手順書検証・配布（第三者が 1 ファミリー追加できるか）
```

- P4〜P6 は互いに独立。1 ファミリーずつ「blueprint → style → 執筆 1 本 → review」までを
  完了させてから次に進む（並行すると共有コード変更で互いの描画が壊れる——両姉妹の教訓
  「サブエージェント作業中は共有コードを触らない」）。
- 規模の目安（v1）：5 ファミリー・20 doctype。**content を足して増やし、style を重ねて数を増やさない。**

## P0 移植 — 姉妹のコードと資産を挙動不変で取り込む

**DoD**：`make check` が通り、smoke が供給元と同一出力。棚卸し表（`docs/architecture.md` §5）が
埋まり、P1 の作業リストが確定している。

- [ ] **基盤の確認**：`HITL_TODO.md` D1 の回答を見る。未回答なら既定（keiyaku ベース）で進めてよいが、
      **P1 以降に進む前に回答を得る**（やり直しの費用が大きい）。
- [ ] `uv init`（Python 3.12・WeasyPrint==70.0・pdfplumber・pypdfium2・fontTools・pydantic v2・
      typer・Jinja2・PyYAML・ruff・pytest）。Makefile（setup/check/fmt/doctor/smoke/doc/batch/clean）を移植。
      **`check` には manifest 鮮度とデータカード鮮度を入れる。**
- [ ] `../contracts/keiyaku/` → `docsynth/` へコピー＆リネーム（import・CLI 名のみ変更）。
      **`answer.py` / `export.py` / `export_models.py` / `search_set.py` / `figure_graph.py` /
      `eval/`（harness・metrics・oracle・search）/ `manifest.py` / `datacard.py` / `batch.py` / `fonts.py` を含める**
      （評価基盤は「最小化」せず丸ごと移植する）。
- [ ] `tests/`（532 件）・`scripts/`（24 本：probe 群・calibrate_styles・fill_records・authoring・
      baseline_reader・apply_review・analyze_reference_pdf・otf_to_ttf）・
      `.claude/`（commands / agents / rules / hooks / settings）を移植。
- [ ] **検索まわりは yakkan から取る**：`search_set.py` のクエリ 10 種・自己検査 V-S1〜V-S9・
      検索指標（`exact_recall@k`・`r_precision`・`doc@1`・`confusion@k`・`false_positive_rate`）は
      keiyaku にまだ無い（`docs/architecture.md` §5）。**取り込み漏れを P0 のチェック項目にする。**
- [ ] フォント同梱：**`.ttf`（TrueType 輪郭）版を使う**。`.otf` は出典検証用に併置し `SOURCES.md` を持ってくる。
- [ ] `doctor` / `make smoke` を通し、**smoke PDF のテキスト層が供給元と一致**することを確認。
- [ ] `tests/golden/numbering_legacy.json`（616KB）を持ってくるかを判断する（keiyaku 側でも去就が未決）。
      持ってこない場合は P2 の同等性 golden で代替することを decisions に書く。
- [ ] 棚卸し：モジュールごとに「そのまま／要汎用化（ドメイン直書き箇所）／捨てる」を
      `docs/architecture.md` §5 の表に**実測で**記入。
- リスク：親 `.gitignore` の `parts/` 等が content を無言で除外する（yakkan 実害あり。
  `git check-ignore -v` で確認）。macOS は `DYLD_FALLBACK_LIBRARY_PATH` 必須。

## P1 コア汎用化 — ドメイン知識を宣言に追い出す

**DoD**：単体テスト通過。numbering YAML **8 方式**（contract 3 ＋ insurance 5）が姉妹の実装と
全 kind × 位置で同一のラベル・同一の `{ref:}` 解決を出す golden。`docsynth families` が動く。

- [ ] ファミリーレジストリ `docsynth/families.py`（family.yaml の読込・検証・hooks のロード・
      doctype 名の衝突検査）。**`family` を固定値 `contract` からレジストリ参照に開く**。
- [ ] **宣言的 numbering の一般化**（`docs/schema.md` §7）：探索パスを `families/<f>/numbering/` に。
      counter に **`iroha` を追加**（kanji は keiyaku で実装済み）。`continuous_articles`・
      `paragraph_ref_style: written`・附則参照の冠・`head_matter_levels` を宣言項目として整理。
      **insurance の 5 方式（nonlife/life/teikan/group/jyusetsu）を YAML に書き下ろす**のがここの山
      （宣言で書けない規則が出たら hooks に逃がし、理由を decisions に記録——宣言スキーマの表現力の実地検証）。
- [ ] semantic_type の 2 層化（コア共通語彙＋family 登録語彙。L00 検証）。契約書語彙 6 種を
      `families/contract/family.yaml` へ移す。
- [ ] lint の**要件値をファミリー宣言から読む**ようにする：L04（required スキーマ）・L10（tone）・
      L13（meta 必須）・L16（QA 配分）・**L20（骨格）**。規則そのものは keiyaku 実装のまま。
- [ ] denylist の 2 層化（コア共通 `docsynth/lint/denylist_common.txt` ＋ `families/<f>/denylist.txt`）。
- [ ] 自動 QA の質問文言からドメイン語を抜き、テンプレートをファミリーが差し替えられるようにする。
- [ ] 部分テンプレートの再編：ページ骨格を `docsynth/render/templates/base/` に、
      契約書固有（parties・head_matter・signature・form_fields・commentary）を
      `families/contract/styles/templates/` に。**ページ骨格の上書きは禁止**（bbox 抽出の前提が壊れる）。
- リスク：L03 のパターン自動生成が過検出する（「第N条」を含む定義文など）。keiyaku の除外規則
  （`{ref:}` 解決後の文字列は対象外・alias は単独出現のみ）を必ず引き継ぐ。

## P2 同等性 — 既に完成した 2 ドメインでリグレッションを固定する

**DoD**：姉妹の既存 content を新コアで再生成し、`source.json` / `layout.json` / `answer.json` / `qa.json` が
姉妹の生成物と一致（許容差：bbox 0.5pt、それ以外は完全一致。受け入れる差分は decisions に記録）。
CI（`make check`）に組込み。

- [ ] `families/insurance/` を作る（family.yaml・numbering 5 方式・blueprints・styles・library・denylist は
      yakkan からコピーし `genre→doctype` の読み替え）。対象は `oneday`・`teikan` 各 3 本。
- [ ] `families/contract/` を作る（keiyaku の blueprints 10・numbering 3・styles 4・library を移す）。
      同等性の対象は `nda`（条文型）・`lease`（頭書型）・`employment`（様式型）。
- [ ] 同等性テスト：`../insurance-contracts/content/` と `../contracts/content/` を読み取り専用参照
      （無い環境ではスキップ）。
- [ ] 差分が出たら「新コアのバグ」を既定として調査（仕様として受け入れる場合のみ decisions へ）。
- リスク：描画は CSS 1 行で全文書が変わる。**同等性 golden を先に立ててから**汎用化の後始末をする。

## P3 contract 完成 — keiyaku の資産を families/contract へ移し切る

**DoD**：10 doctype の blueprint・3 numbering・4 style・50 content が `families/contract/` に収まり、
全 doctype が lint / verify / review を通り manifest に ready。

- [ ] 残り 7 doctype（outsourcing / delegation / consulting / purchase / license / sysdev / contracting）の
      blueprint と content を移す。`genre`/固定値の読み替えだけを行い、**文章は触らない**。
- [ ] `families/contract/docs/structures.md` に keiyaku の **CT1〜CT25** を移す（`../contracts/docs/
      reference_structures.md`。分析ログの URL と入手日も持ってくる。**本文は写さない**）。
- [ ] `families/contract/docs/style.md`（文体・語彙・様式型の体言止め）を keiyaku の style_guide から抜き出す。
- [ ] 骨格 5 類型が全部 ready であることを確認（条文型・頭書型・様式型・約款型・逐条解説型）。
- [ ] `ct-a3-landscape-form`（A3 横・2 段）を持ち込むかを判断（既定：持ち込むが使う文書は 1 本）。
      **2 段 style には段またぎ要素を置かない。**
- リスク：`{party:}` を使っても**論理の取り違え**（甲乙逆転）は機械検出できない。
  reviewer サブエージェントの観点に「条ごとの主語の妥当性」を入れる。

## P4 terms — 深い入れ子リストと改定履歴

**DoD**：tos / privacy 各 1 文書が ready（lint/verify/review/qa とも error 0）。

- [ ] `families/terms/docs/structures.md`（実在の利用規約・プラポリ 4〜6 件の**構造のみ**）。
- [ ] numbering 2 方式（`web-terms` / `web-numbered`）と style 2 種。
- [ ] 3 階層入れ子リストの probe（grid のぶら下げが LineBox 対応を崩さないか。`docs/rendering.md` §7）。
- [ ] revision_history の描画と、改定日 ↔ effective_date ↔ 本文日付の整合（L11 の constants で縛る）。
- [ ] 執筆・QA・review。禁止事項の列挙（15 項目以上）は enumerations 評価の主資材になる。

## P5 regulations — 章立て・附則・別表

**DoD**：shugyo / kitei 各 1 文書が ready。

- [ ] structures.md（就業規則・一般規程。厚労省モデル就業規則は**構造のみ**参考にし文章は写さない。
      「ひな型だから著作権はない」と判断しない——`docs/reference_structures.md` §0）。
- [ ] numbering `kitei-standard`・style 2 種（A4 / B5）。
- [ ] 賃金表（wage_table）：`meta.constants` で等級×号俸の基礎値を持ち矛盾なく展開
      （等差・等比にしない。端数を混ぜる——転載の指紋と作り物っぽさの両方を避ける）。
- [ ] 附則（supplement）＋改正履歴（revision_history）の共存パターン。
- [ ] 執筆・QA・review。

## P6 statute — 法令（漢数字・イロハ・枝番・関係条つき別表）

**DoD**：law / jorei 各 1 文書が ready。`docs/schema.md` §11 の設計課題（relation_refs・目次の条範囲・
枝番）が実装で確定し decisions に記録されている。

**本プロジェクト固有の価値が最も大きいフェーズであり、姉妹に先例が無い**（借りられるのは
漢数字カウンタだけ＝keiyaku の `contract-kanji` で実証済み）。**憶測で実装せず probe を先に打つ。**

- [ ] structures.md（e-Gov の法令・自治体例規集の**構造**分析。条文は著作権対象外だが
      本プロジェクトの生成文はオリジナルに書く——`docs/families.md` §6）。
- [ ] **要probe 2 件**（`docs/rendering.md` §7）：条見出し 2 行構成、漢数字ラベルの幅。
- [ ] numbering `horei`（`iroha` counter は P1 で実装済みの前提）。variant で算用数字体。
- [ ] `Node.relation_refs`（別表「（第◯条関係）」）と `derived.toc[].article_range`（目次の条範囲）。
- [ ] `meta.promulgation` の描画（題名下の公布番号・公布文）。
- [ ] 条の枝番（`number_override`＋reason）の執筆例 1 箇所以上と L03 の整合確認。
- [ ] denylist（実在法令名・実在自治体名）。`law_number` の HITL 項目を起票。
- [ ] 執筆・QA・review。apply QA は「罰則の当てはめ」「経過措置の適用判定」が書ける（§5.1 の手順）。
- リスク：漢数字の正規化（第十二条 ↔ 12）が採点の突合に効く。`docsynth/eval/` の正規化と
  読み順・outline 突合を statute の golden で先に固定する。

## P7 データセット v1 — バッチ・QA・評価向け成果物・データカード

**DoD**：全ファミリー × doctype × content × 1–2 style が ready。
`docsynth eval --all --oracle` が全文書・全指標で満点。elements.jsonl・検索評価セット（V-S1〜V-S9 通過）・
manifest・`dataset/README.md`・**`dataset/data-card.md`** が揃い、`baseline_reader` の採点が全文書で完走する。

- [ ] 各 doctype の 2〜3 本目を執筆（題材・当事者・数値・構成を変える。`lint --similarity` 30% 未満）。
      **contract は keiyaku の 50 content があるので新規執筆は不要。**
- [ ] `specs/batch_v1.yaml`。batch は失敗しても止まらず段別・原因別に集計（yakkan 方式）。
- [ ] 自動 QA 30 問＋執筆 QA 15 問／文書（L14・L16）。`apply` は §5.1 の手順で確定させる。
- [ ] `docsynth export`（elements.jsonl・passages/queries/qrels・README・data-card 生成）。
- [ ] **弁別力の実測**（素朴な検索器 3 系統。`docs/evaluation.md` §7.2）とカードへの申告。
- [ ] V-A / V-B / V-C（`docs/validation_plan.md` §1〜2）を通す。
- リスク：執筆の量が最大の律速（yakkan 実績：1 文書 20〜50 分/エージェント。part 並列より
  1 文書 1 体が整合する）。`RenderLayoutError` は「帯」で起きる——字数を帯の幅以上動かす。

## P8 検証・硬化 — 外の読み手で契約の穴を出し切る

**DoD**：`docs/evaluation.md` §8 の 6 条件をすべて満たす。発見欠陥がすべて lint / verify / docs /
採点側の修正に落ちている。`HITL_TODO.md` の全項目に人間の決定が記入されている。

- [ ] V-D：ファミリーごとに 1 文書を VLM（自セッション）で読む。`cells`・`bbox` も出す。
- [ ] V-E：ファミリーごとに 1 文書（contract は骨格類型ごと）を盲検（独立エージェント）で読む。
      実例は `eval --oracle --dump-pred` で作る。**「仕様に書いていない」の報告が 0 になるまで続ける。**
- [ ] 発見欠陥の修正 → 影響文書の再生成 → oracle 満点の再確認、をループが涸れるまで。
- [ ] `HITL_TODO.md` の検証系項目（D5）を起票し、人間の決定を待つ・反映する。
- [ ] v1 確定タグ（**打つのは人間**。AI は `dataset_version` で版を表すところまで）。

## P9 拡張・手順書検証・配布

**DoD**：手順書（`docs/families.md` §7）だけを頼りに、別セッションが新ファミリー
（候補：官公庁の公示・入札説明書、金融商品の目論見書、マンション管理規約）を 1 つ追加できる。

- [ ] 手順書どおりの追加を第三者セッションで実施し、詰まった箇所を手順書に反映。
- [ ] style 追加・insurance 残り 8 genre の移植・eval 拡張は要件が来てから判断。
- [ ] 配布（`docs/distribution.md`）：`HITL_TODO.md` D2・D3 の決定後に、AI は生成と検査だけを行う。
