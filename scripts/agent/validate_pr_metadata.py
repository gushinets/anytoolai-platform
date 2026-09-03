#!/usr/bin/env python3
from __future__ import annotations

import os
import re
import sys

TITLE_PATTERN = re.compile(r"^(ANY-[1-9][0-9]*) - \S.*$")
LINEAR_SECTION_PATTERN = re.compile(
    r"^## Linear issue[ \t]*\r?\n(?P<content>.*?)(?=^## |\Z)",
    re.MULTILINE | re.DOTALL,
)
FENCE_PATTERN = re.compile(
    r"^ {0,3}(?P<marker>`{3,}|~{3,})(?P<rest>[^\r\n]*)(?:\r?\n)?$"
)
LINEAR_URL_PATTERN = re.compile(
    r"https://linear\.app/paveldik/issue/(ANY-[1-9][0-9]*)(?=/|[\s<]|$)"
    r"(?:/[^\s<]*)?"
)


class MetadataError(ValueError):
    pass


def _without_fenced_code_blocks(markdown: str) -> str:
    rendered_lines: list[str] = []
    fence_character = ""
    fence_length = 0
    for line in markdown.splitlines(keepends=True):
        fence_match = FENCE_PATTERN.fullmatch(line)
        if fence_character:
            if fence_match is not None:
                marker = fence_match.group("marker")
                if (
                    marker[0] == fence_character
                    and len(marker) >= fence_length
                    and not fence_match.group("rest").strip()
                ):
                    fence_character = ""
                    fence_length = 0
            rendered_lines.append("\n" if line.endswith("\n") else "")
            continue

        if fence_match is not None:
            marker = fence_match.group("marker")
            rest = fence_match.group("rest")
            if marker[0] != "`" or "`" not in rest:
                fence_character = marker[0]
                fence_length = len(marker)
                rendered_lines.append("\n" if line.endswith("\n") else "")
                continue

        rendered_lines.append(line)
    return "".join(rendered_lines)


def validate_pr_metadata(title: str, body: str) -> None:
    title_match = TITLE_PATTERN.fullmatch(title)
    if title_match is None:
        raise MetadataError('Invalid PR title. Required format: "ANY-<number> - <summary>"')

    sections = list(LINEAR_SECTION_PATTERN.finditer(_without_fenced_code_blocks(body)))
    if len(sections) != 1:
        raise MetadataError(
            "The PR body must contain exactly one rendered '## Linear issue' section."
        )

    urls = LINEAR_URL_PATTERN.findall(sections[0].group("content"))
    if len(urls) != 1:
        raise MetadataError(
            "The PR body must contain exactly one full Linear issue URL in "
            "the '## Linear issue' section."
        )

    title_issue = title_match.group(1)
    if urls[0] != title_issue:
        raise MetadataError(
            f"PR title issue {title_issue} does not match Linear URL issue {urls[0]}."
        )


def main() -> int:
    try:
        validate_pr_metadata(os.environ.get("PR_TITLE", ""), os.environ.get("PR_BODY", ""))
    except MetadataError as exc:
        print(f"PR metadata validation failed: {exc}", file=sys.stderr)
        return 1
    print("PR metadata is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
