from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .dataset import TimeSegment


TECHNICAL_FEATURE_NAMES = (
    "ma5_ratio",
    "ma20_ratio",
    "volatility20",
    "rsi14",
)


@dataclass(frozen=True)
class SVRSamples:
    X: np.ndarray
    y_return: np.ndarray
    current_prices: np.ndarray
    target_prices: np.ndarray
    target_timestamps_ms: np.ndarray

    @property
    def sample_count(self) -> int:
        return len(self.y_return)


def rolling_mean(values: np.ndarray, window: int) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    result = np.full(len(values), np.nan, dtype=np.float64)
    if len(values) < window:
        return result
    cumsum = np.cumsum(np.insert(values, 0, 0.0))
    result[window - 1 :] = (cumsum[window:] - cumsum[:-window]) / window
    return result


def rolling_std(values: np.ndarray, window: int) -> np.ndarray:
    values = np.asarray(values, dtype=np.float64)
    result = np.full(len(values), np.nan, dtype=np.float64)
    if len(values) < window:
        return result
    cumsum = np.cumsum(np.insert(values, 0, 0.0))
    cumsum_sq = np.cumsum(np.insert(values**2, 0, 0.0))
    mean = (cumsum[window:] - cumsum[:-window]) / window
    mean_sq = (cumsum_sq[window:] - cumsum_sq[:-window]) / window
    variance = np.maximum(mean_sq - mean**2, 0.0)
    result[window - 1 :] = np.sqrt(variance)
    return result


def compute_rsi(prices: np.ndarray, period: int = 14) -> np.ndarray:
    prices = np.asarray(prices, dtype=np.float64)
    if not len(prices):
        return np.asarray([], dtype=np.float64)

    deltas = np.diff(prices, prepend=prices[0])
    gains = np.where(deltas > 0, deltas, 0.0)
    losses = np.where(deltas < 0, -deltas, 0.0)
    average_gain = rolling_mean(gains, period)
    average_loss = rolling_mean(losses, period)

    with np.errstate(divide="ignore", invalid="ignore"):
        relative_strength = average_gain / average_loss
        rsi = 100.0 - 100.0 / (1.0 + relative_strength)

    both_zero = (average_gain == 0) & (average_loss == 0)
    rsi = np.where(average_loss == 0, 100.0, rsi)
    rsi = np.where(both_zero, 50.0, rsi)
    return np.nan_to_num(rsi, nan=50.0) / 100.0


def compute_returns(prices: np.ndarray) -> np.ndarray:
    prices = np.asarray(prices, dtype=np.float64)
    returns = np.zeros(len(prices), dtype=np.float64)
    if len(prices) > 1:
        returns[1:] = np.diff(prices) / prices[:-1]
    return returns


def feature_names(lag_count: int) -> tuple[str, ...]:
    lag_names = tuple(
        f"return_lag_{lag}"
        for lag in range(lag_count, 0, -1)
    )
    return lag_names + TECHNICAL_FEATURE_NAMES


