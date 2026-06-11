REQUIRED_ACTION_DEFINITION_FIELDS = {
    "action_type",
    "version",
    "input_schema_ref",
    "output_schema_ref",
    "executor",
}


def validate_action_definition(data: dict, source: str) -> list[str]:
    missing = sorted(REQUIRED_ACTION_DEFINITION_FIELDS - set(data))
    return [f"{source}: missing {field}" for field in missing]
