import json
import struct
from dataclasses import dataclass, field
from typing import Iterator

from . import vocab

PREAMBLE_LEN = 0x1C
TRIPLE_LEN = 12
SENTINEL_OFF = 0x14
SENTINEL = 0xFFFFFFFF
HEADER_PREAMBLE = 8
HEADER_SENTINEL_OFF = 0x0C


class Reader:
    def __init__(self, data: bytes):
        self.data = data
        self.pos = 0

    def u32(self) -> int:
        v = struct.unpack_from("<I", self.data, self.pos)[0]
        self.pos += 4
        return v

    def f32(self) -> float:
        v = struct.unpack_from("<f", self.data, self.pos)[0]
        self.pos += 4
        return v

    def tell(self) -> int:
        return self.pos

    def seek(self, pos: int) -> None:
        self.pos = pos

    def remaining(self) -> int:
        return len(self.data) - self.pos


@dataclass
class Triple:
    name_hash: int
    value: int
    type_token: int
    decoded: object

    @property
    def name(self) -> str:
        return vocab.name_for_hash(self.name_hash)


@dataclass
class Record:
    idx: int
    offset: int
    length: int
    raw: bytes
    text: str | None
    key: int | None

    def as_floats(self) -> tuple[float, ...] | None:
        if self.length == 0 or self.length % 4:
            return None
        n = self.length // 4
        return struct.unpack_from("<" + "f" * n, self.raw, 0)


@dataclass
class Object:
    offset: int
    size: int
    triples: list[Triple] = field(default_factory=list)
    records: list[Record] = field(default_factory=list)

    @property
    def class_name(self) -> str | None:
        for r in self.records:
            if r.text is not None:
                return r.text
        return None

    @property
    def strings(self) -> list[str]:
        return [r.text for r in self.records if r.text is not None]

    def triple(self, name_hash: int) -> Triple | None:
        for t in self.triples:
            if t.name_hash == name_hash:
                return t
        return None

    def triples_of(self, name_hash: int) -> list[Triple]:
        return [t for t in self.triples if t.name_hash == name_hash]

    def get_int(self, name_hash: int) -> int | None:
        t = self.triple(name_hash)
        if t is None:
            return None
        return t.decoded if isinstance(t.decoded, int) and not isinstance(t.decoded, bool) else t.value

    def get_float(self, name_hash: int) -> float | None:
        t = self.triple(name_hash)
        if t is None:
            return None
        if isinstance(t.decoded, float):
            return t.decoded
        return _as_float(t.value)

    def get_bool(self, name_hash: int) -> bool | None:
        t = self.triple(name_hash)
        if t is None:
            return None
        return bool(t.value)

    def get_str(self, name_hash: int) -> str | None:
        t = self.triple(name_hash)
        if t is None or not isinstance(t.decoded, str):
            return None
        return t.decoded

    def get_string(self, idx: int) -> str | None:
        s = self.strings
        return s[idx] if 0 <= idx < len(s) else None


@dataclass
class Scene:
    total_size: int
    root_class: str | None = None
    entries: list = field(default_factory=list)
    strings: list[str] = field(default_factory=list)
    coverage: float = 0.0
    unknown_tokens: list[int] = field(default_factory=list)
    object_count: int = 0
    objects: list[Object] = field(default_factory=list)

    def object_by_own(self, own_hash: int) -> Object | None:
        for obj in self.objects:
            t = obj.triple(vocab.KH.OWN)
            if t is not None and t.value == own_hash:
                return obj
        return None

    def objects_with_parent(self, parent_own: int) -> Iterator[Object]:
        for obj in self.objects:
            t = obj.triple(vocab.KH.PARENT)
            if t is not None and t.value == parent_own:
                yield obj

    def object_by_first_string(self, name: str) -> Object | None:
        for obj in self.objects:
            if obj.class_name == name:
                return obj
        return None


def _as_float(value: int) -> float:
    return struct.unpack("<f", struct.pack("<I", value))[0]


