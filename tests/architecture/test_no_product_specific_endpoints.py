from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The whole package, not just routers/ + main.py — a router can be defined in any module here
# (bootstrap.py, a future product_api.py, ...) and wired in via `app.include_router(router)` from
# main.py, where main.py itself carries no forbidden literal and the defining module would
# otherwise never be visited by this guard.
PLATFORM_API_PACKAGE = ROOT / "apps" / "platform-api" / "src" / "anytoolai_platform_api"

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
    # FastAPI/Starlette WebSocket registration APIs — same "path is the route" shape as the HTTP
    # ones above, just a different transport.
    "websocket",
    "websocket_route",
    "add_api_websocket_route",
    "add_websocket_route",
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


def _direct_router_names(tree: ast.AST, aliases: dict[str, str]) -> set[str]:
    """Names bound by a direct `<name> = APIRouter(...)`/`FastAPI(...)` constructor call in this
    module, including annotated assignments (`app: FastAPI = FastAPI()`,
    `router: APIRouter = APIRouter()`) and import-aliased constructors
    (`from fastapi import FastAPI as F; app = F()`).

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


def _propagate_router_aliases(tree: ast.AST, names: set[str]) -> bool:
    """Grow `names` (in place) with any local rebinding of an already-known router/app expression
    (`api = router`, `other_app = app.router`), to a fixed point, so a multi-hop chain
    (`b = a; c = b`) resolves too — not just a single reassignment. `_is_router_expr` also covers
    a `.router` RHS, so `other = app.router` is picked up here for free. Returns whether anything
    was added, so a caller running this across several files can tell when to stop iterating.
    """
    changed_overall = False
    changed = True
    while changed:
        changed = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Assign):
                targets = node.targets
                value = node.value
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target]
                value = node.value
            else:
                continue
            if value is None or not _is_router_expr(value, names):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    changed = True
                    changed_overall = True
    return changed_overall


def _router_variable_names(tree: ast.AST, aliases: dict[str, str]) -> set[str]:
    """Per-file router/app names: direct constructor calls plus local alias propagation."""
    names = _direct_router_names(tree, aliases)
    _propagate_router_aliases(tree, names)
    return names


def _module_dotted_name(path: Path) -> str:
    """The dotted module name `path` would import as, e.g.
    `apps/platform-api/src/anytoolai_platform_api/routers/demo.py` ->
    `anytoolai_platform_api.routers.demo`."""
    relative = path.relative_to(PLATFORM_API_PACKAGE.parent)
    parts = list(relative.with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _resolve_import_module(importing_path: Path, node: ast.ImportFrom) -> str | None:
    """The dotted module name a `from X import Y` statement's `X` refers to, handling both
    absolute imports (`node.level == 0`, this repo's actual convention — see `main.py`'s
    `from anytoolai_platform_api.routers.demo import router as demo_router`) and relative ones
    (`from .shared import router` / `from ..shared import router`, via `node.level`)."""
    if node.level == 0:
        return node.module
    parts = _module_dotted_name(importing_path).split(".")
    # A package's __init__.py already IS that package (its dotted name has no trailing
    # "__init__" — see _module_dotted_name), so a level-1 relative import there stays within
    # that same package. A regular module's own package is one level up instead.
    base_parts = parts if importing_path.name == "__init__.py" else parts[:-1]
    for _ in range(node.level - 1):
        base_parts = base_parts[:-1] if base_parts else base_parts
    if node.module:
        base_parts = base_parts + node.module.split(".")
    return ".".join(base_parts) if base_parts else None


def _package_router_names(trees: dict[Path, ast.Module]) -> dict[Path, set[str]]:
    """Router/app variable names per file, resolved across the whole package: a name imported
    from another module in this same package that's a known router there is itself a known
    router here too, propagated to a fixed point so any-length import/alias chains resolve
    (import then local re-alias, or a chain of imports across several files) — not just one hop.
    """
    module_paths = {_module_dotted_name(path): path for path in trees}
    per_file_aliases = {path: _route_target_import_aliases(tree) for path, tree in trees.items()}
    router_names = {
        path: _direct_router_names(tree, per_file_aliases[path]) for path, tree in trees.items()
    }

    import_edges: list[tuple[Path, str, Path, str]] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            source_dotted = _resolve_import_module(path, node)
            source_path = module_paths.get(source_dotted) if source_dotted else None
            if source_path is None:
                continue
            for alias in node.names:
                import_edges.append((path, alias.asname or alias.name, source_path, alias.name))

    changed = True
    while changed:
        changed = False
        for importing_path, local_name, source_path, source_name in import_edges:
            if (
                source_name in router_names[source_path]
                and local_name not in router_names[importing_path]
            ):
                router_names[importing_path].add(local_name)
                changed = True
        for path, tree in trees.items():
            if _propagate_router_aliases(tree, router_names[path]):
                changed = True
    return router_names


def _is_router_expr(expr: ast.expr, router_names: set[str]) -> bool:
    """Whether `expr` evaluates to a router/app object: a tracked name, or a `.router` access on
    one — recursively, so `app.router.router` (never happens in practice, but costs nothing to
    allow) is covered the same way `app.router` is.

    `FastAPI.router` is a real, commonly-used public attribute (it IS the app's root
    `APIRouter`); `app.router.add_api_route(...)` is valid FastAPI usage that registers a route
    exactly like `app.add_api_route(...)` does, so it must resolve to the same receiver check
    instead of requiring the receiver to be a bare `ast.Name`.
    """
    if isinstance(expr, ast.Name):
        return expr.id in router_names
    if isinstance(expr, ast.Attribute) and expr.attr == "router":
        return _is_router_expr(expr.value, router_names)
    return False


def _route_path_literals_for_tree(
    tree: ast.Module,
    router_names: set[str],
    aliases: dict[str, str],
    constants: dict[str, str],
) -> list[str]:
    literals: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            func_name = func.attr
            # `router.get(...)` is a route registration only when `router` resolves to a local
            # APIRouter/app (including via `.router` on one) — otherwise it also matches
            # unrelated `.get(...)` calls, e.g. `request.query_params.get("view", "x")`.
            called_on_router = _is_router_expr(func.value, router_names)
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
    trees: dict[Path, ast.Module] = {}
    for path in sorted(PLATFORM_API_PACKAGE.rglob("*.py")):
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            raise AssertionError(
                f"could not parse {path.relative_to(ROOT)} as Python: {exc}"
            ) from exc

    router_names_by_file = _package_router_names(trees)

    offenders: list[str] = []
    for path, tree in trees.items():
        aliases = _route_target_import_aliases(tree)
        constants = _module_string_constants(tree)
        literals = _route_path_literals_for_tree(
            tree, router_names_by_file[path], aliases, constants
        )
        for literal in literals:
            lowered = literal.lower()
            for term in FORBIDDEN_PRODUCT_PATH_TERMS:
                if term in lowered:
                    offenders.append(f"{path.relative_to(ROOT)}: {literal!r} contains {term!r}")

    assert offenders == [], "product-specific route paths found: " + ", ".join(offenders)
