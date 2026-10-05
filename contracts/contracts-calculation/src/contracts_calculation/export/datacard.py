"""データカード（`<data>/data-card.md`）。`dataset/` の実ファイルだけを測って生成する。

仕様の正本は `docs/data_card.md`。固定文字列に統計値を焼き込まない（規則1・2）。
実行時は標準ライブラリだけを使う（規則12）。PDF の実測は re + zlib で行う。
"""

from __future__ import annotations

import json
import re
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

#: 母数が足りないと見なす閾値（それを含む文書の数）
SMALL_SAMPLE_THRESHOLD = 3

CARD_NAME = "data-card.md"

#: 埋め込みフォント名 → ライセンス（実測した名前にだけ適用する）
_FONT_LICENSE = (
    ("Noto", "SIL Open Font License 1.1"),
    ("IPAex", "IPAフォントライセンス v1.0"),
)


# --- 1 文書から測った事実 ---------------------------------------------------------


@dataclass(frozen=True)
class RuleFacts:
    rule: str
    function: str
    pattern: str
    origin: str
    binding: str | None
    n_units: int
    has_definition_units: bool
    has_explanatory_units: bool
    value_locations: tuple[str, ...]
    modalities: tuple[str, ...]
    difficulty: tuple[tuple[str, str], ...]
    has_examples: bool


@dataclass(frozen=True)
class PdfFacts:
    name: str
    size_bytes: int
    page_count: int
    embedded_fonts: tuple[str, ...]


@dataclass(frozen=True)
class DocFacts:
    content_id: str
    base_content_id: str
    calc_seed: int
    profile: str
    doctype: str
    generator_version: str
    patterns: tuple[str, ...]
    rules: tuple[RuleFacts, ...]
    n_cases: int
    case_kinds: Counter
    case_tags: Counter
    case_functions: int
    n_tasks: int
    task_kinds: Counter
    task_inputs: Counter
    task_outputs: Counter
    tasks_using_calendar: int
    tasks_with_h1: int
    tasks_with_h2: int
    gates: tuple[tuple[str, str], ...]  # (gate, ok|skip|NG)
    g11_unpicked: int
    notes: tuple[str, ...]
    challenge_type: str | None
    challenge_rule: str | None
    bindings_included: Counter
    bindings_excluded: Counter
    mutation_total: int
    mutation_detected: int
    mutation_skipped: int
    mutation_added_cases: int
    patch_ops: Counter
    added_articles: int
    added_appendices: int
    chars: int
    style_id: str | None
    layout_pages: int | None
    renderer: str | None
    page_size_mm: str | None
    registered_fonts: tuple[str, ...]
    pdf: PdfFacts | None
    calendar_years: tuple[str, ...]
    calendar_holidays: int

    @property
    def pages(self) -> int:
        if self.pdf:
            return self.pdf.page_count
        return self.layout_pages or 0

    @property
    def n_rules(self) -> int:
        return len(self.rules)


@dataclass(frozen=True)
class CardFacts:
    root: Path
    docs: tuple[DocFacts, ...]
    size_by_suffix: tuple[tuple[str, int, int], ...]  # (suffix, files, bytes)
    size_by_role: tuple[tuple[str, int, int], ...]
    oracle: dict | None
    declared_patterns: tuple[tuple[str, str], ...]  # (id, title)
    declared_bindings: tuple[str, ...]
    binding_titles: tuple[tuple[str, str], ...]
    binding_patterns: tuple[tuple[str, str], ...]
    declared_profiles: tuple[str, ...]
    warnings: tuple[str, ...] = field(default=())


# --- 測る -------------------------------------------------------------------------


def _read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    out = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def _scan_pdf(path: Path) -> PdfFacts:
    """PDF を標準ライブラリだけで実測する（オブジェクトストリームを zlib で解く）。"""
    raw = path.read_bytes()
    fonts: set[str] = set()
    pages = 0
    for m in re.finditer(rb"stream\r?\n", raw):
        start = m.end()
        end = raw.find(b"endstream", start)
        if end < 0:
            continue
        try:
            body = zlib.decompress(raw[start:end])
        except zlib.error:
            continue
        for name in re.findall(rb"/BaseFont\s*/([A-Za-z0-9+#\-]+)", body):
            # サブセット接頭辞（6 文字＋`+`）を外す
            fonts.add(name.decode("ascii").split("+")[-1])
        pages += len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", body))
    # 非圧縮の PDF にも備える
    for name in re.findall(rb"/BaseFont\s*/([A-Za-z0-9+#\-]+)", raw):
        fonts.add(name.decode("ascii").split("+")[-1])
    if pages == 0:
        pages = len(re.findall(rb"/Type\s*/Page(?![sA-Za-z])", raw))
    return PdfFacts(path.name, len(raw), pages, tuple(sorted(fonts)))


def _collect_doc(doc_dir: Path) -> DocFacts:
    calc = doc_dir / "calc"
    manifest = _read_json(calc / "manifest.json")
    answer_key = _read_json(calc / "answer_key.json")
    spec = _read_json(calc / "spec.json")
    examples_of = {r["id"]: bool(r.get("examples")) for r in spec.get("rules", [])}

    rules = tuple(
        RuleFacts(
            rule=a["rule"],
            function=a["function"],
            pattern=a["pattern"],
            origin=a["origin"],
            binding=a.get("binding"),
            n_units=len(a.get("units", [])),
            has_definition_units=bool(a.get("definition_units")),
            has_explanatory_units=bool(a.get("explanatory_units")),
            value_locations=tuple(sorted(a.get("value_locations", {}).values())),
            modalities=tuple(a.get("modalities", [])),
            difficulty=tuple(sorted((k, str(v)) for k, v in a.get("difficulty", {}).items())),
            has_examples=examples_of.get(a["rule"], False),
        )
        for a in answer_key
    )

    cases = _read_jsonl(calc / "cases.jsonl")
    case_kinds: Counter = Counter(c["kind"] for c in cases)
    case_tags: Counter = Counter(t for c in cases for t in c.get("tags", []))

    tasks = _read_jsonl(calc / "tasks.jsonl")
    task_inputs: Counter = Counter(
        (i["type"], i.get("origin", "?")) for t in tasks for i in t.get("inputs", [])
    )

    gates = tuple(
        (g["gate"], "skip" if g["skipped"] else ("ok" if g["passed"] else "NG"))
        for g in manifest.get("gates", [])
    )
    g11_unpicked = 0
    for g in manifest.get("gates", []):
        if g["gate"] == "G11" and g["detail"].startswith("拾えない単位"):
            g11_unpicked = len(g["detail"].split(": ", 1)[1].split(", "))

    mutation = manifest.get("mutation", {})
    patch_ops: Counter = Counter()
    added_articles = added_appendices = 0
    for op in _read_json(calc / "patch.json").get("ops", []):
        patch_ops[op["op"]] += 1
        if op["op"] == "add_node":
            if op.get("kind") == "article":
                added_articles += 1
            elif op.get("kind") == "appendix":
                added_appendices += 1

    contract = _read_json(doc_dir / "contract.json")
    chars = sum(
        len(v.get("with_label", "")) for v in contract.get("derived", {}).get("plain_text", {}).values()
    )

    style_id = layout_pages = renderer = page_size_mm = None
    registered_fonts: tuple[str, ...] = ()
    for layout_path in sorted(doc_dir.glob("_render/*/layout.json")):
        layout = _read_json(layout_path)
        style_id, layout_pages = layout.get("style_id"), layout.get("page_count")
        rend = layout.get("renderer") or {}
        renderer = f"{rend.get('name', '?')} {rend.get('version', '?')}".strip()
        registered_fonts = tuple(rend.get("fonts", []))
        size = layout.get("page_size_pt")
        if size and len(size) == 2:
            page_size_mm = f"{round(size[0])}×{round(size[1])} pt（{round(size[0] * 25.4 / 72)}×{round(size[1] * 25.4 / 72)} mm）"
        break

    pdfs = sorted(doc_dir.glob("*.pdf"))
    pdf = _scan_pdf(pdfs[0]) if pdfs else None

    calendar = _read_json(calc / "calendar.json")
    years = tuple(sorted(calendar.get("years", {})))
    n_holidays = sum(len(v) for v in calendar.get("years", {}).values())

    challenge = manifest.get("challenge") or {}
    return DocFacts(
        content_id=manifest["content_id"],
        base_content_id=manifest["base_content_id"],
        calc_seed=manifest["calc_seed"],
        profile=manifest.get("profile", "?"),
        doctype=spec.get("document", {}).get("doctype", contract.get("doctype") or "?"),
        generator_version=manifest.get("generator_version", "?"),
        patterns=tuple(manifest.get("patterns", [])),
        rules=rules,
        n_cases=len(cases),
        case_kinds=case_kinds,
        case_tags=case_tags,
        case_functions=len({c["function"] for c in cases}),
        n_tasks=len(tasks),
        task_kinds=Counter(t["kind"] for t in tasks),
        task_inputs=task_inputs,
        task_outputs=Counter(t["output"]["type"] for t in tasks),
        tasks_using_calendar=sum(1 for t in tasks if t.get("uses_calendar")),
        tasks_with_h1=sum(1 for t in tasks if t.get("hints", {}).get("H1")),
        tasks_with_h2=sum(1 for t in tasks if t.get("hints", {}).get("H2")),
        gates=gates,
        g11_unpicked=g11_unpicked,
        notes=tuple(manifest.get("notes", [])),
        challenge_type=challenge.get("type"),
        challenge_rule=challenge.get("rule"),
        bindings_included=Counter(b["binding"] for b in manifest.get("bindings", {}).get("included", [])),
        bindings_excluded=Counter(e["binding"] for e in manifest.get("bindings", {}).get("excluded", [])),
        mutation_total=sum(m["total"] for m in mutation.values()),
        mutation_detected=sum(m["detected"] for m in mutation.values()),
        mutation_skipped=sum(len(m["skipped"]) for m in mutation.values()),
        mutation_added_cases=sum(m["added_cases"] for m in mutation.values()),
        patch_ops=patch_ops,
        added_articles=added_articles,
        added_appendices=added_appendices,
        chars=chars,
        style_id=style_id,
        layout_pages=layout_pages,
        renderer=renderer,
        page_size_mm=page_size_mm,
        registered_fonts=registered_fonts,
        pdf=pdf,
        calendar_years=years,
        calendar_holidays=n_holidays,
    )


