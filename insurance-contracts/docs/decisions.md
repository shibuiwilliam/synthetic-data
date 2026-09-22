# decisions.md — 設計判断の記録

CLAUDE.md §0.2-3 / §0.3 の運用ファイル。**設計変更・probe 結果・renderer 確定・仮決めはすべてここに1行追記する。**

- 書式：`日付｜変更｜理由｜影響範囲｜状態`。状態は **確定** / **仮決め**（既定値で進行中・要ユーザー確認）/ **撤回**。
- フェーズをまたぐ設計変更は、着手する**前**に追記する。
- 「要probe」項目は `scripts/probe_*.py` の実測結果（版・出力・判断）を添えてから確定にする。憶測で確定にしない。
- 撤回する場合は行を消さず、状態を「撤回」にして新しい行を足す。履歴を残すことが目的。

| 日付 | 変更 | 理由 | 影響範囲 | 状態 |
|---|---|---|---|---|
| 2026-09-21 | §15 の未決事項10項目をユーザー回答で確定（規模30文書／縦書き対象外／スキャン風なし／tagged PDF なし／QA 自動30+執筆15／bbox は pt原点左上+正規化併記／配布は dataset+manifest／法令は名称のみ／Python 3.12・uv） | プロジェクト開始にあたりユーザーが決定 | CLAUDE.md §15、全フェーズ | 確定 |
| 2026-09-21 | `travel` の題材は海外旅行保険風のまま仮進行。P4-a で参考URL #5 の実物構造を確認し、変更要否をユーザーに提案する | 実物の商品種別が未確認。確定まで作業を止める必要はない | `blueprints/travel.yaml`、travel の content | 仮決め |
| 2026-09-21 | CLAUDE.md を分割（§5→docs/schema.md、§6→docs/rendering.md、§7→docs/style_guide.md、§4.1+§4.2+付録A/B→docs/blueprints.md）。移設は行範囲の機械抽出＋diff で一字一句一致を確認 | §0.3 の前倒し。毎セッションのコンテキスト削減 | CLAUDE.md、docs/ | 確定 |
| 2026-09-21 | 上記に加え §3（構造分析）→docs/reference_structures.md、§1.1→docs/schema.md 冒頭、§10→docs/repo_layout.md も移設 | §3.2 が「分析結果は reference_structures.md に書く」と定めており追記先を一意にするため。§1.1 の検証対象表はデータモデルと不可分。§10 は250行目安に収めるため。いずれも要約せず全文移設 | CLAUDE.md、docs/ | 確定 |
| 2026-09-21 | `@docs/...` の import は使わない。参照はバッククォート付きのパス表記にし、「触る前に読む」を §0.3 の表で強制する | 公式ドキュメント（code.claude.com/docs/en/memory）で「Imported files are expanded and loaded into context at launch」を確認。import すると分割の目的が失われる | CLAUDE.md §0.3 | 確定 |
| 2026-09-21 | 恒常ルールは `.claude/rules/*.md` に置き、frontmatter `paths:` で対象ファイルを限定する | 同ドキュメントで path-scoped rule が現行仕様として利用可能なことを確認（「only load into context when Claude works with matching files」「Path-scoped rules trigger when Claude reads files matching the pattern」）。`paths:` 無しのルールは毎セッション読み込まれる | `.claude/rules/` | 確定 |
| 2026-09-21 | 分割後の CLAUDE.md は291行。250行の目安を約40行超過した状態で止めた | §0・§2・§8・§11・§12・§14 を要約せず残す指示と両立させた結果。さらに削るなら §1.2（成果物の構成）と §9（評価ハーネス）を docs 送りにする案があるが、毎セッション参照する頻度が高いため保留 | CLAUDE.md | 仮決め |
| 2026-09-21 | git は親リポジトリ `synthetic-data` をそのまま使い、`insurance-contracts/` 配下に `git init` しない。`.gitignore` は本ディレクトリに置く | 親（`/Users/shibuiyusuke/tmp/synthetic-data`）が既に git リポジトリで LICENSE/README を管理している。入れ子リポジトリは gitlink 化して事故のもと | リポジトリ運用 | 仮決め（ユーザー確認待ち） |
| 2026-09-21 | 親 `.gitignore` の `parts/` `lib/` `build/` `dist/` `var/` `downloads/` を、本ディレクトリの `.gitignore` で打ち消す | Python 汎用 ignore のため `content/<cid>/parts/*.json`（CLAUDE.md §13 でコミット対象と明記）が無言で除外される。`library/`, `build.py` は無事だが将来の `lib/` も危険 | `content/`, `library/` | 確定 |
| 2026-09-21 | `dataset/` は Git LFS を使わずコミット対象外にする | CLAUDE.md §13 の二択のうち、`specs/` から再生成できるため。§0.4-3「dataset/ は生成物であり手で書き換えない」とも整合 | `.gitignore` | 確定 |
| 2026-09-21 | WeasyPrint を `==70.0` で固定（当初 66.0 と書いたが PyPI 最新は 70.0） | CLAUDE.md §6.1 は `>=62` かつ「版を固定」。決定論（§0.4-4）のため `==` で固定する | `pyproject.toml`、全描画 | 確定 |
| 2026-09-21 | **renderer 確定：WeasyPrint を採用する**。box ツリー（`_page_box` → `element.get("id")` → `border_box_x/y()` + `border_width/height()`）で element id ごとの bbox が取れることを smoke で実測（122 断片／1 ページ）。段組で分割された要素は同じ id の box が複数現れ、§5.7 の `fragments` にそのまま対応する | CLAUDE.md §6.1 の「判断は P2 の probe 結果で確定」に対する回答。ReportLab への差し替えは不要 | `yakkan/render/`、`yakkan/layout/`、P2 全体 | 確定 |
| 2026-09-21 | `column-span: all` は WeasyPrint 70.0 で動作。段組コンテナ分割による代替は不要 | CLAUDE.md §14 の「要probe」項目。smoke で見出し・段またぎ表の両方で確認 | `styles/css/`、テンプレート | 確定 |
| 2026-09-21 | テキスト層の正規化ルールを確定：比較時に無視するのは空白（ASCII 空白・タブ・改行・U+3000）のみ。全角/半角の区別は保持し、NFKC 等の Unicode 正規化はかけない。テキストは `extract_text()` ではなく `page.chars` から組み立てる | §6.9 の「正規化ルールを明文化して吸収する」に対する具体化。`extract_text()` は原文にない空白を挿入するため使えない。digit_style の検証が全角半角の区別に依存する | `yakkan/verify/normalize.py`、§6.9 の往復検証 | 確定 |
| 2026-09-21 | 2 段組の読み順判定は、文字座標ではなく **box ツリー由来の段またぎ帯**（`span_bands`）を使う | 段またぎのキャプションは描画幅が段幅に満たず、文字座標だけでは左段の行と区別できない。誤判定すると段をまたぐ段落が割れる（smoke で実際に発生） | `yakkan/verify/normalize.py`、P2 の `layout.json` | 確定 |
| 2026-09-21 | SVG 内テキストは PDF のテキスト層に載る。往復比較では `region: "figure"` として本文から除外する | smoke で図のラベル 3 件が pdfplumber で抽出できることを確認。ヘッダ・フッタ・繰り返し表頭と同じ扱いが要る | §5.7 `layout.json`、§6.9 | 確定 |
| 2026-09-21 | テンプレート CSS に `body { margin: 0 }` を必ず入れる | `body` 既定マージン 8px が本文幅を左右 6pt ずつ削り、@page マージンの指定と実寸がずれる（box ツリーの実測で発覚） | `styles/css/`、テンプレート | 確定 |
| 2026-09-21 | フォントは `assets/fonts/` に実体を同梱し、SHA256 を `SOURCES.md` に記録する（計 36MB） | CLAUDE.md §6.2 の「同梱」に従う。決定論のためには版だけでなく実ファイルの同一性が要る。ダウンロードスクリプト方式は取得元の消滅に弱い | リポジトリ容量、`assets/fonts/` | 確定 |
| 2026-09-21 | BIZ UDP明朝 / BIZ UDPゴシックは P0 では取得しない | v1 の必須要素ではなく、当該スタイルは Noto で代替できる。取得元は `assets/fonts/SOURCES.md` に記録済み | 付録A `life-a4-1col-gothic` | 仮決め |
| 2026-09-21 | macOS では `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が必須。Makefile と `.claude/settings.json` の `env` で渡す | Homebrew の dylib が dyld の既定検索パスに無く、WeasyPrint の import が落ちる | 開発環境全体、CI を組むときも同様 | 確定 |
| 2026-09-21 | `dataset/` の手編集防止は `permissions.deny` の `Edit(/dataset/**)` と PreToolUse フックの二重で行う | 公式ドキュメントより、パス規則は `Edit(...)` でしか評価されない（`Write(...)` は無視され警告になる）。フックは拒否理由（作り直す手順）を提示できるため併用する | `.claude/settings.json`、`.claude/hooks/` | 確定 |
| 2026-09-21 | **仕様を追記**：`Cover` 型を定義した（§5.2 が `front_matter.cover: Cover` と書きながら型が無かった） | 表紙も PDF に文字列が出る以上、JSON から導出できなければ §0.4-3 に反する | `docs/schema.md` §5.2、`yakkan/models.py` | 確定 |
| 2026-09-21 | **仕様を追記**：`{const:<key>}` と `{auto_label}` を §5.3 のトークン表に追加し、`meta.constants` を §5.2 に追加 | §8 L11 が `{const:key}` と `meta.constants` を前提にし、§5.10 のサンプルが `{auto_label}` を使っているのに、トークン表にどちらも無かった | `docs/schema.md` §5.2/§5.3、`yakkan/richtext.py` | 確定 |
| 2026-09-21 | **仕様を追記**：`layout.blocks_side_by_side` を Table の型に明記（§5.4 の注記本文にしか無かった）。`MergedInto` も型として明記 | 実装時に型が無いと表現できない | `docs/schema.md` §5.4 | 確定 |
| 2026-09-21 | **仕様を追記**：§5.11「content ディレクトリの形式（parts）」を新設。`doc.json` ＋ `parts/*.json`（`target` と `items`）と定義した | §7.2 が parts 形式での執筆を指示しているのに、ファイルの形が未定義だった。lint と build の入力なので先に決める必要がある | `yakkan/compose.py`、`content/`、scaffold（P4） | 確定 |
| 2026-09-21 | **仕様を追記**：`Node.number_override_reason` を新設 | §5.2 が「lint で理由コメント必須」と書いているが、理由を書く場所が型に無かった。コメントではなくフィールドにした（JSON にコメントは書けない） | `docs/schema.md` §5.2、L03 | 確定 |
| 2026-09-21 | **lint 規則を追加**：L00「スキーマ検証（型・未知フィールド・執筆物への derived 混入）」を CLAUDE.md §8 に追加 | 「執筆物に derived が入っていたらエラー」を既存の L01–L15 のどれにも入れられなかった。pydantic の検証失敗全般を受け止める枠が要る | CLAUDE.md §8、`yakkan/lint/rules.py` | 確定 |
| 2026-09-21 | 用語定義（`defined_terms[].id`）には id 接頭辞を課さない（`policyholder` のような短い slug にする） | 当初 `term_` 接頭辞を付けたが、docs/schema.md §5.10 のサンプルが `{term:policyholder}` と書いており、DoD の「サンプルが lint を通る」と矛盾した。仕様のサンプルを正とした | `yakkan/ids.py`、`content/` | 確定 |
| 2026-09-21 | 括弧の全角/半角は `meta.digit_style` が一括で決める（life の号を `（１）`／halfwidth なら `(1)` と描く） | docs/rendering.md §6.4 の表は nonlife の項を `（１）`、life の号を `(1)` と書き分けているが、同 §が「全角/半角は meta.digit_style」と定めている以上、括弧だけ別の規則にはできない。表の表記ゆれと解釈した | `yakkan/numbering.py` | 確定 |
| 2026-09-21 | `{ref:}` の解決規則を確定：relative は最小共通祖先より下の鎖を連ね、**鎖が条から始まるときだけ**条の見出し文言を添える。short は条までで打ち切り見出し文言なし、full は根からの絶対表記＋見出し文言 | docs/rendering.md §6.4 の 3 例（「（２）」「第２条（通知義務）（２）」「第４章第３節第１条」）を同時に満たす規則がこれ。章・節まで遡る長距離参照に見出し文言を付けないのは実物の慣行とも一致する | `yakkan/numbering.py`、`tests/unit/test_numbering.py` のケース表 | 確定 |
| 2026-09-21 | `}}` を文字としての `}` と解釈するのは最上位だけにし、`{b:…}` `{u:…}` の内側では `}` を常に閉じ括弧として扱う | `{b:重要{u:な}}` の末尾がエスケープに化けて入れ子が壊れた。囲みの中に文字としての `}` を書く需要は無い | `yakkan/richtext.py`、`docs/schema.md` §5.3 | 確定 |
| 2026-09-21 | P1 の `{ref:}` は **ノード id のみ** を対象とし、表・図のブロック id への参照は lint L01 でエラーにする | 表・図の参照は「表１」「図１」というキャプション採番に依存し、採番は P2 の描画側で決まる。中途半端に実装するより、エラーメッセージで P2 送りと明示するほうが安全 | `yakkan/lint/rules.py`、P2 | 仮決め |
| 2026-09-21 | lint L12（定義語）は「`defined_terms` に無い `{term:}`」だけ先に実装し、「定義されたが使われない語」は P4 に回す | 前半は執筆中に毎回効く。後半は用語表が揃う P4 まで誤検知が多い | `yakkan/lint/rules.py` | 仮決め |
| 2026-09-21 | CLI の引数は typer の `Annotated` 形式で書く | 既定値に `typer.Option(...)` を置く旧来の書き方は ruff の B008 に抵触する。抑制するより現行の推奨形に合わせた | `yakkan/cli.py` | 確定 |
| 2026-09-21 | **renderer を WeasyPrint 70.0 で最終確定**（CLAUDE.md §6.1 の「判断は P2 の probe 結果で確定」への回答）。`scripts/probe_weasy.py` の実測表は下の付録に置いた | 「element id → bbox」が段またぎ・改ページの分割も含めて安定して取れることを 22 項目の probe で確認した。判断基準にあった (a) pdfplumber 整列への格上げ・(b) ReportLab 切替はどちらも不要 | `yakkan/render/`、`yakkan/layout/`、P2 以降すべて | 確定 |
| 2026-09-21 | 段またぎの表は `<table>` に直接 `column-span: all` を指定せず、**`<figure>`/`<div>` でくるんで** そちらに指定する | probe：`<table>` 直接指定は無視され段幅（246.6pt）のまま。くるむと本文幅（515.9pt）になる | `yakkan/render/templates/`、`styles/css/` | 確定 |
| 2026-09-21 | 欄外注（B6・`box.style = margin_note`）は **条末に小活字の囲みで置く**（docs/rendering.md §6.5 の (a)）。`float: footnote` は使わない | probe：`float: footnote` は本文内にそのまま残りページ下部へ降りない（WeasyPrint 70.0 未対応） | `styles/*.yaml` の欄外注位置、テンプレート | 確定 |
| 2026-09-21 | ルビは `<ruby>/<rt>` を使わず、**inline-block に読みと基底を縦積みする代替**で描く | probe：`<ruby>` は読みが基底の直後にインラインで並ぶだけでルビにならない（読みと基底の y が同一）。代替は実測で読みが基底の上に出ることを確認した | `styles/css/`、`{ruby:}` の描画（P6 で本格運用） | 確定 |
| 2026-09-21 | SVG の `<text>` には **必ず `font-family` を属性で明示する**。lint/verify で同梱外フォントの混入を検出する | probe：font-family 無指定の `<text>` は Arial Unicode MS（同梱外のシステムフォント）で描かれ、PDF にそのフォントが埋め込まれた。字幅の見積りが崩れるうえ再現性も失う | `yakkan/render/diagrams/`、verify | 確定 |
| 2026-09-21 | PDF のバイト再現性は `doc.metadata.created` / `modified` を固定値にし、`write_pdf(pdf_identifier=...)` を渡して担保する | probe：WeasyPrint 70.0 は `/CreationDate` を出力しないため未固定でもバイト一致したが、版が変われば入りうる。明示的に固定しておく | `yakkan/render/weasy.py` | 確定 |
| 2026-09-21 | **bbox の突合は IoU ではなく「box ツリーの bbox が pdfplumber の文字群を内包するか」で判定する**（docs/rendering.md §6.8-4 の「IoU 0.9」を置き換え） | probe：x は 0.00pt 一致するが、y は BlockBox 上端が文字上端より 4.93pt 上に出る（行の余白ぶん）。TextBox でも 4.15pt ずれる。これは仕様どおりの挙動で、IoU 0.9 は原理的に達成できない。内包判定なら意味があり誤検知もしない | `yakkan/layout/fallback_align.py`、`yakkan/verify/checks.py` | 確定 |
| 2026-09-21 | `leader('.')` と SVG の `<text>`、ルビの読みは **テキスト層に載る**ため、往復比較の前に領域（`region`）で除外する | probe：いずれも pdfplumber で抽出できた。ヘッダ・フッタ・繰り返し表頭と同じ扱いが要る | `layout.json` の `text_lines[].region`、`yakkan/verify/checks.py` | 確定 |
| 2026-09-21 | 図の SVG は自前で座標計算する方針を維持し、6 種すべてを実装した。ノード bbox は viewBox 内座標で返し、`<svg>` 要素の実寸から倍率を求めてページ座標（pt）へ変換する | CLAUDE.md §2-5。外部レイアウトエンジンを使わないので正解座標が自明に得られる。実測で倍率はちょうど 0.75（px→pt、CSS 縮小なし）になった | `yakkan/render/diagrams/`、`layout.figures` | 確定 |
| 2026-09-21 | 算式は SVG ではなく HTML/CSS で組む | 本文と同じフォント・同じテキスト層に載り、往復検証（§6.9）でそのまま比較できる。SVG にすると図と同じ「テキスト層に出るが box ツリーに出ない」問題を抱える | `yakkan/render/formula.py` | 確定 |
| 2026-09-21 | `annotated_mock` の `fields[].x/y/w/h` は証券枠に対する **0〜1 の相対値** と定める | 型に単位の定めが無く px とも読めた。相対値なら証券枠の寸法を変えてもフィールド配置が壊れない。lint L06 が範囲外を error にする | `docs/rendering.md` §6.7、`yakkan/render/diagrams/mock.py` | 確定 |
| 2026-09-21 | flowchart の分岐（列が違う相手へのエッジ）は、下辺ではなく **横の辺から出して相手の上辺に入れる** | 下辺から出すと本線（同じ列への直進エッジ）と重なり、ラベルも衝突した。目視で確認して修正 | `yakkan/render/diagrams/flowchart.py` | 確定 |
| 2026-09-21 | verify に V10（図）を追加：図のノード座標が layout にあること、ラベルが PDF のテキスト層から読めること | SVG の中身は box ツリーに出ないため、図が「描かれたつもりで空」でも他の検査は通ってしまう | `yakkan/verify/checks.py` | 確定 |
| 2026-09-21 | **参考URL 8 件の構造分析を完了**（`docs/reference_structures.md` の分析ログ）。取得は 8/8 成功。構造だけを測る道具 `scripts/analyze_reference_pdf.py` を追加した（本文を一切出力しない） | P4 の blueprint 設計に実測値が要る。文章を持ち込まずに構造を記録する手順を道具として固定した | `blueprints/`（P4）、CLAUDE.md §3.1 の追記案 | 確定 |
| 2026-09-21 | **#5（marinepass）は「リスク細分型海外旅行保険」と判明**。§15 の既定値「海外旅行保険風」と一致するため、**travel の題材は既定値のままで確定してよい**とユーザーに提案する | フッタの文書名で商品種別を特定。§4.1 の travel 必須要素とも矛盾しない | CLAUDE.md §15、`blueprints/travel.yaml` | 提案（ユーザー回答待ち） |
| 2026-09-21 | travel の blueprint に「節を使わないフラット階層」「小型判（約 106×151mm）の style」「全角括弧の項番号」を足す案。**回答をもらうまで仮案とし travel.yaml は確定させない** | 実物が節 0 回・ポケット判・全角括弧 997 回 | `blueprints/travel.yaml`、styles | 仮決め |
| 2026-09-21 | **CLAUDE.md §4 の「auto は 2 段組」は実物と食い違う**（#1 は 1 段組、2 段組だったのは #3 地震保険）。段組はジャンル固定にせず style 側の軸にする案を B-1 として提出 | 目視で確認。段組の自動判定は幅広の表があると誤るため目視を正とした | CLAUDE.md §4 の表、付録A、`blueprints/` | 提案（P4 で反映） |
| 2026-09-21 | **項の括弧幅を `digit_style` から独立させる案**（B-2）。実物は全角（#1#5）と半角（#2#3#4）で二分される | P1 で「括弧幅は digit_style が一括で決める」と判断したが、実測では同じ会社の商品間でも割れており、独立した軸として扱うほうが実物に近い | `yakkan/numbering.py`、`meta`、docs/schema.md | 提案（P4 で反映） |
| 2026-09-21 | **ルビを v1 の対象に戻す案**（B-9）。P6 送りをやめる | #3 の本文で実際に使われていた。P3 で代替実装（inline-block 積み）が動くことは確認済みで、追加コストが小さい | CLAUDE.md §15、`blueprints/quake.yaml` | 提案（ユーザー回答待ち） |
| 2026-09-21 | 条文ライブラリのディレクトリを `<genre>` ではなく **`<scheme>`**（nonlife / life / teikan）で切る | 同じ番号方式のジャンルは条の書き方も共通で、7 ジャンルぶん重複して持つ意味が無い。ジャンル固有の条は `applies_to` で絞る | `library/clauses/`、CLAUDE.md §7.6 の記述 | 確定 |
| 2026-09-21 | **目次は段組コンテナの外に置く**。テンプレートを修正した | 段組の中に 1 ページを超える `column-span: all` 要素があると、WeasyPrint 70.0 が以降の内容を黙って捨てる（目次 45 行で再現）。verify V05 だけが気づけた | `yakkan/render/templates/`、`styles/css/_base.css.j2` | 確定 |
| 2026-09-21 | WeasyPrint のページ分割アサーション失敗は `RenderLayoutError` として**明示的に失敗させる**。自動でレイアウトをずらす回避はしない | 内容の高さが特定条件に一致すると `assert not page_is_empty` で落ちる。レイアウトをずらして回避すると bbox とページ番号が変わり、正解データが壊れる | `yakkan/render/weasy.py`、`/batch` の手順 | 確定 |
| 2026-09-21 | `{auto_label}` の自動採番対象に `semantic_type: exclusions` を追加（`enumeration` だけでは足りなかった） | 免責事由の列挙も実物では ①②… が振られる。build が番号を振らず stub が空になる不具合をテストが検出した | `yakkan/build.py`、lint L03 | 確定 |
| 2026-09-21 | lint に `--skip`（`exclude`）を追加。抜粋やテスト断片では文書全体を見る規則（L04 / L09 / L12 / L15）を外せるようにした | L04 の実装後、3 ページの描画用 fixture が「完全な auto 文書」として検査されて落ちた。規則は正しいので、断片であることを呼び出し側が宣言する形にした | `yakkan/lint/runner.py`、`yakkan/cli.py`、tests | 確定 |
| 2026-09-21 | `chars_per_page_estimate` を実測で較正した（`scripts/calibrate_styles.py`）。1 ページ目に描かれた文字数を box ツリーから数える | 当初の見積りは最大 1.6 倍ずれていた。段落単位で数えると分解能が粗く別スタイルが同値になるため、文字単位で数える | `styles/*.yaml`、lint L09 | 確定 |
| 2026-09-21 | style を 8 種にした（付録A の 7 種 ＋ `nl-a4-1col-plain`） | P4-a で見つけた「装飾のない素組みの Web 配布 PDF」型（参考 #2）を oneday の既定にするため | `styles/`、`blueprints/oneday.yaml` | 確定 |
| 2026-09-21 | `@page` のサイズは CSS キーワードではなく **mm で明示**する | CSS の `B5` は ISO B5（176×250mm）で、JIS B5（182×257mm）と違う。style の yaml と実寸が食い違うと bbox 検証が狂う | `styles/css/_base.css.j2` | 確定 |
| 2026-09-21 | `life-a4-1col-gothic` の BIZ UDPゴシックは Noto Sans JP で代替する | 付録A は BIZ UD を指定しているが未取得（`assets/fonts/SOURCES.md`）。同梱外フォントを使うと verify V02 で落ちる | `styles/life-a4-1col-gothic.yaml` | 仮決め |
| 2026-09-21 | **目次を 2 パス描画にする**：1 パス目で実ページを測り、2 パス目で番号を文字として埋める | `target-counter` が長い目次で収束せず、印字と実ページが食い違う。正解データに誤ったページ番号を残せない | `yakkan/render/weasy.py`、`styles/css/_base.css.j2`、verify V04 | 確定 |
| 2026-09-21 | `.para`（ぶら下げ段落）に `break-inside: avoid` を必須にする | 無いと段またぎで grid が壊れ、本文がヘッダ帯に食い込む（実測 y=35pt）。P2 で記録した「ラベルだけ取り残される」問題も同時に解消 | `styles/css/_base.css.j2`。1 項は段の高さの半分までに収める制約が付く | 確定 |
| 2026-09-21 | 往復比較（V03）はヘッダ・フッタ帯の文字を除外して行う | ページをまたぐ段落の途中に次ページの furniture が挟まり、必ず不一致になる | `yakkan/verify/checks.py` | 確定 |
| 2026-09-21 | 目次の突合は見出し文言ではなく **目次行の id** で行う | 「第1条（この条項の補償内容）」が 3 章に現れ、別の章の行と突き合わせて誤検出した | `yakkan/verify/checks.py` | 確定 |
| 2026-09-21 | **前付け（preface / 目的別もくじ / 特約一覧 / ペットネーム表）をテンプレートで描画する**ようにした | それまでテンプレートに描画箇所が無く、JSON にはあるのに PDF に出ない状態だった。lint は source しか見ないので気づけず、verify V10（図の座標が無い）で発覚した | `yakkan/render/templates/document.html.j2`、`yakkan/render/html.py` | 確定 |
| 2026-09-21 | 段またぎの表（`span_columns: true`）は **14 行以下**。超えたら lint L05 が warn する | 1 ページを超える段またぎ要素は以降の内容を消す。執筆時に気づけるよう規則化した | `yakkan/lint/structure.py` | 確定 |
| 2026-09-21 | 脚注の所属先に **`appendix` を追加**（`appendix_section` は含めない） | 別表にも注記が付くのが実物。区分（「第1」）ではなく別表の末尾にまとめる体裁に合わせた | `yakkan/lint/walk.py`、L02 | 確定 |
| 2026-09-21 | L05 の `records` 照合は **トークンを解いた平文**で行う | `records` は「意味読み取り用の正規化レコード」なので、`{const:}` 入りの生テキストと突き合わせるのは筋が違う（author からの指摘） | `yakkan/lint/structure.py` | 確定 |
| 2026-09-21 | scaffold がライブラリ本文の数字を文書の `digit_style` にそろえる | ライブラリは 1 つの表記で書いてあるため、そのままだと L10 が「digit_style と逆の数字が混ざっている」と警告する | `yakkan/scaffold.py` | 確定 |
| 2026-09-21 | part は **章ごとに 1 ファイル**に割る（`20_<章id>.json`） | 1 ファイルにまとめると author サブエージェントを並列で走らせたときに衝突する | `yakkan/scaffold.py`、CLAUDE.md §7.2 | 確定 |

---

## 付録：WeasyPrint 70.0 の probe 結果（2026-09-21・`make probe`）

`scripts/probe_weasy.py` の出力。**設計はこの表を根拠にしている。** 版を上げたら再実行して差分を見る。

| 項目 | 結果 | 注意点 / 代替 |
|---|---|---|
| `_page_box` 走査で element id → border box | **対応** | 座標は `border_box_x/y()`、寸法は `border_width()/border_height()`（`border_box_width()` は存在しない） |
| 段またぎで fragment が複数になる | **対応** | 同じ id の BlockBox が段ごとに現れる（1 ページ内で 2 個＋次ページで 1 個を確認） |
| 改ページで fragment が複数ページになる | **対応** | 3 ページに分割された段落を確認 |
| TextBox のテキストと座標 | **対応** | 行単位の bbox が取れる。`text_lines` はここから作る |
| `target-counter` による目次ページ番号 | **対応** | 目次に出た数字と見出しの実ページが一致 |
| `leader('.')` | **対応** | ただし点がテキスト層に載る → 往復比較では除外する |
| `column-count: 2` | **対応** | 段幅 246.6pt（計算値と一致） |
| `column-span: all`（ブロック要素） | **対応** | 見出しは本文幅 515.9pt に広がる |
| `column-span: all`（`<table>` に直接） | **非対応** | 無視されて段幅のまま。**`<div>`/`<figure>` でくるむ** |
| `thead` の改ページ時繰り返し | **対応** | 繰り返された表頭も**同じ id** を持つ → `repeated: true` で区別する |
| `tr { break-inside: avoid }` | **対応** | ページをまたいで分割されたセルは 0 |
| `float: footnote` | **非対応** | 本文内に残る。欄外注は**条末に囲みで置く** |
| `<ruby>` / `<rt>` | **非対応** | 読みが基底の直後にインライン表示される（y が同一）。**inline-block 積みで代替**（実測で読みが上に出ることを確認） |
| インライン SVG の `<text>` がテキスト層に載る | **対応** | `region: "figure"` として往復比較から除外する |
| SVG の `font-family` 指定 | **対応** | **無指定だと Arial Unicode MS（同梱外）にフォールバックして埋め込まれる**。必ず明示する |
| PDF に `/CreationDate` | **出力されない** | 70.0 では元から入らない |
| PDF のバイト再現性 | **対応** | 未固定でも一致したが、`metadata.created/modified` と `pdf_identifier` を固定して担保する |
| px → pt（×0.75）・x 座標 | **一致** | box ツリーと pdfplumber の差 0.00pt |
| y 座標（BlockBox 上端 vs 文字上端） | **一致しない** | 差 4.93pt（行の余白）。TextBox でも 4.15pt。**IoU 判定は使えない → 内包判定にする** |

---

## 付録：確定前の CLAUDE.md §15（原文・2026-09-21 に確定表へ置換）

| 項目 | 既定値 | 選択肢 |
|---|---|---|
| データセット規模（v1） | 約 30 文書（7 genre × 3 content × 1–2 style） | 7 / 30 / 100 |
| `travel` の題材 | 海外旅行保険風 | 参考URL #5 の実物に合わせて変更 |
| 縦書き | 対象外 | P6 で表見出しの回転のみ |
| スキャン風劣化画像 | 対象外 | P6 で任意追加（傾き±1°・ノイズ・JPEG、bbox は同アフィン変換） |
| PDF のタグ付け（tagged PDF） | しない | `pdf_tags=True`（要probe）で構造タグ付き版も別 style として出す |
| QA の言語・件数 | 日本語、自動 30 問＋執筆 15 問／文書 | 変更可 |
| 正解 bbox の座標系 | pt・原点左上 | 正規化 [0,1] も併記（既定で併記する） |
| 配布形式 | `dataset/` ディレクトリ + manifest | tar.gz / HF datasets 形式 |
| 実在法令の条番号引用 | 引用しない（法令名のみ） | 正確性を担保できる範囲で引用 |
| 2026-09-21 | `@page` の章名を `string(chapter, first)` にする | 既定（last）はページ末に始まる章名を拾うため、ヘッダが1ページ先行して見えていた（health 担当の指摘、layout.json で再現確認） | 全 style。全文書のヘッダ文字列が変わるので再レンダリング済み | 確定 |
| 2026-09-21 | 別表の見出し（`h2[data-kind="appendix"]`）を `column-span: none` にする | span-all のままだと直後の span-all 表が残り高さに収まらず後続がまとめて次ページへ送られ、見出しだけがページ末に145pt の空白とともに孤立していた（auto p14 で実測）。`break-before: page` も `break-after: avoid` も span-all 要素には効かないことを実測で確認 | 2段組 style の別表見出しが段幅になる。auto はページ数15のまま孤立が解消 | 確定 |
| 2026-09-21 | `figcaption { break-after: avoid }` は**採用しない** | 表題と表本体の分離を防ぐ目的で試したが、health で脚注1件が box ツリーに載りながら PDF に描かれなくなり（V03 error）、ページ数も14→15 に増えた。WeasyPrint の既知の描画欠落を誘発する | 表題と表が別ページに分かれる場合が残る（既知の制約として gotchas に記録） | 確定 |
| 2026-09-21 | 表紙にペットネームを描画する | `Cover.pet_name` がモデルにありながらテンプレートが描いておらず、JSON にだけ存在する文字列になっていた（health・travel 両担当が独立に指摘） | `document.html.j2` に `cover_petname` 要素を追加。`.cover-petname` の CSS も追加 | 確定 |
| 2026-09-21 | `rasterize()` は描画前に `pages/page-*.png` を一掃する | 前回より短い文書を描くと古いページ画像が残り、存在しないページを目視レビューしてしまう（life 担当が page-018.png の残留を報告） | `yakkan/render/weasy.py`。再レンダリングで自動的に解消 | 確定 |
| 2026-09-21 | 段組内の span-all 表は原則使わない | auto の短期率表を `span_columns: true` にしたところ、**後続の別表3が丸ごと描画されなくなった**（V04/V05 が検出）。P4-b で記録した「span-all が段組内で後続を落とす」現象の再現 | 横長表は列数を減らすか見出し語を短縮して段内に収める。verify V04/V05 が安全網 | 確定 |
| 2026-09-21 | verify V05 を「source の全要素 id が layout に現れるか」に拡張 | 従来は `derived.labels`（ノードのみ）を見ていたため、**表や図が丸ごと描画されなくても検出できなかった**。quake で `tbl_ch1_a5_limits` と `tbl_app1_goods` が verify 通過のまま消えていた（担当エージェントが独立に発見） | `yakkan/verify/checks.py`。図の内部ノードは `layout.figures[].nodes` 側と突き合わせる。全7文書で再実行し error 0 を確認 | 確定 |
| 2026-09-21 | teikan の `target_pages` を [6,10] → [8,12] に広げる | reviewer の最大の指摘が「本文4,300字は実物の定款より明らかに薄い」だった。条を8本・1章追加して6,649字・12ページになり、密度を取ると6〜10ページには収まらない（この style の実測密度 約700字/ページ）。ハード上限20は余裕がある | `blueprints/teikan.yaml`。L09 の恒常 warn が消える | 確定 |
| 2026-09-21 | `@page` のヘッダを「編＋章」にする（`string(part, first) string(chapter, first)`） | life で同じ「第３章」が第１編（保険料のお払込み）と第２編（ご契約後のお取扱い）の両方に現れ、**`header_path` の正解が一意に決まらなかった**（reviewer 指摘） | `part` と `chapter` を別の string に立てる。タグは両方 h2 のまま（h1 にしたら版面が動いて WeasyPrint の assert を踏んだ）。区切りの U+3000 は part 側の string に含めるので、編を持たない文書ではヘッダが変わらない。別表では part を空に戻す | 確定 |
| 2026-09-21 | ヘッダの章名は `first`（`start` は採らない） | `start`（ページ先頭時点の値）だと**章が始まるページで前の章名または空が出る**（life p4 が空、p5 が第１章）。`first`（そのページで最初に立った値）なら章の開始ページはその章名になる。残る欠点は「ページ途中で次章が始まるとき、ページ前半の章が出ない」だが、頻度と実害が小さい | 全 style。実測比較を `docs/gotchas.md` に記録 | 確定 |
| 2026-09-21 | 図の内部ノードの bbox は `layout.figures[].nodes` にある（`layout.elements` には無い） | reviewer が「図ノードの bbox が無い」と報告したが、実測すると `figures[].nodes` にページ座標（pt）で全ノード入っていた。P3 の設計どおりで**欠陥ではない** | 変更なし。P5 の QA 生成は `layout.figures` を見る | 確定 |
| 2026-09-21 | 参照表の `records` を機械導出し、lint L05 に「参照表に records が無い」warn を追加 | P4-c で執筆した7文書の表がほぼすべて `records: null` で、CLAUDE.md §2-4 の「grid と records/header_path の二重表現」を満たしていなかった（quake・health 担当の reviewer が独立に指摘）。records が無いと table_lookup / table_reason QA の正解が grid の文字列照合に退化する | `scripts/fill_records.py`（結合セル無し・表頭1行の表を機械導出）で34表を生成。列挙表（enumeration/exclusions）は「文と一体の箇条書き」であって参照表ではないので対象外。結合セルのある表（定義表の五十音列・等級表）は手で埋める | 確定 |
| 2026-09-21 | lint L05 の records 突合で `{ref:}` を build と同じ結果に解決する | `_plain` が `resolve_ref` を空文字にしていたため、**参照を含むセルの `records` が必ず「grid に無い」error になっていた**（oneday 担当が回避策を取らざるを得なかった）。参照入りセルを持つ表に records を付けられないのは §2-4 の二重表現と両立しない | `yakkan/lint/structure.py`。参照元は表を抱えるノードの id（build の `from_id` と同じ） | 確定 |
| 2026-09-21 | oneday の `target_pages` を [8,12] → [8,14] に広げる | reviewer 指摘①（一覧表が掲げる5保険金のうち2つに条文が無い）を直すと2条増え、12ページに収めるために**定義表12語の定義文をすべて1行に圧縮**する必要があった。実物の定義表は2〜3行が普通で、読み取り検証用データとしての価値が落ちる | `blueprints/oneday.yaml`。定義文を実物相当の長さに戻す | 確定 |
| 2026-09-21 | 章見出し（h2）の `column-span: all` を **`column-span: none`** にする | **段組の中に収まらない段またぎ要素があると WeasyPrint はそれ以降の内容を黙って捨てる。** auto-0001 で `ch3_a5_p1` に60字足すだけで 16→11 ページになり、第5章以降（基本条項・特約3本・別表2本・奥付）が全部落ちる再現を取った。しかも通っていた16ページ版は「見出し帯がページ最下部にぎりぎり収まっていたから」通っていただけで、前方の字数がわずかに増えれば同じ事故が起きる状態だった（auto 担当の発見） | 2段組の章見出し帯が段幅になる。auto 16p・health 14p で verify error 0。**この失敗モードが構造的に消える**のが決定理由。別表見出しは 2026-09-21 に同じ理由で先に対応済み | 確定 |
| 2026-09-21 | `render` が内容欠落を検出したら `RenderLayoutError` で止まる | verify まで待つと壊れたデータセットが `dataset/` に書き出される。CLAUDE.md §2-7「失敗は早く・明示的に」に従い、レイアウト抽出の直後に source の全要素 id を突き合わせる。対処法（span_columns を false に／列数を減らす／直前の字数を増減）をメッセージに出す | `yakkan/render/weasy.py` の `_assert_nothing_dropped`。検査本体は verify の `check_fragments` を再利用 | 確定 |
| 2026-09-21 | L09 の字数は**トークンを解いた平文**で数える。係数を7文書の実測で較正 | 生の RichText を数えていたため `{term:liability_period}`（生23字／表示4字）のような長い id を丁寧に使った文書ほど不利だった（travel は生21,138字／平文16,097字。担当の指摘）。さらに較正前は推定ページ数が最大 +28%／−11% の系統誤差を持ち、**L09 の warn が恒常的に出て無視される状態**だった（3体のエージェントが独立に報告） | `FRONT_MATTER_PAGES=3.0` `TABLE_FACTOR=1.25` `FIGURE_PAGE_SHARE=0.24` `HEADING_PAGE_SHARE=0.005`（見出し数の項を新設。定款のように条が多く本文が短い文書は字数だけでは必ず過小評価になる）。最大相対誤差 5.6%。7ジャンルの `chars_min/chars_max` も平文基準に再設定 | 確定 |
| 2026-09-22 | `travel` の題材は**海外旅行保険で確定** | 参考URL #5 の実物は WebFetch の要約では傷害保険と誤判定されたが、PDF を直接見て「リスク細分型海外旅行保険」と確認済み。travel-0001 も海外旅行保険として14ページ完成している（ユーザー回答） | CLAUDE.md §4 の travel 行と §15 を更新。blueprint の仮案フラグを外す | 確定 |
| 2026-09-22 | CLAUDE.md §3.1 に A7・B8・C9・C10・E5–E7・F1–F3 を追記 | P4-a の実測で見つかった、現行カタログに無い要素（縦書きタブ／側注／斜線見出しセル／2段ヘッダ／ページ継続ラベル／商品名バッジ／頁番号の書式／体裁レベル）をユーザーが採用 | 読み取り課題カタログが増える。F3（イラスト）は生成対象外を明記 | 確定 |
| 2026-09-22 | ルビは v1 では作らない | §14 で「要probe」のまま未実装。P6 送り（ユーザー回答） | `<ruby>` の probe も P6 まで保留 | 確定 |
| 2026-09-22 | quake の2スタイル目を `nl-a4-2col-mincho` → `nl-a4-1col-gothic` に | 現在の内容では A4 2段で WeasyPrint の `AssertionError` を踏み、字数調整では通らなかった。B5 2段 vs A4 1段のほうが版面差が大きく、レイアウト頑健性のデータとしてはむしろ有利 | `blueprints/quake.yaml`。11ページ／14ページの2本とも verify error 0 | 確定 |
| 2026-09-22 | `yakkan clean` コマンドを追加 | スタイルを差し替えると古い `dataset/<doc_id>/` が残る。手で `rm` すると `dataset/` の手編集禁止（§0.4-3）と区別がつかないので、**掃除もコマンドで行う**。消すのはディレクトリ単位だけで中身の部分編集はしない | `yakkan clean --stale` で content と blueprint の宣言スタイルから外れた生成物を一掃できる | 確定 |
| 2026-09-22 | `fragment` が自分の `text_lines` を覆うように広げる | 段またぎの脚注で、id を持つ span の box が右段の1行目を含まず、行だけが先に出ていた（quake B5 の V08 warn の正体）。fragment と text_lines はどちらも正解データなので食い違ったままにしない | `yakkan/layout/extract.py` の `_extend_fragments_to_lines`。全8データセットで V08 warn が 0 になった | 確定 |
| 2026-09-22 | P4-c の20コミットを1つに squash する | 修正前の写し疑いの文（暴動の定義、後遺障害等級表の障害の程度の文言と支払割合の数列、視力測定方法の備考文、常用漢字外を避けた交ぜ書き表記など）が中間コミットの履歴に残っており、§0.4-1「リポジトリに入れない」に反する。未 push（`origin/main` は初期コミットのみ）なので今なら安全に消せる（ユーザー回答） | 機能単位のコミット履歴（§13）は失われるので、まとめたコミットメッセージに各段階の要約を残す。最終ツリーは変わらない | 確定 |
| 2026-09-22 | ヘッダの章名は `string(chapter, first)` のままとする（**実測で確定**） | 3人の担当が独立に「ページ冒頭が前章なのにヘッダが次章になる」と報告したので、全13データセット242ページで「ヘッダがそのページの**本文の主の章**と一致する割合」を測った。**`first` 87.6% / `start` 53.7%。** `start` は章の開始ページで前章名または空になるため、かえって外す | 変更なし。残る12.4%は「ページ途中で次章が始まり、前半が前章」のページ。実物の約款でも起こる範囲なので許容する | 確定 |
| 2026-09-22 | ヘッダの経路を **1 本の文字列**としてテンプレートから渡す（`data-headerpath` ＋ `string-set: chapter attr(...)`） | 編と章を別々の CSS string に立てていたため、**編の境界がページ途中に来ると別々の編の値を拾って噛み合わなかった**（life-0002 で「第２編　普通保険約款　第６章　税制上のお取扱い」と出たが、第６章は第１編）。`header_path` の正解として誤り | `yakkan/render/html.py` が `derived.labels[].path` から組んで `data-headerpath` に入れ、CSS は `attr()` で受ける（WeasyPrint で使えることを probe で確認）。ヘッダは余白ボックスなので本文の版面は動かない。別表は編の外なので祖先を付けない | 確定 |
| 2026-09-22 | 表の幅は **格子の位置数**で数える（`colspan` を足さない）／結合とプレースホルダの対応を検査する | quake-0002 の担当が 2 段ヘッダ（§3.1 の C10）を作ろうとして詰まった。原因は L05 の列数計算だけで、`expand_grid`・`header_paths`・描画は最初から `colspan` に対応していた。結合位置には `merged_into` のプレースホルダを置く規約なので、`colspan` を足すと二重に数える | `yakkan/lint/structure.py`。既存文書に `colspan` の使用例はゼロなので再描画は不要。C10 が作れるようになり、カタログと実装の食い違いが解消した | 確定 |
| 2026-09-22 | 表・図の番号は**キャプションのあるものだけ**に振る | 文と一体の列挙表（「次に掲げる事由」の受け）はキャプションを持たず、実物の約款でも「表N」を振らない。これを数えていたため読者に見える番号が「表１→表３」と飛んでいた（P5 の執筆担当 4 人が独立に報告） | `yakkan/build.py` の `assign_caption_labels`。表の約半数が番号を失い、残りが繰り上がる。図は全てキャプションを持つので不変。執筆QAで表番号を書いていた 1 問（teikan-0001）を書き換え、28 データセットを再生成して verify・qa とも error 0 | 確定 |
| 2026-09-22 | `figure_path` の答えが図に実在するラベルかを L14 で検査する | 図の答えは包含検査の対象外で、**間違った答えが素通りしていた**（親自身が travel-0003 の執筆QAで存在しないノード名を書いた）。timeline の区間は軸の目盛で答えるので、ノードのラベルだけでなく `from`/`to`/`ticks` も集める | `yakkan/qa/validate.py`。既存の 1,262 問すべてで error 0 を確認 | 確定 |
