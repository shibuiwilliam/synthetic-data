"""生成器自身のテストの共通部品。

本体（`yakkan`）が import できない環境では、本体を使うテストを飛ばす。
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parent
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent / "unit"))

#: 回帰の基準に使う seed。
#: 3 つの配置（条・別表・特約）がすべて出て、かつ本体の描画が通るものを選んである
#: （本体の描画は内容の長さに敏感で、seed によっては例外になる。`docs/base_rendering_note.md`）。
EXAMPLE_SEED = 4
EXAMPLES = ROOT / "examples"
EXAMPLE_DOC = EXAMPLES / "auto-0001-c1"
BASE_CONTENT = REPO / "content" / "auto-0001"

# macOS で WeasyPrint が Homebrew の dylib を見つけられない（../docs/gotchas.md）
os.environ.setdefault("DYLD_FALLBACK_LIBRARY_PATH", "/opt/homebrew/lib")


def _yakkan_available() -> bool:
    try:
        import yakkan  # noqa: F401
    except Exception:  # noqa: BLE001
        return False
    return True


needs_base = pytest.mark.skipif(not _yakkan_available(), reason="本体（yakkan）が import できない")


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO


@pytest.fixture(scope="session")
def base_content() -> Path:
    return BASE_CONTENT


@pytest.fixture(scope="session")
def example_doc() -> Path:
    return EXAMPLE_DOC
