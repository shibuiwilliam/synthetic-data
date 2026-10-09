"""`dataset/` を Hugging Face Hub のデータセットとして公開できる形に整える（仕様は `docs/publishing.md`）。

    uv run keiyaku publish update   # README（カード）・views/・.gitattributes・licenses/・SHA256SUMS
    uv run keiyaku publish check    # 鮮度と、公開をふさいでいる条件を報告する（書き換えない）

**一次資料は 1 バイトも書き換えない。** `source.json` / `layout.json` / `answer.json` / `qa.json` /
`elements.jsonl` / `doc.pdf` / `pages/*.png` はそのままで、Hub が必要とする面（カードの
frontmatter・平らな jsonl・LFS 指定・ライセンス）を足すだけである。

**人間の決定を代行しない。** 配布条件（`specs/publish.yaml` の `license.id`）が `undecided` の
あいだは、カードに「未決」と書き、frontmatter に `license` を出さず、アップロードを拒否する
（`CLAUDE.md` §0.2-1・`HITL_TODO.md` H13）。

数値は固定文字列に焼き込まず `dataset/` の実測から出す（`docs/data_card.md` §2-1）。
生成は決定論（`datetime.now()` を入れない。SHA256SUMS は自分自身を数えない）。
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

import yaml
from pydantic import Field

from keiyaku.datacard import CARD_NAME, DataCardStats, collect
from keiyaku.models import Model

#: 宣言の置き場（公開の「決定」はここだけから読む）
SPEC_PATH = Path(__file__).resolve().parent.parent / "specs" / "publish.yaml"
#: 平らな面の置き場（`dataset/` からの相対）
VIEWS_DIR = "views"
#: ライセンス本文の置き場（`dataset/` からの相対）
LICENSES_DIR = "licenses"
#: 同梱フォントのライセンス本文の出所
FONTS_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"
#: フォント名の接頭辞 → ライセンス本文のファイル名（PDF に**実際に埋め込まれていた**ものだけ入れる）
FONT_LICENSES: tuple[tuple[str, str, str], ...] = (
    ("Noto-Sans-JP", "LICENSE-NotoSansJP.txt", "SIL Open Font License 1.1"),
    ("Noto-Serif-JP", "LICENSE-NotoSerifJP.txt", "SIL Open Font License 1.1"),
    ("IPAex", "IPA_Font_License_Agreement_v1.0.txt", "IPA Font License v1.0"),
)
#: ライセンス未決を表す値
UNDECIDED = "undecided"
#: チェックサム一覧のファイル名（自分自身は数えない）
SUMS_NAME = "SHA256SUMS"
#: `publish` が作るファイル（`check` が鮮度を見る対象）
GENERATED = ("README.md", ".gitattributes", ".gitignore", SUMS_NAME)
#: `publish` が作るディレクトリ。**`keiyaku clean --stale` の保護一覧に入れる**
#: （doc_id の一覧に無いので、守らないと掃除で消える。`keiyaku/cli.py` の `PROTECTED_DIRS`）
PROTECTED_HINT = frozenset({VIEWS_DIR, LICENSES_DIR})


# --- 宣言のモデル -------------------------------------------------------------


class HubSpec(Model):
    repo_id: str
    repo_type: str = "dataset"
    private: bool = True
    revision: str = ""


class SearchDatasetSpec(Model):
    """検索評価セット（`dataset/search/`）を**別のデータセットとして公開する**宣言。

    本体のデータセットは「文書（PDF・ページ画像・構造・QA）」で、検索評価セットは
    「コーパス全体に 1 組だけある passages / queries / qrels」である。粒度も行数も
    Viewer の見え方も違うので、Hub では 2 つのリポジトリに分ける（`docs/publishing.md` §12）。

    `dir` が**そのリポジトリのルート**になる（`dataset/search/` をそのまま上げる）。
    本体のリポジトリからはこのディレクトリを外す（二重配布を作らない）。
    """

    #: 切り出すか。`false` なら従来どおり本体のリポジトリに `search/` ごと入れる
    enabled: bool = True
    #: 切り出す対象（`dataset/` からの相対。このディレクトリが別リポジトリのルートになる）
    dir: str = "search"
    hub: HubSpec = Field(default_factory=lambda: HubSpec(repo_id=""))
    pretty_name: str = "Japanese contract retrieval evaluation set (synthetic)"
    pretty_name_ja: str = ""
    task_categories: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)

    @property
    def hub_url(self) -> str:
        return f"https://huggingface.co/datasets/{self.hub.repo_id}" if self.hub.repo_id else ""


class LicenseSpec(Model):
    #: Hub の license タグ。`undecided` のあいだは人間の判断待ち（H13）
    id: str = UNDECIDED
    holder: str = ""
    year: str = ""
    note: str = ""

    @property
    def decided(self) -> bool:
        return bool(self.id) and self.id != UNDECIDED


class CitationSpec(Model):
    authors: list[str] = Field(default_factory=list)
    title: str = ""
    year: int = 0


class PublishSpec(Model):
    """`specs/publish.yaml`。公開に関する**人間の決定**の正本。"""

    target: str = "huggingface"
    hub: HubSpec
    pretty_name: str
    pretty_name_ja: str = ""
    license: LicenseSpec = Field(default_factory=LicenseSpec)
    code_repo: str = ""
    language: list[str] = Field(default_factory=lambda: ["ja"])
    multilinguality: str = "monolingual"
    annotations_creators: list[str] = Field(default_factory=list)
    source_datasets: list[str] = Field(default_factory=list)
    task_categories: list[str] = Field(default_factory=list)
    task_ids: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)
    lfs: list[str] = Field(default_factory=list)
    citation: CitationSpec = Field(default_factory=CitationSpec)
    #: 検索評価セットを別のデータセットとして公開する宣言（`docs/publishing.md` §12）
    search_dataset: SearchDatasetSpec = Field(default_factory=SearchDatasetSpec)

    @property
    def hub_url(self) -> str:
        return f"https://huggingface.co/datasets/{self.hub.repo_id}"

    @property
    def search_split(self) -> bool:
        """検索評価セットを別リポジトリに切り出しているか（本体から外す条件そのもの）。"""
        return self.search_dataset.enabled and bool(self.search_dataset.dir)

    @property
    def search_ref_en(self) -> str:
        """カードに書く公開先の指し方（未決なら URL を書かない）。"""
        sd = self.search_dataset
        if not sd.hub.repo_id:
            return "(the companion repository name is not decided yet)"
        return f"[`{sd.hub.repo_id}`]({sd.hub_url})"

    @property
    def search_ref_ja(self) -> str:
        sd = self.search_dataset
        return f"[`{sd.hub.repo_id}`]({sd.hub_url})" if sd.hub.repo_id else "（公開先は未決）"


def default_spec() -> PublishSpec:
    """宣言が無いときの既定（**公開はふさがれた状態**）。

    `keiyaku export` は最後に公開用の面を作るので、宣言が無いだけで生成が止まってはいけない。
    `hub.repo_id` を空にしておくと `blockers()` が「公開先が無い」と報告する。
    """
    return PublishSpec(
        hub=HubSpec(repo_id=""),
        pretty_name="Japanese contract documents (synthetic)",
        exclude=["render.html", ".DS_Store", "*.log", ".gitignore"],
        lfs=["*.pdf", "*.png"],
    )


def load_spec(path: Path = SPEC_PATH) -> PublishSpec:
    """`specs/publish.yaml` を読む。**無ければ既定に落とす**（生成を止めない）。"""
    if not path.is_file():
        return default_spec()
    return PublishSpec.model_validate(yaml.safe_load(path.read_text(encoding="utf-8")))


# --- 平らな面（views/） -------------------------------------------------------


class ViewCounts(Model):
    documents: int = 0
    pages: int = 0
    qa: int = 0


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _dump_jsonl(rows: Iterable[dict[str, Any]], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def _doc_dirs(dataset_dir: Path) -> list[Path]:
    return sorted(d for d in dataset_dir.iterdir() if d.is_dir() and (d / "answer.json").is_file())


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _manifest_rows(dataset_dir: Path) -> dict[str, dict[str, Any]]:
    path = dataset_dir / "manifest.json"
    if not path.is_file():
        return {}
    return {row["doc_id"]: row for row in _load(path).get("documents", [])}


def document_rows(dataset_dir: Path) -> list[dict[str, Any]]:
    """1 文書 1 行（`views/documents.jsonl`）。`manifest.json` ＋ `source.json` の meta ＋ 判型。"""
    manifest = _manifest_rows(dataset_dir)
    rows: list[dict[str, Any]] = []
    for directory in _doc_dirs(dataset_dir):
        doc_id = directory.name
        source = _load(directory / "source.json")
        layout = _load(directory / "layout.json")
        meta = source["meta"]
        entry = manifest.get(doc_id, {})
        size = layout.get("page_size_pt") or [0.0, 0.0]
        images = (
            sorted(p for p in (directory / "pages").glob("page-*.png"))
            if (directory / "pages").is_dir()
            else []
        )
        rows.append(
            {
                "doc_id": doc_id,
                "content_id": source["content_id"],
                "doctype": source["doctype"],
                "style_id": layout["style_id"],
                "title": meta["title"],
                "seed": source["seed"],
                "pages": layout["page_count"],
                "chars": entry.get("chars", 0),
                "tables": entry.get("tables", 0),
                "figures": entry.get("figures", 0),
                "footnotes": entry.get("footnotes", 0),
                "refs": entry.get("refs", 0),
                "qa_items": entry.get("qa_items", 0),
                "status": entry.get("status", ""),
                "numbering_scheme": meta.get("numbering_scheme", ""),
                "digit_style": meta.get("digit_style", ""),
                "contract_date": meta.get("contract_date"),
                "contract_number": meta.get("contract_number"),
                "page_width_pt": float(size[0]),
                "page_height_pt": float(size[1]),
                "dpi_png": layout.get("dpi_png", 0),
                "parties": [
                    {
                        "key": p["key"],
                        "alias": p["alias"],
                        "name": p["name"],
                        "role_label": p.get("role_label") or "",
                    }
                    for p in meta.get("parties", [])
                ],
                "pdf": _rel(directory / "doc.pdf", dataset_dir),
                "page_images": [_rel(p, dataset_dir) for p in images],
                "source_json": _rel(directory / "source.json", dataset_dir),
                "layout_json": _rel(directory / "layout.json", dataset_dir),
                "answer_json": _rel(directory / "answer.json", dataset_dir),
                "qa_json": _rel(directory / "qa.json", dataset_dir),
                "elements_jsonl": _rel(directory / "elements.jsonl", dataset_dir),
            }
        )
    return rows


def page_rows(dataset_dir: Path) -> list[dict[str, Any]]:
    """1 ページ 1 行（`views/pages.jsonl`）。ページ本文と PNG の相対パス。"""
    rows: list[dict[str, Any]] = []
    for directory in _doc_dirs(dataset_dir):
        answer = _load(directory / "answer.json")
        layout = _load(directory / "layout.json")
        source = _load(directory / "source.json")
        size = layout.get("page_size_pt") or [0.0, 0.0]
        dpi = layout.get("dpi_png", 0) or 0
        for page in answer["pages"]:
            number = page["number"]
            image = directory / "pages" / f"page-{number:03d}.png"
            rows.append(
                {
                    "doc_id": answer["doc_id"],
                    "content_id": source["content_id"],
                    "doctype": source["doctype"],
                    "style_id": layout["style_id"],
                    "page": number,
                    "text": page["text"],
                    "text_with_furniture": page["text_with_furniture"],
                    "chars": page["chars"],
                    "image": _rel(image, dataset_dir) if image.is_file() else None,
                    "page_width_pt": float(size[0]),
                    "page_height_pt": float(size[1]),
                    "dpi_png": dpi,
                }
            )
    return rows


def qa_rows(dataset_dir: Path) -> list[dict[str, Any]]:
    """1 問 1 行（`views/qa.jsonl`）。

    `qa.json` の `answer` は **float / str / list[str] が混在する**（`answer_type` で決まる）。
    Arrow は 1 列に複数の型を入れられないので型ごとに列を分け、**生の値は `answer_json` で
    失わずに持つ**（採点に使う正本は `qa.json` のほう。`docs/publishing.md` §4）。
    """
    rows: list[dict[str, Any]] = []
    for directory in _doc_dirs(dataset_dir):
        qa_path = directory / "qa.json"
        if not qa_path.is_file():
            continue
        payload = _load(qa_path)
        source = _load(directory / "source.json")
        layout = _load(directory / "layout.json")
        for item in payload["items"]:
            answer = item["answer"]
            rows.append(
                {
                    "doc_id": payload["doc_id"],
                    "content_id": source["content_id"],
                    "doctype": source["doctype"],
                    "style_id": layout["style_id"],
                    "qa_id": item["id"],
                    "type": item["type"],
                    "source": item["source"],
                    "question": item["question"],
                    "answer_type": item["answer_type"],
                    "answer_text": answer if isinstance(answer, str) else None,
                    "answer_number": float(answer) if isinstance(answer, int | float) else None,
                    "answer_list": answer if isinstance(answer, list) else None,
                    "answer_json": json.dumps(answer, ensure_ascii=False, sort_keys=True),
                    "evidence": item.get("evidence", []),
                    "page_hint": item.get("page_hint", []),
                }
            )
    return rows


def build_views(dataset_dir: Path) -> ViewCounts:
    """`dataset/views/*.jsonl` を書き出す（一次資料からの射影）。"""
    views = dataset_dir / VIEWS_DIR
    return ViewCounts(
        documents=_dump_jsonl(document_rows(dataset_dir), views / "documents.jsonl"),
        pages=_dump_jsonl(page_rows(dataset_dir), views / "pages.jsonl"),
        qa=_dump_jsonl(qa_rows(dataset_dir), views / "qa.jsonl"),
    )


# --- frontmatter --------------------------------------------------------------

#: Hub の `configs`（config 名 → data_files のパス）。**glob はそのまま Hub が解決する**
CONFIGS: tuple[tuple[str, str, str], ...] = (
    ("documents", f"{VIEWS_DIR}/documents.jsonl", "1 行 1 文書（題名・doctype・判型・当事者・成果物のパス）"),
    ("pages", f"{VIEWS_DIR}/pages.jsonl", "1 行 1 ページ（ページ本文と PNG の相対パス）"),
    ("qa", f"{VIEWS_DIR}/qa.jsonl", "1 行 1 問（45 問 × 文書数）"),
    ("elements", "*/elements.jsonl", "1 行 1 要素（本文・構造位置・bbox・表/図/列挙の位置）"),
)
#: 検索評価セットの `configs`。**別リポジトリのルートからの相対**（`dataset/search/` が root）
SEARCH_CONFIGS: tuple[tuple[str, str, str], ...] = (
    ("passages", "passages.jsonl", "検索パッセージ"),
    ("queries", "queries.jsonl", "検索クエリ"),
    ("qrels", "qrels.jsonl", "適合判定（grade 2 / 1）"),
)


def main_configs(spec: PublishSpec) -> tuple[tuple[str, str, str], ...]:
    """本体のリポジトリに出す `configs`。

    検索評価セットを切り出していないときは、従来どおり `search/*.jsonl` も本体に出す
    （**存在しないパスを `configs` に書くと Viewer が落ちる**。`docs/publishing.md` §11）。
    """
    if spec.search_split:
        return CONFIGS
    prefix = spec.search_dataset.dir or "search"
    return CONFIGS + tuple((name, f"{prefix}/{path}", label) for name, path, label in SEARCH_CONFIGS)


def _size_category(documents: int) -> str:
    """Hub の `size_categories`。**文書数から決める**（焼き込まない）。"""
    for limit, label in ((1_000, "n<1K"), (10_000, "1K<n<10K"), (100_000, "10K<n<100K")):
        if documents < limit:
            return label
    return "100K<n<1M"


def frontmatter(spec: PublishSpec, stats: DataCardStats | None) -> str:
    """カード冒頭の YAML。`license` は**決まっていなければキー自体を出さない**。"""
    data: dict[str, Any] = {
        "pretty_name": spec.pretty_name,
        "language": list(spec.language),
        "multilinguality": spec.multilinguality,
        "annotations_creators": list(spec.annotations_creators),
        "source_datasets": list(spec.source_datasets),
        "task_categories": list(spec.task_categories),
        "task_ids": list(spec.task_ids),
        "tags": list(spec.tags),
        "size_categories": [_size_category(stats.scale.documents if stats else 0)],
        "configs": [
            {"config_name": name, "data_files": [{"split": "train", "path": path}]}
            for name, path, _ in main_configs(spec)
        ],
    }
    if spec.license.decided:
        data = {"license": spec.license.id, **data}
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)
    return f"---\n{body}---\n"


# --- カード本文 ---------------------------------------------------------------


def _n(value: int) -> str:
    return f"{value:,}"


def _query_facts(dataset_dir: Path, queries: Sequence[Any], subdir: str = "search") -> tuple[int, int, str]:
    """grade 1 の打ち切り（qrels の解釈に直結する）を実測する。

    渡されていなければ `dataset/<subdir>/queries.jsonl` から読む。**固定値を焼き込まない**
    （以前 README に「1,944 クエリ中 28 件」と直書きされており、文書構成が変わっても
    更新されなかった）。
    """
    rows: list[Any] = list(queries)
    if not rows:
        path = dataset_dir / (subdir or "search") / "queries.jsonl"
        if path.is_file():
            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]

    def field(row: Any, name: str) -> Any:
        return row.get(name) if isinstance(row, dict) else getattr(row, name, None)

    truncated = [r for r in rows if field(r, "related_truncated")]
    examples = ", ".join(f"「{field(r, 'query')}」" for r in truncated[:3])
    return len(rows), len(truncated), f"（{examples}）" if examples else ""


def _qa_per_doc(stats: DataCardStats | None) -> str:
    """1 文書あたりの QA 数（実測）。全文書同数ならその数、違えば範囲。"""
    if not stats or not stats.documents:
        return "QA"
    counts = {d.qa_items for d in stats.documents}
    return f"{_n(min(counts))} 問" if len(counts) == 1 else f"{_n(min(counts))}–{_n(max(counts))} 問"


def _layouts_per_content(stats: DataCardStats | None) -> str:
    """1 content を何通りの版面で描いているか（実測）。**「content × style 数」と書くと嘘になる**
    ——全 style の総当たりではない（`docs/doctypes.md` §7）。"""
    if not stats or not stats.documents:
        return "1 つ以上"
    per: dict[str, int] = {}
    for row in stats.documents:
        per[row.content_id] = per.get(row.content_id, 0) + 1
    low, high = min(per.values()), max(per.values())
    return f"{low}" if low == high else f"{low}–{high}"


def _embedded_font_names(stats: DataCardStats | None) -> list[str]:
    return [row.name for row in stats.layout.embedded_fonts] if stats else []


def _license_line_en(spec: PublishSpec) -> str:
    if spec.license.decided:
        holder = f" © {spec.license.year} {spec.license.holder}".rstrip() if spec.license.holder else ""
        return f"Released under **{spec.license.id}**{holder}. See `LICENSE`."
    return (
        "**The redistribution terms of the generated files are not decided yet.** "
        "This copy is for review only; do not redistribute until a license is set "
        "(tracked as H13 in the project's `HITL_TODO.md`)."
    )


def _license_line_ja(spec: PublishSpec) -> str:
    if spec.license.decided:
        holder = f"（著作権表示：© {spec.license.year} {spec.license.holder}）" if spec.license.holder else ""
        return f"生成物は **{spec.license.id}** で配布する{holder}。本文は `LICENSE`。"
    return (
        "**生成物の配布条件は未決**である（`HITL_TODO.md` H13）。"
        "決定が入るまで再配布しない。`specs/publish.yaml` の `license.id` が決まると"
        "frontmatter の `license` とこの節が入れ替わる。"
    )


def _citation(spec: PublishSpec) -> str:
    key = spec.hub.repo_id.split("/")[-1].replace("-", "_")
    authors = " and ".join(spec.citation.authors) or spec.hub.repo_id.split("/")[0]
    return (
        "```bibtex\n"
        f"@misc{{{key},\n"
        f"  title  = {{{spec.citation.title or spec.pretty_name}}},\n"
        f"  author = {{{authors}}},\n"
        f"  year   = {{{spec.citation.year or ''}}},\n"
        f"  howpublished = {{Hugging Face Hub}},\n"
        f"  url    = {{{spec.hub_url}}}\n"
        "}\n"
        "```\n"
    )


def render_card(
    spec: PublishSpec,
    stats: DataCardStats | None,
    *,
    n_queries: int,
    n_truncated: int,
    truncated_examples: str,
) -> str:
    """`dataset/README.md`（= Hub のデータセットカード）を組み立てる。

    数値は `stats`（`dataset/` の実測）と引数から入れる。**固定文字列に焼き込まない。**
    """
    scale = stats.scale if stats else None
    parts: list[str] = [frontmatter(spec, stats)]
    add = parts.append
    docs = scale.documents if scale else 0
    contents = scale.contents if scale else 0
    pages = scale.pages if scale else 0
    qa_items = scale.qa_items if scale else 0
    doctypes = scale.doctypes if scale else 0
    styles = scale.styles if scale else 0

    # ---- 英語 ---------------------------------------------------------------
    add(f"\n# {spec.pretty_name}\n\n")
    add(
        f"**{_n(docs)} synthetic Japanese business contracts rendered to PDF, each paired with "
        "complete, machine-generated ground truth** — page text, clause tree (chapter / article / "
        "paragraph / item), tables, figures, cross-references, party roles, bounding boxes, reading "
        f"order, and {_n(qa_items)} QA pairs. Every company, person, address, amount and document "
        "number is **fictional**; nothing is copied from real templates.\n\n"
    )
    add(
        f"- **{_n(docs)} documents** = {_n(contents)} written contracts, each rendered in "
        f"{_layouts_per_content(stats)} of {_n(styles)} page layouts, covering {_n(doctypes)} "
        f"contract types, {_n(pages)} pages in total.\n"
        "- The JSON is the **single source of truth**; the PDF is its deterministic rendering "
        "(JSON → HTML → PDF), so the paper and the labels cannot disagree.\n"
        "- 150 dpi page images (`pages/*.png`) are included for OCR / VLM evaluation.\n"
        f"- {_license_line_en(spec)}\n\n"
    )
    add("## \u26a0 Not for training AI models\n\n")
    add(NO_TRAINING_EN.split("\n", 2)[2].strip() + "\n\n")

    add("## What it is for\n\n")
    add(
        "1. OCR / VLM text reading from page images or PDF.\n"
        "2. Clause-structure extraction (the chapter→article→paragraph→item tree and where an "
        "element sits in it).\n"
        "3. Table structure understanding (row header × column header → value) and figure "
        "structure (nodes / edges / paths).\n"
        "4. Reference resolution (cross-references, defined terms, party aliases 甲 / 乙).\n"
        "5. Document QA (extraction, reference following, and arithmetic).\n"
        "6. **Layout robustness**: the same contract body rendered in two different page layouts — "
        "content labels stay identical, only boxes and reading order change.\n"
    )
    if spec.search_split:
        add(
            "7. Retrieval / RAG evaluation — the corpus-wide passages, queries and relevance "
            f"judgements built from these documents are a **companion dataset**: {spec.search_ref_en}.\n\n"
        )
    else:
        add("7. Retrieval / RAG evaluation (passages + queries + qrels under `search/`).\n\n")
    add("## What it is **not** for\n\n")
    add(
        "- **Any real-world legal use.** The clauses are dummies written for reading evaluation and "
        "have not been reviewed by a lawyer. The documents have no legal effect.\n"
        "- Reproducing real contract templates (only structure and layout conventions were studied; "
        "every sentence is original).\n"
        "- **Training, fine-tuning or distilling any AI / ML model** (see the section above; "
        "this is a restriction from Anthropic's Usage Policy, not from the dataset license).\n"
        "- Language-model pre-training (too small, deliberately narrow subject matter).\n"
        "- Scanned / photographed / handwritten document evaluation: these PDFs are born-digital, "
        "with no skew, shadow, noise or seal impressions.\n\n"
    )
    add("## Configs\n\n")
    add("| config | rows | what one row is | files |\n|---|---|---|---|\n")
    counts = {
        "documents": docs,
        "pages": pages,
        "qa": qa_items,
        "elements": scale.elements if scale else 0,
        "passages": stats.search.passages if stats else 0,
        "queries": stats.search.queries if stats else 0,
        "qrels": stats.search.qrels if stats else 0,
    }
    english = {
        "documents": "one document — title, type, layout, parties, paths to its artifacts",
        "pages": "one page — page text and the relative path of its PNG",
        "qa": "one QA pair — answer in typed columns plus the raw `answer_json`",
        "elements": "one element — text, structural citation, page, bounding boxes",
        "passages": "one retrieval passage",
        "queries": "one retrieval query",
        "qrels": "one relevance judgement — grade 2 = answer-bearing, 1 = related",
    }
    for name, path, _ in main_configs(spec):
        add(f"| `{name}` | {_n(counts.get(name, 0))} | {english[name]} | `{path}` |\n")
    add(
        "\n```python\nfrom datasets import load_dataset\nfrom huggingface_hub import snapshot_download\n\n"
        f'pages = load_dataset("{spec.hub.repo_id}", "pages", split="train")\n'
        f'root  = snapshot_download("{spec.hub.repo_id}", repo_type="dataset")\n'
        "\n# `image` is a path relative to the repository root, so join it with the download:\n"
        "png = f\"{root}/{pages[0]['image']}\"      # 150 dpi PNG of that page\n"
        'txt = pages[0]["text"]                    # its ground-truth text\n'
        "```\n\n"
        "The per-document directories hold the **authoritative** ground truth "
        "(`source.json`, `layout.json`, `answer.json`, `qa.json`, `elements.jsonl`, `doc.pdf`, "
        "`pages/*.png`); the three files under `views/` are flat projections for the viewer.\n\n"
    )
    add("## Files\n\n")
    tree = [
        "manifest.json          every document (pages, QA count, artifacts, checksums, status)",
        f"{CARD_NAME}           full data card: measured scale, breakdown, QA, limits and biases",
        "SHA256SUMS             checksums of everything distributed here",
    ]
    if not spec.search_split:
        tree.append("search/                retrieval evaluation set (one layout per written contract)")
    tree += [
        "views/                 flat jsonl projections for the dataset viewer",
        "licenses/              font licenses for the faces embedded in the PDFs",
        "<content_id>--<style_id>/",
        "  doc.pdf  pages/page-001.png …  source.json  layout.json  answer.json  qa.json",
        "  elements.jsonl  passages.jsonl",
    ]
    add("```\n" + "\n".join(tree) + "\n```\n\n")
    if spec.search_split:
        add(
            "The corpus-wide **retrieval evaluation set** (passages / queries / qrels) is published as a "
            f"separate dataset: {spec.search_ref_en}. Its `passage_id` is `<doc_id>::<element_id>`, so it "
            "joins back to the documents here. Each document directory still carries its own "
            "`passages.jsonl`, so that set can be rebuilt or extended from this repository alone.\n\n"
        )
    add(
        f"Read **`{CARD_NAME}`** next: it is generated by measuring these files and holds the scale, "
        "the per-type breakdown, the label vocabulary, the quality-assurance results, and the known "
        "limits and biases.\n\n"
    )
    if spec.code_repo:
        add(f"Generator code: {spec.code_repo}\n\n")
    add("## Citation\n\n")
    add(_citation(spec))

    # ---- 日本語（ファイルの読み方） -----------------------------------------
    add("\n---\n\n")
    add("# 日本語版 — 生成した契約書データセットの読み方\n\n")
    if spec.pretty_name_ja:
        add(f"**{spec.pretty_name_ja}**\n\n")
    add(
        "**このファイルは `keiyaku publish`（`keiyaku export` からも呼ばれる）が生成する。"
        "手で編集しない**（CLAUDE.md §0.4-3）。仕様は `docs/publishing.md`（公開の形）と "
        "`docs/evaluation.md`（予測の形と採点）、データの素性は `"
        f"{CARD_NAME}`。\n\n"
    )
    add(f"- {_license_line_ja(spec)}\n")
    add("- **実務の契約書としては使えない**（法律専門家の校閲を受けていないダミーである）。\n")
    add("- 会社名・人物名・住所・金額・契約書番号はすべて架空で、実在のひな型を転載していない。\n")
    add("- **AI モデルの学習・蒸留には使えない**（次節）。評価・ベンチマークは対象外。\n")
    if spec.search_split:
        add(
            "- **検索評価セット（passages / queries / qrels）は別のデータセットで配布している**："
            f"{spec.search_ref_ja}。文書そのものはこのリポジトリにある。\n"
        )
    add("\n")
    add("## \u26a0 AI モデルの学習・蒸留には使えない\n\n")
    add(NO_TRAINING_JA + "\n\n")
    add("## 並び\n\n")
    add(
        "```\n"
        "dataset/\n"
        f"  README.md                このファイル（Hub のデータセットカード）\n"
        f"  {CARD_NAME}             **データカード**"
        "（規模・内訳・作り方・品質保証・制限と偏り・ライセンス）\n"
        "  manifest.json            全文書の一覧（ページ数・QA 数・成果物・checksums・status）\n"
        f"  {SUMS_NAME}             配布するファイルの SHA256\n"
        + (
            ""
            if spec.search_split
            else "  search/                  検索評価セット（コーパス全体。content ごとに 1 スタイル）\n"
            "    passages.jsonl           検索エンジンに登録する単位\n"
            "    queries.jsonl            クエリ（term / heading / scoped / qa）\n"
            "    qrels.jsonl              適合判定（grade 2 = 答えがある / 1 = 関連する）\n"
        )
        + f"  {VIEWS_DIR}/                   "
        "**Viewer と `load_dataset()` のための平らな面**（一次資料の射影）\n"
        "    documents.jsonl          1 行 1 文書\n"
        "    pages.jsonl              1 行 1 ページ（ページ本文と PNG の相対パス）\n"
        "    qa.jsonl                 1 行 1 問（答えは型ごとの列＋生の `answer_json`）\n"
        f"  {LICENSES_DIR}/                PDF に埋め込まれているフォントのライセンス本文\n"
        "  <content_id>--<style_id>/\n"
        "    doc.pdf                  PDF（フォント埋め込み・テキスト層あり）\n"
        "    pages/page-001.png …     150dpi のページ画像（VLM の入力）\n"
        "    source.json              内容＋構造＋意味（レイアウト非依存）＋ derived\n"
        "    layout.json              描画結果（ページ・要素の bbox・読み順・ヘッダ/フッタ）\n"
        "    answer.json              ページ別テキスト ＋ outline（**source と layout は内包しない**）\n"
        f"    qa.json                  {_qa_per_doc(stats)}（自動＋執筆。内訳は {CARD_NAME} §5.5）\n"
        "    elements.jsonl           **1 行 1 要素の平らな索引。評価スクリプトはまずこれを読む**\n"
        "    passages.jsonl           この文書ぶんの検索パッセージ\n"
        "```\n\n"
        "**`render.html`（デバッグ用の中間 HTML）は配布しない**（CLAUDE.md §1.1）。\n\n"
    )
    add("## どのファイルを使うか\n\n")
    add(
        "| やりたいこと | 読むファイル |\n|---|---|\n"
        "| ページ画像から本文を読み取る精度 | `pages/*.png` ＋ `answer.json` の `pages[].text` |\n"
        "| 文章の**構造内の位置づけ**（第2章 第1条 (1)） | "
        "`elements.jsonl` の `citation` / `node_kind` / `path_ids` |\n"
        "| 見出しツリー | `answer.json` の `outline`（`kind` / `parent_id` / `citation` つき） |\n"
        "| 表の構造 | `source.json` の `grid` ＋ `derived.tables[].header_path` / `records` |\n"
        "| 図の構造 | `derived.figures[].graph`（6 種共通の nodes / edges）＋ `paths` |\n"
        "| 列挙の「N 番目」 | `derived.enumerations` |\n"
        "| 読み順 | `layout.json` の `pages[].reading_order`"
        "（**内容の単位**。ラベルと本文の内訳は含まない） |\n"
        + (
            f"| 検索の評価 | **別データセット** {spec.search_ref_ja}"
            "（`passages.jsonl` ＋ `queries.jsonl` ＋ `qrels.jsonl`） |\n"
            if spec.search_split
            else "| 検索の評価 | `search/passages.jsonl` ＋ `queries.jsonl` ＋ `qrels.jsonl` |\n"
        )
        + f"| 一覧・絞り込み（Viewer） | `{VIEWS_DIR}/documents.jsonl` / `pages.jsonl` / `qa.jsonl` |\n\n"
    )
    add("## 注意点\n\n")
    add(
        "- **`answer.json` は `source` と `layout` を内包しない。** 同じディレクトリに実体があるので\n"
        "  参照で足りる（内包すると同じ正解が 3 か所に並び、どれが正か分からなくなる）。\n"
        "  3 つをまとめて扱いたいときは `keiyaku.answer.load_answer(dataset_dir)` を使う。\n"
        "- **座標は pt・原点は左上。** `elements.jsonl` には正規化 [0,1] の `bboxes_norm` も入れてある。\n"
        "  PNG は 150dpi なので、pt × 150/72 でピクセル座標になる。\n"
        "- **繰り返し表頭とヘッダ/フッタは PDF のテキスト層に何度も出る。**\n"
        "  `answer.json` の `pages[].text` からは除いてある（`text_with_furniture` が除く前）。\n"
        "  `elements.jsonl` の `repeated` が true の fragment は表頭の再掲。\n"
        "- **段組では 1 つの要素が複数の fragment に割れる。** `bboxes` は配列。\n"
        f"- **同じ content を {_layouts_per_content(stats)} 通りの版面で描いた文書がある。** "
        "本文は同一で版面だけが違うので、\n"
        "  レイアウト頑健性の評価に使える。"
        "**検索コーパスは重複を避けて content ごとに 1 スタイルだけ**採っている。\n"
        f"- **`{VIEWS_DIR}/qa.jsonl` の答えは型ごとに列が分かれている**（`answer_text` / `answer_number` /\n"
        "  `answer_list`）。**採点に使う正本は各文書の `qa.json` の `answer`** で、views はその射影である\n"
        "  （Arrow が 1 列に複数の型を入れられないため。`docs/publishing.md` §4）。\n"
        + (
            f"- **qrels の扱い（grade 1 の打ち切りを含む）は別データセットのカードに書いてある**：\n"
            f"  {spec.search_ref_ja}。\n"
            if spec.search_split
            else "- **qrels の grade 1 は 1 クエリ "
            f"{_n(stats.search.related_cap) if stats and stats.search.related_cap else '一定件数'}"
            " で打ち切ってある。** 打ち切ると qrels に出ないので\n"
            "  評価上は非適合と同じ扱いになる。どのクエリで切ったかは `queries.jsonl` の\n"
            f"  `related_truncated` と `n_related_total` でわかる（現行の生成では {_n(n_queries)} クエリ中\n"
            f"  {_n(n_truncated)} 件{truncated_examples}）。**この件数で Recall@k を解釈しない。**\n"
        )
        + "- すべて架空の会社・商品である（各文書の奥付に明記）。\n\n"
    )
    fonts = _embedded_font_names(stats)
    if fonts:
        add(
            "- **PDF にはフォントが埋め込まれている**（実測："
            + "、".join(f"`{n}`" for n in fonts)
            + f"）。ライセンス本文は `{LICENSES_DIR}/` に同梱してある。\n\n"
        )
    add("## 採点\n\n")
    add(
        "```\n"
        "uv run keiyaku eval dataset/<doc_id> --pred pred.json     # 読み取り\n"
        "uv run keiyaku eval --search-run run.json                 # 検索\n"
        "uv run keiyaku eval dataset/<doc_id> --oracle             # ハーネスの自己評価\n"
        "uv run keiyaku eval dataset/<doc_id> --oracle --misread 0.3   # 現実の読み取り誤りで崩して採点\n"
        "```\n"
    )
    if spec.code_repo:
        add(f"\n採点ハーネスを含む生成コード：{spec.code_repo}\n")
    return "".join(parts)


def write_readme(
    dataset_dir: Path,
    queries: Sequence[Any] = (),
    stats: DataCardStats | None = None,
    spec: PublishSpec | None = None,
) -> Path:
    """`dataset/README.md`（Hub のデータセットカード）を書き出す。

    **README の所有者はこの関数**である（`keiyaku export` はこれを呼ぶ）。
    `queries` を渡さなければ `dataset/search/queries.jsonl` から実測する。
    """
    spec = spec if spec is not None else load_spec()
    if stats is None and (dataset_dir / "manifest.json").is_file():
        stats = collect(dataset_dir)
    n_queries, n_truncated, examples = _query_facts(dataset_dir, queries, spec.search_dataset.dir)
    text = render_card(spec, stats, n_queries=n_queries, n_truncated=n_truncated, truncated_examples=examples)
    dataset_dir.mkdir(parents=True, exist_ok=True)
    path = dataset_dir / "README.md"
    path.write_text(text, encoding="utf-8")
    return path


# --- 検索評価セットのカード（別データセット） ---------------------------------


def _md_table(header: Sequence[str], rows: Sequence[Sequence[str]]) -> str:
    out = ["| " + " | ".join(header) + " |", "|" + "|".join("---" for _ in header) + "|"]
    out += ["| " + " | ".join(row) + " |" for row in rows]
    return "\n".join(out) + "\n"


def _count_rows(rows: Sequence[Any]) -> list[list[str]]:
    """`datacard.CountRow` の並びを「名前 / 件数」の表にする（**数は実測のまま**）。"""
    return [[f"`{row.name}`", _n(row.items)] for row in rows]


def jsonl_fields(path: Path) -> list[str]:
    """jsonl の列名を**実測する**（スキーマを固定文字列で書くと生成器と食い違う）。"""
    if not path.is_file():
        return []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                return sorted(json.loads(line).keys())
    return []


def search_fields(search_dir: Path) -> dict[str, list[str]]:
    return {name: jsonl_fields(search_dir / path) for name, path, _ in SEARCH_CONFIGS}


def search_frontmatter(spec: PublishSpec, stats: DataCardStats | None) -> str:
    """検索評価セットのカード冒頭の YAML。

    `configs` は**このリポジトリのルートからの相対**（`dataset/search/` が root）。
    `source_datasets` は本体のデータセットを指す（Hub の `extended|<repo_id>` の形）。
    """
    sd = spec.search_dataset
    data: dict[str, Any] = {
        "pretty_name": sd.pretty_name,
        "language": list(spec.language),
        "multilinguality": spec.multilinguality,
        "annotations_creators": list(spec.annotations_creators),
        "source_datasets": (
            [f"extended|{spec.hub.repo_id}"] if spec.hub.repo_id else list(spec.source_datasets)
        ),
        "task_categories": list(sd.task_categories or spec.task_categories),
        "task_ids": list(sd.task_ids),
        "tags": list(sd.tags or spec.tags),
        "size_categories": [_size_category(stats.search.passages if stats else 0)],
        "configs": [
            {"config_name": name, "data_files": [{"split": "train", "path": path}]}
            for name, path, _ in SEARCH_CONFIGS
        ],
    }
    if spec.license.decided:
        data = {"license": spec.license.id, **data}
    body = yaml.safe_dump(data, allow_unicode=True, sort_keys=False, default_flow_style=False, width=1000)
    return f"---\n{body}---\n"


def _search_citation(spec: PublishSpec) -> str:
    sd = spec.search_dataset
    key = (sd.hub.repo_id or "contract_retrieval").split("/")[-1].replace("-", "_")
    authors = " and ".join(spec.citation.authors) or (
        spec.hub.repo_id.split("/")[0] if spec.hub.repo_id else ""
    )
    url = sd.hub_url or spec.hub_url
    return (
        "```bibtex\n"
        f"@misc{{{key},\n"
        f"  title  = {{{sd.pretty_name}}},\n"
        f"  author = {{{authors}}},\n"
        f"  year   = {{{spec.citation.year or ''}}},\n"
        "  howpublished = {Hugging Face Hub},\n"
        f"  url    = {{{url}}}\n"
        "}\n"
        "```\n"
    )


def render_search_card(
    spec: PublishSpec,
    stats: DataCardStats | None,
    fields: dict[str, list[str]],
) -> str:
    """`dataset/search/README.md`（= 検索評価セットのデータセットカード）を組み立てる。

    数値・列名はすべて実測（`stats.search` と `fields`）から入れる。**焼き込まない。**
    文書そのものは本体のデータセットにあるので、両方向の案内を必ず書く
    （片方だけを見た人が `passage_id` の指す先を見つけられるようにする）。
    """
    sd = spec.search_dataset
    search = stats.search if stats else None
    parts: list[str] = [search_frontmatter(spec, stats)]
    add = parts.append
    passages = search.passages if search else 0
    queries = search.queries if search else 0
    qrels = search.qrels if search else 0
    main_ref = f"[`{spec.hub.repo_id}`]({spec.hub_url})" if spec.hub.repo_id else "the document dataset"

    # ---- 英語 ---------------------------------------------------------------
    add(f"\n# {sd.pretty_name}\n\n")
    add(
        f"**A retrieval evaluation set over fully synthetic Japanese business contracts** — "
        f"{_n(passages)} passages, {_n(queries)} queries and {_n(qrels)} relevance judgements. "
        "The passages are cut along the real structure of each contract (article, paragraph, "
        "table, figure, defined term), not by a fixed window, and the judgements are **derived "
        "from the generator's ground truth**, not from human pooling.\n\n"
    )
    add(
        f"- The documents themselves (PDF, 150 dpi page images, clause trees, tables, figures, QA) "
        f"are in the companion dataset: {main_ref}.\n"
        "- `passage_id` is `<doc_id>::<element_id>`, so every passage joins back to a document "
        "and to its `elements.jsonl` row there.\n"
        f"- The corpus takes **one layout per written contract** "
        f"({_n(search.corpus_documents) if search else 0} documents / "
        f"{_n(search.corpus_contents) if search else 0} contracts) — two renderings of the same "
        "body would be duplicates for retrieval.\n"
        f"- {_license_line_en(spec)}\n\n"
    )
    add("## \u26a0 Not for training AI models\n\n")
    add(NO_TRAINING_EN.split("\n", 2)[2].strip() + "\n\n")

    add("## What it is for\n\n")
    add(
        "1. Retrieval evaluation on Japanese legal/contract text (BM25, dense, hybrid, rerankers).\n"
        "2. **RAG evaluation**: whether the passage that actually carries the answer is retrieved "
        "(`grade 2`), as opposed to a merely related clause (`grade 1`).\n"
        "3. Structure-aware retrieval: passages carry their citation (`第2章 第1条`), kind, pages, "
        "parties, outgoing references and defined terms used, so recall can be sliced by structure.\n\n"
    )
    add("## What it is **not** for\n\n")
    add(
        "- **Any real-world legal use.** The clauses are dummies written for reading evaluation.\n"
        "- **Training, fine-tuning or distilling any AI / ML model** (see the section above; this is a "
        "restriction from Anthropic's Usage Policy, not from the dataset license).\n"
        "- Measuring absolute retrieval difficulty: the corpus is small and deliberately homogeneous "
        "(10 contract types, all synthetic, all born-digital Japanese text).\n\n"
    )
    add("## Configs\n\n")
    counts = {"passages": passages, "queries": queries, "qrels": qrels}
    english = {
        "passages": "one retrieval unit — a clause, table, figure or defined term, with its citation",
        "queries": "one query, with how many relevant passages it has",
        "qrels": "one relevance judgement — grade 2 = answer-bearing, 1 = related",
    }
    add(
        _md_table(
            ["config", "rows", "what one row is", "file"],
            [[f"`{name}`", _n(counts[name]), english[name], f"`{path}`"] for name, path, _ in SEARCH_CONFIGS],
        )
    )
    add(
        "\n```python\nfrom datasets import load_dataset\n\n"
        f'passages = load_dataset("{sd.hub.repo_id}", "passages", split="train")\n'
        f'queries  = load_dataset("{sd.hub.repo_id}", "queries",  split="train")\n'
        f'qrels    = load_dataset("{sd.hub.repo_id}", "qrels",    split="train")\n'
        "```\n\n"
    )
    add("## Fields\n\n")
    add(
        _md_table(
            ["file", "columns (measured)"],
            [
                [f"`{path}`", ", ".join(f"`{c}`" for c in fields.get(name, [])) or "(not generated yet)"]
                for name, path, _ in SEARCH_CONFIGS
            ],
        )
    )
    add("\n")
    # 打ち切りは Recall@k の読み方を変えるので、英語面にも出す（日本語面だけに置かない）
    add("## Caveats\n\n")
    add(
        f"- **`grade 1` is capped at {_n(search.related_cap) if search and search.related_cap else 0} "
        "judgements per query.** Beyond the cap a related passage simply does not appear in `qrels`, "
        "so scoring treats it as non-relevant. `queries.jsonl` carries `related_truncated` and "
        f"`n_related_total`; {_n(search.truncated) if search else 0} of {_n(queries)} queries are "
        "capped. **Do not read Recall@k as if the cap were not there** — use `grade 2` "
        "(answer-bearing) for strict scoring.\n"
        "- **One layout per written contract.** The document dataset renders some contracts in two "
        "page layouts; retrieval would see them as duplicates, so only one is in this corpus.\n"
        "- Queries are generated from the ground truth (defined terms, headings, scoped questions and "
        "QA pairs), not written by human searchers, so phrasing is cleaner than real user queries.\n\n"
    )

    # ---- 日本語 -------------------------------------------------------------
    add("\n---\n\n")
    add("# 日本語版 — 検索評価セットの読み方\n\n")
    if sd.pretty_name_ja:
        add(f"**{sd.pretty_name_ja}**\n\n")
    add(
        "**このファイルは `keiyaku publish` が生成する。手で編集しない**（CLAUDE.md §0.4-3）。"
        "仕様は `docs/publishing.md` §12、採点の指標は `docs/evaluation.md`。\n\n"
    )
    add(f"- {_license_line_ja(spec)}\n")
    add("- **AI モデルの学習・蒸留には使えない**（次節）。評価・ベンチマークは対象外。\n")
    add(
        f"- **文書そのもの（PDF・ページ画像・構造・QA）は別のデータセットにある**：{main_ref}。"
        "こちらはそのコーパスに対する passages / queries / qrels だけを持つ。\n\n"
    )
    add("## \u26a0 AI モデルの学習・蒸留には使えない\n\n")
    add(NO_TRAINING_JA + "\n\n")
    add("## 並び\n\n")
    add(
        "```\n"
        "passages.jsonl   検索エンジンに登録する単位（条・項・表・図・定義語。構造の切れ目で切ってある）\n"
        "queries.jsonl    クエリ（種別と、適合する件数）\n"
        "qrels.jsonl      適合判定（grade 2 = 答えがある / 1 = 関連する）\n"
        f"{SUMS_NAME}       このリポジトリで配布するファイルの SHA256\n"
        "```\n\n"
    )
    if search and search.available:
        add("## 実測（この版の中身）\n\n")
        add(_md_table(["パッセージの種別", "件数"], _count_rows(search.passage_kinds)))
        add("\n")
        add(_md_table(["クエリの種別", "件数"], _count_rows(search.query_kinds)))
        add("\n")
        add(_md_table(["適合判定", "件数"], _count_rows(search.grades)))
        add("\n")
    add("## 注意点\n\n")
    truncated_examples = (
        "（" + "・".join(f"「{q}」" for q in search.truncated_examples) + "）"
        if search and search.truncated_examples
        else ""
    )
    add(
        "- **`passage_id` は `<doc_id>::<element_id>`。** 本文・bbox・構造上の位置は文書側の\n"
        f"  `elements.jsonl`（{main_ref}）と突き合わせて引く。\n"
        "- **コーパスは content ごとに 1 スタイルだけ**採ってある。同じ本文を別の版面で描いた\n"
        "  文書は検索では重複になるため入れていない（版面の頑健性は文書側のデータセットで見る）。\n"
        f"- **grade 1 は 1 クエリ {_n(search.related_cap) if search and search.related_cap else '一定件数'}"
        " 件で打ち切ってある。** 打ち切られた分は qrels に出ないので\n"
        "  評価上は非適合と同じ扱いになる。どのクエリで切ったかは `queries.jsonl` の\n"
        "  `related_truncated` と `n_related_total` でわかる（現行の生成では "
        f"{_n(queries)} クエリ中 {_n(search.truncated) if search else 0} 件{truncated_examples}）。\n"
        "  **この件数で Recall@k を解釈しない。**\n"
        "- **grade 2 は「答えがある」パッセージ**で、grade 1 は「関連する」。"
        "nDCG などの指標は\n  この 2 段階を前提にしている（`docs/evaluation.md`）。\n"
        "- すべて架空の会社・契約である（文章は全文オリジナルで、実在のひな型を転載していない）。\n\n"
    )
    add("## 採点\n\n")
    add(
        "```\n"
        "uv run keiyaku eval --search-run run.json   # recall@k / nDCG@k ほか（docs/evaluation.md §4）\n"
        "```\n"
    )
    if spec.code_repo:
        add(f"\n採点ハーネスを含む生成コード：{spec.code_repo}\n")
    add("\n## Citation\n\n")
    add(_search_citation(spec))
    return "".join(parts)


def write_search_card(
    dataset_dir: Path, spec: PublishSpec, stats: DataCardStats | None = None
) -> Path | None:
    """`dataset/search/README.md` を書き出す（切り出していないときは作らない）。"""
    if not spec.search_split:
        return None
    search_dir = dataset_dir / spec.search_dataset.dir
    if not search_dir.is_dir():
        return None
    path = search_dir / "README.md"
    path.write_text(render_search_card(spec, stats, search_fields(search_dir)), encoding="utf-8")
    return path


# --- git / ライセンス / チェックサム -------------------------------------------


def gitattributes(spec: PublishSpec) -> str:
    lines = [
        "# Hugging Face Hub 用。`keiyaku publish` が生成する（docs/publishing.md §5）。",
        "# PDF と PNG は LFS に入れる。jsonl / json は 1 ファイルが小さく、diff が見えるほうが価値が高い。",
    ]
    lines += [f"{pattern} filter=lfs diff=lfs merge=lfs -text" for pattern in spec.lfs]
    return "\n".join(lines) + "\n"


def gitignore(spec: PublishSpec) -> str:
    lines = [
        "# 配布しないもの（`specs/publish.yaml` の exclude が正本）。",
        "# render.html はデバッグ用の中間 HTML で配布対象外（CLAUDE.md §1.1）。",
    ]
    lines += [p for p in spec.exclude if p != ".gitignore"]
    return "\n".join(lines) + "\n"


def write_licenses(dataset_dir: Path, spec: PublishSpec, stats: DataCardStats | None) -> list[Path]:
    """`licenses/` に **実際に埋め込まれていたフォント**のライセンス本文と NOTICE を置く。"""
    out: list[Path] = []
    target = dataset_dir / LICENSES_DIR
    target.mkdir(parents=True, exist_ok=True)
    embedded = _embedded_font_names(stats)
    wanted: list[tuple[str, str]] = []
    for prefix, filename, label in FONT_LICENSES:
        if any(name.startswith(prefix) for name in embedded):
            wanted.append((filename, label))
    for filename, _ in wanted:
        source = FONTS_DIR / filename
        if source.is_file():
            path = target / filename
            path.write_bytes(source.read_bytes())
            out.append(path)

    notice = ["# NOTICE\n\n"]
    notice.append(
        "このデータセットの PDF には、本文を表示するためのフォントのサブセットが埋め込まれている。\n"
        "The PDFs in this dataset embed subsets of the following fonts.\n\n"
    )
    if embedded:
        notice.append("| 埋め込まれていたフォント / embedded face | ライセンス / license |\n|---|---|\n")
        for name in embedded:
            label = next((lbl for pre, _, lbl in FONT_LICENSES if name.startswith(pre)), "（要確認）")
            notice.append(f"| `{name}` | {label} |\n")
        notice.append(
            "\nライセンス本文は同じディレクトリに置いてある（The license texts are in this directory）。\n"
        )
    notice.append(
        "\n本文・表・図・当事者名はすべてオリジナルに書いた架空の文章であり、"
        "実在の契約書ひな型・標準契約書・モデル契約書を転載していない。\n"
        "All sentences, tables, figures and party names are original and fictional; "
        "no real contract template is reproduced here.\n"
    )
    notice.append(
        "\n**AI モデルの学習・蒸留には使えない**（本文は Claude の Output であり、"
        f"Anthropic Usage Policy が事前許可なしの学習を禁じている。{AUP_URL}）。"
        "評価・ベンチマークは対象外。詳細は README.md と LICENSE。\n"
        "**Not for training AI models** — see README.md and LICENSE. Evaluation is not training.\n"
    )
    if spec.license.decided:
        notice.append(f"\n生成物のライセンス / dataset license: **{spec.license.id}**\n")
    else:
        notice.append(
            "\n生成物の配布条件は未決（The redistribution terms of the generated files are not "
            "decided yet; see README.md）。\n"
        )
    path = target / "NOTICE.md"
    path.write_text("".join(notice), encoding="utf-8")
    out.append(path)
    return out


#: 学習・蒸留の禁止の出どころ。本データセットの本文・QA・図の説明は Claude Code セッション内で
#: Claude（Anthropic）が書いた Output であり、AUP は「入力と出力を AI モデルの学習
#: （model scraping / model distillation を含む）に用いること」を事前許可なしに禁じている。
AUP_URL = "https://www.anthropic.com/legal/aup"

#: `dataset/LICENSE` と カードの英語面に出す禁止の告知。
#: **ライセンス条件ではない。** CC BY 系は下流への追加制限を禁じている（CC BY 4.0 第 2 条(a)(5)(B)）
#: ので、付与条件として書くと違反になる。出どころ（AUP）と拘束の相手を明示した「告知」にとどめる。
#: **「評価は学習ではない」を必ず併記する**——落とすとこのデータセットの目的まで禁じられたように読める。
NO_TRAINING_EN = f"""NOT FOR TRAINING AI MODELS
--------------------------
THIS DATASET MUST NOT BE USED TO TRAIN, FINE-TUNE, DISTILL, OR OTHERWISE DEVELOP
ANY ARTIFICIAL INTELLIGENCE OR MACHINE LEARNING MODEL, INCLUDING LARGE LANGUAGE
MODELS (LLMs) AND VISION-LANGUAGE MODELS (VLMs).

