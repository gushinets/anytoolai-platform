from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.common.html_re import cdata, close_tag, comment, declaration, open_tag, processing

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

# List container token types produced by ordered (`1.`/`1)`) and unordered (`-`/`*`/`+`)
# CommonMark lists — the marker character lives in `token.markup`, not `token.type`, so all
# three unordered markers and both ordered delimiters collapse to the same token types.
# Copy-ready plain text still reads fine with list markers, so these are allowed on top of
# `_PLAIN_TEXT_TOKEN_TYPES`, unlike the stricter `_has_markup` allowlist. A list item's own
# `inline` content is still walked by `_flatten_tokens`, so disallowed markup nested inside a
# list item (e.g. "- **Important**") is still caught via its `strong_open`/`strong_close`
# children.
_PLAIN_TEXT_WITH_LISTS_TOKEN_TYPES = _PLAIN_TEXT_TOKEN_TYPES | frozenset(
    {
        "ordered_list_open",
        "ordered_list_close",
        "bullet_list_open",
        "bullet_list_close",
        "list_item_open",
        "list_item_close",
    }
)

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

# GFM task-list checkboxes ("- [ ] todo", "1. [x] done") aren't tokenized as a distinct
# construct by this parser (the task-lists rule is a separate, unloaded plugin) — they parse
# as an ordinary list item whose inline content happens to start with literal "[ ]"/"[x]".
# The team-lead-specified plain_text allowance only covers plain "ordered/unordered list
# markers", not checkbox syntax, so it's matched by regex against the item's own leading text
# instead. The checkbox may be the item's *entire* content ("- [ ]", no task text at all), not
# just a prefix followed by more text, so the marker must match at end-of-string too, not only
# when trailing whitespace follows it.
_TASK_LIST_CHECKBOX_RE = re.compile(r"^\[[ xX]\](?:\s|$)")


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


# Of CommonMark's six HTML5 constructs, only open/close tags are actual elements; comments,
# processing instructions, declarations like doctype, and CDATA render nothing and don't
# prove "html" formatting on their own - a reply consisting solely of "<!-- note -->" is not
# meaningfully HTML output. A prefix check on the whole token content isn't enough: when a
# comment/PI/declaration/CDATA isn't followed by a blank line, markdown-it-py's block grammar
# lumps it together with any real tag that follows into ONE html_block token (e.g.
# "<!-- note --><p>real</p>"), and leading whitespace before a comment-only token also isn't
# itself a "<!"/"<?" prefix. Reusing the same construct regexes the tokenizer itself uses
# (rather than a hand-rolled prefix or tag-name check) keeps this in lockstep with whatever
# CommonMark/GFM syntax markdown-it-py recognizes.
_NON_ELEMENT_CONSTRUCT_RE = re.compile(f"(?:{comment}|{processing}|{declaration}|{cdata})")
_ELEMENT_TAG_RE = re.compile(f"(?:{open_tag}|{close_tag})")


def _starts_non_element_construct(content: str, index: int) -> bool:
    if content.startswith(("<!--", "<![CDATA[", "<?"), index):
        return True
    return content.startswith("<!", index) and content[index + 2 : index + 3].isalpha()


def _content_has_element_tag(content: str) -> bool:
    index = 0
    while True:
        start = content.find("<", index)
        if start == -1:
            return False
        if _starts_non_element_construct(content, start):
            match = _NON_ELEMENT_CONSTRUCT_RE.match(content, start)
            if match is None:
                # An unterminated comment/PI/declaration/CDATA swallows the rest of the
                # block verbatim (same as a real HTML parser would), so nothing after it
                # can count as a live tag.
                return False
            index = match.end()
            continue
        if _ELEMENT_TAG_RE.match(content, start) is not None:
            return True
        index = start + 1


def _has_html_tag(value: str) -> bool:
    return any(
        token.type.startswith("html_") and _content_has_element_tag(token.content)
        for token in _flatten_tokens(_HTML_RENDERER.parse(value))
    )


# Elements whose content a browser never renders as text. `script`/`style` content is also
# raw text to a real HTML parser (no tags/entities inside), which HTMLParser already honors.
# ponytail: element-name list only; CSS/attribute hiding (`hidden`, `display:none`) is not
# detected -- needs a real layout engine, add if a live model ever produces it.
_NON_RENDERED_ELEMENTS = frozenset({"script", "style", "template"})


