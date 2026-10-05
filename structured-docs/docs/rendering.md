# rendering.md — レンダリングパイプライン（姉妹 2 本からの差分）

> `docsynth/render/` / `layout/` / `verify/` / `numbering.py` / 各ファミリーの styles を触る作業では、
> **着手前に必ず本ファイルと基底仕様を読む**こと。
>
> 基底仕様：`../insurance-contracts/docs/rendering.md`（技術選定・CSS 規約・番号付け・
> 目次/ヘッダ/フッタ/脚注・表・図(SVG)・bbox 抽出・verify・ページ数制御）。
> **WeasyPrint 70.0 の probe 実測 22 項目（`../insurance-contracts/docs/decisions.md` 付録）は
> 本プロジェクトでも前提**であり、再実測しない。WeasyPrint の版を上げるときだけ再 probe する。
> 本ファイルは汎用化に伴う**差分だけ**を書く。
>
> **2026-10-05 更新**：keiyaku-synth が契約書で確定させた描画規約（選択欄の記号・頭書の列数上限・
> 解説枠・記名押印欄の実測値）を §2・§4 に取り込み、verify を **V01–V11 ＋ V-P1〜V-P5** に書き換え、
> §7 の要probe のうち keiyaku が済ませた 3 件を解決済みとして落とした。

## 1. 継承する結論（要点の再掲。根拠は基底仕様）

- Jinja2 → HTML → WeasyPrint 70.0（版固定）→ PDF。検証は pdfplumber + pypdfium2。PyMuPDF 不使用。
- bbox は `doc.pages[i]._page_box`（私的API）の walk。CSS px→pt（×0.75）、原点左上。
  text_lines は LineBox 単位。ヘッダ/フッタ判定は MarginBox の `at_keyword`。
- 見出しのラベルと文言の間隔は margin ではなく U+3000 の文字で空ける。`body { margin: 0 }` 必須。
- `<table>` 直接の `column-span` は効かない（wrapper で包む）。`float: footnote` は未対応。
- SVG `<text>` は `font-family`/`font-size` を必ず明示。SVG 内部は box ツリーに現れない
  （図の正解は `layout.figures[].nodes` が担う）。
- **段またぎ要素があると以降の内容が黙って捨てられることがある**。render の内容欠落検出
  （全要素 ≥1 fragment、`_assert_nothing_dropped`）を常に有効に保つ。
  「レンダリング成功≠内容が全部載った」。
- ルビ（`<ruby>` / `display: ruby`）と縦組み見出し（`transform: rotate`）は**実測済みで不採用**
  （正解が作れない体裁は足さない）。`{ruby:}` トークンは残すが描画しない。

## 2. 姉妹が実害から確定した描画規約（本プロジェクトでは最初から採用する）

基底の rendering.md は 2026-09-21 の写しで、その後の確定事項は yakkan と keiyaku の
decisions / gotchas に散っている。**いずれも実害から確定した規約であり、移植時に逆行させない。**

