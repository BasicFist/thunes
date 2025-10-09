# Repository Guidelines

## Project Structure & Module Organization
Core trading logic is under `src/`, with baked-in domains such as `src/live/` for paper execution, `src/backtest/` for vectorbt backtests, and `src/risk/` for protective controls. Shared helpers sit in `src/utils/` and configuration defaults in `src/config.py`. Feature-specific docs and retrospectives live in `docs/`. Test suites are grouped in `tests/`, mirroring the module layout. Generated artifacts (Optuna studies, backtest stats) write to `artifacts/`, while persistent logs stream into `logs/`. Operational recipes and scripts are stored in `scripts/` and `monitoring/`.

## Build, Test, and Development Commands
Run `make install-dev` after creating a virtualenv to pull core, research, and tooling dependencies. Use `make lint` for `ruff` and `mypy` checks, and `make format` to apply `black` plus autofixes. Execute `make test` (or plain `pytest`) to run the full parallelised suite with coverage reports in `htmlcov/`. Domain workflows depend on `make backtest`, `make optimize`, and `make paper` for SMA validation, Optuna tuning, and paper trading on Binance Testnet respectively.

## Coding Style & Naming Conventions
Python 3.12 is enforced; keep code type-annotated so `mypy` stays green. Format with `black` (100-character lines) and ensure `ruff` passes—call `pre-commit run --all-files` before submitting. Modules and functions should use `snake_case`, classes `CamelCase`, and constants `UPPER_SNAKE`. Prefer descriptive module splits (e.g., `filters/`, `orchestration/`) and keep strategy configs in `config.py` rather than scattering magic numbers.

## Testing Guidelines
All tests live under `tests/` and follow the `test_*.py` pattern; functions align with `test_*` and async cases require the `asyncio` marker. Generate new fixtures beside the relevant module subfolder. Use `@pytest.mark.slow` for runs exceeding ~5 seconds so suites remain parallel-friendly. Maintain coverage parity—HTML coverage is emitted via `make test` to `htmlcov/index.html`; flag dips in PR descriptions.

## Commit & Pull Request Guidelines
Adopt the conventional prefixes visible in history (`feat:`, `fix:`, `docs:`, `ci:`) and keep subjects under 50 characters with concise, lower-case summaries. Squash speculative commits before pushing. Each PR should outline scope, risks, and validation (`make test`, `make lint`, domain command outputs). Link to Jira/GitHub issues when available, attach screenshots for monitoring dashboards, and highlight any configuration or secret changes required for deploys.

## Environment & Secrets
Copy `.env.template` to `.env` for local runs, supplying Binance Testnet keys and optional Telegram credentials. Never commit filled `.env` files or API keys. When testing order flows, use minimal position sizes and the provided `make balance` helper to confirm sandbox funding.
