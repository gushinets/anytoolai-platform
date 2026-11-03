from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


def test_dependabot_covers_workflows_and_composite_action_manifests() -> None:
    config = yaml.safe_load((ROOT / ".github" / "dependabot.yml").read_text(encoding="utf-8"))
    directories = {
        directory
        for update in config["updates"]
        if update["package-ecosystem"] == "github-actions"
        for directory in update.get("directories", [update.get("directory")])
    }
    required = {"/"}
    for pattern in ("action.yml", "action.yaml"):
        for path in (ROOT / ".github" / "actions").rglob(pattern):
            manifest = yaml.safe_load(path.read_text(encoding="utf-8"))
            if manifest["runs"]["using"] == "composite":
                required.add("/" + path.parent.relative_to(ROOT).as_posix())

    missing = required - directories
    assert not missing, f"Dependabot is missing GitHub Actions directories: {sorted(missing)}"
