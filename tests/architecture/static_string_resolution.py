"""Static string-value resolution shared by every architecture boundary gate in this directory.

Every gate here asks source code the same question — "which string value can this expression
statically take?" — and, until round 34, each answered it with its own, differently incomplete,
ad-hoc logic: the endpoint gate folded same-file constants but not imported ones; the LiteLLM
gate folded f-strings only when they had no interpolation at all; the provider-host gate did a
raw substring search that a `"api." + "openai.com"` split defeats; the extension-prompt gate
matched one literal `role: "system"` shape. A gap closed in one of them stayed open in the rest.

This module is the single answer, used by all of them, so a resolution gap is closed once and
everywhere: for Python, a real-AST resolver over module-level constants propagated across
`from X import NAME` / `import X as m` / `from pkg import mod` edges to a fixed point; for JS/TS,
a resolver over `const`/`let`/`var` string bindings propagated across relative
`import { NAME } from "./x"` edges, folding `+` concatenation, grouping parens, and `${NAME}`
template interpolation of a known constant.

Both resolvers only ever *fold* — they never evaluate a real expression. Anything genuinely
dynamic (`f"/{segment}"`, `` `${provider()}/x` ``, a format spec, a member expression) stays
unresolved, so a gate can't be tricked into a false positive by an expression whose value it
couldn't actually know.
"""

from __future__ import annotations

import ast
import itertools
import os
import re
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
    constants: dict[Path, dict[str, str]] = field(default_factory=dict)
    module_aliases: dict[Path, dict[str, Path]] = field(default_factory=dict)


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

    Deliberately out of scope: bare `import a.b` without `as` (Python binds only the top-level
    package name `a`; resolving `a.b.NAME` from that needs multi-level attribute-chain
    resolution, not used anywhere in this repo today).
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


def python_string_value(expr: ast.expr | None, modules: PythonModules, path: Path) -> str | None:
    """A literal string, a module constant (local, imported, or accessed through a module alias
    as `paths.NAME`), a `"a" + "b"` concatenation of either (recursively), or an f-string whose
    every part is a literal or a `FormattedValue` that itself resolves — `None` for anything
    genuinely dynamic. A `FormattedValue` with a conversion flag (`f"{x!r}"`) or a format spec
    (`f"{x:>10}"`) is unresolvable: either changes the text in a way concatenation can't
    reproduce, and this resolver never evaluates a real expression."""
    constants = modules.constants.get(path, {})
    if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
        return expr.value
    if isinstance(expr, ast.Name):
        return constants.get(expr.id)
    if isinstance(expr, ast.Attribute) and isinstance(expr.value, ast.Name):
        target = modules.module_aliases.get(path, {}).get(expr.value.id)
        if target is not None:
            return modules.constants.get(target, {}).get(expr.attr)
        return None
    if isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.Add):
        left = python_string_value(expr.left, modules, path)
        right = python_string_value(expr.right, modules, path)
        if left is not None and right is not None:
            return left + right
        return None
    if isinstance(expr, ast.JoinedStr):
        parts: list[str] = []
        for part in expr.values:
            if isinstance(part, ast.Constant) and isinstance(part.value, str):
                parts.append(part.value)
            elif (
                isinstance(part, ast.FormattedValue)
                and part.conversion == -1
                and part.format_spec is None
            ):
                resolved = python_string_value(part.value, modules, path)
                if resolved is None:
                    return None
                parts.append(resolved)
            else:
                return None
        return "".join(parts)
    return None


def _add_module_level_constants(modules: PythonModules, path: Path) -> None:
    """Add top-level `NAME = <resolvable>` / `NAME: T = <resolvable>` bindings to
    `modules.constants[path]` in place, in source order, so a later binding can reference an
    earlier one in the same pass. `tree.body` only: a same-named local inside a function can't
    overwrite the real module-level value."""
    for node in modules.trees[path].body:
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            targets = [node.target.id]
        else:
            continue
        value = python_string_value(node.value, modules, path)
        if value is not None:
            for name in targets:
                modules.constants[path][name] = value


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

    # ponytail: bounded fixed-point iteration (each pass re-resolves every module); a cycle of
    # mutually-shadowing bindings can't oscillate forever thanks to the cap. Upgrade path: a
    # topological pass over import edges if this ever shows up in test runtime.
    for _ in range(50):
        previous = {path: dict(values) for path, values in modules.constants.items()}
        for path, tree in trees.items():
            imported: dict[str, str] = {}
            for node in module_level_imports(tree):
                if not isinstance(node, ast.ImportFrom):
                    continue
                source = resolve_import_module(modules, path, node)
                if source is None:
                    continue
                for alias in node.names:
                    value = modules.constants[source].get(alias.name)
                    if value is not None:
                        imported[alias.asname or alias.name] = value
            modules.constants[path] = imported
            _add_module_level_constants(modules, path)
        if modules.constants == previous:
            break
    return modules


def python_string_values(modules: PythonModules, path: Path) -> list[tuple[int, str]]:
    """Every statically-resolvable string expression in `path`, as `(lineno, value)` — a
    resolved expression is reported once as a whole (its sub-parts are not also reported
    separately, so a folded concatenation/f-string can't also match on a fragment)."""
    found: list[tuple[int, str]] = []

    def visit(node: ast.AST) -> None:
        if isinstance(node, ast.expr):
            value = python_string_value(node, modules, path)
            if value is not None:
                found.append((node.lineno, value))
                return
        for child in ast.iter_child_nodes(node):
            visit(child)

    visit(modules.trees[path])
    return found


# ---------------------------------------------------------------------------------------------
# JS/TS
# ---------------------------------------------------------------------------------------------

