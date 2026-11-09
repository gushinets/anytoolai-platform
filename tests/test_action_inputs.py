from tests.action_inputs import extract_fields, extract_input


def test_extract_fields_returns_independent_mutable_inputs() -> None:
    first = extract_fields()
    second = extract_fields()
    first[0]["name"] = "changed"
    first.pop()
    assert second == extract_fields()
    assert first != second


def test_extract_input_preserves_overrides_and_isolates_nested_fields() -> None:
    default = extract_input()
    explicit = extract_input(source_text="custom", strict=False)
    assert default == {"source_text": "deadline budget deliverables", "fields": extract_fields()}
    assert explicit == {"source_text": "custom", "fields": extract_fields(), "strict": False}
    explicit["fields"][0]["name"] = "changed"
    assert default["fields"] == extract_fields()
