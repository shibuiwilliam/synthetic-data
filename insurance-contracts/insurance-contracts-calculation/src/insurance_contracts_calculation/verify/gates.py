"""検証ゲート（DESIGN.md §12）。

すべて通った文書だけを出力する。落ちたら**生成側を直す**。ゲートを緩めない
（`CLAUDE.md` 守ること 9）。

| ゲート | 検査 |
|---|---|
| G1 | 仕様の検査（スキーマ・型と単位・未宣言の入力・根拠のない数値） |
| G2 | 根拠の照合（仕様の引用が追加後の約款JSONに逐語で存在する） |
| G3 | 明示性（パターンが宣言した要件に対応する文がある） |
| G4 | 数値の往復（定数の表記と表のセルを読み直した値が仕様と一致する） |
| G5 | 設例の一致（約款に書いた設例の数値が参照インタプリタの結果と一致する） |
| G6 | 実装の一致（参照インタプリタと正解プログラムが全ケースで一致する） |
| G7 | テストの十分性（変異をすべて検出する） |
| G8 | 衝突なし（定数名・用語・保険金名・表記・ID が既定の約款と衝突しない） |
| G9 | 本体の検査（lint・ページ予算・描画・verify） |
| G10 | 発見可能性（根拠単位が決定的な候補検出で拾える） |
| G11 | 決定性（同じ seed で再生成してハッシュが一致する） |
| G12 | 解答可能性（任意。基準となるシステムが H2 のヒントで合格する） |
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from ..core.docindex import Doc
from ..spec import obligations as ob
from ..spec.validate import RuleSet

#: 本体 lint のうち、1 件でも出たら生成を止めるもの（TASK.md S1-5）
BLOCKING_LINT = ("L00", "L01", "L03", "L05", "L06", "L09", "L11", "L12", "L17", "L18")

TOKEN = re.compile(r"\{[a-z]+:[^}]+\}")

#: ゲートの題（コード → 題）。**唯一の正**。
#: 結果だけを持つ側（`calc/manifest.json` の `gates` を読むデータカードなど）が
#: 題を引けるようにしてある。ここを直せば表示も変わる。
GATE_TITLES: dict[str, str] = {
    "G1": "仕様の検査",
    "G2": "根拠の照合",
    "G3": "明示性",
    "G4": "数値の往復",
    "G5": "設例の一致",
    "G6": "実装の一致",
    "G7": "テストの十分性",
    "G8": "衝突なし",
    "G9a": "本体 lint",
    "G9b": "ページ予算",
    "G9c": "本体 verify",
    "G10": "発見可能性",
    "G11": "決定性",
    "G12": "解答可能性",
}

#: 「支払わない」を表す言い回し（条文は「支払いません」、設例は丁寧語の「お支払いしません」）
NOT_PAID = ("支払いません", "支払いしません", "支払いできません")


@dataclass
class GateResult:
    code: str
    name: str
    ok: bool
    detail: str = ""
    data: dict = field(default_factory=dict)

    def __str__(self) -> str:
        head = f"{self.code} {self.name}: {'OK' if self.ok else '失敗'}"
        return f"{head}\n    {self.detail}" if self.detail else head


class GateFailure(RuntimeError):
    """ゲートに落ちた（この文書は出力しない）。"""

    def __init__(self, results: list[GateResult]):
        bad = [r for r in results if not r.ok]
        super().__init__("検証ゲートに失敗:\n" + "\n".join(str(r) for r in bad))
        self.results = results
        self.failed = bad


# ------------------------------------------------------------------ G1 / G2 / G4
def spec_gates(rs: RuleSet) -> list[GateResult]:
    """仕様の検査・根拠の照合・数値の往復。`RuleSet.validate()` の指摘を振り分ける。"""
    issues = [i for i in rs.validate() if i.level in ("error", "block", "warn")]
    source_codes = {"SOURCE_NOT_FOUND", "QUOTE_NOT_VERBATIM", "PARAM_NOT_IN_QUOTE", "NO_SOURCE"}
    number_codes = {
        "PARAM_NOT_NUMERIC",
        "PARAM_UNIT_MISMATCH",
        "CONST_NOT_FOUND",
        "TABLE_CELL_UNPARSED",
        "TABLE_DUP_KEY",
        "TABLE_NOT_SORTED",
        "TABLE_NOT_MONOTONE",
        "TABLE_DOMAIN_GAP",
    }
    g2 = [i for i in issues if i.code in source_codes]
    g4 = [i for i in issues if i.code in number_codes]
    g1 = [i for i in issues if i.code not in source_codes | number_codes]
    return [
        GateResult("G1", GATE_TITLES["G1"], not g1, "\n    ".join(str(i) for i in g1)),
        GateResult("G2", GATE_TITLES["G2"], not g2, "\n    ".join(str(i) for i in g2)),
        GateResult("G4", GATE_TITLES["G4"], not g4, "\n    ".join(str(i) for i in g4)),
    ]


# ------------------------------------------------------------------ G3
def reading_order(doc: Doc) -> dict[str, float]:
    """単位を**読む順**に並べる番号。

    索引は「ノードの文 → ブロック → 子ノード」の順に作られるが、条末脚注は読むときは
    条の**いちばん後**に来る。順序を見る要件（「乗じて得た額」のあとに「端数」など）が
    脚注に割ったとたんに落ちないよう、読む順に直す。
    """
    order = {uid: float(i) for i, uid in enumerate(doc.units)}
    # 条ごとの「いちばん後ろの単位」。項は条の子なので、条の持ち物だけを見ても足りない
    last_of_article: dict[str, float] = {}
    for uid, u in doc.units.items():
        article = doc.article_of(u.owner) if u.owner else None
        if article:
            last_of_article[article] = max(last_of_article.get(article, 0.0), order[uid])
    for uid, u in doc.units.items():
        if u.utype != "footnote":
            continue
        article = doc.article_of(u.owner) if u.owner else None
        if article in last_of_article:
            # 脚注どうしの前後は保つ（(*1) のあとに (*2) を読む）
            order[uid] = last_of_article[article] + 0.5 + order[uid] * 1e-6
    return order


def explicitness(rs: RuleSet, doc: Doc) -> GateResult:
    """パターンが宣言した明示性の要件に対応する文が、実際の文言にあるかを逐語で確かめる。"""
    order = reading_order(doc)
    bad: list[str] = []
    checked = 0
    for rid, rule in rs.rules.items():
        units = sorted({s["unit"] for s in rule.get("sources", [])}, key=lambda u: order.get(u, 10**6))
        text = "".join(doc.units[u].text for u in units if u in doc.units)
        for oid in rule.get("obligations", []):
            checked += 1
            req = ob.build(oid)
            why = req.check(text)
            if why:
                bad.append(f"{rid}: {oid} — {why}")
    return GateResult("G3", GATE_TITLES["G3"], not bad, "\n    ".join(bad), {"checked": checked})


# ------------------------------------------------------------------ G5
def examples_match(
    rs: RuleSet,
    doc: Doc,
    pairs: dict[str, list[tuple[dict, object]]],
    explanatory: dict[str, list[str]],
) -> GateResult:
    """**約款に書いた設例の文字列から読み直した数値**が、参照インタプリタの結果と一致するか。

    文は仕様から作っているが、ここでは出力された文書を読み直して確かめる
    （作り方を信用せず、成果物で照合する）。
    """
    from ..realize.examples import surface_of

    bad: list[str] = []
    n = 0
    for rid, got in pairs.items():
        units = explanatory.get(rid, [])
        if len(units) < len(got):
            bad.append(f"{rid}: 設例 {len(got)} 件に対して囲みの文が {len(units)} 件しかない")
            continue
        for (inputs, value), uid in zip(got, units, strict=False):
            n += 1
            if uid not in doc.units:
                bad.append(f"{rid}: 設例の単位 {uid} が文書にない")
                continue
            text = doc.units[uid].text
            if value is None or isinstance(value, bool):
                continue  # 真偽・不明の設例は数値の照合をしない
            if value == 0:
                # 設例は丁寧語（「お支払いしません」）、条文は「支払いません」。両方を見る
                if not any(m in text for m in NOT_PAID):
                    bad.append(f"{rid}: 0 円の設例に支払わない旨が書かれていない: 「{text[:40]}…」")
                continue
            want = surface_of(value, rs.rules[rid]["output"].get("unit"))
            if want not in text:
                bad.append(f"{rid}: 囲みの文に計算結果 {want} が現れない（入力 {inputs}）: 「{text[:40]}…」")
    return GateResult("G5", GATE_TITLES["G5"], not bad, "\n    ".join(bad), {"examples": n})


# ------------------------------------------------------------------ G6 / G7
def implementation_matches(mismatches: list[str], n_cases: int) -> GateResult:
    return GateResult(
        "G6", GATE_TITLES["G6"], not mismatches, "\n    ".join(mismatches[:10]), {"cases": n_cases}
    )


def test_sufficiency(stats: dict[str, dict], justified: dict[str, str] | None = None) -> GateResult:
    justified = justified or {}
    survivors = {
        rid: [s for s in st["survivors"] if f"{rid}/{s}" not in justified]
        for rid, st in stats.items()
        if st["survivors"]
    }
    survivors = {k: v for k, v in survivors.items() if v}
    detail = "\n    ".join(f"{rid}: {', '.join(v)}" for rid, v in survivors.items())
    return GateResult(
        "G7",
        GATE_TITLES["G7"],
        not survivors,
        detail,
        {"mutants": sum(s["mutants"] for s in stats.values()), "survivors": survivors},
    )


# ------------------------------------------------------------------ G8
def no_clash(
    base_data: dict,
    added_constants: dict[str, str],
    added_nodes: set[str],
    added_blocks: set[str],
    added_benefits: set[str],
    added_texts: list[str],
    ctx,
) -> GateResult:
    """定数名・用語・保険金名・**表記**・ID の衝突。L11（表記の直書き）も含む。"""
    bad: list[str] = []
    for name in sorted(set(added_constants) & set(ctx.constants)):
        bad.append(f"定数名 {name} が既定の約款と衝突")
    for nid in sorted(added_nodes & ctx.node_ids):
        bad.append(f"ノードID {nid} が既定の約款と衝突")
    for bid in sorted(added_blocks & ctx.block_ids):
        bad.append(f"ブロックID {bid} が既定の約款と衝突")
    for name in sorted(added_benefits & ctx.benefits):
        bad.append(f"保険金の名称「{name}」が既定の約款と衝突")
    all_surfaces = set(ctx.const_surfaces) | set(added_constants.values())
    literal = "".join(TOKEN.sub("", t) for t in added_texts)
    for surface in sorted(all_surfaces):
        if len(surface) >= 2 and surface in literal:
            bad.append(f"定数の表記「{surface}」が素の文字列で書かれている（本体 lint L11）")
    return GateResult("G8", GATE_TITLES["G8"], not bad, "\n    ".join(bad))


# ------------------------------------------------------------------ G9
def base_lint(
    findings: list, blocking: tuple[str, ...] = BLOCKING_LINT, draft: dict | None = None
) -> GateResult:
    """本体 lint。`blocking` のコードは severity を問わず失敗にする。

    環境変数 `ICC_DUMP_ON_LINT_FAIL` にパスを入れておくと、落ちたときの draft を書き出す
    （再現しにくい失敗を追うため。既定では何もしない）。
    """
    bad = [f for f in findings if f.severity == "error" or f.code in blocking]
    if bad and draft is not None:
        _dump_on_failure(draft, bad)
    others = [f for f in findings if f not in bad]
    return GateResult(
        "G9a",
        GATE_TITLES["G9a"],
        not bad,
        "\n    ".join(str(f) for f in bad),
        {"warn_only": [str(f) for f in others]},
    )


def _dump_on_failure(draft: dict, bad: list) -> None:
    import json
    import os

    target = os.environ.get("ICC_DUMP_ON_LINT_FAIL")
    if not target:
        return
    path = Path(target)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"findings": [str(f) for f in bad], "draft": draft}, ensure_ascii=False),
        encoding="utf-8",
    )


def page_budget(before: float, after: float, rendered: int | None, max_pages: int) -> GateResult:
    bad = []
    if after > max_pages - 1:
        bad.append(f"追加後の見積りが {after:.1f} ページ（上限 {max_pages} に対して余裕が無い）")
    if rendered is not None and rendered > max_pages:
        bad.append(f"描画結果が {rendered} ページ（上限 {max_pages} を超えた）")
    return GateResult(
        "G9b",
        GATE_TITLES["G9b"],
        not bad,
        "\n    ".join(bad),
        {"before": round(before, 2), "after": round(after, 2), "rendered": rendered},
    )


def base_verify(findings: list, notes: list[str]) -> GateResult:
    bad = [str(f) for f in findings if f.severity == "error"]
    if notes:
        bad += [f"描画の注記（内容が欠けた可能性）: {n}" for n in notes]
    return GateResult("G9c", GATE_TITLES["G9c"], not bad, "\n    ".join(bad))


# ------------------------------------------------------------------ G10
def discoverable(doc: Doc, answer: list[dict]) -> GateResult:
    """根拠単位が、決定的な候補検出で拾えるか（拾えない単位は記録する）。"""
    from . import discoverability

    found = {c.unit.id for c in discoverability.detect(doc)}
    need = sorted({u for a in answer for u in a["units"]})
    missing = [u for u in need if not (u in found or any(f.startswith(u + "__") for f in found))]
    return GateResult(
        "G10",
        GATE_TITLES["G10"],
        True,  # 記録のみ（拾えない単位があっても止めない）
        "拾えない単位: " + ", ".join(missing) if missing else "",
        {"found": len(need) - len(missing), "need": len(need), "missing": missing},
    )


# ------------------------------------------------------------------ G11
def determinism(hashes_a: dict[str, str], hashes_b: dict[str, str]) -> GateResult:
    diff = sorted(k for k in set(hashes_a) | set(hashes_b) if hashes_a.get(k) != hashes_b.get(k))
    return GateResult(
        "G11", GATE_TITLES["G11"], not diff, "差分のあるファイル: " + ", ".join(diff) if diff else ""
    )


def summarize(results: list[GateResult]) -> dict:
    return {r.code: {"ok": r.ok, **({"detail": r.detail} if r.detail else {}), **r.data} for r in results}


def raise_if_failed(results: list[GateResult]) -> None:
    if any(not r.ok for r in results):
        raise GateFailure(results)