# ponytail: no JS/TS tokenizer is available here without adding a new dependency, so this path
# keeps a hand-rolled quote/comment/regex-literal tracker (`strip_js_comments`, below) instead
# of a real parser. Upgrade path: parse with a real JS/TS tokenizer if a bug is ever found here,
# the same way Python/YAML were moved onto real parsers.
JS_QUOTE_CHARS = ("'", '"', "`")  # backtick included: JS/TS template literals

# Characters that mean "the token just before this position is a value" (an identifier/number,
# a closing `)`/`]`, or a closing quote) — i.e. a following `/` is division, not the start of a
# regex literal. Mirrors the standard JS/TS lexer heuristic for the division-vs-regex ambiguity
# (a `/` after an operator, `(`, `,`, `=`, or start of line is a regex; after a value, a
# division).
_REGEX_PRECEDED_BY_VALUE = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_$)]"
) | frozenset(JS_QUOTE_CHARS)

# A last-*character* heuristic alone can't distinguish a real identifier (`foo / 2`, division)
# from a keyword that also ends in a letter (`return /re/`, a regex) — both end in an
# identifier-class character. These are the JS/TS keywords after which a value can't precede a
# `/`, so a following `/` is still a regex literal despite the preceding word looking like a
# value by its last character alone.
_JS_REGEX_KEYWORDS = frozenset(
    {
        "return", "typeof", "instanceof", "in", "of", "new", "delete", "void", "yield",
        "case", "do", "else", "throw", "await", "default",
    }
)

# `)` is normally a value-ending character (a function call's result), so `_REGEX_PRECEDED_BY_VALUE`
# treats a following `/` as division. But `if (cond) /re/` — a control-flow *condition*'s closing
# paren — is a statement boundary, not a value: what follows isn't "the result of `(cond)`", it's
# a brand new statement. Distinguishing the two needs the word immediately before the *matching*
# `(`, not just the last character before `/`.
_JS_CONTROL_KEYWORDS_BEFORE_PAREN = frozenset({"if", "while", "for", "switch", "catch", "with"})


def _regex_literal_end(text: str, start: int, length: int) -> int | None:
    """If `text[start]` (`/`) starts a JS/TS regex literal, the index just past its closing,
    unescaped `/` outside a `[...]` character class — else `None` (no terminator before the next
    newline, so `start` isn't actually a regex literal)."""
    j = start + 1
    in_char_class = False
    while j < length:
        c = text[j]
        if c == "\n":
            return None
        if c == "\\":
            j += 2
            continue
        if c == "[":
            in_char_class = True
        elif c == "]":
            in_char_class = False
        elif c == "/" and not in_char_class:
            return j + 1
        j += 1
    return None


