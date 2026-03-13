from services.agent_event_identity import resolve_event_agent_id


def test_resolve_event_agent_id_prefers_explicit_agent_id():
    assert (
        resolve_event_agent_id({"agent_id": "dba"}, fallback_agent_id="router")
        == "dba"
    )


def test_resolve_event_agent_id_uses_langchain_agent_metadata():
    assert (
        resolve_event_agent_id(
            {"metadata": {"lc_agent_name": "ops"}},
            fallback_agent_id="router",
        )
        == "ops"
    )


def test_resolve_event_agent_id_falls_back_when_metadata_is_missing():
    assert (
        resolve_event_agent_id(
            {"metadata": {"lc_agent_name": "   "}},
            fallback_agent_id="router",
        )
        == "router"
    )
