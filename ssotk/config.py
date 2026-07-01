import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
BIN_DIR = REPO_ROOT / "bin"
SCRIPTS_DIR = REPO_ROOT / "scripts"
CSA_BMS = SCRIPTS_DIR / "star_stable_online.bms"
TGA_CRN_BMS = SCRIPTS_DIR / "star_stable_pte_tga_to_crn.bms"

DEFAULT_PACKFILES = Path(r"C:\Program Files\Star Stable Online\client\PackFiles")


def find_quickbms() -> Path:
    c = BIN_DIR / "quickbms.exe"
    if c.is_file():
        return c
    on_path = shutil.which("quickbms")
    if on_path:
        return Path(on_path)
    raise FileNotFoundError(
        "quickbms.exe not found. Run 'ssotk fetch-tools' or place it on PATH."
    )


def find_optional(exe_name: str) -> Path | None:
    c = BIN_DIR / exe_name
    if c.is_file():
        return c
    on_path = shutil.which(Path(exe_name).stem)
    return Path(on_path) if on_path else None