| 規約 | 理由（yakkan の実害） |
|---|---|
| フォントは `.ttf`（TrueType 輪郭）を同梱・埋め込み。`pdffonts` で `CID Type 0C` が無いことを検査 | `.otf`（CFF）埋め込みは macOS Preview/Quick Look で本文が空になる（26/41 文書で発生） |
| 目次のリーダー罫は `leader(' ')` ＋ `text-decoration: underline dotted`。**`leader('.')` 禁止・`border-bottom` 禁止** | `leader('.')` は「.」がテキスト層に載り、完璧に読んだページの CER が 0.775 になった。`border-bottom` は行が 0.4pt 高くなりページ送りが崩れ、別ジャンルの脚注が消えた |
| 目次は**2 パス描画**（1 パス目で実ページを測り、2 パス目で番号を文字として埋める） | `target-counter` は長い目次で収束せず、印字と実ページが食い違う |
| 目次・長い段またぎ要素は段組コンテナの**外**に置く | 段組内の 1 ページ超の span-all 要素は以降の内容を黙って捨てる |
| 章見出し・別表見出しは `column-span: none`（段内） | span-all 見出しは同じ「後続が消える」失敗モードを持ち、改ページ制御も効かない |
| 表題は `<figcaption>` ではなく **`<table>` の `<caption>`**（表の中） | 段・ページ境界で表題だけが取り残される（23/320 表 → 0） |
| ヘッダの章名は `string(chapter, first)`、経路は `data-headerpath` の**1 本の文字列**で渡す | `start` は章の開始ページで前章名/空になる（実測 first 87.6% vs start 53.7%）。編と章を別 string にすると境界ページで別の編の値を拾う |
| 表紙は `@page :first` でヘッダ・フッタを消す | 実物の表紙にページ番号は入らない |
| フッタのページ番号は文書の `digit_style` に合わせる（`@counter-style` で全角数字） | 本文が全角なのにページ番号だけ半角になる |
| `page_break` は段組コンテナを閉じて開き直す | `break-before: page` は multicol 内で効かない（5 通り試して全滅） |
| 図の辺ラベルは `Svg.edge_label()`（衝突時に下へずらす・白下地・**最後に描く**） | ラベルの重なり・連結線の文字貫通は verify では検出できない（目視でのみ発覚） |
| ラベル欄の固定幅は使わない（`max-content` か「その style の最長ラベル」から決める） | 固定幅は両方向に壊れる（脚注マーカーが折れる／広げると別文書の脚注が消える） |
| `chars_per_page_estimate` は**実コーパスから較正**（新 style は 1 本描いて確かめる） | 合成較正は段落単位に量子化され、別版面が同値になる |
| `{ref:}` は地の文と同じ見た目（`a { color: inherit; text-decoration: none }`） | リンク体裁は文書らしさを壊す（PDF 内部リンクとしては生かす） |
| **結合セルをページ境界にまたがせない**（verify V11 が検出。またぐ表は分割するか行を減らす） | 継続ページの列が空欄になり、**正解データのほうが誤りになる**（keiyaku。頭書型・様式型の大型表で踏む） |
| **選択欄の記号は `■`（選択）/`□`（未選択）。`☑`（U+2611）は使わない** | `☑` は本文フォントに無く記号フォントへフォールバックし、L07 が warn を出して PDF に余分なフォントが埋め込まれる（keiyaku `scripts/probe_checkbox.py`。`■` `□` `〇` は全同梱フォントにある） |
| 頭書の大型表は **A4 1 段で 15 列まで**（実測）。それ以上は項目を分ける | はみ出しと結合セルのページまたぎを同時に踏む |
| **2 段組の style には段またぎ要素（`column-span: all`）を置かない** | 段に収まらない段またぎ要素があると以降の内容が黙って捨てられる（A3 横 2 段 style でも同じ） |
| 枠つきブロック（解説枠・備考枠）は段／ページ境界で割れたときに**続きが版面の外に出ないか**を verify で見る | 「fragment はあるのに PDF にテキストが無い」の典型（yakkan で実害） |
| 新しい style を足したら `styles/css/<style_id>.css.j2` も作る（近い style を `{% include %}` して差分だけ書く） | 無いと `TemplateNotFound` で render が落ちる（keiyaku） |

## 3. テンプレートの構成（変更点）

yakkan の単一テンプレート群を「コア基盤＋ファミリー上書き」に分ける。

```
docsynth/render/templates/base/     # 機構：ページ骨格・見出し・段落・リスト・表・図・脚注・目次
families/<f>/styles/templates/      # MAY：ファミリー固有ブロックの部分テンプレート上書き
```

- 解決順：ファミリー → base（Jinja2 の ChoiceLoader）。上書きは**部分テンプレート単位**
  （`parties.html` など）に限り、ページ骨格（`page.html`）の上書きは禁止
  （bbox 抽出・verify の前提が壊れるため）。
- style YAML の形は yakkan と同じ（判型・段組・フォント・罫線・palette・chars_per_page_estimate・
  `page_number: plain|dashed`）。

## 4. 新ブロックの描画仕様

### 4.1 parties（当事者表示）
- style の `parties_style: table | lines` で表形式（「委託者／受託者」2 行）か行形式
  （「株式会社〇〇（以下「甲」という。）」の段落列）を選ぶ。
- 文字列はすべて `meta.parties` から build が導出した `derived.plain_text` を描画する。手書き文字列なし。

