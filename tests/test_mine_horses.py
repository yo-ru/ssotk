import csv

from ssotk.mine import horses


def test_dataclasses_are_serializable():
    b = horses.Breed(id=2, name="DanishWarmblood")
    h = horses.Horse(
        id=1, name="DanishWarmblood", breed_id=2, breed_name="DanishWarmblood", level=8, price=850
    )
    assert b.id == 2
    assert h.breed_name == "DanishWarmblood"


def test_write_horses_csv_shape(tmp_path):
    b = [horses.Breed(id=2, name="DanishWarmblood")]
    h = [horses.Horse(id=1, name="Horse1", breed_id=2, breed_name="DanishWarmblood", price=None)]
    horses_csv = tmp_path / "horses.csv"
    breeds_csv = tmp_path / "breeds.csv"
    horses.write_breeds_csv(b, breeds_csv)
    horses.write_horses_csv(h, horses_csv)
    rows = list(csv.DictReader(horses_csv.open(encoding="utf-8")))
    assert rows[0]["horse_name"] == "Horse1"
    assert rows[0]["price"] == ""
