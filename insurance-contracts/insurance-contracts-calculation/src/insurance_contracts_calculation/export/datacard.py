"""`dataset/data-card.md` の生成（仕様は `docs/data_card.md`）。

    icc datacard update <dataset>   # 書き出す
    icc datacard check  <dataset>   # 書き換えずに鮮度を見る

**カードに出る数値はすべて `dataset/` の実ファイルから測る。** `TASK.md` の表や過去の
セッションの記憶を数値の出典にしない。固定文に統計値を焼き込まない（焼き込むと、
データを足したときに嘘になる）。例外は「作れなかった組」だけで、これは出力の中に無いので
`_run_report.json` から読み、カードにその出所を書く（`docs/data_card.md` §4.5）。

生成は決定論（`CLAUDE.md` 守ること 3）。時刻を入れず、**自分自身のファイルサイズは数えない**
（数えると書き出すたびに数が動き、鮮度検査が収束しない）。

本体（`yakkan`）は import しない。約款は素の JSON として読み、`core/docindex.py` の `Doc` で
索引する（`policy.json` は `derived` を含む完成形なので、再計算も検証も要らない）。
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

#: 生成するファイル名（`dataset/` 直下）
CARD_NAME = "data-card.md"
#: 生成時の記録。**「作れなかった組」だけ**をここから読む
RUN_REPORT = "_run_report.json"
#: 「母数が足りない」と判断する文書数（`docs/data_card.md` §4.4）
MIN_DOCUMENTS = 3
#: 容量の集計から外すファイル名（自分自身を数えると鮮度検査が収束しない）
SIZE_EXCLUDE = frozenset({CARD_NAME})
#: 容量の集計から外すディレクトリ（pytest を回すと増える）
SIZE_EXCLUDE_DIRS = frozenset({"__pycache__", ".pytest_cache"})
#: 観点の分類（カードの並び順もこの順）
COVERAGE_GROUPS = (
    "パターン",
    "ルール",
    "表現手段",
    "難易度の軸",
    "明示した事項",
    "入力の型",
    "演算",
    "宣言",
)


# --- 統計のモデル -------------------------------------------------------------


@dataclass
class ExtSize:
    """拡張子ごとの容量。"""

    ext: str
    files: int
    bytes: int


@dataclass
class CountRow:
    """「名前 → 件数」の 1 行。`documents` はその名前が出た文書数。"""

    name: str
    items: int = 0
    documents: int = 0
    note: str = ""


class Tally:
    """名前ごとの件数と、それが出た文書数を同時に数える。

    文書の処理を終えるたびに `next_document()` を呼ぶ。件数（総数）と文書数（広がり）は
    別物で、カードは両方を出す——「1 文書に 20 件」と「20 文書に 1 件ずつ」を混同しないため。
    """

    def __init__(self) -> None:
        self.items: Counter[str] = Counter()
        self.documents: Counter[str] = Counter()
        self._seen: set[str] = set()

    def add(self, name: str, count: int = 1) -> None:
        self.items[name] += count
        self._seen.add(name)

    def next_document(self) -> None:
        for name in sorted(self._seen):
            self.documents[name] += 1
        self._seen = set()

    def names(self) -> list[str]:
        return sorted(self.items)

    def rows(self, notes: dict[str, str] | None = None) -> list[CountRow]:
        """件数の多い順 → 名前順（決定論）。"""
        notes = notes or {}
        return [
            CountRow(name=name, items=count, documents=self.documents[name], note=notes.get(name, ""))
            for name, count in sorted(self.items.items(), key=lambda kv: (-kv[1], kv[0]))
        ]


@dataclass
class Scale:
    """データセット全体の規模。"""

    documents: int = 0
    bases: int = 0
    genres: int = 0
    profiles: int = 0
    styles: int = 0
    layouts: int = 0
    pages: int = 0
    pages_min: int = 0
    pages_max: int = 0
    page_images: int = 0
    rules: int = 0
    steps: int = 0
    params: int = 0
    lookup_tables: int = 0
    cases: int = 0
    taskcards: int = 0
    programs: int = 0
    program_lines: int = 0
    #: 約款側（`policy.json`）の実測。レイアウトの数で掛けない
    chars: int = 0
    nodes: int = 0
    blocks: int = 0
    units: int = 0
    tables: int = 0
    table_cells: int = 0
    figures: int = 0
    figure_nodes: int = 0
    figure_edges: int = 0
    formulas: int = 0
    refs: int = 0
    footnotes: int = 0
    defined_terms: int = 0
    term_uses: int = 0
    constants: int = 0
    enumerations: int = 0
    #: 計算規定として足した分（`calc/patch.json` の操作）
    added_nodes: int = 0
    added_blocks: int = 0
    added_constants: int = 0
    added_terms: int = 0
    added_index_rows: int = 0
    #: 検証
    mutants: int = 0
    mutant_survivors: int = 0
    undiscoverable_units: int = 0
    challenge_labels: int = 0
    sizes: list[ExtSize] = field(default_factory=list)

    @property
    def bytes_total(self) -> int:
        return sum(s.bytes for s in self.sizes)

    @property
    def files_total(self) -> int:
        return sum(s.files for s in self.sizes)


@dataclass
class GenreRow:
    genre: str
    documents: int = 0
    bases: int = 0
    seconds: int = 0
    rules: int = 0
    cases: int = 0
    layouts: int = 0
    pages_min: int = 0
    pages_max: int = 0
    chars: int = 0


@dataclass
class StyleRow:
    style_id: str
    layouts: int = 0
    pages: int = 0
    pages_min: int = 0
    pages_max: int = 0
    #: その style の PDF に**実際に埋め込まれていた**フォント
    #: （`layout.renderer.fonts` は描画に登録した候補で、使われたものとは違う）
    fonts: list[str] = field(default_factory=list)


@dataclass
class DocRow:
    doc_id: str
    base: str
    variant: int
    genre: str
    profile: str
    seed: int
    rules: int
    cases: int
    patterns: list[str] = field(default_factory=list)
    styles: list[str] = field(default_factory=list)
    pages_min: int = 0
    pages_max: int = 0
    chars: int = 0
    gates_failed: list[str] = field(default_factory=list)


@dataclass
class VariantRow:
    """同じ既定の約款から作った本どうしの、足した規定の顔ぶれの重なり。"""

    base: str
    left: str
    right: str
    shared: int
    union: int
    jaccard: float
    subset: bool


@dataclass
class GateRow:
    code: str
    title: str
    documents: int = 0
    ok: int = 0


@dataclass
class LayoutStats:
    page_sizes: list[CountRow] = field(default_factory=list)
    columns: list[CountRow] = field(default_factory=list)
    regions: list[CountRow] = field(default_factory=list)
    renderers: list[CountRow] = field(default_factory=list)
    dpi: list[CountRow] = field(default_factory=list)
    #: PDF に実際に埋め込まれていたフォント（レイアウト数）
    embedded_fonts: list[CountRow] = field(default_factory=list)
    #: 描画に登録した候補（`layout.renderer.fonts`）
    registered_fonts: list[CountRow] = field(default_factory=list)


@dataclass
class Coverage:
    """1 つの観点を覆っている文書の数。"""

    group: str
    name: str
    documents: int = 0
    title: str = ""


@dataclass
class NotGenerated:
    """作れなかった（既定の約款 × 何本目）の組。出所は `_run_report.json` だけ。"""

    available: bool = False
    count: int = 0
    reasons: list[CountRow] = field(default_factory=list)


@dataclass
class DataCardStats:
    """カードに出すすべての実測値。**カードの本文はここから組み立てる**。"""

    scale: Scale = field(default_factory=Scale)
    genres: list[GenreRow] = field(default_factory=list)
    profiles: list[CountRow] = field(default_factory=list)
    styles: list[StyleRow] = field(default_factory=list)
    documents: list[DocRow] = field(default_factory=list)
    variants: list[VariantRow] = field(default_factory=list)
    variant_counts: list[CountRow] = field(default_factory=list)
    patterns: list[CountRow] = field(default_factory=list)
    rule_kinds: list[CountRow] = field(default_factory=list)
    placements: list[CountRow] = field(default_factory=list)
    modalities: list[CountRow] = field(default_factory=list)
    difficulty: list[CountRow] = field(default_factory=list)
    obligations: list[CountRow] = field(default_factory=list)
    input_types: list[CountRow] = field(default_factory=list)
    input_origins: list[CountRow] = field(default_factory=list)
    output_types: list[CountRow] = field(default_factory=list)
    ops: list[CountRow] = field(default_factory=list)
    atoms: list[CountRow] = field(default_factory=list)
    unit_types: list[CountRow] = field(default_factory=list)
    unit_zones: list[CountRow] = field(default_factory=list)
    scatter: list[CountRow] = field(default_factory=list)
    case_kinds: list[CountRow] = field(default_factory=list)
    hints: list[CountRow] = field(default_factory=list)
    node_kinds: list[CountRow] = field(default_factory=list)
    block_types: list[CountRow] = field(default_factory=list)
    semantic_types: list[CountRow] = field(default_factory=list)
    figure_kinds: list[CountRow] = field(default_factory=list)
    patch_ops: list[CountRow] = field(default_factory=list)
    layout: LayoutStats = field(default_factory=LayoutStats)
    gates: list[GateRow] = field(default_factory=list)
    undiscoverable: list[CountRow] = field(default_factory=list)
    coverage: list[Coverage] = field(default_factory=list)
    #: 覆っている文書が `MIN_DOCUMENTS` 未満（0 は除く）
    thin: list[Coverage] = field(default_factory=list)
    #: 宣言はあるが使っている文書が 0
    unused: list[Coverage] = field(default_factory=list)
    disclaimers: list[str] = field(default_factory=list)
    generator_versions: list[CountRow] = field(default_factory=list)
    spec_versions: list[CountRow] = field(default_factory=list)
    not_generated: NotGenerated = field(default_factory=NotGenerated)
    public_files: list[str] = field(default_factory=list)
    private_files: list[str] = field(default_factory=list)
    case_kind_notes: dict[str, str] = field(default_factory=dict)
    conventions: dict[str, str] = field(default_factory=dict)
    #: 宣言の総数（登録簿から引く。`docs/data_card.md` §4.2）
    declared: dict[str, int] = field(default_factory=dict)

    @property
    def jaccard_mean(self) -> float:
        if not self.variants:
            return 0.0
        return round(sum(v.jaccard for v in self.variants) / len(self.variants), 2)

    @property
    def jaccard_median(self) -> float:
        return round(_median([v.jaccard for v in self.variants]), 2)

    @property
    def subset_pairs(self) -> int:
        return sum(1 for v in self.variants if v.subset)


# --- 測る ---------------------------------------------------------------------


def documents_in(dataset_dir: Path) -> list[Path]:
    """データセットの文書ディレクトリ（`*/calc/manifest.json` のあるもの）。"""
    return sorted(p.parent.parent for p in Path(dataset_dir).glob("*/calc/manifest.json"))


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _median(values: list[float]) -> float:
    """中央値（`statistics` を使わずに決定的に出す）。"""
    if not values:
        return 0.0
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _sizes(dataset_dir: Path) -> list[ExtSize]:
    files: Counter[str] = Counter()
    size: Counter[str] = Counter()
    for path in dataset_dir.rglob("*"):
        if not path.is_file() or path.name.startswith(".") or path.name in SIZE_EXCLUDE:
            continue
        if SIZE_EXCLUDE_DIRS & set(path.parts):
            continue
        ext = path.suffix.lstrip(".") or "（拡張子なし）"
        files[ext] += 1
        size[ext] += path.stat().st_size
    return [
        ExtSize(ext=ext, files=files[ext], bytes=total)
        for ext, total in sorted(size.items(), key=lambda kv: (-kv[1], kv[0]))
    ]


def embedded_fonts(pdf_path: Path) -> list[str]:
    """PDF に**実際に埋め込まれていた**フォント名（サブセット接頭辞を外したもの）。

    `layout.renderer.fonts` は描画に**登録した候補**の一覧であって、使われたものではない。
    フォントの別は読み取りの精度に直接効くので、候補ではなく実測を載せる。
    ページのフォント資源（`/BaseFont`）から読む——全文字を走査するより速く、同じ結果に
    なることは `scripts/verify_datacard.py` が別経路で突合する。PDF が無ければ空を返す。
    """
    if not pdf_path.is_file():
        return []
    import pdfplumber
    from pdfminer.pdftypes import resolve1

    names: set[str] = set()
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            resources = resolve1(page.page_obj.resources) or {}
            for font in (resolve1(resources.get("Font")) or {}).values():
                entry = resolve1(font) or {}
                base = entry.get("BaseFont")
                if base is None:
                    for descendant in resolve1(entry.get("DescendantFonts")) or []:
                        base = (resolve1(descendant) or {}).get("BaseFont") or base
                if base is not None:
                    names.add(str(getattr(base, "name", base)).split("+")[-1])
    return sorted(names)


def walk_expr(node: object) -> Iterator[dict]:
    """式の節を前順に辿る（演算と原子を数えるため）。"""
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk_expr(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_expr(value)


def variant_of(doc_id: str) -> int:
    """文書IDの接尾（`-c1` / `-c2`）から何本目かを読む（`generate.doc_suffix`）。"""
    head, _, tail = doc_id.rpartition("-c")
    return int(tail) if head and tail.isdigit() else 1


def _declared() -> dict[str, list[tuple[str, str]]]:
    """実装が持っている「宣言」の全体（`docs/data_card.md` §4.2）。

    カードに書き写さず、登録簿から引く。(名前, 題) の組で返す。
    """
    from ..config import EXTRA_STYLES, PROFILES
    from ..core import packs
    from ..patterns.registry import ALL
    from ..spec import obligations as ob
    from ..spec.ops import OPS

    return {
        "パターン": [(p.id, p.title) for p in ALL],
        "明示した事項": [(name, "") for name in ob.FAMILIES],
        "演算": [(name, OPS[name].doc) for name in sorted(OPS)],
        "種目": [(g, "") for g in packs.available()],
        "プロファイル": [(name, "") for name in sorted(PROFILES)],
        "スタイル": [(s, "") for s in sorted({s for v in EXTRA_STYLES.values() for s in v})],
    }


def _gate_sort_key(code: str) -> tuple[int, str]:
    digits = "".join(ch for ch in code if ch.isdigit())
    return (int(digits) if digits else 99, code)


def collect(dataset_dir: Path) -> DataCardStats:  # noqa: C901, PLR0912, PLR0915
    """`dataset/` を走査して実測値を集める（**書き出しはしない**）。"""
    from ..core.docindex import Doc
    from ..testgen.cases import KIND_NOTES
    from ..testgen.taskcards import CONVENTIONS
    from .layout import PRIVATE, PUBLIC

    dataset_dir = Path(dataset_dir)
    stats = DataCardStats()
    docs = documents_in(dataset_dir)
    if not docs:
        return stats
    stats.case_kind_notes = dict(KIND_NOTES)
    stats.conventions = dict(CONVENTIONS)
    stats.public_files, stats.private_files = list(PUBLIC), list(PRIVATE)

    scale = stats.scale
    keys = (
        "patterns",
        "rule_kinds",
        "placements",
        "modalities",
        "difficulty",
        "obligations",
        "input_types",
        "input_origins",
        "output_types",
        "ops",
        "atoms",
        "unit_types",
        "unit_zones",
        "scatter",
        "case_kinds",
        "hints",
        "node_kinds",
        "block_types",
        "semantic_types",
        "figure_kinds",
        "patch_ops",
        "profiles",
        "variant_counts",
        "generator_versions",
        "spec_versions",
        "page_sizes",
        "columns",
        "regions",
        "renderers",
        "dpi",
        "embedded_fonts",
        "registered_fonts",
        "undiscoverable",
    )
    tally: dict[str, Tally] = {key: Tally() for key in keys}
    by_genre: dict[str, GenreRow] = {}
    genre_bases: dict[str, set[str]] = {}
    by_style: dict[str, StyleRow] = {}
    style_fonts: dict[str, set[str]] = {}
    gate_ok: Counter[str] = Counter()
    gate_seen: Counter[str] = Counter()
    rules_by_base: dict[str, dict[str, set[str]]] = {}
    feature_docs: Counter[tuple[str, str]] = Counter()
    disclaimers: set[str] = set()
    bases: set[str] = set()

    for doc_dir in docs:
        calc = doc_dir / "calc"
        manifest = _read_json(calc / "manifest.json")
        spec = _read_json(calc / "spec.json")
        answer = _read_json(calc / "answer_key.json")
        cases = _read_jsonl(calc / "cases.jsonl")
        patch = _read_json(calc / "patch.json")
        policy = _read_json(doc_dir / "policy.json")

        doc_id = str(manifest["content_id"])
        base = str(manifest["base_content_id"])
        genre = str(manifest["genre"])
        profile = str(manifest["profile"])
        variant = variant_of(doc_id)
        bases.add(base)
        features: set[tuple[str, str]] = set()

        # ---- 計算仕様 -----------------------------------------------------
        for rule in spec["rules"]:
            tally["rule_kinds"].add(str(rule["kind"]))
            features.add(("ルール", f"種別: {rule['kind']}"))
            scale.steps += len(rule["steps"])
            placement = str(rule["presentation"]["placement"])
            tally["placements"].add(placement)
            features.add(("ルール", f"配置: {placement}"))
            pattern = str(rule["presentation"]["pattern"])
            tally["patterns"].add(pattern)
            features.add(("パターン", pattern))
            for oid in rule.get("obligations", []):
                tally["obligations"].add(str(oid))
                features.add(("明示した事項", str(oid)))
            for _name, declared_in in sorted(rule.get("inputs", {}).items()):
                tally["input_types"].add(str(declared_in["type"]))
                tally["input_origins"].add(str(declared_in.get("origin", "（未記載）")))
                features.add(("入力の型", str(declared_in["type"])))
            tally["output_types"].add(str(rule["output"]["type"]))
            for node in walk_expr([step["expr"] for step in rule["steps"]]):
                if "op" in node:
                    tally["ops"].add(str(node["op"]))
                    features.add(("演算", str(node["op"])))
                for atom in ("lit", "param", "var", "step", "rule", "item"):
                    if atom in node:
                        tally["atoms"].add(atom)
        scale.rules += len(spec["rules"])
        scale.params += len(spec.get("params", {}))
        scale.lookup_tables += len(spec.get("tables", {}))
        tally["spec_versions"].add(str(spec.get("spec_version", "?")))
        tally["generator_versions"].add(str(manifest.get("generator_version", "?")))

        # ---- 正解表（根拠単位・表現手段・難易度） ----------------------------
        doc_index = Doc.from_dict(policy)
        for entry in answer:
            for modality in entry.get("modalities", []):
                tally["modalities"].add(str(modality))
                features.add(("表現手段", str(modality)))
            for key, value in sorted(entry.get("difficulty", {}).items()):
                if isinstance(value, bool):
                    if not value:
                        continue
                    label = key
                else:
                    label = f"{key}={value}"
                tally["difficulty"].add(label)
                features.add(("難易度の軸", label))
            units = [str(u) for u in entry.get("units", [])]
            tally["scatter"].add(f"{len(units)} 単位")
            for uid in units:
                unit = doc_index.units.get(uid)
                if unit is not None:
                    tally["unit_types"].add(unit.utype)
                    tally["unit_zones"].add(unit.zone)
                elif uid in doc_index.blocks:
                    tally["unit_types"].add(str(doc_index.blocks[uid]["type"]))
                    tally["unit_zones"].add("（ブロック全体）")
                else:
                    tally["unit_types"].add("（索引に無い）")
        rules_by_base.setdefault(base, {})[doc_id] = {str(r["rule"]) for r in answer}

        # ---- テストケースとタスクカード --------------------------------------
        for case in cases:
            tally["case_kinds"].add(str(case["kind"]))
        scale.cases += len(cases)
        for name, hint in (("tasks.jsonl", "H0"), ("tasks_H1.jsonl", "H1"), ("tasks_H2.jsonl", "H2")):
            rows = _read_jsonl(calc / name)
            tally["hints"].add(hint, len(rows))
            scale.taskcards += len(rows)

        # ---- 正解プログラム --------------------------------------------------
        for program in sorted((calc / "programs").glob("*.py")):
            scale.programs += 1
            scale.program_lines += len(program.read_text(encoding="utf-8").splitlines())

        # ---- 約款への追加（パッチ） --------------------------------------------
        for op in patch:
            tally["patch_ops"].add(str(op["op"]))
        added = manifest.get("added", {})
        scale.added_nodes += int(added.get("add_node", 0))
        scale.added_blocks += int(added.get("add_block", 0))
        scale.added_constants += int(added.get("add_constant", 0))
        scale.added_terms += int(added.get("add_term", 0))
        scale.added_index_rows += int(added.get("add_index_row", 0))
        scale.challenge_labels += len(manifest.get("challenge", []) or [])

        # ---- 約款の中身（レイアウトの数で掛けない） -----------------------------
        derived = policy["derived"]
        chars = sum(len(v.get("without_label", "")) for v in derived["plain_text"].values())
        scale.chars += chars
        scale.nodes += len(doc_index.nodes)
        scale.blocks += len(doc_index.blocks)
        scale.units += len(doc_index.units)
        scale.refs += len(derived["refs"])
        scale.footnotes += len(derived["footnote_index"])
        scale.formulas += len(derived["formulas"])
        scale.enumerations += len(derived["enumerations"])
        scale.defined_terms += len(policy.get("defined_terms", []))
        scale.term_uses += len(derived["term_uses"])
        scale.constants += len(policy["meta"].get("constants", {}))
        for node in doc_index.nodes.values():
            tally["node_kinds"].add(str(node["kind"]))
        for block in doc_index.blocks.values():
            tally["block_types"].add(str(block["type"]))
            if block["type"] == "table":
                scale.tables += 1
                scale.table_cells += sum(len(row) for row in block.get("grid", []))
                tally["semantic_types"].add(str(block.get("semantic_type", "（未指定）")))
            if block["type"] == "figure":
                scale.figures += 1
                tally["figure_kinds"].add(str(block["diagram"]["kind"]))
        for figure in derived["figures"].values():
            scale.figure_nodes += len(figure["graph"]["nodes"])
            scale.figure_edges += len(figure["graph"]["edges"])
        disclaimers.add(str(policy["meta"].get("disclaimer", "")))

        # ---- 検証ゲート --------------------------------------------------------
        failed: list[str] = []
        for code, result in sorted(manifest.get("gates", {}).items()):
            gate_seen[code] += 1
            if result.get("ok"):
                gate_ok[code] += 1
            else:
                failed.append(code)
            if code == "G7":
                scale.mutants += int(result.get("mutants", 0))
                scale.mutant_survivors += len(result.get("survivors", {}) or {})
            if code == "G10":
                for uid in result.get("missing", []) or []:
                    scale.undiscoverable_units += 1
                    unit = doc_index.units.get(str(uid))
                    tally["undiscoverable"].add(unit.utype if unit is not None else "（索引に無い）")

        # ---- レイアウト（描画結果） ----------------------------------------------
        pages: list[int] = []
        styles: list[str] = []
        for layout_path in sorted(doc_dir.glob("*/layout.json")):
            layout = _read_json(layout_path)
            style_id = str(layout["style_id"])
            styles.append(style_id)
            page_count = int(layout["page_count"])
            pages.append(page_count)
            scale.layouts += 1
            scale.pages += page_count
            width, height = layout["page_size_pt"]
            tally["page_sizes"].add(
                f"{width:.0f}×{height:.0f} pt（{width * 25.4 / 72:.0f}×{height * 25.4 / 72:.0f} mm）"
            )
            renderer = layout["renderer"]
            tally["renderers"].add(f"{renderer['name']} {renderer['version']}")
            tally["dpi"].add(f"{layout['dpi_png']} dpi")
            for font in renderer.get("fonts", []):
                tally["registered_fonts"].add(str(font))
            for page in layout["pages"]:
                tally["columns"].add(f"{page['columns']} 段")
                for line in page["text_lines"]:
                    tally["regions"].add(str(line["region"]))
            used = embedded_fonts(layout_path.parent / "doc.pdf")
            for font in used:
                tally["embedded_fonts"].add(font)
            style_fonts.setdefault(style_id, set()).update(used)
            row = by_style.setdefault(style_id, StyleRow(style_id=style_id))
            row.layouts += 1
            row.pages += page_count
            row.pages_min = page_count if row.pages_min == 0 else min(row.pages_min, page_count)
            row.pages_max = max(row.pages_max, page_count)
            scale.page_images += len(list((layout_path.parent / "pages").glob("*.png")))
            features.add(("宣言", f"スタイル: {style_id}"))

        tally["profiles"].add(profile)
        tally["variant_counts"].add(f"{variant} 本目")
        features.add(("宣言", f"種目: {genre}"))
        features.add(("宣言", f"プロファイル: {profile}"))

        genre_row = by_genre.setdefault(genre, GenreRow(genre=genre))
        genre_row.documents += 1
        genre_row.rules += len(spec["rules"])
        genre_row.cases += len(cases)
        genre_row.layouts += len(styles)
        genre_row.chars += chars
        if variant >= 2:
            genre_row.seconds += 1
        if pages:
            genre_row.pages_min = (
                min(pages) if genre_row.pages_min == 0 else min(genre_row.pages_min, min(pages))
            )
            genre_row.pages_max = max(genre_row.pages_max, max(pages))
        genre_bases.setdefault(genre, set()).add(base)

        stats.documents.append(
            DocRow(
                doc_id=doc_id,
                base=base,
                variant=variant,
                genre=genre,
                profile=profile,
                seed=int(manifest["seed"]),
                rules=len(spec["rules"]),
                cases=len(cases),
                patterns=sorted({str(r["presentation"]["pattern"]) for r in spec["rules"]}),
                styles=styles,
                pages_min=min(pages) if pages else 0,
                pages_max=max(pages) if pages else 0,
                chars=chars,
                gates_failed=failed,
            )
        )
        for key in sorted(features):
            feature_docs[key] += 1
        for counter in tally.values():
            counter.next_document()

    scale.documents = len(docs)
    scale.bases = len(bases)
    scale.genres = len(by_genre)
    scale.profiles = len(tally["profiles"].items)
    scale.styles = len(by_style)
    scale.pages_min = min((d.pages_min for d in stats.documents if d.pages_min), default=0)
    scale.pages_max = max((d.pages_max for d in stats.documents), default=0)
    scale.sizes = _sizes(dataset_dir)

    for genre, genre_row in by_genre.items():
        genre_row.bases = len(genre_bases[genre])
    stats.genres = sorted(by_genre.values(), key=lambda r: r.genre)
    for style_id, style_row in by_style.items():
        style_row.fonts = sorted(style_fonts.get(style_id, set()))
    stats.styles = sorted(by_style.values(), key=lambda r: r.style_id)
    stats.documents.sort(key=lambda r: r.doc_id)

    declared = _declared()
    stats.declared = {key: len(values) for key, values in sorted(declared.items())}
    pattern_titles = dict(declared["パターン"])
    op_titles = dict(declared["演算"])
    for key in keys:
        if hasattr(stats, key):
            notes = pattern_titles if key == "patterns" else op_titles if key == "ops" else None
            setattr(stats, key, tally[key].rows(notes))
    stats.layout = LayoutStats(
        page_sizes=tally["page_sizes"].rows(),
        columns=tally["columns"].rows(),
        regions=tally["regions"].rows(),
        renderers=tally["renderers"].rows(),
        dpi=tally["dpi"].rows(),
        embedded_fonts=tally["embedded_fonts"].rows(),
        registered_fonts=tally["registered_fonts"].rows(),
    )
    from ..verify.gates import GATE_TITLES

    stats.gates = [
        GateRow(code=code, title=GATE_TITLES.get(code, ""), documents=gate_seen[code], ok=gate_ok[code])
        for code in sorted(gate_seen, key=_gate_sort_key)
    ]
    stats.variants = _variant_rows(rules_by_base)
    stats.disclaimers = sorted(d for d in disclaimers if d)
    stats.coverage, stats.thin, stats.unused = _coverage(feature_docs, declared, pattern_titles, op_titles)
    stats.not_generated = _not_generated(dataset_dir)
    return stats


def _variant_rows(rules_by_base: dict[str, dict[str, set[str]]]) -> list[VariantRow]:
    """同じ既定の約款から作った本どうしの重なり（2 本以上ある約款だけ）。"""
    out: list[VariantRow] = []
    for base in sorted(rules_by_base):
        doc_ids = sorted(rules_by_base[base])
        if len(doc_ids) < 2:
            continue
        for i, left in enumerate(doc_ids):
            for right in doc_ids[i + 1 :]:
                a, b = rules_by_base[base][left], rules_by_base[base][right]
                union, shared = len(a | b), len(a & b)
                out.append(
                    VariantRow(
                        base=base,
                        left=left,
                        right=right,
                        shared=shared,
                        union=union,
                        jaccard=round(shared / union, 2) if union else 0.0,
                        subset=bool(a) and bool(b) and (a <= b or b <= a),
                    )
                )
    return out


def _coverage(
    feature_docs: Counter[tuple[str, str]],
    declared: dict[str, list[tuple[str, str]]],
    pattern_titles: dict[str, str],
    op_titles: dict[str, str],
) -> tuple[list[Coverage], list[Coverage], list[Coverage]]:
    """観点ごとの覆い（文書数）と、母数の小さいもの・使用 0 のものを分ける。"""
    universe: set[tuple[str, str]] = set(feature_docs)
    universe |= {("パターン", pid) for pid, _ in declared["パターン"]}
    universe |= {("明示した事項", oid) for oid, _ in declared["明示した事項"]}
    universe |= {("演算", name) for name, _ in declared["演算"]}
    universe |= {("宣言", f"種目: {g}") for g, _ in declared["種目"]}
    universe |= {("宣言", f"プロファイル: {p}") for p, _ in declared["プロファイル"]}
    universe |= {("宣言", f"スタイル: {s}") for s, _ in declared["スタイル"]}
    order = {group: i for i, group in enumerate(COVERAGE_GROUPS)}
    titles = {("パターン", k): v for k, v in pattern_titles.items()}
    titles |= {("演算", k): v for k, v in op_titles.items()}
    rows = sorted(
        (
            Coverage(
                group=group,
                name=name,
                documents=feature_docs.get((group, name), 0),
                title=titles.get((group, name), ""),
            )
            for group, name in universe
        ),
        key=lambda c: (order.get(c.group, 99), -c.documents, c.name),
    )
    thin = [c for c in rows if 0 < c.documents < MIN_DOCUMENTS]
    unused = [c for c in rows if c.documents == 0]
    return rows, thin, unused


def _not_generated(dataset_dir: Path) -> NotGenerated:
    """作れなかった組（出所は `_run_report.json` だけ。無ければ項を落とす）。"""
    path = dataset_dir / RUN_REPORT
    if not path.is_file():
        return NotGenerated()
    section = (_read_json(path) or {}).get("not_generated") or {}
    entries = section.get("entries") or {}
    reasons = Tally()
    for detail in sorted(entries.values()):
        reasons.add(str(detail).split(":", 1)[0].strip() or "（理由の記録なし）")
    return NotGenerated(available=True, count=int(section.get("count", len(entries))), reasons=reasons.rows())


# --- 書く ---------------------------------------------------------------------


def _n(value: int) -> str:
    return f"{value:,}"


def _range(low: int, high: int) -> str:
    return str(low) if low == high else f"{low}–{high}"


def _size(value: int) -> str:
    """容量（1 MiB 未満は KiB、1 GiB 以上は GiB）。"""
    if value < 1048576:
        return f"{value / 1024:.0f} KiB"
    if value < 1073741824:
        return f"{value / 1048576:.1f} MiB"
    return f"{value / 1073741824:.1f} GiB"


def _table(header: list[str], rows: list[list[str]]) -> str:
    if not rows:
        return "（該当なし）\n"
    out = ["| " + " | ".join(header) + " |", "|" + "---|" * len(header)]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out) + "\n"


def _count_table(rows: list[CountRow], label: str, *, with_documents: bool = True, note: str = "") -> str:
    """件数の表。`note` 欄を持つ行があれば 1 列足す。"""
    has_note = any(r.note for r in rows)
    header = [label, "件数"]
    if with_documents:
        header.append("この要素を持つ文書")
    if has_note:
        header.append(note or "説明")
    body = []
    for r in rows:
        row = [r.name, _n(r.items)]
        if with_documents:
            row.append(_n(r.documents))
        if has_note:
            row.append(r.note)
        body.append(row)
    return _table(header, body)


def render_card(stats: DataCardStats) -> str:  # noqa: PLR0915
    """実測値から Markdown を組み立てる。**固定文に数値を書かない**。"""
    scale, layout = stats.scale, stats.layout
    parts: list[str] = []
    add = parts.append

    add(
        "# データカード — yakkan-calc 合成約款＋計算規定データセット\n\n"
        "**このファイルは `icc datacard update`（`icc batch` / `icc generate` からも呼ばれる）が"
        "生成する。手で編集しない**（`CLAUDE.md` 守ること 2）。仕様は `docs/data_card.md`、"
        "作り方と使い方は `README.md`、設計の正本は `DESIGN.md`。\n\n"
        "数値はすべて `dataset/` の実ファイルを測った結果で、生成し直すたびに更新される。\n"
    )

    if scale.documents == 0:
        add("\n**このデータセットには文書が無い。** `icc batch` で生成する。\n")
        return "".join(parts)

    add("\n## 1. 概要\n\n")
    add(
        f"**完全に架空**の日本語保険約款 **{_n(scale.documents)} 文書**に、"
        f"機械生成した**計算・判定の規定**（条・表・算式・図）を足し、"
        f"その**正解プログラム**（Python）と**テストケース**を同じ計算仕様から作ったデータセットである。"
        f"**{_n(scale.bases)} 件**の既定の約款（本体 `insurance-contracts` の執筆物）をもとに、"
        f"**{_n(scale.genres)} 種目**・計 **{_n(scale.rules)} ルール**・"
        f"**{_n(scale.cases)} テストケース**を収める。\n\n"
        f"- 同じ内容を **{_n(scale.styles)} 種**の体裁で描いた描画結果（レイアウト）が "
        f"**{_n(scale.layouts)}** あり、ページは **{_n(scale.pages)}**、"
        f"ページ画像は **{_n(scale.page_images)}** 枚ある。**正解は 1 文書に 1 組**で、"
        "体裁が変わっても正解は変わらない（レイアウト頑健性の評価に使う）。\n"
        "- **計算仕様が唯一の正である。** 約款の文言・正解プログラム・テストの期待値は、"
        "すべて同じ仕様から機械的に作ってある。文言とプログラムを別々に書いていないので、"
        "両者がずれることが原理的に起きない。\n"
        f"- **⚠ 正解が入っている。**（§12）計算仕様・正解プログラム・正解表・全テストケースが"
        f"同梱されている。**学習に使うと、このデータセットでの評価が成り立たなくなる。**\n"
        "- 会社名・商品名・連絡先・人物名はすべて架空で、法的効力を持たない（§11）。\n"
    )

    add("\n## 2. 想定する用途／想定しない用途\n\n")
    add(
        "**想定する用途**（これに合わせて正解を設計した。`DESIGN.md` §11.4）\n\n"
        "1. **実装**：約款（JSON）とタスクカードを渡し、計算・判定の関数を実装させて"
        "テストケースで採点する（`icc eval --track impl`）。\n"
        "2. **発見**：約款だけを渡し、「どこに計算規定があるか」を根拠単位の単位で答えさせて"
        "再現率と適合率を測る（`--track discover`）。\n"
        "3. **一気通貫**：PDF の読み取り結果を入力にして実装させ、"
        "読み取りの誤りが実装に及ぶ影響を含めて測る（`--track e2e`）。\n"
        "4. **レイアウト頑健性**：同じ内容を別の体裁で描いた対で、正解を変えずに紙面だけ変える。\n"
        "5. 表・算式・図の構造理解（規定が図だけに書かれている場合を含む）。\n"
        "6. **三値論理**（不明な入力の扱い）の評価。\n\n"
        "**想定しない用途**\n\n"
        "- **実務の保険引受・支払査定・法的な参照。** 規定は評価のために機械生成したもので、"
        "保険数理・監督規制の妥当性は一切担保しない。\n"
        "- 実在の約款・商品の再現（構造だけを参考にし、文章はすべて生成した。§11）。\n"
        "- 言語モデルの事前学習コーパス（§12 のとおり正解が混ざるため、**汚染源になる**）。\n"
        "- スキャン画像・手書き・印影を含む劣化画像の評価（§13）。\n"
    )

    add("\n## 3. 規模（実測）\n\n")
    add(
        _table(
            ["項目", "実測値"],
            [
                ["文書（`policy.json` ＋ 1 組の正解）", _n(scale.documents)],
                ["既定の約款（本体の執筆物）", _n(scale.bases)],
                ["種目", f"{_n(scale.genres)}（宣言 {_n(stats.declared.get('種目', 0))}）"],
                [
                    "難易度プロファイル",
                    f"{_n(scale.profiles)}（宣言 {_n(stats.declared.get('プロファイル', 0))}）",
                ],
                ["体裁（style）", _n(scale.styles)],
                ["描画結果（レイアウト）", _n(scale.layouts)],
                [
                    "ページ",
                    f"{_n(scale.pages)}（1 レイアウトあたり {_range(scale.pages_min, scale.pages_max)}）",
                ],
                ["ページ画像（PNG）", _n(scale.page_images)],
                ["ルール（計算・判定の規定）", _n(scale.rules)],
                ["手順（名前つきの中間の額）", _n(scale.steps)],
                ["パラメータ（仕様が参照する定数）", _n(scale.params)],
                ["参照表（表引きの表）", _n(scale.lookup_tables)],
                ["テストケース", _n(scale.cases)],
                ["タスクカード（出題。H0・H1・H2 の合計）", _n(scale.taskcards)],
                ["正解プログラム", f"{_n(scale.programs)} ファイル / {_n(scale.program_lines)} 行"],
                [
                    "変異体（テストの十分性の検査）",
                    f"{_n(scale.mutants)}（生き残り {_n(scale.mutant_survivors)}）",
                ],
                ["約款の本文の文字数（`derived.plain_text`）", _n(scale.chars)],
                [
                    "約款のノード / ブロック / 根拠単位",
                    f"{_n(scale.nodes)} / {_n(scale.blocks)} / {_n(scale.units)}",
                ],
                ["表 / セル", f"{_n(scale.tables)} / {_n(scale.table_cells)}"],
                [
                    "図 / ノード / 辺",
                    f"{_n(scale.figures)} / {_n(scale.figure_nodes)} / {_n(scale.figure_edges)}",
                ],
                ["算式", _n(scale.formulas)],
                ["参照（`{ref:}` の解決結果）", _n(scale.refs)],
                [
                    "列挙 / 定義語 / 用語の参照",
                    f"{_n(scale.enumerations)} / {_n(scale.defined_terms)} / {_n(scale.term_uses)}",
                ],
                ["定数（`{const:}`）", _n(scale.constants)],
                ["脚注", _n(scale.footnotes)],
                ["容量", f"{_size(scale.bytes_total)} / {_n(scale.files_total)} ファイル"],
            ],
        )
    )
    add(
        "\n約款側（文字数・ノード・表・図ほか）は**文書ごとに 1 回だけ**数えている。"
        "同じ `policy.json` が体裁ごとに複製されているが、内容は同一なので"
        "レイアウトの数で掛けない（`docs/data_card.md` §4.1）。\n"
    )
    add("\n容量の内訳：\n\n")
    add(
        _table(
            ["種類", "ファイル数", "容量"],
            [[f"`.{s.ext}`", _n(s.files), _size(s.bytes)] for s in scale.sizes],
        )
    )
    add(f"\n（`{CARD_NAME}` 自身・ドットファイル・`__pycache__` は数えていない。`docs/data_card.md` §4.1）\n")

    add("\n### 3.1 計算規定として足した分\n\n")
    add(
        _table(
            ["足したもの", "件数"],
            [
                ["条・項（ノード）", _n(scale.added_nodes)],
                ["ブロック（表・図・算式・囲み）", _n(scale.added_blocks)],
                ["定数（`meta.constants`）", _n(scale.added_constants)],
                ["定義語", _n(scale.added_terms)],
                ["目的別もくじ・特約一覧への行", _n(scale.added_index_rows)],
            ],
        )
    )
    add("\nパッチの操作の内訳（`calc/patch.json`）：\n\n")
    add(_count_table(stats.patch_ops, "操作"))
    add(
        "\n表・図・算式は多くの場合**条のノードの中**に入れて足すので、`add_node` に数えられる"
        "（`add_block` は既存のノードに単独で足した場合だけである）。"
        "**既定の約款にもともとある規定も読み取りの対象である。** 上は足した分だけで、"
        "§7 の表は足した分と既定の分を合わせた実測である（`docs/data_card.md` §4.3）。\n"
    )

    add("\n## 4. 内訳\n\n### 4.1 種目別\n\n")
    add(
        _table(
            [
                "種目",
                "文書",
                "既定の約款",
                "2 本目以降",
                "ルール",
                "ケース",
                "レイアウト",
                "ページ",
                "本文字数",
            ],
            [
                [
                    f"`{r.genre}`",
                    _n(r.documents),
                    _n(r.bases),
                    _n(r.seconds),
                    _n(r.rules),
                    _n(r.cases),
                    _n(r.layouts),
                    _range(r.pages_min, r.pages_max),
                    _n(r.chars),
                ]
                for r in stats.genres
            ],
        )
    )
    add("\n### 4.2 難易度プロファイル別\n\n")
    add(_count_table(stats.profiles, "プロファイル（文書数）", with_documents=False))
    add(
        "\nプロファイルは「1 条に閉じた規定（`basic`）」「文と表の組合せ・別表への分離（`standard`）」"
        "「図のみ・分散・特約による上書き・月や年の計算（`hard`）」の順に難しくなる"
        "（`DESIGN.md` §9.2。割合は `config.PROFILES`）。\n"
    )
    add("\n### 4.3 体裁（style）別\n\n")
    add(
        _table(
            ["style_id", "レイアウト", "ページ（最小–最大）", "PDF に埋め込まれていたフォント"],
            [
                [
                    f"`{r.style_id}`",
                    _n(r.layouts),
                    _range(r.pages_min, r.pages_max),
                    "、".join(r.fonts) or "（PDF なし）",
                ]
                for r in stats.styles
            ],
        )
    )
    add(
        "\n体裁は本体の style プリセットである。1 文書を複数の体裁で描き、"
        "**正解は 1 組のまま紙面だけ変える**（`config.EXTRA_STYLES` が種目ごとの追加の既定。"
        "`HITL.md` H3 (c)）。描けなかった体裁は**その体裁だけ外して**記録する——"
        "文書は捨てない。\n"
    )
    add("\n### 4.4 文書の全件\n\n")
    add(
        _table(
            [
                "doc_id",
                "既定の約款",
                "何本目",
                "種目",
                "難易度",
                "seed",
                "ルール",
                "ケース",
                "パターン",
                "体裁",
                "ページ",
                "本文字数",
                "落ちたゲート",
            ],
            [
                [
                    f"`{r.doc_id}`",
                    f"`{r.base}`",
                    str(r.variant),
                    f"`{r.genre}`",
                    r.profile,
                    str(r.seed),
                    str(r.rules),
                    str(r.cases),
                    "・".join(r.patterns),
                    str(len(r.styles)),
                    _range(r.pages_min, r.pages_max),
                    _n(r.chars),
                    "・".join(r.gates_failed) or "—",
                ]
                for r in stats.documents
            ],
        )
    )
    add("\n### 4.5 同じ既定の約款から作った 2 本目の重なり\n\n")
    add(_count_table(stats.variant_counts, "何本目（文書数）", with_documents=False))
    if stats.variants:
        add(
            f"\n同じ既定の約款から 2 本以上作った組は **{_n(len(stats.variants))} 組**ある。"
            "足した規定の顔ぶれ（ルールID の集合）の重なりは "
            f"**Jaccard 平均 {stats.jaccard_mean}・中央値 {stats.jaccard_median}**で、"
            f"**{_n(stats.subset_pairs)} 組は一方がもう一方の部分集合**である。"
            "顔ぶれが完全に同じ組は生成時に弾いているが、部分集合は弾いていない。"
            "重なっていても値・表現手段・配置・文言は種が違うので別物になる。"
            "**題材の広さを増やしたいなら、既定の約款を増やすのが本筋である**（`TASK.md` T13）。\n\n"
        )
        add(
            _table(
                ["既定の約款", "組", "共通", "和", "Jaccard", "部分集合"],
                [
                    [
                        f"`{v.base}`",
                        f"`{v.left}` ／ `{v.right}`",
                        str(v.shared),
                        str(v.union),
                        f"{v.jaccard:.2f}",
                        "はい" if v.subset else "—",
                    ]
                    for v in stats.variants
                ],
            )
        )
    else:
        add("\n同じ既定の約款から 2 本以上作った組は無い。\n")

    if stats.not_generated.available:
        add("\n### 4.6 作れなかった組\n\n")
        add(
            f"試して作れなかった（既定の約款 × 何本目）の組は **{_n(stats.not_generated.count)} 件**ある。"
            "**黙って外していないことの記録である。** "
            f"出所はこの節だけ `dataset/{RUN_REPORT}`（生成時の記録）で、"
            "ほかの数値はすべて出力の実ファイルから測っている（`docs/data_card.md` §4.5）。\n\n"
        )
        add(_count_table(stats.not_generated.reasons, "理由", with_documents=False))
        add(
            "\n`gate` は検証ゲートに落ちたもの（規定を足せる章が無いなど）、"
            "`RenderLayoutError` は WeasyPrint の版の既知の弱さで描画が破綻したもの、"
            "`RuntimeError` は種をずらしても先に作った本と同じ顔ぶれにしかならなかったものである。\n"
        )

    add("\n## 5. 計算規定の正解\n\n### 5.1 パターン（ルールの型）\n\n")
    add(_count_table(stats.patterns, "パターン", note="型"))
    add(
        "\nパターンは**ルールの型**で、1 つのパターンが同じ乱数から「約款に足す内容」と「仕様」の"
        "両方を作る（`DESIGN.md` §7）。**使われていないパターンは §13 が名指しする。**\n"
    )
    add("\n### 5.2 ルールの種別と配置\n\n")
    add(_count_table(stats.rule_kinds, "種別"))
    add("\n")
    add(_count_table(stats.placements, "配置"))
    add(
        "\n`article` は条の追加、`rider` は特約への分離、`appendix` は別表への分離である。"
        "分散のしかたは難易度に効く（`DESIGN.md` §8.5）。\n"
    )
    add("\n### 5.3 表現手段（規定がどこに書かれているか）\n\n")
    add(_count_table(stats.modalities, "表現手段"))
    add(
        "\n1 つのルールが複数の手段にまたがる（文＋算式、文＋図など）。"
        "**`figure` だけが規範のルール**は、図を読めないと解けない（§5.4 の `figure_only`）。\n"
    )
    add("\n### 5.4 難易度の軸\n\n")
    add(_count_table(stats.difficulty, "軸"))
    add("\n### 5.5 明示した事項（一義に読めるようにした点）\n\n")
    add(_count_table(stats.obligations, "要件"))
    add(
        "\n適用順・端数処理・以上と超える・起算日・0 円の下限などは、**文に書かれていなければ"
        "一義に読めない**。足した規定については検証ゲート G3 が「対応する文があること」を"
        "強制している（`DESIGN.md` §8.3）。**既定の約款の部分にはこの保証がない**（§13）。\n"
    )
    add("\n### 5.6 入力\n\n")
    add(_count_table(stats.input_types, "型"))
    add("\n")
    add(_count_table(stats.input_origins, "出所（その値を誰が持っているか）"))
    add("\n")
    add(_count_table(stats.output_types, "出力の型", with_documents=False))
    add("\n### 5.7 演算\n\n")
    add(_count_table(stats.ops, "演算", note="意味"))
    add("\n式の原子：\n\n")
    add(_count_table(stats.atoms, "原子"))
    add(
        "\n`var` は入力、`param` は約款から読む定数、`step` は前の手順、`rule` はほかのルールの"
        "呼び出し、`lit` は数値リテラル（0 以外には根拠の注記が必須）、`item` は明細の項目である。\n"
    )
    add("\n### 5.8 根拠単位（どこを読めば答えが分かるか）\n\n")
    add(_count_table(stats.unit_types, "単位の種別"))
    add("\n単位のある場所：\n\n")
    add(_count_table(stats.unit_zones, "zone"))
    add("\n1 ルールあたりの根拠単位の数（分散度）：\n\n")
    add(_count_table(stats.scatter, "根拠単位の数", with_documents=False))
    add(
        "\n`answer_key.json` の `units` が規範の根拠で、「発見」の採点はこれに対して行う。"
        "`explanatory_units`（設例などの説明）は採点に入れない（`DESIGN.md` §10.4）。\n"
    )

    add("\n## 6. 評価データ\n\n### 6.1 テストケース\n\n")
    add(_count_table(stats.case_kinds, "種別", note="ねらい"))
    add(
        "\n期待値は参照インタプリタ（`spec/interp.py`）で計算し、正解プログラムの出力と"
        "一致しなければ生成を止める（検証ゲート G6）。"
        "設例だけは公開してよい——配布時に渡すのは `calc/examples.jsonl` だけである（§12）。\n"
    )
    add("\n### 6.2 タスクカード（出題）とヒントの水準\n\n")
    add(_count_table(stats.hints, "水準（出題の件数）", with_documents=False))
    add(
        "\n| 水準 | 渡すもの |\n|---|---|\n"
        "| H0 | 関数名と入出力だけ（`calc/tasks.jsonl`） |\n"
        "| H1 | H0 ＋ 主な条の条番号（`calc/tasks_H1.jsonl`） |\n"
        "| H2 | H1 ＋ 根拠単位のID（`calc/tasks_H2.jsonl`） |\n\n"
        "出題に添える**呼び出しの取り決め**（`testgen/taskcards.py` の `CONVENTIONS` が唯一の正）：\n\n"
    )
    add("\n".join(f"- **{key}**：{text}。" for key, text in sorted(stats.conventions.items())) + "\n")
    add("\n### 6.3 採点\n\n")
    add(
        "```\n"
        "pytest <doc>/calc/tests                      # 正解プログラムで実行（全件合格が正しい）\n"
        "pytest <doc>/calc/tests --impl my_module.py  # 提出されたプログラムで実行\n"
        "icc eval --submission impl.py --data <doc> --track impl --hint H0\n"
        "```\n\n"
        "提出はネットワークなし・時間制限つきの別プロセスで動かす（`evalkit/runner.py`）。"
        "結果はパターン・表現手段・難易度の軸・ケースの種別ごとに集計する——"
        "合計点だけを見ると「図だけのルールに弱い」「境界に弱い」が見えない。\n"
    )

    add("\n## 7. 約款（読み取りの対象）の中身\n\n")
    add("足した分と既定の分を合わせた実測である。\n\n### 7.1 ノード種別\n\n")
    add(_count_table(stats.node_kinds, "`kind`"))
    add("\n### 7.2 ブロック種別\n\n")
    add(_count_table(stats.block_types, "`type`"))
    add("\n### 7.3 表の意味種別\n\n")
    add(_count_table(stats.semantic_types, "`semantic_type`"))
    add("\n### 7.4 図の種別\n\n")
    add(_count_table(stats.figure_kinds, "`kind`"))
    add(
        "\n図は外部のレイアウトエンジンを使わず、格子座標から決定論的に SVG にしている"
        "（本体 `CLAUDE.md` §2-5）。ノードの座標が正解として自明に得られる。\n"
    )

    add("\n## 8. 版面\n\n")
    add(_count_table(layout.page_sizes, "判型（レイアウト数）", with_documents=False))
    add("\n")
    add(_count_table(layout.columns, "段組（ページ数）", with_documents=False))
    add("\n領域別のテキスト行数（`layout.json` の `text_lines[].region`）：\n\n")
    add(_count_table(layout.regions, "region", with_documents=False))
    add("\n描画環境（正解と紙面の対応はこの組み合わせで決定論になる）：\n\n")
    add(_count_table(layout.renderers, "renderer（レイアウト数）", with_documents=False))
    add("\n")
    add(_count_table(layout.dpi, "PNG の解像度（レイアウト数）", with_documents=False))
    add("\n")
    add(
        _count_table(
            layout.embedded_fonts, "PDF に埋め込まれていたフォント（レイアウト数）", with_documents=False
        )
    )
    add(
        "\n**上は実測**（PDF のフォント資源の `/BaseFont` からサブセット接頭辞を外したもの）。"
        "下は描画に**登録した候補**で、style がこの中から選ぶ——"
        "候補に挙がっているだけのフォントは PDF に埋め込まれない。\n\n"
    )
    add(_count_table(layout.registered_fonts, "描画に登録したフォント（レイアウト数）", with_documents=False))

    add("\n## 9. どう作ったか\n\n")
    add(
        "1. 既定の架空約款（本体 `insurance-contracts` が生成した執筆物）を読み、"
        "章・用語・特約・既存の保険金の名称から**足せる題材**を選ぶ。\n"
        "2. パターン（§5.1）がパラメータを抽選し、**計算仕様**（`calc/spec.json`）を作る。\n"
        "3. 同じ仕様から、約款の**文言・表・算式・図**と、**正解プログラム**と、"
        "**テストケース**を展開する。文言とプログラムを別々に書かない。\n"
        "4. 本体に `derived`（番号・参照・目次・構造内の位置づけ）を再計算させ、"
        "lint・描画・verify を通す。\n"
        "5. 検証ゲート（§10）を全部通った文書だけを出力する。\n\n"
        "**生成の経路で LLM を使っていない。** 文言は文型（`realize/lexicon_ja.py`）から組んでいる。\n\n"
        "**決定論**：同じ既定の約款・同じ seed・同じ生成器の版なら、同じバイト列が出る"
        "（`CLAUDE.md` 守ること 3）。乱数はルールごとに独立で、パターンを足してもほかの"
        "ルールの出力は変わらない。seed は文書ごとに固定（§4.4 の表）。\n\n"
    )
    add(_count_table(stats.generator_versions, "生成器の版（文書数）", with_documents=False))
    add("\n")
    add(_count_table(stats.spec_versions, "計算仕様の版（文書数）", with_documents=False))

    add("\n## 10. 品質保証（検証ゲート）\n\n")
    add(
        "**すべてのゲートを通った文書だけが出力される。** 落ちたら生成側を直す（検査を外さない。"
        "`CLAUDE.md` 守ること 9）。下は `calc/manifest.json` に残った結果の集計である。\n\n"
    )
    add(
        _table(
            ["ゲート", "検査", "測った文書", "ok"],
            [[f"`{g.code}`", g.title, _n(g.documents), _n(g.ok)] for g in stats.gates],
        )
    )
    add(
        f"\n- **G7 テストの十分性**：仕様を 1 箇所だけ壊した変異体 **{_n(scale.mutants)}** に対し、"
        f"検出できなかったもの（生き残り）は **{_n(scale.mutant_survivors)}** である。\n"
        f"- **G10 発見可能性**：決定的な候補検出で拾えなかった根拠単位は "
        f"**{_n(scale.undiscoverable_units)}** 件ある（記録のみで生成は止めない）。"
        "拾えない単位の種別は下の表のとおり。\n"
    )
    if stats.undiscoverable:
        add("\n")
        add(_count_table(stats.undiscoverable, "拾えなかった単位の種別"))
    add(
        f"\n- **G9（本体の検査）**：本体の lint・ページ予算（上限内）・描画・`verify` を通している。"
        f"ページは {_range(scale.pages_min, scale.pages_max)} で、本体の上限（20 ページ）以内である。\n"
        "- **G11 決定性**：生成時の `calc/manifest.json` には結果を記録していない"
        "（上の表に G11 が無いのはそのため）。`icc verify <doc>` が同じ seed で作り直して"
        "ハッシュを突き合わせる。回帰テスト（`tests/integration/test_regression.py`）も同じことを見ている。\n"
        "- **G12 解答可能性**（基準となるシステムが H2 のヒントで合格するか）は生成時には走らせない。"
        "別に実測した記録が `docs/solvability_run.md` にある。\n"
        f"- challenge モード（わざと欠落・矛盾・異例を入れてラベルを付ける）のラベルは "
        f"**{_n(scale.challenge_labels)}** 件である。\n"
    )

    add("\n## 11. 架空性・転載しないこと\n\n")
    add(
        "- **完全架空**：会社名・商品名・ペットネーム・連絡先・URL・様式番号・人物名はすべて架空である。"
        "URL は `example.jp` などのみ、電話番号はゼロ埋めのみを使い、"
        "本体の `yakkan/lint/denylist.txt` が実在名を検出して lint で落とす。\n"
        "- **転載していない**：実在の約款から参考にしたのは**構造・要素の種類・レイアウト慣行だけ**で、"
        "文章はすべて生成している。実在約款の文は 1 文字も含まない。\n"
        "- **実在の法令は名称のみ**を引用し、**条番号は書かない**"
        "（架空の条文に実在の条番号を結びつけないため）。\n"
        "- 足した計算規定の金額・日数・割合は、種目ごとの値域（`packs/<genre>.yaml`）から"
        "抽選したもので、**実在の商品の数値ではない**。\n\n"
    )
    add(f"各文書の奥付に入れた断り書き（{_n(len(stats.disclaimers))} 種）：\n\n")
    add("\n".join(f"> {text}" for text in stats.disclaimers) + "\n")

    add("\n## 12. 正解が入っていること（汚染を避ける）\n\n")
    add(
        "このデータセットには**正解が入っている**。採点のときは、評価対象システムに渡すものを"
        "機械的に絞る（`icc export <doc> --out <先>`。`export/layout.py` が正本）。\n\n"
    )
    add(
        _table(
            ["渡してよい", "渡さない（正解）"],
            [
                [
                    "・".join(f"`{name}`" for name in stats.public_files),
                    "・".join(f"`{name}`" for name in stats.private_files),
                ]
            ],
        )
    )
    add(
        "\n- **学習データに使わないこと。** 使った時点で、このデータセットでそのモデルを"
        "評価できなくなる。\n"
        "- 汚染が疑われるときは**作り直せる**。各文書の `calc/manifest.json` に "
        "`seed` と `profile` と既定の約款のIDが入っているので、"
        "`icc generate --base <既定の約款> --seed <seed> --profile <profile>` で同じものが出る。\n"
        "- 設例（`calc/examples.jsonl`）だけは公開してよい。約款の囲みに印刷されているからである。\n"
    )

    add("\n## 13. 制限と既知の偏り\n\n")
    add(
        "**設計上の制限**（意図して外した。`DESIGN.md` §2.3・`TASK.md` §3.3）\n\n"
        "- **既定の約款にある計算規定の一義性は保証しない。** 足した規定は明示性のゲート（G3）で"
        "一義に読めることを強制しているが、既定の部分にその保証はない"
        "（`icc lint-base` で曖昧な箇所を挙げ、人の承認を得て直した実績はある）。\n"
        "- `teikan`（定款）・`jyusetsu`（重要事項説明書）は対象外である（計算規定が無い／条を持たない）。\n"
        "- SQL の正解プログラム・LLM による言い換え・スキャン風の劣化画像・縦書きは入っていない。\n"
        "- 日本語・横書きのみ。1 文書 1 言語である。\n"
        "- **検証に通った集合は「通りやすい組」に偏る。** 落ちた文書は種をずらして組み直されるので、"
        "特定の経路が黙って消えることがある。「出力に出てこない」を「作っていない」と読まない"
        "（§4.6 と `TASK.md` §5 R4）。\n"
        "- 保険数理・監督規制の妥当性は見ていない。**専門家の校閲を受けていない。**\n\n"
    )
    add(f"**母数の小さい観点**（覆っている文書が {MIN_DOCUMENTS} 本未満。この観点だけで精度を語らない）\n\n")
    if stats.thin:
        add(
            _table(
                ["分類", "観点", "文書"],
                [
                    [c.group, f"{c.name}（{c.title}）" if c.title else c.name, _n(c.documents)]
                    for c in stats.thin
                ],
            )
        )
    else:
        add(
            f"**該当なし。** 出ている観点はすべて {MIN_DOCUMENTS} 文書以上を覆っている"
            "（使われていない観点は下の表）。\n"
        )
    add("\n**宣言はあるが使っている文書が 0 の観点**（実装が検証されていない）\n\n")
    add(
        _table(
            ["分類", "観点"],
            [[c.group, f"{c.name}（{c.title}）" if c.title else c.name] for c in stats.unused],
        )
    )
    add(
        "\nこの 2 つの表は `dataset/` の実測から毎回作り直すので、"
        "データを足して観点が増えれば自動的に消える（`docs/data_card.md` §4.4）。\n"
    )

    add("\n## 14. ライセンスと配布\n\n")
    embedded = [r.name for r in layout.embedded_fonts]
    noto = [n for n in embedded if n.startswith("Noto")]
    ipa = [n for n in embedded if n.startswith("IPA")]
    add(
        "- **Hugging Face での公開を準備している**（`HITL.md` H11 で人が決定）。"
        "公開用のリポジトリは `icc package <dataset> --format hf --out <先>` が組む。"
        "**組むだけで、push もアップロードもしない**（実行は人の作業。`HITL.md` H4-b）。\n"
        "- ライセンスは、公開用リポジトリの `LICENSE` と"
        "データセットカードの `license:` タグが正本である（`icc package --license` で指定する）。"
        "**既定は仮決め**なので、公開前に人が確認する（`HITL.md` H11）。\n"
        "- 公開用リポジトリに入れないもの：`render.html`（生成の中間物。本体が配布対象外と定めている）と、"
        "描画ごとの `source.json`（同じ文書の `policy.json` とバイト単位で同一の重複）。\n"
    )
    if embedded:
        add(
            f"- **PDF にはフォントが埋め込まれている**（実測 {_n(len(embedded))} 種："
            + "、".join(f"`{n}`" for n in embedded)
            + "）。"
        )
        if noto:
            add("Noto 系は **SIL Open Font License 1.1**。")
        if ipa:
            add("IPAex 系は **IPA フォントライセンス v1.0**。")
        add(
            "**PDF を配るときはこれらの条件に従う。**"
            "公開用リポジトリでは `licenses-fonts/` に本文を同梱する"
            "（本体の `assets/fonts/` から複写する）。\n"
        )
    add(
        "- **PNG はラスタライズ済み**でフォントのデータを含まない。"
        "`policy.json` / `layout.json` / `calc/*` も同様で、フォントのライセンスは関わらない。\n"
        "- 参考にした実在の約款は**一切含まれていない**（§11）。\n"
    )

    add("\n## 15. このカードの更新\n\n")
    add(
        "```\n"
        "icc datacard update <dataset>   # 書き出す（dataset/ を測るだけ。再生成も再描画も不要）\n"
        "icc datacard check  <dataset>   # 書き換えずに古くなっていないかを見る（古ければ終了コード 1）\n"
        "make check                      # ruff + 生成器のテスト + このカードの鮮度\n"
        "```\n\n"
        "`icc` を入れていない環境では "
        "`PYTHONPATH=src python -m insurance_contracts_calculation.cli datacard update <dataset>` "
        "と書く（`README.md` の使い方と同じ）。\n\n"
        "`icc batch` は最後にカードを書き直す。`icc generate` は、出力先に**既にカードがあるときだけ**"
        "書き直す（カードの無い出力先を汚さない）。更新を忘れると `make check` が赤くなる。"
        "節の追加手順と測り方は `docs/data_card.md`。\n"
    )
    return "".join(parts)


def write_card(dataset_dir: Path, stats: DataCardStats | None = None) -> Path:
    """`dataset/data-card.md` を書き出す。"""
    dataset_dir = Path(dataset_dir)
    stats = stats if stats is not None else collect(dataset_dir)
    path = dataset_dir / CARD_NAME
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_card(stats), encoding="utf-8")
    return path


def refresh_if_present(dataset_dir: Path) -> Path | None:
    """出力先に**既にカードがあるときだけ**書き直す（`icc generate` から呼ぶ）。

    カードの無い出力先（`examples/` や使い捨ての `out/`）を汚さないためである。
    """
    dataset_dir = Path(dataset_dir)
    if not (dataset_dir / CARD_NAME).is_file():
        return None
    return write_card(dataset_dir)


def check(dataset_dir: Path) -> list[str]:
    """カードが現在の `dataset/` と合っているかを見る（**書き換えない**）。

    食い違いの説明を返す。空なら一致している。
    """
    dataset_dir = Path(dataset_dir)
    path = dataset_dir / CARD_NAME
    if not documents_in(dataset_dir):
        return [f"{dataset_dir} に文書が無い（`icc batch` で生成する）"]
    fresh = render_card(collect(dataset_dir))
    if not path.is_file():
        return [f"{path} が無い（`icc datacard update {dataset_dir}` を実行する）"]
    current = path.read_text(encoding="utf-8")
    if current == fresh:
        return []
    problems = [f"{path} が現在の {dataset_dir}/ と一致しない"]
    current_lines, fresh_lines = current.splitlines(), fresh.splitlines()
    if len(current_lines) != len(fresh_lines):
        problems.append(f"行数が違う（{len(current_lines)} → {len(fresh_lines)}）")
    diff = [
        f"{i + 1} 行目: {was.strip()[:60]} → {now.strip()[:60]}"
        for i, (was, now) in enumerate(zip(current_lines, fresh_lines, strict=False))
        if was != now
    ]
    problems += diff[:5]
    if len(diff) > 5:
        problems.append(f"（ほか {len(diff) - 5} 行）")
    return problems
