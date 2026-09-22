# shared_fixes.md — 共有コード側で直すべきものの積み残し

サブエージェントの報告と自分の目視から集約。いずれも全文書に影響するため
`docs/decisions.md` に記録してから実施し、最後に全7文書を再レンダリング＋verify する。

1. **条末ブロックの並び順**：`yakkan/render/html.py` の `_is_trailing` が
   欄外注（`box style=margin_note`）を条末脚注（`footnotes`）より先に出している。
   実物は脚注 →（ページ下部または条末の）欄外注の順。travel p8・life で確認。
2. **表紙のヘッダ／フッタを消す**：`@page :first` で `@top-left` / `@bottom-center` / `@bottom-right` を空にする。
   実物の約款冊子の表紙にページ番号は入らない。life p1 で確認。
   → `layout.json` の `pages[0].header/footer` が null になる（正解としてはより正確）。
3. **timeline の軸目盛ラベルが5文字以上で viewBox から切れる**：両端にパディングを入れる。
   life・travel の両担当が独立に「4文字までしか入らない」と報告。
4. **`page_break` ブロックが未実装**：`html.py` が空文字を返している。スキーマは宣言しているので実装する。
   travel の別表が12〜13ページにまたがり1行だけ残る問題の制御手段になる。
5. **teikan の号の記号**：現在 ①②③（損保約款流）。定款の慣行は `(1)(2)(3)` または漢数字。
   `yakkan/numbering.py` の teikan scheme を変更する。
6. **teikan の `{ref:}` から章の冠を外す**：条が全編通し番号（`CONTINUOUS_ARTICLE_SCHEMES`）なので
   「第３章第１２条」の章プレフィックスは不要。同一章内参照と挙動も不統一。
7. **matrix 図の列幅が固定 62px**：health 担当が列見出しを「けが／病気／特約」まで短縮せざるを得なかった。
   ラベル長に応じて列幅を広げる。
8. **特約を独立番号体系にする**（auto A12・oneday ⑩）：現在は普通保険約款の章として通し番号化され、
   「普通保険約款を準用する」と書くと自己言及になる。`scaffold`/`numbering` に rider 体系を足す。
   ※ 影響が大きいので P6 送りも検討。暫定対応は各文書側で実施済み。
9. **表題（figcaption）と表本体の分離**：`break-after: avoid` は本文欠落を誘発するため採用できない（実測済み）。
   別手段を探すか、既知の制約として残す。

## 追加（P4-c のレビューと修正で集まったもの）

10. **キャプションのない列挙表が「表N」の番号を消費する**（3人の担当が独立に報告）：oneday で `表13` の次が `表15` に飛んだ。
    `assign_caption_labels` が caption 無しの表まで数えているため。teikan では附則の履歴表に「表４」が付き、
    実物の定款は附則の表に表番号を振らない。読者に見える番号が飛ぶのは正解データとしても不自然。
    → caption を持つ表だけを数える／`semantic_type` が列挙系の表は番号を振らない、のどちらかに寄せる。
11. **`{ref:}` が表・図・別表を参照できない**：`{ref:tbl_coverage_overview}` は L01 で落ちる。
    `build` は `labels` に「表N」を持っているのに ref 解決側が見ていない。
    「表２に掲げる額の２分の１」と書けないため、oneday は `{ref:ch1_a4|short}` で代替した。
    crossref QA の材料としても表・図への参照は欲しい。
12. **`RenderLayoutError` が「字数の増減では通らない」形がある**：oneday 担当が
    「`ch3_a4` の(2)(3)を1項に統合する」形だけは前後の字数をいくら振っても落ちたと報告。
    `docs/gotchas.md` の「数十字増減すれば通る」が常に成り立つわけではない。
    → 最小再現が取れたら `scripts/probe_weasy.py` に追加し、WeasyPrint 側に報告できる形にする。
13. **特約を独立番号体系にする**（auto A12・oneday ⑩・quake・travel T-8 で4文書が同じ指摘）：
    `Node.kind` に特約用の区分が無く、特約を `chapter` として body に置くため
    「第５章 携行品損害補償特約」と普通約款の続き番号になる。そのうえで「普通保険約款を準用します」と書くと自己言及になる。
    → `kind: "rider"` を models に追加し、numbering で「特約第○条」の独立体系にして、目次でも本文と別建てにする。
    **4文書で暫定対応（準用文の書き換え）を入れたが、本筋はこれ。P6 送りも検討。**
