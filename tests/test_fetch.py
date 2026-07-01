import io
import zipfile

from ssotk import fetch


def _fake_quickbms_zip() -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("quickbms.exe", b"MZ-quickbms")
        z.writestr("quickbms_4gb_files.exe", b"MZ-other")  # must NOT be picked
    return buf.getvalue()


def test_fetch_quickbms_extracts_correct_exe(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch.config, "BIN_DIR", tmp_path / "bin")
    monkeypatch.setattr(fetch, "_download", lambda url: _fake_quickbms_zip())
    p = fetch.fetch_quickbms()
    assert p == tmp_path / "bin" / "quickbms.exe"
    assert p.read_bytes() == b"MZ-quickbms"


def test_fetch_skips_when_present(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch.config, "BIN_DIR", tmp_path / "bin")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "crunch_unity.exe").write_bytes(b"existing")

    def boom(url):
        raise AssertionError("should not download when the file already exists")

    monkeypatch.setattr(fetch, "_download", boom)
    p = fetch.fetch_crunch()
    assert p.read_bytes() == b"existing"


def test_fetch_force_redownloads(tmp_path, monkeypatch):
    monkeypatch.setattr(fetch.config, "BIN_DIR", tmp_path / "bin")
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "crunch_unity.exe").write_bytes(b"old")
    monkeypatch.setattr(fetch, "_download", lambda url: b"new")
    p = fetch.fetch_crunch(force=True)
    assert p.read_bytes() == b"new"
