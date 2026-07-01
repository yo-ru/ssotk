import json

from ssotk import text


def test_decode_value_create():
    payload = b"\x05\x00\x01\x42\xff\x71\xff\x64\xff\x60\xff\x73\xff\x64\x00\x00"
    assert text.decode_value(payload) == "Create"


def test_decode_value_rejects_bad_leader():
    assert text.decode_value(b"\x00\x00\x00\x00") is None
    assert text.decode_value(b"") is None


def test_to_json_is_valid_json():
    payload = text.to_json({"KEY_A": "value a", "KEY_B": "value b"})
    parsed = json.loads(payload)
    assert parsed == {"KEY_A": "value a", "KEY_B": "value b"}
