#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MySQL实例健康巡检脚本

基于火山引擎文档:
- GetMetricData API: https://www.volcengine.com/docs/6408/105542
- Python SDK: https://www.volcengine.com/docs/6408/170945

功能:
1. 获取指定时间范围内MySQL实例的监控数据
2. 分析性能趋势和识别瓶颈
3. 计算健康评分
4. 生成结构化巡检报告
"""

import argparse
import os
import json
import re
import time
import math
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
import statistics

# 火山引擎 SDK
import volcenginesdkcore
import volcenginesdkrdsmysqlv2
import volcenginesdkcloudmonitor
from volcenginesdkcore.rest import ApiException


DEFAULT_OUTPUT_DIR = r"D:\Study\python\agent\maintenance-agent\metric_data"
PERCENT_BASED_SPIKE_METRICS = {"cpu", "memory", "disk_util"}
PERCENT_BASED_HIGH_RISK_THRESHOLD = 70.0
THROUGHPUT_HEURISTIC_METRICS = {"qps", "tps", "IOPSRate", "network_in", "network_out"}
REPLICATION_DELAY_HIGH_RISK_THRESHOLD = 5.0
RECENT_TREND_LOOKBACK_HOURS = 24
RECENT_TREND_MIN_POINTS = 5
HIGH_PERCENTILE_MEDIUM_RATIO = 2.0
HIGH_PERCENTILE_HIGH_RATIO = 3.0
HIGH_PERCENTILE_P99_HIGH_RATIO = 4.0
THROUGHPUT_HIGH_SPIKE_RATIO = 0.2
THROUGHPUT_HIGH_CV = 1.0

RESOURCE_SCORE_BANDS = {
    "cpu": [(60.0, 20), (70.0, 15), (80.0, 10), (math.inf, 5)],
    "memory": [(70.0, 20), (80.0, 15), (90.0, 10), (math.inf, 5)],
    "disk_util": [(70.0, 20), (80.0, 15), (90.0, 10), (math.inf, 5)],
}
RESOURCE_MEDIAN_WARNING_THRESHOLDS = {
    "cpu": 60.0,
    "memory": 70.0,
    "disk_util": 70.0,
}
RESOURCE_P95_WARNING_THRESHOLDS = {
    "cpu": 70.0,
    "memory": 80.0,
    "disk_util": 80.0,
}


def load_runtime_env() -> None:
    """自动加载可能存在的 .env 文件（不覆盖已存在环境变量）。"""
    try:
        from dotenv import load_dotenv
    except Exception:
        return

    backend_root = Path(__file__).resolve().parents[3]
    cwd = Path.cwd()
    candidates = [
        cwd / ".env",
        cwd / "backend" / ".env",
        backend_root / ".env",
    ]

    seen: set[str] = set()
    for path in candidates:
        key = str(path.resolve()) if path.exists() else str(path)
        if key in seen:
            continue
        seen.add(key)
        if path.exists():
            load_dotenv(path, override=False)


def normalize_credential_ref(value: str) -> str:
    normalized = str(value or "").strip().lower()
    normalized = re.sub(r"[^a-z0-9_-]+", "_", normalized)
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    if not normalized:
        raise ValueError("credential_ref 不能为空")
    return normalized


def credential_env_keys(credential_ref: str) -> tuple[str, str]:
    suffix = re.sub(r"[^A-Za-z0-9]+", "_", credential_ref).strip("_").upper()
    if not suffix:
        raise ValueError("credential_ref 无法转换为环境变量名")
    prefix = f"VOLC_CREDENTIAL_{suffix}"
    return f"{prefix}_AK", f"{prefix}_SK"


def resolve_credentials(
    *,
    ak: Optional[str],
    sk: Optional[str],
    credential_ref: Optional[str],
) -> tuple[str, str]:
    explicit_ak = (ak or "").strip()
    explicit_sk = (sk or "").strip()
    if explicit_ak and explicit_sk:
        return explicit_ak, explicit_sk
    if explicit_ak or explicit_sk:
        raise ValueError("--ak 和 --sk 必须同时提供")

    normalized_ref = normalize_credential_ref(credential_ref or "")
    ak_key, sk_key = credential_env_keys(normalized_ref)
    resolved_ak = os.getenv(ak_key, "").strip()
    resolved_sk = os.getenv(sk_key, "").strip()
    if not resolved_ak or not resolved_sk:
        raise ValueError(
            f"未找到 credential_ref={normalized_ref} 对应的环境变量，请检查 {ak_key} / {sk_key}"
        )
    return resolved_ak, resolved_sk


def non_negative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("value must be a non-negative integer")
    return parsed


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Collect Volcengine RDS MySQL instance details and metrics."
    )
    parser.add_argument("--instance-id", required=True, help="MySQL instance ID")
    parser.add_argument("--ak", help="Volcengine access key")
    parser.add_argument("--sk", help="Volcengine secret key")
    parser.add_argument("--credential-ref", help="Credential ref")
    parser.add_argument(
        "--action",
        choices=["detail", "metrics", "all"],
        default="all",
        help="detail, metrics, or all",
    )
    parser.add_argument("--start", help="Start time in YYYY-MM-DD HH:MM format")
    parser.add_argument("--end", help="End time in YYYY-MM-DD HH:MM format")
    parser.add_argument(
        "--hours",
        type=int,
        default=1,
        help="Recent hours to query when start/end are not provided",
    )
    parser.add_argument("--period", default="5m", help="Metric aggregation period")
    parser.add_argument("--region", default="cn-shanghai", help="Volcengine region")
    parser.add_argument("--output", help="Output file path in JSON format")
    parser.add_argument(
        "--retention-days",
        type=non_negative_int,
        default=30,
        help="Delete metric_data JSON files older than this many days before collection",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="Skip deleting expired metric_data JSON files before collection",
    )
    return parser


def cleanup_expired_metric_data(
    output_dir: str | Path,
    retention_days: int,
    *,
    now: datetime | None = None,
    printer=print,
) -> dict[str, int]:
    metric_dir = Path(output_dir)
    summary = {"scanned": 0, "deleted": 0, "failed": 0}

    if not metric_dir.exists():
        return summary

    current_time = now or datetime.now()
    cutoff_time = current_time - timedelta(days=retention_days)

    for file_path in sorted(metric_dir.glob("*.json")):
        if not file_path.is_file():
            continue

        summary["scanned"] += 1
        modified_at = datetime.fromtimestamp(file_path.stat().st_mtime)
        if modified_at >= cutoff_time:
            continue

        try:
            os.remove(file_path)
            summary["deleted"] += 1
            printer(f"Deleted expired metric_data file: {file_path}")
        except OSError as exc:
            summary["failed"] += 1
            printer(
                f"Warning: failed to delete expired metric_data file {file_path}: {exc}"
            )

    printer(
        "metric_data cleanup summary: "
        f"scanned={summary['scanned']}, "
        f"deleted={summary['deleted']}, "
        f"failed={summary['failed']}"
    )
    return summary


def resolve_mad_window_size(period: str | None) -> int:
    normalized = str(period or "").strip().lower()
    if normalized == "5m":
        return 5
    if normalized in {"1h", "6h"}:
        return 3
    return 3


def period_to_seconds(period: str | None) -> int:
    normalized = str(period or "").strip().lower()
    if normalized.endswith("m"):
        return int(normalized[:-1]) * 60
    if normalized.endswith("h"):
        return int(normalized[:-1]) * 3600
    if normalized.endswith("d"):
        return int(normalized[:-1]) * 86400
    raise ValueError(f"不支持的 period: {period}")


def percentile_nearest_rank(values: List[float], percentile: int) -> Optional[float]:
    if not values:
        return None
    ordered_values = sorted(values)
    rank = max(1, math.ceil((percentile / 100) * len(ordered_values)))
    return round(ordered_values[rank - 1], 4)


def calculate_coverage(
    *,
    start_time: Optional[datetime],
    end_time: Optional[datetime],
    period: str,
    actual_point_count: int,
    series_count: int = 1,
) -> Dict[str, Any]:
    expected_point_count = 0
    if start_time and end_time and end_time >= start_time:
        period_seconds = period_to_seconds(period)
        duration_seconds = int((end_time - start_time).total_seconds())
        expected_point_count = ((duration_seconds // period_seconds) + 1) * max(
            series_count, 1
        )

    missing_point_count = max(expected_point_count - actual_point_count, 0)
    coverage_ratio = (
        round(actual_point_count / expected_point_count, 4)
        if expected_point_count
        else 0.0
    )
    return {
        "expected_point_count": expected_point_count,
        "actual_point_count": actual_point_count,
        "missing_point_count": missing_point_count,
        "coverage_ratio": coverage_ratio,
    }


def compute_trend(values: List[float]) -> Dict[str, Any]:
    if len(values) < 2:
        return {"direction": "flat", "slope": 0.0}

    x_values = list(range(len(values)))
    x_mean = statistics.mean(x_values)
    y_mean = statistics.mean(values)
    numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, values))
    denominator = sum((x - x_mean) ** 2 for x in x_values)
    slope = (numerator / denominator) if denominator else 0.0
    rounded_slope = round(slope, 4)
    if abs(rounded_slope) < 1e-9:
        direction = "flat"
    elif rounded_slope > 0:
        direction = "up"
    else:
        direction = "down"
    return {"direction": direction, "slope": rounded_slope}


def resolve_recent_trend_sample_size(
    value_count: int,
    *,
    period: str = "5m",
    lookback_hours: int = RECENT_TREND_LOOKBACK_HOURS,
) -> int:
    if value_count <= RECENT_TREND_MIN_POINTS:
        return value_count

    target_points = max(
        int((lookback_hours * 3600) / period_to_seconds(period)) + 1,
        RECENT_TREND_MIN_POINTS,
    )
    if value_count < target_points:
        return max(RECENT_TREND_MIN_POINTS, value_count // 2)
    return target_points


def compute_recent_trend(
    values: List[float],
    *,
    period: str = "5m",
    lookback_hours: int = RECENT_TREND_LOOKBACK_HOURS,
) -> Dict[str, Any]:
    sample_size = resolve_recent_trend_sample_size(
        len(values),
        period=period,
        lookback_hours=lookback_hours,
    )
    if sample_size <= 0:
        return {
            "direction": "flat",
            "slope": 0.0,
            "sample_size": 0,
            "lookback_hours": lookback_hours,
        }

    recent_values = values[-sample_size:]
    return {
        **compute_trend(recent_values),
        "sample_size": sample_size,
        "lookback_hours": lookback_hours,
    }


def build_high_percentile_pressure(distribution: Dict[str, Any]) -> Dict[str, Any]:
    median = distribution.get("median")
    p95 = distribution.get("p95")
    p99 = distribution.get("p99")
    if median is None or p95 is None or p99 is None:
        return {
            "level": "unknown",
            "p95_to_median_ratio": None,
            "p99_to_median_ratio": None,
        }

    safe_median = max(abs(median), 1e-9)
    p95_ratio = round(p95 / safe_median, 4)
    p99_ratio = round(p99 / safe_median, 4)
    if (
        p95_ratio >= HIGH_PERCENTILE_HIGH_RATIO
        or p99_ratio >= HIGH_PERCENTILE_P99_HIGH_RATIO
    ):
        level = "high"
    elif p95_ratio >= HIGH_PERCENTILE_MEDIUM_RATIO or p99_ratio >= HIGH_PERCENTILE_HIGH_RATIO:
        level = "medium"
    else:
        level = "low"

    return {
        "level": level,
        "p95_to_median_ratio": p95_ratio,
        "p99_to_median_ratio": p99_ratio,
    }


def detect_sliding_mad_spikes(
    data_points: List[Dict[str, Any]],
    *,
    window_size: int,
    mad_multiplier: float = 6.0,
    top_n: int = 3,
) -> Dict[str, Any]:
    ordered_points = [dp for dp in data_points if dp.get("value") is not None]
    values = [dp["value"] for dp in ordered_points]
    spike_scores: dict[int, Dict[str, Any]] = {}

    if window_size < 3 or len(values) < window_size:
        return {
            "method": "sliding_mad",
            "window_size": window_size,
            "mad_multiplier": float(mad_multiplier),
            "evaluated_point_count": 0,
            "spike_count": 0,
            "spike_ratio": 0.0,
            "max_deviation_score": 0.0,
            "has_spike": False,
            "top_spikes": [],
        }

    evaluated_indexes: set[int] = set()

    for window_start in range(0, len(values) - window_size + 1):
        window_values = values[window_start : window_start + window_size]
        for offset, center_value in enumerate(window_values):
            baseline = window_values[:offset] + window_values[offset + 1 :]
            if not baseline:
                continue

            global_index = window_start + offset
            evaluated_indexes.add(global_index)
            baseline_median = statistics.median(baseline)
            deviation = abs(center_value - baseline_median)
            baseline_deviations = [abs(value - baseline_median) for value in baseline]
            mad = statistics.median(baseline_deviations)

            if mad == 0:
                if deviation <= 0:
                    continue
                score = mad_multiplier + deviation
            else:
                score = deviation / mad

            if score > mad_multiplier:
                rounded_score = round(score, 4)
                point = ordered_points[global_index]
                previous_score = spike_scores.get(global_index, {}).get("score", 0.0)
                if rounded_score >= previous_score:
                    spike_scores[global_index] = {
                        "ts": point.get("ts"),
                        "time": point.get("time"),
                        "value": point.get("value"),
                        "score": rounded_score,
                        "node": point.get("node"),
                    }

    spike_count = len(spike_scores)
    evaluated_points = len(evaluated_indexes)
    spike_ratio = round(spike_count / evaluated_points, 4) if evaluated_points else 0.0
    top_spikes = sorted(
        spike_scores.values(),
        key=lambda item: (-item["score"], item.get("ts") or 0),
    )[:top_n]
    return {
        "method": "sliding_mad",
        "window_size": window_size,
        "mad_multiplier": float(mad_multiplier),
        "evaluated_point_count": evaluated_points,
        "spike_count": spike_count,
        "spike_ratio": spike_ratio,
        "max_deviation_score": (
            max(item["score"] for item in spike_scores.values()) if spike_scores else 0.0
        ),
        "has_spike": spike_count > 0,
        "top_spikes": top_spikes,
    }


def classify_spike_risk(
    spike_evidence: Dict[str, Any],
    *,
    metric_key: Optional[str] = None,
    absolute_max: Optional[float] = None,
    distribution: Optional[Dict[str, Any]] = None,
    variability: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    if not spike_evidence.get("has_spike"):
        return {
            "risk_tier": "none",
            "risk_reason": "no statistical spikes detected",
        }

    if metric_key in PERCENT_BASED_SPIKE_METRICS:
        if (
            absolute_max is not None
            and absolute_max >= PERCENT_BASED_HIGH_RISK_THRESHOLD
        ):
            return {
                "risk_tier": "high",
                "risk_reason": (
                    f"statistical spike reaches {round(absolute_max, 4)} and meets "
                    f"the {PERCENT_BASED_HIGH_RISK_THRESHOLD:.0f}% absolute threshold"
                ),
            }
        return {
            "risk_tier": "low",
            "risk_reason": (
                "statistical spike detected, but absolute utilization stays below "
                f"the {PERCENT_BASED_HIGH_RISK_THRESHOLD:.0f}% threshold"
            ),
        }

    if metric_key == "replication_delay":
        if (
            absolute_max is not None
            and absolute_max >= REPLICATION_DELAY_HIGH_RISK_THRESHOLD
        ):
            return {
                "risk_tier": "high",
                "risk_reason": (
                    f"replication delay reaches {round(absolute_max, 4)}s and exceeds "
                    f"the {REPLICATION_DELAY_HIGH_RISK_THRESHOLD:.0f}s threshold"
                ),
            }
        return {
            "risk_tier": "low",
            "risk_reason": "statistical spike detected, but replication delay stays below 5s",
        }

    if metric_key in THROUGHPUT_HEURISTIC_METRICS:
        pressure = build_high_percentile_pressure(distribution or {})
        cv = float((variability or {}).get("cv") or 0.0)
        spike_ratio = float(spike_evidence.get("spike_ratio") or 0.0)
        heuristic_signals: list[str] = []

        if pressure["level"] == "high":
            heuristic_signals.append(
                f"p95/p99 pressure ({pressure['p95_to_median_ratio']}x median)"
            )
        if cv >= THROUGHPUT_HIGH_CV and spike_ratio > THROUGHPUT_HIGH_SPIKE_RATIO:
            heuristic_signals.append(f"cv={round(cv, 4)}")
        if spike_ratio > THROUGHPUT_HIGH_SPIKE_RATIO:
            heuristic_signals.append(f"spike_ratio={round(spike_ratio, 4)}")

        if len(heuristic_signals) >= 2:
            return {
                "risk_tier": "high",
                "risk_reason": (
                    "heuristic throughput risk promoted by "
                    + ", ".join(heuristic_signals)
                ),
            }

        return {
            "risk_tier": "low",
            "risk_reason": (
                "statistical spike detected, but without a capacity model the "
                "heuristic throughput signals are not strong enough for high risk"
            ),
        }

    return {
        "risk_tier": "low",
        "risk_reason": (
            "statistical spike detected, but this metric has no capacity model "
            "for high-risk spike promotion"
        ),
    }


def summarize_window_alignment(
    primary_evidence: Dict[str, Any],
    *,
    recent3d_evidence: Optional[Dict[str, Any]] = None,
    recent24h_evidence: Optional[Dict[str, Any]] = None,
) -> Dict[str, str]:
    def is_abnormal(evidence: Optional[Dict[str, Any]]) -> Optional[bool]:
        if evidence is None:
            return None
        return evidence.get("spikes", {}).get("risk_tier") == "high"

    main_flag = bool(is_abnormal(primary_evidence))
    recent3d_flag = is_abnormal(recent3d_evidence)
    recent24h_flag = is_abnormal(recent24h_evidence)

    if recent3d_flag is None and recent24h_flag is None:
        return {
            "current_status": "single_window_only",
            "window_alignment": "main_only",
        }
    if recent24h_flag is None:
        return {
            "current_status": "recent24h_unavailable",
            "window_alignment": (
                f"main_{'abnormal' if main_flag else 'normal'}_recent3d_"
                f"{'abnormal' if recent3d_flag else 'normal'}_recent24h_unknown"
            ),
        }
    if main_flag and recent3d_flag and recent24h_flag:
        return {
            "current_status": "persistent_active",
            "window_alignment": "main_abnormal_recent3d_abnormal_recent24h_abnormal",
        }
    if main_flag and recent3d_flag and not recent24h_flag:
        return {
            "current_status": "persistent_but_easing",
            "window_alignment": "main_abnormal_recent3d_abnormal_recent24h_normal",
        }
    if not main_flag and recent3d_flag and recent24h_flag:
        return {
            "current_status": "recently_intensified",
            "window_alignment": "main_normal_recent3d_abnormal_recent24h_abnormal",
        }
    if not main_flag and not recent3d_flag and recent24h_flag:
        return {
            "current_status": "newly_active",
            "window_alignment": "main_normal_recent3d_normal_recent24h_abnormal",
        }
    if main_flag and not recent3d_flag and not recent24h_flag:
        return {
            "current_status": "historical_only",
            "window_alignment": "main_abnormal_recent3d_normal_recent24h_normal",
        }
    return {
        "current_status": "inactive",
        "window_alignment": (
            f"main_{'abnormal' if main_flag else 'normal'}_recent3d_"
            f"{'abnormal' if recent3d_flag else 'normal'}_recent24h_"
            f"{'abnormal' if recent24h_flag else 'normal'}"
        ),
    }


def compute_balanced_resource_score(
    metric_key: str,
    summary: Dict[str, Any],
    evidence: Dict[str, Any],
) -> Dict[str, Any]:
    if metric_key not in RESOURCE_SCORE_BANDS:
        raise ValueError(f"unsupported resource metric for balanced score: {metric_key}")

    avg = float(summary.get("avg") or 0.0)
    base_score = 5
    for threshold, score in RESOURCE_SCORE_BANDS[metric_key]:
        if avg < threshold:
            base_score = score
            break

    drivers: list[str] = []
    median = summary.get("median")
    if (
        median is not None
        and median >= RESOURCE_MEDIAN_WARNING_THRESHOLDS[metric_key]
    ):
        drivers.append("median")

    p95 = evidence.get("distribution", {}).get("p95")
    if p95 is not None and p95 >= RESOURCE_P95_WARNING_THRESHOLDS[metric_key]:
        drivers.append("p95")

    if evidence.get("spikes", {}).get("risk_tier") == "high":
        drivers.append("risk_tier")

    penalty_steps = max(len(drivers) - 1, 0)
    score = max(base_score - (penalty_steps * 5), 5)
    return {
        "score": score,
        "base_score": base_score,
        "drivers": drivers,
    }


def build_value_summary(
    values: List[float], *, period: str | None = "5m"
) -> Dict[str, Any]:
    if not values:
        return {
            "data_point_count": 0,
            "min": None,
            "max": None,
            "range": None,
            "avg": None,
            "median": None,
            "weighted": None,
        }

    avg = round(statistics.mean(values), 4)
    median = round(statistics.median(values), 4)
    return {
        "data_point_count": len(values),
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "range": round(max(values) - min(values), 4),
        "avg": avg,
        "median": median,
        "weighted": round((avg + median) / 2, 4),
    }


def build_metric_evidence(
    data_points: List[Dict[str, Any]],
    *,
    metric_key: Optional[str] = None,
    period: str = "5m",
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    series_count: int = 1,
) -> Dict[str, Any]:
    ordered_points = [dp for dp in data_points if dp.get("value") is not None]
    values = [dp["value"] for dp in ordered_points]
    window_size = resolve_mad_window_size(period)

    derived_start_time = start_time
    derived_end_time = end_time
    if ordered_points and (derived_start_time is None or derived_end_time is None):
        timestamps = [dp["ts"] for dp in ordered_points if dp.get("ts") is not None]
        if timestamps:
            if derived_start_time is None:
                derived_start_time = datetime.fromtimestamp(min(timestamps))
            if derived_end_time is None:
                derived_end_time = datetime.fromtimestamp(max(timestamps))

    if not values:
        spike_evidence = detect_sliding_mad_spikes(
            [],
            window_size=window_size,
        )
        pressure = build_high_percentile_pressure({})
        variability = {
            "stddev": 0.0,
            "cv": 0.0,
        }
        spike_risk = classify_spike_risk(
            spike_evidence,
            metric_key=metric_key,
            absolute_max=None,
            distribution=None,
            variability=variability,
        )
        return {
            "source_point_count": 0,
            "source_period": period,
            "window": {
                "start": derived_start_time.isoformat() if derived_start_time else None,
                "end": derived_end_time.isoformat() if derived_end_time else None,
            },
            "coverage": calculate_coverage(
                start_time=derived_start_time,
                end_time=derived_end_time,
                period=period,
                actual_point_count=0,
                series_count=series_count,
            ),
            "distribution": {
                "min": None,
                "max": None,
                "range": None,
                "avg": None,
                "median": None,
                "p95": None,
                "p99": None,
            },
            "pressure": {"high_percentile": pressure},
            "variability": variability,
            "spikes": {"sliding_mad": spike_evidence, **spike_risk},
            "trend": {"direction": "flat", "slope": 0.0},
            "recent_trend": {
                "direction": "flat",
                "slope": 0.0,
                "sample_size": 0,
                "lookback_hours": RECENT_TREND_LOOKBACK_HOURS,
            },
        }

    avg = statistics.mean(values)
    stddev = statistics.pstdev(values) if len(values) > 1 else 0.0
    cv = (stddev / avg) if abs(avg) > 1e-9 else 0.0
    distribution = {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "range": round(max(values) - min(values), 4),
        "avg": round(avg, 4),
        "median": round(statistics.median(values), 4),
        "p95": percentile_nearest_rank(values, 95),
        "p99": percentile_nearest_rank(values, 99),
    }
    pressure = {
        "high_percentile": build_high_percentile_pressure(distribution),
    }
    variability = {
        "stddev": round(stddev, 4),
        "cv": round(cv, 4),
    }
    grouped_points: Dict[str, List[Dict[str, Any]]] = {}
    for point in ordered_points:
        node_key = point.get("node") or "__single__"
        grouped_points.setdefault(node_key, []).append(point)

    if len(grouped_points) == 1:
        spike_evidence = detect_sliding_mad_spikes(
            sorted(ordered_points, key=lambda item: item.get("ts") or 0),
            window_size=window_size,
        )
    else:
        grouped_spike_results = []
        for group_points in grouped_points.values():
            grouped_spike_results.append(
                detect_sliding_mad_spikes(
                    sorted(group_points, key=lambda item: item.get("ts") or 0),
                    window_size=window_size,
                )
            )

        merged_top_spikes = sorted(
            [
                spike
                for result in grouped_spike_results
                for spike in result.get("top_spikes", [])
            ],
            key=lambda item: (-item["score"], item.get("ts") or 0),
        )[:3]
        evaluated_point_count = sum(
            result.get("evaluated_point_count", 0) for result in grouped_spike_results
        )
        spike_count = sum(result["spike_count"] for result in grouped_spike_results)
        spike_evidence = {
            "method": "sliding_mad",
            "window_size": window_size,
            "mad_multiplier": 6.0,
            "evaluated_point_count": evaluated_point_count,
            "spike_count": spike_count,
            "spike_ratio": (
                round(spike_count / evaluated_point_count, 4)
                if evaluated_point_count
                else 0.0
            ),
            "max_deviation_score": max(
                (result["max_deviation_score"] for result in grouped_spike_results),
                default=0.0,
            ),
            "has_spike": spike_count > 0,
            "top_spikes": merged_top_spikes,
        }

    spike_risk = classify_spike_risk(
        spike_evidence,
        metric_key=metric_key,
        absolute_max=distribution["max"],
        distribution=distribution,
        variability=variability,
    )

    return {
        "source_point_count": len(values),
        "source_period": period,
        "window": {
            "start": derived_start_time.isoformat() if derived_start_time else None,
            "end": derived_end_time.isoformat() if derived_end_time else None,
        },
        "coverage": calculate_coverage(
            start_time=derived_start_time,
            end_time=derived_end_time,
            period=period,
            actual_point_count=len(values),
            series_count=series_count,
        ),
        "distribution": distribution,
        "pressure": pressure,
        "variability": variability,
        "spikes": {"sliding_mad": spike_evidence, **spike_risk},
        "trend": compute_trend(values),
        "recent_trend": compute_recent_trend(values, period=period),
    }


class MySQLInstanceInfoCollector:
    """MySQL实例信息采集器"""

    # 云监控命名空间
    NAMESPACE = "VCM_RDS_MySQL"

    # 核心监控指标列表
    METRIC_DEFINITIONS = {
        "cpu": {
            "name": "CpuUtil",
            "display_name": "CPU使用率",
            "unit": "%",
            "description": "实例CPU使用率",
            "sub_namespace": "resource_monitor_new",
        },
        "memory": {
            "name": "MemUtil",
            "display_name": "内存使用率",
            "unit": "%",
            "description": "实例内存使用率",
            "sub_namespace": "resource_monitor_new",
        },
        "disk_util": {
            "name": "DiskUtil",
            "display_name": "磁盘使用率",
            "unit": "%",
            "description": "磁盘空间使用百分比",
            "sub_namespace": "resource_monitor_new",
        },
        "qps": {
            "name": "QPS",
            "display_name": "每秒查询数",
            "unit": "Count/s",
            "description": "每秒查询请求数",
            "sub_namespace": "engine_monitor",
        },
        "tps": {
            "name": "TPS",
            "display_name": "每秒事务数",
            "unit": "Count/s",
            "description": "每秒事务处理数",
            "sub_namespace": "engine_monitor",
        },
        "replication_delay": {
            "name": "ReplicationDelay",
            "display_name": "主从延迟",
            "unit": "Seconds",
            "description": "主从复制延迟时间",
            "sub_namespace": "deploy_monitor_new",
        },
        "IOPSRate": {
            "name": "IOPSRate",
            "display_name": "IOPS",
            "unit": "Count/s",
            "description": "每秒IO次数",
            "sub_namespace": "resource_monitor_new",
        },
        "network_in": {
            "name": "NetworkReceiveThroughput",
            "display_name": "网络入流量",
            "unit": "Bytes/s",
            "description": "每秒网络接收字节数",
            "sub_namespace": "resource_monitor_new",
        },
        "network_out": {
            "name": "NetworkTransmitThroughput",
            "display_name": "网络出流量",
            "unit": "Bytes/s",
            "description": "每秒网络发送字节数",
            "sub_namespace": "resource_monitor_new",
        },
    }

    def __init__(
        self,
        ak: Optional[str] = None,
        sk: Optional[str] = None,
        region: str = "cn-shanghai",
    ):
        """
        初始化采集器

        Args:
            ak: Access Key ID
            sk: Secret Access Key
            region: 区域，默认cn-shanghai
        """
        self.ak = ak
        self.sk = sk
        self.region = region

        if not self.ak or not self.sk:
            raise ValueError("必须提供有效的访问凭证")

        # 初始化RDS MySQL客户端
        self._init_rds_client()

        # 初始化云监控客户端（用于GetMetricData）
        self._init_cloudmonitor_client()

    def _init_rds_client(self):
        """初始化RDS MySQL客户端"""
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = self.ak
        configuration.sk = self.sk
        configuration.region = self.region

        volcenginesdkcore.Configuration.set_default(configuration)
        self.rds_client = volcenginesdkrdsmysqlv2.RDSMYSQLV2Api(
            volcenginesdkcore.ApiClient(configuration)
        )

    def _init_cloudmonitor_client(self):
        """初始化云监控客户端"""
        configuration = volcenginesdkcore.Configuration()
        configuration.ak = self.ak
        configuration.sk = self.sk
        configuration.region = self.region

        volcenginesdkcore.Configuration.set_default(configuration)
        self.cloudmonitor_client = volcenginesdkcloudmonitor.CLOUDMONITORApi(
            volcenginesdkcore.ApiClient(configuration)
        )

    def get_instance_detail(self, instance_id: str) -> Dict[str, Any]:
        """
        获取实例详细信息（规格、版本、参数等）

        Args:
            instance_id: 实例ID

        Returns:
            实例详细信息字典
        """
        try:
            request = volcenginesdkrdsmysqlv2.DescribeDBInstanceDetailRequest(
                instance_id=instance_id
            )

            response = self.rds_client.describe_db_instance_detail(request)

            if hasattr(response, "basic_info") and response.basic_info:
                info = response.basic_info
                result = {
                    "instance_id": instance_id,
                    "instance_name": getattr(info, "instance_name", ""),
                    "instance_status": getattr(info, "instance_status", ""),
                    "db_engine": "MySQL",
                    "db_engine_version": getattr(info, "db_engine_version", ""),
                    "instance_type": getattr(info, "instance_type", ""),
                    "node_spec": getattr(info, "node_spec", ""),
                    "node_number": getattr(info, "node_number", 0),
                    "vcpu": getattr(info, "vcpu", 0),
                    "memory": getattr(info, "memory", 0),
                    "storage_space": getattr(info, "storage_space", 0),
                    "storage_type": getattr(info, "storage_type", ""),
                    "storage_use": getattr(info, "storage_use", 0),
                    "vpc_id": getattr(info, "vpc_id", ""),
                    "subnet_id": getattr(info, "subnet_id", ""),
                    "zone_id": getattr(info, "zone_id", ""),
                    "region_id": getattr(info, "region_id", self.region),
                    "create_time": getattr(info, "create_time", ""),
                    "update_time": getattr(info, "update_time", ""),
                    "project_name": getattr(info, "project_name", ""),
                    "tags": getattr(info, "tags", []),
                    "data_sync_mode": getattr(info, "data_sync_mode", ""),
                    "time_zone": getattr(info, "time_zone", ""),
                }

                # 提取计费信息
                if hasattr(response, "charge_detail") and response.charge_detail:
                    charge = response.charge_detail
                    result["charge_type"] = getattr(charge, "charge_type", "")

                return result

            return {"instance_id": instance_id, "error": "无法获取实例基本信息"}

        except ApiException as e:
            return {
                "instance_id": instance_id,
                "error": f"API调用失败: {e.status} - {e.reason}",
                "error_body": str(e.body) if hasattr(e, "body") else None,
            }
        except Exception as e:
            return {"instance_id": instance_id, "error": f"获取实例信息异常: {str(e)}"}

    def _call_get_metric_data(
        self,
        metric_name: str,
        instance_id: str,
        start_time: int,
        end_time: int,
        period: str = "1m",
        sub_namespace: str = "resource_monitor_new",
    ) -> Dict[str, Any]:
        """
        调用GetMetricData API获取监控数据

        基于文档: https://www.volcengine.com/docs/6408/105542

        Args:
            metric_name: 指标名称
            instance_id: 实例ID
            start_time: 开始时间（秒级时间戳）
            end_time: 结束时间（秒级时间戳）
            period: 聚合周期，支持 1m, 5m, 1h, 1d 等
            sub_namespace: 子命名空间

        Returns:
            监控数据
        """
        try:
            request = volcenginesdkcloudmonitor.GetMetricDataRequest(
                start_time=start_time,
                end_time=end_time,
                namespace=self.NAMESPACE,
                sub_namespace=sub_namespace,
                metric_name=metric_name,
                period=period,
                instances=[
                    volcenginesdkcloudmonitor.InstanceForGetMetricDataInput(
                        dimensions=[
                            volcenginesdkcloudmonitor.DimensionForGetMetricDataInput(
                                name="ResourceID", value=instance_id
                            )
                        ]
                    )
                ],
            )

            response = self.cloudmonitor_client.get_metric_data(request)
            return response

        except ApiException as e:
            return {
                "error": f"获取监控数据失败: {e.status} - {e.reason}",
                "metric_name": metric_name,
                "error_body": str(e.body) if hasattr(e, "body") else None,
            }
        except Exception as e:
            return {
                "error": f"获取监控数据失败: {str(e)}",
                "metric_name": metric_name,
                "error_type": type(e).__name__,
            }

    def _parse_metric_response(self, response) -> List[Dict[str, Any]]:
        """
        解析云监控API返回的response对象，提取干净的数据点

        Args:
            response: SDK返回的response对象

        Returns:
            按节点分组的数据列表，每组包含 node_name, dimensions, data_points
        """
        nodes = []
        try:
            # 获取 metric_data_results
            data_attr = getattr(response, "data", None)
            if data_attr is None:
                return nodes

            metric_data_results = getattr(data_attr, "metric_data_results", None)
            if not metric_data_results:
                return nodes

            for result in metric_data_results:
                node_info = {
                    "legend": getattr(result, "legend", ""),
                    "dimensions": {},
                    "data_points": [],
                }

                # 提取维度信息
                dims = getattr(result, "dimensions", [])
                if dims:
                    for dim in dims:
                        name = getattr(dim, "name", "")
                        value = getattr(dim, "value", "")
                        node_info["dimensions"][name] = value

                # 提取数据点，精简格式
                data_points = getattr(result, "data_points", [])
                if data_points:
                    for dp in data_points:
                        ts = getattr(dp, "timestamp", 0)
                        val = getattr(dp, "value", 0)
                        node_info["data_points"].append(
                            {
                                "ts": ts,
                                "time": (
                                    datetime.fromtimestamp(ts).strftime(
                                        "%Y-%m-%d %H:%M"
                                    )
                                    if ts
                                    else ""
                                ),
                                "value": round(val, 4) if val is not None else None,
                            }
                        )

                nodes.append(node_info)

        except Exception as e:
            nodes.append({"error": f"解析响应失败: {str(e)}"})

        return nodes

    def _build_node_summaries(
        self,
        parsed_nodes: List[Dict[str, Any]],
        *,
        period: str = "5m",
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        metric_key: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        为每个节点生成轻量统计摘要，便于多节点场景下优先比较节点差异。

        Args:
            parsed_nodes: `_parse_metric_response` 返回的节点列表

        Returns:
            节点摘要列表，每项包含 node、legend、data_point_count、min、max、avg、all_zero
        """
        node_summaries = []

        for node in parsed_nodes:
            values = [
                dp["value"]
                for dp in node.get("data_points", [])
                if dp.get("value") is not None
            ]

            all_zero = bool(values) and all(abs(value) < 1e-9 for value in values)
            dimensions = node.get("dimensions", {})
            summary = build_value_summary(values, period=period)
            evidence = build_metric_evidence(
                node.get("data_points", []),
                metric_key=metric_key,
                period=period,
                start_time=start_time,
                end_time=end_time,
            )

            node_summaries.append(
                {
                    "node": dimensions.get("Node", ""),
                    "legend": node.get("legend", ""),
                    **summary,
                    "evidence": evidence,
                    "all_zero": all_zero,
                }
            )

        return node_summaries

    def get_metric_data(
        self,
        instance_id: str,
        metric_key: str,
        start_time: datetime,
        end_time: datetime,
        period: str = "1m",
    ) -> Dict[str, Any]:
        """
        获取单个监控指标数据

        Args:
            instance_id: 实例ID
            metric_key: 指标键 (如 "cpu", "memory" 等)
            start_time: 开始时间
            end_time: 结束时间
            period: 聚合周期

        Returns:
            监控数据（已解析为干净的JSON结构）
        """
        if metric_key not in self.METRIC_DEFINITIONS:
            return {"error": f"不支持的指标: {metric_key}"}

        metric = self.METRIC_DEFINITIONS[metric_key]

        # 转换为秒级时间戳
        start_ts = int(start_time.timestamp())
        end_ts = int(end_time.timestamp())

        # 获取指标对应的sub_namespace
        sub_namespace = metric.get("sub_namespace", "resource_monitor_new")

        response = self._call_get_metric_data(
            metric_name=metric["name"],
            instance_id=instance_id,
            start_time=start_ts,
            end_time=end_ts,
            period=period,
            sub_namespace=sub_namespace,
        )

        # 如果返回的是错误字典，直接使用
        if isinstance(response, dict) and "error" in response:
            return {
                "metric_key": metric_key,
                "metric_name": metric["name"],
                "display_name": metric["display_name"],
                "unit": metric["unit"],
                "error": response["error"],
            }

        # 解析SDK response对象，提取干净的数据
        parsed_nodes = self._parse_metric_response(response)
        node_summaries = self._build_node_summaries(
            parsed_nodes,
            period=period,
            start_time=start_time,
            end_time=end_time,
            metric_key=metric_key,
        )

        result = {
            "metric_key": metric_key,
            "metric_name": metric["name"],
            "display_name": metric["display_name"],
            "unit": metric["unit"],
            "node_count": len(parsed_nodes),
            "node_summaries": node_summaries,
            "nodes": parsed_nodes,
        }

        # 计算汇总统计
        all_values = []
        all_points = []
        for node in parsed_nodes:
            for dp in node.get("data_points", []):
                if dp.get("value") is not None:
                    all_values.append(dp["value"])
                    all_points.append(
                        {
                            **dp,
                            "node": node.get("dimensions", {}).get("Node", ""),
                        }
                    )

        result["summary"] = build_value_summary(all_values, period=period)
        result["evidence"] = build_metric_evidence(
            all_points,
            metric_key=metric_key,
            period=period,
            start_time=start_time,
            end_time=end_time,
            series_count=max(len(parsed_nodes), 1),
        )

        return result

    def get_all_metrics(
        self,
        instance_id: str,
        start_time: datetime,
        end_time: datetime,
        period: str = "5m",
        metrics: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """
        获取所有（或指定的）监控指标数据

        Args:
            instance_id: 实例ID
            start_time: 开始时间
            end_time: 结束时间
            period: 聚合周期，默认5分钟
            metrics: 要获取的指标列表，默认获取全部

        Returns:
            所有监控数据汇总
        """
        if metrics is None:
            metrics = list(self.METRIC_DEFINITIONS.keys())

        results = {}
        for metric_key in metrics:
            results[metric_key] = self.get_metric_data(
                instance_id=instance_id,
                metric_key=metric_key,
                start_time=start_time,
                end_time=end_time,
                period=period,
            )
            # 避免触发API限流（1秒20次）
            time.sleep(0.1)

        return {
            "instance_id": instance_id,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "period": period,
            "metrics": results,
        }

    def get_comprehensive_info(
        self,
        instance_id: str,
        start_time: datetime,
        end_time: datetime,
        period: str = "5m",
    ) -> Dict[str, Any]:
        """
        获取实例综合信息（基础配置 + 监控数据），按指标分组返回

        Args:
            instance_id: 实例ID
            start_time: 监控数据开始时间
            end_time: 监控数据结束时间
            period: 监控数据聚合周期

        Returns:
            包含公共信息和按指标分组数据的字典:
            {
                "common": { collection_time, instance_id, time_range, instance_detail },
                "metrics": { "cpu": {...}, "memory": {...}, ... }
            }
        """
        common_info = {
            "collection_time": datetime.now().isoformat(),
            "instance_id": instance_id,
            "time_range": {
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
            },
            "instance_detail": self.get_instance_detail(instance_id),
        }

        # 获取核心监控指标
        core_metrics = [
            "cpu",
            "memory",
            "disk_util",
            "qps",
            "tps",
            "replication_delay",
            "IOPSRate",
            "network_in",
            "network_out",
        ]
        metrics_data = {}
        for metric_key in core_metrics:
            metric_result = self.get_metric_data(
                instance_id=instance_id,
                metric_key=metric_key,
                start_time=start_time,
                end_time=end_time,
                period=period,
            )
            metrics_data[metric_key] = metric_result
            # 避免触发API限流（1秒20次）
            time.sleep(0.1)

        return {
            "common": common_info,
            "metrics": metrics_data,
            "resource_meta": {
                "instance_id": instance_id,
                "time_range": {
                    "start": start_time.isoformat(),
                    "end": end_time.isoformat(),
                },
                "period": period,
            },
        }


def main():
    """主函数 - 演示用法"""
    import argparse

    load_runtime_env()
    default_output_dir = DEFAULT_OUTPUT_DIR

    parser = argparse.ArgumentParser(
        description="获取MySQL实例基础配置和监控信息",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 获取实例详情
  python get_instance_info.py --instance-id mysql-d4f6a32d4e06 --credential-ref peets_prod --action detail
  
  # 获取最近1小时的监控数据
  python get_instance_info.py --instance-id mysql-d4f6a32d4e06 --credential-ref peets_prod --action metrics --hours 1
  
  # 获取综合信息
  python get_instance_info.py --instance-id mysql-d4f6a32d4e06 --action all \\
      --credential-ref peets_prod \\
      --start "2026-02-07 00:00" --end "2026-02-07 12:00"
        """,
    )

    parser.add_argument("--instance-id", required=True, help="MySQL实例ID")
    parser.add_argument(
        "--ak",
        help="火山引擎访问密钥ID（Access Key）",
    )
    parser.add_argument(
        "--sk",
        help="火山引擎访问密钥Secret（Secret Key）",
    )
    parser.add_argument(
        "--credential-ref",
        help="凭证引用，映射到 backend/.env 中的 VOLC_CREDENTIAL_<REF>_AK/SK",
    )
    parser.add_argument(
        "--action",
        choices=["detail", "metrics", "all"],
        default="all",
        help="操作类型: detail=实例详情, metrics=监控数据, all=全部",
    )
    parser.add_argument("--start", help="开始时间 (YYYY-MM-DD HH:MM)")
    parser.add_argument("--end", help="结束时间 (YYYY-MM-DD HH:MM)")
    parser.add_argument(
        "--hours", type=int, default=1, help="查询最近N小时的数据（如未指定start/end）"
    )
    parser.add_argument(
        "--period", default="5m", help="监控数据聚合周期 (1m, 5m, 1h, 1d)"
    )
    parser.add_argument("--region", default="cn-shanghai", help="区域")
    parser.add_argument("--output", help="输出文件路径（JSON格式）")

    parser.add_argument(
        "--retention-days",
        type=non_negative_int,
        default=30,
        help="metric_data JSON retention window in days before auto cleanup",
    )
    parser.add_argument(
        "--skip-cleanup",
        action="store_true",
        help="skip deleting expired metric_data JSON files before collection",
    )

    args = parser.parse_args()
    output_dir = default_output_dir
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    default_base_name = f"{args.instance_id}_{args.action}_{timestamp}"

    if args.output:
        output_dir = os.path.dirname(args.output) or "."
        base_name = os.path.splitext(os.path.basename(args.output))[0]
    else:
        base_name = default_base_name

    os.makedirs(output_dir, exist_ok=True)

    if not ((args.ak and args.sk) or args.credential_ref):
        parser.error("必须提供 --credential-ref，或同时提供 --ak 和 --sk")

    # 解析时间范围
    if args.start and args.end:
        start_time = datetime.strptime(args.start, "%Y-%m-%d %H:%M")
        end_time = datetime.strptime(args.end, "%Y-%m-%d %H:%M")
    else:
        end_time = datetime.now()
        start_time = end_time - timedelta(hours=args.hours)

    if not args.skip_cleanup:
        cleanup_expired_metric_data(
            output_dir=output_dir,
            retention_days=args.retention_days,
        )

    resolved_ak, resolved_sk = resolve_credentials(
        ak=args.ak,
        sk=args.sk,
        credential_ref=args.credential_ref,
    )

    # 初始化采集器
    collector = MySQLInstanceInfoCollector(
        ak=resolved_ak,
        sk=resolved_sk,
        region=args.region,
    )

    # 执行操作
    if args.action == "detail":
        result = collector.get_instance_detail(args.instance_id)

    elif args.action == "metrics":
        result = collector.get_all_metrics(
            instance_id=args.instance_id,
            start_time=start_time,
            end_time=end_time,
            period=args.period,
        )
    else:  # all
        result = collector.get_comprehensive_info(
            instance_id=args.instance_id,
            start_time=start_time,
            end_time=end_time,
            period=args.period,
        )

    if args.action == "all":
        common_info = result["common"]
        resource_meta = result["resource_meta"]
        saved_files = []

        for metric_key, metric_data in result["metrics"].items():
            file_data = {
                "collection_time": common_info["collection_time"],
                "instance_id": common_info["instance_id"],
                "time_range": common_info["time_range"],
                "instance_detail": common_info["instance_detail"],
                "resource_metrics": {
                    "instance_id": resource_meta["instance_id"],
                    "time_range": resource_meta["time_range"],
                    "period": resource_meta["period"],
                    "metrics": {metric_key: metric_data},
                },
            }

            file_path = os.path.join(output_dir, f"{base_name}_{metric_key}.json")
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(file_data, f, ensure_ascii=False, indent=2, default=str)
            saved_files.append(file_path)
            print(f"已保存指标 [{metric_key}] 到: {file_path}")

        print(f"\n共生成 {len(saved_files)} 个文件")
    else:
        output_json = json.dumps(result, ensure_ascii=False, indent=2, default=str)
        file_path = (
            args.output
            if args.output
            else os.path.join(output_dir, f"{base_name}.json")
        )
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(output_json)
        print(f"结果已保存到: {file_path}")

    return result


if __name__ == "__main__":
    main()