### 4.2 signature（後文・記名押印欄）
- 後文（本文段落）＋日付行＋当事者ごとの記名ブロック（住所／名称／代表者＋「印」）。
- 「印」は文字として描画し、丸枠は CSS の border（円）。画像・擬似印影は使わない。
- 記名ブロックは `break-inside: avoid`。ページ末尾で欄だけ次ページに送られるのは**許容**
  （実在文書でも起きる）が、後文と日付が分離してはならない（同一 wrapper に入れる）。
- 各記名行にも id を振り、bbox を `layout.elements` に載せる（読み取り正解）。

### 4.3 head_matter（頭書）
- 冒頭に置く当事者・目的物・金額の一覧。**2 つの型**がある——**表の連なり**（見出しで区切った独立の表を並べる。
  `lease`）と**番号付き項目の羅列**（表を使わない。`purchase`）。どちらも `head_matter` ノードの中身の違いで表す。
- **キャプションを持たない**ので表としては `{ref:}` の対象にできない。`rider` と同じ
  「番号を持たず呼び名で解決する種別」として扱い、`{ref:head}` → `kind_label`（既定「頭書」）に解決する。
- 頭書の**中**は本文と別の番号体系（`numbering/<scheme>.yaml` の `head_matter_levels` で宣言）。
- **結合セルをページ境界にまたがせない**（V11）。A4 1 段で収まるのは 15 列まで（実測）。

### 4.4 form_fields（様式型の記入欄）
- 記入欄は表のセルとして持ち、`records` に `{ 項目: "契約期間の定め", 選択: "期間の定めなし" }` の形で
  意味を持たせる（**選択状態そのものが読み取り課題**なので、図の模式図にしない）。
- 記号は `■`（選択）/`□`（未選択）。L07 のフォント被覆検査の対象。
- 様式型は条を持たないため、見出しは項目番号（`1` →（1）→（ア））。記名押印欄は持たない。

### 4.5 commentary（逐条解説）
- 条文の直後に枠として描く。**紙面にあるので `answer.pages[].text` には含める**が、
  `layout.text_lines[].region` を `"commentary"` として本文と区別し、検索パッセージでは
  `kind: "commentary"` の別パッセージにする（読み取り側には本文と解説の分離を求める）。
- 枠は `break-inside: avoid` を基本とし、割れる場合は**続きが版面の外に出ていないか**を verify で確かめる。

### 4.6 revision_history（改定履歴）
- semantic_type `history` の表として描画（制定・改定日 × 内容）。文書末尾または冒頭
  （blueprint の `revision_history.position`）。

### 4.7 深い入れ子リスト（terms で多用）
- 基底仕様どおり CSS grid のぶら下げインデント＋`break-inside: avoid` で組む。
  3 階層（(1) → ア → (ｱ)）までをサポートし、それ以上は lint L04 で構成の見直しを要求する
  （自動縮小しない）。1 項目は段（版面）の高さの半分までに収める（基底の制約と同じ）。

### 4.8 statute の描画（P6）
- 条見出しは条の上の行に「（定義）」を独立行で置き、次行を「第二条　本文…」で始める
  （`article_heading: above` の機構＋`LabelInfo.run_in_label`。group で実証済みの形の変種）。
- 目次の行は「第一章　総則（第一条―第五条）」。条範囲は `derived.toc[].article_range` から
  文字列を組み、リーダー罫の規約（§2）に従う。
- 公布情報（`meta.promulgation`）は題名の直下に右寄せ 2 行（公布番号・公布日）。
  公布文（statement）はその下の段落。すべて id 付きで `layout.elements` に載せる。
- 別表見出し「別表第一（第三条関係）」は heading_text として 1 行（`relation_refs` から build が導出）。
- 漢数字ラベル（第十二条・一・二）は幅が可変なので、**ラベル欄は `max-content`**（§2 の規約どおり）。

## 5. ファミリー別の既定 @page

| family | 判型 | ヘッダ | フッタ | 備考 |
|---|---|---|---|---|
| contract | A4 1段（様式型は太罫・A3 横 2 段は 1 本まで） | **なし**（実物は無ヘッダが多い）。約款型・長文型は題名＋章名 | 中央ページ番号（`- 1 -` 型 = `page_number: dashed`）。様式型はプレーン数字＋様式番号 | 契約書番号を右上に置く variant あり |
| terms | A4 1段 | 文書題名（小） | ページ番号 | Web 印刷風 style ではフッタに URL（example.jp）と日付 |
| regulations | A4/B5 1段 | 規程名＋章名（string-set） | ページ番号＋規程番号 | 約款に近い |
| statute | A4/B5 1段 | 題名（例規集風は章名も） | ページ番号 | 目次あり。漢数字ノンブルは使わない（読み取り正解の複雑化に見合わない） |
| insurance | yakkan の style をそのまま移植 | | | |

