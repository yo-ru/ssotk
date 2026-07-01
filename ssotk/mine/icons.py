import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path

from tqdm import tqdm

from .. import config, nebula
from ..vocab import KH

TGA_STUB_MAX_BYTES = 256
ICON_PATH_PARTS = ("/gui/icons", "/gui/items")
PKG_RE = re.compile(r"p_(\d+)")
GOOD_REF_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,127}$")

DEFAULT_SCENE = Path("extracted") / "p_00000023" / "Scene" / "PlayerItemManager.scene"
DEFAULT_EXTRACTED = Path("extracted")


def _pkg_rank(path: Path) -> int:
    for part in path.parts:
        m = PKG_RE.fullmatch(part)
        if m:
            return int(m.group(1))
    return -1


def _is_baked_icon(path: Path) -> bool:
    s = str(path).replace("\\", "/").lower()
    return any(part in s for part in ICON_PATH_PARTS)


def build_asset_index(root: Path) -> dict[str, tuple[Path, str]]:
    index: dict[str, tuple[int, int, Path, str]] = {}
    for dirpath, _, filenames in os.walk(root):
        for f in filenames:
            low = f.lower()
            kind: str
            if low.endswith(".tga.dds"):
                stem = f[:-8]
                kind = "dds"
            elif low.endswith(".dds"):
                stem = f[:-4]
                kind = "dds"
            elif low.endswith(".tga"):
                p = Path(dirpath) / f
                try:
                    if p.stat().st_size <= TGA_STUB_MAX_BYTES:
                        continue
                except OSError:
                    continue
                stem = f[:-4]
                kind = "crn"
            else:
                continue
            p = Path(dirpath) / f
            key = stem.lower()
            rank = _pkg_rank(p)
            pref = 2 if kind == "dds" else 1
            cur = index.get(key)
            if cur is None or (pref, rank) > (cur[0], cur[1]):
                index[key] = (pref, rank, p, kind)
    return {k: (v[2], v[3]) for k, v in index.items()}


def parse_icon_refs(scene_path: Path) -> dict[int, tuple[str, str]]:
    scene = nebula.parse(scene_path.read_bytes())
    out: dict[int, tuple[str, str]] = {}
    for obj in scene.objects:
        iid = obj.get_int(KH.ID)
        if iid is None:
            continue
        strings = obj.strings
        if len(strings) < 3:
            continue
        internal, ref = strings[0], strings[2]
        if GOOD_REF_RE.match(ref):
            out[iid] = (internal, ref)
    return out


def _convert_one(
    item_id: int,
    src: Path,
    kind: str,
    tmp_dir: Path,
    out_dir: Path,
    crunch: Path,
    quickbms: Path | None,
    bms_script: Path | None,
    force: bool,
) -> str:
    out_png = out_dir / f"{item_id}.png"
    if out_png.exists() and not force:
        return "skip"
    work = tmp_dir / str(item_id)
    work.mkdir(parents=True, exist_ok=True)
    try:
        if kind == "dds":
            staged = work / "input.dds"
            shutil.copyfile(src, staged)
            crunch_in = staged
        else:
            if quickbms is None or bms_script is None:
                return "fail_crn"
            staged = work / "input.tga"
            shutil.copyfile(src, staged)
            r = subprocess.run(
                [str(quickbms), str(bms_script), str(staged), str(work)],
                capture_output=True, text=True, timeout=30,
            )
            crn = work / "input_new.crn"
            if r.returncode != 0 or not crn.is_file():
                return "fail_crn"
            crunch_in = crn
        r = subprocess.run(
            [
                str(crunch), "-file", str(crunch_in), "-fileformat", "png",
                "-out", str(out_png), "-noprogress", "-quiet",
            ],
            capture_output=True, text=True, timeout=30,
        )
        return "ok" if r.returncode == 0 and out_png.is_file() else "fail_png"
    except subprocess.TimeoutExpired:
        return "fail_timeout"
    finally:
        try:
            for p in work.iterdir():
                p.unlink(missing_ok=True)
            work.rmdir()
        except OSError:
            pass


@dataclass
class RunResult:
    counts: dict[str, int] = field(default_factory=dict)
    missing_examples: list[str] = field(default_factory=list)
    icons_dir: Path | None = None
    textures_dir: Path | None = None


def run(
    *,
    scene: os.PathLike | str = DEFAULT_SCENE,
    extracted: os.PathLike | str = DEFAULT_EXTRACTED,
    out_dir: os.PathLike | str = "out",
    ids: list[int] | None = None,
    workers: int = 8,
    force: bool = False,
) -> RunResult:
    scene_p = Path(scene)
    extracted_p = Path(extracted)
    out = Path(out_dir)
    icons_dir = out / "icons"
    textures_dir = out / "textures"
    tmp_dir = out / "images_tmp"
    icons_dir.mkdir(parents=True, exist_ok=True)
    textures_dir.mkdir(parents=True, exist_ok=True)
    tmp_dir.mkdir(parents=True, exist_ok=True)

    crunch = config.find_optional("crunch_unity.exe")
    quickbms: Path | None
    try:
        quickbms = config.find_quickbms()
    except FileNotFoundError:
        quickbms = None
    bms_script = config.TGA_CRN_BMS if config.TGA_CRN_BMS.exists() else None

    refs = parse_icon_refs(scene_p)
    index = build_asset_index(extracted_p)

    wanted = set(ids) if ids else None
    counts = {
        "ok_icon": 0, "ok_texture": 0, "skip": 0,
        "no_ref": 0, "no_asset": 0,
        "fail_crn": 0, "fail_png": 0, "fail_timeout": 0,
    }
    missing_examples: list[str] = []
    work: list[tuple[int, Path, str, Path]] = []

    for iid, (internal, ref) in refs.items():
        if wanted is not None and iid not in wanted:
            continue
        hit = index.get(ref.lower())
        if not hit:
            counts["no_asset"] += 1
            if len(missing_examples) < 20:
                missing_examples.append(f"{iid} {internal} -> {ref}")
            continue
        path, kind = hit
        out_route = icons_dir if _is_baked_icon(path) else textures_dir
        work.append((iid, path, kind, out_route))

    if crunch is None:
        counts["fail_png"] = len(work)
        return RunResult(
            counts=counts, missing_examples=missing_examples,
            icons_dir=icons_dir, textures_dir=textures_dir,
        )

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(
                _convert_one, iid, path, kind, tmp_dir, out_route,
                crunch, quickbms, bms_script, force,
            ): (iid, out_route)
            for (iid, path, kind, out_route) in work
        }
        for fut in tqdm(as_completed(futs), total=len(futs), desc="Icons", unit="file"):
            iid, out_route = futs[fut]
            status = fut.result()
            if status == "ok":
                key = "ok_icon" if out_route is icons_dir else "ok_texture"
                counts[key] += 1
            else:
                counts[status] = counts.get(status, 0) + 1

    try:
        tmp_dir.rmdir()
    except OSError:
        pass

    return RunResult(
        counts=counts, missing_examples=missing_examples,
        icons_dir=icons_dir, textures_dir=textures_dir,
    )
