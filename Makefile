.PHONY: install test lint typecheck format precommit demo check

install:
	python3 -m venv .venv
	.venv/bin/python -m pip install --upgrade pip
	.venv/bin/pip install -e ".[highs,dev]"

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/ruff check .

format:
	.venv/bin/ruff format .

typecheck:
	.venv/bin/mypy src/ors

precommit:
	.venv/bin/pre-commit run --all-files

check: lint typecheck test

demo:
	.venv/bin/python examples/diagnose_demo.py
