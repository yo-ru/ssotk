import io
import urllib.request
import zipfile
from pathlib import Path

from . import config

QUICKBMS_URL = "https://aluigi.altervista.org/papers/quickbms.zip"
CRUNCH_URL = (
    "https://raw.githubusercontent.com/Unity-Technologies/crunch/unity/bin/crunch_x64.exe"
)


def _download(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "ssotk"})
    with urllib.request.urlopen(req, timeout=120) as resp:
        return resp.read()


def fetch_quickbms(force: bool = False) -> Path:
    dst = config.BIN_DIR / "quickbms.exe"
    if dst.is_file() and not force:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(_download(QUICKBMS_URL))) as z:
        member = next(n for n in z.namelist() if Path(n).name.lower() == "quickbms.exe")
        dst.write_bytes(z.read(member))
    return dst


def fetch_crunch(force: bool = False) -> Path:
    dst = config.BIN_DIR / "crunch_unity.exe"
    if dst.is_file() and not force:
        return dst
    dst.parent.mkdir(parents=True, exist_ok=True)
    dst.write_bytes(_download(CRUNCH_URL))
    return dst


def fetch_tools(force: bool = False) -> dict[str, Path]:
    return {"quickbms": fetch_quickbms(force), "crunch": fetch_crunch(force)}