def _role_of(rel_parts: tuple[str, ...]) -> str:
    if rel_parts[0] == "_work":
        return "`_work/`（パッチ済みの content。再現とデバッグ用）"
    if "_render" in rel_parts:
        return "`_render/`（本体 render の出力。デバッグ用）"
    if len(rel_parts) == 1:
        return "データセット全体のファイル（README・オラクル検査の結果）"
    if rel_parts[1] == "calc":
        return "`calc/`（仕様・正解プログラム・ケース・テスト）"
    return "`contract.json` と PDF（評価対象に渡すもの）"


def _collect_sizes(root: Path) -> tuple[tuple[tuple[str, int, int], ...], tuple[tuple[str, int, int], ...]]:
    """拡張子別・役割別の（ファイル数, バイト数）。カード自身とドットファイルは数えない。"""
    by_suffix: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    by_role: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        parts = rel.parts
        if any(p.startswith(".") or p == "__pycache__" for p in parts):
            continue
        if str(rel) == CARD_NAME:
            continue
        size = path.stat().st_size
        suffix = path.suffix or "(拡張子なし)"
        by_suffix[suffix][0] += 1
        by_suffix[suffix][1] += size
        role = _role_of(parts)
        by_role[role][0] += 1
        by_role[role][1] += size
    suffixes = tuple(sorted(((k, v[0], v[1]) for k, v in by_suffix.items()), key=lambda r: (-r[2], r[0])))
    roles = tuple(sorted(((k, v[0], v[1]) for k, v in by_role.items()), key=lambda r: (-r[2], r[0])))
    return suffixes, roles


def collect(root: Path) -> CardFacts:
    root = Path(root)
    doc_dirs = sorted(p for p in root.iterdir() if p.is_dir() and (p / "calc" / "manifest.json").is_file())
    if not doc_dirs:
        raise FileNotFoundError(f"{root} に計算パックが無い")
    docs = tuple(_collect_doc(p) for p in doc_dirs)

    warnings: list[str] = []
    mismatch = [d.content_id for d in docs if d.pdf and d.layout_pages and d.pdf.page_count != d.layout_pages]
    if mismatch:
        warnings.append(
            "PDF の実測ページ数と `_render/*/layout.json` の `page_count` が食い違う文書がある: "
            + "、".join(mismatch)
        )
    no_pdf = [d.content_id for d in docs if d.pdf is None]
    if no_pdf:
        warnings.append(
            f"PDF が無い文書が {len(no_pdf)} 件ある（`--no-render` で生成したもの）: " + "、".join(no_pdf)
        )
    no_layout = [d.content_id for d in docs if d.layout_pages is None]
    if no_layout:
        warnings.append(
            f"`_render/*/layout.json` が無い文書が {len(no_layout)} 件あり、ページ数の突合をしていない"
        )
    versions = sorted({d.generator_version for d in docs})
    if len(versions) > 1:
        warnings.append("生成器の版が揃っていない（作り直しが要る）: " + "、".join(versions))

    oracle_path = root / "oracle_report.json"
    oracle = _read_json(oracle_path) if oracle_path.is_file() else None

    from ..bindings.engine import BINDING_PATTERNS, BINDING_TITLES, DECLARED_BINDINGS
    from ..config import PROFILES
    from ..patterns.registry import all_patterns

    by_suffix, by_role = _collect_sizes(root)
    return CardFacts(
        root=root,
        docs=docs,
        size_by_suffix=by_suffix,
        size_by_role=by_role,
        oracle=oracle,
        declared_patterns=tuple((p.id, p.title) for p in all_patterns()),
        declared_bindings=tuple(sorted(DECLARED_BINDINGS)),
        binding_titles=tuple(sorted(BINDING_TITLES.items())),
        binding_patterns=tuple(sorted(BINDING_PATTERNS.items())),
        declared_profiles=tuple(sorted(PROFILES)),
        warnings=tuple(warnings),
    )


# --- 整形のヘルパ ------------------------------------------------------------------


def _n(value: int) -> str:
    return f"{value:,}"


def _size(num_bytes: int) -> str:
    mib = num_bytes / 1048576
    if mib < 0.05:
        return f"{num_bytes / 1024:.0f} KiB"
    return f"{mib:.1f} MiB"


def _table(header: list[str], rows: list[list[str]]) -> list[str]:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join(["---"] * len(header)) + "|"]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    out.append("")
    return out


def _freq_rows(rules: Counter, docs: Counter) -> list[list[str]]:
    """件数の多い順。同数はキー順（決定論）。"""
    return [
        [key, _n(rules[key]), _n(docs.get(key, 0))]
        for key in sorted(rules, key=lambda k: (-rules[k], str(k)))
    ]


def _range(values: list[int]) -> str:
    if not values:
        return "—"
    lo, hi = min(values), max(values)
    return str(lo) if lo == hi else f"{lo}–{hi}"


_NOTE_LABELS = (
    ("値の表記の重複を解消できず", "値の表記が重複し、そのパターンを見送った"),
    ("適用できるパターンが下限に満たない", "適用できるパターンがプロファイルの下限に満たなかった"),
    ("既定 style の描画が", "既定 style の描画が破綻し、別 style へ決定的にフォールバックした"),
    ("challenge:", "challenge の対象にできるルールが無かった"),
    ("名称衝突を合成名へ置換", "既知の実在名称との衝突を合成名へ置換した"),
)


def _note_label(note: str) -> str:
    for needle, label in _NOTE_LABELS:
        if needle in note:
            return label
    return re.sub(r"\d+", "N", note.split("（")[0])[:80]


# --- 集計 -------------------------------------------------------------------------


@dataclass(frozen=True)
class Observation:
    """母数の検査にかける「観点」。"""

    group: str
    name: str
    docs: int
    rules: int


def _observations(facts: CardFacts) -> list[Observation]:
    docs = facts.docs
    out: list[Observation] = []

    def add(group: str, counter_rules: Counter, counter_docs: Counter) -> None:
        for key in sorted(counter_docs, key=lambda k: (counter_docs[k], str(k))):
            out.append(Observation(group, str(key), counter_docs[key], counter_rules.get(key, 0)))

    pat_r: Counter = Counter()
    pat_d: Counter = Counter()
    diff_r: Counter = Counter()
    diff_d: Counter = Counter()
    mod_r: Counter = Counter()
    mod_d: Counter = Counter()
    vloc_r: Counter = Counter()
    vloc_d: Counter = Counter()
    kind_r: Counter = Counter()
    kind_d: Counter = Counter()
    decl_r: Counter = Counter()
    decl_d: Counter = Counter()
    for doc in docs:
        for key in {r.pattern for r in doc.rules}:
            pat_d[key] += 1
        for r in doc.rules:
            pat_r[r.pattern] += 1
            for axis, value in r.difficulty:
                diff_r[f"{axis}: {value}"] += 1
            for m in r.modalities:
                mod_r[m] += 1
            for v in r.value_locations:
                vloc_r[v] += 1
        for key in {f"{a}: {v}" for r in doc.rules for a, v in r.difficulty}:
            diff_d[key] += 1
        for key in {m for r in doc.rules for m in r.modalities}:
            mod_d[key] += 1
        for key in {v for r in doc.rules for v in r.value_locations}:
            vloc_d[key] += 1
        for key, cnt in doc.case_kinds.items():
            kind_r[key] += cnt
            kind_d[key] += 1
        for label in (
            f"doctype: {doc.doctype}",
            f"プロファイル: {doc.profile}",
            f"style: {doc.style_id or '（未描画）'}",
            f"calc_seed: {doc.calc_seed}",
        ):
            decl_d[label] += 1
            decl_r[label] += doc.n_rules
    add("パターン", pat_r, pat_d)
    add("難易度の軸", diff_r, diff_d)
    add("表現手段", mod_r, mod_d)
    add("値の在り処", vloc_r, vloc_d)
    add("テストケースの種別", kind_r, kind_d)
    add("宣言", decl_r, decl_d)
    return out


