# assets/fonts/SOURCES.md — 同梱フォントの出典・版・ライセンス

CLAUDE.md §0.4-8（ネットワーク取得は公式配布元のみ）と docs/rendering.md §6.2 に基づく記録。
**すべて OFL 1.1 または IPA フォントライセンス v1.0** で、再配布と埋め込みが認められている。
取得日：2026-09-21。`SHA256` は同梱ファイルそのものの値で、再取得時の同一性検証に使う。

## 同梱しているファイル

| ファイル | フォント | 版（リリース） | name(5) の版 | サイズ | ライセンス | SHA256 |
|---|---|---|---|---|---|---|
| `NotoSerifJP-Regular.otf` | Noto Serif CJK / JP | Serif2.003 | 2.003;hotconv 1.1.1;makeotfexe 2.6.0 | 6.21 MB | SIL Open Font License 1.1 | `2c9a12dbd4f2408c4610c7ee84a108b6…` |
| `NotoSerifJP-Bold.otf` | Noto Serif CJK / JP | Serif2.003 | 2.003;hotconv 1.1.1;makeotfexe 2.6.0 | 6.48 MB | SIL Open Font License 1.1 | `1e03488a0d5e819f07fcd74f54703a79…` |
| `NotoSansJP-Regular.otf` | Noto Sans CJK / JP | Sans2.004 | 2.004;hotconv 1.0.118;makeotfexe 2.5.65603 | 4.53 MB | SIL Open Font License 1.1 | `dff723ba59d57d136764a04b9b2d0320…` |
| `NotoSansJP-Bold.otf` | Noto Sans CJK / JP | Sans2.004 | 2.004;hotconv 1.0.118;makeotfexe 2.5.65603 | 4.66 MB | SIL Open Font License 1.1 | `1b0edfb500b73a4fa8a4fcaae1bbbd40…` |
| `ipaexm.ttf` | IPAex明朝 | IPAexfont00401 | 004.01 | 7.84 MB | IPA Font License Agreement v1.0 | `7a306386f930fee80922f71eebf4ffe0…` |
| `ipaexg.ttf` | IPAexゴシック | IPAexfont00401 | 004.01 | 6.10 MB | IPA Font License Agreement v1.0 | `3b9955a5e437ffb24c41548e79296fa7…` |
| `NotoSansSymbols-Regular.ttf` | Noto Sans Symbols | v2.003 | 2.003; ttfautohint (v1.8.4.7-5d5b) | 0.26 MB | SIL Open Font License 1.1 | `0088617baec0e8ac47e022cc1f38695f…` |
| `NotoSansSymbols2-Regular.ttf` | Noto Sans Symbols 2 | v2.008 | 2.008; ttfautohint (v1.8.4.7-5d5b) | 1.23 MB | SIL Open Font License 1.1 | `3ce38effdb615dd929c8b0f52768dfa2…` |

## 取得元（再取得の手順）

配布元は zip のため、下表の zip をダウンロードして該当メンバーだけを `assets/fonts/` に展開している。

| ファイル | 取得元 URL | zip 内のパス | zip の SHA256 |
|---|---|---|---|
| `NotoSerifJP-Regular.otf` | https://github.com/notofonts/noto-cjk/releases/download/Serif2.003/12_NotoSerifJP.zip | `SubsetOTF/JP/NotoSerifJP-Regular.otf` | `53bdd2a6e4eb63bf24f7890e018dddb9…` |
| `NotoSerifJP-Bold.otf` | https://github.com/notofonts/noto-cjk/releases/download/Serif2.003/12_NotoSerifJP.zip | `SubsetOTF/JP/NotoSerifJP-Bold.otf` | `53bdd2a6e4eb63bf24f7890e018dddb9…` |
| `NotoSansJP-Regular.otf` | https://github.com/notofonts/noto-cjk/releases/download/Sans2.004/16_NotoSansJP.zip | `NotoSansJP-Regular.otf` | `2bbdd2c20f30670b39ca735c96d75f1f…` |
| `NotoSansJP-Bold.otf` | https://github.com/notofonts/noto-cjk/releases/download/Sans2.004/16_NotoSansJP.zip | `NotoSansJP-Bold.otf` | `2bbdd2c20f30670b39ca735c96d75f1f…` |
| `ipaexm.ttf` | https://moji.or.jp/wp-content/ipafont/IPAexfont/ipaexm00401.zip | `ipaexm00401/ipaexm.ttf` | `9604c77067396b4d2ab49816b3e18db7…` |
| `ipaexg.ttf` | https://moji.or.jp/wp-content/ipafont/IPAexfont/ipaexg00401.zip | `ipaexg00401/ipaexg.ttf` | `4ab6fee94bf6f94b3eeb31be2b73c559…` |
| `NotoSansSymbols-Regular.ttf` | https://github.com/notofonts/symbols/releases/download/NotoSansSymbols-v2.003/NotoSansSymbols-v2.003.zip | `NotoSansSymbols/full/ttf/NotoSansSymbols-Regular.ttf` | `0c113cdcf6c31d050b80dac39fba2d80…` |
| `NotoSansSymbols2-Regular.ttf` | https://github.com/notofonts/symbols/releases/download/NotoSansSymbols2-v2.008/NotoSansSymbols2-v2.008.zip | `NotoSansSymbols2/full/ttf/NotoSansSymbols2-Regular.ttf` | `346c930bbe8eb946701a05c54e9c11a2…` |

