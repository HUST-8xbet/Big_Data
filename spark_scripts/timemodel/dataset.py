from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import math
from pathlib import Path
from typing import Iterator

import boto3
from botocore.config import Config
import numpy as np

from .config import DataSettings


MINUTE_MS = 60_000


@dataclass(frozen=True)
class TimeSegment:
    symbol: str
    timestamps_ms: np.ndarray
    prices: np.ndarray
    synthetic_timestamps: bool = False

    def __post_init__(self) -> None:
        if len(self.timestamps_ms) != len(self.prices):
            raise ValueError("timestamps and prices must have the same length")
        if len(self.prices) and (
            not np.all(np.isfinite(self.prices)) or np.any(self.prices <= 0)
        ):
            raise ValueError("segment prices must be finite and positive")

    @property
    def start_ms(self) -> int | None:
        return int(self.timestamps_ms[0]) if len(self.timestamps_ms) else None

    @property
    def end_ms(self) -> int | None:
        return int(self.timestamps_ms[-1]) if len(self.timestamps_ms) else None


@dataclass(frozen=True)
class DatasetBundle:
    segments_by_symbol: dict[str, list[TimeSegment]]
    metadata: dict

    @property
    def symbols(self) -> tuple[str, ...]:
        return tuple(sorted(self.segments_by_symbol))

    @property
    def point_count(self) -> int:
        return sum(
            len(segment.prices)
            for segments in self.segments_by_symbol.values()
            for segment in segments
        )


def _create_s3_client(settings: DataSettings):
    return boto3.client(
        "s3",
        endpoint_url=settings.minio_endpoint,
        aws_access_key_id=settings.minio_access_key,
        aws_secret_access_key=settings.minio_secret_key,
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=60,
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )


def _iter_object_keys(client, settings: DataSettings) -> Iterator[str]:
    paginator = client.get_paginator("list_objects_v2")

    if settings.max_minio_objects > 0:
        newest_keys: deque[str] = deque(maxlen=settings.max_minio_objects)
        for page in paginator.paginate(
            Bucket=settings.minio_bucket,
            Prefix=settings.minio_prefix,
        ):
            for item in page.get("Contents", []):
                key = item["Key"]
                if key.endswith(".json"):
                    newest_keys.append(key)
        yield from newest_keys
        return

    for page in paginator.paginate(
        Bucket=settings.minio_bucket,
        Prefix=settings.minio_prefix,
    ):
        for item in page.get("Contents", []):
            key = item["Key"]
            if key.endswith(".json"):
                yield key


def _load_json_object(client, bucket: str, key: str):
    response = client.get_object(Bucket=bucket, Key=key)
    try:
        return json.loads(response["Body"].read())
    finally:
        response["Body"].close()


def build_segments_from_minute_values(
    symbol: str,
    minute_values: dict[int, tuple[float, int] | list[float | int]],
    gap_fill_limit: int,
) -> tuple[list[TimeSegment], dict]:
    observations = [
        (int(timestamp_ms), float(total) / int(count))
        for timestamp_ms, (total, count) in sorted(minute_values.items())
        if int(count) > 0 and math.isfinite(float(total))
    ]

    if not observations:
        return [], {"filled_points": 0, "long_gap_splits": 0}

    segments: list[TimeSegment] = []
    current_timestamps = [observations[0][0]]
    current_prices = [observations[0][1]]
    filled_points = 0
    long_gap_splits = 0

    previous_timestamp, previous_price = observations[0]
    for timestamp_ms, price in observations[1:]:
        delta_ms = timestamp_ms - previous_timestamp
        if delta_ms <= 0:
            continue

        missing_minutes = max(0, delta_ms // MINUTE_MS - 1)
        is_regular_minute_grid = delta_ms % MINUTE_MS == 0

        if is_regular_minute_grid and missing_minutes <= gap_fill_limit:
            for step in range(1, missing_minutes + 1):
                current_timestamps.append(previous_timestamp + step * MINUTE_MS)
                current_prices.append(previous_price)
                filled_points += 1
            current_timestamps.append(timestamp_ms)
            current_prices.append(price)
        else:
            segments.append(
                TimeSegment(
                    symbol=symbol,
                    timestamps_ms=np.asarray(current_timestamps, dtype=np.int64),
                    prices=np.asarray(current_prices, dtype=np.float64),
                )
            )
            current_timestamps = [timestamp_ms]
            current_prices = [price]
            long_gap_splits += 1

        previous_timestamp = timestamp_ms
        previous_price = price

    segments.append(
        TimeSegment(
            symbol=symbol,
            timestamps_ms=np.asarray(current_timestamps, dtype=np.int64),
            prices=np.asarray(current_prices, dtype=np.float64),
        )
    )
    return segments, {
        "filled_points": filled_points,
        "long_gap_splits": long_gap_splits,
    }


def load_from_minio(settings: DataSettings) -> DatasetBundle:
    cutoff_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=settings.train_days)).timestamp()
        * 1000
    )
    selected_symbols = set(settings.symbols)
    minute_buckets: dict[str, dict[int, list[float | int]]] = defaultdict(
        lambda: defaultdict(lambda: [0.0, 0])
    )
    client = _create_s3_client(settings)

    object_count = 0
    invalid_object_count = 0
    record_count = 0
    kept_record_count = 0
    invalid_record_count = 0

    for key in _iter_object_keys(client, settings):
        object_count += 1
        try:
            records = _load_json_object(client, settings.minio_bucket, key)
        except Exception as exc:
            invalid_object_count += 1
            print(f"[data] Skipping MinIO object {key}: {exc}")
            continue

        if not isinstance(records, list):
            invalid_object_count += 1
            print(f"[data] Skipping MinIO object {key}: JSON body is not a list")
            continue

        for record in records:
            record_count += 1
            try:
                symbol = str(record["symbol"]).strip().upper()
                price = float(record["price"])
                timestamp_ms = int(record["timestamp"])
            except (KeyError, TypeError, ValueError):
                invalid_record_count += 1
                continue

            if (
                not symbol
                or (selected_symbols and symbol not in selected_symbols)
                or timestamp_ms < cutoff_ms
                or not math.isfinite(price)
                or price <= 0
            ):
                continue

            minute_ms = timestamp_ms - timestamp_ms % MINUTE_MS
            bucket = minute_buckets[symbol][minute_ms]
            bucket[0] = float(bucket[0]) + price
            bucket[1] = int(bucket[1]) + 1
            kept_record_count += 1

    segments_by_symbol: dict[str, list[TimeSegment]] = {}
    total_filled_points = 0
    total_long_gap_splits = 0
    raw_minute_count = 0

    for symbol, minute_values in sorted(minute_buckets.items()):
        raw_minute_count += len(minute_values)
        segments, gap_stats = build_segments_from_minute_values(
            symbol,
            minute_values,
            settings.gap_fill_limit,
        )
        if segments:
            segments_by_symbol[symbol] = segments
        total_filled_points += gap_stats["filled_points"]
        total_long_gap_splits += gap_stats["long_gap_splits"]

    metadata = {
        "source": "minio",
        "endpoint": settings.minio_endpoint,
        "bucket": settings.minio_bucket,
        "prefix": settings.minio_prefix,
        "train_days": settings.train_days,
        "cutoff_utc": datetime.fromtimestamp(
            cutoff_ms / 1000,
            tz=timezone.utc,
        ).isoformat(),
        "max_minio_objects": settings.max_minio_objects,
        "objects_read": object_count,
        "invalid_objects": invalid_object_count,
        "records_read": record_count,
        "records_kept": kept_record_count,
        "invalid_records": invalid_record_count,
        "raw_minute_count": raw_minute_count,
        "filled_minute_count": total_filled_points,
        "long_gap_splits": total_long_gap_splits,
        "gap_fill_limit": settings.gap_fill_limit,
        "symbol_count": len(segments_by_symbol),
        "segment_count": sum(len(value) for value in segments_by_symbol.values()),
        "synthetic_timestamps": False,
    }
    return DatasetBundle(segments_by_symbol=segments_by_symbol, metadata=metadata)