# --- 集計（カード全体で 1 回だけ数える） -------------------------------------------


@dataclass(frozen=True)
class Agg:
    n_docs: int
    all_rules: tuple[RuleFacts, ...]
    bases: Counter
    doctypes: Counter
    profiles: Counter
    seeds: Counter
    styles: Counter
    versions: tuple[str, ...]
    pages: tuple[int, ...]
    n_cases: int
    n_tasks: int
    origins: Counter
    task_kinds: Counter
    task_inputs: Counter
    task_outputs: Counter
    case_kinds: Counter
    case_tags: Counter
    patch_ops: Counter
    notes: Counter
    gate_status: dict[str, Counter]
    bind_inc: Counter
    bind_exc: Counter
    pat_rules: Counter
    pat_docs: Counter
    diff_rules: Counter
    diff_docs: Counter
    mod_rules: Counter
    mod_docs: Counter
    vloc_rules: Counter
    vloc_docs: Counter
    embedded_fonts: Counter
    total_bytes: int
    total_files: int
    challenge_types: Counter
    observations: tuple[Observation, ...]


def aggregate(facts: CardFacts) -> Agg:
    docs = facts.docs
    counters: dict[str, Counter] = {
        k: Counter()
        for k in (
            "task_kinds",
            "task_inputs",
            "task_outputs",
            "case_kinds",
            "case_tags",
            "patch_ops",
            "notes",
            "bind_inc",
            "bind_exc",
            "pat_rules",
            "pat_docs",
            "diff_rules",
            "diff_docs",
            "mod_rules",
            "mod_docs",
            "vloc_rules",
            "vloc_docs",
            "embedded_fonts",
            "challenge_types",
        )
    }
    gate_status: dict[str, Counter] = defaultdict(Counter)
    for d in docs:
        counters["task_kinds"] += d.task_kinds
        counters["task_inputs"] += d.task_inputs
        counters["task_outputs"] += d.task_outputs
        counters["case_kinds"] += d.case_kinds
        counters["case_tags"] += d.case_tags
        counters["patch_ops"] += d.patch_ops
        counters["bind_inc"] += d.bindings_included
        counters["bind_exc"] += d.bindings_excluded
        for note in d.notes:
            counters["notes"][_note_label(note)] += 1
        for gate, status in d.gates:
            gate_status[gate][status] += 1
        if d.challenge_type:
            counters["challenge_types"][d.challenge_type] += 1
        if d.pdf:
            for font in d.pdf.embedded_fonts:
                counters["embedded_fonts"][font] += 1
        for r in d.rules:
            counters["pat_rules"][r.pattern] += 1
            for axis, value in r.difficulty:
                counters["diff_rules"][f"{axis}: {value}"] += 1
            for m in r.modalities:
                counters["mod_rules"][m] += 1
            for v in r.value_locations:
                counters["vloc_rules"][v] += 1
        for key in {r.pattern for r in d.rules}:
            counters["pat_docs"][key] += 1
        for key in {f"{a}: {v}" for r in d.rules for a, v in r.difficulty}:
            counters["diff_docs"][key] += 1
        for key in {m for r in d.rules for m in r.modalities}:
            counters["mod_docs"][key] += 1
        for key in {v for r in d.rules for v in r.value_locations}:
            counters["vloc_docs"][key] += 1
    return Agg(
        n_docs=len(docs),
        all_rules=tuple(r for d in docs for r in d.rules),
        bases=Counter(d.base_content_id for d in docs),
        doctypes=Counter(d.doctype for d in docs),
        profiles=Counter(d.profile for d in docs),
        seeds=Counter(d.calc_seed for d in docs),
        styles=Counter(d.style_id for d in docs if d.style_id),
        versions=tuple(sorted({d.generator_version for d in docs})),
        pages=tuple(d.pages for d in docs),
        n_cases=sum(d.n_cases for d in docs),
        n_tasks=sum(d.n_tasks for d in docs),
        origins=Counter(r.origin for d in docs for r in d.rules),
        gate_status=dict(gate_status),
        total_bytes=sum(b for _, _, b in facts.size_by_suffix),
        total_files=sum(f for _, f, _ in facts.size_by_suffix),
        observations=tuple(_observations(facts)),
        **counters,  # type: ignore[arg-type]
    )


# --- 書く（節ごと） ----------------------------------------------------------------


def _sec_overview(facts: CardFacts, g: Agg) -> list[str]:
    L = [
        "# データカード — contracts-calculation 計算条項データセット",
        "",
        (
            "**このファイルは `contracts-calc datacard update` が生成する。手で編集しない**"
            "（CLAUDE.md 規則2）。仕様は `docs/data_card.md`、"
            f"パックの読み方と渡し方は `{facts.root.name}/README.md`。"
        ),
        "",
        "数値はすべてこのディレクトリの実ファイルを測った結果で、生成し直すたびに更新される。",
        "",
        "## 1. 概要",
        "",
        (
            f"計算や判定を要する条項を持つ日本語ビジネス契約書 **{_n(g.n_docs)} 文書**（PDF つき）と、"
            f"その条項の**計算仕様・正解プログラム・テストケース**を対にした合成データセットである。"
            f"既定の契約書（base content）**{_n(len(g.bases))} 本**・契約書種別（doctype）**{_n(len(g.doctypes))} 種**に、"
            f"難易度プロファイル **{_n(len(g.profiles))} 種** × 乱数 calc_seed **{_n(len(g.seeds))} 種**で条項を"
            f"追加・紐づけし、ルール **{_n(len(g.all_rules))} 件**（評価用の関数 **{_n(g.n_tasks)} 件**）と"
            f"テストケース **{_n(g.n_cases)} 件**を収める。"
        ),
        "",
        (
            "- **計算仕様が唯一の正**である。条項の文言・正解プログラム（Python）・テストの期待値は、"
            "すべて同じ仕様から機械的に作られる（§8）。文言とプログラムを別々に書く経路は無い。"
        ),
        (
            "- 当事者・会社名・金額・物件はすべて**架空**で、法的効力を持たない（§9）。"
            "条項は計算能力の評価のために生成したダミーであり、法律専門家の校閲を受けていない。"
        ),
    ]
    oracle_line = (
        f"正解プログラムを提出とみなしたオラクル検査は **{_n(facts.oracle['functions_passed'])} / "
        f"{_n(facts.oracle['functions_total'])} 関数**が合格である。"
        if facts.oracle
        else "オラクル検査の結果（`oracle_report.json`）はこのディレクトリに無い。"
    )
    L += [
        f"- 全 {_n(g.n_docs)} 文書が検証ゲート G1〜G11 と本体の lint / build / render を通っている（§10）。"
        + oracle_line,
        f"- 生成器は contracts-calculation **{'、'.join(g.versions)}**。",
        "",
    ]
    if facts.warnings:
        L.append("> **測定時の注意**（黙って片方の数字を載せないための警告）")
        L += [f"> - {w}" for w in facts.warnings]
        L.append("")
    return L


def _sec_usage() -> list[str]:
    return [
        "## 2. 想定する用途／想定しない用途",
        "",
        "**想定する用途**（これに合わせて正解を設計した。`DESIGN.md` §13）",
        "",
        (
            "1. **条項 → 実装**：契約書の条項を読んで、金額・期日・可否を算出する関数を実装する能力の評価"
            "（impl トラック）。"
        ),
        (
            "2. **条項 → 仕様の発見**：どのルールが・どの条に・どの値で書かれているかを見つける能力の評価"
            "（discovery トラック）。"
        ),
        "3. **日付と暦**：起算日・応当日・期間の満了・営業日への繰上げ／繰下げの扱いの評価（§5.8）。",
        "4. **不明値の扱い**：入力が `None`（不明）のとき結果を確定できるかどうかの三値論理の評価（§5.5）。",
        (
            "5. **読み取りと計算の切り分け**：ヒント水準 H0〜H2 を切り替えて、"
            "読み取りで失敗したのか計算で失敗したのかを分ける（§7）。"
        ),
        "6. **紙面からの端から端まで**：PDF の版面から値を読み、条項の規定どおりに計算する一貫評価（§6）。",
        "",
        "**想定しない用途**",
        "",
        "- **実務の契約書としての利用・法的な参照。** 条項は評価用のダミーである。",
        "- 実在のひな型・標準契約書の再現（base となる契約書も、構造だけを参考にした合成物である）。",
        "- 言語モデルの事前学習コーパス（規模が小さく、題材と文型が意図的に偏っている）。",
        "- スキャン画像・手書き・印影を含む劣化画像の評価（§11）。",
        "- 条項そのものの妥当性・網羅性・法的解釈の評価（§11）。",
        "",
    ]


