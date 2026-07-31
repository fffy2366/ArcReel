import pytest

from server.services.text_model_json import parse_model_json_object


def test_parse_model_json_object_accepts_fenced_json():
    assert parse_model_json_object('```json\n{"summary": "ok"}\n```') == {"summary": "ok"}


def test_parse_model_json_object_extracts_surrounded_object():
    assert parse_model_json_object('Here is the result:\n{"summary": "ok"}\nDone.') == {"summary": "ok"}


def test_parse_model_json_object_accepts_yaml_style_object():
    assert parse_model_json_object("{ summary: 'ok', characters: [] }") == {
        "summary": "ok",
        "characters": [],
    }


def test_parse_model_json_object_rejects_non_object():
    with pytest.raises(ValueError, match="JSON object"):
        parse_model_json_object('["not", "an", "object"]')
