"""`yakkan/export.py` の配布成果物（Hugging Face 向け。docs/distribution.md）。

以前は `README.md`（読み方）と `DATASET_CARD.md`（HF 形式の要約）が別々にあったが、
**HF はリポジトリ直下の `README.md` だけをデータセットカードとして読む**ので 1 枚に統合した。
ここでは「統計値を固定文字列で焼き込まない」ことと、**HF が実際に読める形**であることを検査する。
"""

from __future__ import annotations

import json
from pathlib import Path

from yakkan.export import (
    HF_REPO_ID,
    LICENSE_ID,
    write_card,
    write_documents_jsonl,
    write_gitattributes,
    write_license,
    write_qa_jsonl,
)


def _queries(n_truncated: int = 1, n_total: int = 3) -> list[dict]:
    rows = [{"kind": "term", "related_truncated": False} for _ in range(n_total)]
    for i in range(n_truncated):
        rows[i]["related_truncated"] = True
    return rows


def _documents() -> list[dict]:
    return [
        {
            "doc_id": "auto-0001--nl-a4-2col-mincho",
            "content_id": "auto-0001",
            "style_id": "nl-a4-2col-mincho",
            "genre": "auto",
            "seed": 1,
            "status": "ready",
            "pages": 16,
            "page_images": 16,
            "chars": 1234,
            "tables": 9,
            "figures": 2,
            "footnotes": 20,
            "refs": 3,
            "qa_items": 45,
        },
        {
            "doc_id": "auto-0009--nl-a4-1col-gothic",
            "content_id": "auto-0009",
            "style_id": "nl-a4-1col-gothic",
            "genre": "auto",
            "seed": 9,
            "status": "failed",
            "pages": 21,
            "page_images": 0,
            "chars": 0,
            "tables": 0,
            "figures": 0,
            "footnotes": 0,
            "refs": 0,
            "qa_items": 0,
        },
    ]


def test_cardはqueriesの実測値を埋め込む(tmp_path: Path) -> None:
    """クエリ数・打ち切り件数を固定値で焼き込まない。

    以前は README のテンプレートに「1,944 クエリ中 28 件」と直書きしており、
    文書構成が変わって実際の件数が動いても `yakkan export` を再実行するだけでは
    更新されなかった（auto-0001 等の caption 修正だけで 1,944→1,946 に動いた）。
    """
    path = write_card(tmp_path, queries=_queries())
    text = path.read_text(encoding="utf-8")
    assert path.name == "README.md", "HF は直下の README.md だけをカードとして読む"
    assert "3 クエリ中" in text
    assert "1 件" in text
    assert "{" not in text.split("```bibtex")[0].replace("{{", ""), "未展開のプレースホルダが残っている"


def test_cardはqueriesが空でも書ける(tmp_path: Path) -> None:
    text = write_card(tmp_path).read_text(encoding="utf-8")
    assert "0 クエリ中" in text


def test_cardのfrontmatterがHFの形式になっている(tmp_path: Path) -> None:
    """HF はカード冒頭の YAML frontmatter からライセンスとコンフィグを読む。

    `license` が無い／`configs` の `path` が実在しないとデータセットビューアが動かない。
    """
    import yaml

    text = write_card(tmp_path, queries=_queries(), documents=_documents()).read_text(encoding="utf-8")
    assert text.startswith("---\n")
    front = yaml.safe_load(text.split("---\n")[1])
    assert front["license"] == LICENSE_ID
    assert front["language"] == ["ja"]
    assert front["task_categories"], "task_categories が空だと HF の検索に出ない"
    names = [c["config_name"] for c in front["configs"]]
    assert names == sorted(set(names)) or len(names) == len(set(names)), "config_name が重複している"
    assert sum(1 for c in front["configs"] if c.get("default")) == 1, "default は 1 つだけ"
    for config in front["configs"]:
        for split in config["data_files"]:
            assert split["path"].endswith(".jsonl"), f"{config['config_name']}: 表形式で読める形にする"


def test_cardはreadyの文書だけを数える(tmp_path: Path) -> None:
    """不合格（`status: failed`）を規模に数えると配布物の申告が過大になる。"""
    text = write_card(tmp_path, documents=_documents(), queries=_queries()).read_text(encoding="utf-8")
    assert "**1 点**" in text
    assert "**16 ページ**" in text


def test_cardにライセンスと帰属と引用が入る(tmp_path: Path) -> None:
    text = write_card(tmp_path).read_text(encoding="utf-8")
    assert "cc-by-4.0" in text
    assert "creativecommons.org/licenses/by/4.0" in text
    assert HF_REPO_ID in text
    assert "@misc{" in text, "引用の書き方が無いと CC BY の帰属ができない"
    assert "架空" in text and "実務の参考" in text, "架空であることの注記は必須"


