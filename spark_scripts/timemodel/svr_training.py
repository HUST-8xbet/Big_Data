from __future__ import annotations

from pathlib import Path
import time
import warnings

import joblib
import numpy as np
from sklearn.compose import TransformedTargetRegressor
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import LinearSVR

from .config import TrainingSettings
from .dataset import TimeSegment
from .features import combine_symbol_svr_samples, feature_names
from .metrics import regression_metrics
from .storage import relative_artifact_path, sha256_file


def _build_svr(settings: TrainingSettings) -> TransformedTargetRegressor:
    feature_pipeline = Pipeline(
        steps=[
            ("feature_scaler", StandardScaler()),
            (
                "linear_svr",
                LinearSVR(
                    epsilon=settings.svr_epsilon,
                    C=settings.svr_c,
                    loss="squared_epsilon_insensitive",
                    dual="auto",
                    tol=settings.svr_tolerance,
                    max_iter=settings.svr_max_iterations,
                    random_state=settings.random_state,
                ),
            ),
        ]
    )
    return TransformedTargetRegressor(
        regressor=feature_pipeline,
        transformer=StandardScaler(),
    )


def train_svr_symbol(
    symbol: str,
    segments: list[TimeSegment],
    settings: TrainingSettings,
    run_directory: Path,
) -> dict:
    started = time.perf_counter()
    samples = combine_symbol_svr_samples(segments, settings.svr_lag_count)
    minimum_total_samples = (
        settings.svr_min_train_samples + settings.min_validation_points
    )
    if samples.sample_count < minimum_total_samples:
        raise ValueError(
            f"{symbol} has {samples.sample_count} SVR samples; requires at least "
            f"{minimum_total_samples}"
        )

    validation_samples = max(
        settings.min_validation_points,
        int(samples.sample_count * settings.validation_fraction),
    )
    split_index = samples.sample_count - validation_samples
    if split_index < settings.svr_min_train_samples:
        raise ValueError(
            f"{symbol} has only {split_index} training samples after time split"
        )

    X_train = samples.X[:split_index]
    y_train = samples.y_return[:split_index]
    X_validation = samples.X[split_index:]
    validation_current_prices = samples.current_prices[split_index:]
    validation_target_prices = samples.target_prices[split_index:]

    captured_warnings: list[str] = []
    with warnings.catch_warnings(record=True) as warning_records:
        warnings.simplefilter("always")
        validation_model = _build_svr(settings)
        validation_model.fit(X_train, y_train)
        predicted_returns = np.asarray(
            validation_model.predict(X_validation),
            dtype=np.float64,
        )
        predicted_prices = validation_current_prices * (1.0 + predicted_returns)
        metrics = regression_metrics(
            validation_target_prices,
            predicted_prices,
            validation_current_prices,
        )

        final_model = _build_svr(settings)
        final_model.fit(samples.X, samples.y_return)
        captured_warnings.extend(str(item.message) for item in warning_records)

    model_path = run_directory / "svr" / "models" / f"{symbol}.joblib"
    joblib.dump(final_model, model_path, compress=3)

    fitted_linear_svr = final_model.regressor_.named_steps["linear_svr"]
    n_iter = getattr(fitted_linear_svr, "n_iter_", None)
    result = {
        "status": "trained",
        "symbol": symbol,
        "artifact": {
            "path": relative_artifact_path(model_path, run_directory),
            "sha256": sha256_file(model_path),
            "size_bytes": model_path.stat().st_size,
            "format": "joblib sklearn TransformedTargetRegressor",
        },
        "model": {
            "type": "LinearSVR",
            "target": "next_minute_return",
            "feature_scaler": "StandardScaler",
            "target_scaler": "StandardScaler",
            "loss": "squared_epsilon_insensitive",
            "dual": "auto",
            "C": settings.svr_c,
            "epsilon": settings.svr_epsilon,
            "tolerance": settings.svr_tolerance,
            "max_iterations": settings.svr_max_iterations,
            "iterations_used": int(n_iter) if n_iter is not None else None,
        },
        "features": {
            "lag_count": settings.svr_lag_count,
            "feature_count": samples.X.shape[1],
            "names": list(feature_names(settings.svr_lag_count)),
            "ordering": "oldest_return_lag_to_newest_return_lag_then_technical",
        },
        "data": {
            "available_segment_count": len(segments),
            "sample_count": samples.sample_count,
            "train_samples_for_evaluation": len(X_train),
            "validation_samples": len(X_validation),
            "final_fit_samples": samples.sample_count,
            "first_target_timestamp_ms": int(samples.target_timestamps_ms[0]),
            "last_target_timestamp_ms": int(samples.target_timestamps_ms[-1]),
            "synthetic_timestamps": all(
                segment.synthetic_timestamps for segment in segments
            ),
            "last_observed_price": float(
                max(segments, key=lambda segment: segment.end_ms or -1).prices[-1]
            ),
        },
        "metrics": metrics,
        "warnings": sorted(set(captured_warnings)),
        "training_seconds": time.perf_counter() - started,
    }
    return result

