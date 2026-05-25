.PHONY: install test demo clean build docker docker-test

# ──────────────────────────────────────────────
# Anchor Agent — Makefile
# ──────────────────────────────────────────────

# Install package
install:
	pip install -e .

# Run all tests
test:
	python -m pytest tests/test_agent.py -v --tb=short

# Run single test class
test-factcheck:
	python -m pytest tests/test_agent.py::TestFactCheckMode -v

test-workflow:
	python -m pytest tests/test_agent.py::TestWorkflowMode -v

test-creative:
	python -m pytest tests/test_agent.py::TestCreativeMode -v

test-classifier:
	python -m pytest tests/test_agent.py::TestClassifier -v

test-reporter:
	python -m pytest tests/test_agent.py::TestReporter -v

test-integration:
	python -m pytest tests/test_agent.py::TestIntegration -v

# Run all demos
demo:
	python run_demo.py

# Run single demo scenario
demo-1:
	python run_demo.py --scenario 1

demo-5:
	python run_demo.py --scenario 5

demo-10:
	python run_demo.py --scenario 10

# Docker build
docker:
	docker build -t anchor-demo-agent .

# Docker test
docker-test: docker
	docker run --rm anchor-demo-agent

# Clean
clean:
	rm -rf build/ dist/ *.egg-info __pycache__ .pytest_cache
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name '*.pyc' -delete

# list scenarios
list:
	python run_demo.py --list

.PHONY: help
help:
	@echo "Anchor Agent — Makefile"
	@echo ""
	@echo "install         pip install -e ."
	@echo "test            Run all tests"
	@echo "demo            Run all demos"
	@echo "docker          Build Docker image"
	@echo "docker-test     Build and test in Docker"
	@echo "clean           Clean build artifacts"
	@echo "list            List demo scenarios"
