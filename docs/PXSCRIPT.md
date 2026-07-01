# PXScript

SSO's gameplay logic (quests, triggers, UI handlers) runs on PXScript, a
bytecode VM inside `SSOClient.exe`. Source is not shipped; logic is recovered
by capturing bytecode from the live VM and disassembling.

## VM

- Interpreter: `sub_14065AC90` (RVA `0x65AC90`).
- Run-by-id: `sub_14065BF70` (FNV-1a script id -> hashmap lookup -> program at
  `+32`, start IP at `+24`).
- Program layout: `{ u32 count; Instr* instrs }`. Each `Instr` is 32 bytes:
  `[opcode:1][subop:1][pad:2][line:4][PXScriptValue operand:24]`.
- `PXScriptValue`: `void* data@0; u32 len@8; u8 type@12`. Types:
  `1 int, 2 uint, 3 float, 4 string, 5 ustring, 6 vec2, 7 vec3, 8 vec4,
  9 quat, 0xA color, 0xE bool, 0x12 actor-ptr`.

## Opcodes

| op | mnemonic | op | mnemonic |
|---|---|---|---|
| 0x03 | DECL_VAR (subop = type) | 0x12-0x15 | ADD/SUB/MUL/DIV |
| 0x04 | PUSH_VAL | 0x16 | NEG |
| 0x06 | ACTOR_REF | 0x17 | CONCAT (`..`) |
| 0x07 | JUMP | 0x18 | CALL (by name) |
| 0x08 | LOOP (2000-iteration guard) | 0x19 | CALL2 (actor method) |
| 0x09 | JZ | 0x1C | TOSTRING |
| 0x0A-0x0F | EQ NE LT GT LE GE | 0x1D | END |
| 0x10/0x11 | OR / AND | 0x1E | RESUME (on actor) |

## Capture -> render

1. Capture with `native/pxdump/`: injected DLL, outputs to `C:\tmp\pxscript_dump.txt`.
2. Render with `ssotk pxscript <dump>` to near-source. Operand pushes fold
   into calls, comparisons into conditions, `JZ` into `if` blocks, `LOOP`
   back-edges into `loop` blocks. Irreducible jumps stay as labeled `goto`.

Example:

```
if ( PlayerHasAccessToHorse("parent/parent") > 0 ) {
    if ( PlayerHasAccessToHorse("global/Horse") > 0 ) {
        SpeakerSoundPlay("Mule_Snort_3D", "this/.../Mule_Voice");
        goto 17;
    }
    SpeakerSoundPlay("MuleSlave_Snort_3D", "this/.../Mule_Voice");
}
```
