# gotchas.md — 環境固有の癖・落とし穴

> 環境・ライブラリの癖はここに追記する（auto memory に任せない。CLAUDE.md §0.3）。
> **基底：`../insurance-contracts/docs/gotchas.md` の全項目は本プロジェクトでも有効。**
> `render` / `layout` / `verify` を触る前に必ず基底を読む。本ファイルには**本プロジェクト固有の発見だけ**を足す。

## 基底から特に忘れやすいもの（要点の再掲。詳細は基底ファイル）

- **段またぎ要素（`column-span` 見出し・`span_columns` 表）があると、WeasyPrint はそれ以降の内容を
  黙って捨てることがある。「レンダリング成功」≠「内容が全部載った」。** 内容欠落検出
  （全要素 ≥1 fragment、`_assert_nothing_dropped`）を無効化しない。
  ——契約書は 1 段組なので `column-span` は使わないが、**枠つきブロック（`commentary`・囲み注）が
  ページ境界で割れると続きが版面の外に出る**という同系の事故がある。
- WeasyPrint の box ツリー（`_page_box`）は**私的 API**。版固定（70.0）。座標は
  `border_box_x()/y()` ＋ `border_width()/height()`。box 種別で白リストしない。`text_lines` は LineBox 単位。
- 単位：WeasyPrint は CSS px、PDF は pt（**×0.75**）、PNG は dpi/72 倍。原点は左上。
- ヘッダ/フッタ判定は y 座標ではなく **MarginBox の `at_keyword`**。
- 繰返し表頭・ヘッダ/フッタはテキスト層に複数回現れる。`repeated` / header/footer として**区別してから**比較。
- `<table>` 直接の `column-span: all` は効かない（wrapper で包む）。`float: footnote` は未対応。
- SVG `<text>` には `font-family` / `font-size` を必ず明示（無指定はシステムフォントが埋め込まれ再現性が壊れる）。
- 記号（丸数字・☑ □ ㎡ ○△×）はフォントによって欠ける。**L07 のフォント被覆検査を render 前に必ず実行**
  （`--quick` では飛ぶ）。長い欧文だけ `overflow-wrap: break-word`。
- **`leader('.')` はテキスト層に「.」を残す**（1 ページ数百字。CER が 0.775 になった）。目次のリーダー罫は
  `leader(' ')`＋`text-decoration: underline dotted`。**`border-bottom` は行高が 0.4pt 増えてページ送りが
  崩れ、別文書の内容が消える**（box の大きさを変えない描き方を選ぶ）。
- **WeasyPrint が CFF（`.otf`）を埋め込むと macOS の Preview / Quick Look で本文が描画されない。**
  pdfplumber・pdfium・poppler では読めるため往復検証では検出できない。同梱フォントは `.ttf` を使い、
  `pdffonts` で `CID Type 0C` が無いことを確認する（verify V-P4）。
- `RenderLayoutError` は「**帯**」（yakkan 実測 48 字幅）で起きる。帯の中で字数を振っても通らない——
  **帯をまたぐ量を動かす**（`scripts/probe_layout_band.py` で測れる）。
- **サブエージェントに執筆を任せている間は共有コード（CSS・テンプレート）を触らない**
  （幻の失敗を追わせる）。verify の強化だけは描画結果を変えないので例外的に安全。
- 「fragment はあるのに PDF にテキストが無い」ときは bbox が版面の外（マージン帯）に出ていないか見る。
- 較正（`chars_per_page_estimate`）は**実コーパス基準**。合成較正は `break-inside: avoid` のせいで
  段落単位に量子化され、別版面が同値になる。
