"""Hugging Face 公開形の組み立て（docs/hf_publish.md）。

`dataset/`（生成物）は**そのまま公開できない**。ローカルの絶対パスを含む `render.html`、中間生成物
`_work/`、`__pycache__`、重複ファイルが入っている。ここでは**許可リストに挙げたものだけ**を別の
ディレクトリへコピーし、組み立てたあとに公開前ゲート P1〜P6 を全ファイルに掛ける。

- `dataset/` は読むだけで、書き換えない。
- 同じ入力なら同じ出力になる（時刻・乱数・集合の反復順に依存しない）。
- 実測値は `export.datacard.collect()` を通して採る（測り方を二重に実装しない）。
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from ..fictionalize import load_replacements
from .datacard import CARD_NAME, Agg, CardFacts, aggregate, collect

#: 公開形のファイル名（出力の直下）
README_NAME = "README.md"
NOTICE_NAME = "NOTICE.md"
GITATTRIBUTES_NAME = ".gitattributes"

#: ライセンス未決のときに frontmatter に書く値（HITL HC-3）
UNDECIDED_LICENSE = "other"
UNDECIDED_LICENSE_NAME = "undecided"

#: Anthropic Usage Policy の URL（学習・蒸留禁止の告知が引く）
AUP_URL = "https://www.anthropic.com/legal/aup"

#: カード・LICENSE・NOTICE・引用に出る名前。親プロジェクト（keiyaku-synth。HITL_TODO.md H16）と
#: 揃える（2026-10-12 決定）
COPYRIGHT_HOLDER = "Yusuke Shibui (shibuiwilliam)"
COPYRIGHT_YEAR = "2026"

#: 英語面の pretty_name。親 4 リポジトリと同じ "Japanese <domain> Document Understanding"
#: の命名規則に揃える（本文の日本語見出しは別に持つ）
PRETTY_NAME_EN = (
    "Japanese Contract Document Understanding — Calculation "
    "(synthetic, with ground-truth programs and test cases)"
)

#: 学習・蒸留の禁止（告知。日本語面）。親プロジェクト `keiyaku/publish.py` の `NO_TRAINING_JA` と
#: 同じ設計・同じ文面。**ライセンス条件ではなく告知**として書く
#: （CC BY 系を選んだ場合、第2条(a)(5)(B)が下流への追加制限を禁じているため）。
NO_TRAINING_JA = f"""## ⚠ AI モデルの学習・蒸留には使えない

**本データセットを LLM・VLM・その他 AI モデルの学習・ファインチューニング・蒸留・
強化学習の素材に使ってはならない。**

本データセットの契約書の条文・頭書・別紙・計算仕様の説明は、Claude Code セッション内で
**Claude（Anthropic）が書いた Output** である。Anthropic の Usage Policy は「入力と出力を
AI モデルの学習（model scraping・model distillation を含む）に用いること」を**事前許可なしに
禁じている**（{AUP_URL}）。学習に使う必要がある場合は、まず Anthropic の事前許可を得ること。

**評価は学習ではない。** 契約書の読み取り・計算条項の発見・正解プログラムの生成能力の
**評価とベンチマークは、このデータセットが作られた目的そのもの**で、上の制限は一切かからない。
テストフィクスチャとしての利用、few-shot の実例、推論時の検索コーパスとしての利用も同じく
対象外である。**除かれるのはモデルの重みを更新する用途だけ。**

