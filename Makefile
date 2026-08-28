NAME := fly_in
SYSTEM_PYTHON := python3
VENV := .venv
VENV_PYTHON := $(VENV)/bin/python
PYTHON := $(if $(wildcard $(VENV_PYTHON)),$(VENV_PYTHON),$(SYSTEM_PYTHON))
MODULE := src.fly_in
WEB_MODULE := src.web_app
MAP ?= map.txt
PORT ?= 8085
REQUIREMENTS := requirements.txt

.PHONY: help install run web debug clean lint lint-strict test

help:
	@echo "Fly-in development commands:"
	@echo "  make install              Install development dependencies"
	@echo "  make run [MAP=map.txt]    Run the project with a map"
	@echo "  make web [MAP=map.txt] [PORT=8080]  Open the browser visualizer"
	@echo "  make debug [MAP=map.txt]  Run the project with pdb"
	@echo "  make clean                Remove Python caches"
	@echo "  make lint                 Run flake8 and required mypy checks"
	@echo "  make lint-strict          Run flake8 and mypy --strict"
	@echo "  make test                 Run the complete test suite"

install:
	$(SYSTEM_PYTHON) -m venv $(VENV)
	$(VENV_PYTHON) -m pip install -r $(REQUIREMENTS)

run:
	$(PYTHON) -m $(MODULE) $(MAP)

web:
	$(PYTHON) -m $(WEB_MODULE) --map $(MAP) --port $(PORT)

debug:
	$(PYTHON) -m pdb -m $(MODULE) $(MAP)

clean:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type f -name "*.py[co]" -delete
	@rm -rf .mypy_cache .pytest_cache .ruff_cache

lint:
	@echo "Running flake8 and mypy..."
	@$(PYTHON) -m flake8 .
	@$(PYTHON) -m mypy . --warn-return-any \
		--warn-unused-ignores --ignore-missing-imports \
		--disallow-untyped-defs --check-untyped-defs

lint-strict:
	@echo "Running flake8 and mypy --strict..."
	@$(PYTHON) -m flake8 .
	@$(PYTHON) -m mypy . --strict

test:
	$(PYTHON) -m tests.friendly_runner