def strip_js_comments(text: str, jsx: bool = False) -> str:
    """`text` with JS/TS `//` line comments, `/* ... */` block comments and `/regex/` literals
    removed, one physical line per input line (so offsets/line numbers still map back), with
    quote state carried across line boundaries rather than reset at each newline — a template
    literal containing `//` (e.g. a URL) must not have that `//` misread as a comment start on a
    later physical line.

    Block comments must be recognized as their own state (not just skipped like a line comment):
    otherwise a stray quote char inside one (`/* " */`) opens `in_string` early, and a real,
    legitimately-quoted `//` later on the line (e.g. inside a URL) then gets misread as a line
    comment, truncating a real hardcode past it. The same is true of a regex literal containing a
    quote char (`/"/`): it must be recognized and skipped as its own unit, using the standard
    JS/TS division-vs-regex heuristic (`_REGEX_PRECEDED_BY_VALUE` — a `/` is a regex-literal start
    unless the last significant character before it was part of a value: an identifier/number, a
    closing `)`/`]`, or a closing quote) — except a control-flow condition's closing paren
    (`if (cond) /re/`), which is a statement boundary, not a value; `paren_stack` tracks, for each
    open `(`, whether the word immediately before it was a control keyword, so its matching `)`
    can override `last_sig` back to a non-value when popped.

    `last_sig` and the current identifier word (`word_buf`/`last_word`) are both maintained as
    persistent state across the whole function, not per physical line: a keyword or a
    control-flow `(` can legitimately be separated from what follows it by a line break or a
    comment (`if\\n(cond)`, `if // note\\n(cond)`, `return/*note*//"/`).

    `word_buf`/`last_word` finalization is structural, not opt-in per branch: every identifier
    character (alnum/`_`/`$`) is handled by one dedicated branch at the top of the loop that only
    ever appends to `word_buf`, and *every other* character — whatever it is, whichever branch
    ends up handling it — passes through one unconditional `_finalize_word()` call first, so no
    branch *can* forget to flush the pending word.

    `last_word_is_property` additionally tracks whether the word was reached via a preceding `.`
    (`config.default`, `obj?.if`) — reserved words are valid JS/TS *property names*, so an
    IdentifierName spelled like a keyword right after `.`/`?.` is never a real keyword token, and
    must not be matched against `_JS_REGEX_KEYWORDS`/`_JS_CONTROL_KEYWORDS_BEFORE_PAREN`.

    `jsx` (only ever true for `.jsx`/`.tsx`) excludes one more `/`-preceding character from
    "regex start": `<` directly followed by `/` is a JSX/TSX closing tag (`</div>`, `</>`), never
    a regex literal. `jsx` also disables `//` line-comment *removal* entirely, and treats `/*` as
    two ordinary characters: raw JSX element text (`<div>https://example.com</div>`) is not
    JavaScript — it has no comment syntax at all — and this scanner has no notion of "currently
    inside JSX text" vs. "inside a JS expression", which needs real JSX-aware nesting that a
    character-level heuristic cannot approximate without becoming a second hand-rolled parser.
    The conservative direction for a boundary guard is to *include* more content in scanning,
    never exclude content that should be checked. A `//` comment's own text is still consumed as
    one inert, verbatim run (`in_line_comment`) rather than falling through to the ordinary
    char-by-char scan — comment prose can look like a regex delimiter, a `/*` opener, or a quote,
    and letting it drive the same stateful lexer would mutate state for everything *after* it. A
    misdetected regex span in a JSX-capable file is likewise kept verbatim rather than discarded,
    since its "closing" `/` can be a real hardcode's own separator.
    """
    lines: list[str] = []
    current: list[str] = []
    in_string: str | None = None
    in_block_comment = False
    in_line_comment = False
    last_sig = ""
    word_buf: list[str] = []
    last_word = ""
    last_word_is_property = False
    word_starts_after_dot = False
    paren_stack: list[bool] = []

    def _finalize_word() -> None:
        nonlocal word_buf, last_word, last_word_is_property
        if word_buf:
            last_word = "".join(word_buf)
            last_word_is_property = word_starts_after_dot
            word_buf = []

    i = 0
    length = len(text)
    while i < length:
        char = text[i]
        if char == "\n":
            # Checked unconditionally, before in_block_comment/in_string: a physical line ends
            # here regardless of lexical state, and `lines` must stay one entry per physical
            # line even *inside* a multi-line string or block comment — only
            # `in_string`/`in_block_comment` themselves persist across the split.
            # `in_line_comment` does NOT persist — a `//` comment never spans a line.
            _finalize_word()
            in_line_comment = False
            lines.append("".join(current))
            current = []
            i += 1
            continue
        if in_line_comment:
            current.append(char)
            i += 1
            continue
        if in_block_comment:
            if text.startswith("*/", i):
                in_block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if char == "\\" and i + 1 < length and text[i + 1] != "\n":
                current.append(char)
                current.append(text[i + 1])
                i += 2
                continue
            current.append(char)
            if char == in_string:
                in_string = None
            if not char.isspace():
                last_sig = char
            i += 1
            continue
        if char.isalnum() or char in "_$":
            if not word_buf:
                # First character of a new word — record whether it directly follows a `.`
                # (property access) before `last_sig` moves on to this char itself.
                word_starts_after_dot = last_sig == "."
            word_buf.append(char)
            last_sig = char
            current.append(char)
            i += 1
            continue
        # Every remaining character is a word boundary of some kind, so any word being
        # accumulated is now complete, regardless of which branch below handles this char.
        _finalize_word()
        if char in JS_QUOTE_CHARS:
            in_string = char
            current.append(char)
            last_sig = char
            i += 1
            continue
        if jsx and text.startswith("/*", i):
            # Raw JSX text can contain `/*` literally with no comment semantics — don't open
            # in_block_comment (no guaranteed closing `*/`), and bias a *following* `/` toward
            # "division/ordinary text" rather than "regex start".
            current.append("/")
            current.append("*")
            last_sig = "]"
            i += 2
            continue
        if text.startswith("/*", i):
            in_block_comment = True
            i += 2
            continue
        if jsx and text.startswith("//", i):
            in_line_comment = True
            current.append("/")
            current.append("/")
            i += 2
            continue
        if text.startswith("//", i):
            newline_pos = text.find("\n", i)
            i = length if newline_pos == -1 else newline_pos
            continue
        if char == "(":
            current.append(char)
            last_sig = char
            is_control_keyword = (
                last_word in _JS_CONTROL_KEYWORDS_BEFORE_PAREN and not last_word_is_property
            )
            paren_stack.append(is_control_keyword)
            i += 1
            continue
        if char == ")":
            is_condition_paren = paren_stack.pop() if paren_stack else False
            current.append(char)
            # A condition paren's close is a statement boundary (not a value), so a following
            # `/` reads as a regex start, not division.
            last_sig = "" if is_condition_paren else char
            i += 1
            continue
        if char == "/":
            looks_like_regex = last_sig not in _REGEX_PRECEDED_BY_VALUE
            # `last_sig` alone can't tell a real identifier from a keyword ending the same way
            # (`foo` vs. `return`) — check the whole preceding word against the keyword set only
            # when the char-level heuristic said "value" (a keyword can flip that to "regex"; a
            # real identifier never does). A property name spelled like a keyword
            # (`config.default`) is excluded the same way.
            if not looks_like_regex and last_sig.isalpha():
                looks_like_regex = last_word in _JS_REGEX_KEYWORDS and not last_word_is_property
            # `</` in a JSX/TSX file is always a closing tag, never a regex literal.
            if looks_like_regex and jsx and last_sig == "<":
                looks_like_regex = False
            # A `/` right after `*` is `*/` — a block comment's closing delimiter, or in JSX text
            # the tail of `/* ... */` prose passed through literally — never a new regex start.
            if looks_like_regex and jsx and last_sig == "*":
                looks_like_regex = False
            if looks_like_regex:
                end = _regex_literal_end(text, i, length)
                if end is not None:
                    if jsx:
                        # A plain `/word` in raw JSX text still passes the heuristic above, and
                        # the "closing" `/` can be a real hardcode's own separator — for
                        # JSX-capable files a detected regex span is never discarded.
                        current.append(text[i:end])
                    i = end
                    last_sig = "]"  # a regex literal is a value; a following `/` is division
                    continue
        current.append(char)
        if not char.isspace():
            last_sig = char
        i += 1
    lines.append("".join(current))
    return "\n".join(lines)


