import services.assistant_images as assistant_images


ONE_BY_ONE_PNG = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR"
    b"\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
    b"\x00\x00\x00\rIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe5'\xd4\xa2"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)


def test_extract_agent_browser_screenshot_path_uses_last_image_argument():
    command = 'agent-browser screenshot --selector ".chart" tmp/step-1.png'

    assert assistant_images.extract_agent_browser_screenshot_path(command) == "tmp/step-1.png"


def test_extract_agent_browser_screenshot_path_ignores_other_commands():
    assert (
        assistant_images.extract_agent_browser_screenshot_path(
            "agent-browser click '#submit'"
        )
        is None
    )


def test_persist_agent_browser_screenshot_asset_copies_file(monkeypatch, tmp_path):
    workspace_dir = tmp_path / "workspace"
    screenshot_path = workspace_dir / "tmp" / "step-1.png"
    screenshot_path.parent.mkdir(parents=True, exist_ok=True)
    screenshot_path.write_bytes(ONE_BY_ONE_PNG)

    monkeypatch.setattr(assistant_images, "ASSISTANT_IMAGE_ROOT", tmp_path / "assets")
    monkeypatch.setattr(assistant_images, "WORKSPACE_ROOT", workspace_dir)

    asset = assistant_images.persist_agent_browser_screenshot_asset(
        "conv-1",
        'agent-browser screenshot --selector ".chart" tmp/step-1.png',
    )

    assert asset == {
        "asset_path": "data/conversation_assets/conv-1/step-1.png",
        "asset_mime_type": "image/png",
        "asset_source": "agent-browser",
        "asset_alt": "Agent Browser screenshot",
        "asset_width": 1,
        "asset_height": 1,
    }
    stored_file = tmp_path / "assets" / "conv-1" / "step-1.png"
    assert stored_file.read_bytes() == ONE_BY_ONE_PNG
