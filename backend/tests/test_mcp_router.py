import sys
import types
from types import SimpleNamespace

from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.routers import mcp as mcp_router
from auth.config import get_auth_settings
from services.mcp_registry import McpRegistryService


def create_test_client(tmp_path, monkeypatch):
    app = FastAPI()
    monkeypatch.setenv("AUTH_ENABLED", "false")
    get_auth_settings.cache_clear()
    mcp_router.service = McpRegistryService(config_path=tmp_path / "mcp.json")

    async def fake_invalidate_runtime_cache():
        return None

    monkeypatch.setattr(
        mcp_router,
        "invalidate_runtime_cache",
        fake_invalidate_runtime_cache,
    )
    app.include_router(mcp_router.router)
    return TestClient(app)


def test_get_mcp_config_returns_default_template_when_file_is_missing(
    tmp_path, monkeypatch
):
    client = create_test_client(tmp_path, monkeypatch)

    response = client.get("/api/mcp/config")

    assert response.status_code == 200
    assert response.json() == {
        "config_text": '{\n  "mcpServers": {}\n}\n',
        "servers": [],
    }


def test_put_mcp_config_saves_cursor_style_document(tmp_path, monkeypatch):
    client = create_test_client(tmp_path, monkeypatch)

    response = client.put(
        "/api/mcp/config",
        json={
            "config_text": (
                '{'
                '"mcpServers":{'
                '"weather":{"url":"https://example.com/mcp","enabled":true,"agentIds":["general"]}'
                "}"
                "}"
            )
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["config_text"] == (
        '{\n'
        '  "mcpServers": {\n'
        '    "weather": {\n'
        '      "url": "https://example.com/mcp",\n'
        '      "enabled": true,\n'
        '      "agentIds": [\n'
        '        "general"\n'
        "      ]\n"
        "    }\n"
        "  }\n"
        "}\n"
    )
    assert payload["servers"] == [
        {
            "id": "weather",
            "name": "weather",
            "transport": "http",
            "url": "https://example.com/mcp",
            "command": None,
            "args": [],
            "env": None,
            "has_env": False,
            "env_keys": [],
            "enabled": True,
            "agent_ids": ["general"],
            "has_headers": False,
            "header_keys": [],
            "last_test_status": "untested",
            "last_tested_at": None,
            "last_error": None,
            "last_tools": [],
        }
    ]


def test_test_mcp_server_uses_server_name_from_mcp_config(tmp_path, monkeypatch):
    client = create_test_client(tmp_path, monkeypatch)
    save_response = client.put(
        "/api/mcp/config",
        json={
            "config_text": (
                '{'
                '"mcpServers":{'
                '"weather":{"url":"https://example.com/mcp","enabled":true}'
                "}"
                "}"
            )
        },
    )
    assert save_response.status_code == 200

    class FakeMultiServerMCPClient:
        def __init__(self, connections, tool_name_prefix):
            self.connections = connections
            self.tool_name_prefix = tool_name_prefix

        async def get_tools(self, *, server_name=None):
            assert server_name == "weather"
            assert self.connections["weather"]["url"] == "https://example.com/mcp"
            return [SimpleNamespace(name="forecast", description="Show forecast")]

    if "langchain_mcp_adapters" not in sys.modules:
        adapters_module = types.ModuleType("langchain_mcp_adapters")
        adapters_module.__path__ = []
        sys.modules["langchain_mcp_adapters"] = adapters_module
    if "langchain_mcp_adapters.client" not in sys.modules:
        client_module = types.ModuleType("langchain_mcp_adapters.client")
        client_module.MultiServerMCPClient = FakeMultiServerMCPClient
        sys.modules["langchain_mcp_adapters.client"] = client_module
    sys.modules["langchain_mcp_adapters"].client = sys.modules["langchain_mcp_adapters.client"]

    monkeypatch.setattr(
        "langchain_mcp_adapters.client.MultiServerMCPClient",
        FakeMultiServerMCPClient,
    )

    response = client.post("/api/mcp/servers/weather/test")

    assert response.status_code == 200
    payload = response.json()
    assert payload["ok"] is True
    assert payload["error"] is None
    assert payload["tools"] == [{"name": "forecast", "description": "Show forecast"}]
    assert payload["server"]["name"] == "weather"
    assert payload["server"]["last_test_status"] == "ok"
