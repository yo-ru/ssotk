import csv
import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable

from .. import nebula
from ..vocab import KH


@dataclass
class Breed:
    id: int
    name: str


@dataclass
class Horse:
    id: int
    name: str
    breed_id: int | None = None
    breed_name: str = ""
    level: int | None = None
    price: int | None = None


DEFAULT_SCENE = Path("extracted") / "p_00000018" / "Scene" / "HorseManager.scene"


def read(scene_path: os.PathLike | str) -> tuple[list[Breed], list[Horse]]:
    scene = nebula.parse(Path(scene_path).read_bytes())

    breeds_container = scene.object_by_first_string("Breeds")
    horses_container = scene.object_by_first_string("Horses")
    if breeds_container is None or horses_container is None:
        raise ValueError("HorseManager.scene: missing Breeds/Horses containers")

    breeds_own = breeds_container.triple(KH.OWN)
    horses_own = horses_container.triple(KH.OWN)
    if breeds_own is None or horses_own is None:
        raise ValueError("HorseManager.scene: containers missing OWN triple")

    breeds: list[Breed] = []
    for obj in scene.objects_with_parent(breeds_own.value):
        iid = obj.get_int(KH.ID)
        name = obj.strings[0] if obj.strings else ""
        if iid is not None and name:
            breeds.append(Breed(id=iid, name=name))
    breeds.sort(key=lambda b: b.id)
    breed_by_id = {b.id: b.name for b in breeds}

    horses: list[Horse] = []
    for obj in scene.objects_with_parent(horses_own.value):
        iid = obj.get_int(KH.ID)
        name = obj.strings[0] if obj.strings else ""
        if iid is None or not name:
            continue
        bid = obj.get_int(KH.BREED_ID)
        horses.append(
            Horse(
                id=iid,
                name=name,
                breed_id=bid,
                breed_name=breed_by_id.get(bid, "") if bid is not None else "",
                level=obj.get_int(KH.LEVEL),
                price=obj.get_int(KH.PRICE),
            )
        )
    horses.sort(key=lambda h: h.id)
    return breeds, horses


def write_breeds_csv(breeds: Iterable[Breed], path: os.PathLike | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["breed_id", "breed_name"])
        for b in breeds:
            w.writerow([b.id, b.name])


def write_horses_csv(horses: Iterable[Horse], path: os.PathLike | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["horse_id", "horse_name", "breed_id", "breed_name", "level", "price"])
        for h in horses:
            w.writerow(
                [
                    h.id,
                    h.name,
                    "" if h.breed_id is None else h.breed_id,
                    h.breed_name,
                    "" if h.level is None else h.level,
                    "" if h.price is None else h.price,
                ]
            )


def write_json(breeds: Iterable[Breed], horses: Iterable[Horse], path: os.PathLike | str) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "breeds": [asdict(b) for b in breeds],
        "horses": [asdict(h) for h in horses],
    }
    p.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


@dataclass
class RunResult:
    breeds: list[Breed] = field(default_factory=list)
    horses: list[Horse] = field(default_factory=list)
    outputs: dict[str, Path] = field(default_factory=dict)


def run(
    *,
    scene: os.PathLike | str = DEFAULT_SCENE,
    out_dir: os.PathLike | str = "out",
) -> RunResult:
    breeds, horses = read(scene)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    breeds_csv = out / "horse_breeds.csv"
    horses_csv = out / "horses.csv"
    json_path = out / "horses.json"
    write_breeds_csv(breeds, breeds_csv)
    write_horses_csv(horses, horses_csv)
    write_json(breeds, horses, json_path)
    return RunResult(
        breeds=breeds,
        horses=horses,
        outputs={"breeds": breeds_csv, "horses": horses_csv, "json": json_path},
    )