```bash
# 例：Noto Serif JP の再取得
curl -sL -o /tmp/NotoSerifJP.zip \
  https://github.com/notofonts/noto-cjk/releases/download/Serif2.003/12_NotoSerifJP.zip
unzip -joq /tmp/NotoSerifJP.zip 'SubsetOTF/JP/NotoSerifJP-Regular.otf' -d assets/fonts
shasum -a 256 assets/fonts/NotoSerifJP-Regular.otf   # 上表の値と一致すること
```

## 派生ファイル：`.ttf`（TrueType 輪郭に変換した Noto Serif/Sans JP）

**取得日：2026-09-26。** 外部から新規取得したのではなく、上表の `.otf`（CFF 輪郭）
から `scripts/otf_to_ttf.py`（fontTools の `Cu2QuPen`、変換誤差上限 0.001em）で
**ローカルに変換して作った派生ファイル**。理由は `docs/gotchas.md`
「WeasyPrint が CFF（.otf）を埋め込むと、macOS の Preview/Quick Look で本文が
描画されない」を見ること。`keiyaku/fonts.py` の `FONTS` はこの `.ttf` を参照する。
`.otf` は出典検証用にそのまま残してあり、削除しない。

輪郭の形以外（cmap・advance width・グリフ数・Unicode 被覆）は元の `.otf` と同一
であることを検証済み（GID 単位の advance width が全グリフで完全一致。CID フォントは
再読み込みのたびにグリフ"名前"が変わるため、名前ではなく GID の並び順で比較する）。

| ファイル | 変換元 | fontTools 版 | サイズ | SHA256 |
|---|---|---|---|---|
| `NotoSerifJP-Regular.ttf` | `NotoSerifJP-Regular.otf` | 4.65.0 | 7.1 MB | `5eed9fac420df96bd691b895fed605e8ab9aa533a6f88d034e54df936597bfa3` |
| `NotoSerifJP-Bold.ttf` | `NotoSerifJP-Bold.otf` | 4.65.0 | 7.1 MB | `f6a1447463e5e82c104117fd0af16995151515580d80464cf34f039429dcda7b` |
| `NotoSansJP-Regular.ttf` | `NotoSansJP-Regular.otf` | 4.65.0 | 5.2 MB | `c008f942721bf0f025c5b8ce08a4e481ec2d1ace2cc8978dc20d1742a7d8b18b` |
| `NotoSansJP-Bold.ttf` | `NotoSansJP-Bold.otf` | 4.65.0 | 5.1 MB | `143d8ad6acb4fb0776181e941f5732c3e8a51855d3b71304fbd0e1e7a9c00721` |

**この変換はバイト単位では決定論的ではない**（同じ入力・同じ fontTools 版で
再実行しても SHA256 は一致しない。実測済み）。輪郭点の走査順など fontTools 内部の
非決定的な要素が原因とみられ、原因は未特定。そのため `.ttf` は`.otf` と同様に
**一度作った実体をこのままコミットして固定資産として扱う**（CLAUDE.md §0.4-4 の
決定論は「同じ資産から同じ PDF が作れること」を指し、資産自体の生成手順の
再現性までは要求していない）。再変換する場合は、cmap・GID 単位の advance width が
元の `.otf` と一致することを必ず検証してから差し替える（`scripts/otf_to_ttf.py` は
変換のみを行い、この検証は別途 Python で行う。上の「advance width が完全一致」の
記述を参照）。

```bash
# 作り直す場合（既存の .ttf は上書きされる。差し替え前に検証すること）
uv run python scripts/otf_to_ttf.py assets/fonts/NotoSerifJP-Regular.otf
```

ライセンスは変換元と同じ **SIL Open Font License 1.1**（OFL は派生フォントの
再配布・改変を明示的に許可している）。

## ライセンス本文

- `LICENSE-NotoSerifJP.txt` / `LICENSE-NotoSansJP.txt`：SIL Open Font License 1.1（Noto CJK のリリース同梱物）
- `IPA_Font_License_Agreement_v1.0.txt`：IPA フォントライセンス v1.0（IPAex 配布物の同梱物）
- Noto Sans Symbols / Symbols 2 も OFL 1.1。配布元 https://github.com/notofonts/symbols の `OFL.txt` と同一。

## 未取得のフォント

| フォント | 用途 | 状態 | 代替 / 取得方法 |
|---|---|---|---|
| BIZ UDP明朝 / BIZ UDPゴシック | docs/rendering.md §6.2 が「バリエーション用」として挙げるスタイル差分（付録A `life-a4-1col-gothic`） | **未取得** | v1 の必須要素ではないため P0 では取得していない。必要になった時点で OFL 版を https://github.com/googlefonts/morisawa-biz-ud-mincho と https://github.com/googlefonts/morisawa-biz-ud-gothic のリリースから取得する。それまで当該スタイルは Noto Sans JP / Noto Serif JP で代替する（`styles/*.yaml` の font 指定を差し替えるだけで済む） |

**日本語非対応フォントでの代用はしない**（豆腐・字形差が読み取り評価を汚染するため）。
`keiyaku doctor` の cmap 被覆表で、本文フォントが代表文字を全て持つことを毎回確認する。

