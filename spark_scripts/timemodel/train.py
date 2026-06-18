from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
import sys
import time
import traceback


if __package__ in {None, ""}:
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))
    from spark_scripts.timemodel.arima_training import train_arima_symbol
    from spark_scripts.timemodel.config import (
        Settings,
        parse_arima_order,
        parse_symbols,
    )
    from spark_scripts.timemodel.dataset import load_dataset
    from spark_scripts.timemodel.metrics import summarize_symbol_metrics
    from spark_scripts.timemodel.storage import (
        create_run_directory,
        library_versions,
        upload_run_directory,
        utc_now_iso,
        write_json_atomic,
    )
    from spark_scripts.timemodel.svr_training import train_svr_symbol
else:
    from .arima_training import train_arima_symbol
    from .config import Settings, parse_arima_order, parse_symbols
    from .dataset import load_dataset
    from .metrics import summarize_symbol_metrics
    from .storage import (
        create_run_directory,
        library_versions,
        upload_run_directory,
        utc_now_iso,
        write_json_atomic,
    )
    from .svr_training import train_svr_symbol


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Train isolated per-symbol ARIMA and LinearSVR models from MinIO "
            "one-minute data, with NPZ fallback."
        )
    )
    parser.add_argument(
        "--models",
        choices=("all", "arima", "svr"),
        default="all",
        help="Model family to train (default: all).",
    )
    parser.add_argument(
        "--source",
        choices=("auto", "minio", "npz"),
        help="Override TIMEMODEL_DATA_SOURCE.",
    )
    parser.add_argument(
        "--symbols",
        help="Comma-separated symbol allowlist, for example BTCUSDT,ETHUSDT.",
    )
    parser.add_argument("--train-days", type=float)
    parser.add_argument("--max-minio-objects", type=int)
    parser.add_argument("--gap-fill-limit", type=int)
    parser.add_argument("--npz-path", type=Path)
    parser.add_argument("--validation-fraction", type=float)
    parser.add_argument(
        "--arima-order",
        help="ARIMA p,d,q order (default: 5,1,0).",
    )
    parser.add_argument(
        "--arima-max-points",
        type=int,
        help="Use only the latest N points for ARIMA; 0 means no limit.",
    )
    parser.add_argument("--svr-c", type=float)
    parser.add_argument("--svr-epsilon", type=float)
    parser.add_argument("--svr-max-iterations", type=int)
    parser.add_argument(
        "--upload-minio",
        action="store_true",
        help="Upload the completed run to the isolated MinIO timemodel prefix.",
    )
    parser.add_argument(
        "--run-id",
        help="Optional artifact run id. Existing run directories are never overwritten.",
    )
    return parser


def apply_cli_overrides(settings: Settings, args: argparse.Namespace) -> Settings:
    data = settings.data
    training = settings.training
    upload = settings.upload

    if args.source is not None:
        data = replace(data, source=args.source)
    if args.symbols is not None:
        data = replace(data, symbols=parse_symbols(args.symbols))
    if args.train_days is not None:
        data = replace(data, train_days=args.train_days)
    if args.max_minio_objects is not None:
        data = replace(data, max_minio_objects=args.max_minio_objects)
    if args.gap_fill_limit is not None:
        data = replace(data, gap_fill_limit=args.gap_fill_limit)
    if args.npz_path is not None:
        data = replace(data, npz_path=args.npz_path)

    if args.validation_fraction is not None:
        training = replace(
            training,
            validation_fraction=args.validation_fraction,
        )
    if args.arima_order is not None:
        training = replace(
            training,
            arima_order=parse_arima_order(args.arima_order),
        )
    if args.arima_max_points is not None:
        training = replace(
            training,
            arima_max_points=args.arima_max_points,
        )
    if args.svr_c is not None:
        training = replace(training, svr_c=args.svr_c)
    if args.svr_epsilon is not None:
        training = replace(training, svr_epsilon=args.svr_epsilon)
    if args.svr_max_iterations is not None:
        training = replace(
            training,
            svr_max_iterations=args.svr_max_iterations,
        )
    if args.upload_minio:
        upload = replace(upload, enabled=True)

    overridden = Settings(data=data, training=training, upload=upload)
    overridden.validate()
    return overridden


def dataset_inventory(bundle) -> dict:
    inventory = {}
    for symbol, segments in sorted(bundle.segments_by_symbol.items()):
        point_count = sum(len(segment.prices) for segment in segments)
        starts = [
            segment.start_ms
            for segment in segments
            if segment.start_ms is not None
        ]
        ends = [
            segment.end_ms
            for segment in segments
            if segment.end_ms is not None
        ]
        inventory[symbol] = {
            "segment_count": len(segments),
            "point_count": point_count,
            "longest_segment_points": max(len(segment.prices) for segment in segments),
            "start_timestamp_ms": min(starts) if starts else None,
            "end_timestamp_ms": max(ends) if ends else None,
            "synthetic_timestamps": all(
                segment.synthetic_timestamps for segment in segments
            ),
        }
    return inventory


def failure_result(symbol: str, exc: Exception) -> dict:
    return {
        "status": "failed",
        "symbol": symbol,
        "error_type": type(exc).__name__,
        "error": str(exc),
        "traceback": "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        ),
    }