The clauses, tables, figure descriptions and QA pairs in this dataset were written
by Claude (Anthropic) inside a Claude Code session; they are Outputs of that
service. Anthropic's Usage Policy prohibits "Utilization of inputs and outputs to
train an AI model (e.g., 'model scraping' or 'model distillation') without prior
authorization from Anthropic" ({AUP_URL}).

EVALUATION IS NOT TRAINING. Benchmarking or evaluating document-reading systems
(OCR, layout analysis, VLMs, structured extraction), retrieval and RAG pipelines,
or AI agents against this dataset is the purpose it was built for, and nothing
above restricts it. Neither does using it as test fixtures, as few-shot examples,
or as a retrieval corpus at inference time. What is excluded is updating model
weights from it.

This is a NOTICE, not an additional condition of the license above. CC BY 4.0
Section 2(a)(5)(B) forbids imposing further restrictions on downstream recipients,
so this statement is not offered as a term of that grant and does not narrow it.
It tells you about a restriction that arises from Anthropic's Usage Policy and
that binds everyone subject to that policy. If you need to train on data of this
kind, obtain prior authorization from Anthropic first."""

#: カードの日本語面に出す同じ告知。英語面（`NO_TRAINING_EN`）と**対で直す**。
NO_TRAINING_JA = f"""**本データセットを LLM・VLM・その他 AI モデルの学習・ファインチューニング・蒸留・
強化学習の素材に使ってはならない。**

