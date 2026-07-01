import pytest
from ssotk import config


def test_find_quickbms_prefers_bin(tmp_path, monkeypatch):
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    exe = bin_dir / "quickbms.exe"
    exe.write_bytes(b"MZ")
    monkeypatch.setattr(config, "BIN_DIR", bin_dir)
    monkeypatch.setattr(config.shutil, "which", lambda _: None)
    assert config.find_quickbms() == exe


def test_find_quickbms_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "BIN_DIR", tmp_path / "bin")
    monkeypatch.setattr(config.shutil, "which", lambda _: None)
    with pytest.raises(FileNotFoundError):
        config.find_quickbms()


def test_csa_bms_path_points_into_scripts():
    assert config.CSA_BMS.name == "star_stable_online.bms"
    assert config.CSA_BMS.parent == config.SCRIPTS_DIR
