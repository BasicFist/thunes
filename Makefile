.PHONY: help install install-core install-research install-dev install-all test lint format backtest optimize paper clean

help:  ## Show this help message
	@echo "Available commands:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

install-core:  ## Install core dependencies only (production runtime ~400 MB)
	python -m pip install --upgrade pip
	pip install -r requirements-core.txt

install-research:  ## Install research dependencies (includes core + backtest/optimize)
	python -m pip install --upgrade pip
	pip install -r requirements-research.txt

install-dev:  ## Install development dependencies (includes core + testing/linting)
	python -m pip install --upgrade pip
	pip install -r requirements-dev.txt
	pre-commit install

install-all:  ## Install all dependencies (core + research + dev)
	python -m pip install --upgrade pip
	pip install -r requirements-research.txt -r requirements-dev.txt
	pre-commit install

install:  ## Alias for install-all (backward compatibility)
	@echo "⚠️  Using 'make install-all' for complete installation"
	@echo "💡 Tip: Use 'make install-core' for production, 'make install-dev' for development"
	$(MAKE) install-all

test:  ## Run tests (parallel execution via pytest-xdist)
	pytest

lint:  ## Run linters (ruff + mypy)
	ruff check src tests
	mypy src

format:  ## Format code with black and ruff
	black src tests
	ruff check --fix src tests

pre-commit:  ## Run all pre-commit hooks
	pre-commit run --all-files

backtest:  ## Run backtest (default: BTCUSDT 1h)
	python -m src.backtest.run_backtest --symbol BTCUSDT --timeframe 1h --lookback 90

optimize:  ## Run Optuna optimization (default: 25 trials)
	python -m src.optimize.run_optuna --trials 25 --timeout 300

paper:  ## Run paper trading (testnet)
	python -m src.live.paper_trader --symbol BTCUSDT --quote 10 --tf 1h

balance:  ## Check testnet balance
	python -c "from src.live.paper_trader import PaperTrader; t = PaperTrader(); print(f'USDT: {t.get_account_balance(\"USDT\")}')"

clean:  ## Clean artifacts and cache
	rm -rf .pytest_cache .mypy_cache .ruff_cache __pycache__
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete

docker-build:  ## Build Docker image
	docker build -t thunes:latest .

docker-run:  ## Run Docker container
	docker-compose up -d

docker-stop:  ## Stop Docker container
	docker-compose down

logs:  ## Tail logs
	tail -f logs/*.log
