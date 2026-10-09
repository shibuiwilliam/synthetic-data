# decisions.md — 設計変更履歴

> フェーズをまたぐ設計変更・仮決め・probe の結論はここに追記する（CLAUDE.md §0.2-3）。
> 形式：日付／変更（決定）／理由／影響／状態（確定・仮決め）。新しいものを上に足す。

## 2026-10-06 生成物を AI モデルの学習・蒸留に使えないことの明記（両姉妹の決定を継承）

生成に使った技術の利用規約を両姉妹で洗い直した結果、**生成物の本文は Claude の Output であり、
Anthropic Usage Policy が事前許可なしの学習利用を禁じている**ことが確定した。
yakkan-synth（`docs/distribution.md` §7）と keiyaku-synth（`docs/publishing.md` §10）が同日に
成果物への明記を実装したので、docsynth も仕様として継承する。**配布条件（D2）の決定を待たずに確定できる**
——どのライセンスを選んでも消えない制約だからである。

| 日付 | 決定 | 理由 | 影響 | 状態 |
|---|---|---|---|---|
| 2026-10-06 | **「AI モデルの学習・蒸留には使えない」を、配布条件（D2）の決定と独立に確定する**（両姉妹 2026-10-06 の決定を継承） | 生成物の本文・表・図の説明・QA は Claude Code セッション内で Claude が書いた Output であり、Anthropic Usage Policy（2025-09-15 発効）が「入力と出力を AI モデルの学習（model scraping・model distillation を含む）に用いること」を**事前許可なしに禁じている**。この一項に「競合モデルに限る」の限定は無い。**どの配布ライセンスを選んでも消えない制約**なので、D2 の決定を待たずに確定できる。ただし CC BY 系は下流への追加制限を禁じている（CC BY 4.0 第 2 条(a)(5)(B)）ため、**ライセンス条件ではなく「告知」として書く**（拘束力のある条件にするなら独自ライセンスへの差し替えが必要で、それは D2 と併せた人間の判断） | `docs/distribution.md` §6 新設・ヘッダ・§1 のファイル表・§2 の検査・§4 の D2、`CLAUDE.md` §15。実装は P0 の移植時に姉妹の定数（`NO_TRAINING_EN` / `NO_TRAINING_JA` / `AUP_URL`）とテスト（`-k 学習`）を一緒に持ってくる。**「評価は学習ではない」を必ず併記する** | 確定 |

## 2026-10-05 姉妹プロジェクトが 2 本になったことへの追随（keiyaku-synth の到達点を取り込む）

発足（2026-09-22）時点の姉妹は `../insurance-contracts/`（yakkan-synth）1 本だったが、2026-09-26 に
**`../contracts/`（keiyaku-synth）が発足し、2026-10-05 にデータセット v1 を完成させた**。
keiyaku は yakkan のコードを移植したうえで、**本プロジェクトが P1 でやろうとしていた汎用化の大半
（`family`+`doctype`・宣言的 numbering・`{party:}`・新 kind/Block・lint L19 以降）を、contract 単一
ドメインの実装として先に済ませている**（`../contracts/docs/architecture.md` §6 に「将来 docsynth の
`families/contract/` として切り出せる形を保つ」と明記されている）。
yakkan 側も `dataset_version: v7`（10 genre・100 content・114 文書）まで進み、検索クエリの全面改修・
データカード・配布（Hugging Face / CC BY 4.0）を終えた。**両方の実証結果に仕様を追随させる。**

