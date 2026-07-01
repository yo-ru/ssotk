import json
import os
from pathlib import Path

HEADER_LEN = 0x10


def decode_value(payload: bytes) -> str | None:
    if len(payload) < 4 or payload[:3] != b"\x05\x00\x01":
        return None
    first_low = payload[3]
    chars: list[int] = []
    first_high: int | None = None
    i = 4
    while i + 1 < len(payload):
        high = payload[i]
        low = payload[i + 1]
        if high == 0 and low == 0:
            break
        if first_high is None:
            first_high = high
        shift = (0x100 - high) & 0xFF
        chars.append((low + shift) & 0xFF)
        i += 2
    if first_high is None:
        first_high = 0xFF
    first_shift = (0x100 - first_high) & 0xFF
    first_char = (first_low + first_shift) & 0xFF
    return bytes([first_char] + chars).decode("latin1", errors="replace")


def parse(data: bytes) -> dict[str, str]:
    out: dict[str, str] = {}
    off = HEADER_LEN
    n = len(data)
    while off + 16 < n:
        key_len = int.from_bytes(data[off : off + 2], "little")
        pad = data[off + 2]
        shift = data[off + 3]
        if key_len == 0 or key_len > 256 or pad != 0:
            off += 1
            continue
        key_start = off + 4
        if key_start + key_len + 12 > n:
            off += 1
            continue
        sa = int.from_bytes(data[key_start + key_len : key_start + key_len + 4], "little")
        sb = int.from_bytes(data[key_start + key_len + 4 : key_start + key_len + 8], "little")
        if sa != 0 or sb != 1:
            off += 1
            continue
        vbc = int.from_bytes(
            data[key_start + key_len + 8 : key_start + key_len + 12], "little"
        )
        payload_off = key_start + key_len + 12
        if payload_off + vbc + 2 > n:
            off += 1
            continue
        key_bytes = data[key_start : key_start + key_len]
        key = "".join(chr((b + shift) & 0xFF) for b in key_bytes).lstrip("\t")
        payload = data[payload_off : payload_off + vbc]
        value = decode_value(payload + b"\x00\x00")
        if value is not None:
            out[key] = value.rstrip("\x00")
        off = payload_off + vbc + 2
    return out


def parse_file(path: os.PathLike | str) -> dict[str, str]:
    return parse(Path(path).read_bytes())


def to_json(table: dict[str, str], *, sort_keys: bool = True) -> str:
    return json.dumps(table, ensure_ascii=False, indent=2, sort_keys=sort_keys)


try:
    from . import _core as _c

    parse = _c.text.parse  # noqa: F811
    if hasattr(_c.text, "decode_value"):
        decode_value = _c.text.decode_value  # noqa: F811
except ImportError:
    pass
