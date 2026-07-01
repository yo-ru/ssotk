import subprocess
from pathlib import Path

from . import config


def build_command(quickbms: Path, bms: Path, header: Path, out_dir: Path) -> list[str]:
    return [str(quickbms), "-o", str(bms), str(header), str(out_dir)]


def unpack_archive(header: Path, out_root: Path, label: str = "") -> Path:
    quickbms = config.find_quickbms()
    out_dir = out_root / header.stem
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_command(quickbms, config.CSA_BMS, header, out_dir)
    print(f"{label}{header.stem} ...", end="", flush=True)
    result = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    n = sum(1 for p in out_dir.rglob("*") if p.is_file())
    note = f"  [quickbms exit {result.returncode}]" if result.returncode else ""
    print(f"\r{label}{header.stem}: {n} files{note}    ")
    return out_dir


def unpack_all(packfiles: Path = config.DEFAULT_PACKFILES, out_root: Path = Path("extracted")) -> list[Path]:
    headers = sorted(packfiles.glob("*.csaheader"))
    total = len(headers)
    outs: list[Path] = []
    for i, header in enumerate(headers, 1):
        outs.append(unpack_archive(header, out_root, label=f"[{i}/{total}] "))
    return outs
