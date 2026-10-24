.PHONY: test lint typecheck demo check

test:
	.venv/bin/python -m pytest -q

lint:
	.venv/bin/ruff check .

typecheck:
	.venv/bin/mypy src/ors

check: lint typecheck test

demo:
	.venv/bin/python examples/diagnose_demo.py
