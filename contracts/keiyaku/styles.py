"""スタイル定義の読み込み（`styles/<style_id>.yaml`）。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from keiyaku.models import Model

STYLES_DIR = Path(__file__).resolve().parent.parent / "styles"
MM_TO_PT = 2.834645669291339


class Margin(Model):
    top: float
    right: float
    bottom: float
    left: float


class PageSpec(Model):
    size: str = "A4"
    width_mm: float = 210
    height_mm: float = 297
    margin_mm: Margin

    @property
    def width_pt(self) -> float:
        return self.width_mm * MM_TO_PT

    @property
    def height_pt(self) -> float:
        return self.height_mm * MM_TO_PT

    def content_width_pt(self) -> float:
        return (self.width_mm - self.margin_mm.left - self.margin_mm.right) * MM_TO_PT

    def header_below_pt(self) -> float:
        return self.margin_mm.top * MM_TO_PT

    def footer_above_pt(self) -> float:
        return (self.height_mm - self.margin_mm.bottom) * MM_TO_PT


class ColumnSpec(Model):
    count: int = 1
    gap_mm: float = 8

    @property
    def gap_pt(self) -> float:
        return self.gap_mm * MM_TO_PT


class FontSpec(Model):
    body: str
    heading: str
    symbol_fallback: list[str] = Field(default_factory=list)


class HeadingSpec(Model):
    """見出しの体裁。`band` が False なら色帯も色文字も使わない（素組み）。"""

    band: bool = True


class TableSpec(Model):
    #: `form` は様式型の帳票用（罫線を太めにする。docs/rendering.md §4.5）
    border: Literal["grid", "horizontal", "minimal", "form"] = "grid"


class Style(Model):
    style_id: str
    description: str = ""
    page: PageSpec
    columns: ColumnSpec = Field(default_factory=ColumnSpec)
    fonts: FontSpec
    sizes: dict[str, float] = Field(default_factory=dict)
    palette: dict[str, str] = Field(default_factory=dict)
    headings: HeadingSpec = Field(default_factory=HeadingSpec)
    table: TableSpec = Field(default_factory=TableSpec)
    margin_note: Literal["article_end", "page_bottom"] = "article_end"
    #: フッタのページ番号の書式（§3.1 E7）。`dashed` は「− 3 −」のようにダッシュで囲む。
    #: 参考 #3・#11〜#14 がこの形。`plain` は数字だけ。
    page_number: Literal["plain", "dashed"] = "plain"
    #: ヘッダに何を出すか。**契約書は無ヘッダが既定**（実物の契約書はヘッダを持たないものが多い。
    #: docs/rendering.md §5）。`chapter` は章名、`title` は題名、`title_chapter` は両方。
    header: Literal["none", "title", "chapter", "title_chapter"] = "none"
    #: 目次の見出し語。yakkan の保険約款は「もくじ」だが、**契約書は「目次」**が普通
    #: （2026-09-27：sysdev の目次に「もくじ」と出た）。style の宣言にして doctype 群ごとに選べるようにする。
    toc_heading: str = "目次"
    #: 当事者表示の体裁（docs/rendering.md §4.1）
    parties_style: Literal["table", "lines"] = "lines"
    #: 記名押印欄の並び（docs/rendering.md §4.4。横並びは probe 済み＝decisions 42）
    signature_layout: Literal["vertical", "horizontal"] = "vertical"
    #: 1 ページに入る本文の字数。**実コーパスから較正する**（合成較正は段落単位に量子化されて
    #: 別版面が同値になる。docs/gotchas.md）。新 style は 1 本描いて実ページ数で確かめる。
    chars_per_page_estimate: int = 2300

    def gutter_pt(self) -> tuple[float, float]:
        """段間の x 範囲（pt）。読み順の判定に使う。"""
        center = self.page.width_pt / 2
        half = self.columns.gap_pt / 2
        return (center - half, center + half)

    def column_width_pt(self) -> float:
        if self.columns.count < 2:
            return self.page.content_width_pt()
        return (self.page.content_width_pt() - self.columns.gap_pt) / self.columns.count


def load_style(style_id: str, styles_dir: Path | None = None) -> Style:
    path = (styles_dir or STYLES_DIR) / f"{style_id}.yaml"
    if not path.is_file():
        raise FileNotFoundError(f"スタイルが無い: {path}")
    return Style.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


def available_styles(styles_dir: Path | None = None) -> list[str]:
    return sorted(p.stem for p in (styles_dir or STYLES_DIR).glob("*.yaml"))
