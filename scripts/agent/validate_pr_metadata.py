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
LINEAR_URL_PATTERN = re.compile(
    r"https://linear\.app/paveldik/issue/(ANY-[1-9][0-9]*)(?=/|[\s<]|$)"
    r"(?:/[^\s<]*)?"
)


class MetadataError(ValueError):
    pass


def validate_pr_metadata(title: str, body: str) -> None:
    title_match = TITLE_PATTERN.fullmatch(title)
    if title_match is None:
        raise MetadataError('Invalid PR title. Required format: "ANY-<number> - <summary>"')

    section_match = LINEAR_SECTION_PATTERN.search(body)
    urls = (
        LINEAR_URL_PATTERN.findall(section_match.group("content"))
        if section_match is not None
        else []
    )
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
