from __future__ import annotations

import re
import unicodedata
from html.parser import HTMLParser
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


# Every content-bearing element the HTML spec's rendering section hides by name
# (`display: none` in the user-agent stylesheet) -- taken from the spec as a set rather than
# grown one review finding at a time. HTMLParser never synthesizes the implicit closes a
# browser does, so an element allowed to omit its end tag would leave the skip active and hide
# everything after it; every entry therefore has a mandatory end tag, with one exception
# handled explicitly: `rp`, whose implicit closes are emulated via `_RP_IMPLICIT_CLOSE_*`
# below. Deliberately absent: `head` (optional end tag, and no bounded set of closers -- its
# text-bearing children are listed instead), the spec's void entries (`base`, `link`, `meta`,
# ... -- no content), and `noscript` (rendered whenever scripting is off, which a copied
# message can't assume).
# ponytail: element names only; CSS/attribute hiding (`hidden`, `display:none`) is not
# detected -- needs style resolution, add if a live model ever produces it.
_NON_RENDERED_ELEMENTS = frozenset(
    {"datalist", "noembed", "noframes", "rp", "script", "style", "template", "title"}
)

# "An rp element's end tag can be omitted if [it] is immediately followed by an rb, rt, rtc or
# rp element, or if there is no more content in the parent element" (HTML spec, optional tags).
# ponytail: the parent is assumed to be ruby/rtc -- an `rp` anywhere else is invalid HTML.
# Code is not message text: the placeholder check reads around it, and a code element breaks a
# bracket so "[Your <code>x</code> Name]" is not read as one label.
_CODE_ELEMENTS = frozenset({"code", "pre"})
_TEXT_BARRIER = "\x00"

# A line break or a block boundary is visible whitespace: "<p>Dear [Your<br>Name]</p>" shows
# "[Your" and "Name]" on two lines, not "[YourName]". Inline elements ("<b>", "<span>") add nothing.
# ponytail: element names only; CSS `display` is not resolved, same as _NON_RENDERED_ELEMENTS.
_LINE_BREAK_ELEMENTS = frozenset(
    {
        "address", "article", "aside", "blockquote", "br", "dd", "details", "div", "dl", "dt",
        "figcaption", "figure", "footer", "h1", "h2", "h3", "h4", "h5", "h6", "header", "hr", "li",
        "main", "nav", "ol", "p", "section", "summary", "table", "td", "th", "tr", "ul",
    }
)

_RP_IMPLICIT_CLOSE_START_TAGS = frozenset({"rb", "rt", "rtc", "rp"})
_RP_IMPLICIT_CLOSE_END_TAGS = frozenset({"ruby", "rtc"})

# Foreign (SVG/MathML) content is the one place a trailing `/` really self-closes an element
# -- but not everywhere inside it: at the spec's integration points children are parsed as
# HTML again (HTMLParser lowercases tag names, hence `foreignobject`).
_FOREIGN_CONTENT_ROOTS = frozenset({"svg", "math"})
_SVG_HTML_INTEGRATION_POINTS = frozenset({"foreignobject", "desc", "title"})
_MATHML_TEXT_INTEGRATION_POINTS = frozenset({"mi", "mo", "mn", "ms", "mtext"})
_ANNOTATION_XML_HTML_ENCODINGS = frozenset({"text/html", "application/xhtml+xml"})


def _is_html_integration_point(foreign_root: str, tag: str, attrs: Any) -> bool:
    if foreign_root == "svg":
        return tag in _SVG_HTML_INTEGRATION_POINTS
    if tag in _MATHML_TEXT_INTEGRATION_POINTS:
        return True
    return tag == "annotation-xml" and any(
        name == "encoding" and (value or "").lower() in _ANNOTATION_XML_HTML_ENCODINGS
        for name, value in attrs
    )


def _close_innermost(open_elements: list[Any], tag: str, *, key: Any = lambda entry: entry) -> None:
    """Pops the innermost open `tag` plus anything left open inside it -- the recovery a
    browser applies to mis-nested tags. A tag that isn't open is ignored: HTMLParser doesn't
    pair end tags with start tags, so a stray `</style>` must not end a `<template>`."""
    for index in range(len(open_elements) - 1, -1, -1):
        if key(open_elements[index]) == tag:
            del open_elements[index:]
            return


