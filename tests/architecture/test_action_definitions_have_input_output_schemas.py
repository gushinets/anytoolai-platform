from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
ACTION_ROOT = ROOT / "configs" / "kernel" / "action_definitions"


def test_action_definitions_have_input_output_schemas() -> None:
    files = list(ACTION_ROOT.glob("*.yaml"))
    assert len(files) == 11
    for path in files:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        assert data.get("input_schema_ref"), path
        assert data.get("output_schema_ref"), path
        assert data.get("executor") == "structured_llm", path
