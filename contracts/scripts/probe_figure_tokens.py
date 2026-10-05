"""図の中の {const:} {term:} {ref:} が解決されて SVG に載るかを実測する。

docs/shared_fixes.md A2。sample_min の図のノードラベルをトークン入りに書き換えて
build → render し、PDF のテキスト層に解決後の文字列が出るかを見る。
"""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main() -> int:
    from keiyaku.build import build_content
    from keiyaku.render.weasy import render_source
    from keiyaku.styles import load_style

    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp) / "sample_min"
        shutil.copytree(ROOT / "tests" / "golden" / "sample_min", work)

        part = work / "parts" / "30_ch4.json"
        data = json.loads(part.read_text(encoding="utf-8"))

        def patch(obj: object) -> None:
            if isinstance(obj, dict):
                if obj.get("type") == "figure":
                    nodes = obj["diagram"].get("nodes") or []
                    if nodes:
                        nodes[0]["label"] = "事故の発生（{const:notify_days}日以内に連絡）"
                    obj["facts"].append("連絡の期限は{const:notify_days}日である。")
                for value in obj.values():
                    patch(value)
            elif isinstance(obj, list):
                for value in obj:
                    patch(value)

        patch(data)
        part.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

        doc = json.loads((work / "doc.json").read_text(encoding="utf-8"))
        const = doc["meta"].setdefault("constants", {})
        const["notify_days"] = "３０"
        (work / "doc.json").write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")

        source = build_content(work)
        figure_id = next(iter(source.derived.figures))
        derived = source.derived.figures[figure_id]
        print("resolved_labels:")
        for raw, resolved in derived.resolved_labels.items():
            print(f"  {raw!r}\n    → {resolved!r}")

        out = Path(tmp) / "out"
        render_source(source, load_style("nl-a4-2col-mincho"), out)
        import pdfplumber

        with pdfplumber.open(out / "doc.pdf") as pdf:
            text = "".join(page.extract_text() or "" for page in pdf.pages)
        text = text.replace("\n", "")
        print()
        print("PDF に '３０日以内に連絡' が載った:", "３０日以内に連絡" in text)
        print("PDF に生トークン '{const:' が残った:", "{const:" in text)
        print("derived.figures.paths[0][:2]:", derived.paths[0][:2] if derived.paths else None)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
