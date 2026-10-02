.PHONY: help install dev lint format test clean

help:
	@echo "AgentScanner Development Commands"
	@echo "=================================="
	@echo "  make install   - Install the package in development mode"
	@echo "  make dev       - Install with dev dependencies"
	@echo "  make lint      - Run linting checks"
	@echo "  make format    - Format code with black"
	@echo "  make test      - Run tests"
	@echo "  make clean     - Remove build artifacts"

install:
	pip install -e .

dev:
	pip install -e ".[dev,llm]"

lint:
	ruff check src tests
	mypy src

format:
	black src tests

test:
	pytest tests/ -v --cov=src

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type d -name .pytest_cache -exec rm -rf {} +
	find . -type d -name .mypy_cache -exec rm -rf {} +
	rm -rf build dist *.egg-info