class _HtmlTextExtractor(HTMLParser):
    """One structural pass over HTML, answering both questions the html format asks:
    `parts` is the text a browser would actually show (character references decoded via
    `convert_charrefs`, tags/comments/doctypes dropped, `_NON_RENDERED_ELEMENTS` content
    skipped -- so an escaped `&lt;p&gt;` stays literal text instead of being re-read as a tag),
    and `saw_element_tag` is whether any real element tag occurred at all (comments, doctypes,
    processing instructions and CDATA render nothing and don't count)."""

    def __init__(self, *, skip_code: bool = False) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._skip_code = skip_code
        self._skipped = _NON_RENDERED_ELEMENTS | (_CODE_ELEMENTS if skip_code else frozenset())
        self.saw_element_tag = False
        self._open_non_rendered: list[str] = []
        # (tag, is_foreign) per namespace switch: an svg/math root enters foreign content, an
        # integration point inside it re-enters HTML. A bare depth counter can't tell
        # `<svg><title/>` (foreign: self-closed) from `<svg><foreignObject><template/>`
        # (HTML again: the slash is ignored and the template stays open).
        self._namespace_contexts: list[tuple[str, bool]] = []

    def _foreign_root(self) -> str | None:
        if self._namespace_contexts and self._namespace_contexts[-1][1]:
            return self._namespace_contexts[-1][0]
        return None

    def handle_starttag(self, tag: str, attrs: Any) -> None:
        self.saw_element_tag = True
        foreign_root = self._foreign_root()
        if tag in _FOREIGN_CONTENT_ROOTS:
            self._namespace_contexts.append((tag, True))
        elif foreign_root and _is_html_integration_point(foreign_root, tag, attrs):
            self._namespace_contexts.append((tag, False))
        if tag in _RP_IMPLICIT_CLOSE_START_TAGS and self._open_non_rendered[-1:] == ["rp"]:
            self._open_non_rendered.pop()
        # A boundary is visible output like data: only an element in visible context marks one.
        if not self._open_non_rendered:
            self._mark_boundary(tag)
        if tag in self._skipped:
            self._open_non_rendered.append(tag)

    def handle_startendtag(self, tag: str, attrs: Any) -> None:
        # HTMLParser's default treats `<x/>` as start + end. HTML itself ignores the slash on
        # its own elements -- `<template/>Hidden` leaves the template open in a browser --
        # and honors it only in foreign content (`<svg><title/></svg>`). Foreign-ness is read
        # *before* the start tag, which may itself switch namespace (svg `<title/>`).
        was_foreign = self._foreign_root() is not None
        self.handle_starttag(tag, attrs)
        if was_foreign or tag not in self._skipped:
            self.handle_endtag(tag)

    def _mark_boundary(self, tag: str) -> None:
        if self._skip_code and tag in _CODE_ELEMENTS:
            self.parts.append(_TEXT_BARRIER)
        elif tag in _LINE_BREAK_ELEMENTS:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        self.saw_element_tag = True
        # A stray end tag of an element that is not open renders nothing, so it marks no code
        # boundary ("[Your</code> Name]" still reads "[Your Name]").
        closes_open_code = tag in _CODE_ELEMENTS and tag in self._open_non_rendered
        _close_innermost(self._namespace_contexts, tag, key=lambda context: context[0])
        if tag in _RP_IMPLICIT_CLOSE_END_TAGS and self._open_non_rendered[-1:] == ["rp"]:
            self._open_non_rendered.pop()
        _close_innermost(self._open_non_rendered, tag)
        if not self._open_non_rendered and (closes_open_code or tag not in _CODE_ELEMENTS):
            self._mark_boundary(tag)

    def handle_data(self, data: str) -> None:
        if not self._open_non_rendered:
            self.parts.append(data)


def _parse_html(value: str, *, skip_code: bool = False) -> _HtmlTextExtractor:
    extractor = _HtmlTextExtractor(skip_code=skip_code)
    extractor.feed(value)
    extractor.close()
    return extractor