def js_string_literals(text: str) -> dict[int, tuple[int, str]]:
    """Every quoted string in `text` (JS/TS, already comment-stripped), keyed by the offset of
    its opening quote: `{open_quote_offset: (close_quote_offset, quote_char)}`."""
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


# One binding's write history, sorted by position: `(write_position, write_block_path,
# possible_values)`. Every `const`/`let`/`var` declaration, every parameter default, and every
# import starts a timeline with one entry (`write_block_path` equal to the binding's own
# `block_path` — see `JsModules`); a later bare reassignment reachable from that binding's scope
# appends another, at *its own* (possibly deeper) block path. `possible_values` is the set of
# statically-known strings that write could produce — empty means "genuinely dynamic, nothing
# known here". Resolving a name at a use site replays the timeline up to that use site: a write
# at the binding's own block path is a *deterministic* one (a straight-line statement, always
# reached before the use site) and replaces whatever was reachable before it; a write at a
# strictly deeper block path is only *conditionally* reached (inside an `if`/loop/etc. that might
# not execute) and adds its values to what's already reachable, without discarding them — see
# `resolve_js_identifier`.
_JsTimeline = list[tuple[int, tuple[int, ...], frozenset[str]]]


@dataclass
class JsModules:
    """Comment-stripped JS/TS sources with their statically-known string declarations.

    `declarations[path][name]` is every distinct binding of `name` in `path`, as `(block_path,
    timeline)`: `block_path` is the stack of enclosing `{ ... }` block ids the binding's own
    declaration sits in (`()` at module top level — see `_js_block_path_at`), and `timeline` is
    its write history (see `_JsTimeline`). A name resolves at a given use site through
    `resolve_js_identifier`, which first picks the *innermost* binding whose `block_path`
    encloses that use site — real lexical shadowing, not "whichever declaration appears last in
    the file" (round 36) — and then, within that binding's own timeline, the set of every
    statically-known value still reachable at the use site's own position: a deterministic write
    replaces the reachable set, a conditional one only adds to it (round 38 — a use site can be
    reached with more than one possible value when a write sits behind a branch the resolver
    can't evaluate, e.g. `if (cond) { role = "user"; }`; discarding the pre-branch value there
    would hide a real violation still reachable when the branch doesn't run). Round 37: a
    deterministic reassignment (no branch involved) is a real, static value and must resolve to
    it, not to "unresolved" just because a write happened after the declaration."""

    texts: dict[Path, str]
    literals: dict[Path, dict[int, tuple[int, str]]] = field(default_factory=dict)
    declarations: dict[Path, dict[str, list[tuple[tuple[int, ...], _JsTimeline]]]] = field(
        default_factory=dict
    )


_JS_IDENT = r"[A-Za-z_$][\w$]*"
_JS_IDENT_RE = re.compile(_JS_IDENT)
# `const NAME = ...` / `let NAME: string = ...` / `export var NAME = ...` (`(?!=)`: not `==`).
_JS_DECL_RE = re.compile(rf"\b(const|let|var)\s+({_JS_IDENT})\s*(?::[^=;{{}}]+?)?=(?!=)")
# A bare `NAME = ...` reassignment (no `const`/`let`/`var`) — `(?<![\w$.])` excludes a member
# assignment (`obj.name = `, not a rebind of `name` itself); `(?![=>])` excludes `==`/`===`
# comparisons and an arrow function (`name => ...`), neither of which is a write to `name`.
#
# ponytail: also matches a `const`/`let`/`var` declaration's own `NAME =` and a parameter
# default's own `NAME =` — both excluded by the caller via `exempt_positions`, not by this regex
# — and a nested-block reassignment that is only *conditionally* reached at runtime
# (`if (cond) { role = "x"; }`), which this still attaches unconditionally to the enclosing
# binding's timeline. Every one of these pushes toward treating *more* code as a real, static
# write, never toward missing one — the safe direction for a boundary gate (a false positive here
# costs one extra line to look at; a false negative hides a real prompt/model/host leak). Upgrade
# path: a real JS/TS parser.
_JS_ASSIGNMENT_RE = re.compile(rf"""(?<![\w$.])({_JS_IDENT})\s*=(?![=>])""")
# `import { A, B as C } from "./x"` (an optional `type` keyword is a TS type-only import — its
# names are never string values, so it's simply left unmatched).
_JS_NAMED_IMPORT_RE = re.compile(r"""\bimport\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']""")
_JS_TEMPLATE_HOLE_RE = re.compile(r"\$\{([^}]*)\}")
# A `function [NAME](...)` signature's parameter list — one level of nested parens tolerated in
# `params` (enough for a simple call in a default value, e.g. `(role = pick())`).
_JS_FUNCTION_SIGNATURE_RE = re.compile(
    r"\bfunction\b(?:\s+[A-Za-z_$][\w$]*)?\s*\((?P<params>(?:[^()]|\([^()]*\))*)\)"
)
# An arrow function's parameter list — identified by what *follows* its closing `)` (an optional
# TS return-type annotation, then `=>`), the one shape a plain call expression's `(...)` can never
# be followed by in valid JS/TS syntax, so this doesn't false-trigger on an ordinary call.
_JS_ARROW_SIGNATURE_RE = re.compile(
    r"\((?P<params>(?:[^()]|\([^()]*\))*)\)\s*(?::\s*[^={};]+?)?\s*=>"
)
# `NAME = <value>` (optionally `NAME: Type = <value>`) inside a parameter list's own text.
_JS_PARAM_DEFAULT_RE = re.compile(rf"(?<![\w$.])({_JS_IDENT})\s*(?::[^,=()]+?)?=(?!=)")
# `if`/`for`/`while` (each followed by a `(...)` guard clause) and `else` (no guard) — JS/TS
# control-flow keywords whose single-statement body, when not wrapped in `{ ... }`, still needs
# its own "virtual" block in `_js_block_path_at` (round 39: `if (cond) role = "x";`, with no
# braces at all, must be recognized as conditional the same way `if (cond) { role = "x"; }` is).
_JS_CONTROL_KEYWORD_RE = re.compile(r"\b(if|else|for|while)\b")


