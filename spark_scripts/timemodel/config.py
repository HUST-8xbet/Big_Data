from __future__ import annotations

from dataclasses import asdict, dataclass, field
import os
from pathlib import Path
from typing import Iterable


PACKAGE_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_DIR.parent.parent
ARTIFACT_ROOT = PACKAGE_DIR / "artifacts"
DEFAULT_NPZ_PATH = PROJECT_ROOT / "spark_scripts" / "ml" / "artifacts" / "training_data.npz"


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def parse_symbols(value: str | Iterable[str] | None) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, str):
        values = value.split(",")
    else:
        values = value
    return tuple(sorted({item.strip().upper() for item in values if item.strip()}))


def parse_arima_order(value: str | tuple[int, int, int]) -> tuple[int, int, int]:
    if isinstance(value, tuple):
        order = value
    else:
        parts = [part.strip() for part in value.split(",")]
        if len(parts) != 3:
            raise ValueError("ARIMA order must have the form p,d,q, for example 5,1,0")
        order = tuple(int(part) for part in parts)

    if len(order) != 3 or any(part < 0 for part in order):
        raise ValueError("ARIMA order values must be three non-negative integers")
    return order


@dataclass(frozen=True)
class DataSettings:
    source: str = "auto"
    minio_endpoint: str = "http://localhost:9000"
    minio_access_key: str = "admin"
    minio_secret_key: str = "password123"
    minio_bucket: str = "raw-data"
    minio_prefix: str = "binance/"
    train_days: float = 7.0
    max_minio_objects: int = 0
    npz_path: Path = DEFAULT_NPZ_PATH
    gap_fill_limit: int = 3
    symbols: tuple[str, ...] = ()

    def validate(self) -> None:
        if self.source not in {"auto", "minio", "npz"}:
            raise ValueError("source must be one of: auto, minio, npz")
        if self.train_days <= 0:
            raise ValueError("train_days must be positive")
        if self.max_minio_objects < 0:
            raise ValueError("max_minio_objects cannot be negative")
        if self.gap_fill_limit < 0:
            raise ValueError("gap_fill_limit cannot be negative")


@dataclass(frozen=True)
class TrainingSettings:
    validation_fraction: float = 0.20
    min_validation_points: int = 60
    random_state: int = 42

    arima_order: tuple[int, int, int] = (5, 1, 0)
    arima_min_train_points: int = 300
    arima_max_points: int = 0
    arima_enforce_stationarity: bool = True
    arima_enforce_invertibility: bool = True

    svr_lag_count: int = 60
    svr_min_train_samples: int = 300
    svr_c: float = 1.0
    svr_epsilon: float = 0.0
    svr_tolerance: float = 1e-4
    svr_max_iterations: int = 20_000

    def validate(self) -> None:
        if not 0 < self.validation_fraction < 0.5:
            raise ValueError("validation_fraction must be between 0 and 0.5")
        if self.min_validation_points < 1:
            raise ValueError("min_validation_points must be positive")
        parse_arima_order(self.arima_order)
        if self.arima_min_train_points < 20:
            raise ValueError("arima_min_train_points must be at least 20")
        if self.arima_max_points < 0:
            raise ValueError("arima_max_points cannot be negative")
        if self.svr_lag_count < 2:
            raise ValueError("svr_lag_count must be at least 2")
        if self.svr_min_train_samples < 20:
            raise ValueError("svr_min_train_samples must be at least 20")
        if self.svr_c <= 0:
            raise ValueError("svr_c must be positive")
        if self.svr_epsilon < 0:
            raise ValueError("svr_epsilon cannot be negative")
        if self.svr_tolerance <= 0:
            raise ValueError("svr_tolerance must be positive")
        if self.svr_max_iterations < 1:
            raise ValueError("svr_max_iterations must be positive")


@dataclass(frozen=True)
class UploadSettings:
    enabled: bool = False
    bucket: str = "ml-models"
    prefix: str = "timemodel"

    def validate(self) -> None:
        if self.enabled and not self.bucket.strip():
            raise ValueError("upload bucket cannot be empty")
        if self.enabled and not self.prefix.strip("/"):
            raise ValueError("upload prefix cannot be empty")