def _has_html_tag(value: str) -> bool:
    """Whether html-format `value` contains a real element tag. Asked of the HTML parser, not
    the Markdown one: CommonMark reads four leading spaces or a tab as an indented code block,
    so ordinarily-indented HTML (`    <p>Ready.</p>`) showed no `html_*` token at all and was
    rejected as "missing markup"."""
    return _parse_html(value).saw_element_tag


def _html_text_content(value: str, *, skip_code: bool = False) -> str:
    return "".join(_parse_html(value, skip_code=skip_code).parts)


def _reader_text(value: str, text_format: Any, *, skip_code: bool = False) -> str:
    """The text the reader of `value` sees in the format it will be rendered as."""
    if text_format == "html":
        return _html_text_content(value, skip_code=skip_code)
    if text_format == "markdown":
        # Rendering first makes every markdown construct (code spans/blocks, entities, raw
        # HTML passthrough, links and reference definitions) reduce to the one question the
        # HTML extractor already answers.
        return _html_text_content(_HTML_RENDERER.render(value), skip_code=skip_code)
    # plain_text / omitted: copied to the client literally, never parsed. Disallowed markup is
    # a separate check (`_has_disallowed_plain_text_markup`).
    return value


def _has_visible_text(value: str, text_format: Any) -> bool:
    """Whether `value` shows the reader any non-whitespace text *in the format it will be
    rendered as* -- the same string is content in one format and empty in another:
    `&nbsp;` is six literal characters as plain_text but a lone space as html/markdown.

    Code review findings this shape replaces a format-blind token walk for: plain_text was
    entity-decoded like markup ("&nbsp;" rejected as blank), and a regex tag-strip counted
    `<style>`/`<script>`/`<template>` content as visible text."""
    return _reader_text(value, text_format).strip() != ""


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


# Plain-text list markers a CommonMark parser does not treat as lists. A bullet character at the
# start of a line is a list item even alone (prose never starts with one); a dash or a lettered
# marker ("a)", "(b)") can start a sentence, a signature or a quote, so two such lines are a list
# and one is not.
_BULLET_LINE = re.compile(r"^\s*[•●▪‣]\s+\S")
_PLAIN_LIST_LINE = re.compile(r"^\s*(?:[–—]|\(?[A-Za-z]\))\s+\S")


def _has_list(value: str) -> bool:
    """True when the text is a CommonMark ordered or unordered list, has a line that starts with a
    bullet character, or has two or more lines that start with a dash or a lettered marker."""
    if any(
        token.type in ("bullet_list_open", "ordered_list_open") for token in _tokenize_markdown(value)
    ):
        return True
    lines = value.splitlines()
    if any(_BULLET_LINE.match(line) for line in lines):
        return True
    return sum(bool(_PLAIN_LIST_LINE.match(line)) for line in lines) >= 2  # noqa: PLR2004