| 日付 | 決定 | 理由 | 影響 | 状態 |
|---|---|---|---|---|
| 2026-10-05 | **姉妹プロジェクトは 2 本**として扱う。`../insurance-contracts/`＝保険約款の参照実装（凍結）、`../contracts/`＝**契約書の参照実装かつコード供給元の第一候補**。どちらも本プロジェクトから書き換えない | keiyaku は yakkan の全資産＋汎用化の半分＋検証の階段 V-A〜V-F＋100 文書の実績を持つ。実証済みを再検証しない原則（§2-1）の適用先が 2 本になった | CLAUDE.md 冒頭・§0.3・§14、`docs/architecture.md` §6 | 確定 |
| 2026-10-05 | **P0 のコード基盤を keiyaku ベースに切り替える**（`../contracts/keiyaku/` → `docsynth/`）。insurance の資産（blueprints・styles・library・numbering 5 方式・content）は yakkan から `families/insurance/` として戻す | keiyaku には `family`+`doctype`（固定値 `contract`）・宣言的 numbering 3 方式（standard/form/kanji）・`{party:}`・`head_matter`/`commentary`・lint L19–L26・verify V01–V11・`datacard` が**実装済み**。yakkan から始めると同じ作業を 2 度やる。逆に keiyaku から始めると P1 は「固定値 `contract` をレジストリに開く」作業になる | P0・P1・P3 の内容（`docs/plan.md`）、`docs/architecture.md` §4・§5 | **仮決め**（人間の判断待ち。`HITL_TODO.md` D1。`../contracts/HITL_TODO.md` H10「docsynth 切り出しの範囲」と連動する） |
| 2026-10-05 | **lint は L00–L26 を継承**（yakkan L00–L18 ＋ keiyaku L19–L26）。本プロジェクトの新設は **L27 以降**、ファミリー固有は FLxx | 番号・意味を両姉妹と互換に保つと、移植コード・テスト・docs・3 プロジェクトの会話がそのまま通じる。L19（当事者整合）は本プロジェクトが先に設計し keiyaku が同番号で実装したので既に揃っている | CLAUDE.md §8、`docs/schema.md` §9、`docs/lint_rules.md`（新設） | 確定 |
| 2026-10-05 | **verify は V01–V11 ＋ V-P1〜V-P5 を継承**。とくに **V11（結合セルがページ境界をまたがない）** を初期仕様に含める | またぐと継続ページの列が空欄になり、**正解データのほうが誤りになる**（keiyaku で実害）。頭書型・様式型の大型表で踏みやすい | CLAUDE.md §6、`docs/rendering.md` §6 | 確定 |
| 2026-10-05 | **contract ファミリーの doctype を 4 → 10 にする**（nda / outsourcing / delegation / consulting / purchase / lease / license / sysdev / contracting / employment）。番号方式は 3 種（`contract-standard` / `contract-form`（条を持たない）/ `contract-kanji`（漢数字））、骨格は 5 類型（条文型・頭書型・様式型・約款型・逐条解説型） | keiyaku が 10 doctype × 5 content ＝ 100 文書で成立させた実績をそのまま family 化するのが最短で、かつ**骨格 5 類型は読み取り課題の幅そのもの**。旧 4 doctype（outsourcing/nda/sales/lease）は `sales`→`purchase` に読み替え | CLAUDE.md §4、`docs/families.md` §2、`docs/plan.md` P3 | 確定 |
| 2026-10-05 | contract のページ上限を **既定 12・絶対上限 20**（旧「10」）に。`employment` は 2–6、`contracting` は 10–18 | keiyaku の実測（657 ページ／100 文書・平均 6.6・最大 14）。10 では約款型・長文型が入らない | lint L09、`docs/families.md` §2 | 確定 |
| 2026-10-05 | スキーマに **`Node.kind: head_matter`（頭書）**・**`Block.commentary`（逐条解説）**・**`{party:<key>|role}`**・契約書の `semantic_type` 6 種（`fee_schedule` `deliverables` `inventory` `head_matter` `form_fields` `allocation`）を初期仕様として含める。頭書は `{ref:head}` → `kind_label` で解決する（`rider` と同じ「番号を持たず呼び名で解決する種別」） | keiyaku が P4・P5 で実装・実証済み（`../contracts/docs/schema.md` §11.1〜§11.5）。本プロジェクトの旧仕様には頭書・逐条解説が無く、`lease`・`license`・`purchase` を表現できない | `docs/schema.md` §5・§6・§11、`docs/rendering.md` §4 | 確定 |
| 2026-10-05 | **検索評価セットを 4 系統 → 10 種**（`term` `heading` `scoped` `filtered` `enumeration` `qa` `definition_masked` `multi_hop` `situational` `no_answer`）にし、検索指標に `exact_recall@k`・`r_precision`・`doc@1`・`confusion@k`・`false_positive_rate` を加える。`filters` は**クエリの一部**、索引した範囲は `index_setting` で申告する。**生成時の自己検査 V-S1〜V-S9** を必須にする | yakkan の実測：旧 `term`/`heading` は gold の `title` を字面コピーしていたため素朴な BM25 で nDCG@1 0.92 に飽和し、**順位の良し悪しを測る分解能が無かった**。さらに `qa` の gold が 76% 誤った文書を指していた。改修後は意味で引く 3 kind が 0.32〜0.39 に収まり、誤配は 0 になった | `docs/evaluation.md` §2・§7、P7 | 確定 |
| 2026-10-05 | **データカード `dataset/data-card.md` を成果物に加える**（規模・内訳・作り方・品質保証・制限と偏り・ライセンス）。`docsynth datacard update|check` を持ち、`make check` に鮮度検査を入れる。**数値は実ファイルから測り、固定文字列に焼き込まない。母数の小さい観点はカード自身が申告する** | 両姉妹で「仕様書に書いた統計値が実測と食い違う」事故が起きた（yakkan：クエリ 778 と書いて実測 1,170。keiyaku：`dataset/README.md` が統計値を焼き込んでいた）。使う側が素性を判断できる成果物が無いと、データセットとして配れない | `docs/data_card.md`（新設）、CLAUDE.md §1.2・§11、`docs/evaluation.md` §2.1 | 確定 |
| 2026-10-05 | `docs/authoring_checklist.md`・`docs/lint_rules.md`・`docs/distribution.md` を**本リポジトリに新設**する（姉妹の同名ファイルを参照するだけにしない） | 参照だけにすると移植時に落ちる／ファミリー横断の観点が書けない。lint が 27 規則＋FLxx になり「どのファイルのどの関数が検査しているか」の地図が無いと保守できない | `docs/`、CLAUDE.md §0.3 | 確定 |
| 2026-10-05 | **`HITL_TODO.md` を最初から置く**（従来は「P8 で起票」）。台帳形式（件名・種類・重さ・決定・経緯）とし、決定は `HITL_TODO.md` → `docs/validation_plan.md` §5 → `docs/decisions.md` の順に反映する | 人間の判断が要る項目は P8 まで待たずに**今**発生している（コード基盤の切替・配布条件・コードのライセンス）。両姉妹とも台帳方式に収束した | `HITL_TODO.md`（新設）、CLAUDE.md §0.2、`docs/validation_plan.md` §5 | 確定 |
| 2026-10-05 | `apply` 型 QA の答えは「**機械検算 → 読み幅の明示 → 人間の承認**」の 3 手順を踏んでから確定する。検算は正解プログラム（別プロジェクト・本体を書き換えない）で行う | keiyaku H5 の実績：47 問を形式仕様に落として検算し、一致 32・読み幅あり 15・不一致 0。読み幅のある 15 問だけを人間が承認した。`apply` は L14 の包含検査にも eval にも引っかからない | `docs/style_guide.md` §5、`HITL_TODO.md`、`docs/validation_plan.md` §5 | 確定 |
| 2026-10-05 | **商用 OCR / VLM API など外部サービスへ生成物を送らない**を既定とする（必要になったら HITL 起票） | 両姉妹で同じ判断（yakkan H7「不要」・keiyaku H8「不可」）。検証は規則ベース → 自セッション VLM → 盲検独立エージェントで足りている | `docs/validation_plan.md` §3・§4、`HITL_TODO.md` D4 | 仮決め |
| 2026-10-05 | 生成物の配布条件は**未決**。先例（yakkan：Hugging Face Datasets ＋ GitHub Releases・**CC BY 4.0**・`render.html` は配布しない）と手順を `docs/distribution.md` に書き、判断と実行は人間が持つ | 配布は取り消せない外向き操作で、コード側のライセンス（`pyproject.toml` が `Proprietary`・親リポジトリ直下は MIT）との食い違いも未解決 | `docs/distribution.md`（新設）、`HITL_TODO.md` D2・D3 | 仮決め |
| 2026-10-05 | `--misread` の単調性は**図が 3 点以上ある文書**で測る（旧「5 本以上」） | 契約書・規約・法令は図が 1〜2 点しかなく、5 本以上の文書を作ると不自然になる。keiyaku は図 3 点（ノード 24・辺 24・経路 9）の文書で単調性を固定できた | `docs/validation_plan.md` §1、`docs/plan.md` P7 | 確定 |
| 2026-10-05 | v1 の規模は **content を足して増やす。style を重ねて数を増やさない**。2 style 目は「版面が最も遠いもの」を選ぶ | 同系の style を重ねてもレイアウト頑健性の検証にならない（keiyaku H10 の決定・`../contracts/docs/doctypes.md` §7） | `docs/plan.md` P7、`specs/` | 確定 |
| 2026-10-05 | insurance ファミリーの移植元は yakkan の **v7**（10 genre・100 content・114 文書・番号方式 5 種・style 13 種）。同等性の対象は引き続き `oneday`・`teikan` | 発足時の記述（v1 相当）から規模が 4 倍になった。同等性 golden の対象を増やす判断は P2 の安定後 | `docs/families.md` §5、`docs/architecture.md` §6 | 確定 |
| 2026-10-05 | **statute（法令）は依然どちらの姉妹にも無い**。G8〜G13（漢数字・イロハ・枝番・目次の条範囲・関係条つき別表・公布情報・読替え表）は**未実証のまま**で、P6 で probe してから確定する。ただし漢数字カウンタだけは keiyaku の `contract-kanji`（約款型）で実証済みとして継承する | 本プロジェクト固有の価値が最も大きいのが statute であり、ここだけは先例を借りられない。借りられる部分（漢数字）と借りられない部分を分けて書く | `docs/schema.md` §11、`docs/reference_structures.md` §3、`docs/plan.md` P6 | 確定 |
| 2026-10-05 | CLAUDE.md の長さの目安を **250 行 → 350 行／35KB** に改める | ファミリー 5・doctype 20・lint 27 規則を扱う以上、表が伸びる。keiyaku も同じ理由で 350 行／35KB を目安にしている（yakkan 240 行・旧 docsynth 288 行） | CLAUDE.md §0.3 | 確定 |

