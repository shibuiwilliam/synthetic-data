"""`yakkan/export.py` の配布成果物（Hugging Face 向け。docs/distribution.md）。

以前は `README.md`（読み方）と `DATASET_CARD.md`（HF 形式の要約）が別々にあったが、
**HF はリポジトリ直下の `README.md` だけをデータセットカードとして読む**ので 1 枚に統合した。
ここでは「統計値を固定文字列で焼き込まない」ことと、**HF が実際に読める形**であることを検査する。
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from yakkan.export import (
    AUP_URL,
    HF_REPO_ID,
    LICENSE_ID,
    PRETTY_NAME_EN,
    RETIRED_SEARCH_ARTIFACTS,
    SEARCH_HF_REPO_ID,
    SEARCH_PRETTY_NAME_EN,
    remove_retired,
    write_card,
    write_documents_jsonl,
    write_gitattributes,
    write_license,
    write_qa_jsonl,
    write_search_card,
    write_search_license,
    write_search_sha256sums,
)


def _without_fenced_code(text: str) -> str:
    """フェンス付きコードブロック（```json のサンプルや ```bibtex）を取り除く。

    **未展開の `.format()` プレースホルダ**（カードが壊れている証拠）を検査するための前処理。
    JSON サンプルや BibTeX は中に生の `{`/`}` を持つ正当な内容なので、プレースホルダ検査の対象外にする。
    """
    return re.sub(r"```.*?```", "", text, flags=re.DOTALL)


def _queries(n_truncated: int = 1, n_total: int = 3) -> list[dict]:
    rows = [{"kind": "term", "related_truncated": False} for _ in range(n_total)]
    for i in range(n_truncated):
        rows[i]["related_truncated"] = True
    return rows


def _passages(n: int = 2) -> list[dict]:
    kinds = ("article", "table")
    return [
        {
            "passage_id": f"auto-0001--nl-a4-2col-mincho::e{i}",
            "doc_id": "auto-0001--nl-a4-2col-mincho",
            "content_id": "auto-0001",
            "genre": "auto",
            "kind": kinds[i % len(kinds)],
            "title": f"t{i}",
            "text": f"本文 {i}",
        }
        for i in range(n)
    ]


def _qrels() -> list[dict]:
    return [
        {"query_id": "q1", "passage_id": "auto-0001--nl-a4-2col-mincho::e0", "grade": 2},
        {"query_id": "q1", "passage_id": "auto-0001--nl-a4-2col-mincho::e1", "grade": 1},
    ]


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
    """クエリ数を固定値で焼き込まない。

    以前は README のテンプレートに「1,944 クエリ中 28 件」と直書きしており、
    文書構成が変わって実際の件数が動いても `yakkan export` を再実行するだけでは
    更新されなかった（auto-0001 等の caption 修正だけで 1,944→1,946 に動いた）。
    """
    path = write_card(tmp_path, queries=_queries(), passages=_passages(), qrels=_qrels())
    text = path.read_text(encoding="utf-8")
    assert path.name == "README.md", "HF は直下の README.md だけをカードとして読む"
    assert "クエリ **3**" in text
    assert "{" not in _without_fenced_code(text).replace("{{", ""), "未展開のプレースホルダが残っている"


def test_cardはqueriesが空でも書ける(tmp_path: Path) -> None:
    text = write_card(tmp_path).read_text(encoding="utf-8")
    assert "クエリ **0**" in text


def test_cardは検索評価セットを別データセットとして案内する(tmp_path: Path) -> None:
    """検索評価セットは別のリポジトリで配る（2026-10-08・docs/distribution.md §1）。

    本体のカードに `search/*.jsonl` の config が残っていると、HF のデータセット
    ビューアが**上げていないファイル**を読もうとして config ごと壊れる。
    """
    import yaml

    text = write_card(tmp_path, queries=_queries(), documents=_documents()).read_text(encoding="utf-8")
    front = yaml.safe_load(text.split("---\n")[1])
    paths = [s["path"] for c in front["configs"] for s in c["data_files"]]
    assert not [p for p in paths if p.startswith("search/")], "search/ は別リポジトリなので config に出さない"
    assert SEARCH_HF_REPO_ID in text, "分けた先への案内が無いと検索セットに到達できない"
    assert "## 検索評価セットは別のデータセット" in text


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
    assert front["pretty_name"] == PRETTY_NAME_EN, "Hub の表示名は英語（姉妹プロジェクトと同じ設計）"
    assert front["multilinguality"] == "monolingual"
    assert front["annotations_creators"] == ["machine-generated"], "人手注釈ではないことを申告する"
    assert front["source_datasets"] == ["original"]
    assert front["task_categories"], "task_categories が空だと HF の検索に出ない"
    names = [c["config_name"] for c in front["configs"]]
    assert names == sorted(set(names)) or len(names) == len(set(names)), "config_name が重複している"
    assert sum(1 for c in front["configs"] if c.get("default")) == 1, "default は 1 つだけ"
    for config in front["configs"]:
        for split in config["data_files"]:
            assert split["path"].endswith(".jsonl"), f"{config['config_name']}: 表形式で読める形にする"


def test_search_cardはそれ自体がHFのカードになる(tmp_path: Path) -> None:
    """`dataset/search/` をそのまま別リポジトリの直下として上げるので、README.md がカード。"""
    import yaml

    path = write_search_card(
        tmp_path / "search", queries=_queries(), passages=_passages(), qrels=_qrels(), n_corpus_docs=7
    )
    text = path.read_text(encoding="utf-8")
    assert path.name == "README.md" and path.parent.name == "search"
    assert text.startswith("---\n")
    front = yaml.safe_load(text.split("---\n")[1])
    assert front["license"] == LICENSE_ID
    assert front["pretty_name"] == SEARCH_PRETTY_NAME_EN
    assert front["source_datasets"] == [f"extended|{HF_REPO_ID}"], "派生元の申告が無いと孤立する"
    assert front["annotations_creators"] == ["machine-generated"]
    assert front["size_categories"], "size_categories は行数の実測から選ぶ"
    names = [c["config_name"] for c in front["configs"]]
    assert names == ["passages", "queries", "qrels"]
    assert sum(1 for c in front["configs"] if c.get("default")) == 1, "default は 1 つだけ"
    for config in front["configs"]:
        for split in config["data_files"]:
            assert "/" not in split["path"], "リポジトリ直下に置くので相対パスにしない"
    assert HF_REPO_ID in text, "文書本体への案内が無いと紙面に辿れない"
    assert "{" not in _without_fenced_code(text).replace("{{", ""), "未展開のプレースホルダが残っている"


def test_search_cardが検索固有の実測値と注意点を持つ(tmp_path: Path) -> None:
    """設計・ベースライン・打ち切りの説明は**評価セット側のカード**が持つ（本体から移した）。"""
    text = write_search_card(
        tmp_path / "search",
        queries=_queries(),
        passages=_passages(),
        qrels=_qrels(),
        n_corpus_docs=7,
        baseline_table="| kind | nDCG@1 |\n|---|---|\n| term | 0.90 |",
    ).read_text(encoding="utf-8")
    assert "3 クエリ中" in text and "1 件" in text, "打ち切り件数を固定値で焼き込まない"
    assert "| term | 0.90 |" in text, "ベースラインの実測表が入っていない"
    assert "7 文書" in text, "コーパスの文書数を固定値で焼き込まない"
    assert "index_setting" in text, "filters を索引しない検索器への注意が要る"
    assert "no_answer" in text and "false_positive_rate" in text
    assert "## ⚠ Not for training AI models" in text, "英語面の告知が無いと英語圏の閲覧者に伝わらない"
    assert "# 日本語版 — 検索評価セットの読み方" in text, "英語面＋日本語面の二層にする"
    assert text.index("## ⚠ Not for training AI models") < text.index("## What it is for")
    assert "## ⚠ AI モデルの学習・蒸留には使えない" in text
    assert AUP_URL in text and "評価は学習ではない" in text and "EVALUATION IS NOT TRAINING" in text
    assert "架空" in text and "実務の参考" in text
    # 列名は jsonl から実測する（スキーマを固定文字列で書くと生成器と食い違う）
    assert "`related_truncated`" in text and "`passage_id`" in text
    assert "| パッセージの種別 | 件数 |" in text and "| クエリの種別 | 件数 |" in text
    assert "| `grade 2` | 1 |" in text, "適合判定の内訳を実測で出す"
    assert "SHA256SUMS" in text, "配布物の一覧に SHA256SUMS を載せる"


def test_search_licenseは短縮形でフォントには触れない(tmp_path: Path) -> None:
    """検索評価セットには PDF もフォントも無い。学習禁止の告知は本体と同じことを言う。

    姉妹プロジェクト contracts と同じ設計で、**本体より短い専用の本文**を使う
    （存在しないフォントの節や「及ぶ範囲」の長い説明を出さない）。
    """
    text = write_search_license(tmp_path / "search").read_text(encoding="utf-8")
    assert text.startswith(SEARCH_PRETTY_NAME_EN), "リポジトリの名前で始める"
    assert "Creative Commons Attribution 4.0" in text
    assert "NOT FOR TRAINING AI MODELS" in text and AUP_URL in text
    assert "EVALUATION IS NOT TRAINING" in text
    assert "NOTICE, not an additional condition" in text and "2(a)(5)(B)" in text
    assert "Open Font License" not in text and "IPA Font License" not in text
    assert "WHAT THIS LICENSE COVERS" not in text, "本体の長い説明は持ち込まない"
    assert HF_REPO_ID in text, "パッセージの出どころ（本体データセット）を示す"
    assert "FICTITIOUS" in text, "実在の約款と誤解されないようにする"


def test_search_sha256sumsは自分のルートからの相対パスで数える(tmp_path: Path) -> None:
    """`dataset/search/` がそのままリポジトリの直下になるので、`search/` を付けない。

    自分自身と隠しファイルは数えない（`sha256sum -c` がそのまま通る形）。
    """
    search = tmp_path / "search"
    search.mkdir()
    (search / "passages.jsonl").write_text('{"a": 1}\n', encoding="utf-8")
    (search / "README.md").write_text("card\n", encoding="utf-8")
    (search / ".hidden").write_text("x\n", encoding="utf-8")
    text = write_search_sha256sums(search).read_text(encoding="utf-8")
    names = [line.split("  ", 1)[1] for line in text.splitlines()]
    assert names == ["README.md", "passages.jsonl"], "名前順・相対パス・自分自身は数えない"
    assert ".hidden" not in text
    assert all(len(line.split("  ")[0]) == 64 for line in text.splitlines())


def test_検索側のgitattributesは廃止されて生成器が片付ける(tmp_path: Path) -> None:
    """LFS 対象が無いリポジトリに置いても意味が無いので廃止した（2026-10-09）。

    `dataset/` は手編集禁止なので、**古い名前の後片付けも生成器の仕事**にする。
    """
    search = tmp_path / "search"
    search.mkdir()
    (search / ".gitattributes").write_text("*.jsonl text\n", encoding="utf-8")
    assert remove_retired(search, RETIRED_SEARCH_ARTIFACTS) == [".gitattributes"]
    assert not (search / ".gitattributes").exists()


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


def test_licenseが学習と蒸留の禁止を明記する(tmp_path: Path) -> None:
    """本文は Claude の Output なので、Anthropic Usage Policy の制限を受領者に伝える義務がある。

    **告知であってライセンス条件ではない**ことも書く——CC BY 4.0 第 2 条(a)(5)(B)が
    下流への追加制限を禁じているので、条件として書くと CC BY 違反になる。
    """
    text = write_license(tmp_path).read_text(encoding="utf-8")
    assert "NOT FOR TRAINING AI MODELS" in text
    for word in ("TRAIN", "FINE-TUNE", "DISTILL", "LLM", "VLM"):
        assert word in text, word
    assert AUP_URL in text, "制限の出どころ（AUP）へのリンクが無いと確かめようがない"
    assert "EVALUATION IS NOT TRAINING" in text, "評価が除かれることを書かないと目的を潰す"
    assert "NOTICE, not an additional condition" in text
    assert "2(a)(5)(B)" in text


def test_cardが学習と蒸留の禁止を目立つ節で明記する(tmp_path: Path) -> None:
    """カードは HF 上の唯一の説明面なので、ライセンス節より前に出す。"""
    text = write_card(tmp_path).read_text(encoding="utf-8")
    heading = "## ⚠ AI モデルの学習・蒸留には使えない"
    assert heading in text
    assert text.index(heading) < text.index("## ライセンス"), "禁止の節はライセンス節より前に置く"
    assert "蒸留" in text and "ファインチューニング" in text
    assert AUP_URL in text
    assert "評価は学習ではない" in text, "評価が除かれることを書かないとデータセットの目的を潰す"
    assert "告知であってライセンス条件ではない" in text


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
