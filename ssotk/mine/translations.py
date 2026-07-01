import os
from dataclasses import dataclass, field
from pathlib import Path

from .. import text

DEFAULT_SOURCE = Path("extracted") / "p_00000026" / "Text" / "TranslationEN.text"


@dataclass
class RunResult:
    table: dict[str, str] = field(default_factory=dict)
    outputs: dict[str, Path] = field(default_factory=dict)


def run(
    *,
    source: os.PathLike | str = DEFAULT_SOURCE,
    out_dir: os.PathLike | str = "out",
    filename: str = "translations_en.json",
) -> RunResult:
    src = Path(source)
    table = text.parse_file(src)
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dst = out / filename
    dst.write_text(text.to_json(table), encoding="utf-8")
    return RunResult(table=table, outputs={"json": dst})
