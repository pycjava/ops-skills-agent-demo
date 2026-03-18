from __future__ import annotations

import re
import shutil
from pathlib import Path
from uuid import uuid4

from config import BASE_DIR, PROJECT_DIR


ASSISTANT_IMAGE_ROOT = (BASE_DIR / "data" / "conversation_assets").resolve()
WORKSPACE_ROOT = Path(PROJECT_DIR).resolve()
SUPPORTED_IMAGE_EXTENSIONS = frozenset({".png", ".jpg", ".jpeg", ".webp"})
MIME_TYPE_BY_EXTENSION = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".webp": "image/webp",
}
MAX_ASSISTANT_IMAGE_BYTES = 5 * 1024 * 1024
IMAGE_PATH_PATTERN = re.compile(
    r'"([^"\r\n]+\.(?:png|jpe?g|webp))"|'
    r"'([^'\r\n]+\.(?:png|jpe?g|webp))'|"
    r"([^\s\"'\r\n]+\.(?:png|jpe?g|webp))",
    re.IGNORECASE,
)


def extract_agent_browser_screenshot_path(command: str) -> str | None:
    normalized = str(command or "").strip()
    if not normalized:
        return None

    normalized_lower = normalized.lower()
    if "agent-browser" not in normalized_lower or "screenshot" not in normalized_lower:
        return None

    matches = [
        next(group for group in match.groups() if group)
        for match in IMAGE_PATH_PATTERN.finditer(normalized)
    ]
    return matches[-1] if matches else None


def build_assistant_image_asset_url(conversation_id: str, message_id: str) -> str:
    return f"/api/conversations/{conversation_id}/messages/{message_id}/asset"


def resolve_assistant_image_asset_path(relative_path: str) -> Path:
    normalized = Path(str(relative_path or "").strip().replace("\\", "/"))
    if normalized.parts[:2] != ("data", "conversation_assets"):
        raise FileNotFoundError("Invalid assistant image asset path")

    resolved = (ASSISTANT_IMAGE_ROOT / Path(*normalized.parts[2:])).resolve()
    resolved.relative_to(ASSISTANT_IMAGE_ROOT)
    return resolved


def persist_agent_browser_screenshot_asset(
    conversation_id: str,
    command: str,
) -> dict[str, object] | None:
    source_arg = extract_agent_browser_screenshot_path(command)
    if not source_arg:
        return None

    source_file = _resolve_workspace_image_path(source_arg)
    if source_file is None or not source_file.is_file():
        return None

    suffix = source_file.suffix.lower()
    if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
        return None

    if source_file.stat().st_size > MAX_ASSISTANT_IMAGE_BYTES:
        return None

    target_dir = ASSISTANT_IMAGE_ROOT / conversation_id
    target_dir.mkdir(parents=True, exist_ok=True)

    target_file = target_dir / source_file.name
    if target_file.exists():
        target_file = target_dir / f"{source_file.stem}-{uuid4().hex[:8]}{suffix}"

    shutil.copy2(source_file, target_file)
    width, height = _inspect_image_size(target_file)

    return {
        "asset_path": (
            Path("data") / "conversation_assets" / conversation_id / target_file.name
        ).as_posix(),
        "asset_mime_type": MIME_TYPE_BY_EXTENSION.get(suffix, "application/octet-stream"),
        "asset_source": "agent-browser",
        "asset_alt": "Agent Browser screenshot",
        "asset_width": width,
        "asset_height": height,
    }


def delete_all_assistant_image_assets(conversation_id: str) -> None:
    asset_dir = ASSISTANT_IMAGE_ROOT / conversation_id
    if asset_dir.exists():
        shutil.rmtree(asset_dir)


def _resolve_workspace_image_path(source_arg: str) -> Path | None:
    candidate = Path(source_arg)
    resolved = candidate if candidate.is_absolute() else (WORKSPACE_ROOT / candidate)
    try:
        normalized = resolved.resolve()
        normalized.relative_to(WORKSPACE_ROOT)
    except (OSError, ValueError):
        return None
    return normalized


def _inspect_image_size(path: Path) -> tuple[int | None, int | None]:
    try:
        data = path.read_bytes()
    except OSError:
        return None, None

    if data.startswith(b"\x89PNG\r\n\x1a\n") and len(data) >= 24:
        return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")

    if len(data) >= 30 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        if data[12:16] == b"VP8X":
            width = int.from_bytes(data[24:27] + b"\x00", "little") + 1
            height = int.from_bytes(data[27:30] + b"\x00", "little") + 1
            return width, height

    return None, None
