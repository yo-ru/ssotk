import csv

from ssotk.mine import items


def test_looks_english_needs_space_or_lowercase():
    assert items._looks_english("Red marking tape")
    assert items._looks_english("cabbage")
    assert not items._looks_english("MININGPICK")
    assert not items._looks_english("")


def test_is_internal_token_flags_snake_case_and_paths():
    assert items._is_internal_token("SOME_KEY_NAME")
    assert items._is_internal_token("global/Horse")
    assert items._is_internal_token("Hair")
    assert items._is_internal_token("HorseHair12")
    assert not items._is_internal_token("Red marking tape")


def test_is_slot_like_rejects_punctuation():
    assert items._is_slot_like("HorseDecorationHead")
    assert items._is_slot_like("Icon_Top_A_Generic")
    assert items._is_slot_like("EQF_Ribbons")
    assert not items._is_slot_like(" ")
    assert not items._is_slot_like("-.--O")
    assert not items._is_slot_like("")


def test_pick_english_skips_internal_tokens():
    class R:
        def __init__(self, text, raw=b""):
            self.text = text
            self.raw = raw

    recs = [R("Item_Axe"), R(None, raw=b"\x00" * 16), R("A sharp axe")]
    assert items.pick_english_from_records(recs) == "A sharp axe"


def test_row_and_csv_shape(tmp_path):
    catalog = [
        items.Item(id=1, internal_name="Red", english_name="Red", slot="Quest", level=19),
        items.Item(id=2, internal_name="Blue", english_name="Blue", slot="Quest"),
    ]
    p = tmp_path / "items.csv"
    items.write_csv(catalog, p)
    rows = list(csv.DictReader(p.open(encoding="utf-8")))
    assert [r["id"] for r in rows] == ["1", "2"]
    assert rows[0]["slot"] == "Quest"
    assert rows[0]["level"] == "19"
    assert rows[1]["level"] == ""
