"""パッチ：コピーした content ディレクトリに、追加操作だけを適用する。

- 既存の文言は書き換えない。足すだけにする。
- 平らな本文（条が最上位）には、新しい part ファイルを body の最後に足す。
- 章立ての本文には、対象の章を含む part ファイルの章 children に条を足す。
- 操作はすべて記録し、patch.json として書き出せる形で返す。
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class Patcher:
    content_dir: Path
    doc: dict
    ops: list[dict] = field(default_factory=list)

    @classmethod
    def load(cls, content_dir: Path) -> Patcher:
        content_dir = Path(content_dir)
        doc = json.loads((content_dir / "doc.json").read_text(encoding="utf-8"))
        return cls(content_dir=content_dir, doc=doc)

    # --- 操作 -------------------------------------------------------------------

    def set_content_id(self, new_cid: str) -> None:
        self.ops.append({"op": "set_content_id", "from": self.doc["content_id"], "to": new_cid})
        self.doc["content_id"] = new_cid

    def add_constants(self, constants: dict[str, str]) -> None:
        existing = self.doc["meta"].setdefault("constants", {})
        for key, value in constants.items():
            if key in existing:
                raise ValueError(f"定数名が既定の契約書と衝突した: {key}（生成を止める）")
            existing[key] = value
            self.ops.append({"op": "add_constant", "key": key, "value": value})

    def add_article_flat(self, article_node: dict, seq: int) -> None:
        """平らな本文の最後に、条を新しい part として足す。"""
        filename = f"{60 + seq}_{article_node['id']}.json"
        part_path = self.content_dir / "parts" / filename
        if part_path.exists():
            raise ValueError(f"part が既に存在する: {filename}")
        part_path.write_text(
            json.dumps({"target": "body", "items": [article_node]}, ensure_ascii=False, indent=1) + "\n",
            encoding="utf-8",
        )
        parts: list[str] = self.doc["parts"]
        insert_at = self._last_body_part_index() + 1
        parts.insert(insert_at, filename)
        self.ops.append({"op": "add_node", "kind": "article", "id": article_node["id"], "part": filename})

    def add_article_to_chapter(self, article_node: dict, chapter_id: str) -> None:
        """章立ての本文で、対象の章の children の末尾に条を足す。"""
        for name in self.doc["parts"]:
            path = self.content_dir / "parts" / name
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("target") != "body":
                continue
            for item in data.get("items", []):
                if item.get("kind") == "chapter" and item.get("id") == chapter_id:
                    item.setdefault("children", []).append(article_node)
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                    self.ops.append(
                        {
                            "op": "add_node",
                            "kind": "article",
                            "id": article_node["id"],
                            "chapter": chapter_id,
                            "part": name,
                        }
                    )
                    return
        raise ValueError(f"章が見つからない: {chapter_id}")

    def write_doc(self) -> None:
        (self.content_dir / "doc.json").write_text(
            json.dumps(self.doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )

    # --- 内部 -------------------------------------------------------------------

    def _last_body_part_index(self) -> int:
        last = 0
        for i, name in enumerate(self.doc["parts"]):
            path = self.content_dir / "parts" / name
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except FileNotFoundError:
                continue
            if data.get("target") == "body":
                last = i
        return last

    def add_appendix(self, appendix_node: dict, seq: int) -> None:
        """別紙を appendices の末尾に足す。"""
        filename = f"{80 + seq}_{appendix_node['id']}.json"
        part_path = self.content_dir / "parts" / filename
        if part_path.exists():
            raise ValueError(f"part が既に存在する: {filename}")
        part_path.write_text(
            json.dumps({"target": "appendices", "items": [appendix_node]}, ensure_ascii=False, indent=1)
            + "\n",
            encoding="utf-8",
        )
        self.doc["parts"].append(filename)
        self.ops.append({"op": "add_node", "kind": "appendix", "id": appendix_node["id"], "part": filename})

    def add_header_row(self, head_matter_id: str, item_node: dict) -> None:
        """頭書に項目（見出し＋値の段落）を足す（DESIGN.md §12.5 add_header_row）。"""
        for name in self.doc["parts"]:
            path = self.content_dir / "parts" / name
            if not path.is_file():
                continue
            data = json.loads(path.read_text(encoding="utf-8"))
            if data.get("target") != "body":
                continue
            for item in data.get("items", []):
                if item.get("kind") == "head_matter" and item.get("id") == head_matter_id:
                    item.setdefault("children", []).append(item_node)
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
                    self.ops.append(
                        {
                            "op": "add_header_row",
                            "head_matter": head_matter_id,
                            "id": item_node["id"],
                            "part": name,
                        }
                    )
                    return
        raise ValueError(f"頭書が見つからない: {head_matter_id}")