def _js_word_is_property(text: str, position: int) -> bool:
    """Whether the identifier/keyword-spelled word starting at `position` is reached via a
    preceding `.` (`obj.if`, `obj.for` — legal JS property names spelled like reserved words) —
    never a real keyword token in that case."""
    j = position - 1
    while j >= 0 and text[j].isspace():
        j -= 1
    return j >= 0 and text[j] == "."


def _js_block_path_at(text: str, spans: list[tuple[int, int]], position: int) -> tuple[int, ...]:
    """The stack of enclosing block ids immediately before `position` — `()` at module top level,
    a longer tuple inside nested blocks. Each `{` outside a string-literal span (a `{`/`}` inside
    a string's own text must not count — `spans`, from `js_string_literals`, excludes it) opens a
    new, uniquely-numbered *real* block; its matching `}` closes it. A declaration's block path
    being a *prefix* of a use site's block path means the declaration's scope encloses that use
    site — real JS lexical (block) scoping for `const`/`let`, and object literals/array literals
    never contain a declaration statement, so the extra "blocks" this coarse counting adds for
    them are harmless: they can only make a use site look more deeply nested than its true
    statement-level scope, which prefix-matching absorbs without ever finding an unrelated
    declaration (each block id is unique and genuinely encloses only what's textually between its
    `{` and matching `}`). A reasonable, conservative-direction approximation for `var` too (real
    `var` is function-scoped and can escape an enclosing non-function block this treats as its
    own scope — narrower than reality, so this can only miss a `var` that's really in scope,
    never wrongly resolve one that isn't).

    JS/TS control flow doesn't require braces at all: `if (cond) role = "x";` is exactly as
    conditional as `if (cond) { role = "x"; }`, but has no `{`/`}` for the counting above to see
    at all. Immediately after an `if`/`for`/`while`'s own `(...)` guard (or immediately after a
    bare `else`, unless it's `else if` — the following `if` handles its own body, so `else` alone
    needs no separate scope) — whenever the next token isn't `{` — a *virtual* block (same
    globally-unique id space as real ones, so it deepens a block path the identical way) is
    pushed instead, standing in for the single statement that follows. It's popped at that
    statement's own terminating `;` (tracked with `;` inside any open, un-skipped `(...)`
    correctly excluded — a `for (init; cond; update)`'s own semicolons don't end anything), along
    with every other virtual block still open at that same `;` (closing a chain of braceless
    `if (a) if (b) x = 1;` together, since they all end at the one shared statement). A `do`
    loop's braceless body (terminated by a following `while (...)`, not a `;`) isn't modeled —
    ponytail: rare in practice, upgrade path is a real JS/TS parser, same ceiling as the rest of
    this file's JS/TS scanning.

    An arrow function's concise (expression) body is the exact same shape: `(role = "x") => role`
    has no `{ ... }` either, so its parameter needs the identical treatment — a virtual block
    pushed right after `=>` whenever it isn't immediately followed by `{`, closed the same way at
    the expression's own terminating `;` (round 40).
    """
    stack: list[tuple[bool, int]] = []  # (is_real_block, id)
    next_id = 0
    span_end_by_start = dict(spans)
    paren_depth = 0
    length = len(text)

    def skip_ws(j: int) -> int:
        while j < length and text[j].isspace():
            j += 1
        return j

    i = 0
    while i < position:
        if i in span_end_by_start:
            i = span_end_by_start[i] + 1
            continue
        char = text[i]
        if char == "(":
            paren_depth += 1
            i += 1
            continue
        if char == ")":
            paren_depth = max(0, paren_depth - 1)
            i += 1
            continue
        if char == "{":
            stack.append((True, next_id))
            next_id += 1
            i += 1
            continue
        if char == "}":
            while stack and not stack[-1][0]:
                stack.pop()
            if stack:
                stack.pop()
            i += 1
            continue
        if char == ";" and paren_depth == 0:
            while stack and not stack[-1][0]:
                stack.pop()
            i += 1
            continue
        if char.isalpha():
            keyword_match = _JS_CONTROL_KEYWORD_RE.match(text, i)
            if keyword_match is not None and not _js_word_is_property(text, i):
                keyword = keyword_match.group(1)
                j = keyword_match.end()
                if keyword in ("if", "for", "while"):
                    j = skip_ws(j)
                    if j < length and text[j] == "(":
                        depth = 0
                        k = j
                        while k < length:
                            if k in span_end_by_start:
                                k = span_end_by_start[k] + 1
                                continue
                            if text[k] == "(":
                                depth += 1
                            elif text[k] == ")":
                                depth -= 1
                                if depth == 0:
                                    k += 1
                                    break
                            k += 1
                        j = k
                j = skip_ws(j)
                next_word = _JS_IDENT_RE.match(text, j)
                is_else_if = keyword == "else" and next_word is not None and next_word.group(0) == "if"
                if not is_else_if and (j >= length or text[j] != "{"):
                    stack.append((False, next_id))
                    next_id += 1
                i = keyword_match.end()
                continue
        if char == "=" and text.startswith("=>", i):
            # An arrow function's own concise (expression) body needs the identical treatment:
            # `(role = "x") => role` has no `{ ... }` to give the parameter its own scope, but
            # the parameter is still only meaningful for the single expression that follows —
            # exactly the same "single statement, no braces" shape a braceless `if`/`for`/`while`
            # body already gets above, closed by that expression's own terminating `;` the same
            # way (round 40 — a `{ ... }` body already worked; a concise one didn't).
            j = skip_ws(i + 2)
            if j >= length or text[j] != "{":
                stack.append((False, next_id))
                next_id += 1
            i += 2
            continue
        i += 1
    return tuple(id_ for _, id_ in stack)


