from pathlib import Path


def test_backend_requirements_include_itsdangerous_for_session_middleware():
    requirements_path = Path(__file__).resolve().parents[1] / "requirements.txt"
    requirements = requirements_path.read_text(encoding="utf-8").splitlines()

    normalized = [
        line.strip().lower()
        for line in requirements
        if line.strip() and not line.strip().startswith("#")
    ]

    assert any(line.startswith("itsdangerous") for line in normalized)


def test_backend_requirements_include_chromadb_for_local_rag_index():
    requirements_path = Path(__file__).resolve().parents[1] / "requirements.txt"
    requirements = requirements_path.read_text(encoding="utf-8").splitlines()

    normalized = [
        line.strip().lower()
        for line in requirements
        if line.strip() and not line.strip().startswith("#")
    ]

    assert any(line.startswith("chromadb") for line in normalized)