INLINE_HANDLERS: dict[int, object] = {}
POINTER_HANDLERS: dict[int, object] = {}


def _register_inline(token: int):
    def deco(fn):
        INLINE_HANDLERS[token] = fn
        return fn
    return deco


def _register_pointer(token: int):
    def deco(fn):
        POINTER_HANDLERS[token] = fn
        return fn
    return deco


@_register_inline(0x0100)
def _t_100(name_hash, value):
    return value


@_register_inline(0x0A02)
def _t_a02(name_hash, value):
    return value


@_register_inline(0x0A0E)
def _t_a0e(name_hash, value):
    return value


@_register_inline(0x0A03)
def _t_a03(name_hash, value):
    return _as_float(value)


@_register_pointer(0x0204)
def _t_204(name_hash, value, rec):
    if rec.text is not None:
        return rec.text
    return rec.raw.rstrip(b"\x00").decode("latin1", errors="replace") or None


@_register_pointer(0x0207)
def _t_207(name_hash, value, rec):
    if rec.length < 12:
        return None
    return struct.unpack_from("<3f", rec.raw, 0)


@_register_pointer(0x0209)
def _t_209(name_hash, value, rec):
    if rec.length < 16:
        return None
    return struct.unpack_from("<4f", rec.raw, 0)


@_register_pointer(0x020A)
def _t_20a(name_hash, value, rec):
    if rec.length < 16:
        return None
    return struct.unpack_from("<4f", rec.raw, 0)


@_register_pointer(0x0410)
def _t_410(name_hash, value, rec):
    if rec.length < 16:
        return None
    return bytes(rec.raw[:16])


@_register_pointer(0x0402)
def _t_402(name_hash, value, rec):
    if rec.length < 12:
        return None
    return struct.unpack_from("<3I", rec.raw, 0)


def read_string_table(data: bytes) -> list[str]:
    out: list[str] = []
    n = len(data)
    o = 0
    while o + 4 <= n:
        length = struct.unpack_from("<I", data, o)[0]
        if 1 <= length <= 256 and o + 4 + length <= n:
            raw = data[o + 4 : o + 4 + length]
            dec, key = vocab.auto_deobfuscate(raw.rstrip(b"\x00"))
            if key is not None and dec:
                text = dec.decode("latin1")
                if text.isprintable():
                    out.append(text)
                    o += 4 + length
                    continue
        o += 1
    return out


def _string_table_start(data: bytes, base: int) -> int:
    count = struct.unpack_from("<I", data, base + 8)[0]
    return base + PREAMBLE_LEN + TRIPLE_LEN * (count - 1)


def _parse_record_stream(data: bytes, start: int, end: int, obj: Object) -> tuple[int, dict[int, Record]]:
    o = start
    idx = 0
    by_offset: dict[int, Record] = {}
    while o + 4 <= end:
        length = struct.unpack_from("<I", data, o)[0]
        if length == 0 or o + 4 + length > end:
            break
        raw = data[o + 4 : o + 4 + length]
        stripped = raw.rstrip(b"\x00")
        dec, key = vocab.auto_deobfuscate(stripped)
        text: str | None = None
        if key is not None:
            candidate = dec.decode("latin1")
            if (
                len(candidate) >= 3
                and candidate.isprintable()
                and any(c.isalpha() for c in candidate)
            ):
                text = candidate
        if text is None and len(stripped) >= 3:
            try:
                plain = stripped.decode("latin1")
                if plain.isprintable() and any(c.isalpha() for c in plain):
                    text = plain
            except UnicodeDecodeError:
                pass
        rec = Record(idx=idx, offset=o, length=length, raw=raw, text=text, key=key)
        obj.records.append(rec)
        by_offset[o - start] = rec
        idx += 1
        o += 4 + length
    if o < end and not any(data[o:end]):
        o = end
    return o, by_offset


