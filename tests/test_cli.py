import pytest
from pathlib import Path
from ssotk.cli import build_parser, main
from ssotk import cli


def test_parser_has_all_subcommands():
    parser = build_parser()
    sub = {a.dest: a for a in parser._subparsers._group_actions} if parser._subparsers else {}
    # Parse each known subcommand without error.
    for cmd in ["unpack", "identify", "scene", "deserialize", "convert", "all"]:
        ns = parser.parse_args([cmd] if cmd != "scene" and cmd != "deserialize" else [cmd, "x"])
        assert ns.command == cmd


def test_main_unknown_command_returns_nonzero(capsys):
    with pytest.raises(SystemExit):
        main(["bogus"])


def test_identify_command_prints_counts(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(cli.identify, "scan", lambda root: {"dds": 3, "nebula": 2})
    rc = cli.main(["identify", "--root", str(tmp_path)])
    assert rc == 0
    assert "dds" in capsys.readouterr().out


def test_scene_command_writes_json(tmp_path, monkeypatch):
    src = tmp_path / "a.scene"
    src.write_bytes(b"\x00")
    out = tmp_path / "out"

    class FakeScene:
        pass

    monkeypatch.setattr(cli.nebula, "parse", lambda data: FakeScene())
    monkeypatch.setattr(cli.nebula, "to_json", lambda s: '{"root_class":"Actor"}')
    rc = cli.main(["scene", str(src), "--out", str(out)])
    assert rc == 0
    assert (out / "a.json").read_text().startswith("{")