def _sec_scale(facts: CardFacts, g: Agg) -> list[str]:
    docs = facts.docs
    rows = [
        ("文書（計算パック）", _n(g.n_docs)),
        ("既定の契約書（base content）", _n(len(g.bases))),
        ("doctype（契約書種別）", _n(len(g.doctypes))),
        ("難易度プロファイル", f"{_n(len(g.profiles))}（宣言 {_n(len(facts.declared_profiles))}）"),
        ("calc_seed", f"{_n(len(g.seeds))}（{'、'.join(str(s) for s in sorted(g.seeds))}）"),
        ("ページ（PDF の実測の合計）", _n(sum(g.pages))),
        ("1 文書のページ数", _range(list(g.pages))),
        ("契約書本文の文字数（`derived.plain_text`）", _n(sum(d.chars for d in docs))),
        ("ルール（計算・判定の規定）", _n(len(g.all_rules))),
        ("　うち条項を追加したもの（`origin: added`）", _n(g.origins.get("added", 0))),
        ("　うち既定の条項に紐づけたもの（`origin: bound`）", _n(g.origins.get("bound", 0))),
        ("1 文書のルール数", _range([d.n_rules for d in docs])),
        ("評価用の関数（タスクカード `calc/tasks.jsonl`）", _n(g.n_tasks)),
        ("　うち計算（`calculation`）", _n(g.task_kinds.get("calculation", 0))),
        ("　うち判定（`determination`）", _n(g.task_kinds.get("determination", 0))),
        ("テストケース（`calc/cases.jsonl`）", _n(g.n_cases)),
        ("1 文書のテストケース数", _range([d.n_cases for d in docs])),
        (
            "パターン（出現したもの）",
            (
                f"{_n(len(g.pat_docs))}（宣言 {_n(len(facts.declared_patterns))} ＋ 付与 "
                f"{_n(len(facts.declared_bindings))}）"
            ),
        ),
        ("追加した条", _n(sum(d.added_articles for d in docs))),
        ("追加した別紙", _n(sum(d.added_appendices for d in docs))),
        ("追加した定数（`meta.constants`）", _n(g.patch_ops.get("add_constant", 0))),
        ("頭書へ分離した値", _n(g.patch_ops.get("add_header_row", 0))),
        ("紙面に計算例を載せた文書", _n(sum(1 for d in docs if any(r.has_examples for r in d.rules)))),
        ("容量", f"{_size(g.total_bytes)} / {_n(g.total_files)} ファイル"),
    ]
    L = ["## 3. 規模（実測）", ""]
    L += _table(["項目", "実測値"], [[k, v] for k, v in rows])
    L += ["容量の内訳（拡張子別）：", ""]
    L += _table(
        ["種類", "ファイル数", "容量"],
        [[s, _n(f), _size(b)] for s, f, b in facts.size_by_suffix],
    )
    L += ["容量の内訳（役割別）：", ""]
    L += _table(
        ["役割", "ファイル数", "容量"],
        [[r, _n(f), _size(b)] for r, f, b in facts.size_by_role],
    )
    L += [
        (
            f"（`{CARD_NAME}` 自身とドットファイル・`__pycache__` は数えていない。`docs/data_card.md` §4.1。"
            "評価対象システムに渡すのは `contract.json` と PDF と `calc/` の一部だけで、"
            f"`_render/` と `_work/` は再現・デバッグ用である＝`{facts.root.name}/README.md`）"
        ),
        "",
    ]
    return L


def _sec_breakdown(facts: CardFacts, g: Agg) -> list[str]:
    docs = facts.docs
    L = ["## 4. 内訳", "", "### 4.1 難易度プロファイル別", ""]
    rows = []
    for name in sorted(g.profiles):
        sel = [d for d in docs if d.profile == name]
        rules = [r for d in sel for r in d.rules]
        rows.append(
            [
                f"`{name}`",
                _n(len(sel)),
                _n(len(rules)),
                f"{len(rules) / len(sel):.1f}",
                _range([d.n_rules for d in sel]),
                _n(sum(d.n_cases for d in sel)),
                _n(sum(1 for d in sel if d.challenge_type)),
            ]
        )
    L += _table(
        ["プロファイル", "文書", "ルール", "1 文書平均", "1 文書の幅", "ケース", "難所つき"],
        rows,
    )
    L += [
        (
            "プロファイルは「どの表現手段をどの割合で使うか」の宣言である（`config.py`）。"
            "`basic` は本文だけ・`standard`/`hard` は別紙・頭書・分散・計算例・図を混ぜ、"
            "`challenge` はラベル付きの難所を 1 件入れようとする（入れられなかった文書は §11 に出る）。"
        ),
        "",
        "### 4.2 doctype 別",
        "",
    ]
    rows = []
    for name in sorted(g.doctypes):
        sel = [d for d in docs if d.doctype == name]
        rules = [r for d in sel for r in d.rules]
        rows.append(
            [
                f"`{name}`",
                _n(len({d.base_content_id for d in sel})),
                _n(len(sel)),
                _range([d.pages for d in sel]),
                _n(len(rules)),
                _n(sum(d.n_cases for d in sel)),
                _n(sum(d.chars for d in sel)),
            ]
        )
    L += _table(["doctype", "base", "文書", "ページ", "ルール", "ケース", "本文字数"], rows)
    L += ["### 4.3 既定の契約書（base content）別", ""]
    rows = []
    for name in sorted(g.bases):
        sel = [d for d in docs if d.base_content_id == name]
        rows.append(
            [
                f"`{name}`",
                f"`{sel[0].doctype}`",
                _n(len(sel)),
                "、".join(str(s) for s in sorted({d.calc_seed for d in sel})),
                "、".join(sorted({d.profile for d in sel})),
                _n(sum(d.n_rules for d in sel)),
            ]
        )
    L += _table(["base", "doctype", "文書", "calc_seed", "プロファイル", "ルール"], rows)
    L += [
        (
            "新しい `content_id` は `base + 100 × calc_seed` で払い出す（`docs/decisions.md`）。"
            "**同じ base から作った文書は本文を共有する**ので、独立な契約書としては数えられない（§11）。"
        ),
        "",
        "### 4.4 文書の全件",
        "",
    ]
    rows = []
    for d in docs:
        rows.append(
            [
                f"`{d.content_id}`",
                f"`{d.base_content_id}`",
                f"`{d.doctype}`",
                d.profile,
                str(d.calc_seed),
                f"`{d.style_id}`" if d.style_id else "—",
                _n(d.pages),
                _n(d.n_rules),
                f"{_n(d.task_kinds.get('calculation', 0))}/{_n(d.task_kinds.get('determination', 0))}",
                _n(d.n_cases),
                "・".join(d.patterns) or "—",
                f"{d.challenge_rule}（{d.challenge_type}）" if d.challenge_type else "—",
            ]
        )
    L += _table(
        [
            "content_id",
            "base",
            "doctype",
            "プロファイル",
            "seed",
            "style",
            "ページ",
            "ルール",
            "計算/判定",
            "ケース",
            "追加パターン",
            "難所",
        ],
        rows,
    )
    L += [
        (
            "「追加パターン」は条項を**足した**パターンだけである。既定の条項に**紐づけた**ルール"
            "（`B-` で始まるもの）は §5.7 を見る。"
        ),
        "",
        "### 4.5 パターン別",
        "",
    ]
    rows = []
    for pid, title in facts.declared_patterns:
        if pid in g.pat_docs:
            rows.append([f"`{pid}`", title, _n(g.pat_docs[pid]), _n(g.pat_rules[pid])])
    titles = dict(facts.binding_titles)
    for pid, binding in facts.binding_patterns:
        if pid in g.pat_docs:
            rows.append(
                [
                    f"`{pid}`",
                    f"{titles.get(binding, binding)}（付与モード。§5.7）",
                    _n(g.pat_docs[pid]),
                    _n(g.pat_rules[pid]),
                ]
            )
    L += _table(["パターン", "題名", "文書", "ルール"], rows)
    unused = [f"`{pid}`（{title}）" for pid, title in facts.declared_patterns if pid not in g.pat_docs]
    L += [
        (
            "宣言したパターンのうち、このデータセットに出ていないものは無い。"
            if not unused
            else "宣言したが**このデータセットに出ていない**パターン：" + "、".join(unused) + "（§11）。"
        ),
        "",
    ]
    return L


_ORIGIN_JA = {
    "order": "個別契約・注文書・仕様書に定める値",
    "fact": "起きた事実",
    "notice": "当事者の通知や意思表示の有無と日付",
    "judgment": "評価を要する事項",
    "external": "法令・指標・暦",
}

#: テストケースのタグ → 読者向けの分類（接頭辞で引く。DESIGN.md §10.3・§13.2）
_TAG_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("日付：月末（28・30・31 日）", ("date:month_end",)),
    ("日付：うるう年の 2 月 29 日", ("date:leap_feb_29",)),
    ("日付：年末年始", ("date:year_end",)),
    ("日付：土曜・金曜", ("date:saturday", "date:friday")),
    ("日付：期間の境目（N−1・N・N+1）", ("date:delta",)),
    ("祝日を入力で与えたもの", ("holiday",)),
    ("不明値（入力が `None`）", ("none:",)),
    ("しきい値の前後", ("anchor:", "list_anchor:")),
    ("入力が互いに等しいとき", ("equal:",)),
    ("真偽の組合せ", ("bool_combo", "bools_true")),
    ("変異を検出するために足したもの", ("kills:",)),
    ("パターン固有の勘所", ("hint",)),
    ("その他（空・合計・下限側）", ("empty", "sum", "others_lo")),
)


