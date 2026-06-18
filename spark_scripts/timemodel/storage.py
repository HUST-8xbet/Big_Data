from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import re
import uuid

import boto3
from botocore.config import Config
import numpy as np

from .config import ARTIFACT_ROOT, DataSettings, UploadSettings


RUN_ID_PATTERN = re.compile(r"^[A-Za-z0-9._-]+$")


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid.uuid4().hex[:8]}"


def validate_run_id(run_id: str) -> str:
    run_id = run_id.strip()
    if not run_id or not RUN_ID_PATTERN.fullmatch(run_id):
        raise ValueError(
            "run_id may contain only letters, digits, dot, underscore and hyphen"
        )
    return run_id


def create_run_directory(run_id: str | None = None) -> tuple[str, Path]:
    ARTIFACT_ROOT.mkdir(parents=True, exist_ok=True)
    resolved_run_id = validate_run_id(run_id) if run_id else create_run_id()
    run_directory = ARTIFACT_ROOT / resolved_run_id
    if run_directory.exists():
        raise FileExistsError(f"artifact run already exists: {run_directory}")
    (run_directory / "arima" / "models").mkdir(parents=True)
    (run_directory / "svr" / "models").mkdir(parents=True)
    return resolved_run_id, run_directory


def _json_default(value):
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.generic):
        return value.item()
    if isinstance(value, np.ndarray):
        return value.tolist()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _sanitize_json(value):
    if isinstance(value, dict):
        return {str(key): _sanitize_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_sanitize_json(item) for item in value]
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, np.ndarray):
        return [_sanitize_json(item) for item in value.tolist()]
    if isinstance(value, np.generic):
        return _sanitize_json(value.item())
    if isinstance(value, float) and not np.isfinite(value):
        return None
    return value


def write_json_atomic(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(path.suffix + ".tmp")
    with temporary_path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(
            _sanitize_json(payload),
            handle,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            default=_json_default,
            allow_nan=False,
        )
        handle.write("\n")
    os.replace(temporary_path, path)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def library_versions() -> dict[str, str | None]:
    packages = (
        "numpy",
        "scipy",
        "statsmodels",
        "scikit-learn",
        "joblib",
        "boto3",
        "botocore",
    )
    versions: dict[str, str | None] = {}
    for package in packages:
        try:
            versions[package] = importlib.metadata.version(package)
        except importlib.metadata.PackageNotFoundError:
            versions[package] = None
    return versions


def relative_artifact_path(path: Path, run_directory: Path) -> str:
    return path.resolve().relative_to(run_directory.resolve()).as_posix()


def _create_s3_client(data_settings: DataSettings):
    return boto3.client(
        "s3",
        endpoint_url=data_settings.minio_endpoint,
        aws_access_key_id=data_settings.minio_access_key,
        aws_secret_access_key=data_settings.minio_secret_key,
        config=Config(
            signature_version="s3v4",
            connect_timeout=10,
            read_timeout=120,
            retries={"max_attempts": 5, "mode": "standard"},
        ),
    )


def upload_run_directory(
    run_directory: Path,
    run_id: str,
    data_settings: DataSettings,
    upload_settings: UploadSettings,
) -> dict:
    if not upload_settings.enabled:
        return {"status": "disabled"}

    client = _create_s3_client(data_settings)
    prefix = upload_settings.prefix.strip("/")
    uploaded_files = 0

    for path in sorted(run_directory.rglob("*")):
        if not path.is_file() or path.name.endswith(".tmp"):
            continue
        relative_path = path.relative_to(run_directory).as_posix()
        object_key = f"{prefix}/{run_id}/{relative_path}"
        client.upload_file(str(path), upload_settings.bucket, object_key)
        uploaded_files += 1

    return {
        "status": "uploaded",
        "bucket": upload_settings.bucket,
        "prefix": f"{prefix}/{run_id}/",
        "uploaded_file_count": uploaded_files,
        "endpoint": data_settings.minio_endpoint,
    }