14. **teikan の号の記号**：`yakkan/build.py` の `enumeration_labels()` が `circled()` を無条件に呼ぶため、
    scheme に関係なく ①②③ になる。`_label_teikan` の item は既に `（１）` を返すので、
    `enumeration_labels` を `label_for(ctx, "item", n, in_appendix=...)` 経由にすれば scheme と揃う。
15. **teikan の `{ref:}` から章の冠を外す**：条が全編通し番号なので「第３章第１４条」の章プレフィックスは不要。
    同一章内参照（「第１４条（決議）」）と挙動も不統一。
16. **teikan の附則の見出し**：`_label_appendix_inner` が `appendix_section` に「第１」、paragraph に「１．」を振る。
    定款の附則は項番号「１」「２」で起こすのが通例。
17. **`blueprints/travel.yaml` は appendices に `kind_label: "付表"` を指定しているが描画は「別表１」**。
    blueprint か numbering のどちらかに寄せる。
18. **rowspan がページ境界をまたぐと継続ページのセルが空欄になる**（life `tbl_benefit` の受取人列）。
    読み取り課題としては妥当だが、正解側が `repeated` 扱いを区別できているか verify で確認したい。
19. **フッタのページ番号が半角**（`counter(page)`）で `digit_style: fullwidth` の文書と不整合。
    実物の日本語冊子もページ番号は半角が多いので、意図的に半角と決めるなら decisions に記録する。

20. **図の中の文字は RichText 解決を通らない**（`{term:}` `{const:}` `{ref:}` がそのまま PDF に描かれる）。
    auto-0002 の annotated_mock の凡例で実際に起きた。
    **暫定対応**：lint L06 に「図の中にトークンがあったら error」を追加し、平文で書かせるようにした（2026-09-22）。
    **本筋**：build が `derived.figures[fig_id].resolved_labels`（node_id → 解決後の文字列）を作り、
    描画側がそれを使う。`source` の diagram は執筆物のまま残せるし、QA も解決後の文字列を使える。
    現状は「図の数値を本文と揃えたいときは手で追従」という運用で、
    定数を変えたときに取り残される事故が実際に複数回起きている（quake の 30日/20日、health-0002 の 75日）。

21. **`colspan`（2段ヘッダ）がツールチェーン未対応。** quake-0002 の担当が実装を試みて詰まった。
    - `colspan: 2` ＋ 同じ行の `merged_into` を書くと L05 が「行ごとに列数が違う」で error になる
    - プレースホルダを外すと `expand_grid` が colspan を展開せず `header_path` がずれる
    - 既存文書に `colspan` の使用例はゼロ（rowspan は動いている）
    **C10「2段ヘッダ」は §3.1 の読み取り課題カタログに入れた要素**なので、
    未対応のままだとカタログと実装が食い違う。`expand_grid` の colspan 展開と
    L05 の列数計算を直す必要がある。
22. **`Formula` の box が RichText を受け付けない。** `{const:}` を通せないので算式内の数値は生文字列。
    #20（図のラベル）と同じ問題で、定数を変えたときに取り残される。
23. **未執筆 content が L15 の比較対象に入ると幻の重複が出る**（対処済み・2026-09-22）。
    scaffold の骨組みが同じなので、未執筆どうしは 100%、執筆済み × 未執筆で 79〜86% になる。
    `_unfinished()`（TODO が残っているか）で除外した。
    なお L15 の分母は `min(|A|, |B|)` なので、**片方が小さいと重複率が跳ね上がる**性質がある。

---

## 着手の順序について

**#10（表番号が飛ぶ）を直すときは、執筆QAの見直しとセットで行うこと。**
執筆QAの問い文は「表３（総代会の決議事項）のうち…」のように**表番号を本文中に書いている**。
番号の振り方を変えると、問いが指す表がずれる。手順：

1. すべての content の執筆が終わってから着手する
2. `assign_caption_labels` を直す
3. 全文書を build → render → verify
4. `content/*/qa_authored.json` を grep して「表N」「図N」「別表N」を含む問いを洗い出し、
   新しい番号に直す
5. `yakkan qa` を全データセットで回して L14 が通ることを確認する

自動QAは番号を `derived.tables[].caption_label` から取るので自動で追従する。
**手で書いた問いだけが追従しない。**
