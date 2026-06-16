from __future__ import annotations

from pathlib import Path
import shutil
import sys

import pytest
import yaml

REPO_ROOT = Path(__file__).resolve().parents[3]
PLATFORM_CORE_SRC = REPO_ROOT / "packages" / "backend" / "platform-core" / "src"
PLATFORM_API_SRC = REPO_ROOT / "apps" / "platform-api" / "src"

for src_path in (PLATFORM_CORE_SRC, PLATFORM_API_SRC):
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))

from anytoolai_platform_core.config.errors import RegistryLoadError
from anytoolai_platform_api.main import create_app


CONFIG_ROOT = REPO_ROOT / "configs" / "kernel"


def test_create_app_fails_before_serving_when_config_is_invalid(tmp_path: Path) -> None:
    config_root = tmp_path / "kernel"
    shutil.copytree(CONFIG_ROOT, config_root)

    scenario_path = config_root / "products" / "kernel_demo" / "scenarios.yaml"
    with scenario_path.open("r", encoding="utf-8") as handle:
        data = yaml.safe_load(handle) or {}

    data["scenarios"][0]["workflow_id"] = "kernel_demo.invalid_workflow_v1"

    with scenario_path.open("w", encoding="utf-8") as handle:
        yaml.safe_dump(data, handle, sort_keys=False)

    with pytest.raises(RegistryLoadError):
        create_app(config_root=config_root)
