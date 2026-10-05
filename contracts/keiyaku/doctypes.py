"""doctype レジストリ（`keiyaku doctypes`）。

`blueprints/<doctype>.yaml` が正本で、doctype 名を Python の enum に持たない
（docs/architecture.md §2「Python に doctype 名で分岐を書かない」）。そのぶん
**宣言どうしの食い違いを機械で検査する**必要があるので、ここで次を見る。

- ファイル名と `doctype:` フィールドが一致しているか
- 参照先が存在するか（`numbering/<scheme>.yaml`・`styles/<style_id>.yaml`）
- `variants.styles` に挙げた style がすべて存在するか
- doctype 名が重複していないか（ファイル名が一意なので通常は起きないが、大文字小文字差を拾う）

`keiyaku doctypes` は「読めるものは読み、読めないものは理由をつけて報告する」。
1 件でも問題があれば非ゼロ終了する（CLAUDE.md §2-7「失敗は早く・明示的に」）。
"""

from __future__ import annotations

from pathlib import Path

from keiyaku.blueprints import BLUEPRINTS_DIR, available_doctypes, load_blueprint
from keiyaku.models import Model
from keiyaku.styles import STYLES_DIR

#: numbering の宣言（`numbering/<scheme>.yaml`）の置き場。P2-2 で中身を書く。
NUMBERING_DIR = Path(__file__).resolve().parent.parent / "numbering"


class DoctypeInfo(Model):
    """1 doctype ぶんの読み取り結果。`problems` が空なら健全。"""

    doctype: str
    family: str = "contract"
    description: str = ""
    target_pages: tuple[int, int] | None = None
    page_limit: int | None = None
    numbering_scheme: str = ""
    default_style: str = ""
    styles: list[str] = []
    problems: list[str] = []

    @property
    def ok(self) -> bool:
        return not self.problems


def available_schemes(numbering_dir: Path | None = None) -> list[str]:
    directory = numbering_dir or NUMBERING_DIR
    if not directory.is_dir():
        return []
    return sorted(p.stem for p in directory.glob("*.yaml"))


def inspect(
    blueprints_dir: Path | None = None,
    numbering_dir: Path | None = None,
    styles_dir: Path | None = None,
) -> list[DoctypeInfo]:
    """導入済みの doctype を読み、宣言どうしの食い違いを集める。"""
    bp_dir = blueprints_dir or BLUEPRINTS_DIR
    st_dir = styles_dir or STYLES_DIR
    schemes = set(available_schemes(numbering_dir))
    out: list[DoctypeInfo] = []
    seen: dict[str, str] = {}

    for name in available_doctypes(bp_dir):
        problems: list[str] = []
        try:
            bp = load_blueprint(name, bp_dir)
        except Exception as error:  # noqa: BLE001
            out.append(DoctypeInfo(doctype=name, problems=[f"blueprint が読めない: {error}"]))
            continue

        if bp.doctype != name:
            problems.append(f"ファイル名 {name}.yaml と doctype: {bp.doctype} が食い違う")
        key = name.lower()
        if key in seen:
            problems.append(f"doctype 名が {seen[key]} と衝突する（大文字小文字だけの違い）")
        seen[key] = name

        if schemes and bp.numbering_scheme not in schemes:
            problems.append(f"numbering/{bp.numbering_scheme}.yaml が無い")
        styles = list(getattr(bp.variants, "styles", None) or [bp.default_style])
        for style_id in dict.fromkeys([bp.default_style, *styles]):
            if not (st_dir / f"{style_id}.yaml").is_file():
                problems.append(f"styles/{style_id}.yaml が無い")

        out.append(
            DoctypeInfo(
                doctype=bp.doctype,
                family=bp.family,
                description=bp.description,
                target_pages=bp.target_pages,
                page_limit=getattr(bp, "page_limit", None),
                numbering_scheme=bp.numbering_scheme,
                default_style=bp.default_style,
                styles=styles,
                problems=problems,
            )
        )
    return out