- macOS：Homebrew の dylib は dyld の既定検索パスに無い。`make` 経由で
  `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が渡る。素の `uv run` では自分で付ける。
- git：**親リポジトリの `.gitignore` の `parts/` が `content/<cid>/parts/` を無言で除外する。**
  ディレクトリ単位の否定（`!parts/` `!content/**/parts/`）で打ち消し、`git check-ignore -v` で確認する。
- PDF のメタデータ日時を固定しないとバイト差分が出る（テキスト層一致が必須、バイナリ一致は目標）。

## 参考 PDF の計測の癖（`scripts/analyze_reference_pdf.py`）

- **段組の自動判定は幅広の表があると誤る。段組は目視を正とする。**
- 和文 PDF は `extract_text` が原文にない空白を字間に入れる。空白を潰してから数える。
- MediaBox の原点が (0,0) でない PDF がある。ToUnicode の無いフォントはテキスト計測不能
  （その場合は「目視のみを根拠」と明記する）。
- `samples/` の**ページ数はファイル全体**の数であり「契約書本体」の長さではない
  （逐条解説つきモデル契約は解説が大半。経産省モデル契約書 205 ページは複数の契約書＋解説の合本）。

## 本プロジェクト固有

### 姉妹プロジェクトを誤って書き換えた（2026-09-26）

**症状**：`contracts/tests/golden/sample_min/parts/30_ch4.json` を編集したつもりが、
`insurance-contracts/` 側の同名ファイルを書き換えていた。

**原因**：Bash の作業ディレクトリは呼び出しをまたいで保持される。直前のコマンドが
`cd ../insurance-contracts` を含んでいたため、次の `cd tests/golden/sample_min` が
**姉妹プロジェクト配下**に解決された。ファイル構成が 3 プロジェクトで同じなので、
相対パスは同じ形のまま別の実体を指す。

**対処**：`../insurance-contracts/` と `../structured-docs/` を読むコマンドを実行したあとは、
**書き込みを伴う操作では必ず絶対パスを使う**（`cd` に頼らない）。
姉妹プロジェクトは読み取り専用なので、汚したら `git checkout -- <path>` で即座に戻す
（親リポジトリで追跡されているので復元できる）。作業の切れ目で
`git status --porcelain ../insurance-contracts/ ../structured-docs/` が空であることを確かめる。

### `inline-block` は 1 つの id に 3 box を作る（2026-09-26・`scripts/probe_signature.py`）

**症状**：記名押印欄の「印」（`display: inline-block` ＋ `border-radius: 50%`）を box ツリーで数えると、
同じ `id` に **InlineBlockBox / LineBox / TextBox の 3 つ**が現れる。

**実測**：`InlineBlockBox x=144.18 y=54.85 w=34.82 h=34.82`（丸枠の実体）／
`LineBox x=157.59 y=55.25 w=8.00 h=34.02`／`TextBox x=157.59 y=66.51 w=8.00 h=11.50`。
**丸枠の寸法を持っているのは InlineBlockBox だけ。**

**なぜ実害が出ないか**：本番の抽出器（`keiyaku/layout/extract.py` の `_walk`）が
`TextBox` と `LineBox` を bbox の対象から除外しているので、断片は 1 つに落ち着く。

**注意**：`extract.py` の除外規則を「取りこぼしを減らすため」に緩めると、
inline 要素の bbox が 3 重に出て IoU 評価が壊れる。**除外は意図的なもの**である
（同ファイルのコメント「box 種別で絞らない」は BlockBox 系の話で、TextBox/LineBox は別）。
probe を書くときも、`boxes_by_id` のような素朴な helper ではなく
本番と同じ規則（`production_fragments`）で測る。

### 表題（`<caption>`）は表の中にあってもページ境界で離れる（2026-09-26）

**症状**：別紙の表で、`tbl_scope__caption` が p2（y0=726.5）、全行が p3（y0=71.1）。
表題だけが前のページに取り残された。

**なぜ意外か**：yakkan は「表題を `<figcaption>`（表の外）から `<table>` の `<caption>`（表の中）へ移す」
ことでこれを 23/320 表 → 0 にしている。**中に置いても、表そのものがページ境界で割れると離れる。**
yakkan は 2 段組で、表が段の途中から始まる幾何が違ったため踏まなかったと思われる。

**対処**：`table > caption { break-after: avoid; }` を**caption にだけ**当てる。
`break-*: avoid` を本文ブロックに当てると内容欠落を招く（yakkan の実害）が、caption は小さな box なので安全。
入れたあと、render の内容欠落検出（全要素 ≥1 fragment）と verify V03 で内容が落ちていないことを確かめる
（実測：要素 124 件すべてに fragment あり、ページ数 3 のまま、verify error 0）。

### 図の格子座標は 0 起点。負にすると版面の外に出る（2026-09-26）

**症状**：flowchart の分岐先を `col: -1` に置いたら、ノードと辺ラベル「交付を受けたもの」が
SVG の左端で切れた（「り」だけ見える状態）。**verify は通る。目視でしか見つからない。**

**原因**：`keiyaku/render/diagrams/flowchart.py` が `cx = PADDING + col * CELL_W + CELL_W / 2` で配置し、
`cols = max(col) + 1` で viewBox の幅を決めている。負の col は viewBox の外になる。

**対処**：L06 に「格子座標が負なら error」を足した（2026-09-26）。左に置きたいときは全体をずらす。

### ラベル欄の幅は「その文書に実際に出るラベル」から決める（2026-09-26）

**症状**：項ラベル「２」に対してラベル欄が広すぎ、「２　　　　第１項の義務は」のように間延びした。

**原因**：CSS に `--label-w: 3.6em` と**固定値**で書いてあった。保険の項ラベル「（１）」（3 文字）に
合わせた値で、契約書の「２」（1 文字）には広すぎる。
`docs/rendering.md` §2 の「ラベル欄の固定幅は使わない」に反していた。

**対処**：`keiyaku/render/html.py` の `label_widths()` が `derived.labels` を走査して kind ごとの
最長ラベルを測り、CSS に渡す（全角 1.0em・半角 0.5em ＋ 余白 0.6em、下限 1.4em）。
実測：契約書は `paragraph` が 1.6em、保険は 3.6em になる。

### その他（発見したら追記）

（最初の候補は `docs/rendering.md` §7 の要probe 6 件：記名押印欄の丸枠、
`signature_layout: horizontal` の読み順、`- 1 -` 型フッタ、頭書の大型表のページまたぎ、
☑ □ のフォント被覆、`commentary` 枠の境界割れ。**probe の結論は `docs/decisions.md` にも記録する。**）

## flowchart の L 字エッジは間のノードを貫通する（2026-09-27・修正済み）

`keiyaku/render/diagrams/flowchart.py` の L 字エッジは**始点の行の中心**を横に走る。
同じ行に別のノードがあるとその箱を横切り、**隣のノードへ繋がっているように見える**。
検収フローの差戻し経路（`補正 → 検査の判定`）で実害が出た。

- 衝突するときだけ**行と行の隙間**を通す経路に切り替えるようにした（`_crosses`）。衝突しない経路は従来どおり。
- **verify も lint も通ったまま**で、**目視でしか見つからない**（CLAUDE.md §0.4-7）。
- 残る癖：判定ノードの下の頂点に、下りの本線と戻りの矢印が同じ点で集まる。読めるので許容している。
  気になる図は、戻り先の列をずらすか、戻る経路を持たない構成にする。

## `{term:}` は語を太字にするだけで定義文は出ない（2026-09-27・L12 で検出できるようにした）

`defined_terms` に定義を書いても、紙面には現れない。定義条（散文）か定義表を置かないと、
読み手には語の意味が分からず `definition` の QA も作れない。**nda-0001 と ots-0001 で 2 度踏んだ**。

- さらに `defined_terms[].definition` は**正解データ**なので、紙面の文言とずれていたら
  **紙面から答えた読み手が不正解になる**。L12 が両方を突き合わせる（トークンは両側で解いてから照合）。

## `id(obj)` をキーにしたキャッシュは別オブジェクトに化ける（2026-09-27・修正済み）

`_ARTICLE_CACHE: dict[int, ...]` を `id(draft)` で引いていた。Python の `id()` は
**解放されたオブジェクトのアドレスを再利用する**ので、前の文書が GC された後に作った文書が
同じ id を得ると、**前の文書のキャッシュ**が返る。

- 症状：脚注の所属先が `None` になり、L02 が「{fn:1} の所属先が無い」という**偽の error** を出す。
- **1 文書しか扱わない CLI では表に出ない。** テストのようにプロセス内で draft を何度も作ると出る。
  `keiyaku batch` は複数文書を 1 プロセスで回すので、そこでも必ず踏む。
- 直し方：モジュール変数に持たず、走査 1 回ぶんの表を呼び出し側で作って渡す（`node_kinds()`）。
  どうしてもオブジェクト単位で持ちたいなら `WeakKeyDictionary` を使う。

## `RenderLayoutError` の「帯」は style ごとに幅が違う（2026-09-27・実測）

`scripts/probe_layout_band.py` を `content/dlg-0001` に当てた実測値（1 段組の契約書の版面）：

| style | 帯の幅 |
|---|---|
| `ct-a4-1col-mincho` | **32 字** |
| `ct-a4-1col-gothic` | **96 字** |

yakkan の 2 段組で測った 48 字とは違う。**帯の幅は版面ごとに測り直す**こと。

- **帯の中で数十字振っても通らない。** 実際、90 字前後の段落を 3 回足して 3 回とも帯の中に留まり、
  probe を取るまで「自分の文が悪いのか」を探索してしまった（D-1 の「3 回試して通らなければ probe」は正しい）。
- mincho と gothic で帯の位置が違うので、**片方が通ってももう片方が落ちる**。両方描いて確かめる。
- `.signature` に `break-inside: avoid` を付けると、この帯を**安定して踏む**（本文を増減しても外れない）。
  記名押印欄をページで割らせない目的で入れたが撤回した。当事者ブロック単位の
  `.sig-block { break-inside: avoid }` は問題なく効く。

## 結合セル（rowspan）がページ境界をまたぐと、継続ページの列が空欄になる（2026-09-27・実測）

`scripts/probe_head_matter.py` で実測（`ct-a4-1col-mincho`・A4 1 段）：

- 30 行の表の 20〜25 行目に 6 行の rowspan を置くと、**行見出しは p1（20〜21 行）と p2（22〜25 行）に分かれる**
  のに、**結合セル本体の fragment は p1 に 1 つだけ**。p2 のその列は空欄になる。
- 紙面を読んだ人はその値を取り出せないのに `layout.elements` は p1 を指す。
  **正解データのほうが間違っている状態**になる（CLAUDE.md §0.4-6）。
- **verify の V11 が落とす**（`check_merged_cells_across_pages`）。頭書のように行数の多い表で必ず確かめる。
- 回避：結合が覆う行が 1 ページに収まるように表を分けるか、結合を使わない。

## 頭書（大型表）の実測値（2026-09-27）

同じ probe で測った、A4 1 段（版面幅 532.9pt）での挙動：

| 測ったもの | 結果 |
|---|---|
| 繰返し表頭 | `repeat_header: true` で 2 ページ目にも出る。**2 回目以降は `repeated: true`** が付き、往復比較から正しく外れる |
| 列数のはみ出し | **15 列までは収まり、16 列で版面をはみ出す**（538.9pt）。verify の V06 が捕まえるので黙って出ることはない |
| rowspan | 上記のとおり、ページ境界をまたぐと継続側が空欄（V11） |

実物（国交省の標準賃貸借契約書）の頭書は最大 14 列だったので、**A4 1 段で表現できる**。

## 逐条解説の枠はページ境界をまたいでも壊れない（2026-09-27・実測）

`scripts/probe_commentary.py` で 6 / 20 / 40 / 70 行の解説を描いた実測（A4 1 段）：

| 測ったもの | 結果 |
|---|---|
| 40 行以上で枠がページをまたぐ | **2 fragment**（p2・p3）に分かれる |
| 内容欠落（V05） | **無し**。全行が layout に載る |
| はみ出し（V06） | **無し** |
| テキスト往復一致（V03） | **一致** |
| 見た目 | 左の罫線が両ページで正しく引かれ、続きが版面の外に出ることは無かった |

yakkan の「枠つきブロックが割れると続きが版面の外に出る」は**段組（2 段）の話**であり、
**1 段組の契約書では再現しなかった**。`.commentary` の `break-inside: avoid` は
1 ページに収まらない長さでは自然に諦められ、正しく分割される。

- したがって「長い解説は複数ブロックに分ける」方針は**必須ではない**。
  読みやすさのために分けるのは自由だが、機構上の制約ではない。
- 2 段組の style を足すとき（P8）は**測り直す**こと。

## 逐条解説つきの文書は `ct-a4-1col-form` で描けない（2026-09-27・実測）

`lic-0002`（解説 7 枠・31 行）を `ct-a4-1col-form` で描くと WeasyPrint の AssertionError になる。
`scripts/probe_layout_band.py` で **496 字ぶん増減させても全通り落ちた**——帯ではなく**構造的な相性**。

- 同じ style でも `lic-0001`（解説なし）は描ける。**解説の枠と form の版面の組み合わせ**が原因。
- 対処は `PROMPT.md` P6-1 の「別の style で描く」。`license` の 2 style 目だけ `ct-a4-1col-gothic` にした。
- 解説つきの doctype を増やすときは、**form 以外の style を組にする**こと。

## `keiyaku clean --stale` は blueprint の `variants.styles` を基準に消す（2026-09-27）

manifest ではなく**宣言**を見る。`specs/*.yaml` で宣言に無い style を描くと、
`clean --stale` がその場で消してしまう（実際に batch の出力 9 件が消えた）。

- **batch spec と blueprint の `variants.styles` は揃える。**
- `clean --stale` を走らせる前に、消される一覧を必ず読む（`削除:` の行が出る）。

## `render` は `source.json` を使い回す——古ければ直す前の版が描かれる（2026-09-27）

`keiyaku render` は `content/<cid>/source.json` があればそれを描く。build を挟まないと
**執筆物を直しても版面が変わらない**。図の位置を直したのに反映されず、原因の特定に時間を使った。

- **実装（`keiyaku/**/*.py`）を直したときも同じ。** `{party:}` を図で解けるようにした直後、
  執筆物は触っていないので「新しい」と判定され、旧 `source.json` が描かれた。
- 対処：`build.source_is_stale()` が**執筆物と実装の両方の更新時刻**を見て、古ければ
  render が黙って build し直す（`source.json が古い（執筆物か実装の方が新しい）ので build から実行する`）。
- 手で確かめたいときは `uv run keiyaku build content/<cid>` を先に走らせる。

## 図の中のトークンは「許可された種類」しか解決されない（2026-09-27）

`derived.figures[].resolved_labels` は `build.FLAT_TOKENS` に載っている種類だけを解決する。
**載っていないトークンは生のまま SVG に描かれ、lint も verify も鳴らなかった**
（`{party:client}の確認` がそのまま紙面に出た）。

- いまの許可は `{ref:}` `{term:}` `{const:}` `{party:}`。**行内マークアップを持つものは入れない**。
- L06 は「許可の一覧に無いトークンはすべてエラー」に変えたので、次に token 種別を足したときは
  **まず lint が落ちる**（`FLAT_TOKENS` に足すか、図では使わないかを決めること）。

## flowchart の格子は「隣の行・隣の列」に置くと素直に描ける（2026-09-27）

エッジの経路は格子の配置で決まる。**離れた行へ戻る経路**は、間の行を避けて隙間を走るので
線が長くなり、同じ列を上下する別のエッジと重なって見えることがある。

- 戻り先はできるだけ**隣の行**に置く（`csl-0002` の更新の図は、更新後のノードを判断の行から
  1 つ上げて、戻り経路を横 1 本にした）。
- 横エッジのラベルは**列の隙間 18px** に収まらなければ自動で箱の上へ逃げる。
  逃がしても窮屈なら、ラベルを短くするか、ノードの配置を変えること。
- 図を直したら**必ず PNG を見る**。lint も verify も線の重なりは見ていない。

## 宣言（blueprint・numbering）と実装の定数が二重になっていないか疑う（2026-09-27）

同じ規約が 2 か所にあると、片方だけ直って食い違う。実際に出た 2 件：

| 宣言 | 実装 | 症状 |
|---|---|---|
| `blueprints/*.yaml` の `authored_qa`（図 2・apply 2） | `lint/qa_authored.py` の定数（図 3・apply 1） | 宣言どおり図 2 問で書くと lint が落ちる |
| `numbering/*.yaml` の `head_matter_levels` | 宣言に `paragraph` が無く**本文の規則に落ちる** | 頭書の注記に「2」が付く |

- **規約は宣言に置き、実装は宣言を読む。** 実装側の定数は「宣言が読めないときの既定値」に留める。
- `numbering/*.yaml` は build の入力なので、直したら `source.json` は古い（`source_is_stale` が見る）。
