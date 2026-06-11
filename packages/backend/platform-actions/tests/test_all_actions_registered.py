from pathlib import Path


def test_all_11_action_definition_configs_exist() -> None:
    root = Path(__file__).resolve().parents[4] / "configs" / "kernel" / "action_definitions"
    assert len(list(root.glob("*.yaml"))) == 11