なお、**この節は告知であってライセンス条件ではない。** 選んだライセンスが CC BY 系であれば、
下流の受領者に追加の制限を課すことを禁じている（第 2 条(a)(5)(B)）ため、上の禁止をその付与条件として
書くことはできず、書いてもいない。制限の出どころは Anthropic の Usage Policy であり、
同ポリシーの適用を受ける者を縛る。
"""

#: 同上・英語面。
NO_TRAINING_EN = f"""**Not for training AI models.** This dataset must not be used to train,
fine-tune, distill, or otherwise develop any AI/ML model (including LLMs and VLMs). The contract
clauses, calculation-spec explanations and task cards were written by Claude (Anthropic) inside a
Claude Code session; they are Outputs of that service, and Anthropic's Usage Policy prohibits
using inputs/outputs to train a model without prior authorization ({AUP_URL}). Evaluation is not
training — benchmarking systems against this dataset, using it as test fixtures, few-shot
examples, or a retrieval corpus at inference time is unrestricted; what is excluded is updating
model weights from it. This is a notice, not a license condition.
"""

#: 1 文書から `inputs/` へ持っていくもの（出題に渡すもの）
#: (出力名, dataset/<cid> からの相対パスの候補を返す関数のキー)
_INPUT_FILES = (
    ("contract.json", "contract"),
    ("layout.json", "layout"),
    ("calendar.json", "calendar"),
    ("tasks.jsonl", "tasks"),
)

#: 1 文書から `answers/` へ持っていくもの（正解）
_ANSWER_FILES = (
    ("spec.json", "calc/spec.json"),
    ("answer_key.json", "calc/answer_key.json"),
    ("patch.json", "calc/patch.json"),
    ("manifest.json", "calc/manifest.json"),
    ("cases.jsonl", "calc/cases.jsonl"),
)

#: 公開形に置く平索引（load_dataset 用）。(ファイル名, 正解を含むか)
_VIEWS = (
    ("documents.jsonl", False),
    ("rules.jsonl", False),
    ("tasks.jsonl", False),
    ("cases.jsonl", True),
)


@dataclass
class PublishResult:
    out_root: Path
    n_docs: int
    include_answers: bool
    license_id: str
    files: tuple[str, ...]
    total_bytes: int
    gates: tuple[tuple[str, bool, str], ...] = field(default=())

    @property
    def ok(self) -> bool:
        return all(passed for _, passed, _ in self.gates)


# --- 入力の所在 -------------------------------------------------------------------


def _render_dir(doc_dir: Path) -> Path | None:
    """`_render/<doc_id>/` を決定的に 1 つ選ぶ（フォールバックで 2 つある文書がある）。"""
    base = doc_dir / "_render"
    if not base.is_dir():
        return None
    cands = sorted(p for p in base.iterdir() if p.is_dir() and (p / "layout.json").is_file())
    return cands[0] if cands else None


def _pdf_path(doc_dir: Path) -> Path | None:
    cands = sorted(doc_dir.glob("*.pdf"))
    return cands[0] if cands else None


def _input_sources(doc_dir: Path) -> dict[str, Path | None]:
    rd = _render_dir(doc_dir)
    return {
        "contract": doc_dir / "contract.json",
        "layout": (rd / "layout.json") if rd else None,
        "calendar": doc_dir / "calc" / "calendar.json",
        "tasks": doc_dir / "calc" / "tasks.jsonl",
    }


# --- 平索引 -----------------------------------------------------------------------


def _dumps(value) -> str:
    """自由形式の値を JSON 文字列の列にする（Arrow の型推論が行ごとに揺れないように）。"""
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _sample_toggle(title: str, row: dict | None) -> list[str]:
    """1 行ぶんの実データを `<details>` で折りたたんで見せる。

    **先頭行を決定的に採る**（乱数も時刻も使わない。`CLAUDE.md` 守ること 3）。
    `row` が無ければ空リストを返す（カードが崩れた本文を持つより、節自体を省くほうがよい）。
    """
    if not row:
        return []
    body = json.dumps(row, ensure_ascii=False, indent=2, sort_keys=False)
    return [
        "",
        f"<details>\n<summary><b>{title}のサンプル1件</b></summary>",
        "",
        f"```json\n{body}\n```",
        "",
        "</details>",
        "",
    ]


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def _documents_rows(facts: CardFacts) -> list[dict]:
    rows = []
    for d in sorted(facts.docs, key=lambda x: x.content_id):
        pdf_name = d.pdf.name if d.pdf else None
        rows.append(
            {
                "content_id": d.content_id,
                "base_content_id": d.base_content_id,
                "doctype": d.doctype,
                "profile": d.profile,
                "calc_seed": d.calc_seed,
                "generator_version": d.generator_version,
                "style_id": d.style_id,
                "pages": d.pages,
                "page_size_mm": d.page_size_mm,
                "renderer": d.renderer,
                "n_rules": d.n_rules,
                "n_cases": d.n_cases,
                "n_tasks": d.n_tasks,
                "patterns": list(d.patterns),
                "challenge_type": d.challenge_type,
                "challenge_rule": d.challenge_rule,
                "chars": d.chars,
                "contract_file": f"inputs/{d.content_id}/contract.json",
                "pdf_file": f"inputs/{d.content_id}/{pdf_name}" if pdf_name else None,
                "layout_file": f"inputs/{d.content_id}/layout.json",
            }
        )
    return rows


def _rules_rows(facts: CardFacts) -> list[dict]:
    rows = []
    for d in sorted(facts.docs, key=lambda x: x.content_id):
        for r in d.rules:
            rows.append(
                {
                    "content_id": d.content_id,
                    "rule": r.rule,
                    "function": r.function,
                    "pattern": r.pattern,
                    "origin": r.origin,
                    "binding": r.binding,
                    "n_units": r.n_units,
                    "value_locations": list(r.value_locations),
                    "modalities": list(r.modalities),
                    "difficulty_json": _dumps(dict(r.difficulty)),
                    "has_examples": r.has_examples,
                }
            )
    return rows


def _read_jsonl(path: Path) -> list[dict]:
    if not path.is_file():
        return []
    out = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(json.loads(line))
    return out


def _tasks_rows(data_root: Path, facts: CardFacts) -> list[dict]:
    rows = []
    for d in sorted(facts.docs, key=lambda x: x.content_id):
        for t in _read_jsonl(data_root / d.content_id / "calc" / "tasks.jsonl"):
            rows.append(
                {
                    "content_id": d.content_id,
                    "task_id": t.get("task_id"),
                    "function": t.get("function"),
                    "title": t.get("title"),
                    "kind": t.get("kind"),
                    "task_json": _dumps(t),
                }
            )
    return rows


def _cases_rows(data_root: Path, facts: CardFacts) -> list[dict]:
    rows = []
    for d in sorted(facts.docs, key=lambda x: x.content_id):
        for c in _read_jsonl(data_root / d.content_id / "calc" / "cases.jsonl"):
            rows.append(
                {
                    "content_id": d.content_id,
                    "case_id": c.get("case_id"),
                    "function": c.get("function"),
                    "kind": c.get("kind"),
                    "inputs_json": _dumps(c.get("inputs")),
                    "expected_json": _dumps(c.get("expected")),
                    "tags": list(c.get("tags") or []),
                }
            )
    return rows


# --- カード -----------------------------------------------------------------------


def _font_licenses(g: Agg) -> list[tuple[str, list[str]]]:
    """実測した埋め込みフォント → ライセンス名でまとめる（data-card と同じ対応表を使う）。"""
    from .datacard import _FONT_LICENSE

    groups: dict[str, list[str]] = {}
    for font in sorted(g.embedded_fonts):
        name = next((lic for key, lic in _FONT_LICENSE if key in font), "ライセンス未同定")
        groups.setdefault(name, []).append(font)
    return sorted(groups.items())


def _size_category(n_rows: int) -> str:
    """HF の size_categories。データセットの**行数**で決める（文書数ではない）。"""
    bounds = (
        (1_000, "n<1K"),
        (10_000, "1K<n<10K"),
        (100_000, "10K<n<100K"),
        (1_000_000, "100K<n<1M"),
    )
    for limit, label in bounds:
        if n_rows < limit:
            return label
    return "1M<n<10M"


def _frontmatter(facts: CardFacts, g: Agg, *, license_id: str, include_answers: bool) -> list[str]:
    views = [name for name, needs_answers in _VIEWS if include_answers or not needs_answers]
    n_rows = max([g.n_docs, len(g.all_rules), g.n_tasks] + ([g.n_cases] if include_answers else []))
    size_cat = _size_category(n_rows)
    L = ["---"]
    L += [
        f"pretty_name: {json.dumps(PRETTY_NAME_EN, ensure_ascii=False)}",
        "language:",
        "- ja",
        f"license: {license_id}",
    ]
    if license_id == UNDECIDED_LICENSE:
        # HF のカード仕様では license: other に license_name と license_link が要る。
        # 未決なので、その旨を書いた NOTICE.md を指す。
        L.append(f"license_name: {UNDECIDED_LICENSE_NAME}")
        L.append(f"license_link: {NOTICE_NAME}")
    L += [
        f"size_categories:\n- {size_cat}",
        "task_categories:",
        "- document-question-answering",
        "- question-answering",
        "- text-generation",
        "tags:",
        "- japanese",
        "- contracts",
        "- synthetic",
        "- legal",
        "- code-generation",
        "- document-understanding",
        "- evaluation",
        "configs:",
    ]
    for name in views:
        L += [
            f"- config_name: {name.removesuffix('.jsonl')}",
            "  data_files:",
            "  - split: train",
            f"    path: data/{name}",
        ]
    L.append("---")
    return L


def _card_body(
    facts: CardFacts,
    g: Agg,
    *,
    license_id: str,
    include_answers: bool,
    repo_id: str,
    sample_case: dict | None = None,
) -> list[str]:
    gen = "／".join(g.versions) or "?"
    profiles = "、".join(f"{k} {v} 件" for k, v in sorted(g.profiles.items()))
    doctypes = "、".join(f"{k} {v}" for k, v in sorted(g.doctypes.items()))
    pages = f"{min(g.pages)}〜{max(g.pages)}" if g.pages else "—"
    origins = "、".join(f"{k} {v}" for k, v in sorted(g.origins.items()))

    L = [
        "",
        "# 日本語契約書の計算・判定条項データセット（合成）",
        "",
        "**本物そっくりだが完全に架空**の日本語ビジネス契約書と、そこに書かれた計算・判定条項の",
        "**計算仕様・正解プログラム・テストケース**を対で持つ合成データセット。",
        "「契約書から計算が必要な条項を見つけ、実装し、テストする」システムの評価用に作った。",
        "",
        "計算仕様が唯一の正であり、契約書の文言・正解プログラム・テストの期待値は**同じ仕様から",
        "機械的に生成**している。文言と式を別々に書いていないので三者はずれず、出力前に機械検査で",
        "一致を確かめてある。",
        "",
        (
            f"生成物は **{license_id}** で配布する（著作権表示：© {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}）。"
            "本文は `LICENSE`。"
            if license_id != UNDECIDED_LICENSE
            else "配布条件は未決である（下の「ライセンス」）。"
        ),
        "",
        "<details>",
        "<summary><b>English summary</b></summary>",
        "",
        "Synthetic Japanese business contracts (entirely fictional, no real templates reproduced)",
        "paired with machine-checked ground truth for the **calculation and decision clauses**",
        "they contain: a formal calculation spec, a reference Python implementation, and unit-test",
        "cases with expected values.",
        "",
        "Built for evaluating systems that must *find* the clauses in a contract that require",
        "computation, *implement* them, and *test* them — payment due dates, late-payment interest,",
        "tiered pricing, pro-rating, liability caps, renewal notice periods, business-day calendars,",
        "and so on.",
        "",
        "The calculation spec is the single source of truth: the contract wording, the reference",
        "program and the test expectations are all generated from it, so they cannot drift apart.",
        "No LLM is involved in generation and the pipeline is deterministic.",
        "",
        f"- **{g.n_docs} documents** across **{len(g.doctypes)} contract types**, 4 difficulty profiles",
        f"- **{len(g.all_rules)} rules**, **{g.n_tasks} task cards**, **{g.n_cases} test cases**",
        "- Each document ships as structured JSON **and** a rendered PDF with a text layer, plus",
        "  page-level bounding boxes and reading order",
        "- `inputs/` is what you give the system under test; `answers/` is the ground truth",
        "",
        "**These are not legally valid contracts.** They are synthetic fixtures for system",
        "development and evaluation, not for real-world use or legal advice. See the license",
        "section below — redistribution terms are still undecided.",
        "",
        NO_TRAINING_EN,
        "</details>",
        "",
        NO_TRAINING_JA,
        "## 規模（実測）",
        "",
        f"- 文書数 **{g.n_docs}**（難易度プロファイル: {profiles}）",
        f"- 契約書の種類 **{len(g.doctypes)}** 種（{doctypes}）",
        f"- ルール数 **{len(g.all_rules)}**（出どころ: {origins}）",
        f"- テストケース数 **{g.n_cases}**、タスクカード **{g.n_tasks}**",
        f"- PDF のページ数 {pages}（全文書 A4 縦）",
        f"- 生成器 contracts-calculation {gen}",
        "",
        "## 使い方",
        "",
        "```python",
        "from datasets import load_dataset",
        "",
        f'docs  = load_dataset("{repo_id}", "documents")["train"]   # 1 行 1 文書',
        f'rules = load_dataset("{repo_id}", "rules")["train"]       # 1 行 1 ルール',
        f'tasks = load_dataset("{repo_id}", "tasks")["train"]       # 1 行 1 出題',
    ]
    if include_answers:
        L.append(f'cases = load_dataset("{repo_id}", "cases")["train"]       # 1 行 1 テストケース（正解）')
    L += [
        "```",
        "",
        "入れ子になる値（`inputs`・`expected`・タスクカード全文）は、行ごとに型が揺れて Arrow の変換が",
        "落ちないよう **JSON 文字列の列**（`*_json`）で持たせている。`json.loads` で復元する。",
        "",
        "契約書そのもの（JSON・PDF）は `inputs/` に、正解は `answers/` にファイルとして置いてある。",
    ]
    L += _sample_toggle("cases", sample_case)
    L += [
        "## 構成",
        "",
        "```",
        "data/        load_dataset() 用の平索引（上記 configs）",
        "inputs/<content_id>/",
        "  contract.json            契約書（構造・意味つき。PDF の元）",
        "  <content_id>--<style>.pdf  紙面",
        "  layout.json              bbox・読み順・ページ数（紙面の読み取り正解）",
        "  calendar.json            その文書が使う祝日の固定版",
        "  tasks.jsonl              関数名と入出力の契約（出題）",
    ]
    if include_answers:
        L += [
            "answers/<content_id>/",
            "  spec.json                計算仕様（唯一の正）",
            "  answer_key.json          ルールと根拠単位の対応・表現手段・難易度",
            "  patch.json               既定の契約書に対して行った追加操作",
            "  manifest.json            生成の記録・検証ゲートの結果・ハッシュ",
            "  cases.jsonl              テストケース（入力と期待値）",
            "  programs/                正解プログラム（Python）",
            "  tests/                   同梱 pytest（--impl で提出実装に差し替えられる）",
        ]
    L += ["```", ""]

    if include_answers:
        L += [
            "### 正解を同梱していることの注意",
            "",
            "`answers/` と `cases` config には**正解が入っている**。評価に使うときは、評価対象の学習データに",
            "このデータセットが入っていないことを確かめる。学習に使うなら、`inputs/` と `tasks` だけを使い、",
            "`answers/` を伏せた運用にする。",
            "",
        ]
    else:
        L += [
            "### 正解は入っていない",
            "",
            "この配布形には `answers/` と `cases` config を含めていない。採点は提供者側で行う。",
            "",
        ]

    L += [
        "## どう作ったか",
        "",
        "1. 既定の契約書（人が執筆した架空の契約書 JSON）を選ぶ。",
        "2. 計算・判定のパターン（31 種）から、その契約書に無い事項を選ぶ。",
        "3. 計算仕様を組み、そこから**条文の文言・頭書の行・別紙の表・図**を生成して契約書に足す。",
        "4. 同じ仕様から**正解プログラム**と**テストケース**を生成する。",
        "5. 契約書を PDF に描画する（JSON → HTML → WeasyPrint）。",
        "6. 検証ゲートを掛け、**全部通った文書だけ**を出す。",
        "",
        "生成の経路で LLM は使っていない。同じ seed なら同じ出力になる（決定的）。",
        "",
        "## 品質保証",
        "",
        "全文書が次の検証ゲートを通っている。",
        "",
        "| | 検査 |",
        "|---|---|",
        "| G1–G2 | 仕様のスキーマ・型・単位。仕様の引用が契約書の単位に逐語で存在する |",
        "| G3–G4 | 明示すべき事項に対応する文がある。本文・頭書・別紙から読み直した値が仕様と一致する |",
        "| G5–G6 | 契約書に書いた計算例が参照インタプリタと一致する。参照インタプリタと正解プログラムが全ケースで一致する |",
        "| G7–G8 | 生成したテストが変異をすべて検出する。日付を扱うルールに暦の境界ケースが入っている |",
        "| G9–G10 | 既存の条項・定数・定義語・別紙番号と衝突しない。スキーマ検証・索引再計算・描画が成功する |",
        "| G11–G12 | 根拠単位が言い回しと構造で発見できる。同じ seed で再生成してハッシュが一致する |",
        "",
    ]
    if facts.oracle:
        n_fn = facts.oracle.get("n_functions", "?")
        n_case = facts.oracle.get("n_cases", "?")
        L += [
            f"正解プログラムを提出とみなした採点（オラクル検査）は満点である（{n_fn} 関数・{n_case} ケース）。",
            "",
        ]
    L += [
        "### 制限と既知の偏り",
        "",
        "- **法的に有効な契約書ではない。** 実務にも法的助言にも使えない。",
        "- 日本語・横書き・A4 縦のみ。印影・手書き・スキャン劣化は含まない。",
        "- 税率・法定利率・祝日は法令の実装ではなく、契約書に書かれた値か外部からの入力として扱う。",
        "- 祝日は固定版（実行時に外部へ取りに行かない）。",
        "- 既定の契約書の本数が限られるので、**同じ base から作った文書が複数ある**。",
        "  学習と評価で分けるときは `base_content_id` で分ける（`content_id` で分けると漏れる）。",
        "- より詳しい偏りと母数は、同梱の詳細データカードを見る。",
        "",
        "## 架空性",
        "",
        "会社名・屋号・人物名・住所・連絡先・URL・契約書番号・物件名・金額・日付は**すべて架空**である。",
        "参考にした実在の契約書ひな型の文章は、部分的にも語順を変えただけのものも**一切含まない**。",
        "実在名称との偶発的な衝突は、生成前に合成名称へ置換し、全量で回帰検査している。",
        "",
    ]
    return L


def _license_section(g: Agg, *, license_id: str) -> list[str]:
    L = ["## ライセンス", ""]
    if license_id == UNDECIDED_LICENSE:
        L += [
            "> **配布条件は未決である。** この配布形はライセンスが決まるまで公開しない。",
            "",
            "生成物（契約書 JSON・PDF・仕様・正解プログラム・テストケース）の配布条件は、作成者側で",
            "未決のまま起票されている（`HITL.md` HC-3）。決定が入るまで外部配布しない。",
            "",
        ]
    else:
        L += [
            f"データセット全体は `{license_id}` で提供する。Copyright (c) {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}",
            "",
            "正解プログラムと同梱テスト（`answers/*/programs/`・`answers/*/tests/`）は生成された",
            "Python コードであり、同じ条件で利用できる。",
            "",
        ]
    fonts = _font_licenses(g)
    if fonts:
        L += [
            "PDF にはフォントが埋め込まれている（PDF のフォント記述子から実測）。再配布は次の条件に従う。",
            "",
        ]
        for name, names in fonts:
            L.append(f"- **{name}**：" + "、".join(f"`{f}`" for f in names))
        if any(name == "ライセンス未同定" for name, _ in fonts):
            L += ["", "**ライセンスを同定できなかったフォントがある。配布の前に確認する。**"]
        L += [
            "",
            "`contract.json`・`layout.json`・`data/`・`answers/` はフォントのデータを含まない。",
            "",
        ]
    else:
        L += ["PDF が無いため、埋め込みフォントのライセンスは関係しない。", ""]
    return L


def render_card(
    facts: CardFacts,
    *,
    license_id: str,
    include_answers: bool,
    repo_id: str,
    sample_case: dict | None = None,
) -> str:
    g = aggregate(facts)
    lines = _frontmatter(facts, g, license_id=license_id, include_answers=include_answers)
    lines += _card_body(
        facts,
        g,
        license_id=license_id,
        include_answers=include_answers,
        repo_id=repo_id,
        sample_case=sample_case,
    )
    lines += _license_section(g, license_id=license_id)
    lines += [
        "## 詳しい素性",
        "",
        f"規模・内訳・正解の中身・テストケースの作り方・品質保証の実測値は `{CARD_NAME}` に全部入っている",
        "（実測だけから生成したデータカード）。",
        "",
    ]
    if license_id != UNDECIDED_LICENSE:
        lines += [
            "## Citation",
            "",
            "```bibtex",
            "@misc{keiyaku_calc,",
            f"  title  = {{{PRETTY_NAME_EN}}},",
            f"  author = {{{COPYRIGHT_HOLDER}}},",
            f"  year   = {{{COPYRIGHT_YEAR}}},",
            "  howpublished = {Hugging Face Hub},",
            f"  url    = {{https://huggingface.co/datasets/{repo_id}}},",
            f"  note   = {{Licensed under {license_id}.}}",
            "}",
            "```",
            "",
        ]
    return "\n".join(lines) + "\n"


def _card_preface(data_root: Path, *, license_id: str, include_answers: bool) -> str:
    """詳細データカードの前書き。カードは作業用データセットを測ったもので、公開形は部分集合である。"""
    L = [
        "<!-- 以下は生成元の作業用データセットを測った詳細データカードである（自動生成） -->",
        "",
        "> **この詳細カードの読み方**",
        "> ",
        f"> 以下は生成元の作業用データセット `{data_root.name}/` を実測した詳細データカードである。",
        "> 公開形はそこからの**部分集合**で、ローカルの絶対パスを含むデバッグ出力・中間生成物・",
        "> 重複ファイルを除いてある。したがって **§3「規模」の容量と役割別の表は、公開形ではなく",
        "> 作業用データセットの数字**である（文書数・ルール数・ケース数は同じ）。",
    ]
    if not include_answers:
        L.append("> この配布形には正解を含めていないので、正解に関する節は手元には無いものを指す。")
    if license_id == UNDECIDED_LICENSE:
        L += [
            "> ",
            "> ライセンスは**未決**である。§12 の記載が現在の状態であり、`README.md` と一致する。",
        ]
    else:
        L += [
            "> ",
            (
                f"> **ライセンスは `{license_id}` に決まった。** §12 は作成時点の記録であり、"
                "現在の条件は `README.md` の「ライセンス」節が正しい。"
            ),
        ]
    L += [
        "> ",
        "> カード本文が挙げる `HITL.md`・`docs/`・`dataset/README.md` は**生成器のリポジトリ側**の",
        "> ファイルで、このデータセットには入っていない。公開形の構成と、何をなぜ除いたかは",
        "> `README.md` にある。",
        "",
        "---",
        "",
    ]
    return "\n".join(L) + "\n"


def render_notice(facts: CardFacts, *, license_id: str) -> str:
    g = aggregate(facts)
    L = [
        "# NOTICE",
        "",
        "## 架空性と免責",
        "",
        "本データセットに含まれる契約書は**完全に架空**である。会社名・人物名・住所・連絡先・金額・",
        "日付・契約書番号はすべて合成であり、実在の個人・法人・取引とは関係がない。",
        "",
        "**法的に有効な契約書ではない。** 実務での使用、法的助言、ひな型としての流用はできない。",
        "読み取り・計算発見・コード生成システムの開発検証を目的とした合成データである。",
        "",
        "参考にした実在の契約書ひな型の文章は、部分的にも、語順を変えただけのものも含まない。",
        "",
        NO_TRAINING_JA,
        "## 埋め込みフォント",
        "",
    ]
    fonts = _font_licenses(g)
    if fonts:
        L.append("PDF には次のフォントが埋め込まれている（PDF のフォント記述子から実測）。")
        L.append("")
        for name, names in fonts:
            L.append(f"- **{name}**")
            for f in names:
                L.append(f"  - `{f}`")
        L += [
            "",
            "SIL Open Font License 1.1 の条文は <https://openfontlicense.org/> にある。",
            "フォントのデータは PDF の中にだけあり、ほかのファイルには含まれない。",
            "",
        ]
    else:
        L += ["PDF が無いため、埋め込みフォントは無い。", ""]
    L += ["## ライセンス", ""]
    if license_id == UNDECIDED_LICENSE:
        L += ["配布条件は**未決**である（作成者側 `HITL.md` HC-3）。決定が入るまで外部配布しない。", ""]
    else:
        L += [
            f"データセット全体は `{license_id}` で提供する。Copyright (c) {COPYRIGHT_YEAR} {COPYRIGHT_HOLDER}",
            "",
        ]
    return "\n".join(L) + "\n"


def render_gitattributes() -> str:
    return "# 紙面は Git LFS に送る（1 文書あたり 100KB 超）\n*.pdf filter=lfs diff=lfs merge=lfs -text\n"


# --- 公開前ゲート -----------------------------------------------------------------


_FORBIDDEN_PARTS = ("__pycache__", "_work", "_render")
_FORBIDDEN_NAMES = ("render.html",)
_TEXT_SUFFIXES = {".json", ".jsonl", ".py", ".md", ".txt", ".gitattributes", ""}


def _allowed(rel: Path, *, include_answers: bool) -> bool:
    parts = rel.parts
    if len(parts) == 1:
        return rel.name in {README_NAME, NOTICE_NAME, GITATTRIBUTES_NAME, CARD_NAME}
    if parts[0] == "data":
        return len(parts) == 2 and parts[1] in {n for n, _ in _VIEWS}
    if parts[0] == "inputs":
        if len(parts) != 3:
            return False
        names = {n for n, _ in _INPUT_FILES}
        return parts[2] in names or parts[2].endswith(".pdf")
    if parts[0] == "answers":
        if not include_answers:
            return False
        if len(parts) == 3:
            return parts[2] in {n for n, _ in _ANSWER_FILES}
        if len(parts) == 4:
            return parts[2] in {"programs", "tests"} and parts[3].endswith(".py")
        return False
    return False


def _secrets_patterns() -> tuple[str, ...]:
    """絶対パス・ホーム・実行ユーザー名。公開形に 1 件もあってはならない。"""
    pats = ["/Users/", "/home/", str(Path.home())]
    for key in ("USER", "LOGNAME", "USERNAME"):
        name = os.environ.get(key)
        if name and len(name) >= 3:
            pats.append(name)
    return tuple(dict.fromkeys(p for p in pats if p))


def run_gates(
    out_root: Path, data_root: Path, *, include_answers: bool, calc_root: Path
) -> list[tuple[str, bool, str]]:
    files = sorted(p for p in out_root.rglob("*") if p.is_file())
    rels = [p.relative_to(out_root) for p in files]

    # P1 許可リスト
    unexpected = [str(r) for r in rels if not _allowed(r, include_answers=include_answers)]
    gates = [
        (
            "P1",
            not unexpected,
            ("想定外: " + "、".join(unexpected[:5])) if unexpected else f"{len(rels)} ファイル",
        )
    ]

    # P2 パスの漏れ（テキストだけ読む。PDF は本体がメタデータを固定値にしている）
    pats = _secrets_patterns()
    leaked = []
    for p, r in zip(files, rels):
        if p.suffix not in _TEXT_SUFFIXES:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        hit = [q for q in pats if q in text]
        if hit:
            leaked.append(f"{r}（{hit[0]}）")
    gates.append(
        (
            "P2",
            not leaked,
            ("漏れ: " + "、".join(leaked[:5])) if leaked else f"検査語 {len(pats)} 件・漏れ無し",
        )
    )

    # P3 副産物
    junk = [
        str(r)
        for r in rels
        if any(part in _FORBIDDEN_PARTS for part in r.parts)
        or r.name in _FORBIDDEN_NAMES
        or r.suffix == ".pyc"
    ]
    gates.append(("P3", not junk, ("副産物: " + "、".join(junk[:5])) if junk else "なし"))

    # P4 実在名称
    repl = load_replacements(calc_root)
    bad_names: list[str] = []
    for p, r in zip(files, rels):
        if p.suffix not in _TEXT_SUFFIXES:
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        for name in repl:
            if name in text:
                bad_names.append(f"{r}（{name}）")
                break
    gates.append(
        (
            "P4",
            not bad_names,
            ("残存: " + "、".join(bad_names[:5])) if bad_names else f"禁止 {len(repl)} 件・残存無し",
        )
    )

    # P5 文書集合の対応
    src = {p.name for p in sorted(data_root.iterdir()) if (p / "calc" / "manifest.json").is_file()}
    got_in = {r.parts[1] for r in rels if r.parts[0] == "inputs"}
    detail = f"inputs {len(got_in)} / dataset {len(src)}"
    ok5 = got_in == src
    if include_answers:
        got_ans = {r.parts[1] for r in rels if r.parts[0] == "answers"}
        ok5 = ok5 and got_ans == src
        detail += f" / answers {len(got_ans)}"
    gates.append(("P5", ok5, detail))

    # P6 カード
    card = (out_root / README_NAME).read_text(encoding="utf-8")
    ok6, why = True, "frontmatter と configs は妥当"
    if not card.startswith("---\n"):
        ok6, why = False, "frontmatter が無い"
    else:
        fm = card.split("---\n", 2)[1]
        missing = [k for k in ("license:", "language:", "configs:") if k not in fm]
        if missing:
            ok6, why = False, "frontmatter に " + "、".join(missing) + " が無い"
        else:
            bad_path = [
                line.split("path:", 1)[1].strip()
                for line in fm.splitlines()
                if "path:" in line and not (out_root / line.split("path:", 1)[1].strip()).is_file()
            ]
            if bad_path:
                ok6, why = False, "configs の指すファイルが無い: " + "、".join(bad_path)
    gates.append(("P6", ok6, why))
    return gates


# --- 組み立て ---------------------------------------------------------------------


def build(
    data_root: Path,
    out_root: Path,
    *,
    license_id: str | None = None,
    repo_id: str = "cvusk/japanese-contract-document-understanding-calculation",
    include_answers: bool = True,
    calc_root: Path | None = None,
) -> PublishResult:
    """`dataset/` から Hugging Face 公開形を組み立てる。`dataset/` は読むだけ。"""
    data_root = Path(data_root)
    out_root = Path(out_root)
    calc_root = Path(calc_root) if calc_root else Path(__file__).resolve().parents[3]
    if out_root.resolve() == data_root.resolve() or data_root.resolve() in out_root.resolve().parents:
        raise ValueError("公開形の出力先を dataset/ の中に置かない（生成物を書き換えないため）")
    lic = license_id or UNDECIDED_LICENSE

    facts = collect(data_root)
    if not facts.docs:
        raise FileNotFoundError(f"{data_root} に計算パックが無い")

    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True)

    # 1 文書ずつ、許可リストのものだけをコピーする
    for d in sorted(facts.docs, key=lambda x: x.content_id):
        doc_dir = data_root / d.content_id
        dst_in = out_root / "inputs" / d.content_id
        dst_in.mkdir(parents=True, exist_ok=True)
        srcs = _input_sources(doc_dir)
        for out_name, key in _INPUT_FILES:
            src = srcs[key]
            if src and src.is_file():
                shutil.copyfile(src, dst_in / out_name)
        pdf = _pdf_path(doc_dir)
        if pdf:
            shutil.copyfile(pdf, dst_in / pdf.name)
        if not include_answers:
            continue
        dst_ans = out_root / "answers" / d.content_id
        dst_ans.mkdir(parents=True, exist_ok=True)
        for out_name, rel in _ANSWER_FILES:
            src = doc_dir / rel
            if src.is_file():
                shutil.copyfile(src, dst_ans / out_name)
        for sub in ("programs", "tests"):
            src_dir = doc_dir / "calc" / sub
            if not src_dir.is_dir():
                continue
            (dst_ans / sub).mkdir(parents=True, exist_ok=True)
            for src in sorted(src_dir.glob("*.py")):
                shutil.copyfile(src, dst_ans / sub / src.name)

    # 平索引
    rows_by_name = {
        "documents.jsonl": _documents_rows(facts),
        "rules.jsonl": _rules_rows(facts),
        "tasks.jsonl": _tasks_rows(data_root, facts),
        "cases.jsonl": _cases_rows(data_root, facts),
    }
    for name, needs_answers in _VIEWS:
        if needs_answers and not include_answers:
            continue
        _write_jsonl(out_root / "data" / name, rows_by_name[name])

    # カード・表示・LFS 設定・詳細データカード
    cases_rows = rows_by_name["cases.jsonl"]
    (out_root / README_NAME).write_text(
        render_card(
            facts,
            license_id=lic,
            include_answers=include_answers,
            repo_id=repo_id,
            sample_case=cases_rows[0] if include_answers and cases_rows else None,
        ),
        encoding="utf-8",
    )
    (out_root / NOTICE_NAME).write_text(render_notice(facts, license_id=lic), encoding="utf-8")
    (out_root / GITATTRIBUTES_NAME).write_text(render_gitattributes(), encoding="utf-8")
    card_src = data_root / CARD_NAME
    if card_src.is_file():
        (out_root / CARD_NAME).write_text(
            _card_preface(data_root, license_id=lic, include_answers=include_answers)
            + card_src.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    gates = run_gates(out_root, data_root, include_answers=include_answers, calc_root=calc_root)
    files = tuple(sorted(str(p.relative_to(out_root)) for p in out_root.rglob("*") if p.is_file()))
    total = sum((out_root / f).stat().st_size for f in files)
    return PublishResult(
        out_root=out_root,
        n_docs=len(facts.docs),
        include_answers=include_answers,
        license_id=lic,
        files=files,
        total_bytes=total,
        gates=tuple(gates),
    )
