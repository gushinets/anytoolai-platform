"""Config registry errors with structured fields for precise diagnostics."""

from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from anytoolai_platform_core.common.errors import PlatformError


@dataclass
class ConfigError(PlatformError):
    """Structured config error with file path and reference context."""

    code: str
    message: str
    file_path: Path | None = None
    config_id: str | None = None
    ref_type: str | None = None
    ref_value: str | None = None

    def __init__(
        self,
        code: str,
        message: str,
        file_path: Path | None = None,
        config_id: str | None = None,
        ref_type: str | None = None,
        ref_value: str | None = None,
    ) -> None:
        object.__setattr__(self, "code", code)
        object.__setattr__(self, "message", message)
        object.__setattr__(self, "file_path", file_path)
        object.__setattr__(self, "config_id", config_id)
        object.__setattr__(self, "ref_type", ref_type)
        object.__setattr__(self, "ref_value", ref_value)
        Exception.__init__(self, message)

    def __str__(self) -> str:
        """Format error with full context."""
        parts = [f"[{self.code}] {self.message}"]
        if self.file_path:
            parts.append(f"  File: {self.file_path}")
        if self.config_id:
            parts.append(f"  Config ID: {self.config_id}")
        if self.ref_type is not None and self.ref_value is not None:
            parts.append(f"  {self.ref_type}: {self.ref_value}")
        return "\n".join(parts)


@dataclass
class DuplicateConfigIdError(ConfigError):
    """Raised when two configs with the same ID are found."""

    def __init__(
        self,
        config_type: str,
        config_id: str,
        first_file: Path,
        second_file: Path,
    ) -> None:
        message = (
            f"Duplicate {config_type} ID '{config_id}' found in multiple files: "
            f"{first_file} and {second_file}"
        )
        super().__init__(
            code="config_duplicate_id",
            message=message,
            file_path=second_file,
            config_id=config_id,
            ref_type=config_type,
            ref_value=config_id,
        )
        object.__setattr__(self, "first_file", first_file)
        object.__setattr__(self, "second_file", second_file)


@dataclass
class MissingConfigFileError(ConfigError):
    """Raised when a required config file is missing."""

    reason: str = ""

    def __init__(
        self,
        file_path: Path,
        reason: str = "",
        *,
        config_id: str | None = None,
        ref_type: str | None = None,
        ref_value: str | None = None,
    ) -> None:
        message = f"Config file not found: {file_path}"
        if reason:
            message += f". {reason}"
        super().__init__(
            code="config_missing_file",
            message=message,
            file_path=file_path,
            config_id=config_id,
            ref_type=ref_type,
            ref_value=ref_value,
        )
        object.__setattr__(self, "reason", reason)


@dataclass
class BrokenReferenceError(ConfigError):
    """Raised when a config references a non-existent definition."""

    def __init__(
        self,
        ref_type: str,
        ref_value: str,
        config_id: str,
        file_path: Path,
        target_type: str,
    ) -> None:
        message = (
            f"Broken reference: {ref_type}='{ref_value}' in {config_id} "
            f"does not exist in {target_type} registry"
        )
        super().__init__(
            code="config_broken_reference",
            message=message,
            file_path=file_path,
            config_id=config_id,
            ref_type=ref_type,
            ref_value=ref_value,
        )
        object.__setattr__(self, "target_type", target_type)


@dataclass
class InvalidConfigShapeError(ConfigError):
    """Raised when config file shape is invalid (missing required fields)."""

    def __init__(
        self,
        file_path: Path,
        reason: str,
        config_id: str | None = None,
        ref_type: str | None = None,
        ref_value: str | None = None,
    ) -> None:
        message = f"Invalid config shape in {file_path}: {reason}"
        super().__init__(
            code="config_invalid_shape",
            message=message,
            file_path=file_path,
            config_id=config_id,
            ref_type=ref_type,
            ref_value=ref_value,
        )


@dataclass
class RegistryLoadError(ConfigError):
    """Raised when registry loading fails."""

    def __init__(
        self,
        message: str,
        errors: Iterable[ConfigError] | None = None,
        context: str | None = None,
    ) -> None:
        full_message = message
        if context:
            full_message += f" ({context})"
        normalized_errors = tuple(errors or ())
        super().__init__(
            code="config_registry_load_error",
            message=full_message,
        )
        object.__setattr__(self, "errors", normalized_errors)

    def __str__(self) -> str:
        base = super().__str__()
        if not self.errors:
            return base

        details = "\n\n".join(str(error) for error in self.errors)
        return f"{base}\n\n{details}"


# Kernel-level labels reserved across every product-bundle composition boundary
# (apps/platform-api/bootstrap.py, apps/platform-worker/composition.py,
# scripts/agent/validate_configs.py): "platform_actions" names the platform-actions kernel
# bundle, "kernel_demo" names the kernel's own smoke-test product directory. A single shared
# definition here (ANY-32 code review finding: three independently-defined-but-tested-equal
# copies were rejected as not actually "shared/reused") -- plain string literals, not sourced
# from PlatformActionsBundle.bundle_id, because platform-actions depends on platform-core (not
# the reverse); importing it here would be circular. Drift against
# PlatformActionsBundle.bundle_id is caught by
# tests/architecture/test_bundle_composition_parity.py, which imports both.
RESERVED_BUNDLE_IDS: tuple[str, ...] = ("platform_actions", "kernel_demo")


def check_ids_are_unique(
    ids: Iterable[str],
    *,
    reserved: Iterable[str] = (),
    ref_type: str = "id",
    context: str = "composed ids",
) -> None:
    """Raise RegistryLoadError if `ids` contains a repeat, or a value already in `reserved`.

    Takes plain id strings, not ProductBundle instances, so every composition boundary
    (apps/platform-api/bootstrap.py, apps/platform-worker/composition.py,
    scripts/agent/validate_configs.py) can share this one check instead of each hand-rolling its
    own (ANY-32 code review finding: only bootstrap.py had a duplicate-bundle_id check, so a
    duplicate could pass worker/validate-configs startup while failing the API)."""
    seen = set(reserved)
    errors: list[ConfigError] = []
    for value in ids:
        if value in seen:
            errors.append(
                ConfigError(
                    code=f"config_duplicate_{ref_type}",
                    message=f"Duplicate {ref_type} '{value}' in {context}",
                    config_id=value,
                    ref_type=ref_type,
                    ref_value=value,
                )
            )
        else:
            seen.add(value)
    if errors:
        raise RegistryLoadError(f"Duplicate {ref_type} in {context}", errors=errors)