def _valid_price_runs(prices: np.ndarray) -> Iterator[tuple[int, int]]:
    valid = np.isfinite(prices) & (prices > 0)
    start: int | None = None
    for index, is_valid in enumerate(valid):
        if is_valid and start is None:
            start = index
        elif not is_valid and start is not None:
            yield start, index
            start = None
    if start is not None:
        yield start, len(prices)


def load_from_npz(settings: DataSettings) -> DatasetBundle:
    path = Path(settings.npz_path)
    if not path.exists():
        raise FileNotFoundError(f"NPZ fallback file does not exist: {path}")

    selected_symbols = set(settings.symbols)
    segments_by_symbol: dict[str, list[TimeSegment]] = {}
    invalid_point_count = 0

    with np.load(path, allow_pickle=False) as archive:
        for raw_symbol in archive.files:
            symbol = raw_symbol.strip().upper()
            if selected_symbols and symbol not in selected_symbols:
                continue

            prices = np.asarray(archive[raw_symbol], dtype=np.float64).reshape(-1)
            invalid_point_count += int(np.sum(~np.isfinite(prices) | (prices <= 0)))
            symbol_segments: list[TimeSegment] = []

            for start, end in _valid_price_runs(prices):
                run_prices = prices[start:end]
                if not len(run_prices):
                    continue
                timestamps = np.arange(start, end, dtype=np.int64) * MINUTE_MS
                symbol_segments.append(
                    TimeSegment(
                        symbol=symbol,
                        timestamps_ms=timestamps,
                        prices=run_prices.copy(),
                        synthetic_timestamps=True,
                    )
                )

            if symbol_segments:
                segments_by_symbol[symbol] = symbol_segments

    metadata = {
        "source": "npz",
        "path": str(path.resolve()),
        "symbol_count": len(segments_by_symbol),
        "segment_count": sum(len(value) for value in segments_by_symbol.values()),
        "invalid_points": invalid_point_count,
        "gap_fill_limit": None,
        "synthetic_timestamps": True,
        "timestamp_assumption": "Each NPZ array element is treated as one consecutive minute.",
    }
    return DatasetBundle(segments_by_symbol=segments_by_symbol, metadata=metadata)


def load_dataset(settings: DataSettings) -> DatasetBundle:
    settings.validate()

    if settings.source == "minio":
        bundle = load_from_minio(settings)
        if not bundle.segments_by_symbol:
            raise RuntimeError("MinIO returned no usable time-series data")
        return bundle

    if settings.source == "npz":
        bundle = load_from_npz(settings)
        if not bundle.segments_by_symbol:
            raise RuntimeError("NPZ returned no usable time-series data")
        return bundle

    try:
        bundle = load_from_minio(settings)
        if bundle.segments_by_symbol:
            return bundle
        print("[data] MinIO returned no usable data; falling back to NPZ")
    except Exception as exc:
        print(f"[data] MinIO load failed; falling back to NPZ: {exc}")

    bundle = load_from_npz(settings)
    if not bundle.segments_by_symbol:
        raise RuntimeError("Neither MinIO nor NPZ returned usable time-series data")
    bundle.metadata["fallback_reason"] = "MinIO was unavailable or returned no usable data."
    return bundle

