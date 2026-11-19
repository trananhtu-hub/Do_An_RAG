PYTHON ?= python
ARGS ?=

export PYTHONUTF8 := 1
export PYTHONIOENCODING := utf-8

ifeq ($(OS),Windows_NT)
VENV_PY := .venv/Scripts/python.exe
else
VENV_PY := .venv/bin/python
endif

.PHONY: help install dev test lint ingest eval

help:
	@echo "make install  - Tạo venv, cài phụ thuộc backend và frontend"
	@echo "make dev      - Chạy backend (cổng 8000) và frontend (cổng 3000)"
	@echo "make lint     - ruff + black --check (backend), eslint (frontend)"
	@echo "make test     - pytest (backend)"
	@echo "make ingest   - Nạp PDF vào Supabase (thêm ARGS=--force để nạp lại)"
	@echo "make eval     - Chưa triển khai (Giai đoạn 2/8)"

install:
	$(PYTHON) -m venv .venv
	"$(VENV_PY)" -m pip install --upgrade pip
	"$(VENV_PY)" -m pip install -r backend/requirements-dev.txt -r ingestion/requirements.txt
	npm --prefix frontend install

dev:
	"$(VENV_PY)" scripts/dev.py

test:
	"$(VENV_PY)" -m pytest backend tests/ingestion -q

lint:
	"$(VENV_PY)" -m ruff check backend ingestion scripts tests
	"$(VENV_PY)" -m black --check backend ingestion scripts tests
	npm --prefix frontend run lint

ingest:
	"$(VENV_PY)" -m ingestion.pipeline $(ARGS)

eval:
	@echo "Chưa triển khai — sẽ có ở Giai đoạn 2/8 (xem CLAUDE.md)."
