import importlib.util
import os
import statistics
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPT_PATH = (
    BACKEND_DIR
    / "skills"
    / "volcengine-rds-health-analyzer"
    / "scripts"
    / "get_instance_info.py"
)


def load_get_instance_info_module(monkeypatch):
    core_module = types.ModuleType("volcenginesdkcore")

    class DummyConfiguration:
        def __init__(self):
            self.ak = None
            self.sk = None
            self.region = None

        @classmethod
        def set_default(cls, _config):
            return None

    core_module.Configuration = DummyConfiguration
    core_module.ApiClient = lambda _config: object()

    rest_module = types.ModuleType("volcenginesdkcore.rest")

    class DummyApiException(Exception):
        pass

    rest_module.ApiException = DummyApiException

    rds_module = types.ModuleType("volcenginesdkrdsmysqlv2")

    class DummyRdsApi:
        def __init__(self, _client):
            self.client = _client

    rds_module.RDSMYSQLV2Api = DummyRdsApi

    cloudmonitor_module = types.ModuleType("volcenginesdkcloudmonitor")

    class DummyCloudMonitorApi:
        def __init__(self, _client):
            self.client = _client

    cloudmonitor_module.CLOUDMONITORApi = DummyCloudMonitorApi

    monkeypatch.setitem(sys.modules, "volcenginesdkcore", core_module)
    monkeypatch.setitem(sys.modules, "volcenginesdkcore.rest", rest_module)
    monkeypatch.setitem(sys.modules, "volcenginesdkrdsmysqlv2", rds_module)
    monkeypatch.setitem(sys.modules, "volcenginesdkcloudmonitor", cloudmonitor_module)

    spec = importlib.util.spec_from_file_location(
        "test_get_instance_info_cleanup_module", SCRIPT_PATH
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def write_file(path: Path, content: str = "{}") -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def set_mtime(path: Path, value: datetime) -> None:
    ts = value.timestamp()
    os.utime(path, (ts, ts))


def build_expected_summary(values):
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


def build_data_points(values, start_time, interval_minutes: int = 5):
    data_points = []
    for index, value in enumerate(values):
        point_time = start_time + timedelta(minutes=index * interval_minutes)
        data_points.append(
            {
                "ts": int(point_time.timestamp()),
                "time": point_time.strftime("%Y-%m-%d %H:%M"),
                "value": value,
            }
        )
    return data_points


def test_cleanup_expired_metric_data_deletes_only_stale_json(monkeypatch, tmp_path):
    module = load_get_instance_info_module(monkeypatch)
    now = datetime(2026, 3, 11, 12, 0, 0)

    stale_json = write_file(tmp_path / "stale.json")
    fresh_json = write_file(tmp_path / "fresh.json")
    ignored_text = write_file(tmp_path / "notes.txt", "keep")

    set_mtime(stale_json, now - timedelta(days=31))
    set_mtime(fresh_json, now - timedelta(days=5))
    set_mtime(ignored_text, now - timedelta(days=60))

    summary = module.cleanup_expired_metric_data(
        output_dir=tmp_path,
        retention_days=30,
        now=now,
    )

    assert summary == {"scanned": 2, "deleted": 1, "failed": 0}
    assert not stale_json.exists()
    assert fresh_json.exists()
    assert ignored_text.exists()


def test_cleanup_expired_metric_data_warns_and_continues_on_delete_failure(
    monkeypatch, tmp_path
):
    module = load_get_instance_info_module(monkeypatch)
    now = datetime(2026, 3, 11, 12, 0, 0)

    failed_json = write_file(tmp_path / "failed.json")
    deleted_json = write_file(tmp_path / "deleted.json")

    set_mtime(failed_json, now - timedelta(days=45))
    set_mtime(deleted_json, now - timedelta(days=45))

    original_remove = module.os.remove
    messages = []

    def fake_remove(path):
        if Path(path) == failed_json:
            raise PermissionError("locked")
        return original_remove(path)

    monkeypatch.setattr(module.os, "remove", fake_remove)

    summary = module.cleanup_expired_metric_data(
        output_dir=tmp_path,
        retention_days=30,
        now=now,
        printer=messages.append,
    )

    assert summary == {"scanned": 2, "deleted": 1, "failed": 1}
    assert failed_json.exists()
    assert not deleted_json.exists()
    assert any("failed.json" in message for message in messages)


def test_build_arg_parser_supports_metric_data_retention_flags(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)

    parser = module.build_arg_parser()

    default_args = parser.parse_args(
        ["--instance-id", "mysql-demo", "--credential-ref", "demo"]
    )
    assert default_args.retention_days == 30
    assert default_args.skip_cleanup is False

    explicit_args = parser.parse_args(
        [
            "--instance-id",
            "mysql-demo",
            "--credential-ref",
            "demo",
            "--retention-days",
            "7",
            "--skip-cleanup",
        ]
    )
    assert explicit_args.retention_days == 7
    assert explicit_args.skip_cleanup is True


def test_build_node_summaries_include_median_and_weighted(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    collector = module.MySQLInstanceInfoCollector(ak="ak", sk="sk", region="cn-shanghai")
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    parsed_nodes = [
        {
            "legend": "node-a",
            "dimensions": {"Node": "node-a"},
            "data_points": build_data_points([1.0, 2.0, 100.0, 2.0, 1.0], start_time),
        },
        {
            "legend": "node-b",
            "dimensions": {"Node": "node-b"},
            "data_points": build_data_points([10.0, 20.0, 30.0, 40.0, 50.0], start_time),
        },
    ]

    node_summaries = collector._build_node_summaries(
        parsed_nodes,
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    assert node_summaries[0]["node"] == "node-a"
    assert node_summaries[0]["legend"] == "node-a"
    assert node_summaries[0]["range"] == 99.0
    assert "spike_detection" not in node_summaries[0]
    assert node_summaries[0]["evidence"]["source_period"] == "5m"
    assert node_summaries[0]["evidence"]["coverage"]["expected_point_count"] == 5
    assert node_summaries[0]["evidence"]["spikes"]["sliding_mad"]["window_size"] == 5
    assert node_summaries[0]["evidence"]["spikes"]["sliding_mad"]["spike_count"] == 1
    assert node_summaries[0]["evidence"]["spikes"]["risk_tier"] == "low"
    assert node_summaries[0]["all_zero"] is False

    assert node_summaries[1]["node"] == "node-b"
    assert node_summaries[1]["legend"] == "node-b"
    assert node_summaries[1]["range"] == 40.0
    assert node_summaries[1]["evidence"]["distribution"]["p95"] == 50.0
    assert node_summaries[1]["evidence"]["trend"]["direction"] == "up"
    assert node_summaries[1]["evidence"]["spikes"]["sliding_mad"]["spike_count"] == 0
    assert node_summaries[1]["evidence"]["spikes"]["risk_tier"] == "none"
    assert node_summaries[1]["all_zero"] is False


def test_get_metric_data_summary_includes_median_and_weighted(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    collector = module.MySQLInstanceInfoCollector(ak="ak", sk="sk", region="cn-shanghai")
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    parsed_nodes = [
        {
            "legend": "node-a",
            "dimensions": {"Node": "node-a"},
            "data_points": build_data_points([10.0, 10.0, 10.0, 100.0, 10.0], start_time),
        },
        {
            "legend": "node-b",
            "dimensions": {"Node": "node-b"},
            "data_points": build_data_points([5.0, 10.0, 15.0, 20.0, 25.0], start_time),
        },
    ]

    monkeypatch.setattr(collector, "_call_get_metric_data", lambda **_kwargs: object())
    monkeypatch.setattr(collector, "_parse_metric_response", lambda _response: parsed_nodes)

    result = collector.get_metric_data(
        instance_id="mysql-demo",
        metric_key="cpu",
        start_time=start_time,
        end_time=end_time,
        period="5m",
    )

    expected_summary = build_expected_summary(
        [10.0, 10.0, 10.0, 100.0, 10.0, 5.0, 10.0, 15.0, 20.0, 25.0]
    )
    for key, value in expected_summary.items():
        assert result["summary"][key] == value
    assert "spike_detection" not in result["summary"]
    assert result["evidence"]["source_point_count"] == 10
    assert result["evidence"]["source_period"] == "5m"
    assert result["evidence"]["coverage"]["expected_point_count"] == 10
    assert result["evidence"]["coverage"]["actual_point_count"] == 10
    assert result["evidence"]["distribution"]["p95"] == 100.0
    assert result["evidence"]["spikes"]["sliding_mad"]["window_size"] == 5
    assert result["evidence"]["spikes"]["sliding_mad"]["spike_count"] == 1
    assert result["evidence"]["spikes"]["sliding_mad"]["top_spikes"][0]["node"] == "node-a"
    assert result["evidence"]["spikes"]["sliding_mad"]["top_spikes"][0]["time"] == "2026-03-10 00:15"
    assert result["evidence"]["spikes"]["risk_tier"] == "high"
    assert result["node_summaries"][0]["median"] == build_expected_summary([10.0, 10.0, 10.0, 100.0, 10.0])["median"]
    assert result["node_summaries"][0]["weighted"] == build_expected_summary([10.0, 10.0, 10.0, 100.0, 10.0])["weighted"]
    assert result["node_summaries"][0]["evidence"]["spikes"]["sliding_mad"]["spike_count"] == 1
    assert result["node_summaries"][0]["evidence"]["spikes"]["risk_tier"] == "high"


def test_build_metric_evidence_includes_distribution_coverage_and_trend(
    monkeypatch,
):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    data_points = build_data_points([10.0, 20.0, 30.0, 40.0, 50.0], start_time)

    evidence = module.build_metric_evidence(
        data_points,
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    assert evidence["source_point_count"] == 5
    assert evidence["source_period"] == "5m"
    assert evidence["window"]["start"] == start_time.isoformat()
    assert evidence["window"]["end"] == end_time.isoformat()
    assert evidence["coverage"]["expected_point_count"] == 5
    assert evidence["coverage"]["actual_point_count"] == 5
    assert evidence["coverage"]["missing_point_count"] == 0
    assert evidence["coverage"]["coverage_ratio"] == 1.0
    assert evidence["distribution"]["min"] == 10.0
    assert evidence["distribution"]["p95"] == 50.0
    assert evidence["distribution"]["p99"] == 50.0
    assert evidence["pressure"]["high_percentile"]["level"] == "low"
    assert evidence["pressure"]["high_percentile"]["p95_to_median_ratio"] == 1.6667
    assert evidence["variability"]["stddev"] > 0.0
    assert evidence["variability"]["cv"] > 0.0
    assert evidence["trend"]["direction"] == "up"
    assert evidence["recent_trend"]["direction"] == "up"
    assert evidence["recent_trend"]["sample_size"] == 5
    assert evidence["spikes"]["sliding_mad"]["spike_count"] == 0
    assert evidence["spikes"]["risk_tier"] == "none"


def test_build_metric_evidence_marks_low_absolute_cpu_spike_as_low_risk(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    data_points = build_data_points([10.0, 10.0, 10.0, 65.0, 10.0], start_time)

    evidence = module.build_metric_evidence(
        data_points,
        metric_key="cpu",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    assert evidence["spikes"]["sliding_mad"]["spike_count"] == 1
    assert evidence["spikes"]["risk_tier"] == "low"
    assert "absolute" in evidence["spikes"]["risk_reason"]


def test_build_metric_evidence_marks_high_absolute_cpu_spike_as_high_risk(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    data_points = build_data_points([10.0, 10.0, 10.0, 70.0, 10.0], start_time)

    evidence = module.build_metric_evidence(
        data_points,
        metric_key="cpu",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    assert evidence["spikes"]["sliding_mad"]["spike_count"] == 1
    assert evidence["spikes"]["risk_tier"] == "high"
    assert "70" in evidence["spikes"]["risk_reason"]


def test_build_metric_evidence_keeps_qps_spikes_as_low_risk_without_capacity_model(
    monkeypatch,
):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    data_points = build_data_points([10.0, 10.0, 10.0, 1000.0, 10.0], start_time)

    evidence = module.build_metric_evidence(
        data_points,
        metric_key="qps",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    assert evidence["spikes"]["sliding_mad"]["spike_count"] == 1
    assert evidence["spikes"]["risk_tier"] == "low"
    assert "capacity" in evidence["spikes"]["risk_reason"]


def test_build_metric_evidence_promotes_qps_spikes_to_high_risk_with_heuristics(
    monkeypatch,
):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 40, 0)
    data_points = build_data_points(
        [10.0, 10.0, 100.0, 10.0, 10.0, 100.0, 10.0, 10.0, 100.0],
        start_time,
    )

    evidence = module.build_metric_evidence(
        data_points,
        metric_key="qps",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    assert evidence["spikes"]["sliding_mad"]["spike_count"] >= 2
    assert evidence["pressure"]["high_percentile"]["level"] == "high"
    assert evidence["spikes"]["risk_tier"] == "high"
    assert "p95" in evidence["spikes"]["risk_reason"]
    assert "spike_ratio" in evidence["spikes"]["risk_reason"]


def test_build_metric_evidence_marks_sustained_cpu_pressure_without_spikes(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    data_points = build_data_points([72.0, 74.0, 76.0, 78.0, 80.0], start_time)

    evidence = module.build_metric_evidence(
        data_points,
        metric_key="cpu",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    assert evidence["spikes"]["risk_tier"] == "none"
    assert evidence["pressure"]["level"] == "high"
    assert "median" in evidence["pressure"]["drivers"]
    assert "p95" in evidence["pressure"]["drivers"]


def test_build_metric_evidence_identifies_stable_qps_saturation(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 40, 0)
    data_points = build_data_points(
        [80.0, 82.0, 81.0, 83.0, 82.0, 84.0, 85.0, 84.0, 83.0],
        start_time,
    )

    evidence = module.build_metric_evidence(
        data_points,
        metric_key="qps",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    assert evidence["spikes"]["risk_tier"] == "none"
    assert evidence["saturation"]["level"] == "medium"
    assert "plateau" in evidence["saturation"]["reason"]


def test_build_metric_correlation_summary_identifies_compute_pressure(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 40, 0)

    cpu_evidence = module.build_metric_evidence(
        build_data_points([72.0, 74.0, 76.0, 78.0, 80.0, 79.0, 77.0, 76.0, 78.0], start_time),
        metric_key="cpu",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )
    qps_evidence = module.build_metric_evidence(
        build_data_points([80.0, 82.0, 81.0, 83.0, 82.0, 84.0, 85.0, 84.0, 83.0], start_time),
        metric_key="qps",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )
    tps_evidence = module.build_metric_evidence(
        build_data_points([25.0, 26.0, 27.0, 26.0, 25.0, 27.0, 28.0, 27.0, 26.0], start_time),
        metric_key="tps",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )

    correlation_summary = module.build_metric_correlation_summary(
        {
            "cpu": {"evidence": cpu_evidence},
            "memory": {"evidence": module.build_metric_evidence(build_data_points([40.0] * 9, start_time), metric_key="memory", period="5m", start_time=start_time, end_time=end_time)},
            "disk_util": {"evidence": module.build_metric_evidence(build_data_points([45.0] * 9, start_time), metric_key="disk_util", period="5m", start_time=start_time, end_time=end_time)},
            "qps": {"evidence": qps_evidence},
            "tps": {"evidence": tps_evidence},
            "replication_delay": {"evidence": module.build_metric_evidence(build_data_points([0.0] * 9, start_time), metric_key="replication_delay", period="5m", start_time=start_time, end_time=end_time)},
            "IOPSRate": {"evidence": module.build_metric_evidence(build_data_points([40.0] * 9, start_time), metric_key="IOPSRate", period="5m", start_time=start_time, end_time=end_time)},
            "network_in": {"evidence": module.build_metric_evidence(build_data_points([4096.0] * 9, start_time), metric_key="network_in", period="5m", start_time=start_time, end_time=end_time)},
            "network_out": {"evidence": module.build_metric_evidence(build_data_points([4096.0] * 9, start_time), metric_key="network_out", period="5m", start_time=start_time, end_time=end_time)},
        }
    )

    assert correlation_summary["top_signal"]["category"] == "compute_pressure"
    assert correlation_summary["top_signal"]["level"] == "high"


def test_summarize_window_alignment_classifies_newly_active_issue(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)

    summary = module.summarize_window_alignment(
        {"spikes": {"risk_tier": "none"}},
        recent3d_evidence={"spikes": {"risk_tier": "none"}},
        recent24h_evidence={"spikes": {"risk_tier": "high"}},
    )

    assert summary["current_status"] == "newly_active"
    assert summary["window_alignment"] == "main_normal_recent3d_normal_recent24h_abnormal"


def test_compute_balanced_resource_score_penalizes_high_p95_even_with_low_avg(
    monkeypatch,
):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    data_points = build_data_points([10.0, 10.0, 10.0, 10.0, 75.0], start_time)

    summary = module.build_value_summary([dp["value"] for dp in data_points], period="5m")
    evidence = module.build_metric_evidence(
        data_points,
        metric_key="cpu",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )
    score = module.compute_balanced_resource_score("cpu", summary, evidence)

    assert score["score"] == 15
    assert "p95" in score["drivers"]
    assert "risk_tier" in score["drivers"]


def test_compute_balanced_resource_score_penalizes_sustained_pressure_without_spike(
    monkeypatch,
):
    module = load_get_instance_info_module(monkeypatch)
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 0, 20, 0)
    data_points = build_data_points([72.0, 74.0, 76.0, 78.0, 80.0], start_time)

    summary = module.build_value_summary([dp["value"] for dp in data_points], period="5m")
    evidence = module.build_metric_evidence(
        data_points,
        metric_key="cpu",
        period="5m",
        start_time=start_time,
        end_time=end_time,
    )
    score = module.compute_balanced_resource_score("cpu", summary, evidence)

    assert "pressure" in score["drivers"]
    assert "risk_tier" not in score["drivers"]
    assert score["score"] == 5


def test_classify_resource_pressure_marks_single_threshold_breach_as_medium(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)

    result = module.classify_resource_pressure(
        "cpu",
        {
            "avg": 55.0,
            "median": 55.0,
            "p95": 72.0,
        },
    )

    assert result["level"] == "medium"
    assert result["drivers"] == ["p95"]
    assert "warning" in result["reason"]


def test_get_all_metrics_defaults_to_default_core_metrics(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    collector = module.MySQLInstanceInfoCollector(ak="ak", sk="sk", region="cn-shanghai")
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 1, 0, 0)
    captured_metric_keys = []

    def fake_get_metric_data(**kwargs):
        captured_metric_keys.append(kwargs["metric_key"])
        return {"metric_key": kwargs["metric_key"], "evidence": {}, "summary": {}}

    monkeypatch.setattr(collector, "get_metric_data", fake_get_metric_data)
    monkeypatch.setattr(module.time, "sleep", lambda _seconds: None)
    monkeypatch.setattr(
        module,
        "build_metric_correlation_summary",
        lambda metrics_data: {"signals": [], "top_signal": None, "metric_keys": list(metrics_data.keys())},
    )

    result = collector.get_all_metrics(
        instance_id="mysql-demo",
        start_time=start_time,
        end_time=end_time,
        period="5m",
    )

    assert captured_metric_keys == module.DEFAULT_CORE_METRICS
    assert list(result["metrics"].keys()) == module.DEFAULT_CORE_METRICS


def test_get_comprehensive_info_reuses_default_core_metrics_collection(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    collector = module.MySQLInstanceInfoCollector(ak="ak", sk="sk", region="cn-shanghai")
    start_time = datetime(2026, 3, 10, 0, 0, 0)
    end_time = datetime(2026, 3, 10, 1, 0, 0)
    captured_metrics_argument = {}

    monkeypatch.setattr(
        collector,
        "get_instance_detail",
        lambda instance_id: {"instance_id": instance_id, "status": "ok"},
    )

    def fake_get_all_metrics(**kwargs):
        captured_metrics_argument["metrics"] = kwargs["metrics"]
        return {
            "instance_id": kwargs["instance_id"],
            "time_range": {
                "start": kwargs["start_time"].isoformat(),
                "end": kwargs["end_time"].isoformat(),
            },
            "period": kwargs["period"],
            "metrics": {metric_key: {"metric_key": metric_key} for metric_key in kwargs["metrics"]},
            "correlation_summary": {"signals": [], "top_signal": None},
        }

    monkeypatch.setattr(collector, "get_all_metrics", fake_get_all_metrics)

    result = collector.get_comprehensive_info(
        instance_id="mysql-demo",
        start_time=start_time,
        end_time=end_time,
        period="5m",
    )

    assert captured_metrics_argument["metrics"] == module.DEFAULT_CORE_METRICS
    assert list(result["metrics"].keys()) == module.DEFAULT_CORE_METRICS


def test_main_cleans_expired_metric_files_before_writing_output(
    monkeypatch, tmp_path
):
    module = load_get_instance_info_module(monkeypatch)
    now = datetime(2026, 3, 11, 12, 0, 0)

    stale_json = write_file(tmp_path / "old_snapshot.json")
    set_mtime(stale_json, now - timedelta(days=45))

    class FakeCollector:
        def __init__(self, ak, sk, region):
            self.ak = ak
            self.sk = sk
            self.region = region

        def get_instance_detail(self, instance_id):
            return {"instance_id": instance_id, "status": "ok"}

    class FrozenDatetime:
        @staticmethod
        def now():
            return now

        @staticmethod
        def fromtimestamp(value):
            return datetime.fromtimestamp(value)

        @staticmethod
        def strptime(value, fmt):
            return datetime.strptime(value, fmt)

    monkeypatch.setattr(module, "MySQLInstanceInfoCollector", FakeCollector)
    monkeypatch.setattr(module, "resolve_credentials", lambda **_kwargs: ("ak", "sk"))
    monkeypatch.setattr(module, "datetime", FrozenDatetime)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "get_instance_info.py",
            "--instance-id",
            "mysql-demo",
            "--credential-ref",
            "demo",
            "--action",
            "detail",
            "--output",
            str(tmp_path / "instance_data.json"),
        ],
    )

    result = module.main()

    assert result == {"instance_id": "mysql-demo", "status": "ok"}
    assert not stale_json.exists()
    assert (tmp_path / "instance_data.json").exists()
