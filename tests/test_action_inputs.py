from tests.action_inputs import extract_fields


def test_extract_fields_returns_independent_mutable_inputs() -> None:
    first = extract_fields()
    second = extract_fields()
    first[0]["name"] = "changed"
    first.pop()
    assert second == extract_fields()
    assert first != second
