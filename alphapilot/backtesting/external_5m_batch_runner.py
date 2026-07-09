"""Run all local research strategies against imported external 5m data.

This runner only launches local Freqtrade backtests. It does not start dry-run,
does not connect to private exchange endpoints, and does not create orders.
"""

from __future__ import annotations

import argparse
import ast
import json
import shutil
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


DEFAULT_DATA_DIR = Path("user_data/data/local5m/okx")
DEFAULT_RESULT_DIR = Path("user_data/backtest_results")
DEFAULT_STRATEGY_DIR = Path("user_data/strategies")
DEFAULT_MANIFEST_PATH = Path("reports/external_5m_all_strategy_backtest_manifest.json")
DEFAULT_SUMMARY_PATH = Path("reports/external_5m_all_strategy_backtest_summary.json")
DEFAULT_LOG_DIR = Path("reports/external_5m_backtest_logs")


@dataclass
class StrategyInfo:
    strategyClass: str
    sourceFile: str
    timeframe: str | None
    canShort: bool | None


@dataclass
class StrategyRunResult:
    strategyClass: str
    sourceFile: str
    timeframe: str | None
    chunkIndex: int
    chunkCount: int
    pairCount: int
    pairs: list[str]
    status: str
    exitCode: int | None
    resultZipPath: str | None
    logPath: str | None
    startedAt: str
    completedAt: str
    command: list[str]
    error: str | None = None


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _literal_value(node: ast.AST) -> Any:
    try:
        return ast.literal_eval(node)
    except Exception:
        return None


