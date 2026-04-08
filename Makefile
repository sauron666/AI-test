.PHONY: install start dev test lint clean docker ollama

VENV ?= .venv
PY   ?= $(VENV)/bin/python
PIP  ?= $(VENV)/bin/pip

install:
	./scripts/install.sh

start:
	./scripts/start.sh

dev:
	$(PY) -m uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000

test:
	$(PY) -m pytest -q

lint:
	$(VENV)/bin/ruff check backend tests || true

docker:
	docker compose up --build

ollama:
	./scripts/setup_ollama.sh

clean:
	rm -rf data logs reports/output screenshots artifacts sessions
	find . -name __pycache__ -type d -exec rm -rf {} +
