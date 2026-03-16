from __future__ import annotations

import shlex
from pathlib import Path


def test_backend_dockerfile_copy_sources_exist_in_build_context():
    dockerfile_path = Path(__file__).resolve().parents[1] / "Dockerfile"
    build_context = dockerfile_path.parent
    dockerfile_lines = dockerfile_path.read_text(encoding="utf-8").splitlines()

    missing_sources: list[str] = []

    for raw_line in dockerfile_lines:
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.upper().startswith("COPY "):
            continue

        parts = shlex.split(line)
        if len(parts) < 3:
            continue

        if any(part.startswith("--from=") for part in parts[1:]):
            continue

        payload = [part for part in parts[1:] if not part.startswith("--")]
        if len(payload) < 2:
            continue

        for source in payload[:-1]:
            if source == ".":
                continue
            if list(build_context.glob(source)):
                continue
            missing_sources.append(source)

    assert missing_sources == []