def test_licenseはCCBYを宣言しフォントの扱いにも触れる(tmp_path: Path) -> None:
    """PDF には字形のサブセットが埋まっているので、CC BY だけで説明しきれない。"""
    text = write_license(tmp_path).read_text(encoding="utf-8")
    assert "Creative Commons Attribution 4.0" in text
    assert "creativecommons.org/licenses/by/4.0/legalcode" in text
    assert "Open Font License" in text and "IPA Font License" in text
    assert "FICTITIOUS" in text


def test_gitattributesがPNGとPDFをLFSに入れる(tmp_path: Path) -> None:
    """LFS に入れないと HF Hub が大きなバイナリを弾く（PNG は 600MiB 超ある）。"""
    text = write_gitattributes(tmp_path).read_text(encoding="utf-8")
    assert "*.png filter=lfs" in text
    assert "*.pdf filter=lfs" in text
    assert "*.jsonl filter=lfs" not in text, "正解は差分が読めるよう LFS に入れない"


def test_documents_jsonlは1行1文書で型の揺れる列を落とす(tmp_path: Path) -> None:
    n = write_documents_jsonl(tmp_path, _documents())
    rows = [
        json.loads(line) for line in (tmp_path / "documents.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert n == len(rows) == 2, "failed も素性として載せる（manifest と件数を合わせる）"
    assert {r["doc_id"] for r in rows} == {d["doc_id"] for d in _documents()}
    assert "checksums" not in rows[0] and "errors" not in rows[0]
    assert len({tuple(sorted(r)) for r in rows}) == 1, "列が揺れると表形式で読めない"


def _write_qa(doc_dir: Path) -> None:
    doc_dir.mkdir(parents=True, exist_ok=True)
    (doc_dir / "qa.json").write_text(
        json.dumps(
            {
                "doc_id": doc_dir.name,
                "items": [
                    {
                        "id": "qa_auto_001",
                        "type": "count",
                        "question": "何条あるか",
                        "answer": 5.0,
                        "answer_type": "number",
                        "evidence": ["a1"],
                        "page_hint": [3],
                        "source": "auto",
                    },
                    {
                        "id": "qa_auto_002",
                        "type": "extract",
                        "question": "だれが",
                        "answer": "保険契約者",
                        "answer_type": "string",
                        "evidence": ["a2"],
                        "page_hint": [4],
                        "source": "auto",
                    },
                    {
                        "id": "qa_authored_001",
                        "type": "negative",
                        "question": "免責は",
                        "answer": ["故意", "地震"],
                        "answer_type": "list",
                        "evidence": ["a3"],
                        "page_hint": [5],
                        "source": "authored",
                    },
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )


def test_qa_jsonlはanswerの3つの型を別の列に分ける(tmp_path: Path) -> None:
    """Arrow は 1 列に文字列・数値・配列を混ぜられない。

    `qa.json` の `answer` は `string` / `number` / `list` の 3 型をとる（実測 3,641 / 1,107 / 337）。
    そのまま 1 列に流すと HF のデータセットビューアが型推論で落ちる。
    """
    docs = _documents()
    _write_qa(tmp_path / docs[0]["doc_id"])
    _write_qa(tmp_path / docs[1]["doc_id"])  # failed はスキップされる
    n = write_qa_jsonl(tmp_path, docs)
    rows = [json.loads(line) for line in (tmp_path / "qa.jsonl").read_text(encoding="utf-8").splitlines()]
    assert n == len(rows) == 3, "ready の文書だけを合流させる"
    assert len({tuple(sorted(r)) for r in rows}) == 1, "列が揺れると表形式で読めない"
    by_id = {r["qa_id"]: r for r in rows}
    number = by_id["qa_auto_001"]
    assert number["answer_number"] == 5.0
    assert number["answer_text"] == "5", "整数値の答えを 5.0 と見せない"
    assert number["answer_list"] == []
    string = by_id["qa_auto_002"]
    assert (string["answer_text"], string["answer_number"], string["answer_list"]) == ("保険契約者", None, [])
    listed = by_id["qa_authored_001"]
    assert listed["answer_list"] == ["故意", "地震"]
    assert listed["answer_number"] is None
    assert listed["source"] == "authored"
    for row in rows:
        for key in ("answer_text", "answer_type", "doc_id", "genre"):
            assert isinstance(row[key], str)
