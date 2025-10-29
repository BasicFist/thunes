# Strategy Plugin Metadata Guide

**Last Updated**: 2025-10-29

This guide explains how to define metadata for new strategy plugins so they plug
seamlessly into the optimization and re-optimization pipeline.

---

## 1. Strategy Skeleton

Every strategy must inherit from `BaseStrategy` and define a `StrategyMetadata`
object describing its parameters.

```python
from src.strategies import BaseStrategy, StrategyMetadata, register_strategy


@register_strategy(aliases=("my_rl",))
class MyRLStrategy(BaseStrategy):
    metadata = StrategyMetadata(
        name="MY_RL",
        description="Policy-gradient strategy using Stable-Baselines3 PPO",
        parameters={
            "policy_path": {"type": "str", "default": "artifacts/models/ppo.zip"},
            "lookback": {"type": "int", "default": 256, "min": 128, "max": 1024},
            "freq": {"type": "str", "default": "1h"},
        },
    )

    def __init__(self, policy_path: str, lookback: int, freq: str = "1h") -> None:
        super().__init__(policy_path=policy_path, lookback=lookback, freq=freq)
        ...
```

Use the metadata fields below to describe each parameter.

---

## 2. Metadata Schema

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `type` | `"int" | "float" | "str" | "bool"` | ✅ | Controls Optuna sampler behaviour |
| `default` | `Any` | ✅ | Value used when not provided (also stored for run history) |
| `min`/`max` | `int`/`float` | ⚠️ | Defines tunable range; required for hyperparameter optimization |
| `step` | `float` | Optional | Granularity for discrete floats (e.g., 0.1) |
| `log` | `bool` | Optional | Sample on log scale (positive values only) |
| `less_than` / `greater_than` | `str` | Optional | Enforce relational constraint against another parameter |
| `less_than_equal` / `greater_than_equal` | `str` | Optional | Inclusive relational constraint |
| `choices` | `list[Any]` | Optional | Categorical search space (future extension) |

**Best practices**:

- Always supply `min` and `max` for numerical parameters so Optuna can tune them.
- Use relational constraints for monotonic parameters (e.g., `fast_window < slow_window`).
- Keep `freq` parameters defaulted; the optimization helpers automatically
  override it with the CLI timeframe.

---

## 3. RL / Hugging Face Strategy Guidelines

1. **Model Paths**: Store pretrained weights under `artifacts/models/` and
   reference them via metadata defaults (`policy_path`). Add validation in the
   strategy constructor to ensure the file exists.
2. **Observation Windows**: Expose `lookback` or `context_window` as tunable
   integers with guarded ranges.
3. **Action Scaling**: If the model expects normalized actions, include boolean
   flags or scaling factors so execution can invert transforms.
4. **Inference Device**: Add a `device` parameter (choices: `"cpu"`, `"cuda"`).
   Keep defaults aligned with production hardware.
5. **HF Integration**: When loading from Hugging Face Hub, allow the metadata to
   accept a `repo_id` string. Use environment variables or `.env` entries for
   API tokens if required.

Example metadata snippet for a Hugging Face LLM assistant strategy:

```python
metadata = StrategyMetadata(
    name="LLM_SIGNAL",
    description="LLM-assisted sentiment scoring using HF pipeline",
    parameters={
        "model_id": {"type": "str", "default": "latchkeyChild/deepseek-trading-assistant"},
        "temperature": {"type": "float", "default": 0.2, "min": 0.0, "max": 1.0, "step": 0.05},
        "context_tokens": {"type": "int", "default": 800, "min": 200, "max": 1600},
        "freq": {"type": "str", "default": "1h"},
    },
)
```

See `src/strategies/nlp/sentiment_lm.py` for a complete, production-ready example that loads
`distilbert-base-uncased-finetuned-sst-2-english`, enforces CPU inference, and exposes
lookback/threshold tuning ranges.

---

## 4. Testing Checklist

- Add unit tests that instantiate the strategy with default parameters.
- Extend `tests/test_optimize_utils.py` or create a new module covering custom
  constraints/metadata.
- Update `docs/FEATURES-COMPREHENSIVE.md` with a bullet describing the new
  strategy once merged.

---

## 5. Updating the Scheduler

The weekly re-optimization job can target any registered strategy:

```python
from src.orchestration.scheduler import TradingScheduler

scheduler = TradingScheduler()
scheduler.schedule_signal_check(interval_minutes=10)
scheduler.schedule_daily_summary(hour=23, minute=0)
scheduler.schedule_weekly_reoptimization(
    day_of_week="sun", hour=3, strategy="my_rl", lookback_days=21, n_trials=40
)
scheduler.start()
```

The job writes optimized parameters to `artifacts/optimize/current_parameters.json`,
which the `PaperTrader` hot-reloads before each execution cycle.
