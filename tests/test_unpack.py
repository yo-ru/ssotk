import subprocess
from pathlib import Path
from ssotk import unpack


def test_build_command_uses_overwrite_flag():
    cmd = unpack.build_command(
        Path("q.exe"), Path("s.bms"), Path("p_0.csaheader"), Path("out/p_0")
    )
    assert cmd[0] == "q.exe"
    assert "-o" in cmd
    assert cmd[-3:] == [str(Path("s.bms")), str(Path("p_0.csaheader")), str(Path("out/p_0"))]


def test_unpack_all_pairs_each_csaheader(tmp_path, monkeypatch):
    pf = tmp_path / "PackFiles"
    pf.mkdir()
    for i in (0, 1):
        (pf / f"p_{i:08d}.csaheader").write_bytes(b"\x00")
        (pf / f"p_{i:08d}.csa").write_bytes(b"\x00")
    called = []
    monkeypatch.setattr(
        unpack, "unpack_archive", lambda h, out, label="": called.append(h) or out / h.stem
    )
    outs = unpack.unpack_all(pf, tmp_path / "extracted")
    assert len(called) == 2
    assert len(outs) == 2


def test_unpack_archive_warns_not_raises_on_nonzero_exit(tmp_path, monkeypatch, capsys):
    # quickbms returns non-zero for recoverable cases (e.g. one entry with a
    # misread size near the end of an archive) yet still extracts the rest, so
    # a non-zero exit must warn and continue, never abort the batch.
    monkeypatch.setattr(unpack.config, "find_quickbms", lambda: Path("q.exe"))

    class FakeCompleted:
        returncode = 3

    def fake_run(cmd, *args, **kwargs):
        if kwargs.get("check") and FakeCompleted.returncode != 0:
            raise subprocess.CalledProcessError(FakeCompleted.returncode, cmd)
        return FakeCompleted()

    monkeypatch.setattr(unpack.subprocess, "run", fake_run)
    header = tmp_path / "p_0.csaheader"
    header.write_bytes(b"\x00")
    out = unpack.unpack_archive(header, tmp_path / "extracted")
    assert out == tmp_path / "extracted" / "p_0"
    assert "exit 3" in capsys.readouterr().out


def test_unpack_archive_prints_progress_with_count(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(unpack.config, "find_quickbms", lambda: Path("q.exe"))
    out_root = tmp_path / "extracted"

    class FakeCompleted:
        returncode = 0

    def fake_run(cmd, *args, **kwargs):
        # Simulate quickbms extracting one file into the output dir.
        d = out_root / "p_0"
        d.mkdir(parents=True, exist_ok=True)
        (d / "x.dds").write_bytes(b"x")
        return FakeCompleted()

    monkeypatch.setattr(unpack.subprocess, "run", fake_run)
    header = tmp_path / "p_0.csaheader"
    header.write_bytes(b"\x00")
    unpack.unpack_archive(header, out_root, label="[3/31] ")
    out = capsys.readouterr().out
    assert "[3/31]" in out
    assert "p_0" in out
    assert "1 files" in out
