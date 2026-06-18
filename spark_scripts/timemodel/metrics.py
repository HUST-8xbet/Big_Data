from __future__ import annotations

import math

import numpy as np


def _finite_float(value: float) -> float | None:
    value = float(value)
    return value if math.isfinite(value) else None


def regression_metrics(
    actual_prices: np.ndarray,
    predicted_prices: np.ndarray,
    current_prices: np.ndarray,
) -> dict:
    actual = np.asarray(actual_prices, dtype=np.float64)
    predicted = np.asarray(predicted_prices, dtype=np.float64)
    current = np.asarray(current_prices, dtype=np.float64)

    if not (len(actual) == len(predicted) == len(current)):
        raise ValueError("actual, predicted and current arrays must have equal length")
    if not len(actual):
        raise ValueError("cannot compute metrics for an empty validation set")

    valid = (
        np.isfinite(actual)
        & np.isfinite(predicted)
        & np.isfinite(current)
        & (actual > 0)
        & (current > 0)
    )
    actual = actual[valid]
    predicted = predicted[valid]
    current = current[valid]
    if not len(actual):
        raise ValueError("validation set contains no finite positive observations")

    error = predicted - actual
    absolute_error = np.abs(error)
    squared_error = error**2
    denominator = np.maximum(np.abs(actual) + np.abs(predicted), 1e-12)

    actual_return = actual / current - 1.0
    predicted_return = predicted / current - 1.0
    return_error = predicted_return - actual_return

    baseline_error = current - actual
    baseline_mae = float(np.mean(np.abs(baseline_error)))
    model_mae = float(np.mean(absolute_error))

    metrics = {
        "sample_count": int(len(actual)),
        "price_mae": _finite_float(model_mae),
        "price_rmse": _finite_float(np.sqrt(np.mean(squared_error))),
        "price_smape_percent": _finite_float(
            np.mean(2.0 * absolute_error / denominator) * 100.0
        ),
        "return_mae": _finite_float(np.mean(np.abs(return_error))),
        "return_rmse": _finite_float(np.sqrt(np.mean(return_error**2))),
        "directional_accuracy": _finite_float(
            np.mean(np.sign(predicted_return) == np.sign(actual_return))
        ),
        "baseline_price_mae": _finite_float(baseline_mae),
        "baseline_price_rmse": _finite_float(
            np.sqrt(np.mean(baseline_error**2))
        ),
    }
    metrics["mae_improvement_over_baseline_percent"] = _finite_float(
        (baseline_mae - model_mae) / baseline_mae * 100.0
        if baseline_mae > 0
        else 0.0
    )
    metrics["quality_status"] = (
        "beats_naive_baseline" if model_mae < baseline_mae else "below_naive_baseline"
    )
    return metrics


def summarize_symbol_metrics(symbol_results: dict[str, dict]) -> dict:
    completed = [
        result
        for result in symbol_results.values()
        if result.get("status") == "trained" and result.get("metrics")
    ]
    summary: dict[str, object] = {
        "trained_symbol_count": len(completed),
        "failed_symbol_count": sum(
            result.get("status") != "trained"
            for result in symbol_results.values()
        ),
    }
    if not completed:
        return summary

    metric_names = (
        "price_mae",
        "price_rmse",
        "price_smape_percent",
        "return_mae",
        "return_rmse",
        "directional_accuracy",
        "mae_improvement_over_baseline_percent",
    )
    macro_average = {}
    macro_median = {}
    for metric_name in metric_names:
        values = [
            result["metrics"].get(metric_name)
            for result in completed
            if result["metrics"].get(metric_name) is not None
        ]
        if values:
            macro_average[metric_name] = float(np.mean(values))
            macro_median[metric_name] = float(np.median(values))

    summary["macro_average"] = macro_average
    summary["macro_median"] = macro_median
    summary["symbols_beating_naive_baseline"] = sum(
        result["metrics"].get("quality_status") == "beats_naive_baseline"
        for result in completed
    )
    return summary

