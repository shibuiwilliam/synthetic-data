"""同梱フォントの台帳。`assets/fonts/` の実ファイルと CSS の font-family を結びつける。

出典・版・ライセンス・SHA256 は `assets/fonts/SOURCES.md` を参照。
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

#: フォント実体の置き場所。環境変数 YAKKAN_ASSETS で上書きできる。
ASSETS_DIR = Path(os.environ.get("YAKKAN_ASSETS") or Path(__file__).resolve().parent.parent / "assets")
FONTS_DIR = ASSETS_DIR / "fonts"


@dataclass(frozen=True)
class FontSpec:
    """1 つのフォントファイル。"""

    key: str
    family: str
    weight: int
    style: str
    filename: str
    role: str

    @property
    def path(self) -> Path:
        return FONTS_DIR / self.filename

    @property
    def exists(self) -> bool:
        return self.path.is_file()


#: 本文・見出し・記号フォールバックに使うフォント一覧（docs/rendering.md §6.2）。
FONTS: tuple[FontSpec, ...] = (
    FontSpec(
        "noto-serif-jp-regular", "Noto Serif JP", 400, "normal", "NotoSerifJP-Regular.otf", "本文（明朝）"
    ),
    FontSpec(
        "noto-serif-jp-bold", "Noto Serif JP", 700, "normal", "NotoSerifJP-Bold.otf", "本文太字（明朝）"
    ),
    FontSpec(
        "noto-sans-jp-regular",
        "Noto Sans JP",
        400,
        "normal",
        "NotoSansJP-Regular.otf",
        "本文・見出し（ゴシック）",
    ),
    FontSpec(
        "noto-sans-jp-bold", "Noto Sans JP", 700, "normal", "NotoSansJP-Bold.otf", "見出し太字（ゴシック）"
    ),
    FontSpec("ipaexm", "IPAexMincho", 400, "normal", "ipaexm.ttf", "高密度スタイル（明朝）"),
    FontSpec("ipaexg", "IPAexGothic", 400, "normal", "ipaexg.ttf", "高密度スタイル（ゴシック）"),
    FontSpec(
        "noto-sans-symbols",
        "Noto Sans Symbols",
        400,
        "normal",
        "NotoSansSymbols-Regular.ttf",
        "記号フォールバック1",
    ),
    FontSpec(
        "noto-sans-symbols2",
        "Noto Sans Symbols 2",
        400,
        "normal",
        "NotoSansSymbols2-Regular.ttf",
        "記号フォールバック2",
    ),
)

#: 約款で実際に使う代表文字。render 前の cmap 被覆検査（lint L07）の最小セット。
REPRESENTATIVE_CHARS: tuple[str, ...] = (
    "①",
    "⑳",
    "❶",
    "☞",
    "◆",
    "ⅰ",
    "※",
    "〈",
    "・",
    "／",
    "第",
    "条",
    "険",
    "ｱ",
    "ア",
    "あ",
    "１",
    "％",
    "（",
    "－",
)

#: 記号のフォールバック順（本文フォント → Symbols → Symbols 2）。
FALLBACK_FAMILIES: tuple[str, ...] = ("Noto Sans Symbols", "Noto Sans Symbols 2")


def by_key(key: str) -> FontSpec:
    for f in FONTS:
        if f.key == key:
            return f
    raise KeyError(key)


def font_face_css(specs: tuple[FontSpec, ...] = FONTS) -> str:
    """`@font-face` 宣言を組み立てる。WeasyPrint には file:// の絶対パスで渡す。"""
    blocks = []
    for f in specs:
        if not f.exists:
            continue
        fmt = "opentype" if f.filename.endswith(".otf") else "truetype"
        blocks.append(
            "@font-face {\n"
            f"  font-family: '{f.family}';\n"
            f"  font-weight: {f.weight};\n"
            f"  font-style: {f.style};\n"
            f"  src: url('{f.path.as_uri()}') format('{fmt}');\n"
            "}"
        )
    return "\n".join(blocks)


def coverage(spec: FontSpec, chars: tuple[str, ...] = REPRESENTATIVE_CHARS) -> dict[str, bool]:
    """フォントの cmap に各文字が含まれるかを返す（豆腐の事前検出）。"""
    from fontTools.ttLib import TTFont

    with TTFont(spec.path, fontNumber=0, lazy=True) as tt:
        cmap = tt.getBestCmap()
    return {c: ord(c) in cmap for c in chars}