## 2026-09-26 yakkan-synth 最終形への追随と statute 追加

yakkan-synth は 2026-09-22 の本プロジェクト発足後も進み、評価ハーネス・盲検検証・
残課題 38 件の解消（R/S/T/W/X/Y/Z）・フォント問題の修正を終えて完成した。
その最終形に仕様を追随させ、ユーザー指示（契約書・規約・**法令**）に基づき statute を足した。

| 日付 | 決定 | 理由 | 影響 | 状態 |
|---|---|---|---|---|
| 2026-09-26 | **`statute`（法令）ファミリーを v1 に追加**（doctype: law / jorei）。v1 は 5 ファミリー・14 doctype | ユーザー指示「契約書、規約、法令ドキュメント」のうち法令が未カバーだった。漢数字・イロハ・枝番・条範囲つき目次・関係条つき別表という独自の読み取り課題を持つ | `docs/families.md` §6、`docs/schema.md` §11、CLAUDE.md §4/§12、フェーズ P6 新設 | 仮決め（構造分析後に blueprint を確定） |
| 2026-09-26 | **評価基盤は「最小」にせず yakkan の完成形を P0 で丸ごと移植する**（eval 13 指標・検索 7 指標・elements.jsonl・検索評価セット・prediction/search_run スキーマ・oracle/misread・`--all`・manifest check・export README） | yakkan で残課題 7 次ループと盲検読み取りを経て固まった実証済み資産。削って再発明する理由が無い。旧 CLAUDE.md §9「最小に留める」を撤回 | `docs/evaluation.md` 新設、P0 の移植対象、CLAUDE.md §9 | 確定 |
| 2026-09-26 | **lint 番号を yakkan 最終形 L00–L18 と互換にし、当事者整合を L16 → L19 に改番** | yakkan は発足後に L16（執筆QA配分）L17（header_cols）L18（列挙表の caption 禁止）を追加した。移植コード・テスト・docs の番号突合を崩さないことを優先 | `docs/schema.md` §9、CLAUDE.md §8 | 確定 |
| 2026-09-26 | **フォントは `.ttf`（TrueType 輪郭）版を同梱**。`.otf` は出典検証用に併置。verify に「CFF 埋め込みが無いこと」を追加（V-P4） | yakkan 2026-09-26 実測：CFF（CID Type 0C）埋め込みは macOS Preview/Quick Look で本文が描画されない（41 文書中 26 文書。テキスト抽出系の検査では検出不能） | `assets/fonts/`、P0、`docs/rendering.md` §2 | 確定 |
| 2026-09-26 | 目次リーダー罫は `leader(' ')`＋`text-decoration: underline dotted`。`leader('.')` と `border-bottom` は禁止 | yakkan W6：`leader('.')` はテキスト層に「.」が入り CER 0.775。`border-bottom` は行高 0.4pt 増でページ送りが崩れ脚注が消えた | `docs/rendering.md` §2 | 確定 |
| 2026-09-26 | **検証・硬化を独立フェーズ P8 にする**（oracle → misread → 規則ベース読取 → VLM → 盲検独立エージェント → HITL の階段）。フェーズ番号を再編（statute P6・データセット P7・検証 P8・拡張 P9） | yakkan の実証：開発セッション自身の読み取り（3 本）では踏まなかった契約の穴が、盲検（3 本）では 2 本で出た。検証は生成の付録ではなく独立の工程 | `docs/validation_plan.md` 新設、CLAUDE.md §12、`docs/plan.md` | 確定 |
| 2026-09-26 | numbering 解釈器の counter に `kanji`（第十二条）と `iroha`（イ ロ ハ）を追加。同等性 golden の対象を 3 方式 → **5 方式**（nonlife/life/teikan/group/jyusetsu）に拡大 | statute に必須。yakkan は発足後に group / jyusetsu の 2 方式を追加しており、宣言スキーマの表現力検証には 5 方式全部が要る | `docs/schema.md` §7、P1 | 仮決め |
| 2026-09-26 | statute の条の枝番（第二条の二）は v1 では `number_override`（＋reason）で表現し、宣言的な branch 機構は作らない | 出現頻度が低く、既存機構で正解表現が成立する。宣言化は 2 ファミリー以上で必要になってから | `docs/schema.md` §11.2 | 仮決め |
| 2026-09-26 | statute の `law_number`（公布番号）は実在様式＋架空番号とし、実在法令との偶然一致を HITL レビュー項目にする | 様式を崩すと実物らしさが失われる。題名は denylist で守り、番号の衝突は人間が確認する | `docs/families.md` §6、`docs/validation_plan.md` §5 | 仮決め |
| 2026-09-26 | CLAUDE.md は 288 行（目安 250 行を約 40 行超過）で止めた | statute 追加と lint 再編で §4・§8・§12・§15 の表が伸びた。さらに削るなら §1.2 と §8 の表を docs 送りにする案があるが、毎セッション参照する頻度が高いため保留（yakkan も同様の経緯で一時 291 行を許容した） | CLAUDE.md | 仮決め |
| 2026-09-26 | 基底仕様確定後の yakkan 拡張（rider・badges・kind_label・article_heading・footnote_style・caption_numbering・図の resolved_labels・graph/paths・citation 系・enumerations・answer スリム化・outline 除外規則・L16〜L18）を**初期仕様に含める**一覧を `docs/schema.md` §1.1 に置く | 基底 docs は 2026-09-21 の写しで、その後の拡張は yakkan の decisions 等に散っており移植時に見落とす | `docs/schema.md` §1.1 | 確定 |

