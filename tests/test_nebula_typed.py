from ssotk import nebula
from ssotk.vocab import KH
from tests.fixtures.actor_scene import ACTOR_SCENE
from tests.fixtures.dreiren_scene import DREIREN_SCENE


def test_scene_exposes_objects_list():
    scene = nebula.parse(ACTOR_SCENE)
    assert len(scene.objects) == scene.object_count == 1
    assert scene.objects[0].class_name == "Actor"


def test_multi_object_scene_populates_objects_list():
    scene = nebula.parse(DREIREN_SCENE)
    assert len(scene.objects) == 2
    assert scene.objects[0].class_name == "Actor"


def test_object_typed_accessors_return_none_when_absent():
    scene = nebula.parse(ACTOR_SCENE)
    obj = scene.objects[0]
    assert obj.triple(0xDEADBEEF) is None
    assert obj.get_int(0xDEADBEEF) is None
    assert obj.get_float(0xDEADBEEF) is None
    assert obj.get_string(999) is None


def test_object_get_float_reads_ieee754_bits():
    scene = nebula.parse(DREIREN_SCENE)
    for obj in scene.objects:
        t = obj.triple(0x09595084)
        if t is not None:
            assert obj.get_float(0x09595084) == 1.0
            return
    raise AssertionError("expected triple not found in DREIREN")


def test_known_hash_constants_defined():
    assert KH.OWN == 0x06D029F4
    assert KH.PARENT == 0x0FA8A5A4
    assert KH.ID == 0x040034D4
    assert KH.BREED_ID == 0x0BB21504
    assert KH.LEVEL == 0x06A98294
    assert KH.PRICE == 0x01DA6705
    assert KH.JS_PRICE == 0x088D4FB5
    assert KH.SC_PRICE == 0x008D4FA5


def test_records_carry_offset_length_and_raw():
    scene = nebula.parse(ACTOR_SCENE)
    for r in scene.objects[0].records:
        assert r.length > 0
        assert len(r.raw) == r.length
        assert r.offset >= 0


def test_nebula_header_flavor_identified():
    from ssotk import identify
    scene_head = ACTOR_SCENE[:32]
    assert identify.classify(scene_head, ".scene") == "nebula"
