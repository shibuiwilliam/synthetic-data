# gotchas.md — 環境固有の癖・落とし穴

> 環境・ライブラリの癖はここに追記する（auto memory に任せない。CLAUDE.md §0.3）。
> **基底：`../insurance-contracts/docs/gotchas.md` と `../contracts/docs/gotchas.md` の全項目は
> 本プロジェクトでも有効。** render / layout / verify を触る前に必ず基底を読む。
> 本ファイルには要点の再掲と、本プロジェクト固有の発見だけを足す。

## 基底から特に忘れやすいもの（要点の再掲。詳細は基底ファイル）

- **段またぎ要素（column-span 見出し・span_columns 表）があると、WeasyPrint はそれ以降の内容を黙って捨てることがある。**
  「レンダリング成功」≠「内容が全部載った」。内容欠落検出（全要素 ≥1 fragment）を無効化しない。
- WeasyPrint の box ツリー（`_page_box`）は私的 API。版固定（70.0）。座標は
  `border_box_x()/y()` ＋ `border_width()/height()`。box 種別で白リストしない。text_lines は LineBox 単位。
- 単位：WeasyPrint は CSS px、PDF は pt（×0.75）、PNG は dpi/72 倍。原点は左上。
- ヘッダ/フッタ判定は y 座標ではなく MarginBox の `at_keyword`。
- 繰返し表頭・ヘッダ/フッタはテキスト層に複数回現れる。`repeated` / header/footer として区別してから比較。
- `<table>` 直接の `column-span: all` は効かない（wrapper で包む）。`float: footnote` は未対応。
- SVG `<text>` には `font-family`/`font-size` を必ず明示（無指定はシステムフォントで埋め込まれ再現性が壊れる）。
- 丸数字等の記号はフォント被覆検査（L07）を render 前に必ず実行。長い欧文だけ `overflow-wrap: break-word`。
- macOS：Homebrew の dylib は既定検索パスに無い。`make` 経由で `DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib`
  が渡る。素の `uv run` では自分で付ける。
- PDF のメタデータ日時を固定しないとバイト差分が出る（テキスト層一致が必須、バイナリ一致は目標）。

## 基底の 2026-09-22 以降に追記された項目（見落としやすいので明示）

- **`leader('.')` はテキスト層に「.」を残す**（1 ページ数百字）。目次のリーダー罫は
  `leader(' ')`＋`text-decoration: underline dotted`。**`border-bottom` は行高が 0.4pt 増えて
  ページ送りが崩れ、別ジャンルの内容が消える**（box の大きさを変えない描き方を選ぶ）。
- **WeasyPrint が CFF（.otf）を埋め込むと macOS Preview/Quick Look で本文が描画されない。**
  pdfplumber・pdfium・poppler では読めるため往復検証では検出できない。同梱フォントは `.ttf` を使い、
  `pdffonts` で `CID Type 0C` が無いことを確認する。
- `RenderLayoutError` は「帯」（実測 48 字幅）で起きる。帯の中で字数を振っても通らない——
  帯をまたぐ量を動かす（`scripts/probe_layout_band.py` で測れる）。
- **サブエージェントに執筆を任せている間は共有コード（CSS・テンプレート）を触らない**
  （幻の失敗を追わせる）。verify の強化だけは描画結果を変えないので例外的に安全。
- 「fragment はあるのに PDF にテキストが無い」ときは bbox が版面の外（マージン帯）に
  出ていないか見る（枠つきブロックの段またぎで実例）。
- 較正（`chars_per_page_estimate`）は**実コーパス基準**。合成較正は `.para { break-inside: avoid }`
  のせいで段落単位に量子化され、別版面が同値になる。

## keiyaku（契約書）側で新たに判明した項目（2026-09-26〜10-05。本プロジェクトでも有効）

- **結合セルがページ境界をまたぐと、継続ページの列が空欄になる。** 紙面が壊れるだけでなく
  **正解データのほうが誤りになる**（layout と source が食い違う）。verify V11 が検出する。
  頭書・記入欄・賃金表のような大型表で踏む。対処：表を分ける／行を減らす／改ページ位置を動かす。
- **`☑`（U+2611）は本文フォントに無い。** 記号フォントへフォールバックし、L07 が warn を出して
  PDF に余分なフォントが埋め込まれる。選択欄は **`■`（選択）/`□`（未選択）** を使う
  （`■` `□` `〇` は全同梱フォントにある）。
- **A4 1 段で表に収まる列数は 15 列まで**（実測）。それ以上は項目を分ける。
- **新しい style を足したら `styles/css/<style_id>.css.j2` も作る。** 無いと `TemplateNotFound` で
  render が落ちる。差分だけ書き、近い style を `{% include %}` する。
- **`chars_per_page_estimate` は新 style ごとに 1 本描いて較正する。** 鵜呑みにすると L09 の推定が外れる
  （keiyaku の A3 横 2 段は 2600 → 2638 に補正された）。
- **枠つきブロック（解説枠）がページ境界で割れると続きが版面の外に出ることがある。**
  長い解説は複数ブロックに分ける。
- **記名押印欄の「印」丸枠**は `inline-block`＋`border-radius: 50%` で 1 断片（34.8×34.8pt）に収まり、
  文字はテキスト層に載る。`signature_layout: horizontal` は `flex`＋`flex: 1 1 0` で左右に並び、
  **読み順は DOM 順と一致する**（probe 済み。再実測しない）。
- **`- 1 -` 型フッタ**は `@bottom-center` の MarginBox として判定でき、テキスト層に載る（probe 済み）。

## 本プロジェクト固有（発見したら追記）

（まだ無し。最初の候補は `docs/rendering.md` §7 の要probe 4 件：3 階層入れ子リストの grid（terms）、
statute の条見出し 2 行構成、漢数字ラベルの幅、イロハ細目の折返し。
**記名押印欄の丸枠・`- 1 -` 型フッタ・チェックボックス・頭書の大型表・解説枠は keiyaku が済ませた**ので
再 probe しない（上節）。probe の結論は `docs/decisions.md` にも記録すること。）
