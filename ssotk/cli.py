import argparse
import json
import sys
from pathlib import Path

from tqdm import tqdm

from . import config, convert, fetch, identify, mine, nebula, pxscript, text, unpack


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="ssotk", description="Star Stable Online toolkit")
    sub = p.add_subparsers(dest="command", required=True)

    u = sub.add_parser("unpack", help="unpack .csa archives via quickbms")
    u.add_argument("--archive", help="single archive base name, e.g. p_00000000")
    u.add_argument("--out", default="extracted", help="output root")

    i = sub.add_parser("identify", help="classify extracted files by magic bytes")
    i.add_argument("--root", default="extracted")
    i.add_argument("--json", action="store_true")

    s = sub.add_parser("scene", help="deserialize .scene files to JSON")
    s.add_argument("path", help="a .scene file or a directory to scan")
    s.add_argument("--out", default="out/scenes")

    d = sub.add_parser("deserialize", help="deserialize any Nebula-format file to JSON")
    d.add_argument("path")

    c = sub.add_parser("convert", help="convert dds/tga textures")
    c.add_argument("--root", default="extracted")
    c.add_argument("--out", default="out/converted")
    c.add_argument("--types", default="dds", help="comma-separated: dds, tga")
    c.add_argument("--workers", type=int, default=None, help="parallel workers (default: cpu count)")
    c.add_argument("--force", action="store_true", help="re-convert files even if output exists")

    ft = sub.add_parser("fetch-tools", help="download quickbms.exe + crunch_unity.exe into bin/")
    ft.add_argument("--force", action="store_true")

    px = sub.add_parser("pxscript", help="render a captured PXScript VM dump to near-source")
    px.add_argument("dump")
    px.add_argument("--out", default="-")

    tx = sub.add_parser("text", help="decode .text (translation) files to JSON")
    tx.add_argument("path")
    tx.add_argument("--out", default="-")

    m = sub.add_parser("mine", help="datamining pipelines (items, horses, translations, icons)")
    msub = m.add_subparsers(dest="mine_command", required=True)

    mi = msub.add_parser("items", help="extract player item catalog")
    mi.add_argument("--scene", default=str(mine.items.DEFAULT_SCENE))
    mi.add_argument("--translations", default=str(mine.items.DEFAULT_TRANSLATIONS))
    mi.add_argument("--out", default="out")

    mh = msub.add_parser("horses", help="extract horse breeds + variants")
    mh.add_argument("--scene", default=str(mine.horses.DEFAULT_SCENE))
    mh.add_argument("--out", default="out")

    mt = msub.add_parser("translations", help="decode a .text translation table to JSON")
    mt.add_argument("--source", default=str(mine.translations.DEFAULT_SOURCE))
    mt.add_argument("--out", default="out")
    mt.add_argument("--filename", default="translations_en.json")

    mic = msub.add_parser("icons", help="extract item icons/textures to PNG")
    mic.add_argument("--scene", default=str(mine.icons.DEFAULT_SCENE))
    mic.add_argument("--extracted", default=str(mine.icons.DEFAULT_EXTRACTED))
    mic.add_argument("--out", default="out")
    mic.add_argument("--workers", type=int, default=8)
    mic.add_argument("--force", action="store_true")
    mic.add_argument("ids", nargs="*", type=int)

    sub.add_parser(
        "all",
        help="unpack -> identify -> scenes -> mine translations/horses/items "
             "(excludes textures and icons)",
    )
    return p


def _cmd_unpack(args) -> int:
    if args.archive:
        header = config.DEFAULT_PACKFILES / f"{args.archive}.csaheader"
        unpack.unpack_archive(header, Path(args.out))
    else:
        unpack.unpack_all(config.DEFAULT_PACKFILES, Path(args.out))
    return 0


def _cmd_identify(args) -> int:
    counts = identify.scan(Path(args.root))
    if args.json:
        print(json.dumps(counts, indent=2))
    else:
        for t, n in counts.items():
            print(f"{n:>8}  {t}")
    return 0


def _cmd_scene(args) -> int:
    src = Path(args.path)
    targets = [src] if src.is_file() else sorted(src.rglob("*.scene"))
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    print(f"Deserializing {len(targets)} scene(s) -> {out}")
    for f in tqdm(targets, desc="Scenes", unit="file"):
        scene = nebula.parse(f.read_bytes())
        (out / f"{f.stem}.json").write_text(nebula.to_json(scene))
    return 0


def _cmd_deserialize(args) -> int:
    scene = nebula.parse(Path(args.path).read_bytes())
    print(nebula.to_json(scene))
    return 0


