from sqlalchemy import create_engine, inspect, text

from db.session import _bootstrap_sqlite_compat_columns


def test_bootstrap_sqlite_compat_columns_adds_message_attachment_snapshot_column():
    engine = create_engine("sqlite:///:memory:")

    with engine.begin() as connection:
        connection.execute(
            text(
                "CREATE TABLE conversations ("
                "id VARCHAR(36) PRIMARY KEY, "
                "title TEXT, "
                "source TEXT"
                ")"
            )
        )
        connection.execute(
            text(
                "CREATE TABLE messages ("
                "id VARCHAR(36) PRIMARY KEY, "
                "conversation_id VARCHAR(36), "
                "role VARCHAR(20), "
                "content TEXT, "
                "type VARCHAR(20)"
                ")"
            )
        )

        _bootstrap_sqlite_compat_columns(connection)

        inspector = inspect(connection)
        conversation_columns = {
            column["name"] for column in inspector.get_columns("conversations")
        }
        message_columns = {column["name"] for column in inspector.get_columns("messages")}

    assert "agent_id" in conversation_columns
    assert "agent_id" in message_columns
    assert "attachments_snapshot" in message_columns