def resolve_js_identifier(modules: JsModules, path: Path, name: str, position: int) -> frozenset[str]:
    """Every statically-known string `name` could hold at `position` in `path`, honoring lexical
    shadowing: among every binding of `name` whose `block_path` encloses `position` (is a prefix
    of the position's own block path), the innermost one wins — matching real JS scoping instead
    of "whichever declaration is textually last" (round 36). Within that binding's own timeline,
    replay every write up to and including `position`: a write at the binding's own block path is
    deterministic (a straight-line statement) and *replaces* the reachable set; a write at a
    deeper block path is only conditionally reached and *adds* to it, never discarding a value
    that's still reachable when that branch doesn't run (round 38). Empty when `name` has no
    enclosing binding at all, or nothing in its timeline up to `position` resolved to anything
    statically known."""
    groups = modules.declarations.get(path, {}).get(name)
    if not groups:
        return frozenset()
    block_path = _js_block_path_at(
        modules.texts[path], _outside_literals(modules.literals[path]), position
    )
    best_timeline: _JsTimeline | None = None
    best_group_block_path: tuple[int, ...] | None = None
    best_len = -1
    for group_block_path, timeline in groups:
        depth = len(group_block_path)
        if depth <= len(block_path) and block_path[:depth] == group_block_path and depth > best_len:
            best_len = depth
            best_group_block_path = group_block_path
            best_timeline = timeline
    if best_timeline is None:
        return frozenset()
    reachable: set[str] = set()
    for write_position, write_block_path, write_values in best_timeline:
        if write_position > position:
            break
        if write_block_path == best_group_block_path:
            reachable = set(write_values)
        else:
            reachable |= write_values
    return frozenset(reachable)


def _template_value(modules: JsModules, path: Path, raw: str, literal_start: int) -> str | None:
    """A template literal's content with each `${NAME}` hole filled from a known constant —
    Empty if any hole is anything but a bare known identifier (`${provider()}`, `${a + b}`,
    `${cfg.model}`: genuinely dynamic, or at least not statically known here). Every hole is
    resolved as of `literal_start` (the enclosing template literal's own opening-backtick
    offset), not its own position inside `raw` — every hole in one template literal shares that
    literal's lexical scope regardless of where inside the (otherwise opaque, from this scanner's
    perspective) literal text it sits. Multiple reachable values per hole (round 38 — a hole can
    resolve to more than one statically-known string when it's behind a conditional write)
    combine with the surrounding literal text and each other via `_combine`."""
    segments: list[frozenset[str]] = []
    pos = 0
    for hole in _JS_TEMPLATE_HOLE_RE.finditer(raw):
        segments.append(frozenset({raw[pos : hole.start()]}))
        name = hole.group(1).strip()
        segments.append(resolve_js_identifier(modules, path, name, literal_start))
        pos = hole.end()
    segments.append(frozenset({raw[pos:]}))
    return _combine(segments)


def _combine(parts: list[frozenset[str]]) -> frozenset[str]:
    """Cartesian-product join of each operand's own set of statically-known possible values —
    empty (unresolvable) if any operand's own set is empty, or if the combined product would be
    pathologically large.

    ponytail: the size cap is a hard limit, not real path-sensitive analysis — a real hardcode
    fed by more than a couple of conditional branches in one expression is vanishingly unlikely,
    and even if missed here, the same literal value very likely also appears reachable through a
    simpler branch elsewhere in the same file. Upgrade path: a real JS/TS parser with proper
    control-flow analysis, same ceiling as the rest of this file's JS/TS scanning."""
    if any(not part for part in parts):
        return frozenset()
    size = 1
    for part in parts:
        size *= len(part)
        if size > 256:
            return frozenset()
    return frozenset("".join(combo) for combo in itertools.product(*parts))


def js_string_expr_at(modules: JsModules, path: Path, pos: int) -> tuple[frozenset[str], int]:
    """Fold the string expression starting at `pos`: operands (a quoted literal, a template
    literal with known-constant holes, a known constant name, or a parenthesized expression)
    joined by `+`. Returns `(values, end)`; `values` is the set of statically-known strings the
    expression could resolve to — empty when any operand is genuinely dynamic (an unknown name, a
    call, a member expression) or nothing string-like starts here; more than one value when an
    operand is itself multi-valued (round 38 — reachable through more than one conditional write).
    A `+` chain is followed to its end either way, so `end` is past the whole expression."""
    text = modules.texts[path]
    literals = modules.literals[path]
    length = len(text)

    def skip_ws(i: int) -> int:
        while i < length and text[i].isspace():
            i += 1
        return i

    parts: list[frozenset[str]] = []
    i = skip_ws(pos)
    while True:
        if i < length and text[i] in JS_QUOTE_CHARS and i in literals:
            end, quote = literals[i]
            raw = text[i + 1 : end]
            part = _template_value(modules, path, raw, i) if quote == "`" else frozenset({raw})
            i = end + 1
        elif i < length and text[i] == "(":
            part, i = js_string_expr_at(modules, path, i + 1)
            i = skip_ws(i)
            if i < length and text[i] == ")":
                i += 1
            else:
                return frozenset(), i
        elif (match := _JS_IDENT_RE.match(text, i)) is not None:
            part = resolve_js_identifier(modules, path, match.group(0), i)
            i = match.end()
            # `name.member` / `name(...)` / `name[...]` — not the bare constant, a real
            # expression: unresolvable, and the chain stops here.
            if skip_ws(i) < length and text[skip_ws(i)] in ".([":
                return frozenset(), i
        else:
            return frozenset(), i
        parts.append(part)
        j = skip_ws(i)
        if j < length and text[j] == "+" and not text.startswith("++", j):
            i = skip_ws(j + 1)
            continue
        return _combine(parts), i


