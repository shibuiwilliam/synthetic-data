# insurance-contracts-calculation — 開発用ターゲット（TASK.md §10「毎回の確認」）
SHELL := /bin/bash

# 本体の venv に同居させる（TASK.md §2.3）。uv は親プロジェクトを指す。
PY  ?= PYTHONPATH=src uv run --project ..
# macOS: WeasyPrint が Homebrew の dylib を見つけられない（../docs/gotchas.md）
DYLD_FALLBACK_LIBRARY_PATH ?= /opt/homebrew/lib
export DYLD_FALLBACK_LIBRARY_PATH

BASE ?= ../content/auto-0001
SEED ?= 1
OUT  ?= out
DOC  ?= out/auto-0001-c1

DATASET ?= dataset

.PHONY: help check test test-all lint fmt gen verify clean examples datacard datacard-check

help:                ## ターゲット一覧
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-14s %s\n", $$1, $$2}'

check: lint test datacard-check   ## lint + テスト + データカードの鮮度（作業の最後に必ず通す）

test:                ## 生成器自身のテスト（slow を除く）
	$(PY) python -m pytest tests -q -m "not slow"

test-all:            ## slow（seed の振り直し）も含めて全部
	$(PY) python -m pytest tests -q

lint:                ## ruff（format 検査 + lint）
	uv run --project .. ruff format --check .
	uv run --project .. ruff check .

fmt:                 ## ruff format を適用する
	uv run --project .. ruff format .
	uv run --project .. ruff check --fix .

gen:                 ## 1 文書を生成する: make gen BASE=../content/auto-0001 SEED=1
	$(PY) python -m insurance_contracts_calculation.cli generate --base $(BASE) --out $(OUT) --seed $(SEED)

verify:              ## 出力に検証ゲートを再実行する: make verify DOC=out/auto-0001-c1
	$(PY) python -m insurance_contracts_calculation.cli verify $(DOC)

datacard:            ## データカードを書き出す: make datacard DATASET=dataset
	$(PY) python -m insurance_contracts_calculation.cli datacard update $(DATASET)

datacard-check:      ## カードが現在の dataset/ と合っているか（文書が無ければ飛ばす）
	$(PY) python -m insurance_contracts_calculation.cli datacard check $(DATASET)

examples:            ## 回帰基準 examples/ を作り直す（差分の理由をコミットメッセージに書く）
	$(PY) python -m insurance_contracts_calculation.cli generate --base ../content/auto-0001 --out examples --seed 4

clean:               ## 一時生成物を消す（examples/ は消さない）
	rm -rf out .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
