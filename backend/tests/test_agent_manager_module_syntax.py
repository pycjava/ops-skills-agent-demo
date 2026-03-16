from pathlib import Path
import py_compile


def test_agent_manager_module_compiles():
    module_path = Path(__file__).resolve().parents[1] / "agent_manager.py"

    py_compile.compile(str(module_path), doraise=True)