def train_model_family(
    model_name: str,
    bundle,
    settings: Settings,
    run_directory: Path,
    manifest: dict,
) -> dict[str, dict]:
    trainer = train_arima_symbol if model_name == "arima" else train_svr_symbol
    symbol_results: dict[str, dict] = {}

    for index, symbol in enumerate(bundle.symbols, start=1):
        print(
            f"[{model_name}] {index}/{len(bundle.symbols)} training {symbol}..."
        )
        try:
            result = trainer(
                symbol,
                bundle.segments_by_symbol[symbol],
                settings.training,
                run_directory,
            )
            print(
                f"[{model_name}] {symbol} complete in "
                f"{result['training_seconds']:.2f}s"
            )
        except Exception as exc:
            result = failure_result(symbol, exc)
            print(f"[{model_name}] {symbol} failed: {exc}")

        symbol_results[symbol] = result
        manifest["models"][model_name]["symbols"] = symbol_results
        manifest["updated_at_utc"] = utc_now_iso()
        write_json_atomic(run_directory / "manifest.json", manifest)

    return symbol_results


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    settings = apply_cli_overrides(Settings.from_environment(), args)
    requested_models = (
        ("arima", "svr") if args.models == "all" else (args.models,)
    )

    print("=" * 72)
    print("Offline Time-Series Model Training")
    print(f"models={','.join(requested_models)} source={settings.data.source}")
    print("=" * 72)

    run_id, run_directory = create_run_directory(args.run_id)
    started_at = utc_now_iso()
    started_perf = time.perf_counter()
    manifest = {
        "schema_version": 1,
        "run_id": run_id,
        "status": "initializing",
        "created_at_utc": started_at,
        "updated_at_utc": started_at,
        "requested_models": list(requested_models),
        "settings": settings.public_dict(),
        "library_versions": library_versions(),
        "data": {},
        "models": {
            model_name: {
                "status": "pending",
                "symbols": {},
                "summary": {},
            }
            for model_name in requested_models
        },
        "upload": {"status": "pending" if settings.upload.enabled else "disabled"},
    }
    write_json_atomic(run_directory / "manifest.json", manifest)

    try:
        print("[data] Loading and preprocessing training data...")
        bundle = load_dataset(settings.data)
        print(
            f"[data] source={bundle.metadata['source']} "
            f"symbols={len(bundle.symbols)} points={bundle.point_count}"
        )
        manifest["status"] = "training"
        manifest["data"] = {
            **bundle.metadata,
            "processed_point_count": bundle.point_count,
            "symbols": dataset_inventory(bundle),
        }
        manifest["updated_at_utc"] = utc_now_iso()
        write_json_atomic(run_directory / "manifest.json", manifest)

        metrics_payload = {
            "schema_version": 1,
            "run_id": run_id,
            "models": {},
        }

        for model_name in requested_models:
            manifest["models"][model_name]["status"] = "training"
            write_json_atomic(run_directory / "manifest.json", manifest)
            symbol_results = train_model_family(
                model_name,
                bundle,
                settings,
                run_directory,
                manifest,
            )
            summary = summarize_symbol_metrics(symbol_results)
            trained_count = summary["trained_symbol_count"]
            manifest["models"][model_name]["status"] = (
                "completed" if trained_count else "failed"
            )
            manifest["models"][model_name]["summary"] = summary
            metrics_payload["models"][model_name] = {
                "summary": summary,
                "symbols": {
                    symbol: result.get("metrics")
                    for symbol, result in symbol_results.items()
                    if result.get("metrics")
                },
            }
            write_json_atomic(run_directory / "metrics.json", metrics_payload)
            write_json_atomic(run_directory / "manifest.json", manifest)

        model_failures = sum(
            model_data["summary"].get("failed_symbol_count", 0)
            for model_data in manifest["models"].values()
        )
        trained_models = sum(
            model_data["summary"].get("trained_symbol_count", 0)
            for model_data in manifest["models"].values()
        )
        if trained_models == 0:
            manifest["status"] = "failed"
        elif model_failures:
            manifest["status"] = "completed_with_errors"
        else:
            manifest["status"] = "completed"

        manifest["training_seconds"] = time.perf_counter() - started_perf
        manifest["updated_at_utc"] = utc_now_iso()
        write_json_atomic(run_directory / "manifest.json", manifest)

        if settings.upload.enabled:
            try:
                manifest["upload"] = {
                    "status": "uploading",
                    "bucket": settings.upload.bucket,
                    "prefix": settings.upload.prefix,
                }
                write_json_atomic(run_directory / "manifest.json", manifest)
                upload_result = upload_run_directory(
                    run_directory,
                    run_id,
                    settings.data,
                    settings.upload,
                )
                manifest["upload"] = upload_result
                write_json_atomic(run_directory / "manifest.json", manifest)
                # Re-upload the final manifest so remote status matches local.
                upload_run_directory(
                    run_directory,
                    run_id,
                    settings.data,
                    settings.upload,
                )
            except Exception as exc:
                manifest["upload"] = {
                    "status": "failed",
                    "error_type": type(exc).__name__,
                    "error": str(exc),
                }
                manifest["status"] = (
                    "completed_with_errors"
                    if trained_models
                    else "failed"
                )
                write_json_atomic(run_directory / "manifest.json", manifest)
                print(f"[upload] Failed: {exc}")

        print("=" * 72)
        print(f"Run status: {manifest['status']}")
        print(f"Artifacts: {run_directory}")
        print("=" * 72)
        return 0 if trained_models else 2

    except Exception as exc:
        manifest["status"] = "failed"
        manifest["fatal_error"] = failure_result("__run__", exc)
        manifest["training_seconds"] = time.perf_counter() - started_perf
        manifest["updated_at_utc"] = utc_now_iso()
        write_json_atomic(run_directory / "manifest.json", manifest)
        print(f"[fatal] {type(exc).__name__}: {exc}")
        print(f"[fatal] Failure manifest: {run_directory / 'manifest.json'}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

