# gotchas.md — 環境固有の癖・落とし穴

> 環境・ライブラリの癖はここに追記する（auto memory に任せない。CLAUDE.md §0.3）。
> **基底：`../insurance-contracts/docs/gotchas.md` の全項目は本プロジェクトでも有効。**
> render / layout / verify を触る前に必ず基底を読む。本ファイルには本プロジェクト固有の発見だけを足す。

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

## 本プロジェクト固有（発見したら追記）

（まだ無し。最初の候補は `docs/rendering.md` §6 の要probe 3 件：記名押印欄の丸枠、`- 1 -` 型フッタ、
3 階層入れ子リストの grid。probe の結論は `docs/decisions.md` にも記録すること。）