def build_segment_svr_samples(
    segment: TimeSegment,
    lag_count: int = 60,
) -> SVRSamples:
    prices = np.asarray(segment.prices, dtype=np.float64)
    minimum_points = lag_count + 2
    if len(prices) < minimum_points:
        return SVRSamples(
            X=np.empty((0, lag_count + len(TECHNICAL_FEATURE_NAMES)), dtype=np.float32),
            y_return=np.empty(0, dtype=np.float64),
            current_prices=np.empty(0, dtype=np.float64),
            target_prices=np.empty(0, dtype=np.float64),
            target_timestamps_ms=np.empty(0, dtype=np.int64),
        )

    returns = compute_returns(prices)
    ma5 = rolling_mean(prices, 5)
    ma20 = rolling_mean(prices, 20)
    volatility20 = rolling_std(prices, 20) / prices
    rsi14 = compute_rsi(prices, 14)

    with np.errstate(divide="ignore", invalid="ignore"):
        ma5_ratio = prices / ma5 - 1.0
        ma20_ratio = prices / ma20 - 1.0

    # returns[1:] excludes the synthetic zero return at the first price.
    lag_windows = np.lib.stride_tricks.sliding_window_view(
        returns[1:],
        lag_count,
    )
    current_indices = np.arange(lag_count, len(prices) - 1)
    lag_windows = lag_windows[: len(current_indices)]

    technical_features = np.column_stack(
        (
            ma5_ratio[current_indices],
            ma20_ratio[current_indices],
            volatility20[current_indices],
            rsi14[current_indices],
        )
    )
    X = np.column_stack((lag_windows, technical_features))
    y_return = returns[current_indices + 1]
    current_prices = prices[current_indices]
    target_prices = prices[current_indices + 1]
    target_timestamps = segment.timestamps_ms[current_indices + 1]

    valid_rows = (
        np.all(np.isfinite(X), axis=1)
        & np.isfinite(y_return)
        & np.isfinite(current_prices)
        & np.isfinite(target_prices)
        & (current_prices > 0)
        & (target_prices > 0)
    )
    return SVRSamples(
        X=np.asarray(X[valid_rows], dtype=np.float32),
        y_return=np.asarray(y_return[valid_rows], dtype=np.float64),
        current_prices=np.asarray(current_prices[valid_rows], dtype=np.float64),
        target_prices=np.asarray(target_prices[valid_rows], dtype=np.float64),
        target_timestamps_ms=np.asarray(target_timestamps[valid_rows], dtype=np.int64),
    )


def combine_symbol_svr_samples(
    segments: list[TimeSegment],
    lag_count: int = 60,
) -> SVRSamples:
    parts = [
        build_segment_svr_samples(segment, lag_count)
        for segment in segments
    ]
    parts = [part for part in parts if part.sample_count]
    feature_count = lag_count + len(TECHNICAL_FEATURE_NAMES)

    if not parts:
        return SVRSamples(
            X=np.empty((0, feature_count), dtype=np.float32),
            y_return=np.empty(0, dtype=np.float64),
            current_prices=np.empty(0, dtype=np.float64),
            target_prices=np.empty(0, dtype=np.float64),
            target_timestamps_ms=np.empty(0, dtype=np.int64),
        )

    X = np.concatenate([part.X for part in parts], axis=0)
    y_return = np.concatenate([part.y_return for part in parts])
    current_prices = np.concatenate([part.current_prices for part in parts])
    target_prices = np.concatenate([part.target_prices for part in parts])
    target_timestamps = np.concatenate(
        [part.target_timestamps_ms for part in parts]
    )
    order = np.argsort(target_timestamps, kind="stable")

    return SVRSamples(
        X=X[order],
        y_return=y_return[order],
        current_prices=current_prices[order],
        target_prices=target_prices[order],
        target_timestamps_ms=target_timestamps[order],
    )


def build_latest_svr_feature(
    prices: np.ndarray | list[float],
    lag_count: int = 60,
) -> np.ndarray:
    """Build one feature row for future offline use of a saved SVR model."""
    prices_array = np.asarray(prices, dtype=np.float64)

    # Append one placeholder price so the standard sample builder emits a row
    # whose features end at the actual final price. The placeholder is removed
    # from the feature calculation target and is never supplied to the model.
    if len(prices_array) < lag_count + 1:
        raise ValueError(
            f"At least {lag_count + 1} prices are required to build an SVR feature"
        )
    extended_prices = np.append(prices_array, prices_array[-1])
    extended_timestamps = np.arange(len(extended_prices), dtype=np.int64) * 60_000
    extended_segment = TimeSegment(
        symbol="INFERENCE",
        timestamps_ms=extended_timestamps,
        prices=extended_prices,
        synthetic_timestamps=True,
    )
    samples = build_segment_svr_samples(extended_segment, lag_count)
    if not samples.sample_count:
        raise ValueError("Unable to build a finite SVR feature from the supplied prices")
    return samples.X[-1:].copy()
