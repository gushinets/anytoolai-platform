from __future__ import annotations

import ast
from pathlib import Path

from static_string_resolution import (
    PythonModules,
    iter_source_files,
    module_import_aliases,
    parse_python_files,
    python_expr_values,
    python_modules,
    resolve_import_module,
)

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
    # Starlette methods FastAPI/APIRouter inherit — `add_route(path, endpoint)` registers a route
    # the same way `add_api_route` does, and `mount(path, app)` registers `path` as a sub-app
    # prefix; `_path_argument`'s "first positional, or path=" extraction already covers both shapes.
    "add_route",
    "mount",
}
# `app.include_router(router, prefix=...)` is how main.py could hardcode a product-specific
# prefix without ever calling APIRouter(...) itself — must be caught alongside APIRouter/route
# decorators, not just them.
PREFIX_KEYWORD_CALLS = {"APIRouter", "include_router"}

ROUTE_TARGET_CONSTRUCTORS = {"APIRouter", "FastAPI"}
# Starlette route-object constructors — `FastAPI(routes=[Route("/proposal_ai/status", endpoint)])`
# (and the `WebSocketRoute`/`Mount` equivalents) register a route the same way `router.get(...)`
# does, but as a standalone object construction rather than a method call on a tracked
# router/app — a call shape `_route_path_literals_for_tree`'s `called_on_router` gate never
# recognizes, since there is no router/app receiver to check at all.
ROUTE_OBJECT_CONSTRUCTORS = {"Route", "WebSocketRoute", "Mount"}


def _keyword_value(node: ast.Call, keyword: str, modules: PythonModules, path: Path) -> frozenset[str]:
    for kw in node.keywords:
        if kw.arg == keyword:
            return python_expr_values(kw.value, modules, path)
    return frozenset()


def _path_argument(node: ast.Call, modules: PythonModules, path: Path) -> frozenset[str]:
    """The route's `path`: first positional arg, or the `path=` keyword — every statically-known
    reachable value (a name reassigned inside a conditional branch resolves to the full set, not
    just one). Resolved through the shared static resolver, so a literal, a same-file constant, a
    constant imported from another module (`from .paths import PROPOSAL_STATUS_PATH`), a module-
    qualified constant (`paths.PROPOSAL_STATUS_PATH`, including through a bare dotted import), a
    `+` concatenation, or an f-string of any of those all fold to the path(s) they register."""
    if node.args:
        values = python_expr_values(node.args[0], modules, path)
        if values:
            return values
    return _keyword_value(node, "path", modules, path)


def _import_aliases_for(tree: ast.AST, tracked_names: set[str]) -> dict[str, str]:
    """Maps a local import name to the real name it's bound to, for any name in
    `tracked_names`, e.g. `from fastapi import FastAPI as F` -> `{"F": "FastAPI"}` (a bare
    `from fastapi import FastAPI` maps `"FastAPI": "FastAPI"`, redundant but harmless)."""
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                if alias.name in tracked_names:
                    aliases[alias.asname or alias.name] = alias.name
    return aliases


def _route_target_import_aliases(tree: ast.AST) -> dict[str, str]:
    return _import_aliases_for(tree, ROUTE_TARGET_CONSTRUCTORS)


def _route_object_import_aliases(tree: ast.AST) -> dict[str, str]:
    """A separate alias map from `_route_target_import_aliases`, deliberately not merged with
    it: `_is_route_target_call`/`_direct_router_names` treat *any* name in the router/app alias
    dict as "this creates a router/app object" — merging `Route`/`WebSocketRoute`/`Mount` into
    that same dict would wrongly make `x = Route(...)` look like a router/app binding too."""
    return _import_aliases_for(tree, ROUTE_OBJECT_CONSTRUCTORS)


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


