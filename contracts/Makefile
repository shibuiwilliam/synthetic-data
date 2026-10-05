# keiyaku-synth — 開発用ターゲット（CLAUDE.md §10 / §11）
SHELL := /bin/bash
UV    ?= uv

# macOS: Homebrew の dylib は dyld の既定検索パスに無いため WeasyPrint が import できない。
# 詳細は docs/gotchas.md「WeasyPrint / macOS」。Linux では無害なので無条件に渡す。
DYLD_FALLBACK_LIBRARY_PATH ?= /opt/homebrew/lib
export DYLD_FALLBACK_LIBRARY_PATH

.PHONY: help setup check fmt lint test manifest-check datacard-check publish-check doctor smoke probe doc batch publish clean

help:                ## ターゲット一覧
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*?## ' '{printf "  %-10s %s\n", $$1, $$2}'

setup:               ## 依存を導入する（uv sync）
	$(UV) sync

check: lint test manifest-check datacard-check publish-check  ## lint + テスト + manifest・データカード・公開用の面の鮮度（コミット前に必ず通す）

fmt:                 ## ruff format を適用する
	$(UV) run ruff format .
	$(UV) run ruff check --fix .

lint:                ## ruff（format 検査 + lint）
	$(UV) run ruff format --check .
	$(UV) run ruff check .

test:                ## pytest
	$(UV) run pytest

manifest-check:      ## dataset/manifest.json が実ファイルと合っているか（dataset/ が無ければ飛ばす）
	@if [ -f dataset/manifest.json ]; then \
		$(UV) run keiyaku manifest check --no-verify; \
	else \
		echo "dataset/ が無いので manifest の検査は飛ばす"; \
	fi

datacard-check:      ## dataset/data-card.md が実ファイルと合っているか（dataset/ が無ければ飛ばす）
	@if [ -f dataset/manifest.json ]; then \
		$(UV) run keiyaku datacard check; \
	else \
		echo "dataset/ が無いのでデータカードの検査は飛ばす"; \
	fi

publish-check:       ## dataset/ の公開用の面（カード・views・SHA256SUMS）が実ファイルと合っているか
	@if [ -f dataset/manifest.json ]; then \
		$(UV) run keiyaku publish check; \
	else \
		echo "dataset/ が無いので公開用の面の検査は飛ばす"; \
	fi

doctor:              ## 実行環境の検査
	$(UV) run keiyaku doctor

smoke:               ## smoke PDF と PNG を生成する（scratch/smoke/）
	$(UV) run python scripts/smoke_render.py

probe:               ## WeasyPrint の挙動を実測する（設計を決める前に走らせる）
	$(UV) run python scripts/probe_weasy.py

doc:                 ## 1 文書を生成する: make doc CONTENT=nda-0001 STYLE=ct-a4-1col-mincho
ifndef CONTENT
	$(error CONTENT= を指定する。例: make doc CONTENT=nda-0001 STYLE=ct-a4-1col-mincho)
endif
ifndef STYLE
	$(error STYLE= を指定する。例: make doc CONTENT=nda-0001 STYLE=ct-a4-1col-mincho)
endif
	$(UV) run keiyaku lint content/$(CONTENT)
	$(UV) run keiyaku build content/$(CONTENT)
	$(UV) run keiyaku render content/$(CONTENT) --style $(STYLE)
	$(UV) run keiyaku verify dataset/$(CONTENT)--$(STYLE)
	$(UV) run keiyaku qa dataset/$(CONTENT)--$(STYLE)

batch:               ## バッチ生成: make batch SPEC=specs/batch_v1.yaml
ifndef SPEC
	$(error SPEC= を指定する。例: make batch SPEC=specs/batch_v1.yaml)
endif
	$(UV) run keiyaku batch $(SPEC)
	$(UV) run keiyaku manifest update
	$(UV) run keiyaku manifest check
	$(UV) run keiyaku export
	$(UV) run keiyaku datacard check

publish:             ## 公開用の面を作り直し、何が上がるかを数える（通信しない）
	$(UV) run keiyaku publish update
	$(UV) run python scripts/verify_views.py
	$(UV) run python scripts/upload_hf.py --dataset dataset

clean:               ## 一時生成物を消す（dataset/ は消さない）
	rm -rf scratch .pytest_cache .ruff_cache
	find . -name __pycache__ -type d -prune -not -path './.venv/*' -exec rm -rf {} +
