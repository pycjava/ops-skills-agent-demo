ROLE_DESCRIPTIONS = {
    "viewer": "Read-only access to conversations, tasks, notifications, MCP, and memory.",
    "operator": "Day-to-day operator access for chat, attachments, tasks, MCP, and memory.",
    "admin": "Full platform administration, including cloud credentials.",
}

PERMISSION_DESCRIPTIONS = {
    "conversations:read": "View conversations and message history.",
    "conversations:write": "Create and update conversations.",
    "conversations:delete": "Delete conversations.",
    "attachments:read": "View conversation attachments.",
    "attachments:write": "Upload conversation attachments.",
    "attachments:delete": "Delete conversation attachments.",
    "inspection_tasks:read": "View inspection tasks and runs.",
    "inspection_tasks:write": "Create and update inspection tasks.",
    "inspection_tasks:trigger": "Trigger inspection task execution.",
    "inspection_tasks:delete": "Delete inspection tasks.",
    "task_notifications:read": "View task notifications.",
    "task_notifications:update": "Mark task notifications as read.",
    "mcp_servers:read": "View MCP server configuration.",
    "mcp_servers:write": "Create and update MCP servers.",
    "mcp_servers:test": "Test MCP servers.",
    "mcp_servers:delete": "Delete MCP servers.",
    "cloud_credentials:read": "View cloud credential registry and resolution output.",
    "cloud_credentials:write": "Update cloud credential registry.",
    "cloud_credentials:delete": "Delete cloud credential entries.",
    "memories:read": "View shared memory files.",
    "memories:write": "Create and update shared memory files.",
    "memories:delete": "Delete shared memory files.",
    "agents:read": "View agent and skill catalog data.",
}

ROLE_PERMISSIONS = {
    "viewer": {
        "conversations:read",
        "attachments:read",
        "inspection_tasks:read",
        "task_notifications:read",
        "mcp_servers:read",
        "memories:read",
        "agents:read",
    },
    "operator": {
        "conversations:read",
        "conversations:write",
        "conversations:delete",
        "attachments:read",
        "attachments:write",
        "attachments:delete",
        "inspection_tasks:read",
        "inspection_tasks:write",
        "inspection_tasks:trigger",
        "inspection_tasks:delete",
        "task_notifications:read",
        "task_notifications:update",
        "mcp_servers:read",
        "mcp_servers:write",
        "mcp_servers:test",
        "mcp_servers:delete",
        "memories:read",
        "memories:write",
        "memories:delete",
        "agents:read",
    },
    "admin": set(PERMISSION_DESCRIPTIONS),
}


def all_permissions() -> list[str]:
    return sorted(PERMISSION_DESCRIPTIONS)

