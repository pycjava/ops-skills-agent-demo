import json

import pytest

from services.mcp_registry import McpRegistryService


@pytest.mark.asyncio
async def test_list_servers_returns_empty_when_mcp_config_file_is_missing(tmp_path):
    service = McpRegistryService(config_path=tmp_path / "mcp.json")

    records = await service.list_servers()

    assert records == []
    assert await service.load_config_text() == '{\n  "mcpServers": {}\n}\n'


@pytest.mark.asyncio
async def test_save_config_supports_cursor_style_servers_and_filters_connections_by_agent(
    tmp_path,
):
    service = McpRegistryService(config_path=tmp_path / "mcp.json")

    saved_text, records = await service.save_config_text(
        json.dumps(
            {
                "mcpServers": {
                    "weather": {
                        "url": "https://example.com/mcp",
                        "headers": {"Authorization": "Bearer token"},
                        "enabled": True,
                        "agentIds": ["general"],
                    },
                    "local-tools": {
                        "command": "python",
                        "args": ["server.py"],
                        "env": {"API_KEY": "secret"},
                        "enabled": True,
                        "agentIds": [],
                    },
                    "disabled": {
                        "url": "https://disabled.example.com/mcp",
                        "enabled": False,
                    },
                }
            }
        )
    )

    assert json.loads(saved_text) == {
        "mcpServers": {
            "weather": {
                "url": "https://example.com/mcp",
                "headers": {"Authorization": "Bearer token"},
                "enabled": True,
                "agentIds": ["general"],
            },
            "local-tools": {
                "command": "python",
                "args": ["server.py"],
                "env": {"API_KEY": "secret"},
                "enabled": True,
                "agentIds": [],
            },
            "disabled": {
                "url": "https://disabled.example.com/mcp",
                "enabled": False,
                "agentIds": [],
            },
        }
    }
    assert [record.name for record in records] == ["weather", "local-tools", "disabled"]

    general_connections = await service.get_agent_connections("general")
    assert general_connections == {
        "weather": {
            "transport": "http",
            "url": "https://example.com/mcp",
            "timeout": 15.0,
            "headers": {"Authorization": "Bearer token"},
        },
        "local-tools": {
            "transport": "stdio",
            "command": "python",
            "args": ["server.py"],
            "env": {"API_KEY": "secret"},
        },
    }

    ops_connections = await service.get_agent_connections("ops")
    assert ops_connections == {
        "local-tools": {
            "transport": "stdio",
            "command": "python",
            "args": ["server.py"],
            "env": {"API_KEY": "secret"},
        }
    }


@pytest.mark.asyncio
async def test_save_config_rejects_invalid_cursor_mcp_shape(tmp_path):
    service = McpRegistryService(config_path=tmp_path / "mcp.json")

    with pytest.raises(ValueError, match="mcpServers"):
        await service.save_config_text('{"mcpServers":[]}')

    with pytest.raises(ValueError, match="command or url"):
        await service.save_config_text('{"mcpServers":{"broken":{"enabled":true}}}')


@pytest.mark.asyncio
async def test_save_config_rejects_removed_legacy_agent_aliases(tmp_path):
    service = McpRegistryService(config_path=tmp_path / "mcp.json")

    with pytest.raises(ValueError, match="agent_id"):
        await service.save_config_text(
            json.dumps(
                {
                    "mcpServers": {
                        "legacy-router": {
                            "url": "https://example.com/mcp",
                            "enabled": True,
                            "agentIds": ["orchestrator", "router"],
                        }
                    }
                }
            )
        )
