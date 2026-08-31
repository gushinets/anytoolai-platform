from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ROUTERS_DIR = ROOT / "apps" / "platform-api" / "src" / "anytoolai_platform_api" / "routers"
MAIN_MODULE = ROOT / "apps" / "platform-api" / "src" / "anytoolai_platform_api" / "main.py"

# MVP-B products (docs/product-specs/mvp-scope-source-of-truth.md); platform-api routes must stay
# parameterized on {product_id} instead of hardcoding one of these.
FORBIDDEN_PRODUCT_PATH_TERMS = [
    "proposal_ai",
    "proposal-ai",
    "acceptance_builder",
    "acceptance-builder",
    "case_study",
    "case-study",
    "scope_guard",
    "scope-guard",
    "task_finder",
    "task-finder",
    "send_ready",
    "send-ready",
    "brief_decoder",
    "brief-decoder",
    "persuasion_lens",
    "persuasion-lens",
    "freelancer",
]

ROUTE_REGISTRATION_METHODS = {
    "get",
    "post",
    "put",
    "delete",
    "patch",
    "options",
    "head",
    "trace",
    "api_route",
    "add_api_route",
}
# `app.include_router(router, prefix=...)` is how main.py could hardcode a product-specific
# prefix without ever calling APIRouter(...) itself — must be caught alongside APIRouter/route
# decorators, not just them.
PREFIX_KEYWORD_CALLS = {"APIRouter", "include_router"}


def _module_string_constants(tree: ast.Module) -> dict[str, str]:
    """Module-level `<NAME> = "<literal>"` / `<NAME>: <type> = "<literal>"` bindings, so
    `@router.get(PROPOSAL_STATUS_PATH)` is resolved back to its literal instead of being invisible
    to `_path_argument` (an `ast.Name`, not an `ast.Constant`).

    Scoped to `tree.body` (top-level statements only) — walking the whole tree would also collect
    a same-named local inside a function/class (`def helper(): PROPOSAL_STATUS_PATH = "/safe"`),
    which could overwrite the real module-level value and make a route resolve against the wrong
    string.
    """
    constants: dict[str, str] = {}
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    constants[target.id] = node.value.value
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
        ):
            constants[node.target.id] = node.value.value
    return constants


def _string_value(expr: ast.expr | None, constants: dict[str, str]) -> str | None:
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name) and expr.id in constants:
        return constants[expr.id]
    return None


def _keyword_value(node: ast.Call, keyword: str, constants: dict[str, str]) -> str | None:
    for kw in node.keywords:
        if kw.arg == keyword:
            return _string_value(kw.value, constants)
    return None


def _path_argument(node: ast.Call, constants: dict[str, str]) -> str | None:
    """The route's `path`: first positional arg, or the `path=` keyword."""
    if node.args:
        value = _string_value(node.args[0], constants)
        if value is not None:
            return value
    return _keyword_value(node, "path", constants)


ROUTE_TARGET_CONSTRUCTORS = {"APIRouter", "FastAPI"}


def _route_target_import_aliases(tree: ast.AST) -> dict[str, str]:
    """Maps a local import name to the real constructor name it's bound to, e.g.
    `from fastapi import FastAPI as F` -> `{"F": "FastAPI"}` (a bare
    `from fastapi import FastAPI` maps `"FastAPI": "FastAPI"`, redundant but harmless)."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in ROUTE_TARGET_CONSTRUCTORS:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _is_route_target_call(value: ast.expr | None, aliases: dict[str, str]) -> bool:
    if not isinstance(value, ast.Call):
        return False
    func = value.func
    if isinstance(func, ast.Name):
        # Bare name, or an import alias (`from fastapi import FastAPI as F` -> `F()`).
        return func.id in ROUTE_TARGET_CONSTRUCTORS or func.id in aliases
    # Module-qualified form, e.g. `fastapi.FastAPI()`/`fastapi.APIRouter()` — the import alias
    # (`fastapi`, `fa`, ...) doesn't matter, only the final attribute name does.
    if isinstance(func, ast.Attribute):
        return func.attr in ROUTE_TARGET_CONSTRUCTORS
    return False


def _router_variable_names(tree: ast.AST, aliases: dict[str, str]) -> set[str]:
    """Names bound by `<name> = APIRouter(...)`/`FastAPI(...)` in this module, including
    annotated assignments (`app: FastAPI = FastAPI()`, `router: APIRouter = APIRouter()`) and
    import-aliased constructors (`from fastapi import FastAPI as F; app = F()`).

    `main.py` binds `app = FastAPI(...)`, not `APIRouter(...)` — `app.add_api_route(...)`/
    `@app.api_route(...)` register routes directly on the app and must be tracked the same way
    `router.get(...)` is, or a hardcoded product path registered straight on `app` bypasses this
    guard entirely. A type-annotated binding is an `ast.AnnAssign`, not `ast.Assign` — ordinary,
    valid Python that must be recognized the same way.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_route_target_call(node.value, aliases):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
        elif (
            isinstance(node, ast.AnnAssign)
            and isinstance(node.target, ast.Name)
            and _is_route_target_call(node.value, aliases)
        ):
            names.add(node.target.id)
    return names


def _route_path_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    aliases = _route_target_import_aliases(tree)
    router_names = _router_variable_names(tree, aliases)
    constants = _module_string_constants(tree)
    literals: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            func_name = func.attr
            # `router.get(...)` is a route registration only when `router` is a local
            # APIRouter — otherwise it also matches unrelated `.get(...)` calls, e.g.
            # `request.query_params.get("view", "task-finder-debug")`.
            called_on_router = isinstance(func.value, ast.Name) and func.value.id in router_names
        else:
            func_name = getattr(func, "id", None)
            # Resolve an import alias (`APIRouter as R` -> `R(...)`) back to the real
            # constructor name so its `prefix=` keyword is inspected the same way a bare
            # `APIRouter(prefix=...)`/`include_router(prefix=...)` call is.
            func_name = aliases.get(func_name, func_name)
            called_on_router = False

        if func_name in ROUTE_REGISTRATION_METHODS and called_on_router:
            # Only the route's own path, not other string kwargs like `summary=`/`description=`
            # (free-form prose that could coincidentally contain a forbidden substring).
            path = _path_argument(node, constants)
            if path is not None:
                literals.append(path)
        elif func_name in PREFIX_KEYWORD_CALLS:
            prefix = _keyword_value(node, "prefix", constants)
            if prefix is not None:
                literals.append(prefix)
    return literals


def test_no_product_specific_endpoint_paths() -> None:
    offenders: list[str] = []
    router_files = sorted(ROUTERS_DIR.rglob("*.py"))
    for path in (*router_files, MAIN_MODULE):
        for literal in _route_path_literals(path):
            lowered = literal.lower()
            for term in FORBIDDEN_PRODUCT_PATH_TERMS:
                if term in lowered:
                    offenders.append(f"{path.relative_to(ROOT)}: {literal!r} contains {term!r}")

    assert offenders == [], "product-specific route paths found: " + ", ".join(offenders)