def discover_strategy_classes(strategy_dir: Path) -> list[StrategyInfo]:
    class_defs: dict[str, tuple[Path, ast.ClassDef]] = {}
    parents: dict[str, list[str]] = {}
    metadata: dict[str, dict[str, Any]] = {}
    for path in sorted(strategy_dir.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in tree.body:
            if not isinstance(node, ast.ClassDef):
                continue
            class_defs[node.name] = (path, node)
            parents[node.name] = [getattr(base, "id", None) or getattr(base, "attr", None) or "" for base in node.bases]
            fields: dict[str, Any] = {}
            for statement in node.body:
                if isinstance(statement, ast.Assign):
                    for target in statement.targets:
                        if isinstance(target, ast.Name) and target.id in {"timeframe", "can_short"}:
                            fields[target.id] = _literal_value(statement.value)
            metadata[node.name] = fields

    descendants: set[str] = set()

    def is_strategy_class(name: str, seen: set[str] | None = None) -> bool:
        if seen is None:
            seen = set()
        if name in seen:
            return False
        seen.add(name)
        base_names = parents.get(name, [])
        if "IStrategy" in base_names:
            return True
        return any(base in class_defs and is_strategy_class(base, seen) for base in base_names)

    for name in class_defs:
        if name.startswith("_"):
            continue
        if is_strategy_class(name):
            descendants.add(name)

    results: list[StrategyInfo] = []
    for name in sorted(descendants):
        path, _ = class_defs[name]
        frame = metadata.get(name, {}).get("timeframe")
        short = metadata.get(name, {}).get("can_short")
        if frame is None:
            for base in parents.get(name, []):
                frame = metadata.get(base, {}).get("timeframe")
                if frame is not None:
                    break
        if short is None:
            for base in parents.get(name, []):
                short = metadata.get(base, {}).get("can_short")
                if short is not None:
                    break
        results.append(StrategyInfo(name, str(path), str(frame) if frame else None, bool(short) if short is not None else None))
    return results


def discover_pairs(data_dir: Path, timeframe: str = "5m") -> list[str]:
    direct_futures_dir = data_dir / "futures"
    nested_futures_dir = data_dir / "okx" / "futures"
    futures_dir = direct_futures_dir if direct_futures_dir.exists() else nested_futures_dir
    pairs: list[str] = []
    for path in sorted(futures_dir.glob(f"*-{timeframe}-futures.feather")):
        stem = path.name[: -len(f"-{timeframe}-futures.feather")]
        if not stem.endswith("_USDT_USDT"):
            continue
        symbol = stem[: -len("_USDT_USDT")]
        pairs.append(f"{symbol}/USDT:USDT")
    return pairs


def parse_csv(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def chunk_pairs(pairs: list[str], chunk_size: int) -> list[list[str]]:
    if chunk_size <= 0:
        return [pairs]
    return [pairs[index : index + chunk_size] for index in range(0, len(pairs), chunk_size)]


def read_last_result(result_dir: Path) -> Path | None:
    last_path = result_dir / ".last_result.json"
    if not last_path.exists():
        return None
    try:
        payload = json.loads(last_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    latest = payload.get("latest_backtest") if isinstance(payload, dict) else None
    if not latest:
        return None
    candidate = result_dir / str(latest)
    return candidate if candidate.exists() else None


def run_result_key(strategy_class: str, chunk_index: int, chunk_count: int, pairs: list[str]) -> tuple[str, int, int, tuple[str, ...]]:
    return (strategy_class, chunk_index, chunk_count, tuple(pairs))


def result_key(result: StrategyRunResult) -> tuple[str, int, int, tuple[str, ...]]:
    return run_result_key(result.strategyClass, result.chunkIndex, result.chunkCount, result.pairs)


def _path_exists(path_value: str | None) -> bool:
    if not path_value:
        return False
    return Path(path_value).exists()


def should_skip_completed_result(result: StrategyRunResult, run: bool) -> bool:
    if run:
        return result.status == "success" and _path_exists(result.resultZipPath)
    return result.status == "preview"


def load_resume_results(manifest_path: Path, run: bool) -> list[StrategyRunResult]:
    if not manifest_path.exists():
        return []
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    raw_results = payload.get("results")
    if not isinstance(raw_results, list):
        return []
    loaded: list[StrategyRunResult] = []
    seen: dict[tuple[str, int, int, tuple[str, ...]], StrategyRunResult] = {}
    for item in raw_results:
        if not isinstance(item, dict):
            continue
        try:
            result = StrategyRunResult(
                strategyClass=str(item["strategyClass"]),
                sourceFile=str(item.get("sourceFile") or ""),
                timeframe=str(item["timeframe"]) if item.get("timeframe") is not None else None,
                chunkIndex=int(item["chunkIndex"]),
                chunkCount=int(item["chunkCount"]),
                pairCount=int(item.get("pairCount") or len(item.get("pairs") or [])),
                pairs=[str(pair) for pair in item.get("pairs") or []],
                status=str(item.get("status") or "unknown"),
                exitCode=int(item["exitCode"]) if item.get("exitCode") is not None else None,
                resultZipPath=str(item["resultZipPath"]) if item.get("resultZipPath") is not None else None,
                logPath=str(item["logPath"]) if item.get("logPath") is not None else None,
                startedAt=str(item.get("startedAt") or ""),
                completedAt=str(item.get("completedAt") or ""),
                command=[str(part) for part in item.get("command") or []],
                error=str(item["error"]) if item.get("error") is not None else None,
            )
        except (KeyError, TypeError, ValueError):
            continue
        if should_skip_completed_result(result, run):
            seen[result_key(result)] = result
    loaded.extend(seen.values())
    return loaded


def build_command(
    strategy: str,
    timeframe: str | None,
    timerange: str,
    pairs: list[str],
    data_dir: Path,
    config: Path,
    skip_pair_validation: bool,
) -> list[str]:
    config_arg = config.as_posix()
    data_dir_arg = data_dir.as_posix()
    command = [
        "docker",
        "compose",
        "run",
        "--rm",
        "freqtrade",
        "backtesting",
        "--config",
        config_arg,
        "--datadir",
        data_dir_arg,
        "--strategy",
        strategy,
        "--timerange",
        timerange,
        "--fee",
        "0.0005",
        "--export",
        "trades",
        "--pairs",
        *pairs,
    ]
    if timeframe:
        command.extend(["--timeframe", timeframe])
    if skip_pair_validation:
        command.append("--skip-pair-validation")
    return command


def run_strategy(
    info: StrategyInfo,
    pairs: list[str],
    chunk_index: int,
    chunk_count: int,
    timerange: str,
    data_dir: Path,
    config: Path,
    result_dir: Path,
    log_dir: Path,
    output_prefix: str,
    skip_pair_validation: bool,
    run: bool,
) -> StrategyRunResult:
    started_at = utc_now()
    command = build_command(info.strategyClass, info.timeframe, timerange, pairs, data_dir, config, skip_pair_validation)
    log_path = log_dir / f"{output_prefix}_{info.strategyClass}_chunk_{chunk_index:03d}_of_{chunk_count:03d}.log"
    if not run:
        return StrategyRunResult(
            strategyClass=info.strategyClass,
            sourceFile=info.sourceFile,
            timeframe=info.timeframe,
            chunkIndex=chunk_index,
            chunkCount=chunk_count,
            pairCount=len(pairs),
            pairs=pairs,
            status="preview",
            exitCode=None,
            resultZipPath=None,
            logPath=None,
            startedAt=started_at,
            completedAt=utc_now(),
            command=command,
        )
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        previous_latest = read_last_result(result_dir)
        with log_path.open("w", encoding="utf-8") as log_file:
            completed = subprocess.run(  # noqa: S603 - local docker command.
                command,
                cwd=Path.cwd(),
                text=True,
                check=False,
                stdout=log_file,
                stderr=subprocess.STDOUT,
            )
        latest = read_last_result(result_dir) if completed.returncode == 0 else None
        copied_path: Path | None = None
        status = "success" if completed.returncode == 0 else "failed"
        error = None if completed.returncode == 0 else f"docker exited with code {completed.returncode}"
        if completed.returncode == 0:
            if latest and latest != previous_latest:
                copied_path = result_dir / f"{output_prefix}_{info.strategyClass}_chunk_{chunk_index:03d}_of_{chunk_count:03d}.zip"
                shutil.copy2(latest, copied_path)
            else:
                status = "result_missing"
                error = ".last_result.json did not point to a new result zip"
        return StrategyRunResult(
            strategyClass=info.strategyClass,
            sourceFile=info.sourceFile,
            timeframe=info.timeframe,
            chunkIndex=chunk_index,
            chunkCount=chunk_count,
            pairCount=len(pairs),
            pairs=pairs,
            status=status,
            exitCode=completed.returncode,
            resultZipPath=str(copied_path) if copied_path else None,
            logPath=str(log_path),
            startedAt=started_at,
            completedAt=utc_now(),
            command=command,
            error=error,
        )
    except Exception as exc:  # noqa: BLE001 - keep batch running and report strategy-level failure.
        return StrategyRunResult(
            strategyClass=info.strategyClass,
            sourceFile=info.sourceFile,
            timeframe=info.timeframe,
            chunkIndex=chunk_index,
            chunkCount=chunk_count,
            pairCount=len(pairs),
            pairs=pairs,
            status="failed",
            exitCode=None,
            resultZipPath=None,
            logPath=str(log_path),
            startedAt=started_at,
            completedAt=utc_now(),
            command=command,
            error=str(exc),
        )


def build_manifest(
    results: list[StrategyRunResult],
    pairs: list[str],
    timerange: str,
    data_dir: Path,
    run: bool,
    selected_strategy_count: int,
) -> dict[str, Any]:
    return {
        "reportId": "external_5m_all_strategy_backtest_manifest",
        "source": "alphapilot_external_5m_batch_runner",
        "runMode": "executed" if run else "preview",
        "timerange": timerange,
        "dataDir": str(data_dir),
        "pairCount": len(pairs),
        "pairs": pairs,
        "selectedStrategyCount": selected_strategy_count,
        "runCount": len(results),
        "successCount": sum(1 for item in results if item.status == "success"),
        "failedCount": sum(1 for item in results if item.status == "failed"),
        "resultMissingCount": sum(1 for item in results if item.status == "result_missing"),
        "previewCount": sum(1 for item in results if item.status == "preview"),
        "results": [asdict(item) for item in results],
        "safetyBoundary": {
            "dryRunApproved": False,
            "liveTradingApproved": False,
            "tradeApiUsed": False,
            "withdrawApiUsed": False,
            "apiKeyStored": False,
            "accountRead": False,
            "positionRead": False,
            "orderCreated": False,
            "autoTradingUsed": False,
        },
        "generatedAt": utc_now(),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run all local strategies against imported external 5m data.")
    parser.add_argument("--data-dir", default=str(DEFAULT_DATA_DIR))
    parser.add_argument("--config", default="user_data/config/config.backtest.json")
    parser.add_argument("--strategy-dir", default=str(DEFAULT_STRATEGY_DIR))
    parser.add_argument("--result-dir", default=str(DEFAULT_RESULT_DIR))
    parser.add_argument("--log-dir", default=str(DEFAULT_LOG_DIR))
    parser.add_argument("--manifest-path", default=str(DEFAULT_MANIFEST_PATH))
    parser.add_argument("--summary-path", default=str(DEFAULT_SUMMARY_PATH))
    parser.add_argument("--timerange", default="20180101-")
    parser.add_argument("--pairs", default="")
    parser.add_argument("--max-pairs", type=int, default=0)
    parser.add_argument("--pair-chunk-size", type=int, default=20)
    parser.add_argument("--max-chunks", type=int, default=0)
    parser.add_argument("--strategies", default="all")
    parser.add_argument("--output-prefix", default="external_5m_all_strategy")
    parser.add_argument("--run", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--skip-pair-validation", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    data_dir = Path(args.data_dir)
    result_dir = Path(args.result_dir)
    log_dir = Path(args.log_dir)
    strategy_dir = Path(args.strategy_dir)
    config = Path(args.config)
    all_pairs = parse_csv(args.pairs) if args.pairs else discover_pairs(data_dir, "5m")
    if args.max_pairs and args.max_pairs > 0:
        all_pairs = all_pairs[: args.max_pairs]
    if not all_pairs:
        raise SystemExit(f"No imported pairs found under {data_dir}")
    discovered_strategies = discover_strategy_classes(strategy_dir)
    requested = None if args.strategies == "all" else set(parse_csv(args.strategies))
    strategy_infos = [item for item in discovered_strategies if requested is None or item.strategyClass in requested]
    if not strategy_infos:
        raise SystemExit("No strategy classes selected.")

    print(f"Pairs: {len(all_pairs)}")
    print(f"Strategies: {len(strategy_infos)}")
    print(f"Timerange: {args.timerange}")
    print(f"Pair chunk size: {args.pair_chunk_size if args.pair_chunk_size > 0 else 'all pairs in one run'}")
    print(f"Run mode: {'execute' if args.run else 'preview'}")
    print(f"Resume mode: {'enabled' if args.resume else 'disabled'}")
    print("Research backtest only. No Dry-run, no live trading, no private API, no orders.")

    pair_chunks = chunk_pairs(all_pairs, args.pair_chunk_size)
    if args.max_chunks and args.max_chunks > 0:
        pair_chunks = pair_chunks[: args.max_chunks]

    allowed_keys = {
        run_result_key(info.strategyClass, chunk_index, len(pair_chunks), pair_chunk)
        for info in strategy_infos
        for chunk_index, pair_chunk in enumerate(pair_chunks, start=1)
    }
    resume_results = load_resume_results(Path(args.manifest_path), args.run) if args.resume else []
    results: list[StrategyRunResult] = [item for item in resume_results if result_key(item) in allowed_keys]
    completed_by_key = {result_key(item): item for item in results}
    if args.resume:
        print(f"Resume loaded completed chunks: {len(results)}")
    for index, info in enumerate(strategy_infos, start=1):
        print(f"\n[{index}/{len(strategy_infos)}] {info.strategyClass}")
        for chunk_index, pair_chunk in enumerate(pair_chunks, start=1):
            print(f"  chunk {chunk_index}/{len(pair_chunks)} pairs={len(pair_chunk)} first={pair_chunk[0]} last={pair_chunk[-1]}")
            current_key = run_result_key(info.strategyClass, chunk_index, len(pair_chunks), pair_chunk)
            existing_result = completed_by_key.get(current_key)
            if existing_result is not None:
                print(f"  status=skipped resume result={existing_result.resultZipPath} log={existing_result.logPath}")
                continue
            result = run_strategy(
                info=info,
                pairs=pair_chunk,
                chunk_index=chunk_index,
                chunk_count=len(pair_chunks),
                timerange=args.timerange,
                data_dir=data_dir,
                config=config,
                result_dir=result_dir,
                log_dir=log_dir,
                output_prefix=args.output_prefix,
                skip_pair_validation=args.skip_pair_validation,
                run=args.run,
            )
            print(f"  status={result.status} exitCode={result.exitCode} result={result.resultZipPath} log={result.logPath}")
            if result.error:
                print(f"  error={result.error}")
            results.append(result)
            if should_skip_completed_result(result, args.run):
                completed_by_key[current_key] = result
            manifest = build_manifest(results, all_pairs, args.timerange, data_dir, args.run, len(strategy_infos))
            Path(args.manifest_path).parent.mkdir(parents=True, exist_ok=True)
            Path(args.manifest_path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    manifest = build_manifest(results, all_pairs, args.timerange, data_dir, args.run, len(strategy_infos))
    summary = {
        key: manifest[key]
        for key in (
            "reportId",
            "runMode",
            "timerange",
            "pairCount",
            "selectedStrategyCount",
            "runCount",
            "successCount",
            "failedCount",
            "resultMissingCount",
            "previewCount",
            "generatedAt",
        )
    }
    Path(args.manifest_path).write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(args.summary_path).write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(f"Wrote {args.manifest_path}")
    print(f"Wrote {args.summary_path}")


if __name__ == "__main__":
    main()
