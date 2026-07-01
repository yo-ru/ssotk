import struct
from ssotk import identify


def test_classify_dds():
    assert identify.classify(b"DDS " + b"\x00" * 60, ".tga") == "dds"


def test_classify_fmod_bank():
    head = b"RIFF" + b"\x00\x00\x00\x00" + b"FEV " + b"FMT "
    assert identify.classify(head, ".bank") == "fmod_bank"


def test_classify_nebula_preamble():
    # u32 size, 5, 10, 5, 0, 0xffffffff, 0x00000100, ...
    head = struct.pack("<7I", 152, 5, 10, 5, 0, 0xFFFFFFFF, 0x00000100)
    assert identify.classify(head, ".scene") == "nebula"


def test_classify_tga_container_dxt():
    head = b"\x00" * 8 + b"DXT5" + b"\x00" * 12
    assert identify.classify(head, ".tga") == "tga_container"


def test_classify_fallback_extension():
    assert identify.classify(b"\x01\x02\x03\x04", ".fbx") == "fbx"
