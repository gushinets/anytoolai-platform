"""Static string-value resolution shared by every architecture boundary gate in this directory.

Every gate here asks source code the same question — "which string value can this expression
statically take?" — and, until round 34, each answered it with its own, differently incomplete,
ad-hoc logic: the endpoint gate folded same-file constants but not imported ones; the LiteLLM
gate folded f-strings only when they had no interpolation at all; the provider-host gate did a
raw substring search that a `"api." + "openai.com"` split defeats; the extension-prompt gate
matched one literal `role: "system"` shape. A gap closed in one of them stayed open in the rest.

This module is the single answer, used by all of them, so a resolution gap is closed once and
everywhere: for Python, a real-AST (`ast`) resolver over module-level constants propagated across
`from X import NAME` / `import X as m` / `from pkg import mod` edges to a fixed point; for JS/TS,
a real-AST resolver too — via `scripts/agent/js_scope_resolver.mjs`, which parses every file with
the TypeScript compiler (already a repo devDependency) and resolves `const`/`let`/`var`/parameter
bindings through genuine lexical scope, shadowing, write order, and cross-file
`import { NAME } from "./x"` edges.

The JS/TS side used to be a hand-rolled character-level scanner approximating scope and control
flow (brace counting, comma/ASI heuristics). Round 36 through round 42 of the ANY-25 boundary
audit each closed one more real gap the approximation couldn't see — braceless control flow,
concise arrow bodies, ASI, object-literal commas — because a text-level approximation of "where
does this scope end" can only ever be refined one more edge case at a time. A real parser has
none of these ambiguities: it already knows exactly where every statement, block, and expression
starts and ends, so round 43 replaced the whole scanner with one.

Both resolvers only ever *fold* — they never evaluate a real expression. Anything genuinely
dynamic (`f"/{segment}"`, `` `${provider()}/x` ``, a format spec, a member expression, a function
call) stays unresolved, so a gate can't be tricked into a false positive by an expression whose
value it couldn't actually know. A binding reachable through more than one statically-known
value (a name reassigned inside a conditional branch) resolves to the *set* of every value still
reachable, not just one — a gate flags a use if *any* reachable value violates its boundary.
"""

from __future__ import annotations

