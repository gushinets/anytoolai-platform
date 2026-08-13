from __future__ import annotations

import re
import unicodedata
from typing import Any

from markdown_it import MarkdownIt

# A hand-rolled tag-name allowlist keeps missing real constructs (svg/math, custom
# elements like <x-card>, comments, doctypes) no matter how many names get added, and a
# bare `<[a-zA-Z][^>]*>` regex over-matches non-markup bracketed text like "<Tuesday>". A
# real HTML tokenizer resolves both: markdown-it-py's `html_inline`/`html_block` rules
# recognize every HTML5 construct (tags of any name, comments, doctypes, CDATA, ...) by
# parsing the actual grammar, not by enumerating known names.
_HTML_RENDERER = MarkdownIt("gfm-like")
_HTML_RENDERER.options["linkify"] = False
_HTML_RENDERER.options["html"] = True

# With `html` disabled, raw "<...>" is inert (never a markup signal here — _has_html_tag
# covers it separately), so only genuine CommonMark/GFM syntax (bold, tables, code fences,
# strikethrough, emphasis pairing rules, ...) is left to detect, all by the same real
# parser instead of a growing pile of regexes.
_MARKDOWN_RENDERER = MarkdownIt("gfm-like")
_MARKDOWN_RENDERER.options["linkify"] = False
_MARKDOWN_RENDERER.options["html"] = False

# Token types a plain paragraph of text (no formatting) produces on its own.
_PLAIN_TEXT_TOKEN_TYPES = frozenset({"paragraph_open", "paragraph_close", "inline", "text", "softbreak"})

# CommonMark's real emphasis rule allows an unspaced `*` to open/close emphasis intraword
# (unlike `_`), so a parser alone flags plain arithmetic/dimension expressions - numeric
# ("2*3*4"), variable ("a*b*c", "2*x*4"), symbolic ("L*W*H"), or localized (
# "Д*Ш*Г", "宽*高*深") - as italic. Escaping a `*` sitting directly between two alphanumeric
# characters makes CommonMark treat it as literal punctuation instead, while leaving
# whitespace/punctuation-flanked emphasis (e.g. "*actual*") to the parser's real rules.
# `str.isalnum()` is Unicode-aware (unlike an `[A-Za-z0-9]` character class), so this also
# covers non-ASCII scripts. A combining mark (Unicode category Mn/Mc/Me - accents, niqud,
# tashkil, matras, ...) is not itself alphanumeric but always attaches to whatever character
# precedes it, so a `*` right after one must be judged by that base character, not the mark -
# otherwise a mark stuck to punctuation (e.g. "!" + combining acute) would wrongly count as
# flanking material and swallow real emphasis. Only the left side needs this walk-back: marks
# trail their base character, so they never sit between `*` and the start of a word on the
# right.
_ASTERISK = re.compile(r"\*")


def _base_character_before(value: str, index: int) -> str | None:
    while index >= 0 and unicodedata.category(value[index]).startswith("M"):
        index -= 1
    return value[index] if index >= 0 else None


def _escape_alnum_flanked_asterisks(value: str) -> str:
    def _escape(match: re.Match[str]) -> str:
        index = match.start()
        before = _base_character_before(value, index - 1)
        after = value[index + 1] if index + 1 < len(value) else None
        if before is not None and before.isalnum() and after is not None and after.isalnum():
            return "\\*"
        return "*"

    return _ASTERISK.sub(_escape, value)


def _flatten_tokens(tokens: Any) -> Any:
    for token in tokens:
        yield token
        for child in token.children or ():
            yield child


def _flatten_token_types(tokens: Any) -> Any:
    for token in _flatten_tokens(tokens):
        yield token.type


def _has_html_construct(value: str) -> bool:
    # html_inline/html_block are the only token types the "html"-enabled parser adds on
    # top of the plain/markdown ones, so this is unaffected by any markdown syntax also
    # present in the same text. This covers all six HTML5 constructs CommonMark's grammar
    # recognizes (open tag, close tag, comment, processing instruction, declaration,
    # CDATA) - none of them belong in text that's supposed to be plain, even the four that
    # render nothing.
    return any(
        token_type.startswith("html_")
        for token_type in _flatten_token_types(_HTML_RENDERER.parse(value))
    )


# Of CommonMark's six HTML5 constructs, only open/close tags are actual elements; comments
# ("<!--"), processing instructions ("<?"), declarations like doctype ("<!DOCTYPE"), and
# CDATA ("<![CDATA[") render nothing and don't prove "html" formatting on their own - a
# reply consisting solely of "<!-- note -->" is not meaningfully HTML output. All four of
# those constructs start with "<!" or "<?", while an open tag starts "<" + letter and a
# close tag starts "</" + letter, so that two-character prefix alone tells them apart
# without needing to parse tag names or attributes.
_NON_ELEMENT_HTML_PREFIXES = ("<!", "<?")


def _has_html_tag(value: str) -> bool:
    return any(
        token.type.startswith("html_") and not token.content.startswith(_NON_ELEMENT_HTML_PREFIXES)
        for token in _flatten_tokens(_HTML_RENDERER.parse(value))
    )


def _has_markdown(value: str) -> bool:
    value = _escape_alnum_flanked_asterisks(value)
    return any(
        token_type not in _PLAIN_TEXT_TOKEN_TYPES
        for token_type in _flatten_token_types(_MARKDOWN_RENDERER.parse(value))
    )


def _has_markup(value: str) -> bool:
    return _has_html_construct(value) or _has_markdown(value)
