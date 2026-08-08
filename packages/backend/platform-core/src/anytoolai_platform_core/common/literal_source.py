from __future__ import annotations

from anytoolai_platform_core.common.strict_json import parse_strict_json

LITERAL_SOURCE_PREFIX = "literal:"

# Kept as an alias so existing importers (workflow mappings, handoff payloads, config loader)
# don't need call-site changes; `parse_strict_json` is the general-purpose primitive, also used
# for provider structured-output parsing which has nothing to do with `literal:` sources.
parse_strict_literal_json = parse_strict_json
