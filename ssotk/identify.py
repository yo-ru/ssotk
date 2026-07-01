from pathlib import Path

HEAD_BYTES = 32


def classify(head: bytes, ext: str) -> str:
    if head[:4] == b"DDS ":
        return "dds"
    if head[:4] == b"RIFF" and head[8:12] == b"FEV ":
        return "fmod_bank"
    if (
        len(head) >= 0x1C
        and head[0x14:0x18] == b"\xff\xff\xff\xff"
        and head[0x18:0x1C] == b"\x00\x01\x00\x00"
    ):
        return "nebula"
    if len(head) >= 0x10 and head[0x0C:0x10] == b"\xff\xff\xff\xff":
        return "nebula_header"
    if head[8:12] in (b"DXT1", b"DXT3", b"DXT5"):
        return "tga_container"
    if len(head) >= 16 and head[12:16] in (b"DXT1", b"DXT3", b"DXT5"):
        return "tps_container"
    if head[:2] == b"Hx":
        return "crn"
    if len(head) >= 0x14 and head[0x12] == 0 and 1 <= head[0x10] <= 128 and head[0x11] == 0:
        return "text"
    return ext.lower().lstrip(".") or "unknown"


def scan(root: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        with open(p, "rb") as f:
            head = f.read(HEAD_BYTES)
        t = classify(head, p.suffix)
        counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: -kv[1]))