class _HtmlTextExtractor(HTMLParser):
    """Collects the text a browser would actually show: character references decoded
    (`convert_charrefs`), tags/comments/doctypes dropped, `_NON_RENDERED_ELEMENTS` content
    skipped. A single structural pass, so an escaped `&lt;p&gt;` stays literal text instead of
    being re-read as a tag the way strip-tags-then-unescape would risk."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        if tag in _NON_RENDERED_ELEMENTS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in _NON_RENDERED_ELEMENTS and self._skip_depth:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip_depth:
            self.parts.append(data)


def _html_text_content(value: str) -> str:
    extractor = _HtmlTextExtractor()
    extractor.feed(value)
    extractor.close()
    return "".join(extractor.parts)


def _has_visible_text(value: str, text_format: Any) -> bool:
    """Whether `value` shows the reader any non-whitespace text *in the format it will be
    rendered as* -- the same string is content in one format and empty in another:
    `&nbsp;` is six literal characters as plain_text but a lone space as html/markdown.

    Code review findings this shape replaces a format-blind token walk for: plain_text was
    entity-decoded like markup ("&nbsp;" rejected as blank), and a regex tag-strip counted
    `<style>`/`<script>`/`<template>` content as visible text."""
    if text_format == "html":
        rendered = _html_text_content(value)
    elif text_format == "markdown":
        # Rendering first makes every markdown construct (code spans/blocks, entities, raw
        # HTML passthrough) reduce to the one question the HTML extractor already answers.
        rendered = _html_text_content(_HTML_RENDERER.render(value))
    else:
        # plain_text / omitted: copied to the client literally, never parsed. Disallowed
        # markup is a separate check (`_has_disallowed_plain_text_markup`).
        rendered = value
    return rendered.strip() != ""


def _tokenize_markdown(value: str) -> list[Any]:
    # Shared by `_has_markdown` and `_has_disallowed_plain_text_markup` so both check the
    # identical parse (same escaping, same renderer instance) and only diverge on which
    # token types/structure they treat as disallowed — a single pipeline instead of two
    # independently-maintained copies that could quietly drift apart.
    escaped = _escape_alnum_flanked_asterisks(value)
    return list(_flatten_tokens(_MARKDOWN_RENDERER.parse(escaped)))


def _has_markdown(value: str) -> bool:
    return any(token.type not in _PLAIN_TEXT_TOKEN_TYPES for token in _tokenize_markdown(value))


def _has_markup(value: str) -> bool:
    return _has_html_construct(value) or _has_markdown(value)


def _has_disallowed_plain_text_markup(value: str) -> bool:
    # Same as `_has_markup`, except a CommonMark list — ordered or unordered, flat or
    # nested, with real item content — is treated as allowed copy-ready formatting (the
    # Linear-decided policy allows "ordered/unordered list markers" without a nesting-depth
    # restriction; a list nested inside something already disallowed, e.g. a blockquote, is
    # still rejected via that construct's own token type below). Everything else is still
    # rejected, including cases a plain token-type allowlist alone would miss: an empty list
    # item ("-", "1)") carries no meaningful content, and a GFM task-list checkbox
    # ("- [ ] todo") is checkbox formatting, not a plain list marker, even though this parser
    # tokenizes it as an ordinary list item (see `_TASK_LIST_CHECKBOX_RE`).
    if _has_html_construct(value):
        return True
    tokens = _tokenize_markdown(value)
    for index, token in enumerate(tokens):
        if token.type not in _PLAIN_TEXT_WITH_LISTS_TOKEN_TYPES:
            return True
        if token.type == "list_item_open":
            # markdown-it-py guarantees every `_open` token has a matching `_close`, so
            # `list_item_open` is never the last token in the stream.
            next_token = tokens[index + 1]
            if next_token.type == "list_item_close":
                # An empty item ("-", "1)") carries no meaningful content — not a real list.
                return True
            if next_token.type == "paragraph_open":
                inline_token = tokens[index + 2]
                if inline_token.type == "inline" and _TASK_LIST_CHECKBOX_RE.match(inline_token.content):
                    return True
    return False