# A fill-in-the-blank slot: a bracketed label the sender was meant to replace ("[Your Name]",
# "[Your Full Name Here]", "[Project Price]", "[Insert date]", "[Price:]", "[YOUR_NAME]",
# "[Имя клиента]", "[Укажите срок]"). The contract has two parts, so its boundary is known instead
# of found by review:
#   1. What is read: the text the reader sees in the requested format (`_reader_text`). Formatting
#      inside the brackets disappears ("[**Your Name**]", "[<b>Your Name</b>]" read "[Your Name]"),
#      a line break or block boundary is whitespace ("[Your<br>Name]"), invisible format
#      characters (zero-width space, soft hyphen) are dropped, a genuine Markdown link loses its
#      brackets, an undefined reference or a definition without a destination stays literal, and
#      code ("<code>", "<pre>", Markdown code spans and blocks) is not read at all.
#   2. What is a slot: a label made only of slot words (_SLOT_FIELD or _SLOT_FILLER) and blank or
#      separator characters (_SLOT_SEPARATORS), with at least one field word. Any other character
#      means a filled value or prose: a word outside the vocabulary ("[Price is fixed]",
#      "[Client update]", "[Project brief]", "[sic]", "[FYI]"), a digit or a sign ("[Price: $100]",
#      "[Date: 2026-10-24]", "[Rate: 5%]"). A label without a field word is prose too ("[Here]").
# So a slot is missed only when its label holds a word or character outside the contract
# ("[Your Awesome Name]", "[Price: TBD]"), and prose is rejected only when it consists of slot
# words and separators alone ("[Project Price]" as a heading), which this contract defines as a
# slot. Only ASCII square brackets are read; full-width "［ ］" and "【 】" are not. Curly and angle
# brackets are legitimate in code and HTML; a product opts in through A06 forbidden_patterns.
# ponytail: EN/RU vocabulary; extend it when live output shows a missed label or a product ships
# another language.
_SLOT_FIELD = (
    r"names?|fullname|information|info|details|contacts?|email|mail|phone|number|date|time"
    r"|deadline|address|company|title|position|role|signature|link|url|website|portfolio"
    r"|description|price|cost|rate|fee|budget|amount|total|timeline|duration|location"
    r"|имя|имени|фамили\w*|отчеств\w*|контакт\w*|данн(?:ые|ых)|телефон\w*|почт\w*|дат[аеуы]"
    r"|срок\w*|адрес\w*|компани\w*|названи\w*|должност\w*|подпис\w*|ссылк\w*|сайт\w*|описани\w*"
    r"|цен[аеуы]|стоимост\w*|ставк\w*|сумм[аеуы]|бюджет\w*|реквизит\w*|номер\w*"
)
_SLOT_FILLER = (
    r"your|yours|my|our|their|his|her|client|client's|clients|customer|customer's|recipient"
    r"|recipient's|company's|project|project's|business|legal|full|first|last|middle|job|start|end"
    r"|delivery|due|hourly|final|estimated|home|work|mobile|office|personal|team|agency|e"
    r"|here|goes|go|of|the|a|an|to|for|and|or|with|in|insert|enter|add|type|write|put|fill|please"
    r"|ваш\w*|мо[йеёия]|мои|наш\w*|клиент\w*|заказчик\w*|проект\w*|полн\w*|электронн\w*"
    r"|мобильн\w*|рабоч\w*|итогов\w*|начал\w*|окончани\w*|сдач\w*|оплат\w*"
    r"|здесь|сюда|тут|укажите|вставьте|введите|впишите|и|или|для|по"
)
_SLOT_FIELD_WORD = re.compile(_SLOT_FIELD, re.IGNORECASE)
_SLOT_WORD = re.compile(f"{_SLOT_FIELD}|{_SLOT_FILLER}", re.IGNORECASE)
# A word is letters and apostrophes only, so "_" and "-" separate words ("[YOUR_NAME]",
# "[Client-Name]", "e-mail"); a blank ("[Name: ____]", "[Price:]") is separators alone.
_LABEL_WORD = re.compile(r"[^\W\d_](?:[^\W\d_]|')*")
_SLOT_SEPARATORS = re.compile(r"[\s/,&.:_\-\u2026]*")
# No nested brackets, so a bounded label stays linear.
_BRACKETED = re.compile(r"\[([^\[\]\x00]{1,100})\]")


def _is_slot_label(label: str) -> bool:
    label = label.replace("\u2019", "'")
    words = _LABEL_WORD.findall(label)
    return (
        bool(words)
        and _SLOT_SEPARATORS.fullmatch(_LABEL_WORD.sub(" ", label)) is not None
        and all(_SLOT_WORD.fullmatch(word) for word in words)
        and any(_SLOT_FIELD_WORD.fullmatch(word) for word in words)
    )


def _without_format_characters(value: str) -> str:
    return "".join(char for char in value if unicodedata.category(char) != "Cf")


def _find_unfilled_placeholder(text: str, text_format: Any) -> str | None:
    """The first slot (see the contract above) in what the reader of `text` sees, or None."""
    visible = _without_format_characters(_reader_text(text, text_format, skip_code=True))
    for match in _BRACKETED.finditer(visible):
        if _is_slot_label(match.group(1)):
            return " ".join(match.group(0).split())
    return None