## 2026-09-22 プロジェクト発足時の初期決定

## 2026-09-22 プロジェクト発足時の初期決定

| 日付 | 決定 | 理由 | 影響 | 状態 |
|---|---|---|---|---|
| 2026-09-22 | プロジェクト名 `structured-docs`、パッケージ・CLI 名 `docsynth` | yakkan（約款）はドメイン名なので汎用側では使わない | 全体 | 確定 |
| 2026-09-22 | yakkan のコードは**コピーして改名**し、本リポジトリで発展させる。`insurance-contracts/` は凍結参照 | submodule/ライブラリ依存にすると、汎用化リファクタリングのたびに凍結側へ変更が波及する。二重メンテを避け、同等性テストで整合を守る方が安い | P0 の作業内容、`docs/architecture.md` §4 | 仮決め（P2 完了時に再評価） |
| 2026-09-22 | 正解スキーマは yakkan 互換＋差分（`genre`→`family`+`doctype`、`{party:}`、kind/Block 追加、schema_version 2.0） | 読み取り側が両データセットを同じローダで扱えるようにする | `docs/schema.md` | 仮決め |
| 2026-09-22 | renderer は WeasyPrint 70.0 固定。probe 実測 22 項目（yakkan-synth `docs/decisions.md` 付録）を再実測せず継承 | 同一版・同一機構なら結果は変わらない。再検証はコストのみ | `docs/rendering.md` | 確定（版を上げるときに要再probe） |
| 2026-09-22 | 番号方式は宣言的 YAML＋family フックの2段構え | ファミリー追加のたびにコアの numbering.py を書き換えないため。yakkan の3方式が YAML で表現できることを P1 golden で確認する | `docs/schema.md` §7 | 仮決め |
| 2026-09-22 | v1 ファミリーは contract / terms / regulations / insurance（移植）の4つ。insurance は同等性検証を兼ねる | 「契約書・利用規約・法的文書」という要望を、番号方式・当事者・文体が互いに異なる3ドメインで最小カバーし、汎用化のリグレッションは insurance で守る | CLAUDE.md §4、`docs/families.md` | **更新**（2026-09-26 に statute を加え5つ） |
| 2026-09-22 | ページ上限はファミリー既定（contract 10 / terms 10 / regulations 16 / statute 14 / insurance 20）、blueprint で上書き可 | 契約書に 20 ページ上限は緩すぎ、実物の分布に合わせる（statute は 2026-09-26 追加） | lint L09、verify | 仮決め |
| 2026-09-22 | 法令・裁判所は名称のみ引用、法令の条番号は書かない（yakkan 踏襲） | 誤った条番号を生成するリスクと検証コストを避ける。契約書で著しく不自然になったら doctype 単位で再検討 | `docs/style_guide.md` §2 | 仮決め |
| 2026-09-22 | 印影・手書き署名は描画しない。「印」の文字＋丸枠のみ | 読み取り検証の焦点はテキスト・構造・表・図であり、画像要素は決定論と正解表現を複雑にする | `docs/rendering.md` §3.2 | 仮決め |
| 2026-09-22 | 縦書き・ルビ・スキャン劣化画像は v1 対象外（yakkan 踏襲） | yakkan-synth と同じ判断。需要が出たら拡張フェーズで | CLAUDE.md §1.4 | 確定 |
| 2026-09-22 | v1 規模：4ファミリー・10 doctype × 2–3 content × 1–2 style ≈ 40–60 文書 | yakkan v1（約30文書）と同程度の密度をファミリー横断で | specs/、P7 | **更新**（2026-09-26 に 5ファミリー・14 doctype ≈ 50–70 文書 → 2026-10-05 に 5ファミリー・20 doctype。**style を重ねず content を足す**方針に変更） |

