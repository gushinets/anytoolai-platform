from __future__ import annotations

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = ROOT / "infra" / "compose" / "docker-compose.yml"
PUBLIC_FRONTEND_ROOTS = (
    ROOT / "apps" / "web-mirror",
    ROOT / "packages" / "frontend",
    ROOT / "extensions",
)
FRONTEND_SOURCE_SUFFIXES = {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".json"}
FORBIDDEN_PUBLIC_FRONTEND_TOKENS = {
    "X-Atom-Lab-Access-Code",
    "/v1/atom-lab",
    "runtime_scope",
    "prompt_override",
    "model_override",
    "provider_policy_ref",
    "model_id",
}


def test_atom_lab_access_code_is_wired_only_to_platform_api() -> None:
    compose = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    services = compose["services"]

    api_environment = services["platform-api"]["environment"]
    assert api_environment["ANYTOOLAI_ATOM_LAB_ACCESS_CODE"] == (
        "${ANYTOOLAI_ATOM_LAB_ACCESS_CODE:-}"
    )
    for service_name, service in services.items():
        if service_name == "platform-api":
            continue
        assert "ANYTOOLAI_ATOM_LAB_ACCESS_CODE" not in service.get("environment", {})


def test_public_frontends_cannot_import_atom_lab_authority_or_overrides() -> None:
    offenders: list[str] = []
    for root in PUBLIC_FRONTEND_ROOTS:
        for path in root.rglob("*"):
            if (
                not path.is_file()
                or path.suffix not in FRONTEND_SOURCE_SUFFIXES
                or any(
                    part in {"node_modules", "dist", "build", ".next", "generated"}
                    for part in path.parts
                )
            ):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for token in FORBIDDEN_PUBLIC_FRONTEND_TOKENS:
                if token in text:
                    offenders.append(f"{path.relative_to(ROOT)} contains {token!r}")

    assert offenders == [], "public frontend Atom Lab boundary violations: " + ", ".join(offenders)


def test_atom_lab_shell_contains_no_embedded_registry_contracts() -> None:
    shell_root = (
        ROOT / "apps" / "platform-api" / "src" / "anytoolai_platform_api" / "static" / "atom_lab"
    )
    source = "\n".join(
        path.read_text(encoding="utf-8", errors="ignore")
        for path in shell_root.iterdir()
        if path.is_file()
    )
    assert "kernel.schemas." not in source
    assert "kernel_demo." not in source
    assert "prompt_ref" not in source
    assert "input_schema" not in source
    assert "output_schema" not in source
