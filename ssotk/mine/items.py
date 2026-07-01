import csv
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .. import nebula, text
from ..vocab import KH

DEFAULT_SCENE = Path("extracted") / "p_00000023" / "Scene" / "PlayerItemManager.scene"
DEFAULT_TRANSLATIONS = Path("extracted") / "p_00000026" / "Text" / "TranslationEN.text"


@dataclass
class Item:
    id: int
    internal_name: str
    english_name: str = ""
    slot: str = ""
    level: int | None = None
    price_js: int | None = None
    price_sc: int | None = None


TYPE_NAMES = frozenset(
    {
        "Hair", "HairStandard", "Face", "Top", "Pants", "Shoes", "Hat", "Gloves",
        "HorseBody", "HorseHair", "HorseReins", "HorseBlanket", "HorseBlanket2",
        "HorseSaddle", "HorseDecorationTail", "HorseDecorations_Socks",
        "Item", "Resource", "Consumables", "Pet", "Bridle",
    }
)
TYPE_PREFIXES = ("HorseHair", "HorseBlanket")

SLOTS_HORSE_TACK = frozenset(
    {
        "HorseBody", "HorseHair", "HorseLeggings", "HorseDecorationHead",
        "HorseDecorationTail", "HorseSaddleBagRight", "HorseSaddleBagLeft",
        "HorseAccessory", "HorseAccessoryNeck", "HorseGear", "HorseShoes",
        "HorseSock", "HorseSocks", "Blanket", "Reins", "Saddle", "Halter",
        "Bridle", "SaddlePad", "LegProtectors", "Tail", "Mane",
    }
)
# "Boots" is intentionally left out here; the scene names both horse leg
# protection and player footwear "Boots", and the icon-prefix rules below
# disambiguate.
SLOTS_CLOTHING = frozenset(
    {
        "Pants", "Shoes", "Shoe", "Hands", "Hair", "HairStandard", "Top", "Hat",
        "Shirt", "Jacket", "Sweater", "Skirt", "Boots", "Glasses", "Belt",
        "Necklace", "Ring", "Earring", "Watch", "Accessory",
        "PlayerDecorationHead", "Face", "Makeup", "Piercing", "Backpack", "Pet", "PetSeal",
    }
)
SLOTS_QUEST = frozenset({"Quest"})

ICON_HORSE_TACK = (
    "Icon_Blanket", "Icon_Reins", "Icon_Saddle", "Icon_Bridle", "Icon_Halter",
    "Icon_LegProtectors", "Icon_Legs_H", "Icon_HorseBody", "Icon_Tail",
    "Icon_Mane", "Icon_Hoof",
)
ICON_CLOTHING = (
    "Icon_Top", "Icon_Hat", "Icon_Shoe", "Icon_Pants", "Icon_Hands",
    "Icon_HairStyle", "Icon_Hair", "Icon_Glasses", "Icon_Belt", "Icon_Necklace",
    "Icon_Earring", "Icon_Piercing", "Icon_Face", "Icon_Makeup", "Icon_Pet",
    "Icon_PlayerDecorations", "Icon_Accessory",
)


def _looks_english(s: str) -> bool:
    if not s:
        return False
    if any(ord(c) < 0x20 for c in s):
        return False
    if not all(0x20 <= ord(c) <= 0xFF for c in s):
        return False
    return " " in s or any(c.islower() for c in s)


def _is_internal_token(s: str) -> bool:
    if not s:
        return True
    if "_" in s and " " not in s:
        return True
    if "\\" in s or "/" in s:
        return True
    if s.isupper() and " " not in s:
        return True
    if s in TYPE_NAMES:
        return True
    for p in TYPE_PREFIXES:
        if s.startswith(p) and s[len(p):].isdigit():
            return True
    return False


def pick_english_from_records(records) -> str:
    for i, r in enumerate(records):
        if i < 2:
            continue
        s = r.text
        if s is None:
            continue
        if not _looks_english(s):
            continue
        if _is_internal_token(s):
            continue
        return s
    return ""


