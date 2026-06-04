from app import _compact_custom_fields


def test_compact_custom_fields_keeps_only_filled_field_boxes():
    fields = [
        {"label": " name ", "value": " Competition "},
        {"label": "", "value": ""},
        {"label": "role", "value": "Team lead"},
    ]

    assert _compact_custom_fields(fields) == [
        {"label": "General subfield", "value": "Competition"},
        {"label": "General subfield", "value": "Team lead"},
    ]
