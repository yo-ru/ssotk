# ssotk

Unpack Star Stable Online `.csa` PackFiles, deserialize Nebula `.scene` files
to JSON, decode `.text` translation tables, convert textures, render captured
PXScript VM dumps, and produce datamining catalogs (items, horses,
translations, icons).

## Install

```
pip install -e .
```

Requires Python 3.11+ and a C++20 compiler (MSVC 2022 or MinGW-w64 on
Windows, GCC/Clang elsewhere). If no compiler is present the pure-Python
fallback runs; every path just gets slower.

## Setup + full pipeline

```
ssotk fetch-tools           # downloads bin/quickbms.exe + bin/crunch_unity.exe
ssotk all                   # unpack + identify + scenes + mine translations/horses/items
ssotk convert --types dds,tga    # textures -> PNG (slow; not in `all`)
ssotk mine icons                  # per-item icon PNGs (slow; not in `all`)
```

`ssotk all` is the "everything but textures and icons" shortcut. Textures
and icons are gated because they can take tens of minutes and depend on
`bin/crunch_unity.exe`. To run the steps individually:

```
ssotk unpack                            # 31 .csa archives -> extracted/
ssotk identify                          # magic-byte file breakdown
ssotk scene extracted --out out/scenes  # every .scene -> JSON
ssotk mine translations                 # -> out/translations_en.json
ssotk mine horses                       # -> out/horses.csv + horse_breeds.csv + horses.json
ssotk mine items                        # -> out/items.csv + items.json
ssotk convert --types dds,tga           # -> out/converted/**/*.png
ssotk mine icons                        # -> out/icons/<id>.png + out/textures/<id>.png
```

## Commands

```
ssotk unpack [--archive p_00000005] [--out extracted]
ssotk identify [--root extracted] [--json]
ssotk scene <file-or-dir> [--out out/scenes]
ssotk deserialize <file>
ssotk convert [--root extracted] [--out out/converted] [--types dds,tga]
ssotk fetch-tools [--force]
ssotk pxscript <dump> [--out -]
ssotk text <file> [--out -]
ssotk mine {items,horses,translations,icons} [...]
ssotk all
```

Every `mine` subcommand takes `--scene`, `--translations`, `--out` overrides.
`--translations none` skips the English-name join.

## Programmatic API

```python
from ssotk import nebula, text
from ssotk.mine import items, horses
from ssotk.vocab import KH

scene = nebula.parse(open("HorseManager.scene", "rb").read())
container = scene.object_by_first_string("Horses")
for obj in scene.objects_with_parent(container.triple(KH.OWN).value):
    print(obj.get_int(KH.ID), obj.strings[0])

trans = text.parse_file("TranslationEN.text")
catalog = items.read("PlayerItemManager.scene", translations=trans)
```

## Format coverage

| Format | Handling |
|---|---|
| `.csa` PackFile | `ssotk unpack` (bundled `.bms` + quickbms) |
| `.scene` / `.csaheader` / `.nasset` / `NebulaScriptBinary.bin` | `ssotk.nebula` |
| `.text` | `ssotk.text` |
| `.dds` | `ssotk convert` (Pillow) |
| `.tga` (CRN-wrapped) | `ssotk convert` (extract; PNG needs `crunch_unity.exe`) |
| PXScript VM dumps | `ssotk pxscript` |
| `.bank` (FMOD) | out of scope; use FMOD Studio |
| `.fbx` | out of scope; use Blender |
| `.ccx` (integrity manifests) | out of scope; see [RealIndrit/sso-format](https://github.com/RealIndrit/sso-format) |

## PXScript capture
`native/pxdump/` produces dumps for `ssotk pxscript`.

See [native/pxdump/README.md](native/pxdump/README.md) and
[docs/PXSCRIPT.md](docs/PXSCRIPT.md).