def _is_slot_like(s: str) -> bool:
    return bool(s) and all(c.isalnum() or c == "_" for c in s)


def _classify_slot(slot: str) -> str:
    if not slot:
        return "other"
    if slot in SLOTS_HORSE_TACK:
        return "horse_tack"
    if slot in SLOTS_CLOTHING:
        return "clothing"
    if slot in SLOTS_QUEST:
        return "quest"
    if slot.startswith(ICON_HORSE_TACK):
        return "horse_tack"
    if slot.startswith(ICON_CLOTHING):
        return "clothing"
    return "other"


def read(scene_path: os.PathLike | str, *, translations: dict[str, str] | None = None) -> list[Item]:
    scene = nebula.parse(Path(scene_path).read_bytes())
    trans = translations or {}
    by_own = {}
    for obj in scene.objects:
        t = obj.triple(KH.OWN)
        if t is not None:
            by_own[t.value] = obj

    items: list[Item] = []
    for obj in scene.objects:
        iid_t = obj.triple(KH.ID)
        if iid_t is None or not obj.records:
            continue

        # Most items have text at record 0; a couple (Item_Axe, Item_Pen)
        # start with a 16-byte GUID and put the name at record 1.
        internal = next((r.text for r in obj.records if r.text), "")
        if not internal:
            continue

        parent_t = obj.triple(KH.PARENT)
        parent = by_own.get(parent_t.value) if parent_t else None
        parent_first = next((r.text for r in parent.records if r.text), "") if parent else ""
        slot_parent = parent_first if _is_slot_like(parent_first) else ""
        s3 = obj.records[3].text if len(obj.records) > 3 and obj.records[3].text else ""
        slot_str3 = s3 if _is_slot_like(s3) else ""

        slot = ""
        for s in (slot_parent, slot_str3):
            if s and _classify_slot(s) != "other":
                slot = s
                break
        if not slot:
            slot = slot_parent or slot_str3

        eng = trans.get(internal.upper() + "_NAME", "") or pick_english_from_records(obj.records)

        js = obj.get_float(KH.JS_PRICE)
        sc = obj.get_float(KH.SC_PRICE)
        items.append(
            Item(
                id=iid_t.value,
                internal_name=internal,
                english_name=eng,
                slot=slot,
                level=obj.get_int(KH.LEVEL),
                price_js=round(js) if js is not None else None,
                price_sc=round(sc) if sc is not None else None,
            )
        )
    items.sort(key=lambda x: x.id)
    return items


CSV_COLUMNS = ["id", "internal_name", "english_name", "slot", "level", "price_js", "price_sc"]


def _row(item: Item) -> list:
    return [
        item.id,
        item.internal_name,
        item.english_name,
        item.slot,
        "" if item.level is None else item.level,
        "" if item.price_js is None else item.price_js,
        "" if item.price_sc is None else item.price_sc,
    ]


def write_csv(items: Iterable[Item], path: os.PathLike | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(CSV_COLUMNS)
        for it in items:
            w.writerow(_row(it))


def write_json(items: Iterable[Item], path: os.PathLike | str) -> None:
    items_list = list(items)
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps({"items": [asdict(i) for i in items_list]}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


@dataclass
class RunResult:
    items: list[Item] = field(default_factory=list)
    outputs: dict[str, Path] = field(default_factory=dict)


def run(
    *,
    scene: os.PathLike | str = DEFAULT_SCENE,
    translations_path: os.PathLike | str | None = None,
    out_dir: os.PathLike | str = "out",
) -> RunResult:
    trans = text.parse_file(translations_path) if translations_path else None
    items = read(scene, translations=trans)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    csv_path = out / "items.csv"
    json_path = out / "items.json"
    write_csv(items, csv_path)
    write_json(items, json_path)
    return RunResult(items=items, outputs={"csv": csv_path, "json": json_path})
