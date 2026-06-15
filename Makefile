# PyTorch Inference Platform — developer entrypoints
.DEFAULT_GOAL := help
PY ?= python
PIP ?= pip

.PHONY: help install install-ml dev-install lint type test up down logs \
        run-gateway run-scheduler run-worker run-metrics \
        bench-concurrency bench-pytorch load-test seed-models clean

help: ## Show this help
	@grep -E '^[a-zA-Z0-9_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install: ## Install control-plane deps + the common lib (no torch)
	$(PIP) install -e ".[dev]"
	$(PIP) install -e libs/platform_common

install-ml: ## Install the real PyTorch/ONNX runtime extras
	$(PIP) install -e ".[ml]"

lint: ## Run ruff
	ruff check .

type: ## Run mypy
	mypy libs services

test: ## Run the test suite (uses fakeredis + stub runtime, no torch needed)
	pytest

up: ## Start the full stack via docker compose
	docker compose up --build -d

down: ## Tear down the stack
	docker compose down -v

logs: ## Tail all service logs
	docker compose logs -f --tail=100

run-gateway: ## Run the API gateway locally
	uvicorn services.api_gateway.main:app --host 0.0.0.0 --port 8080 --reload

run-scheduler: ## Run the scheduler locally
	$(PY) -m services.scheduler.main

run-worker: ## Run a single inference worker locally
	$(PY) -m services.inference_worker.main

run-metrics: ## Run the metrics service locally
	uvicorn services.metrics.main:app --host 0.0.0.0 --port 9000

seed-models: ## Generate model artifacts (v1/v2/v3) for the worker
	$(PY) scripts/build_models.py

bench-concurrency: ## Compare naive / async / pool / batched inference
	$(PY) benchmarks/concurrency_comparison.py

bench-pytorch: ## Benchmark eval/no_grad/torchscript/amp/quantization/onnx
	$(PY) benchmarks/pytorch_optimizations.py

load-test: ## Open Locust UI against the gateway
	locust -f loadtest/locustfile.py --host http://localhost:8080

clean: ## Remove caches and generated artifacts
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .pytest_cache .ruff_cache .mypy_cache
