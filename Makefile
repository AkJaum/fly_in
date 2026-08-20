NAME := fly_in
PYTHON := python3
MODULE := src.fly_in
MAP ?= map.txt
REQUIREMENTS := requirements.txt

.PHONY: help install run debug clean lint lint-strict test

help:
	@echo "Fly-in development commands:"
	@echo "  make install              Install development dependencies"
	@echo "  make run [MAP=map.txt]    Run the project with a map"
	@echo "  make debug [MAP=map.txt]  Run the project with pdb"
	@echo "  make clean                Remove Python caches"
	@echo "  make lint                 Run flake8 and required mypy checks"
	@echo "  make lint-strict          Run flake8 and mypy --strict"
	@echo "  make test                 Run the complete test suite"

install:
	$(PYTHON) -m pip install -r $(REQUIREMENTS)

run:
	$(PYTHON) -m $(MODULE) $(MAP)

debug:
	$(PYTHON) -m pdb -m $(MODULE) $(MAP)

clean:
	@find . -type d -name "__pycache__" -prune -exec rm -rf {} +
	@find . -type f -name "*.py[co]" -delete
	@rm -rf .mypy_cache .pytest_cache .ruff_cache

lint:
	@echo "Running flake8 and mypy..."
	@$(PYTHON) -m flake8 --jobs=1 src tests
	@$(PYTHON) -m mypy src tests --warn-return-any \
		--warn-unused-ignores --ignore-missing-imports \
		--disallow-untyped-defs --check-untyped-defs

lint-strict:
	@echo "Running flake8 and mypy --strict..."
	@$(PYTHON) -m flake8 --jobs=1 src tests
	@$(PYTHON) -m mypy src tests --strict

test:
	$(PYTHON) -m tests.friendly_runner