def _decode_body(data: bytes, start: int, end: int, scene: Scene, obj: Object, records_by_offset: dict[int, Record]) -> None:
    o = start
    while o + TRIPLE_LEN <= end:
        name_hash, value, token = struct.unpack_from("<III", data, o)
        decoded: object = value
        inline = INLINE_HANDLERS.get(token)
        pointer = POINTER_HANDLERS.get(token)
        if inline is not None:
            decoded = inline(name_hash, value)
        elif pointer is not None:
            rec = records_by_offset.get(value)
            if rec is not None:
                r = pointer(name_hash, value, rec)
                if r is not None:
                    decoded = r
        else:
            scene.unknown_tokens.append(token)
        obj.triples.append(Triple(name_hash=name_hash, value=value, type_token=token, decoded=decoded))
        scene.entries.append({"key": vocab.name_for_hash(name_hash), "type": token, "value": decoded})
        o += TRIPLE_LEN


def _is_header_flavor(data: bytes) -> bool:
    return (
        len(data) >= HEADER_SENTINEL_OFF + 4
        and struct.unpack_from("<I", data, HEADER_SENTINEL_OFF)[0] == SENTINEL
    )


def _parse_header(data: bytes) -> Scene:
    scene = Scene(total_size=len(data))
    n = len(data)
    count = struct.unpack_from("<I", data, 0)[0]
    table_start = HEADER_PREAMBLE + TRIPLE_LEN * count
    if table_start > n:
        return scene
    obj = Object(offset=0, size=n)
    rec_end, by_offset = _parse_record_stream(data, table_start, n, obj)
    _decode_body(data, HEADER_PREAMBLE, table_start, scene, obj, by_offset)
    scene.objects.append(obj)
    scene.strings = obj.strings
    scene.root_class = obj.class_name
    scene.object_count = 1
    scene.coverage = rec_end / n if data else 1.0
    return scene


def parse(data: bytes) -> Scene:
    if _is_header_flavor(data):
        return _parse_header(data)
    scene = Scene(total_size=len(data))
    consumed = 0
    n = len(data)
    o = 0
    while o + PREAMBLE_LEN <= n:
        size = struct.unpack_from("<I", data, o)[0]
        sentinel = struct.unpack_from("<I", data, o + SENTINEL_OFF)[0]
        if sentinel != SENTINEL or size < PREAMBLE_LEN or o + size > n:
            break
        obj_end = o + size
        obj = Object(offset=o, size=size)
        table_start = _string_table_start(data, o)

        rec_end, by_offset = _parse_record_stream(data, table_start, obj_end, obj)
        _decode_body(data, o + PREAMBLE_LEN, table_start, scene, obj, by_offset)
        scene.objects.append(obj)

        scene.strings.extend(obj.strings)
        if scene.root_class is None and obj.class_name is not None:
            scene.root_class = obj.class_name

        consumed += rec_end - o
        scene.object_count += 1
        o = obj_end

    scene.coverage = consumed / n if data else 1.0
    return scene


try:
    from . import _core as _c

    parse = _c.nebula.parse  # noqa: F811
    _is_header_flavor = _c.nebula.is_header_flavor
    Scene = _c.nebula.Scene  # noqa: F811
    Object = _c.nebula.Object  # noqa: F811
    Triple = _c.nebula.Triple  # noqa: F811
    Record = _c.nebula.Record  # noqa: F811
except ImportError:
    pass


def to_json(scene) -> str:
    def _clean(v):
        if isinstance(v, bytes):
            return v.hex()
        if isinstance(v, tuple):
            return list(v)
        return v

    return json.dumps(
        {
            "total_size": scene.total_size,
            "root_class": scene.root_class,
            "object_count": scene.object_count,
            "coverage": scene.coverage,
            "unknown_tokens": [hex(t) for t in sorted(set(scene.unknown_tokens))],
            "strings": scene.strings,
            "entries": [
                {"key": e["key"], "type": hex(e["type"]), "value": _clean(e["value"])}
                for e in scene.entries
            ],
        },
        indent=2,
    )
