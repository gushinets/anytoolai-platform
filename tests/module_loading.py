"""Shared by tests/test_kernel_demo_smoke.py's load_smoke_module() and
tests/test_atoms_proof.py's load_atoms_proof_module(): both load a scripts/agent/*.py module by
file path (registering it in sys.modules before exec_module() so a `from __future__ import
annotations` dataclass in the loaded file can resolve its string annotations) and cache it,
instead of re-parsing the file on every one of the ~20-40 test functions that call them. No test
mutates a loaded module directly -- every test goes through pytest's monkeypatch fixture, which
auto-restores per test regardless of whether the module object is shared -- so one
process-lifetime instance per (name, path) is safe."""

from __future__ import annotations

import functools
import importlib.util
import sys
from pathlib import Path
from types import ModuleType


@functools.cache
def load_cached_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module
