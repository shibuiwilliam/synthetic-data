"""スタイル定義の読み込み（`styles/<style_id>.yaml`）。"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import Field

from yakkan.models import Model

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
    border: Literal["grid", "horizontal", "minimal"] = "grid"


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
