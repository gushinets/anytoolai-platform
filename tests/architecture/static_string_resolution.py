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


@dataclass
class JsModules:
    """Comment-stripped JS/TS sources with their statically-known string constants."""

    texts: dict[Path, str]
    literals: dict[Path, dict[int, tuple[int, str]]] = field(default_factory=dict)
    constants: dict[Path, dict[str, str]] = field(default_factory=dict)


_JS_IDENT = r"[A-Za-z_$][\w$]*"
_JS_IDENT_RE = re.compile(_JS_IDENT)
# `const NAME = ...` / `let NAME: string = ...` / `export var NAME = ...` (`(?!=)`: not `==`).
_JS_CONST_DECL_RE = re.compile(rf"\b(?:const|let|var)\s+({_JS_IDENT})\s*(?::[^=;{{}}]+?)?=(?!=)")
# `import { A, B as C } from "./x"` (an optional `type` keyword is a TS type-only import — its
# names are never string values, so it's simply left unmatched).
_JS_NAMED_IMPORT_RE = re.compile(r"""\bimport\s*\{([^}]*)\}\s*from\s*["']([^"']+)["']""")
_JS_TEMPLATE_HOLE_RE = re.compile(r"\$\{([^}]*)\}")


def _template_value(raw: str, constants: dict[str, str]) -> str | None:
    """A template literal's content with each `${NAME}` hole filled from a known constant —
    `None` if any hole is anything but a bare known identifier (`${provider()}`, `${a + b}`,
    `${cfg.model}`: genuinely dynamic, or at least not statically known here)."""
    out: list[str] = []
    pos = 0
    for hole in _JS_TEMPLATE_HOLE_RE.finditer(raw):
        name = hole.group(1).strip()
        if name not in constants:
            return None
        out.append(raw[pos : hole.start()])
        out.append(constants[name])
        pos = hole.end()
    out.append(raw[pos:])
    return "".join(out)


def js_string_expr_at(modules: JsModules, path: Path, pos: int) -> tuple[str | None, int]:
    """Fold the string expression starting at `pos`: operands (a quoted literal, a template
    literal with known-constant holes, a known constant name, or a parenthesized expression)
    joined by `+`. Returns `(value, end)`; `value` is `None` when any operand is genuinely
    dynamic (an unknown name, a call, a member expression) or nothing string-like starts here.
    A `+` chain is followed to its end either way, so `end` is past the whole expression."""
    text = modules.texts[path]
    literals = modules.literals[path]
    constants = modules.constants[path]
    length = len(text)

    def skip_ws(i: int) -> int:
        while i < length and text[i].isspace():
            i += 1
        return i

    parts: list[str] = []
    resolvable = True
    i = skip_ws(pos)
    while True:
        if i < length and text[i] in JS_QUOTE_CHARS and i in literals:
            end, quote = literals[i]
            raw = text[i + 1 : end]
            part = _template_value(raw, constants) if quote == "`" else raw
            i = end + 1
        elif i < length and text[i] == "(":
            part, i = js_string_expr_at(modules, path, i + 1)
            i = skip_ws(i)
            if i < length and text[i] == ")":
                i += 1
            else:
                return None, i
        elif (match := _JS_IDENT_RE.match(text, i)) is not None:
            part = constants.get(match.group(0))
            i = match.end()
            # `name.member` / `name(...)` / `name[...]` — not the bare constant, a real
            # expression: unresolvable, and the chain stops here.
            if skip_ws(i) < length and text[skip_ws(i)] in ".([":
                return None, i
        else:
            return None, i
        if part is None:
            resolvable = False
        else:
            parts.append(part)
        j = skip_ws(i)
        if j < length and text[j] == "+" and not text.startswith("++", j):
            i = skip_ws(j + 1)
            continue
        return ("".join(parts) if resolvable else None), i


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


def js_modules(paths: Iterable[Path]) -> JsModules:
    """Strip comments, index string literals, and resolve every file's string constants
    (`const`/`let`/`var` bindings whose value folds) across relative named imports to a fixed
    point. Constants are one flat namespace per file (ponytail: no scope tracking — a shadowed
    same-named binding resolves to whichever declaration comes last; upgrade path: a real
    parser, as the module docstring already calls for)."""
    modules = JsModules(texts={})
    for path in paths:
        text = path.read_text(encoding="utf-8", errors="ignore")
        modules.texts[path] = strip_js_comments(text, jsx=path.suffix in (".jsx", ".tsx"))
        modules.literals[path] = js_string_literals(modules.texts[path])
        modules.constants[path] = {}
    resolved_paths = {path.resolve(): path for path in modules.texts}

    for _ in range(50):
        previous = {path: dict(values) for path, values in modules.constants.items()}
        for path, text in modules.texts.items():
            spans = _outside_literals(modules.literals[path])
            found: dict[str, str] = {}
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
                    value = modules.constants[source].get(exported)
                    if value is not None:
                        found[local] = value
            for match in _JS_CONST_DECL_RE.finditer(text):
                if _inside_literal(spans, match.start()):
                    continue
                value, _ = js_string_expr_at(modules, path, match.end())
                if value is not None:
                    found[match.group(1)] = value
            modules.constants[path] = found
        if modules.constants == previous:
            break
    return modules


def js_string_values(modules: JsModules, path: Path) -> list[tuple[int, str]]:
    """Every statically-resolvable string expression in `path`, as `(offset, value)` in the
    comment-stripped text. Candidate starts are every string literal and every use of a known
    constant name (not a `.member` access); a resolved expression consumes its whole `+` chain,
    so a folded value is reported once, as a whole, not also per fragment."""
    text = modules.texts[path]
    spans = _outside_literals(modules.literals[path])
    constants = modules.constants[path]
    starts = {start for start, _ in spans}
    for match in _JS_IDENT_RE.finditer(text):
        if match.group(0) not in constants or _inside_literal(spans, match.start()):
            continue
        if text[: match.start()].rstrip().endswith("."):
            continue  # `obj.NAME` is a member access, not the constant
        starts.add(match.start())

    values: list[tuple[int, str]] = []
    consumed_until = -1
    for start in sorted(starts):
        if start < consumed_until:
            continue
        value, end = js_string_expr_at(modules, path, start)
        if value is not None:
            values.append((start, value))
            consumed_until = end
    return values