import ast
import hashlib
import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Vendor/build/scratch directory names never scanned by any gate — a checked-out `node_modules`
# under an extension, a wxt `.output`/`.wxt` build, a `dist`, ... are not repo source.
SKIP_PATH_PARTS = {
    ".git",
    ".venv",
    ".quick-check-venv",
    ".quick-check-tmp",
    ".tmp",
    ".uv-cache",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "__pycache__",
    "site-packages",
    "node_modules",
    ".pnpm-store",
    ".next",
    ".output",
    ".wxt",
    "dist",
    "build",
    "coverage",
    "tmp",
    "uv-cache",
}
# The canonical JS-family extension set — matches `scripts/agent/validate_architecture.py`'s own.
JS_TS_EXTS = {".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


def iter_source_files(root: Path, exts: set[str], extra_skip: set[str] = frozenset()) -> list[Path]:
    """Files under `root` with a suffix in `exts`, skipping `SKIP_PATH_PARTS` (plus `extra_skip`)
    directories *relative to `root`* — a path component above `root` (pytest's `tmp_path` lives
    under `/tmp`, and "tmp" is a skipped name) must not disqualify the whole tree."""
    skip = SKIP_PATH_PARTS | extra_skip
    found: list[Path] = []
    # `os.walk` with in-place pruning, not `rglob`: the repo tree holds >1M entries under
    # `node_modules`/`.venv`/... and `rglob` visits every one of them before a filter can run
    # (~4s per walk, and each gate walks several times).
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(name for name in dirnames if name not in skip)
        found.extend(
            Path(dirpath) / name for name in sorted(filenames) if Path(name).suffix in exts
        )
    return found


def line_number_at(text: str, offset: int) -> int:
    """1-indexed line of `offset` in `text`."""
    return text.count("\n", 0, offset) + 1


# ---------------------------------------------------------------------------------------------
# Python
# ---------------------------------------------------------------------------------------------


@dataclass
class PythonModules:
    """A set of parsed Python modules with their statically-known string constants.

    `module_paths` maps every dotted name a file could be imported as to its path — all suffixes
    of its `root`-relative parts (`apps/platform-api/src/anytoolai_platform_api/routers/demo.py`
    is reachable as `anytoolai_platform_api.routers.demo`, `routers.demo`, `demo`, ...), because
    this index spans several `src/` layouts and namespace packages (no `__init__.py`) at once.
    A name two files share is ambiguous and resolves to nothing (`None`) rather than to a guess.
    """

    root: Path
    trees: dict[Path, ast.Module]
    module_paths: dict[str, Path | None] = field(default_factory=dict)
    module_names: dict[Path, str] = field(default_factory=dict)
    constants: dict[Path, dict[str, frozenset[str]]] = field(default_factory=dict)
    module_aliases: dict[Path, dict[str, Path]] = field(default_factory=dict)
    # Local top-level names bound by a bare `import a.b...` (no `as`) — `alias.name.split(".")[0]`
    # for each. Used only to let `python_expr_values`'s `ast.Attribute` case recognize a
    # multi-level dotted chain rooted at one of these names (`pkg.paths.NAME`) as reachable through
    # an ordinary import, without `module_aliases` needing a one-hop-only entry for it.
    bare_import_roots: dict[Path, set[str]] = field(default_factory=dict)


def parse_python_files(paths: Iterable[Path]) -> dict[Path, ast.Module]:
    """`ast.Module` per parseable file; a file that isn't valid Python is left out."""
    trees: dict[Path, ast.Module] = {}
    for path in paths:
        try:
            trees[path] = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
        except (SyntaxError, ValueError):
            continue
    return trees


def python_module_names(root: Path, path: Path) -> list[str]:
    parts = list(path.relative_to(root).with_suffix("").parts)
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return [".".join(parts[i:]) for i in range(len(parts))]


def import_container_name(modules: PythonModules, importing_path: Path, node: ast.ImportFrom) -> str | None:
    """The dotted name a `from X import Y` statement's `X` refers to — absolute (`node.level ==
    0`) or relative (`from .shared import x` / `from ..shared import x`, via `node.level`; a
    package's `__init__.py` already *is* its package, so a level-1 import there stays in it).
    A dotted *name*, not a file: `X` can be a namespace package with no file of its own."""
    if node.level == 0:
        return node.module
    parts = modules.module_names[importing_path].split(".")
    base = parts if importing_path.name == "__init__.py" else parts[:-1]
    base = base[: max(len(base) - (node.level - 1), 0)]
    if node.module:
        base = base + node.module.split(".")
    return ".".join(base) or None


def resolve_import_module(modules: PythonModules, importing_path: Path, node: ast.ImportFrom) -> Path | None:
    """The module file a `from X import Y` statement's `X` refers to, if it's one in `modules`."""
    dotted = import_container_name(modules, importing_path, node)
    return modules.module_paths.get(dotted) if dotted else None


def module_level_imports(tree: ast.Module) -> list[ast.Import | ast.ImportFrom]:
    """Only import statements declared at module top level (`tree.body`), not nested inside a
    function/class. A function-local `from .safe_paths import PATH` only rebinds `PATH` inside
    that function — it can't and doesn't change the real module-level `PATH` a decorator
    elsewhere in the file actually sees at runtime, so it must not be treated as if it does. Same
    module-scope restriction plain assignments already get in `_add_module_level_constants`,
    applied here to imports."""
    return [node for node in tree.body if isinstance(node, (ast.Import, ast.ImportFrom))]


def module_import_aliases(modules: PythonModules, path: Path) -> dict[str, Path]:
    """Local names bound to *a module itself*: `import a.b as m` -> `{"m": <a/b.py>}`, and
    `from <container> import name` (bare-relative, qualified-relative, or absolute) whenever a
    submodule file actually named `name` exists in `<container>` — the only static signal that
    separates "the submodule `<container>.name`" from "a name defined in `<container>/__init__.py`".

    A bare `import a.b` without `as` isn't one of these (Python binds only the top-level package
    name `a`, not `a.b`) — see `bare_import_roots`/`_bare_dotted_import_roots` instead, which lets
    `python_expr_values` resolve a multi-level chain like `a.b.NAME` rooted at that bare-bound name.
    """
    aliases: dict[str, Path] = {}
    for node in module_level_imports(modules.trees[path]):
        if isinstance(node, ast.Import):
            for alias in node.names:
                target = modules.module_paths.get(alias.name) if alias.asname else None
                if target is not None:
                    aliases[alias.asname] = target
        elif isinstance(node, ast.ImportFrom):
            container = import_container_name(modules, path, node)
            if container is None:
                continue
            for alias in node.names:
                candidate = modules.module_paths.get(f"{container}.{alias.name}")
                if candidate is not None:
                    aliases[alias.asname or alias.name] = candidate
    return aliases


def _bare_dotted_import_roots(tree: ast.Module) -> set[str]:
    """Local top-level names bound by a bare `import a.b...` (no `as`) — Python's own binding
    rule for that form: only the top-level package name (`a`) is bound, not the full dotted path.
    Kept separate from `module_import_aliases` (which maps a name to *one specific module file*)
    since a bare-imported root isn't itself a module reference — it only becomes one once
    `python_expr_values` sees the rest of the dotted chain used against it."""
    return {
        alias.name.split(".", 1)[0]
        for node in module_level_imports(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
        if alias.asname is None
    }


def _attribute_chain(expr: ast.expr) -> tuple[str | None, list[str]]:
    """Walk a chain of `ast.Attribute` nodes down to its root: `a.b.c` -> `("a", ["b", "c"])`.
    `(None, [])` for anything that doesn't bottom out on a plain name (e.g. `f().attr`)."""
    attrs: list[str] = []
    node: ast.expr = expr
    while isinstance(node, ast.Attribute):
        attrs.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        attrs.reverse()
        return node.id, attrs
    return None, []


# A real hardcode fed by more than a couple of conditional branches combined in one expression is
# vanishingly unlikely, and would very likely also be reachable through a simpler branch
# elsewhere — matches `MAX_COMBINATIONS` in `js_scope_resolver.mjs` exactly (same cap, same
# reasoning, the JS/TS side's own long-standing Cartesian-product bound).
_MAX_COMBINATIONS = 256


def _combine(parts: list[frozenset[str]]) -> frozenset[str]:
    """Every possible concatenation of one value from each of `parts`, in order — empty if any
    part is itself unresolved (empty), or if the combination count would exceed
    `_MAX_COMBINATIONS` (mirrors `combine()` in `js_scope_resolver.mjs`)."""
    size = 1
    for part in parts:
        if not part:
            return frozenset()
        size *= len(part)
        if size > _MAX_COMBINATIONS:
            return frozenset()
    combos = {""}
    for part in parts:
        combos = {prefix + value for prefix in combos for value in part}
    return frozenset(combos)


def python_expr_values(expr: ast.expr | None, modules: PythonModules, path: Path) -> frozenset[str]:
    """Every statically-known string value `expr` could take — a literal string, a module
    constant (local, imported, or accessed through a module alias or a bare dotted import as
    `paths.NAME`/`pkg.paths.NAME`), a `"a" + "b"` concatenation of either (recursively, as a
    Cartesian product of every operand's reachable values via `_combine`), or an f-string whose
    every part is a literal or a `FormattedValue` that itself resolves (same Cartesian product
    across parts). Empty for anything genuinely dynamic. A `FormattedValue` with a conversion flag
    (`f"{x!r}"`) or a format spec (`f"{x:>10}"`) is unresolvable: either changes the text in a way
    concatenation can't reproduce, and this resolver never evaluates a real expression.

    A name reachable through more than one statically-known value (reassigned inside a module-
    level `if`) resolves to the full set, not just one (see `_add_module_level_constants`) — and
    composing it with `+`/an f-string composes the *sets*, not just a single value, so a
    conditionally-reachable name can't silently go unresolved (and therefore unreported) just by
    being concatenated with something else."""
    constants = modules.constants.get(path, {})
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return frozenset({expr.value})
    if isinstance(expr, ast.Name):
        return constants.get(expr.id, frozenset())
    if isinstance(expr, ast.Attribute):
        base, chain = _attribute_chain(expr)
        if base is None or not chain:
            return frozenset()
        if len(chain) == 1:
            target = modules.module_aliases.get(path, {}).get(base)
            if target is not None:
                return modules.constants.get(target, {}).get(chain[0], frozenset())
        if len(chain) >= 2 and base in modules.bare_import_roots.get(path, set()):
            dotted_module = ".".join([base, *chain[:-1]])
            target = modules.module_paths.get(dotted_module)
            if target is not None:
                return modules.constants.get(target, {}).get(chain[-1], frozenset())
        return frozenset()
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = python_expr_values(expr.left, modules, path)
        right = python_expr_values(expr.right, modules, path)
        return _combine([left, right])
    if isinstance(expr, ast.JoinedStr):
        parts: list[frozenset[str]] = []
        for part in expr.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(frozenset({part.value}))
            elif (
                isinstance(part, ast.FormattedValue)
                and part.conversion == -1
                and part.format_spec is None
            ):
                parts.append(python_expr_values(part.value, modules, path))
            else:
                return frozenset()
        return _combine(parts)
    return frozenset()


def _add_module_level_constants(modules: PythonModules, path: Path) -> None:
    """Add top-level `NAME = <resolvable>` / `NAME: T = <resolvable>` bindings to
    `modules.constants[path]` in place, in source order, so a later binding can reference an
    earlier one in the same pass. `tree.body` only (recursing into `ast.If` branches, see below):
    a same-named local inside a function can't overwrite the real module-level value.

    A binding replaces the name's reachable set — ordinary, deterministic, source-order semantics,
    the same within an `ast.If` branch as in straight-line code. An `ast.If` itself evaluates its
    `body` and `orelse` (recursed into, so `elif`/nested `if` chains both work) each from the exact
    same *entry* state — the state as of just before the `if` — independently of one another, then
    joins the two *resulting* states by union, name by name, once both branches are done. Round 69:
    this — not unioning each write into the live state as it's *found* — is what keeps a value
    correctly dropped when every branch unconditionally overwrites it (`X = "bad"; if c: X = "a"
    else: X = "b"` must resolve `X` to `{"a", "b"}` only, since no runtime path still has `"bad"`
    reachable at the join point; the live-union approach a prior round shipped would incorrectly
    keep `"bad"` alive forever once it was ever written). Only `ast.If` is modeled; `try`/`for`/
    `while`/`with` stay out of scope (not raised by any review round so far). `PATH += "x"`
    (`ast.AugAssign`, `+` only) is handled like any other deterministic write — it replaces the
    name's reachable set with the Cartesian product (`_combine`) of its own previous set and the
    RHS's, so a value built up across more than one statement (including across an `ast.If`
    branch, via the same entry-state/join machinery above) is still seen, not silently dropped."""

    def visit(stmts: list[ast.stmt]) -> None:
        for node in stmts:
            if isinstance(node, ast.If):
                entry = dict(modules.constants[path])
                visit(node.body)
                then_state = dict(modules.constants[path])
                modules.constants[path] = dict(entry)
                visit(node.orelse)
                else_state = dict(modules.constants[path])
                modules.constants[path] = {
                    name: then_state.get(name, frozenset()) | else_state.get(name, frozenset())
                    for name in {*then_state, *else_state}
                }
                continue
            if isinstance(node, ast.Assign):
                targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
                values = python_expr_values(node.value, modules, path)
            elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                targets = [node.target.id]
                values = python_expr_values(node.value, modules, path)
            elif isinstance(node, ast.AugAssign) and isinstance(node.target, ast.Name) and isinstance(
                node.op, ast.Add
            ):
                targets = [node.target.id]
                previous = modules.constants[path].get(node.target.id, frozenset())
                rhs = python_expr_values(node.value, modules, path)
                values = _combine([previous, rhs])
            else:
                continue
            if not values:
                continue
            for name in targets:
                modules.constants[path][name] = values

    visit(modules.trees[path].body)


def python_modules(root: Path, trees: dict[Path, ast.Module]) -> PythonModules:
    """Index `trees` and resolve every module's string constants across imports to a fixed point,
    so `paths.py: X = "/a"` + `routes.py: from pkg.paths import X` + `main.py: from pkg.routes
    import X as Y` all know `X`/`Y` — any-length chains, in any file order."""
    modules = PythonModules(root=root, trees=trees)
    for path in trees:
        names = python_module_names(root, path)
        modules.module_names[path] = names[0]
        for name in names:
            modules.module_paths[name] = None if name in modules.module_paths else path
    modules.constants = {path: {} for path in trees}
    modules.module_aliases = {path: module_import_aliases(modules, path) for path in trees}
    modules.bare_import_roots = {path: _bare_dotted_import_roots(tree) for path, tree in trees.items()}

    # ponytail: bounded fixed-point iteration (each pass re-resolves every module); a cycle of
    # mutually-shadowing bindings can't oscillate forever thanks to the cap. Upgrade path: a
    # topological pass over import edges if this ever shows up in test runtime.
    for _ in range(50):
        previous = {path: dict(values) for path, values in modules.constants.items()}
        for path, tree in trees.items():
            imported: dict[str, frozenset[str]] = {}
            for node in module_level_imports(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                source = resolve_import_module(modules, path, node)
                if source is None:
                    continue
                for alias in node.names:
                    value = modules.constants[source].get(alias.name)
                    if value:
                        imported[alias.asname or alias.name] = value
            modules.constants[path] = imported
            _add_module_level_constants(modules, path)
        if modules.constants == previous:
            break
    return modules


def python_string_values(modules: PythonModules, path: Path) -> list[tuple[int, str]]:
    """Every statically-resolvable string expression in `path`, as `(lineno, value)` — one entry
    per reachable value (an expression with more than one statically-known possible value,
    reassigned inside a conditional branch, is reported once per value, matching `js_string_values`
    on the JS/TS side), and a resolved expression's sub-parts are not also reported separately, so
    a folded concatenation/f-string can't also match on a fragment."""
    found: list[tuple[int, str]] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.expr):
            values = python_expr_values(node, modules, path)
            if values:
                found.extend((node.lineno, value) for value in values)
                return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(modules.trees[path])
    return found


# ---------------------------------------------------------------------------------------------
# JS/TS
# ---------------------------------------------------------------------------------------------

JS_QUOTE_CHARS = ("'", '"', "`")  # backtick included: JS/TS template literals

_JS_SCOPE_RESOLVER_DIR = Path(__file__).resolve().parents[2] / "scripts" / "agent"
_JS_SCOPE_RESOLVER_SCRIPT = _JS_SCOPE_RESOLVER_DIR / "js_scope_resolver.mjs"
_js_scope_resolver_ready = False


def _js_scope_resolver_fingerprint() -> str:
    package_json = _JS_SCOPE_RESOLVER_DIR / "package.json"
    return hashlib.sha256(package_json.read_bytes()).hexdigest()


def _js_scope_resolver_marker() -> Path:
    return _JS_SCOPE_RESOLVER_DIR / "node_modules" / ".quick-check-fingerprint"


def _require_tool(name: str) -> str:
    """Resolve `name` to its full path via `shutil.which`, which — unlike a bare command name
    passed straight to `subprocess.run(..., shell=False)` — applies `PATHEXT` on Windows. npm
    ships as `npm.cmd`; Windows `CreateProcess` (what `subprocess` calls without `shell=True`)
    only launches an exact executable it's given, so a bare `"npm"` fails to resolve there even
    when it's genuinely on `PATH` (round 46's `windows-latest` CI failure: `npm ... wasn't found
    on PATH`, though `node` itself — a real `.exe` — resolved fine). `runner.py`'s own
    `probe_tool()` already does this same resolution; this mirrors it."""
    resolved = shutil.which(name)
    if resolved is None:
        raise AssertionError(
            f"{name} is required to run the JS/TS architecture gates but wasn't found on PATH."
            + (" Install Node.js (npm ships with it)." if name == "npm" else "")
        )
    return resolved


def _ensure_js_scope_resolver_dependencies() -> None:
    """`js_scope_resolver.mjs` needs the `typescript` package (round 45) — installed via its own,
    standalone `scripts/agent/package.json`, deliberately separate from the frontend workspace's
    own pnpm-managed `node_modules`: quick-check's baseline CI job (the required check on every
    PR) never runs `pnpm install`, so the repo root's `node_modules/typescript` isn't guaranteed
    to exist there, and broadening that job to provision the whole frontend workspace just for
    this would cut against quick-check's own "no frontend checks" design. A plain, scoped `npm
    install` — self-installed here, on first use, and cached on disk exactly the way
    `.quick-check-venv` self-manages the Python side (see `quick_check.py`'s own
    `dependency_fingerprint()`) — keeps this check self-contained with no CI workflow change: the
    GitHub-hosted runner images this repo's CI uses already ship Node.js and npm with no setup
    step (confirmed by the very failure this fixes — the error was `typescript` not being
    found, not `node`/`npm` being absent)."""
    global _js_scope_resolver_ready
    if _js_scope_resolver_ready:
        return
    marker = _js_scope_resolver_marker()
    fingerprint = _js_scope_resolver_fingerprint()
    if not marker.exists() or marker.read_text(encoding="utf-8").strip() != fingerprint:
        npm = _require_tool("npm")
        result = subprocess.run(
            [npm, "install", "--no-audit", "--no-fund"],
            cwd=_JS_SCOPE_RESOLVER_DIR,
            capture_output=True,
            text=True,
            encoding="utf-8",
            # `npm` is itself a Node.js process under the hood — a well-documented Node/Windows
            # quirk (nodejs/node#10836) makes `process.stdin` access hang when its stdin handle is
            # inherited from a non-interactive parent without ever being closed, even for a command
            # that never actually reads input. Left unset, this inherits the test runner's own
            # stdin; explicitly closing it removes that hang path (round 55, found via the same
            # hang in `runner.py`'s `probe_tool` on a real `windows-latest` run).
            stdin=subprocess.DEVNULL,
            timeout=180,
        )
        if result.returncode != 0:
            raise AssertionError(
                f"npm install for {_JS_SCOPE_RESOLVER_DIR} failed (exit {result.returncode}):\n"
                f"{result.stderr}"
            )
        marker.write_text(fingerprint, encoding="utf-8")
    _js_scope_resolver_ready = True


def js_string_literals(text: str) -> dict[int, tuple[int, str]]:
    """Every quoted string in `text`, keyed by the offset of its opening quote:
    `{open_quote_offset: (close_quote_offset, quote_char)}`. A plain quote-pair scan — used
    directly for `.json` (no comment syntax, no scope/expression structure to resolve, so it
    never goes through the real-parser path below at all) and for computing quoted-string spans
    within an already comment-blanked JS/TS text (see `js_modules`)."""
    literals: dict[int, tuple[int, str]] = {}
    quote_char: str | None = None
    open_at = 0
    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if quote_char:
            if char == "\\":
                i += 2
                continue
            if char == quote_char:
                literals[open_at] = (i, quote_char)
                quote_char = None
            i += 1
            continue
        if char in JS_QUOTE_CHARS:
            quote_char = char
            open_at = i
        i += 1
    return literals


@dataclass
class JsModules:
    """Every JS/TS file's statically-known string values, as resolved by a real parse (see
    `js_modules`).

    `texts[path]` is the file's own source with every comment blanked to same-length whitespace
    (newlines kept) — every other character offset below is therefore identical to the original
    file's, so a gate can still regex-scan this text for a candidate position (a `role:` key, an
    import specifier, a `provider/model` shape) and resolve the value found there against
    `values` directly, with no separate comment-handling of its own needed.

    `values[path]` maps a text offset to every statically-known string the expression starting
    there could produce — real lexical scope, shadowing, write order, and cross-file
    `import { NAME } from "./x"` resolution are already baked in; a name reachable through more
    than one value (reassigned inside a conditional branch) maps to the full set, not just one.
    Absent from the map (or empty) means "genuinely dynamic here."

    `roots[path]` is every top-level (not itself nested inside another already-foldable string
    expression, so a `+`-chain or template is reported once as a whole, not per fragment)
    resolved expression's `(offset, value)` pairs — an exhaustive scan of every
    hardcoded/foldable string reachable anywhere in the file.
    """

    texts: dict[Path, str]
    values: dict[Path, dict[int, frozenset[str]]] = field(default_factory=dict)
    roots: dict[Path, list[tuple[int, str]]] = field(default_factory=dict)


def js_modules(paths: Iterable[Path]) -> JsModules:
    """Parse every JS/TS file in `paths` with the real TypeScript compiler, in one batched call to
    `scripts/agent/js_scope_resolver.mjs` (self-installs its own `typescript` dependency on first
    use — see `_ensure_js_scope_resolver_dependencies`), and index each file's
    statically-resolvable string expressions. See `JsModules` for the result shape, and the
    script's own module docstring for the resolution model (real lexical scope/shadowing/write-
    order, no character-level heuristics)."""
    paths = list(paths)
    modules = JsModules(texts={})
    if not paths:
        return modules
    _ensure_js_scope_resolver_dependencies()
    node = _require_tool("node")
    result = subprocess.run(
        [node, str(_JS_SCOPE_RESOLVER_SCRIPT)],
        input=json.dumps([str(path) for path in paths]),
        capture_output=True,
        text=True,
        # Explicit, not the platform default: `text=True` alone decodes stdout/stderr with
        # `locale.getpreferredencoding()`, which on `windows-latest` CI is cp1252, not UTF-8 — the
        # script's stdout is the JSON-serialized text of every real source file scanned, which can
        # (and, in this repo's own prose-heavy comments, does) contain multi-byte UTF-8 sequences
        # cp1252 can't decode at all (round 49: a real CI failure — every byte 0x80-0xFF is
        # *something* in cp1252, but 0x90 specifically is undefined there, so decoding crashed on
        # the reader thread instead of just mangling the text).
        encoding="utf-8",
        timeout=120,
    )
    if result.returncode != 0:
        raise AssertionError(
            f"js_scope_resolver.mjs failed (exit {result.returncode}):\n{result.stderr}"
        )
    data = json.loads(result.stdout)
    for path in paths:
        entry = data.get(str(path))
        if entry is None:
            continue
        modules.texts[path] = entry["text"]
        modules.values[path] = {
            int(offset): frozenset(values) for offset, values in entry["values"].items()
        }
        modules.roots[path] = [(offset, value) for offset, value in entry["roots"]]
    return modules


def _resolved_at(modules: JsModules, path: Path, position: int) -> frozenset[str]:
    """Every statically-known value the expression at `position` resolves to — skipping leading
    whitespace first, since a caller's position (e.g. right after a `role:` key's own `:`, or a
    regex match's end) is rarely the value expression's *exact* start offset."""
    text = modules.texts.get(path, "")
    length = len(text)
    while position < length and text[position].isspace():
        position += 1
    return modules.values.get(path, {}).get(position, frozenset())


def js_string_expr_at(modules: JsModules, path: Path, pos: int) -> frozenset[str]:
    """The set of statically-known values the expression starting at (or shortly after, past
    whitespace) `pos` resolves to — empty if genuinely dynamic or nothing string-like starts
    there."""
    return _resolved_at(modules, path, pos)


def resolve_js_identifier(modules: JsModules, path: Path, name: str, position: int) -> frozenset[str]:
    """The set of statically-known values the identifier `name` resolves to at `position` — an
    alias of `js_string_expr_at` (a specific text offset already uniquely identifies the resolved
    expression; `name` is redundant with it, kept only so call sites reading a shorthand property
    or a bare reference stay self-documenting)."""
    return _resolved_at(modules, path, position)


def js_string_values(modules: JsModules, path: Path) -> list[tuple[int, str]]:
    """Every statically-resolvable string expression in `path`, as `(offset, value)` — one entry
    per reachable value, so an expression with more than one statically-known possible value
    (reassigned inside a conditional branch) is reported once per value, not once overall."""
    return sorted(modules.roots.get(path, []))
