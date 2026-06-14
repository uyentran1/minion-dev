# MinionDev Development Commands

.PHONY: install test test-unit test-integration test-watch clean lint

# Install dependencies
install:
	pip install -e ".[test]"

# Run all tests
test:
	pytest

# Run only unit tests (fast, no external dependencies)
test-unit:
	pytest -m "not integration"

# Run integration tests (require AWS credentials)
test-integration:
	pytest -m integration

# Run tests in watch mode (re-run on file changes)
test-watch:
	pytest --looponfail

# Run tests with coverage
test-coverage:
	pytest --cov=src/miniondev --cov-report=term-missing --cov-report=html

# Clean up generated files
clean:
	rm -rf __pycache__ .pytest_cache .coverage htmlcov
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete

# Lint code (if we add linting later)
lint:
	@echo "Linting not configured yet"

# Quick development cycle
dev-cycle: test-unit lint

# Full CI pipeline
ci: test test-coverage lint