## 未決事項（既定値で進める前提。決まったら上の表へ）

**人間の判断が要るものは `HITL_TODO.md`**（D1〜D5）。ここには AI が既定値で進めてよいものだけを置く。

- `terms` の HTML 的装飾（リンク下線・アンカー風）をどこまで再現するか → 既定：再現しない（印刷風のみ）。
- `regulations` の別表（賃金表）の実額をどう作るか → 既定：`meta.constants` で等級×号俸の基礎値を持ち矛盾なく展開。
- insurance の残り 8 genre をいつ移植するか → 既定：P7 のバッチ設計時に判断（yakkan v7 は 10 genre）。
- contract の `commentary`（逐条解説）を何本持つか → 既定：keiyaku と同じく `license` の variant 1〜2 本。
  **母数が小さい観点としてデータカードが自動で申告する**（`docs/data_card.md` §4.3）。
- 様式型の選択欄の記号 → 既定：`■`（選択）/`□`（未選択）。`☑`（U+2611）は使わない（keiyaku 実測：
  本文フォントに無く記号フォントへフォールバックする）。「該当を〇で囲む」方式は P9 の拡張。
- keiyaku が持つ `ct-a3-landscape-form`（A3 横・2 段）を contract ファミリーに持ち込むか → 既定：持ち込むが
  v1 では使う文書を 1 本に限る（**2 段 style では段またぎ要素を置かない**。`docs/rendering.md` §2）。
