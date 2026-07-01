import struct
from pathlib import Path
from ssotk import convert


def _make_uncompressed_dds(path, w=2, h=2):
    # Minimal uncompressed 32-bit BGRA DDS; Pillow reads these without a DXT decoder.
    hd = bytearray(128)
    hd[0:4] = b"DDS "
    struct.pack_into("<I", hd, 4, 124)            # dwSize
    struct.pack_into("<I", hd, 8, 0x0000100F)     # CAPS|HEIGHT|WIDTH|PITCH|PIXELFORMAT
    struct.pack_into("<I", hd, 12, h)
    struct.pack_into("<I", hd, 16, w)
    struct.pack_into("<I", hd, 20, w * 4)         # pitch
    struct.pack_into("<I", hd, 76, 32)            # ddspf.dwSize
    struct.pack_into("<I", hd, 80, 0x41)          # DDPF_RGB | DDPF_ALPHAPIXELS
    struct.pack_into("<I", hd, 88, 32)            # dwRGBBitCount
    struct.pack_into("<I", hd, 92, 0x00FF0000)    # R mask
    struct.pack_into("<I", hd, 96, 0x0000FF00)    # G mask
    struct.pack_into("<I", hd, 100, 0x000000FF)   # B mask
    struct.pack_into("<I", hd, 104, 0xFF000000)   # A mask
    struct.pack_into("<I", hd, 108, 0x1000)       # DDSCAPS_TEXTURE
    path.write_bytes(bytes(hd) + b"\xff\x00\x00\xff" * (w * h))


def test_dds_to_png(tmp_path):
    src = tmp_path / "t.dds"
    _make_uncompressed_dds(src)
    dst = tmp_path / "t.png"
    out = convert.dds_to_png(src, dst)
    assert out.exists()
    assert out.read_bytes()[:8] == b"\x89PNG\r\n\x1a\n"


def test_tga_to_crn_no_payload_returns_none(tmp_path):
    src = tmp_path / "ref.tga"
    src.write_bytes(b"\x00" * 32)  # no "Hx"
    assert convert.tga_to_crn(src, tmp_path / "ref.crn") is None


def test_tga_to_crn_extracts_hx(tmp_path):
    src = tmp_path / "tex.tga"
    src.write_bytes(b"\x00" * 24 + b"Hx" + b"PAYLOAD")
    out = convert.tga_to_crn(src, tmp_path / "tex.crn")
    assert out is not None
    assert out.read_bytes() == b"Hx" + b"PAYLOAD"


_EMPTY = {"dds": 0, "tga": 0, "crn_only": 0, "skipped": 0, "skipped_existing": 0, "failed": 0}


def test_convert_tree_filters_types(tmp_path):
    root = tmp_path / "root"
    (root / "a").mkdir(parents=True)
    _make_uncompressed_dds(root / "a" / "tex.dds")
    (root / "a" / "ref.tga").write_bytes(b"\x00" * 32)  # under stub threshold -> skipped
    (root / "a" / "model.fbx").write_bytes(b"\x00" * 8)  # not a requested type
    result = convert.convert_tree(root, tmp_path / "out", {"dds", "tga"})
    assert result == {**_EMPTY, "dds": 1, "skipped": 1}
    assert (tmp_path / "out" / "a" / "tex.png").exists()


def test_convert_tree_counts_unrecognized_dds_as_failed(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "bad.dds").write_bytes(b"DDS " + b"\x00" * 20)
    result = convert.convert_tree(root, tmp_path / "out", {"dds"})
    assert result == {**_EMPTY, "failed": 1}


def test_convert_tree_tga_extract_only_without_crunch(tmp_path, monkeypatch):
    root = tmp_path / "root"
    root.mkdir()
    # Above the stub-size threshold so we don't short-circuit.
    (root / "tex.tga").write_bytes(b"\x00" * 300 + b"Hx" + b"PAYLOAD")
    monkeypatch.setattr("ssotk.config.find_optional", lambda _name: None)
    result = convert.convert_tree(root, tmp_path / "out", {"tga"})
    assert result == {**_EMPTY, "crn_only": 1}
    assert (tmp_path / "out" / "tex.crn").exists()


def test_convert_tree_skips_existing_png_on_rerun(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _make_uncompressed_dds(root / "tex.dds")
    out = tmp_path / "out"
    first = convert.convert_tree(root, out, {"dds"})
    assert first == {**_EMPTY, "dds": 1}
    second = convert.convert_tree(root, out, {"dds"})
    assert second == {**_EMPTY, "skipped_existing": 1}


def test_convert_tree_force_reconverts(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    _make_uncompressed_dds(root / "tex.dds")
    out = tmp_path / "out"
    convert.convert_tree(root, out, {"dds"})
    result = convert.convert_tree(root, out, {"dds"}, force=True)
    assert result == {**_EMPTY, "dds": 1}


def test_convert_tree_filters_tga_stubs(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    # Under-threshold tga stubs are filtered without a read.
    (root / "stub.tga").write_bytes(b"\x00" * 50)
    result = convert.convert_tree(root, tmp_path / "out", {"tga"})
    assert result == {**_EMPTY, "skipped": 1}