本データセットの条文・表・図の説明・QA は、Claude Code セッション内で **Claude（Anthropic）が
書いた Output** である。Anthropic の Usage Policy は「入力と出力を AI モデルの学習
（model scraping・model distillation を含む）に用いること」を**事前許可なしに禁じている**
（{AUP_URL}）。学習に使う必要がある場合は、まず Anthropic の事前許可を得ること。

**評価は学習ではない。** ドキュメント読み取り（OCR・レイアウト解析・VLM・構造化抽出）・
検索／RAG・AI エージェントの**評価とベンチマークは、このデータセットが作られた目的そのもの**で、
上の制限は一切かからない。テストフィクスチャとしての利用、few-shot の実例、
推論時の検索コーパスとしての利用も同じく対象外である。**除かれるのはモデルの重みを更新する用途だけ。**

なお、**この節は告知であってライセンス条件ではない。** CC BY 4.0 は下流の受領者に追加の制限を
課すことを禁じている（第 2 条(a)(5)(B)）ため、上の禁止を CC BY の付与条件として書くことはできず、
書いてもいない。制限の出どころは Anthropic の Usage Policy であり、同ポリシーの適用を受ける者を縛る。"""


#: 既知のライセンス本文への案内（Hub の license タグ → URL）
LICENSE_URLS: dict[str, str] = {
    "cc-by-4.0": "https://creativecommons.org/licenses/by/4.0/legalcode",
    "cc-by-sa-4.0": "https://creativecommons.org/licenses/by-sa/4.0/legalcode",
    "cc-by-nc-4.0": "https://creativecommons.org/licenses/by-nc/4.0/legalcode",
    "cc0-1.0": "https://creativecommons.org/publicdomain/zero/1.0/legalcode",
    "apache-2.0": "https://www.apache.org/licenses/LICENSE-2.0",
    "mit": "https://opensource.org/license/mit",
}


def write_license_file(
    dataset_dir: Path, spec: PublishSpec, *, title: str = "", fonts: bool = True
) -> Path | None:
    """`<repo>/LICENSE`。**決まっていなければ作らない**（嘘の条件を置かない）。

    検索評価セットのリポジトリ（`fonts=False`）には PDF が無いので、
    フォントの案内（存在しない `licenses/NOTICE.md` への参照）を書かない。
    """
    path = dataset_dir / "LICENSE"
    if not spec.license.decided:
        if path.is_file():
            path.unlink()
        return None
    holder = f"Copyright (c) {spec.license.year} {spec.license.holder}".strip()
    url = LICENSE_URLS.get(spec.license.id, "")
    kinds = "PDF, JSON, JSONL, PNG" if fonts else "JSONL"
    lines = [
        title or spec.pretty_name,
        "",
        holder,
        "",
        f"The generated files in this repository ({kinds}) are licensed under {spec.license.id}.",
    ]
    if url:
        lines.append(f"Full license text: {url}")
    lines.append("")
    if fonts:
        lines += [
            "The PDFs embed subsets of third-party fonts; see licenses/NOTICE.md for their terms.",
            "",
        ]
    lines.append(NO_TRAINING_EN)
    if spec.license.note:
        lines += ["", spec.license.note]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def _excluded(rel: str, patterns: Sequence[str]) -> bool:
    name = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(rel, p) for p in patterns)


def _files_under(root: Path, spec: PublishSpec, skip_dirs: Sequence[str] = ()) -> list[Path]:
    out: list[Path] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = _rel(path, root)
        if rel == SUMS_NAME or _excluded(rel, spec.exclude):
            continue
        if rel.split("/", 1)[0] in skip_dirs:
            continue
        out.append(path)
    return out


def distributed_files(dataset_dir: Path, spec: PublishSpec) -> list[Path]:
    """本体のリポジトリで配布するファイル（`exclude` と `SHA256SUMS` 自身を除く）。並びは決定論。

    検索評価セットを切り出しているときは、その**ディレクトリごと除く**
    （別リポジトリで配るので、二重に配らない。`docs/publishing.md` §12）。
    """
    skip = (spec.search_dataset.dir,) if spec.search_split else ()
    return _files_under(dataset_dir, spec, skip)


def search_distributed_files(dataset_dir: Path, spec: PublishSpec) -> list[Path]:
    """検索評価セットのリポジトリで配布するファイル（`dataset/search/` がそのルート）。"""
    if not spec.search_split:
        return []
    search_dir = dataset_dir / spec.search_dataset.dir
    return _files_under(search_dir, spec) if search_dir.is_dir() else []


def _checksum_lines(root: Path, files: Sequence[Path]) -> str:
    """`sha256sum` と同じ書式（`<hex>  <path>`）。パスは `root` からの相対。"""
    lines: list[str] = []
    for path in files:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1 << 20), b""):
                digest.update(chunk)
        lines.append(f"{digest.hexdigest()}  {_rel(path, root)}")
    return "\n".join(lines) + "\n" if lines else ""


def checksums(dataset_dir: Path, spec: PublishSpec) -> str:
    return _checksum_lines(dataset_dir, distributed_files(dataset_dir, spec))


def search_checksums(dataset_dir: Path, spec: PublishSpec) -> str:
    return _checksum_lines(dataset_dir / spec.search_dataset.dir, search_distributed_files(dataset_dir, spec))


# --- まとめ -------------------------------------------------------------------


class PublishResult(Model):
    views: ViewCounts = Field(default_factory=ViewCounts)
    files: int = 0
    bytes: int = 0
    license_id: str = UNDECIDED
    #: 検索評価セットを別データセットとして出した場合の公開先と量（切り出していなければ空）
    search_repo: str = ""
    search_files: int = 0
    search_bytes: int = 0
    #: 公開をふさいでいる条件（人間の判断待ちなど）。**空でなければアップロードしない**
    blockers: list[str] = Field(default_factory=list)
    written: list[str] = Field(default_factory=list)


def blockers(spec: PublishSpec) -> list[str]:
    """公開をふさいでいる条件（AI が決めてはいけないもの）。"""
    out: list[str] = []
    if not spec.license.decided:
        out.append(
            "生成物の配布条件が未決（`specs/publish.yaml` の `license.id`。HITL_TODO.md H13）"
            "——人間が決めるまでアップロードしない"
        )
    if not spec.hub.repo_id or "/" not in spec.hub.repo_id:
        out.append(
            "公開先が無い（`specs/publish.yaml` の `hub.repo_id` を `owner/name` の形で書く。"
            "宣言そのものが無ければ既定で動いている）"
        )
    if spec.search_split and "/" not in spec.search_dataset.hub.repo_id:
        out.append(
            "検索評価セットの公開先が無い（`specs/publish.yaml` の `search_dataset.hub.repo_id` を "
            "`owner/name` の形で書く。別データセットとして出すと決めたので本体には入らない）"
        )
    return out


def publish(
    dataset_dir: Path, stats: DataCardStats | None = None, spec: PublishSpec | None = None
) -> PublishResult:
    """公開用の面を作り直す（一次資料は触らない）。"""
    spec = spec if spec is not None else load_spec()
    if stats is None and (dataset_dir / "manifest.json").is_file():
        stats = collect(dataset_dir)
    written: list[str] = []
    views = build_views(dataset_dir)
    written += [f"{VIEWS_DIR}/{n}.jsonl" for n in ("documents", "pages", "qa")]
    write_readme(dataset_dir, stats=stats, spec=spec)
    written.append("README.md")
    (dataset_dir / ".gitattributes").write_text(gitattributes(spec), encoding="utf-8")
    (dataset_dir / ".gitignore").write_text(gitignore(spec), encoding="utf-8")
    written += [".gitattributes", ".gitignore"]
    written += [_rel(p, dataset_dir) for p in write_licenses(dataset_dir, spec, stats)]
    license_path = write_license_file(dataset_dir, spec)
    if license_path:
        written.append("LICENSE")
    # 検索評価セットは**別のデータセット**として出す（`dataset/search/` がそのルート）。
    # 本体の SHA256SUMS より先に作る——あちらはこのディレクトリを数えないので順序に依存しないが、
    # 自分の SHA256SUMS は自分のカードと LICENSE を含める必要がある（`docs/publishing.md` §12）。
    search_files: list[Path] = []
    if spec.search_split:
        search_dir = dataset_dir / spec.search_dataset.dir
        card = write_search_card(dataset_dir, spec, stats)
        if card:
            written.append(_rel(card, dataset_dir))
            search_license = write_license_file(
                search_dir, spec, title=spec.search_dataset.pretty_name, fonts=False
            )
            if search_license:
                written.append(_rel(search_license, dataset_dir))
            (search_dir / SUMS_NAME).write_text(search_checksums(dataset_dir, spec), encoding="utf-8")
            written.append(f"{spec.search_dataset.dir}/{SUMS_NAME}")
            search_files = search_distributed_files(dataset_dir, spec)
    # SHA256SUMS は**最後**に作る（上で書いたファイルを含めるため）
    (dataset_dir / SUMS_NAME).write_text(checksums(dataset_dir, spec), encoding="utf-8")
    written.append(SUMS_NAME)
    files = distributed_files(dataset_dir, spec)
    return PublishResult(
        views=views,
        files=len(files) + 1,
        bytes=sum(p.stat().st_size for p in files),
        license_id=spec.license.id,
        search_repo=spec.search_dataset.hub.repo_id if spec.search_split else "",
        search_files=len(search_files) + 1 if search_files else 0,
        search_bytes=sum(p.stat().st_size for p in search_files),
        blockers=blockers(spec),
        written=written,
    )


def check(dataset_dir: Path, spec: PublishSpec | None = None) -> tuple[list[str], list[str]]:
    """**書き換えずに**鮮度を見る。返り値は（食い違い, 公開をふさぐ条件）。

    鮮度の食い違いだけが終了コード 1 の対象で、未決のライセンスは `make check` を赤くしない
    （`docs/publishing.md` §8）。
    """
    spec = spec if spec is not None else load_spec()
    problems: list[str] = []
    if not (dataset_dir / "manifest.json").is_file():
        return (
            [f"{dataset_dir}/manifest.json が無い（`keiyaku manifest update` を実行する）"],
            blockers(spec),
        )
    stats = collect(dataset_dir)

    expected: dict[str, str] = {
        "README.md": render_card(
            spec,
            stats,
            **dict(
                zip(
                    ("n_queries", "n_truncated", "truncated_examples"),
                    _query_facts(dataset_dir, (), spec.search_dataset.dir),
                    strict=True,
                )
            ),
        ),
        ".gitattributes": gitattributes(spec),
        ".gitignore": gitignore(spec),
    }
    search_dir = dataset_dir / spec.search_dataset.dir
    if spec.search_split and search_dir.is_dir():
        expected[f"{spec.search_dataset.dir}/README.md"] = render_search_card(
            spec, stats, search_fields(search_dir)
        )
    for name, text in expected.items():
        path = dataset_dir / name
        if not path.is_file():
            problems.append(f"{path} が無い（`keiyaku publish update` を実行する）")
        elif path.read_text(encoding="utf-8") != text:
            problems.append(f"{path} が現在の dataset/ と一致しない")

    for name, rows in (
        ("documents.jsonl", document_rows(dataset_dir)),
        ("pages.jsonl", page_rows(dataset_dir)),
        ("qa.jsonl", qa_rows(dataset_dir)),
    ):
        path = dataset_dir / VIEWS_DIR / name
        fresh = "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in rows)
        if not path.is_file():
            problems.append(f"{path} が無い（`keiyaku publish update` を実行する）")
        elif path.read_text(encoding="utf-8") != fresh:
            problems.append(f"{path} が現在の dataset/ と一致しない（{len(rows)} 行で作り直す）")

    license_paths = [dataset_dir / "LICENSE"]
    if spec.search_split and search_dir.is_dir():
        license_paths.append(search_dir / "LICENSE")
    for license_path in license_paths:
        if spec.license.decided and not license_path.is_file():
            problems.append(f"{license_path} が無い（ライセンスが決まっているので作る）")
        if not spec.license.decided and license_path.is_file():
            problems.append(f"{license_path} があるが `license.id` は未決（どちらかが古い）")

    # 本体と検索評価セットは別リポジトリなので SHA256SUMS も別々に持つ
    sums_targets: list[tuple[Path, str]] = [(dataset_dir / SUMS_NAME, checksums(dataset_dir, spec))]
    if spec.search_split and search_dir.is_dir():
        sums_targets.append((search_dir / SUMS_NAME, search_checksums(dataset_dir, spec)))
    for sums, _ in sums_targets:
        if not sums.is_file():
            problems.append(f"{sums} が無い（`keiyaku publish update` を実行する）")
    # README 等が古いと必ず SHA256SUMS も古いので、そちらを先に直す（二重報告を避ける）
    if not problems:
        for sums, fresh in sums_targets:
            if sums.read_text(encoding="utf-8") != fresh:
                problems.append(f"{sums} が現在の dataset/ と一致しない")
    return (problems, blockers(spec))
