# SSO file formats

Byte-layout reference for what ssotk parses. Authoritative source for the
`.csaheader` triple layout is `scripts/star_stable_online.bms`.

## Nebula object format (`.scene`, header-flavor)

Two layouts share one parser.

**Scene flavor**: `u32[0]` file size, sentinel `0xFFFFFFFF` at `0x14`. Can stack
multiple size-prefixed objects.

**Header flavor** (`.csaheader`, `.nasset`, `NebulaScriptBinary.bin`): single
object, 8-byte preamble (`u32[0]` = triple count), sentinel at `0x0C`, string
table at `8 + 12*count`.

### Object layout (scene flavor)

```
offset  size  field
0x00    u32   object_size
0x04    u32   0x00000005
0x08    u32   entry_count       triple count + 1
0x0c    u32   0x00000005
0x10    u32   0
0x14    u32   0xffffffff        sentinel
0x18    u32   0x00000100
0x1c    ...   entry_count-1 triples (12 bytes each)
...           record stream to object end
```

`string_table_start = object_start + 0x1c + 12 * (entry_count - 1)`.

### Triples

Fixed 12-byte records: `(name_hash:u32, value:u32, type_token:u32)`.

- `name_hash` resolves via `vocab.name_for_hash` (unknown => `0x........`).
- `value` is a raw u32. For inline tokens it is the decoded value or its
  IEEE-754 bits. For record-pointer tokens it is an offset into the object's
  record stream.

### Record stream

Contiguous `[u32 len][len bytes]` records, no alignment padding, running to
the object boundary. Two kinds:

- **String records**: length-prefixed asset / class names. Some are
  rotate-add obfuscated (see `vocab.auto_deobfuscate`).
- **Typed value blobs**: fixed-size (vec3 = 12B, quat/color = 16B, GUID = 16B,
  u32[3] = 12B). Pointed at from a triple.

The object's class name is its first text record.

### Type tokens

| token  | kind    | meaning        | payload |
|--------|---------|----------------|---------|
| 0x0100 | inline  | bool / enum    | value 0 or 1 |
| 0x0a02 | inline  | u32            | counts, ids, packed handles |
| 0x0a0e | inline  | u32            | distinct token, same width |
| 0x0a03 | inline  | float32        | u32 bits reinterpreted |
| 0x0204 | pointer | string         | record = length-prefixed asset name |
| 0x0207 | pointer | vec3           | record = 3 x float32 (12B) |
| 0x0209 | pointer | quaternion     | record = 4 x float32 (16B, unit length) |
| 0x020a | pointer | color RGBA     | record = 4 x float32 in [0,1] (16B) |
| 0x0410 | pointer | GUID           | record = 16 raw bytes |
| 0x0402 | pointer | u32[3]         | record = 3 x u32 (12B) |

Unknown tokens still observed: `0xa10 0xa01 0x410 0xa0f 0x209 0x20a 0x208 0xa04
0x40e 0x20b 0x406 0x403 0x402 0x401 0x20c 0x407 0x206`. Unknown tokens don't
block parsing; the triple's `decoded` holds the raw u32.

### Coverage

`coverage = bytes_consumed / file_size`. Sub-1.0 coverage is honest: a
non-zero leftover inside an object is embedded asset binary (DDS / obfuscated
PXScript blobs in quest `QC*.scene` files).

## Per-extension handling

| Extension | Type | ssotk |
|-----------|------|-------|
| `.scene` | Nebula typed-object graph | `ssotk.nebula`, 100% coverage |
| `.csaheader` | Archive index | `ssotk.nebula` |
| `.nasset` | Nebula UI widget | `ssotk.nebula` |
| `NebulaScriptBinary.bin` | UI script schema | `ssotk.nebula` |
| `.text` | Translation table | `ssotk.text` |
| `.dds` | DDS texture | `ssotk convert` |
| `.tga` | CRN-wrapped texture | `ssotk convert` extracts .crn |
| `.tps` | Texture variant (DXT at [12:16]) | detected, not decoded |
| `.bank` | FMOD audio | FMOD Studio |
| `.fbx` | Proprietary model container | not handled |
| `.cfbx` | Composite FBX manifest | not handled |
| `.dat` | Raw geometry/collision/terrain | not handled |
| `.PTF` | Raw float array | not handled |
| `.ccx` | Integrity manifest | [RealIndrit/sso-format](https://github.com/RealIndrit/sso-format) |
| `.glsl` | Shader source | plain text |
| `.xml` | Animation state machines | plain XML |

## External tools

**quickbms.exe** - required for `ssotk unpack`. https://aluigi.altervista.org/quickbms.htm.
Discovery: `bin/` -> `PATH`. Run `ssotk fetch-tools` to drop it in `bin/`.

**crunch_unity.exe** - optional for full `.tga` -> PNG and icon extraction.
https://github.com/Unity-Technologies/crunch (unity fork).

`ssotk fetch-tools` downloads both into `bin/`.

## Translation tables (`Text/Translation*.text`)

Flat key/value tables. `TranslationEN.text` decodes to 87k+ entries.

```
0x00  u32*4   file header (ignored)
0x10  entries packed end-to-end
```

Per entry:

```
u16   key_len
u8    pad = 0
u8    shift               additive cipher for the key
byte  key[key_len]
u32   0
u32   1
u32   value_byte_count
byte  payload[value_byte_count]
u16   0x0000              terminator
```

**Key cipher**: `decoded[i] = (key[i] + shift) & 0xFF`. `shift` varies per
entry (commonly 3, 8, 13, 16). Short keys front-pad with cipher bytes that
decode to `\t`; strip after decoding.

**Value cipher**: payload starts with `05 00 01 <first_low>`, then
`<high><low>` pairs ending at `<00><00>`. Character =
`(low + (0x100 - high)) & 0xFF`; the first character uses the first pair's
high byte. Example: `05 00 01 42 ff 71 ff 64 ff 60 ff 73 ff 64` -> `Create`.

Item ID -> English mapping is NOT via this table. Items carry localized
strings inline as records in `PlayerItemManager.scene`; the translation table
is authoritative for quests, dialogue, UI strings, and tooltips (e.g.
`QC31_CABBAGE_NAME` -> `"Fresh cabbage"`).
