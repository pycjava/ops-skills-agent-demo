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
        "avg": avg,
        "median": median,
        "weighted": round((avg + median) / 2, 4),
    }


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
    parsed_nodes = [
        {
            "legend": "node-a",
            "dimensions": {"Node": "node-a"},
            "data_points": [
                {"value": 1.0},
                {"value": 2.0},
                {"value": 100.0},
                {"value": None},
            ],
        },
        {
            "legend": "node-b",
            "dimensions": {"Node": "node-b"},
            "data_points": [
                {"value": 10.0},
                {"value": 20.0},
                {"value": 30.0},
            ],
        },
    ]

    node_summaries = collector._build_node_summaries(parsed_nodes)

    assert node_summaries[0] == {
        "node": "node-a",
        "legend": "node-a",
        **build_expected_summary([1.0, 2.0, 100.0]),
        "all_zero": False,
    }
    assert node_summaries[1] == {
        "node": "node-b",
        "legend": "node-b",
        **build_expected_summary([10.0, 20.0, 30.0]),
        "all_zero": False,
    }


def test_get_metric_data_summary_includes_median_and_weighted(monkeypatch):
    module = load_get_instance_info_module(monkeypatch)
    collector = module.MySQLInstanceInfoCollector(ak="ak", sk="sk", region="cn-shanghai")
    parsed_nodes = [
        {
            "legend": "node-a",
            "dimensions": {"Node": "node-a"},
            "data_points": [{"value": 1.0}, {"value": 2.0}, {"value": 100.0}],
        },
        {
            "legend": "node-b",
            "dimensions": {"Node": "node-b"},
            "data_points": [{"value": 10.0}, {"value": 20.0}, {"value": 30.0}],
        },
    ]

    monkeypatch.setattr(collector, "_call_get_metric_data", lambda **_kwargs: object())
    monkeypatch.setattr(collector, "_parse_metric_response", lambda _response: parsed_nodes)

    result = collector.get_metric_data(
        instance_id="mysql-demo",
        metric_key="cpu",
        start_time=datetime(2026, 3, 10, 0, 0, 0),
        end_time=datetime(2026, 3, 11, 0, 0, 0),
        period="1h",
    )

    assert result["summary"] == build_expected_summary([1.0, 2.0, 100.0, 10.0, 20.0, 30.0])
    assert result["node_summaries"][0]["median"] == build_expected_summary([1.0, 2.0, 100.0])["median"]
    assert result["node_summaries"][0]["weighted"] == build_expected_summary([1.0, 2.0, 100.0])["weighted"]


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
