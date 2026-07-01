import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from PIL import Image, UnidentifiedImageError
from tqdm import tqdm

from . import config

# Stub .tga files (~50 bytes) are metadata pointing at their sibling
# .tga.dds and carry no CRN payload; skip them upfront.
TGA_STUB_MAX_BYTES = 256


def dds_to_png(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src) as im:
        im.convert("RGBA").save(dst, "PNG")
    return dst


def tga_to_crn(src: Path, dst: Path) -> Path | None:
    data = src.read_bytes()
    i = data.find(b"Hx")
    if i < 0:
        return None
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(data[i:])
    return dst


def crn_to_png(src: Path, dst: Path, crunch: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(
        [
            str(crunch), "-file", str(src), "-fileformat", "png",
            "-out", str(dst), "-noprogress", "-quiet",
        ],
        capture_output=True,
        timeout=30,
    )
    return r.returncode == 0 and dst.is_file()


def _convert_one(
    p: Path, root: Path, out: Path, crunch: Path | None, force: bool
) -> str:
    rel = p.relative_to(root)
    suffix = p.suffix.lower()

    if suffix == ".dds":
        dst = (out / rel).with_suffix(".png")
        if dst.exists() and not force:
            return "skipped_existing"
        try:
            dds_to_png(p, dst)
            return "dds"
        except (UnidentifiedImageError, OSError, ValueError, NotImplementedError):
            return "failed"

    if suffix == ".tga":
        try:
            if p.stat().st_size <= TGA_STUB_MAX_BYTES:
                return "skipped"
        except OSError:
            return "skipped"
        crn_path = (out / rel).with_suffix(".crn")
        png_path = crn_path.with_suffix(".png")
        final = png_path if crunch else crn_path
        if final.exists() and not force:
            return "skipped_existing"
        if not tga_to_crn(p, crn_path):
            return "skipped"
        if crunch is None:
            return "crn_only"
        try:
            ok = crn_to_png(crn_path, png_path, crunch)
        except subprocess.TimeoutExpired:
            ok = False
        if ok:
            crn_path.unlink(missing_ok=True)
            return "tga"
        return "failed"

    return "skipped"


def convert_tree(
    root: Path,
    out: Path,
    types: set[str],
    *,
    crunch: Path | None = None,
    workers: int | None = None,
    force: bool = False,
) -> dict[str, int]:
    done = {"dds": 0, "tga": 0, "crn_only": 0, "skipped": 0, "skipped_existing": 0, "failed": 0}

    if "tga" in types and crunch is None:
        crunch = config.find_optional("crunch_unity.exe")
        if crunch is None:
            print("  (crunch_unity.exe not found; .tga extracted to .crn only)")

    if workers is None:
        workers = min(16, os.cpu_count() or 4)

    targets = [
        p for p in root.rglob("*")
        if p.is_file() and p.suffix.lower().lstrip(".") in types
    ]

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_convert_one, p, root, out, crunch, force) for p in targets]
        for fut in tqdm(as_completed(futs), total=len(futs), desc="Converting", unit="file"):
            done[fut.result()] += 1

    return done
