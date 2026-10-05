"""実行環境の検査（`keiyaku doctor` の中身）。

macOS では Homebrew の dylib が dyld の既定検索パスに無いため、WeasyPrint の import に
`DYLD_FALLBACK_LIBRARY_PATH=/opt/homebrew/lib` が要る（docs/gotchas.md 参照）。
"""

from __future__ import annotations

import ctypes
import ctypes.util
import importlib
import platform
import sys
from dataclasses import dataclass, field

REQUIRED_PYTHON = (3, 12)
HOMEBREW_LIB = "/opt/homebrew/lib"


@dataclass
class Check:
    """1 行ぶんの検査結果。"""

    name: str
    ok: bool
    detail: str
    hint: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, ok: bool, detail: str, hint: str = "") -> None:
        self.checks.append(Check(name, ok, detail, hint))

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


def _c_library_version(soname: str, func: str) -> str | None:
    """C ライブラリを dlopen して版文字列を取る（pango / harfbuzz 用）。"""
    path = ctypes.util.find_library(soname)
    if not path:
        return None
    try:
        lib = ctypes.CDLL(path)
        fn = getattr(lib, func)
    except (OSError, AttributeError):
        return None
    fn.restype = ctypes.c_char_p
    value = fn()
    return value.decode() if value else None


def check_python(report: Report) -> None:
    v = sys.version_info
    ok = (v.major, v.minor) == REQUIRED_PYTHON
    report.add(
        "Python",
        ok,
        f"{platform.python_version()} ({platform.machine()})",
        hint=""
        if ok
        else f"CLAUDE.md §15 の決定は {REQUIRED_PYTHON[0]}.{REQUIRED_PYTHON[1]}。uv sync で揃える",
    )


def check_weasyprint(report: Report) -> None:
    try:
        weasyprint = importlib.import_module("weasyprint")
    except OSError as exc:  # dylib が見つからない
        report.add(
            "WeasyPrint",
            False,
            f"import 失敗: {str(exc).splitlines()[0][:70]}",
            hint=f"macOS は DYLD_FALLBACK_LIBRARY_PATH={HOMEBREW_LIB} を付けて実行する（make 経由なら自動）",
        )
        return
    report.add("WeasyPrint", True, weasyprint.__version__)


def check_native_libs(report: Report) -> None:
    for label, soname, func in (
        ("Pango", "pango-1.0", "pango_version_string"),
        ("HarfBuzz", "harfbuzz", "hb_version_string"),
    ):
        version = _c_library_version(soname, func)
        report.add(
            label,
            version is not None,
            version or "未検出",
            hint=""
            if version
            else "macOS: brew install pango / Ubuntu: apt install libpango-1.0-0 libpangoft2-1.0-0",
        )
    # libffi は版関数を持たず、macOS では dyld 共有キャッシュにあるため find_library では見つからない。
    # 実用上の要件は「cffi が動くこと」なので、cffi の import 可否で判定する。
    try:
        import cffi

        report.add("libffi (cffi)", True, f"cffi {cffi.__version__}")
    except ImportError as exc:
        report.add(
            "libffi (cffi)",
            False,
            f"import 失敗: {exc}",
            hint="macOS: Xcode CLT を入れる / Ubuntu: apt install libffi-dev のうえ uv sync",
        )


def check_python_packages(report: Report) -> None:
    for label, module, attr in (
        ("Jinja2", "jinja2", "__version__"),
        ("pydantic", "pydantic", "VERSION"),
        ("pdfplumber", "pdfplumber", "__version__"),
        ("fontTools", "fontTools", "version"),
        ("Pillow", "PIL", "__version__"),
    ):
        try:
            mod = importlib.import_module(module)
        except ImportError as exc:
            report.add(label, False, f"import 失敗: {exc}", hint="uv sync")
            continue
        report.add(label, True, str(getattr(mod, attr, "?")))


def check_pypdfium2(report: Report) -> None:
    """ラスタライズが実際に通るかまで確認する（版の表示だけでは足りない）。"""
    try:
        import pypdfium2 as pdfium
        from pypdfium2.version import PDFIUM_INFO, PYPDFIUM_INFO
    except ImportError as exc:
        report.add("pypdfium2", False, f"import 失敗: {exc}", hint="uv sync")
        return
    version = f"{PYPDFIUM_INFO} / pdfium {PDFIUM_INFO}"
    try:
        pdf = pdfium.PdfDocument.new()
        page = pdf.new_page(595, 842)
        bitmap = page.render(scale=150 / 72)
        image = bitmap.to_pil()
        report.add("pypdfium2", True, f"{version} / ラスタライズ {image.width}x{image.height}px OK")
    except Exception as exc:  # noqa: BLE001 - 何が出ても環境不備として報告する
        report.add(
            "pypdfium2", False, f"{version} / ラスタライズ失敗: {exc}", hint="pypdfium2 を再インストール"
        )


def check_fonts(report: Report) -> list[tuple[object, dict[str, bool]]]:
    """同梱フォントの存在と cmap 被覆を調べ、被覆表を返す。"""
    from keiyaku.fonts import FONTS, FONTS_DIR, REPRESENTATIVE_CHARS, coverage

    table: list[tuple[object, dict[str, bool]]] = []
    missing = [f.filename for f in FONTS if not f.exists]
    report.add(
        "フォント同梱",
        not missing,
        f"{len(FONTS) - len(missing)}/{len(FONTS)} 本 @ {FONTS_DIR}",
        hint="" if not missing else f"未配置: {', '.join(missing)}（assets/fonts/SOURCES.md の手順で取得）",
    )
    for spec in FONTS:
        if not spec.exists:
            continue
        table.append((spec, coverage(spec)))

    # 代表文字が「どのフォントにも無い」場合だけを致命扱いにする（フォールバック前提のため）。
    uncovered = [c for c in REPRESENTATIVE_CHARS if not any(cov.get(c) for _, cov in table)]
    report.add(
        "代表文字の被覆",
        not uncovered,
        f"全 {len(REPRESENTATIVE_CHARS)} 文字がいずれかのフォントに存在"
        if not uncovered
        else f"未被覆: {' '.join(uncovered)}",
        hint="" if not uncovered else "記号フォントを追加するか、その文字の使用をやめる（lint L07）",
    )
    return table


def run_all() -> tuple[Report, list[tuple[object, dict[str, bool]]]]:
    report = Report()
    check_python(report)
    check_weasyprint(report)
    check_native_libs(report)
    check_python_packages(report)
    check_pypdfium2(report)
    coverage_table = check_fonts(report)
    return report, coverage_table