ヘッダ・フッタは基底仕様どおり `layout.pages[].header/footer` にのみ入れ、
reading_order・`answer.pages[].text` に含めない。

## 6. verify（V01–V11 ＋ V-P1〜V-P5）

姉妹から継承する検査。**番号は keiyaku の実装（`verify/checks.py`）と互換に保つ。**

| # | 検査 | 要点 |
|---|---|---|
| V01 | フォント被覆・埋め込み | 描画に使った字がすべて埋め込まれている |
| V02 | 豆腐（U+FFFD） | テキスト層に U+FFFD が無い |
| V03 | テキスト往復一致 | box ツリーのテキストと PDF のテキスト層が正規化後に一致 |
| V04 | 目次ページ一致 | 目次の各行が描画され、ページ番号が実ページと一致。**目次を持たない文書では「検査していない」旨をレポートに明記**（黙って通さない） |
| V05 | 描画漏れ | 全要素が ≥1 fragment を持つ（**内容欠落の最後の砦**） |
| V06 | はみ出し | 版面・段からのはみ出し |
| V07 | 重なり | 要素同士の重なり |
| V08 | ページ数上限 | blueprint の `page_limit`（無指定なら family.yaml の既定。絶対上限 20） |
| V09 | 決定論 | 2 回描画して `layout.json` と PDF のテキスト層が一致 |
| V10 | 図の座標 | 図とそのノードの座標が `layout` にある（空でない） |
| **V11** | **結合セルのページまたぎ** | 結合セルがページ境界をまたがない。**またぐと継続ページの列が空欄になり、正解データのほうが誤りになる** |

ファミリー条件つきの追加検査：

| # | 検査 | 条件 |
|---|---|---|
| V-P1 | 記名押印欄の記名文字列（名称・住所・代表者）が `meta.parties` と一致（往復比較に含める） | `signature` を持つ文書 |
| V-P2 | ページ上限は blueprint の `page_limit` を読む（V08 の実装details） | 全文書 |
| V-P3 | 目次なし文書では目次検査をスキップし、**その旨をレポートに明記** | 目次を持たない文書 |
| V-P4 | PDF の埋め込みフォントに CFF（`CID Type 0C`）が無い（§2 の `.ttf` 規約の検査） | 全文書 |
| V-P5 | `derived.party_uses[]` の `rendered` が PDF のテキスト層に出現する（`{party:}` の解決漏れ検出） | `{party:}` を使う文書 |

## 7. 要probe（本プロジェクトで新たに確認が必要なもの。**憶測で実装しない**）

keiyaku が済ませた 3 件（記名押印欄の「印」丸枠＝`inline-block`＋`border-radius: 50%` で 1 断片・
34.8×34.8pt／`signature_layout: horizontal`＝`flex` で左右に並び読み順は DOM 順と一致／
`- 1 -` 型フッタ＝`@bottom-center` の MarginBox として判定でき テキスト層に載る）と、
チェックボックス（`■`/`□` に決定）・頭書の大型表（15 列まで）・解説枠は**解決済み**として継承する（§2・§4）。
**残るのは statute と terms のものだけ**である。

| 項目 | 何を確かめる | いつ |
|---|---|---|
| 3 階層入れ子リストの grid | 深い grid 入れ子で LineBox の element_id 対応が崩れないか | P4 冒頭 |
| 条見出し 2 行構成（statute） | 「（見出し）」行と「第二条　本文」行の 2 要素が heading_text の正解と食い違わないか | P6 冒頭 |
| 漢数字カウンタの幅 | 「第百二十三条」級の長いラベルでぶら下げが壊れないか（ラベル欄は `max-content`） | P6 冒頭 |
| イロハ細目の折返し | 「イ」「ロ」のぶら下げが 3 階層目で崩れないか | P6 冒頭 |

probe は `scripts/probe_*.py` に書き、結果を `docs/decisions.md` と `docs/gotchas.md` に記録してから
設計を確定する。憶測で実装しない。
