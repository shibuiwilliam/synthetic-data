"""データセットの説明書（README）。manifest の実測値から生成する（固定文字列を焼き込まない）。"""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path


def write_datasheet(data_root: Path) -> Path:
    data_root = Path(data_root)
    manifests = []
    for p in sorted(data_root.glob("*/calc/manifest.json")):
        manifests.append(json.loads(p.read_text(encoding="utf-8")))
    if not manifests:
        raise FileNotFoundError(f"{data_root} に計算パックが無い")
    patterns = Counter()
    origins = Counter()
    profiles = Counter()
    challenges = []
    n_rules = 0
    n_cases = 0
    bindings_inc = Counter()
    bindings_exc = Counter()
    for m in manifests:
        profiles[m.get("profile", "?")] += 1
        if m.get("challenge"):
            challenges.append(f"{m['content_id']}:{m['challenge']['rule']}（{m['challenge']['type']}）")
        ak = json.loads(
            (data_root / m["content_id"] / "calc" / "answer_key.json").read_text(encoding="utf-8")
        )
        for a in ak:
            patterns[a["pattern"]] += 1
            origins[a["origin"]] += 1
            n_rules += 1
        cases_path = data_root / m["content_id"] / "calc" / "cases.jsonl"
        n_cases += sum(1 for _ in cases_path.open(encoding="utf-8"))
        for b in m.get("bindings", {}).get("included", []):
            bindings_inc[b["binding"]] += 1
        for e in m.get("bindings", {}).get("excluded", []):
            bindings_exc[e["binding"]] += 1
    gen_version = manifests[0].get("generator_version", "?")
    lines = [
        "# 計算パック データセット（自動生成。手で編集しない）",
        "",
        f"- 生成器: contracts-calculation {gen_version}",
        f"- 文書数: {len(manifests)}（プロファイル: "
        + "、".join(f"{k} {v} 件" for k, v in sorted(profiles.items()))
        + "）",
        f"- ルール数: {n_rules}（origin: " + "、".join(f"{k} {v}" for k, v in sorted(origins.items())) + "）",
        f"- テストケース数: {n_cases}",
        "",
        "## パターン別のルール数",
        "",
        "| パターン | 件数 |",
        "|---|---|",
    ]
    lines += [f"| {k} | {v} |" for k, v in sorted(patterns.items())]
    lines += [
        "",
        "## 付与モード（既定の契約書の条項への紐づけ）",
        "",
        "採用: " + ("、".join(f"{k} {v} 件" for k, v in sorted(bindings_inc.items())) or "なし"),
        "",
        "除外（明示性の欠落を記録）: "
        + ("、".join(f"{k} {v} 件" for k, v in sorted(bindings_exc.items())) or "なし"),
        "",
        "## challenge（ラベル付きの難所）",
        "",
        ("、".join(challenges) if challenges else "なし（通常モード）"),
        "",
        "## 評価対象システムに渡すもの",
        "",
        "`contract.json`・PDF・`calc/calendar.json`・`calc/tasks.jsonl`（ヒント水準は評価側で H0〜H2 に削る）。",
        (
            "`calc/cases.jsonl`・`calc/tests/`・`calc/spec.json`・`calc/programs/`・`calc/answer_key.json`・"
            "`calc/patch.json` は渡さない。"
        ),
    ]
    out = data_root / "README.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return out