def _propagate_router_aliases(
    tree: ast.AST,
    names: set[str],
    module_router_names: dict[str, set[str]] | None = None,
) -> bool:
    """Grow `names` (in place) with any local rebinding of an already-known router/app expression
    (`api = router`, `other_app = app.router`, `local = shared.router`), to a fixed point, so a
    multi-hop chain (`b = a; c = b`) resolves too — not just a single reassignment.
    `_is_router_expr` also covers a `.router` RHS and a module-alias attribute access, so
    `other = app.router` / `local = shared.router` are picked up here for free. Returns whether
    anything was added, so a caller running this across several files can tell when to stop
    iterating.
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
            if value is None or not _is_router_expr(value, names, module_router_names):
                continue
            for target in targets:
                if isinstance(target, ast.Name) and target.id not in names:
                    names.add(target.id)
                    changed = True
                    changed_overall = True
    return changed_overall


def _package_router_names(
    modules: PythonModules,
) -> tuple[dict[Path, set[str]], dict[Path, dict[str, set[str]]]]:
    """Router/app variable names per file, resolved across the whole package: a name imported
    from another module in this same package that's a known router there is itself a known
    router here too, propagated to a fixed point so any-length import/alias chains resolve
    (import then local re-alias, a chain of imports across several files, or an attribute access
    through a module-alias import) — not just one hop. Returns `(router_names_by_file,
    module_router_names_by_file)` — the second lets a later pass resolve `shared.router` the same
    way this function's own `_propagate_router_aliases` calls already do.
    """
    trees = modules.trees
    per_file_aliases = {path: _route_target_import_aliases(tree) for path, tree in trees.items()}
    router_names = {
        path: _direct_router_names(tree, per_file_aliases[path]) for path, tree in trees.items()
    }

    import_edges: list[tuple[Path, str, Path, str]] = []
    for path, tree in trees.items():
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            source_path = resolve_import_module(modules, path, node)
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
        # Recomputed each iteration: a module-alias target's own router set can itself still be
        # growing (e.g. it gained a name via the import-edge loop above just now).
        module_router_names = _module_router_names_by_file(modules, router_names)
        for path, tree in trees.items():
            if _propagate_router_aliases(tree, router_names[path], module_router_names[path]):
                changed = True
    return router_names, _module_router_names_by_file(modules, router_names)


def _module_router_names_by_file(
    modules: PythonModules,
    router_names_by_file: dict[Path, set[str]],
) -> dict[Path, dict[str, set[str]]]:
    """For each file, maps a local module-identity name (see `module_import_aliases`) to the set
    of router names known in the module it refers to, so `shared.router` (an attribute access
    through a *module* identity, not a name bound directly by `from ... import`) resolves the
    router the same way `from .shared import router` already does."""
    return {
        path: {
            local: router_names_by_file[source]
            for local, source in module_import_aliases(modules, path).items()
            if source in router_names_by_file
        }
        for path in modules.trees
    }


def _is_router_expr(
    expr: ast.expr,
    router_names: set[str],
    module_router_names: dict[str, set[str]] | None = None,
) -> bool:
    """Whether `expr` evaluates to a router/app object: a tracked name, a `.router` access on one
    — recursively, so `app.router.router` (never happens in practice, but costs nothing to allow)
    is covered the same way `app.router` is — or an attribute access through a module alias
    (`shared.router`, where `shared` is `import ...shared as shared` and `router` is a known
    router name in that module — see `_module_router_names_by_file`).

    `FastAPI.router` is a real, commonly-used public attribute (it IS the app's root
    `APIRouter`); `app.router.add_api_route(...)` is valid FastAPI usage that registers a route
    exactly like `app.add_api_route(...)` does, so it must resolve to the same receiver check
    instead of requiring the receiver to be a bare `ast.Name`.
    """
    if isinstance(expr, ast.Name):
        return expr.id in router_names
    if isinstance(expr, ast.Attribute):
        # Check the module-alias case first: `shared.router` (`shared` a module alias) must not
        # fall into the ".router" recursion below, which would instead ask "is `shared` itself a
        # tracked router name?" (no — it's a module alias, a different kind of identity) and
        # wrongly return False.
        if module_router_names and isinstance(expr.value, ast.Name):
            names = module_router_names.get(expr.value.id)
            if names is not None and expr.attr in names:
                return True
        if expr.attr == "router":
            return _is_router_expr(expr.value, router_names, module_router_names)
    return False


def _route_path_literals_for_tree(
    modules: PythonModules,
    path: Path,
    router_names: set[str],
    aliases: dict[str, str],
    module_router_names: dict[str, set[str]],
    object_aliases: dict[str, str],
) -> list[str]:
    literals: list[str] = []
    for node in ast.walk(modules.trees[path]):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        if isinstance(func, ast.Attribute):
            func_name = func.attr
            # `router.get(...)` is a route registration only when `router` resolves to a local
            # APIRouter/app (including via `.router` on one, or a module-alias attribute access
            # like `shared.router`) — otherwise it also matches unrelated `.get(...)` calls, e.g.
            # `request.query_params.get("view", "x")`.
            called_on_router = _is_router_expr(func.value, router_names, module_router_names)
        else:
            func_name = getattr(func, "id", None)
            # Resolve an import alias (`APIRouter as R` -> `R(...)`, or `Route as Rt` -> `Rt(...)`)
            # back to the real constructor name. A name can only ever be bound to one of these two
            # disjoint constructor sets, so checking both dicts is unambiguous.
            func_name = aliases.get(func_name, object_aliases.get(func_name, func_name))
            called_on_router = False

        if func_name in ROUTE_REGISTRATION_METHODS and called_on_router:
            # Only the route's own path, not other string kwargs like `summary=`/`description=`
            # (free-form prose that could coincidentally contain a forbidden substring).
            literals.extend(_path_argument(node, modules, path))
        elif func_name in PREFIX_KEYWORD_CALLS:
            literals.extend(_keyword_value(node, "prefix", modules, path))
        elif func_name in ROUTE_OBJECT_CONSTRUCTORS:
            # A standalone `Route(...)`/`WebSocketRoute(...)`/`Mount(...)` construction — never a
            # method call on a router/app, so no `called_on_router` gate applies here at all.
            literals.extend(_path_argument(node, modules, path))
    return literals


def check_product_specific_endpoint_paths(root: Path, package: Path) -> list[str]:
    """Offender descriptions for every product-specific route path/prefix registered anywhere in
    `package`. `root` is the tree the package's absolute imports are rooted under (the repo root
    for the real package; a temp dir for an isolated regression fixture)."""
    trees: dict[Path, ast.Module] = {}
    for path in iter_source_files(package, {".py"}):
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as exc:
            raise AssertionError(f"could not parse {path.relative_to(root)} as Python: {exc}") from exc
    modules = python_modules(root, trees)
    router_names_by_file, module_router_names_by_file = _package_router_names(modules)

    offenders: list[str] = []
    for path, tree in trees.items():
        literals = _route_path_literals_for_tree(
            modules,
            path,
            router_names_by_file[path],
            _route_target_import_aliases(tree),
            module_router_names_by_file[path],
            _route_object_import_aliases(tree),
        )
        for literal in literals:
            lowered = literal.lower()
            for term in FORBIDDEN_PRODUCT_PATH_TERMS:
                if term in lowered:
                    offenders.append(f"{path.relative_to(root)}: {literal!r} contains {term!r}")
    return offenders


def test_no_product_specific_endpoint_paths() -> None:
    offenders = check_product_specific_endpoint_paths(ROOT, PLATFORM_API_PACKAGE)
    assert offenders == [], "product-specific route paths found: " + ", ".join(offenders)


# Isolated regressions: each fixture is a tiny package under `tmp_path`, so a gate gap is proven
# closed by a permanent test rather than by a one-off repro script.
_PATHS_MODULE = 'PROPOSAL_STATUS_PATH = "/proposal_ai/status"\n'


def _write_package(tmp_path: Path, files: dict[str, str]) -> Path:
    package = tmp_path / "pkg"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    for name, body in files.items():
        (package / name).write_text(body, encoding="utf-8")
    return package


def test_route_path_constant_imported_from_another_module_is_detected(tmp_path: Path) -> None:
    package = _write_package(
        tmp_path,
        {
            "paths.py": _PATHS_MODULE,
            "routes.py": (
                "from fastapi import APIRouter\n"
                "from pkg.paths import PROPOSAL_STATUS_PATH\n"
                "router = APIRouter()\n"
                "@router.get(PROPOSAL_STATUS_PATH)\n"
                "def status(): ...\n"
            ),
        },
    )
    offenders = check_product_specific_endpoint_paths(tmp_path, package)
    assert len(offenders) == 1 and "'/proposal_ai/status'" in offenders[0]


def test_route_path_constant_via_module_alias_is_detected(tmp_path: Path) -> None:
    package = _write_package(
        tmp_path,
        {
            "paths.py": _PATHS_MODULE,
            "routes.py": (
                "from fastapi import APIRouter\n"
                "from pkg import paths\n"
                "router = APIRouter()\n"
                "@router.get(paths.PROPOSAL_STATUS_PATH)\n"
                "def status(): ...\n"
            ),
            "relative_routes.py": (
                "from fastapi import APIRouter\n"
                "from . import paths as p\n"
                "router = APIRouter()\n"
                "@router.get(f\"{p.PROPOSAL_STATUS_PATH}/detail\")\n"
                "def detail(): ...\n"
            ),
        },
    )
    offenders = check_product_specific_endpoint_paths(tmp_path, package)
    assert len(offenders) == 2, offenders


def test_function_local_import_does_not_shadow_module_level_constant(tmp_path: Path) -> None:
    package = _write_package(
        tmp_path,
        {
            "paths.py": 'PATH = "/proposal_ai/status"\n',
            "safe_paths.py": 'PATH = "/safe"\n',
            "routes.py": (
                "from fastapi import APIRouter\n"
                "from pkg.paths import PATH\n\n"
                "def helper():\n"
                "    from pkg.safe_paths import PATH\n"
                "    return PATH\n\n"
                "router = APIRouter()\n\n"
                "@router.get(PATH)\n"
                "def status(): ...\n"
            ),
        },
    )
    offenders = check_product_specific_endpoint_paths(tmp_path, package)
    assert len(offenders) == 1 and "'/proposal_ai/status'" in offenders[0]


def test_dynamic_route_path_is_not_a_false_positive(tmp_path: Path) -> None:
    package = _write_package(
        tmp_path,
        {
            "routes.py": (
                "from fastapi import APIRouter\n"
                "router = APIRouter()\n"
                "def register(segment: str) -> None:\n"
                "    router.add_api_route(f\"/products/{segment}\", lambda: None)\n"
                "    router.add_api_route(\"/products/\" + segment, lambda: None)\n"
            ),
        },
    )
    assert check_product_specific_endpoint_paths(tmp_path, package) == []


def test_route_path_constant_conditionally_reassigned_is_detected(tmp_path: Path) -> None:
    # Round 68 (team lead #4) — the review's own repro: a module-level constant reassigned inside
    # an `if` is invisible to `_add_module_level_constants` unless it walks into the branch, so
    # the forbidden value registered only when `ENABLE_PROPOSAL` is truthy went undetected.
    package = _write_package(
        tmp_path,
        {
            "routes.py": (
                "from fastapi import APIRouter\n"
                "import os\n\n"
                'PATH = "/safe"\n'
                'if os.environ.get("ENABLE_PROPOSAL"):\n'
                '    PATH = "/proposal_ai/status"\n\n'
                "router = APIRouter()\n"
                "@router.get(PATH)\n"
                "def status(): ...\n"
            ),
        },
    )
    offenders = check_product_specific_endpoint_paths(tmp_path, package)
    assert len(offenders) == 1 and "'/proposal_ai/status'" in offenders[0]


def test_route_path_constant_with_only_safe_branches_is_not_a_false_positive(tmp_path: Path) -> None:
    # Negative control for the fix above: unioning reachable values across an `if`/`else` must not
    # manufacture an offender when neither branch is forbidden.
    package = _write_package(
        tmp_path,
        {
            "routes.py": (
                "from fastapi import APIRouter\n"
                "import os\n\n"
                "if os.environ.get('SHORT'):\n"
                '    PATH = "/s"\n'
                "else:\n"
                '    PATH = "/status"\n\n'
                "router = APIRouter()\n"
                "@router.get(PATH)\n"
                "def status(): ...\n"
            ),
        },
    )
    assert check_product_specific_endpoint_paths(tmp_path, package) == []


def test_route_path_constant_via_bare_dotted_import_is_detected(tmp_path: Path) -> None:
    # Round 68 (team lead #4) — the review's own repro: `import pkg.paths` (no `as`) binds only
    # the top-level name `pkg`; `pkg.paths.PROPOSAL_STATUS_PATH` is a two-level attribute chain the
    # old single-hop `ast.Attribute` match couldn't structurally reach.
    package = _write_package(
        tmp_path,
        {
            "paths.py": _PATHS_MODULE,
            "routes.py": (
                "from fastapi import APIRouter\n"
                "import pkg.paths\n"
                "router = APIRouter()\n"
                "@router.get(pkg.paths.PROPOSAL_STATUS_PATH)\n"
                "def status(): ...\n"
            ),
        },
    )
    offenders = check_product_specific_endpoint_paths(tmp_path, package)
    assert len(offenders) == 1 and "'/proposal_ai/status'" in offenders[0]