@dataclass(frozen=True)
class Settings:
    data: DataSettings = field(default_factory=DataSettings)
    training: TrainingSettings = field(default_factory=TrainingSettings)
    upload: UploadSettings = field(default_factory=UploadSettings)

    @classmethod
    def from_environment(cls) -> "Settings":
        access_key = os.getenv(
            "MINIO_ROOT_USER",
            os.getenv("MINIO_ACCESS_KEY", "admin"),
        )
        secret_key = os.getenv(
            "MINIO_ROOT_PASSWORD",
            os.getenv("MINIO_SECRET_KEY", "password123"),
        )

        settings = cls(
            data=DataSettings(
                source=os.getenv("TIMEMODEL_DATA_SOURCE", "auto").strip().lower(),
                minio_endpoint=os.getenv("MINIO_ENDPOINT", "http://localhost:9000"),
                minio_access_key=access_key,
                minio_secret_key=secret_key,
                minio_bucket=os.getenv(
                    "MINIO_TRAIN_BUCKET",
                    os.getenv("MINIO_RAW_BUCKET", "raw-data"),
                ),
                minio_prefix=os.getenv("MINIO_TRAIN_PREFIX", "binance/"),
                train_days=float(os.getenv("TRAIN_DAYS", "7")),
                max_minio_objects=int(os.getenv("MAX_MINIO_OBJECTS", "0")),
                npz_path=Path(os.getenv("TRAINING_DATA_FILE", str(DEFAULT_NPZ_PATH))),
                gap_fill_limit=int(os.getenv("TIMEMODEL_GAP_FILL_LIMIT", "3")),
                symbols=parse_symbols(os.getenv("TIMEMODEL_SYMBOLS")),
            ),
            training=TrainingSettings(
                validation_fraction=float(os.getenv("TIMEMODEL_VALIDATION_FRACTION", "0.20")),
                min_validation_points=int(os.getenv("TIMEMODEL_MIN_VALIDATION_POINTS", "60")),
                random_state=int(os.getenv("TIMEMODEL_RANDOM_STATE", "42")),
                arima_order=parse_arima_order(os.getenv("TIMEMODEL_ARIMA_ORDER", "5,1,0")),
                arima_min_train_points=int(os.getenv("TIMEMODEL_ARIMA_MIN_TRAIN_POINTS", "300")),
                arima_max_points=int(os.getenv("TIMEMODEL_ARIMA_MAX_POINTS", "0")),
                arima_enforce_stationarity=env_bool(
                    "TIMEMODEL_ARIMA_ENFORCE_STATIONARITY",
                    True,
                ),
                arima_enforce_invertibility=env_bool(
                    "TIMEMODEL_ARIMA_ENFORCE_INVERTIBILITY",
                    True,
                ),
                svr_lag_count=int(os.getenv("TIMEMODEL_SVR_LAG_COUNT", "60")),
                svr_min_train_samples=int(os.getenv("TIMEMODEL_SVR_MIN_TRAIN_SAMPLES", "300")),
                svr_c=float(os.getenv("TIMEMODEL_SVR_C", "1.0")),
                svr_epsilon=float(os.getenv("TIMEMODEL_SVR_EPSILON", "0.0")),
                svr_tolerance=float(os.getenv("TIMEMODEL_SVR_TOLERANCE", "0.0001")),
                svr_max_iterations=int(os.getenv("TIMEMODEL_SVR_MAX_ITERATIONS", "20000")),
            ),
            upload=UploadSettings(
                enabled=env_bool("TIMEMODEL_UPLOAD_TO_MINIO", False),
                bucket=os.getenv("TIMEMODEL_MODEL_BUCKET", "ml-models"),
                prefix=os.getenv("TIMEMODEL_MODEL_PREFIX", "timemodel"),
            ),
        )
        settings.validate()
        return settings

    def validate(self) -> None:
        self.data.validate()
        self.training.validate()
        self.upload.validate()

    def public_dict(self) -> dict:
        data = asdict(self)
        data["data"].pop("minio_access_key", None)
        data["data"].pop("minio_secret_key", None)
        data["data"]["npz_path"] = str(self.data.npz_path)
        data["artifact_root"] = str(ARTIFACT_ROOT)
        return data

