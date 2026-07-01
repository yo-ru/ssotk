NAME_CHARS = set(
    b"abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789/\\._- "
)


class KH:
    OFFSET      = 0x0B6EF964
    SIZE        = 0x0B1A6E08
    NAME_OFFSET = 0x01C65A88
    EXTRACT     = 0x0E89DE15
    OWN         = 0x06D029F4
    PARENT      = 0x0FA8A5A4
    ID          = 0x040034D4
    BREED_ID    = 0x0BB21504
    PRICE       = 0x01DA6705
    JS_PRICE    = 0x088D4FB5
    SC_PRICE    = 0x008D4FA5
    LEVEL       = 0x06A98294


HASH_NAMES: dict[int, str] = {
    KH.OFFSET:      "offset",
    KH.SIZE:        "size",
    KH.NAME_OFFSET: "name_offset",
    KH.EXTRACT:     "extract",
    KH.OWN:         "own",
    KH.PARENT:      "parent",
    KH.ID:          "id",
    KH.BREED_ID:    "breed_id",
    KH.PRICE:       "price",
    KH.JS_PRICE:    "price_js",
    KH.SC_PRICE:    "price_sc",
    KH.LEVEL:       "level",
}


def deobfuscate(data: bytes, key: int) -> bytes:
    return bytes((b + key) & 0xFF for b in data)


def _looks_text(b: bytes) -> bool:
    return bool(b) and all(c in NAME_CHARS for c in b)


def auto_deobfuscate(data: bytes) -> tuple[bytes, int | None]:
    if _looks_text(data):
        return data, 0
    for key in range(1, 256):
        if data and all(((b + key) & 0xFF) in NAME_CHARS for b in data):
            return deobfuscate(data, key), key
    return data, None


def name_for_hash(h: int) -> str:
    return HASH_NAMES.get(h, f"0x{h:08x}")


try:
    from . import _core as _c

    def deobfuscate(data: bytes, key: int) -> bytes:  # noqa: F811
        return _c.vocab.deobfuscate(data, key)

    def auto_deobfuscate(data: bytes) -> tuple[bytes, int | None]:  # noqa: F811
        return _c.vocab.auto_deobfuscate(data)

    def name_for_hash(h: int) -> str:  # noqa: F811
        return _c.vocab.name_for_hash(h)
except ImportError:
    pass
