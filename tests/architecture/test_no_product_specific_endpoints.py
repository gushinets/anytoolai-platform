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


def _keyword_value(node: ast.Call, keyword: str) -> str | None:
    for kw in node.keywords:
        if kw.arg == keyword and isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
            return kw.value.value
    return None


def _path_argument(node: ast.Call) -> str | None:
    """The route's `path`: first positional arg, or the `path=` keyword."""
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return _keyword_value(node, "path")


ROUTE_TARGET_CONSTRUCTORS = {"APIRouter", "FastAPI"}


def _router_variable_names(tree: ast.AST) -> set[str]:
    """Names bound by `<name> = APIRouter(...)`/`FastAPI(...)` in this module.

    `main.py` binds `app = FastAPI(...)`, not `APIRouter(...)` — `app.add_api_route(...)`/
    `@app.api_route(...)` register routes directly on the app and must be tracked the same way
    `router.get(...)` is, or a hardcoded product path registered straight on `app` bypasses this
    guard entirely.
    """
    names: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Assign)
            and isinstance(node.value, ast.Call)
            and isinstance(node.value.func, ast.Name)
            and node.value.func.id in ROUTE_TARGET_CONSTRUCTORS
        ):
            names.update(target.id for target in node.targets if isinstance(target, ast.Name))
    return names


def _route_path_literals(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    router_names = _router_variable_names(tree)
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
            called_on_router = False

        if func_name in ROUTE_REGISTRATION_METHODS and called_on_router:
            # Only the route's own path, not other string kwargs like `summary=`/`description=`
            # (free-form prose that could coincidentally contain a forbidden substring).
            path = _path_argument(node)
            if path is not None:
                literals.append(path)
        elif func_name in PREFIX_KEYWORD_CALLS:
            prefix = _keyword_value(node, "prefix")
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
