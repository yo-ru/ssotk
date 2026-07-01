from ssotk import nebula
from tests.fixtures.actor_scene import ACTOR_SCENE
from tests.fixtures.dreiren_scene import DREIREN_SCENE
from tests.fixtures.metaldetector_scene import METALDETECTOR_SCENE
from tests.fixtures.nasset_widget import NASSET_WIDGET


def test_reader_reads_u32_le():
    r = nebula.Reader(b"\x98\x00\x00\x00\x05\x00\x00\x00")
    assert r.u32() == 152
    assert r.u32() == 5
    assert r.tell() == 8


def test_parse_total_size_matches_file():
    scene = nebula.parse(ACTOR_SCENE)
    assert scene.total_size == len(ACTOR_SCENE)


def test_string_table_recovers_actor():
    strings = nebula.read_string_table(ACTOR_SCENE)
    assert "Actor" in strings


def test_parse_exposes_root_class():
    scene = nebula.parse(ACTOR_SCENE)
    assert scene.root_class == "Actor"


def test_actor_scene_full_coverage():
    scene = nebula.parse(ACTOR_SCENE)
    assert scene.coverage == 1.0


def test_actor_scene_decodes_nine_entries():
    scene = nebula.parse(ACTOR_SCENE)
    assert len(scene.entries) == 9
    assert scene.unknown_tokens == []
    string_entry = next(e for e in scene.entries if e["type"] == 0x204)
    assert string_entry["value"] == "Actor"
    big_a02 = next(e for e in scene.entries if e["value"] == 0x0F6B14D5)
    assert big_a02["type"] == 0x0A02


def test_to_json_roundtrips():
    import json
    scene = nebula.parse(ACTOR_SCENE)
    obj = json.loads(nebula.to_json(scene))
    assert obj["root_class"] == "Actor"
    assert obj["coverage"] == 1.0
    assert len(obj["entries"]) == 9


def test_metaldetector_full_coverage():
    scene = nebula.parse(METALDETECTOR_SCENE)
    assert scene.coverage == 1.0


def test_metaldetector_recovers_record_strings():
    scene = nebula.parse(METALDETECTOR_SCENE)
    assert "Mesh" in scene.strings
    assert "CowGPS" in scene.strings
    assert scene.root_class == "Mesh"


def test_dreiren_multi_object_full_coverage():
    scene = nebula.parse(DREIREN_SCENE)
    assert scene.object_count == 2
    assert scene.coverage == 1.0


def test_dreiren_recovers_animation_names():
    scene = nebula.parse(DREIREN_SCENE)
    assert scene.root_class == "Actor"
    assert "HorseIdle" in scene.strings
    assert "Camilla_Idle" in scene.strings


def test_float_token_decodes_to_real_float():
    # 0x0a03 raw bits 0x3f800000 must reinterpret to 1.0, not the int 1065353216.
    scene = nebula.parse(DREIREN_SCENE)
    entry = next(e for e in scene.entries if e["type"] == 0x0A03 and e["key"] == "0x09595084")
    assert entry["value"] == 1.0


def test_header_flavor_detected_not_scene():
    assert nebula._is_header_flavor(NASSET_WIDGET)
    assert not nebula._is_header_flavor(ACTOR_SCENE)


def test_header_flavor_full_coverage():
    scene = nebula.parse(NASSET_WIDGET)
    assert scene.object_count == 1
    assert scene.coverage == 1.0


def test_header_flavor_recovers_widget_class_and_strings():
    scene = nebula.parse(NASSET_WIDGET)
    assert scene.root_class == "PureImageKeyWidget"
    assert "VerticalBox" in scene.strings
    assert "GUI_Icon_HW_LeftClickLeft" in scene.strings