def _cmd_convert(args) -> int:
    types = {t.strip() for t in args.types.split(",") if t.strip()}
    print(f"Converting {','.join(sorted(types))} under {args.root} -> {args.out}")
    result = convert.convert_tree(
        Path(args.root), Path(args.out), types,
        workers=args.workers, force=args.force,
    )
    print(f"done: {result}")
    return 0


def _cmd_pxscript(args) -> int:
    rendered = pxscript.render_dump(Path(args.dump).read_text(encoding="utf-8"))
    if args.out == "-":
        print(rendered)
    else:
        Path(args.out).write_text(rendered, encoding="utf-8")
        print(f"wrote {args.out}")
    return 0


def _cmd_text(args) -> int:
    table = text.parse_file(args.path)
    payload = text.to_json(table)
    if args.out == "-":
        print(payload)
    else:
        Path(args.out).write_text(payload, encoding="utf-8")
        print(f"wrote {args.out} ({len(table)} entries)")
    return 0


def _cmd_fetch_tools(args) -> int:
    print("Fetching tools into bin/...")
    for name, path in fetch.fetch_tools(force=args.force).items():
        print(f"  {name}: {path} ({path.stat().st_size // 1024} KB)")
    return 0


def _cmd_all(args) -> int:
    extracted = Path("extracted")

    print("[1/6] Unpacking archives...")
    unpack.unpack_all(config.DEFAULT_PACKFILES, extracted)

    print("[2/6] Identifying file types...")
    counts = identify.scan(extracted)
    for t, c in counts.items():
        print(f"  {c:>8}  {t}")

    print("[3/6] Deserializing scenes...")
    _cmd_scene(type("A", (), {"path": str(extracted), "out": "out/scenes"})())

    print("[4/6] Mining translations...")
    tr = mine.translations.run()
    print(f"  {len(tr.table)} entries -> {tr.outputs['json']}")

    print("[5/6] Mining horses...")
    hr = mine.horses.run()
    print(f"  {len(hr.breeds)} breeds, {len(hr.horses)} horses -> {hr.outputs['horses']}")

    print("[6/6] Mining items...")
    it = mine.items.run(translations_path=mine.items.DEFAULT_TRANSLATIONS)
    print(f"  {len(it.items)} items -> {it.outputs['csv']}")

    n_dds = counts.get("dds", 0)
    n_tga = counts.get("tga_container", 0)
    print(
        "\nDone. Textures and icons are excluded (slow); run explicitly when wanted:\n"
        f"  ssotk convert --types dds,tga   ({n_dds} dds + {n_tga} tga textures)\n"
        "  ssotk mine icons                 (per-item PNGs; needs crunch_unity.exe)"
    )
    return 0


def _cmd_mine(args) -> int:
    if args.mine_command == "items":
        translations = args.translations
        if translations.lower() in ("none", "") or not Path(translations).exists():
            translations = None
        result = mine.items.run(scene=args.scene, translations_path=translations, out_dir=args.out)
        print(f"Wrote {len(result.items)} items:")
        for k, p in result.outputs.items():
            print(f"  {k:6s} -> {p}")
        return 0
    if args.mine_command == "horses":
        result = mine.horses.run(scene=args.scene, out_dir=args.out)
        print(f"Wrote {len(result.breeds)} breeds, {len(result.horses)} horses to {args.out}/")
        for k, p in result.outputs.items():
            print(f"  {k:12s} -> {p}")
        return 0
    if args.mine_command == "translations":
        result = mine.translations.run(source=args.source, out_dir=args.out, filename=args.filename)
        print(f"Wrote {len(result.table)} translation entries to {result.outputs['json']}")
        return 0
    if args.mine_command == "icons":
        result = mine.icons.run(
            scene=args.scene,
            extracted=args.extracted,
            out_dir=args.out,
            ids=args.ids or None,
            workers=args.workers,
            force=args.force,
        )
        print("Icons run finished. Counts:")
        for k, v in result.counts.items():
            print(f"  {k:14s} {v}")
        if result.missing_examples:
            print("Sample missing assets (first 20):")
            for s in result.missing_examples:
                print(f"  {s}")
        return 0
    return 2


DISPATCH = {
    "unpack": _cmd_unpack,
    "identify": _cmd_identify,
    "scene": _cmd_scene,
    "deserialize": _cmd_deserialize,
    "convert": _cmd_convert,
    "fetch-tools": _cmd_fetch_tools,
    "pxscript": _cmd_pxscript,
    "text": _cmd_text,
    "mine": _cmd_mine,
    "all": _cmd_all,
}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv if argv is not None else sys.argv[1:])
    return DISPATCH[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