def _outside_literals(literals: dict[int, tuple[int, str]]) -> list[tuple[int, int]]:
    return sorted((start, end) for start, (end, _) in literals.items())


def _inside_literal(spans: list[tuple[int, int]], offset: int) -> bool:
    # ponytail: linear scan; spans per file are small. Upgrade path: bisect on span starts.
    return any(start <= offset <= end for start, end in spans)


def _resolve_js_module(importing: Path, specifier: str) -> Path | None:
    """A relative import specifier (`./config`, `../shared/models.js`, `./dir` -> `dir/index.*`)
    resolved to a file. Package/bare specifiers (`openai`, `@scope/pkg`) are never constants
    sources here and resolve to nothing."""
    if not specifier.startswith("."):
        return None
    base = (importing.parent / specifier).resolve()
    candidates = [base] + [base.with_name(base.name + ext) for ext in JS_TS_EXTS]
    candidates += [base / f"index{ext}" for ext in JS_TS_EXTS]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _find_real_brace(text: str, spans: list[tuple[int, int]], start: int) -> int:
    """The offset of the first `{` at or after `start` that isn't inside a string-literal span
    (`spans`), or -1 if none exists — a plain `text.find("{", start)` can't tell a real body
    brace from one that only coincidentally appears inside a template literal's `${` earlier in
    the search range."""
    pos = start
    while True:
        brace = text.find("{", pos)
        if brace == -1 or not _inside_literal(spans, brace):
            return brace
        pos = brace + 1


def _js_param_default_events(
    modules: JsModules, path: Path, text: str, spans: list[tuple[int, int]]
) -> list[tuple[str, tuple[int, ...], int, frozenset[str]]]:
    """`(name, body_block_path, name_position, values)` for every default parameter value —
    `function f(role = "system") { ... }`, `(role = "system") => { ... }`, and `(role = "system")
    => role` (a concise/expression arrow body, round 40 — `_js_block_path_at` gives it its own
    virtual scope the same way a braceless `if`/`for`/`while` body already gets one, so it needs
    no special-casing here beyond anchoring at the right position). `function`'s own body is
    never optional (real JS/TS has no concise form for it) — a `function` signature with no `{`
    body at all before its own terminating `;` is an ambient/overload signature and is skipped.
    `body_block_path` is the block path *inside* that body (where the parameter is actually
    usable), not the block path of the signature itself. A parameter is always mutable (JS
    parameters are never `const`), so it's just another timeline-bearing binding — a later
    reassignment inside the function body attaches to it exactly like a `let`'s would.
    """
    events: list[tuple[str, tuple[int, ...], int, frozenset[str]]] = []
    length = len(text)

    def skip_ws(j: int) -> int:
        while j < length and text[j].isspace():
            j += 1
        return j

    def collect(match: re.Match, body_block_path: tuple[int, ...]) -> None:
        params = match.group("params")
        params_start = match.start("params")
        for default_match in _JS_PARAM_DEFAULT_RE.finditer(params):
            name_pos = params_start + default_match.start(1)
            if _inside_literal(spans, name_pos):
                continue
            value_pos = params_start + default_match.end()
            values, _ = js_string_expr_at(modules, path, value_pos)
            events.append((default_match.group(1), body_block_path, name_pos, values))

    for match in _JS_FUNCTION_SIGNATURE_RE.finditer(text):
        if _inside_literal(spans, match.start()):
            continue
        after_signature = match.end()
        # `function`'s own return-type annotation (`function f(x): void {`) isn't part of this
        # regex's own match, so the real body brace can sit an arbitrary distance past
        # `after_signature` — a forward, span-aware search (not a fixed "next non-ws char" check,
        # which the arrow branch below can use instead) is still needed here.
        brace = _find_real_brace(text, spans, after_signature)
        semicolon = text.find(";", after_signature)
        if brace == -1 or (semicolon != -1 and semicolon < brace):
            continue  # no real body (an ambient/overload signature) — nothing to model
        collect(match, _js_block_path_at(text, spans, brace + 1))

    for match in _JS_ARROW_SIGNATURE_RE.finditer(text):
        if _inside_literal(spans, match.start()):
            continue
        j = skip_ws(match.end())
        # A `{` right after `=>` anchors inside a real block body; anything else is a concise
        # (expression) body with no block of its own — `_js_block_path_at` already opens a
        # virtual scope right after `=>` for that case, so anchoring the query there reflects it.
        # Unlike the function branch above, this never searches forward for a later `{`: an
        # arrow's concise body can itself legitimately contain an unrelated `{` (a template
        # literal's `${`, a parenthesized object literal like `=> ({ role })`), and guessing
        # which one is "the real body" is exactly the coincidental, fragile behavior this fix
        # replaces with one rule that's correct unconditionally.
        body_anchor = j + 1 if j < length and text[j] == "{" else match.end()
        collect(match, _js_block_path_at(text, spans, body_anchor))

    return events


