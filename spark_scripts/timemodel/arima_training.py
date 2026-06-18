from __future__ import annotations

from pathlib import Path
import time
import warnings

import numpy as np
from statsmodels.tsa.arima.model import ARIMA

from .config import TrainingSettings
from .dataset import TimeSegment
from .metrics import regression_metrics
from .storage import relative_artifact_path, sha256_file


def _select_arima_segment(segments: list[TimeSegment]) -> TimeSegment:
    if not segments:
        raise ValueError("no time-series segments were supplied")
    # Longest segment first; if lengths tie, prefer the most recent segment.
    return max(
        segments,
        key=lambda segment: (
            len(segment.prices),
            segment.end_ms if segment.end_ms is not None else -1,
        ),
    )


def _build_arima(
    log_prices: np.ndarray,
    settings: TrainingSettings,
) -> ARIMA:
    return ARIMA(
        log_prices,
        order=settings.arima_order,
        enforce_stationarity=settings.arima_enforce_stationarity,
        enforce_invertibility=settings.arima_enforce_invertibility,
    )


def train_arima_symbol(
    symbol: str,
    segments: list[TimeSegment],
    settings: TrainingSettings,
    run_directory: Path,
) -> dict:
    started = time.perf_counter()
    segment = _select_arima_segment(segments)
    prices = np.asarray(segment.prices, dtype=np.float64)
    timestamps = np.asarray(segment.timestamps_ms, dtype=np.int64)

    original_point_count = len(prices)
    if settings.arima_max_points > 0 and len(prices) > settings.arima_max_points:
        prices = prices[-settings.arima_max_points :]
        timestamps = timestamps[-settings.arima_max_points :]

    p, d, q = settings.arima_order
    minimum_train_points = max(
        settings.arima_min_train_points,
        p + d + q + 20,
    )
    validation_points = max(
        settings.min_validation_points,
        int(len(prices) * settings.validation_fraction),
    )
    if len(prices) - validation_points < minimum_train_points:
        raise ValueError(
            f"{symbol} has {len(prices)} usable points; requires at least "
            f"{minimum_train_points + validation_points}"
        )

    split_index = len(prices) - validation_points
    train_prices = prices[:split_index]
    validation_prices = prices[split_index:]
    log_train_prices = np.log(train_prices)
    log_all_prices = np.log(prices)

    captured_warnings: list[str] = []
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always")
        validation_fit = _build_arima(log_train_prices, settings).fit()

        # Filter the full series with parameters estimated only on the training
        # portion. Non-dynamic predictions are one-step-ahead predictions that
        # may use earlier observed validation values but never future values.
        filtered_full = _build_arima(log_all_prices, settings).filter(
            validation_fit.params
        )
        predicted_log_prices = np.asarray(
            filtered_full.get_prediction(
                start=split_index,
                end=len(prices) - 1,
                dynamic=False,
            ).predicted_mean,
            dtype=np.float64,
        )
        predicted_prices = np.exp(predicted_log_prices)
        current_prices = prices[split_index - 1 : -1]
        metrics = regression_metrics(
            validation_prices,
            predicted_prices,
            current_prices,
        )

        # The final saved model is refit on every selected point after the
        # holdout evaluation has been calculated.
        final_fit = _build_arima(log_all_prices, settings).fit()
        captured_warnings.extend(str(item.message) for item in warning_records)

    model_path = run_directory / "arima" / "models" / f"{symbol}.pkl"
    final_fit.save(model_path, remove_data=False)

    convergence_details = getattr(final_fit, "mle_retvals", {}) or {}
    converged = convergence_details.get("converged")
    result = {
        "status": "trained",
        "symbol": symbol,
        "artifact": {
            "path": relative_artifact_path(model_path, run_directory),
            "sha256": sha256_file(model_path),
            "size_bytes": model_path.stat().st_size,
            "format": "statsmodels.ARIMAResults pickle",
        },
        "model": {
            "type": "ARIMA",
            "order": list(settings.arima_order),
            "target_transform": "natural_log_price",
            "enforce_stationarity": settings.arima_enforce_stationarity,
            "enforce_invertibility": settings.arima_enforce_invertibility,
            "converged": bool(converged) if converged is not None else None,
            "aic": float(final_fit.aic),
            "bic": float(final_fit.bic),
            "hqic": float(final_fit.hqic),
        },
        "data": {
            "selected_segment_policy": "longest_then_most_recent",
            "available_segment_count": len(segments),
            "selected_segment_original_points": original_point_count,
            "points_used": len(prices),
            "points_truncated_by_max_limit": original_point_count - len(prices),
            "train_points_for_evaluation": len(train_prices),
            "validation_points": len(validation_prices),
            "final_fit_points": len(prices),
            "start_timestamp_ms": int(timestamps[0]),
            "end_timestamp_ms": int(timestamps[-1]),
            "synthetic_timestamps": segment.synthetic_timestamps,
            "last_observed_price": float(prices[-1]),
        },
        "metrics": metrics,
        "warnings": sorted(set(captured_warnings)),
        "training_seconds": time.perf_counter() - started,
    }
    return result