def _sec_answers(facts: CardFacts, g: Agg) -> list[str]:
    docs = facts.docs
    L = ["## 5. 正解の中身", "", "### 5.1 ルールの種別と出どころ", ""]
    kind_docs = Counter(k for d in docs for k in d.task_kinds)
    L += _table(
        ["種別", "ルール", "この種別を持つ文書"],
        [
            [
                "`calculation`（金額・期日を算出する）",
                _n(g.task_kinds.get("calculation", 0)),
                _n(kind_docs.get("calculation", 0)),
            ],
            [
                "`determination`（可否・該当性を判定する）",
                _n(g.task_kinds.get("determination", 0)),
                _n(kind_docs.get("determination", 0)),
            ],
        ],
    )
    origin_docs = Counter(o for d in docs for o in {r.origin for r in d.rules})
    L += _table(
        ["出どころ", "ルール", "この出どころを持つ文書"],
        [
            [
                "`added`（条項を足して、その計算仕様を付ける）",
                _n(g.origins.get("added", 0)),
                _n(origin_docs.get("added", 0)),
            ],
            [
                "`bound`（既定の条項に仕様を紐づける。文言は変えない）",
                _n(g.origins.get("bound", 0)),
                _n(origin_docs.get("bound", 0)),
            ],
        ],
    )
    L += ["### 5.2 関数の入力と出力", "", "出力の型："]
    L.append("")
    out_docs = Counter(t for d in docs for t in d.task_outputs)
    L += _table(
        ["型", "関数", "この型を持つ文書"],
        [
            [f"`{k}`", _n(v), _n(out_docs.get(k, 0))]
            for k, v in sorted(g.task_outputs.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    )
    L += ["入力の型 × 出どころ（`DESIGN.md` §12.4）：", ""]
    L += _table(
        ["型", "出どころ", "意味", "入力の件数"],
        [
            [f"`{t}`", f"`{o}`", _ORIGIN_JA.get(o, "—"), _n(v)]
            for (t, o), v in sorted(g.task_inputs.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    )
    cal_funcs = sum(d.tasks_using_calendar for d in docs)
    cal_docs = sum(1 for d in docs if d.tasks_using_calendar)
    L += [
        (
            f"**暦を受け取る関数は {_n(cal_funcs)} 件**（{_n(cal_docs)} 文書）。この関数だけが `holidays`"
            "（`frozenset[date]`）を引数に取り、§5.3 の `calendar: business_days` の件数と一致する"
            "——月・日だけで決まる期限は暦を要しない。祝日をプログラムに書かず、入力で渡す（§5.8）。"
        ),
        "",
        (
            "契約書（本文・頭書・別紙）に書かれた値は入力ではなく**定数**で、"
            f"合計 {_n(g.patch_ops.get('add_constant', 0))} 件を追加している（§3）。"
        ),
        "",
        "### 5.3 難易度の軸",
        "",
        (
            "ルールごとに「何が難しいか」を軸で持つ（`answer_key.json` の `difficulty`）。"
            "**軸の値ごとに、何件のルールが・何文書に出ているか**を測った結果が次である。"
        ),
        "",
        (
            "軸の意味：`value_location`＝値が本文・本文の表・別紙・個別契約のどこにあるか／"
            "`depth`＝計算の段数／`calendar`＝暦の扱い（日・月・営業日）／"
            "`condition`＝条件の組み立て（2 経路・列挙と経路・定義と除外・バスケット・段階）／"
            "`unknown`＝不明値が結果を左右する／`scatter`＝定義が別の条に分かれている単位の数／"
            "`modality`＝規範が図だけにある／`priority`＝本文と別紙の優先順位で解く／"
            "`distractor`＝使ってはいけない値が紙面にある／`origin`＝既定の条項への紐づけ。"
        ),
        "",
    ]
    axes: dict[str, list[tuple[str, int, int]]] = defaultdict(list)
    for key in sorted(g.diff_rules, key=lambda k: (k.split(": ")[0], -g.diff_rules[k], k)):
        axis, value = key.split(": ", 1)
        axes[axis].append((value, g.diff_rules[key], g.diff_docs.get(key, 0)))
    rows = []
    for axis in sorted(axes):
        for value, n_rules, n_docs_ in axes[axis]:
            rows.append([f"`{axis}`", f"`{value}`", _n(n_rules), _n(n_docs_)])
    L += _table(["軸", "値", "ルール", "文書"], rows)
    L += ["### 5.4 表現手段と値の在り処", ""]
    L += _table(
        ["表現手段（`modalities`）", "ルール", "文書"],
        _freq_rows(g.mod_rules, g.mod_docs),
    )
    L += ["値がどこに書かれているか（`value_locations`。定数ごとに数える）：", ""]
    L += _table(["在り処", "定数", "文書"], _freq_rows(g.vloc_rules, g.vloc_docs))
    n_def = sum(1 for r in g.all_rules if r.has_definition_units)
    n_exp = sum(1 for r in g.all_rules if r.has_explanatory_units)
    n_ex = sum(1 for r in g.all_rules if r.has_examples)
    units = [r.n_units for r in g.all_rules]
    L += [
        "",
        "規範と説明の切り分け（読み取りの罠になる）：",
        "",
        _rows(
            ["観点", "件数", "意味"],
            [
                [
                    "定義が別の条に分散しているルール",
                    _n(n_def),
                    "「営業日」の定義を独立の条に置き、ルールはそこを指す（`definition_units`）",
                ],
                [
                    "説明だけの要素を伴うルール",
                    _n(n_exp),
                    "図や計算例の箱。**規範ではない**ので、計算の根拠にしてはいけない（`explanatory_units`）",
                ],
                ["紙面に計算例があるルール", _n(n_ex), "設例は仕様から計算して載せ、G5 で検算している"],
                [
                    "1 ルールの根拠単位の数",
                    _range(units),
                    "条・項・表のセルなど、仕様の値の出どころ（`units`）",
                ],
            ],
        ),
    ]
    return L


def _rows(header: list[str], rows: list[list[str]]) -> str:
    return "\n".join(_table(header, rows))


def _sec_cases(facts: CardFacts, g: Agg) -> list[str]:
    docs = facts.docs
    kind_docs = Counter(k for d in docs for k in d.case_kinds)
    kind_ja = {
        "boundary": "境界値（しきい値の前後・日付の4類型・真偽の組合せ）",
        "random": "乱数（値域から決定的に引く）",
        "unknown": "不明値（入力の一部を `None` にする）",
    }
    L = ["### 5.5 テストケース", ""]
    L += _table(
        ["種別", "意味", "ケース", "文書"],
        [
            [f"`{k}`", kind_ja.get(k, "—"), _n(v), _n(kind_docs.get(k, 0))]
            for k, v in sorted(g.case_kinds.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    )
    matched: set[str] = set()
    rows = []
    for label, prefixes in _TAG_GROUPS:
        total = 0
        for tag, count in g.case_tags.items():
            if any(tag.startswith(p) for p in prefixes):
                total += count
                matched.add(tag)
        if total:
            rows.append([label, _n(total)])
    L += ["ケースに付いたタグを分類した件数（1 ケースに複数付く）：", ""]
    L += _table(["分類", "ケース"], rows)
    leftover = sorted(set(g.case_tags) - matched)
    if leftover:
        L += [
            "分類に入らなかったタグ（カードの分類表を足すべき印）：" + "、".join(f"`{t}`" for t in leftover),
            "",
        ]
    added = sum(d.mutation_added_cases for d in docs)
    L += [
        (
            f"**日付の4類型**（月末・うるう年・年末年始・土日と祝日の前後）は `DESIGN.md` §10.3 の必須項目で、"
            f"ゲート G8 が日付を扱うルールごとに覆いを検査する（§10）。"
            f"変異を検出できなかったときに足したケースは {_n(added)} 件ある（§10 の G7）。"
        ),
        "",
        "### 5.6 ラベル付きの難所（challenge）",
        "",
    ]
    if g.challenge_types:
        type_ja = {
            "omission": "欠落：計算に要る事項が条項に書かれていない（不足を見抜けるか）",
            "contradiction": "矛盾：本文と別紙の値が食い違う（優先順位の規定で解く）",
            "anomaly": "異例：ふつうでない組み立て（素直に読むと間違う）",
        }
        L += _table(
            ["型", "意味", "文書"],
            [
                [f"`{k}`", type_ja.get(k, "—"), _n(v)]
                for k, v in sorted(g.challenge_types.items(), key=lambda kv: (-kv[1], kv[0]))
            ],
        )
        L += _table(
            ["content_id", "ルール", "型"],
            [
                [f"`{d.content_id}`", f"`{d.challenge_rule}`", f"`{d.challenge_type}`"]
                for d in docs
                if d.challenge_type
            ],
        )
        no_chal = [d for d in docs if d.profile == "challenge" and not d.challenge_type]
        if no_chal:
            L += [
                f"`challenge` プロファイルで生成したが**難所を入れられなかった文書が {_n(len(no_chal))} 件**ある"
                "（対象にできるルールが無かった。§11）：" + "、".join(f"`{d.content_id}`" for d in no_chal),
                "",
            ]
    else:
        L += ["難所を入れた文書は無い（`challenge` プロファイルを使っていない）。", ""]
    L += ["### 5.7 既定の条項への紐づけ（付与モード）", ""]
    L += [
        (
            "既定の契約書にもともと書かれている条項のうち、**一義に計算できるもの**だけに計算仕様を紐づける"
            "（文言は一切変えない）。明示性が欠けるものは、何が欠けているかを記録して除外する。"
        ),
        "",
    ]
    titles = dict(facts.binding_titles)
    rows = []
    for name in facts.declared_bindings:
        rows.append(
            [
                f"`{name}`",
                titles.get(name, "—"),
                _n(g.bind_inc.get(name, 0)),
                _n(g.bind_exc.get(name, 0)),
            ]
        )
    L += _table(["バインディング", "対象の条項", "採用（bound ルール）", "除外（明示性の欠落を記録）"], rows)
    unused_b = [f"`{b}`" for b in facts.declared_bindings if not g.bind_inc.get(b)]
    if unused_b:
        L += ["採用が 0 件のバインディング：" + "、".join(unused_b) + "（§11）。", ""]
    L += ["### 5.8 暦（`calc/calendar.json`）", ""]
    years = sorted({y for d in docs for y in d.calendar_years})
    holiday_counts = sorted({d.calendar_holidays for d in docs})
    L += [
        f"- 収録年：**{years[0]}〜{years[-1]} 年**（{_n(len(years))} 年分）"
        if years
        else "- 暦のファイルに年の情報が無い",
        f"- 祝日の件数：**{'、'.join(_n(c) for c in holiday_counts)} 件**"
        + ("（全文書で同一の固定版）" if len(holiday_counts) == 1 else "（文書間で食い違っている）"),
        "- 祝日は**プログラムに書かず、入力として渡す**。一覧は固定版で、生成時・評価時に外部へ取りに行かない。",
        (
            "- 春分の日・秋分の日は近似式による計算値で、官報告示と 1 日ずれる可能性がある"
            "（`calc/calendar.json` の `note`）。**評価の再現性はこのファイルで閉じる。**"
        ),
        "",
    ]
    return L


_GATE_JA = {
    "G1": "仕様の検査（スキーマ・型と単位・未宣言の入力・根拠のない数値・循環参照）",
    "G2": "根拠の照合（仕様の引用が契約書JSONの単位に逐語で存在する）",
    "G3": "明示性（明示すべき事項に対応する文がある）",
    "G4": "数値の往復（本文・頭書・別紙から読み直した値が仕様と一致する）",
    "G5": "設例の一致（紙面に書いた計算例が参照インタプリタの結果と一致する）",
    "G6": "実装の一致（参照インタプリタと正解プログラムが全ケースで一致する）",
    "G7": "テストの十分性（仕様を1箇所だけ誤らせた実装を、生成したテストが落とす）",
    "G8": "暦の網羅（日付を扱うルールのテストに月末・うるう年・年末年始・土日と祝日が含まれる）",
    "G9": "衝突なし（追加した条項が既存の条項・定数・定義語・別紙番号と衝突しない）",
    "G10": "本体の検査（本体の lint・build・PDF 描画が成功する）",
    "G11": "発見可能性（根拠単位が言い回しと構造による検出で拾える。拾えない単位は記録する）",
    "G12": "決定性（同じ seed で再生成してハッシュが一致する）",
}

_FIXED_LIMITS = (
    (
        "**計算と判定に限る。** 契約の解釈・交渉・リスク評価は対象外で、"
        "条項は「一義に計算できること」を優先して書いてある（現実の契約書より曖昧さが少ない）。"
    ),
    "**法律専門家の校閲を受けていない。** 条項の妥当性・網羅性・実務での通用性は保証しない。",
    "日本語・横書きのみ。金額は円（整数）、割合は分子と分母で持つ。",
    "PDF はデジタル生成で、**スキャン劣化・傾き・影・手書き・印影を含まない**。",
    "暦は**固定版**（外部に取りに行かない）。春分・秋分は近似式の計算値で、官報告示と 1 日ずれ得る。",
    "題材・金額・当事者は実際の取引分布を模していない（業種・規模・地域の偏りを再現する設計ではない）。",
    (
        "`determination`（判定）の入力のうち `judgment`（評価を要する事項）は**真偽として与える**。"
        "評価そのもの（「重大な違反か」の認定）はデータセットの外にある。"
    ),
)


def _sec_pdf(facts: CardFacts, g: Agg) -> list[str]:
    docs = facts.docs
    L = ["## 6. 紙面（PDF）", ""]
    if not any(d.pdf for d in docs):
        return L + [
            (
                f"**この {_n(len(docs))} 文書には PDF が無い**（`--no-render` で生成したもの）。"
                "紙面からの読み取りを含む評価には使えない（`contract.json` と `calc/` だけが揃っている）。"
                "描画するには `--no-render` を外して作り直す。"
            ),
            "",
        ]
    sizes = Counter(d.page_size_mm for d in docs if d.page_size_mm)
    if sizes:
        L += _table(
            ["判型", "文書"],
            [[k, _n(v)] for k, v in sorted(sizes.items(), key=lambda kv: (-kv[1], kv[0]))],
        )
    L += _table(
        ["ページ数", "文書"],
        [[_n(k), _n(v)] for k, v in sorted(Counter(g.pages).items())],
    )
    rows = []
    for style in sorted(g.styles):
        sel = [d for d in docs if d.style_id == style]
        fonts: Counter = Counter()
        for d in sel:
            if d.pdf:
                for f in d.pdf.embedded_fonts:
                    fonts[f] += 1
        rows.append(
            [
                f"`{style}`",
                _n(len(sel)),
                _n(sum(d.pages for d in sel)),
                "、".join(sorted(fonts)) or "—",
            ]
        )
    L += _table(["style_id", "文書", "ページ", "PDF に埋め込まれていたフォント"], rows)
    renderers = Counter(d.renderer for d in docs if d.renderer)
    if renderers:
        L += _table(
            ["renderer", "文書"],
            [[k, _n(v)] for k, v in sorted(renderers.items(), key=lambda kv: (-kv[1], kv[0]))],
        )
    L += _table(
        ["PDF に埋め込まれていたフォント", "文書"],
        [[f"`{k}`", _n(v)] for k, v in sorted(g.embedded_fonts.items(), key=lambda kv: (-kv[1], kv[0]))],
    )
    reg: Counter = Counter()
    for d in docs:
        for f in d.registered_fonts:
            reg[f] += 1
    if reg:
        L += [
            (
                "**上は PDF のフォント記述子から実測した値**（サブセット接頭辞を外したもの）。"
                "下は描画に**登録した候補**で、style がこの中から選ぶ——候補に挙がっているだけのフォントは"
                "PDF に埋め込まれない。"
            ),
            "",
        ]
        L += _table(
            ["描画に登録したフォント", "文書"],
            [[f"`{k}`", _n(v)] for k, v in sorted(reg.items(), key=lambda kv: (-kv[1], kv[0]))],
        )
    checked = [d for d in docs if d.pdf and d.layout_pages]
    L += [
        f"ページ数は **PDF から実測**し、`_render/*/layout.json` の `page_count` と突き合わせている"
        f"（突合できた文書 {_n(len(checked))} / {_n(len(docs))}"
        + (
            "、食い違い無し）。"
            if not any(d.pdf.page_count != d.layout_pages for d in checked)
            else "、食い違いは §1 の警告に出る）。"
        ),
        "",
        (
            "既定 style の描画が WeasyPrint 70.0 の既知不具合で破綻する文書があり、"
            "その場合は**決定的な順で別 style にフォールバック**して描画し、"
            "`calc/manifest.json` の `notes` に残す（件数は §11）。"
        ),
        "",
    ]
    return L


def _sec_evalkit(facts: CardFacts, g: Agg) -> list[str]:
    docs = facts.docs
    L = ["## 7. 評価キット", ""]
    L += [
        (
            f"出題に渡すもの／渡さないものは `{facts.root.name}/README.md` が正本である（ここでは再掲しない）。"
            "評価の入口は `contracts-calc eval`（impl トラック＝実装の採点／discovery トラック＝仕様の発見の採点）。"
        ),
        "",
        "**ヒント水準**（`calc/tasks.jsonl` の `hints`。出題時に削る）：",
        "",
    ]
    L += _table(
        ["水準", "与えるもの", "ヒントを持つ関数"],
        [
            ["H0", "契約書と PDF だけ（条の位置を教えない）", "—（ヒントを与えない）"],
            ["H1", "根拠の条（`第◯条`）", _n(sum(d.tasks_with_h1 for d in docs))],
            ["H2", "根拠の単位 id（条・項・表のセル）", _n(sum(d.tasks_with_h2 for d in docs))],
        ],
    )
    L += [
        (
            "採点は**関数単位**（その関数の全ケースに通ったら合格）と**ケース単位**の 2 段で集計する。"
            "不明値（`None`）のケースも採点に含める（`docs/decisions.md`）。"
        ),
        "",
    ]
    if facts.oracle:
        o = facts.oracle
        L += [
            "**オラクル検査**（正解プログラムを提出とみなして採点した結果。`oracle_report.json`）：",
            "",
        ]
        L += _table(
            ["項目", "実測値"],
            [
                ["合格した関数", f"{_n(o['functions_passed'])} / {_n(o['functions_total'])}"],
                ["関数の合格率", f"{o['function_pass_rate']:.4f}"],
            ],
        )
        by_kind = o.get("by_case_kind", {})
        if by_kind:
            L += _table(
                ["ケースの種別", "合格", "総数"],
                [[f"`{k}`", _n(v["ok"]), _n(v["total"])] for k, v in sorted(by_kind.items())],
            )
        by_pattern = o.get("by_pattern", {})
        failed = {k: v for k, v in by_pattern.items() if v["passed"] != v["total"]}
        L += [
            (
                f"パターン別でも全 {_n(len(by_pattern))} パターンが満点である。"
                if by_pattern and not failed
                else "パターン別に満点でないものがある：" + "、".join(f"`{k}`" for k in sorted(failed))
            )
            if by_pattern
            else "パターン別の内訳は `oracle_report.json` に無い。",
            "",
            (
                "**満点でなければ生成器の誤りである**（採点ハーネス自身の検査であり、"
                "評価対象システムの成績ではない）。"
            ),
            "",
        ]
    else:
        L += ["オラクル検査の結果がこのディレクトリに無い（`contracts-calc eval --oracle` で作る）。", ""]
    return L


def _sec_how(facts: CardFacts, g: Agg) -> list[str]:
    op_ja = {
        "set_content_id": "`content_id` を別番号帯へ付け替える（base + 100 × calc_seed）",
        "add_constant": "`meta.constants` に定数を足す（紙面の表記と値を 1 箇所で持つ）",
        "add_node": "条・別紙を足す",
        "add_header_row": "頭書の表に行を足し、値を本文から分離する",
        "add_table": "表を足す（段階料金などの段階表）",
        "add_figure": "図を足す",
        "add_term": "定義語を足す",
    }
    L = ["## 8. どう作ったか", ""]
    L += [
        "1. 既定の契約書（本体 `contracts` の `content/<cid>`）を**コピーする**。本体は読むだけで変更しない。",
        "2. 既知の実在名称との衝突を**合成名へ置換**する（§9）。",
        (
            "3. 文書の文脈（doctype・既存の条項の題目・当事者・数字の表記）を索引して、"
            "**適用できるパターンを選ぶ**。すでに同じ事項の条項があるパターンは選ばない（追加ではなく付与の対象にする）。"
        ),
        (
            "4. パターンが**同じ乱数から**「契約書に足す文言」と「計算仕様」の両方を作る"
            "（`RuleDraft`。文言とプログラムを別々に書く経路は無い）。"
        ),
        "5. 契約書JSONへの追加を**操作の列**（`calc/patch.json`）として記録し、適用する。",
        "6. 既定の条項に**仕様を紐づける**（付与モード。文言は変えない。§5.7）。",
        (
            "7. 本体の `fill_records` → `lint` → `build` → `render` を呼び、索引・条番号・参照・PDF を本体に再計算させる"
            "（索引を自作しない）。"
        ),
        (
            "8. 仕様から**正解プログラム（Python）**・**テストケース**・**タスクカード**を生成し、"
            "検証ゲート G1〜G11 を回す（§10）。"
        ),
        "",
        "契約書JSONへの追加操作の内訳：",
        "",
    ]
    L += _table(
        ["操作", "内容", "件数"],
        [
            [f"`{k}`", op_ja.get(k, "—"), _n(v)]
            for k, v in sorted(g.patch_ops.items(), key=lambda kv: (-kv[1], kv[0]))
        ],
    )
    L += [
        (
            f"**決定論**：同じ base・`calc_seed`・プロファイル・同じ生成器の版なら、同じ JSON・同じ仕様・"
            f"同じ正解プログラム・同じテストケースが出る（乱数は文書ごと・ルールごとに独立した `random.Random`、"
            f"現在時刻・`uuid`・`hash()` を使わない）。生成器は **{'、'.join(g.versions)}**、"
            f"`calc/manifest.json` が成果物の SHA-256 を持つ。"
        ),
        "",
        (
            "**生成の経路で LLM を呼んでいない。** パターン・語彙・値域は宣言（`patterns/`・`packs/`）にあり、"
            "文言は宣言から組み立てる。"
        ),
        "",
    ]
    return L


def _sec_fiction(facts: CardFacts, g: Agg) -> list[str]:
    replaced = 0
    docs_replaced = 0
    for d in facts.docs:
        for note in d.notes:
            m = re.search(r"名称衝突を合成名へ置換: (\d+) 件", note)
            if m:
                replaced += int(m.group(1))
                docs_replaced += 1
    return [
        "## 9. 架空性",
        "",
        (
            "- **完全架空**：会社名・屋号・人物名・住所・連絡先・物件名・契約書番号はすべて架空である"
            "（base となる契約書から継承する。本体の `keiyaku/lint/denylist.txt` が実在名を検出する）。"
        ),
        (
            f"- **生成の前に実在名称との衝突を潰す**：既知の実在名称と当たった表記を合成名へ置換した件数は"
            f"**{_n(replaced)} 件**（{_n(docs_replaced)} 文書）で、置換後に禁止名称の全量検査を回している"
            "（`fictionalize.py`・`tests/test_fictionalize.py`）。"
        ),
        (
            "- **金額・数量・割合・期間はパターンの値域から決定的に抽選した架空の値**である。"
            "実在の相場・料率を写していない。"
        ),
        (
            "- **実在の法令・裁判所・官公庁は名称のみ**を引用し、**法令の条番号は書かない**"
            "（架空の条文に実在の条番号を結び付けないため）。"
        ),
        "- 印影・手書き署名は描画しない（記名押印欄は枠と「印」の文字だけ）。",
        "",
    ]


def _sec_quality(facts: CardFacts, g: Agg) -> list[str]:
    docs = facts.docs
    L = ["## 10. 品質保証", "", "### 10.1 検証ゲート", ""]
    rows = []
    for gate in sorted(g.gate_status, key=lambda x: int(x[1:])):
        st = g.gate_status[gate]
        rows.append(
            [
                f"`{gate}`",
                _GATE_JA.get(gate, "—"),
                _n(st.get("ok", 0)),
                _n(st.get("skip", 0)),
                _n(st.get("NG", 0)),
            ]
        )
    L += _table(["ゲート", "何を見るか", "通過", "スキップ", "不合格"], rows)
    ng = [f"`{d.content_id}`" for d in docs if any(s == "NG" for _, s in d.gates)]
    L += [
        (
            "**不合格の文書は無い。**"
            if not ng
            else "**不合格の文書がある**（データセットに入れてはいけない）：" + "、".join(ng)
        ),
        "",
    ]
    mt = sum(d.mutation_total for d in docs)
    md = sum(d.mutation_detected for d in docs)
    ms = sum(d.mutation_skipped for d in docs)
    unpicked = sum(d.g11_unpicked for d in docs)
    L += ["### 10.2 変異検出（G7）と発見可能性（G11）の実測", ""]
    L += _table(
        ["項目", "実測値", "意味"],
        [
            [
                "仕様を 1 箇所だけ誤らせた実装",
                _n(mt),
                "生成したテストがこれを落とせなければ、テストが足りない",
            ],
            [
                "そのうち検出できたもの",
                f"{_n(md)}（{md / mt:.1%}）" if mt else "—",
                "G7 の合格条件は全件検出",
            ],
            [
                "検出の対象から外したもの",
                _n(ms),
                "誤らせても結果が変わらない変異（理由つきで記録する）",
            ],
            [
                "言い回しで拾えなかった根拠単位",
                _n(unpicked),
                "G11。**discovery トラックの難しさの実測**であり、不合格ではない",
            ],
            [
                "変異の検出のために足したケース",
                _n(sum(d.mutation_added_cases for d in docs)),
                "乱数まかせにしない（`docs/decisions.md`）",
            ],
        ],
    )
    L += ["### 10.3 そのほか", ""]
    L += [
        "- **本体の検査を通している**（G10）：本体の `lint`（L00–L26）・`build`・`render` が成功した文書だけを収める。",
        (
            "- **成果物のハッシュ**：`calc/manifest.json` が `contract.json`・`spec.json`・`answer_key.json`・"
            "正解プログラム・テストの SHA-256 を持つ。"
        ),
        "- **オラクル検査**（§7）は採点ハーネスと生成器の整合の検査である。満点でなければ生成器の誤り。",
        (
            "- 生成器自身の回帰は `tests/`（20 base の生成とゲート通過・同 seed 2 回の一致・"
            "変異実装が不合格になること・意味論の一致）で固定している。"
        ),
        "",
    ]
    return L


def _sec_limits(facts: CardFacts, g: Agg) -> list[str]:
    docs = facts.docs
    L = ["## 11. 制限と既知の偏り", "", "**設計上の制限**（意図して外した）", ""]
    L += [f"- {line}" for line in _FIXED_LIMITS]
    L.append("")
    L += ["**データの作りから来る偏り**（実測）", ""]
    base_docs = sorted(g.bases.items(), key=lambda kv: (-kv[1], kv[0]))
    doctype_docs = sorted(g.doctypes.items(), key=lambda kv: (kv[1], kv[0]))
    L += [
        f"- **本文は base を共有する。** {_n(g.n_docs)} 文書は {_n(len(g.bases))} 本の契約書から作ってあり、"
        f"1 本の base から最大 {_n(base_docs[0][1])} 文書（`{base_docs[0][0]}`）を作っている。"
        "**独立な契約書 {0} 本ぶんの多様性は無い**（計算条項と値は文書ごとに違う）。".format(_n(g.n_docs)),
        (
            f"- **doctype ごとの文書数が揃っていない。** 最少は `{doctype_docs[0][0]}` の {_n(doctype_docs[0][1])} 文書、"
            f"最多は `{doctype_docs[-1][0]}` の {_n(doctype_docs[-1][1])} 文書である。doctype 別の精度を比べるときは母数を見る。"
        ),
        (
            f"- **1 文書のルール数は {_range([d.n_rules for d in docs])} 件**で、プロファイルの宣言に従う（§4.1）。"
            "文書あたりの難易度は均一ではない。"
        ),
        "",
    ]
    small = [o for o in g.observations if o.docs < SMALL_SAMPLE_THRESHOLD]
    L += [
        (
            f"**母数の小さい観点**（覆っている文書が {SMALL_SAMPLE_THRESHOLD} 件未満。"
            "この観点だけで精度を語らない）"
        ),
        "",
    ]
    if small:
        L += _table(
            ["分類", "観点", "文書", "ルール"],
            [[o.group, f"`{o.name}`", _n(o.docs), _n(o.rules)] for o in small],
        )
    else:
        L += [f"覆っている文書が {SMALL_SAMPLE_THRESHOLD} 件未満の観点は無い。", ""]
    unused_pat = [f"`{pid}`（{title}）" for pid, title in facts.declared_patterns if pid not in g.pat_docs]
    unused_bind = [f"`{b}`" for b in facts.declared_bindings if not g.bind_inc.get(b)]
    unused_prof = [f"`{p}`" for p in facts.declared_profiles if p not in g.profiles]
    L += ["**宣言はあるが使っている文書が 0 の観点**（実装が検証されていない）", ""]
    unused_rows = (
        [["パターン", x] for x in unused_pat]
        + [["バインディング", x] for x in unused_bind]
        + [["プロファイル", x] for x in unused_prof]
    )
    if unused_rows:
        L += _table(["分類", "観点"], unused_rows)
    else:
        L += ["宣言のうち使われていないものは無い。", ""]
    L += [
        (
            "この 2 つの表は `dataset/` の実測から毎回作り直すので、文書を足して観点が増えれば自動的に消える"
            "（`docs/data_card.md` §4.3）。"
        ),
        "",
        "**生成時に記録された注記**（何を諦めたかの実測）",
        "",
    ]
    if g.notes:
        L += _table(
            ["注記", "件数"],
            [[k, _n(v)] for k, v in sorted(g.notes.items(), key=lambda kv: (-kv[1], kv[0]))],
        )
        L += [
            (
                "注記は `calc/manifest.json` の `notes` にそのまま入っている。"
                "「パターンを見送った」「下限に満たない」は、**その文書のルールが宣言より少ない**ことを意味する。"
            ),
            "",
        ]
    else:
        L += ["注記のある文書は無い。", ""]
    return L


def _sec_license(facts: CardFacts, g: Agg) -> list[str]:
    L = ["## 12. ライセンスと配布", ""]
    L += [
        (
            "- **生成物（契約書JSON・PDF・仕様・正解プログラム・テストケース）の配布条件は未決**である。"
            "決定は人間の領分で `HITL.md`（HC-3）に起票してある。**決定が入るまで外部配布しない。**"
        ),
        (
            "- 本データセットは本体 `contracts`（keiyaku-synth）の契約書を**コピーして**作っており、"
            "本体の配布条件（親 `dataset/data-card.md` §12。同じく未決）に従う。"
        ),
    ]
    if g.embedded_fonts:
        groups: dict[str, list[str]] = defaultdict(list)
        for font in sorted(g.embedded_fonts):
            license_name = next((lic for key, lic in _FONT_LICENSE if key in font), "ライセンス未同定")
            groups[license_name].append(font)
        L.append("- **PDF にはフォントが埋め込まれている**（実測。§6）。再配布するときは次の条件に従う：")
        for license_name in sorted(groups):
            L.append(f"  - {license_name}：" + "、".join(f"`{f}`" for f in groups[license_name]))
        unknown = groups.get("ライセンス未同定")
        if unknown:
            L.append("  - **ライセンスを同定できなかったフォントがある。** 配布の前に確認する。")
    else:
        L.append("- PDF が無いため、埋め込みフォントのライセンスは関係しない。")
    L += [
        (
            "- `contract.json`・`calc/` 配下（仕様・正解プログラム・ケース・タスクカード）は"
            "フォントのデータを含まない。"
        ),
        "- 参考にした実在の契約書ひな型は**一切含まれていない**（§9）。",
        "",
    ]
    return L


def _sec_update(facts: CardFacts) -> list[str]:
    root = facts.root.name
    return [
        "## 13. このカードの更新",
        "",
        "```",
        f"contracts-calc datacard update --data {root}   # 書き出す（実ファイルを測るだけ。再生成は不要）",
        f"contracts-calc datacard check  --data {root}   # 書き換えずに古くなっていないかを見る（古ければ終了コード 1）",
        f"contracts-calc datasheet       --data {root}   # README とこのカードを対で作り直す",
        "```",
        "",
        (
            "`generate` と `bind` は 1 回の実行の最後に、出力先の README とこのカードを書き直す"
            "（文書を足したら更新される）。**この更新を忘れたら `datacard check` が落ちる**"
            "（`tests/test_datacard.py` が常設で検査する）。"
        ),
        "",
        (
            "測り方そのものの検査は別物で、`uv run --project .. python scripts/verify_data_card.py --data "
            f"{root}`（本実装を通さない別経路で数え直して突き合わせる）を、節や項目を足したときに手で回す。"
        ),
        "",
        "仕様と節の追加手順は `docs/data_card.md`。",
    ]


def render(facts: CardFacts) -> str:
    g = aggregate(facts)
    lines: list[str] = []
    lines += _sec_overview(facts, g)
    lines += _sec_usage()
    lines += _sec_scale(facts, g)
    lines += _sec_breakdown(facts, g)
    lines += _sec_answers(facts, g)
    lines += _sec_cases(facts, g)
    lines += _sec_pdf(facts, g)
    lines += _sec_evalkit(facts, g)
    lines += _sec_how(facts, g)
    lines += _sec_fiction(facts, g)
    lines += _sec_quality(facts, g)
    lines += _sec_limits(facts, g)
    lines += _sec_license(facts, g)
    lines += _sec_update(facts)
    text = "\n".join(lines).rstrip() + "\n"
    return re.sub(r"\n{3,}", "\n\n", text)


# --- 書き出しと鮮度の検査 ----------------------------------------------------------


def write_card(data_root: Path) -> Path:
    """データカードを書き出す。戻り値はカードのパス。"""
    data_root = Path(data_root)
    text = render(collect(data_root))
    out = data_root / CARD_NAME
    out.write_text(text, encoding="utf-8")
    return out


def check_card(data_root: Path) -> tuple[bool, str]:
    """書き換えずに鮮度を見る。(ok, 説明) を返す。"""
    data_root = Path(data_root)
    card = data_root / CARD_NAME
    if not card.is_file():
        return False, f"{card} が無い（`datacard update` で作る）"
    want = render(collect(data_root))
    got = card.read_text(encoding="utf-8")
    if got == want:
        return True, f"{card} は現在の {data_root} から生成したものと一致する"
    want_lines, got_lines = want.splitlines(), got.splitlines()
    diffs = [
        f"  {i + 1} 行目: いま「{g[:60]}」／あるべき「{w[:60]}」"
        for i, (g, w) in enumerate(zip(got_lines, want_lines))
        if g != w
    ]
    detail = (
        "\n".join(diffs[:5]) or f"  行数が違う（いま {len(got_lines)} 行／あるべき {len(want_lines)} 行）"
    )
    return False, f"{card} が古い（`datacard update` で書き直す）:\n{detail}"