def js_modules(paths: Iterable[Path]) -> JsModules:
    """Strip comments, index string literals, and resolve every file's `const`/`let`/`var`
    declarations and parameter defaults (scope-, write-order-, and branch-aware — see
    `JsModules`) across relative named imports to a fixed point."""
    modules = JsModules(texts={})
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        modules.texts[path] = strip_js_comments(text, jsx=path.suffix in (".jsx", ".tsx"))
        modules.literals[path] = js_string_literals(modules.texts[path])
        modules.declarations[path] = {}
    resolved_paths = {path.resolve(): path for path in modules.texts}

    for _ in range(50):
        previous = {path: dict(values) for path, values in modules.declarations.items()}
        for path, text in modules.texts.items():
            spans = _outside_literals(modules.literals[path])
            groups: dict[str, dict[tuple[int, ...], _JsTimeline]] = {}

            def add_write(
                name: str,
                group_block_path: tuple[int, ...],
                write_block_path: tuple[int, ...],
                position: int,
                values: frozenset[str],
            ) -> None:
                groups.setdefault(name, {}).setdefault(group_block_path, []).append(
                    (position, write_block_path, values)
                )

            for match in _JS_NAMED_IMPORT_RE.finditer(text):
                source = _resolve_js_module(path, match.group(2))
                source = resolved_paths.get(source) if source is not None else None
                if source is None:
                    continue
                for item in match.group(1).split(","):
                    names = item.replace("\n", " ").split()
                    if not names or names[0] == "type":
                        continue
                    exported, local = names[0], names[-1]
                    # An export's value, from an importer's perspective, is whatever the source
                    # module's top-level code has settled it to by the time module evaluation
                    # finishes — resolved at the end of the source text, not at its start (which
                    # would see no writes at all yet, in this timeline model — every write in a
                    # module-level `()` binding is, by definition, a real assignment that runs
                    # during module evaluation).
                    values = resolve_js_identifier(
                        modules, source, exported, len(modules.texts[source])
                    )
                    add_write(local, (), (), match.start(), values)

            decl_matches = [
                match for match in _JS_DECL_RE.finditer(text) if not _inside_literal(spans, match.start())
            ]
            param_events = _js_param_default_events(modules, path, text, spans)
            # A declaration's or parameter's own `NAME =` must not also be counted as a bare
            # reassignment of itself below (both match `_JS_ASSIGNMENT_RE`'s shape too).
            exempt_positions = {match.start(2) for match in decl_matches} | {
                name_pos for _, _, name_pos, _ in param_events
            }

            for match in decl_matches:
                name = match.group(2)
                block_path = _js_block_path_at(text, spans, match.start(2))
                values, _ = js_string_expr_at(modules, path, match.end())
                add_write(name, block_path, block_path, match.start(2), values)

            for name, block_path, position, values in param_events:
                add_write(name, block_path, block_path, position, values)

            # A bare reassignment attaches to whichever already-known binding most tightly
            # encloses it (the innermost group block path that's a prefix of the reassignment's
            # own) — the same shadowing priority `resolve_js_identifier` itself uses — at *its
            # own* block path, so `resolve_js_identifier` can tell a deterministic write (same
            # depth as the binding) from a conditional one (deeper) and combine values
            # accordingly. One with no enclosing binding at all (an untracked/global name) is
            # simply dropped.
            for match in _JS_ASSIGNMENT_RE.finditer(text):
                if match.start(1) in exempt_positions or _inside_literal(spans, match.start(1)):
                    continue
                name = match.group(1)
                candidates = groups.get(name)
                if not candidates:
                    continue
                assignment_block_path = _js_block_path_at(text, spans, match.start(1))
                best_block_path: tuple[int, ...] | None = None
                best_len = -1
                for candidate_block_path in candidates:
                    depth = len(candidate_block_path)
                    if (
                        depth <= len(assignment_block_path)
                        and assignment_block_path[:depth] == candidate_block_path
                        and depth > best_len
                    ):
                        best_len = depth
                        best_block_path = candidate_block_path
                if best_block_path is not None:
                    values, _ = js_string_expr_at(modules, path, match.end())
                    candidates[best_block_path].append((match.start(1), assignment_block_path, values))

            modules.declarations[path] = {
                name: sorted(
                    (
                        (block_path, sorted(timeline, key=lambda entry: (entry[0], entry[1])))
                        for block_path, timeline in block_paths.items()
                    )
                )
                for name, block_paths in groups.items()
            }
        if modules.declarations == previous:
            break
    return modules


def js_string_values(modules: JsModules, path: Path) -> list[tuple[int, str]]:
    """Every statically-resolvable string expression in `path`, as `(offset, value)` in the
    comment-stripped text. Candidate starts are every string literal and every use of a known
    constant name (not a `.member` access); a resolved expression consumes its whole `+` chain,
    so a folded expression's every possible value (round 38 — an expression reachable through a
    conditional write can have more than one) is reported once each, as a whole, not also per
    fragment."""
    text = modules.texts[path]
    spans = _outside_literals(modules.literals[path])
    known_names = modules.declarations.get(path, {})
    starts = {start for start, _ in spans}
    for match in _JS_IDENT_RE.finditer(text):
        if match.group(0) not in known_names or _inside_literal(spans, match.start()):
            continue
        if text[: match.start()].rstrip().endswith("."):
            continue  # `obj.NAME` is a member access, not the constant
        starts.add(match.start())

    values: list[tuple[int, str]] = []
    consumed_until = -1
    for start in sorted(starts):
        if start < consumed_until:
            continue
        resolved, end = js_string_expr_at(modules, path, start)
        if resolved:
            values.extend((start, value) for value in sorted(resolved))
            consumed_until = end
    return values
