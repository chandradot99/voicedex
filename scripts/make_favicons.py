"""Render the site icon to real files: favicon.svg, PNGs and a multi-size favicon.ico.

Google's search results only show a favicon that has its own crawlable URL and is at least 48x48
(a multiple of 48 is best); an inline data: URI is ignored. The SVG below is the source of truth.

    uv run python scripts/make_favicons.py
"""
from __future__ import annotations

import struct
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "voicedex/web/static"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# The "V-meter": five level-meter bars whose tops trace a V, dark on an amber app-icon tile (matches the provider
# logos it sits beside and stands out on both themes). SQUARE is the same mark full-bleed, for iOS, which rounds
# corners itself.
_BARS = "".join(f'<rect x="{10 + k * 9.5}" y="{51 - h}" width="6" height="{h}" rx="3" fill="#120c02"/>'
                for k, h in enumerate((38, 26, 13, 26, 38)))
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="#f5a524"/>'
       + _BARS + "</svg>\n")
SQUARE = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64"><rect width="64" height="64" fill="#f5a524"/>'
          + _BARS + "</svg>\n")

PNGS = {"favicon-48.png": 48, "favicon-96.png": 96, "favicon-192.png": 192, "logo.png": 512}
SQUARE_PNGS = {"apple-touch-icon.png": 180}
ICO_SIZES = (16, 32, 48)


def render(size: int, out: Path, svg: str = SVG) -> None:
    html = (f"<html><body style='margin:0;background:transparent'>"
            f"<img src='data:image/svg+xml;utf8,{svg.strip().replace('#', '%23')}' width='{size}' height='{size}'"
            f" style='display:block'></body></html>")
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--default-background-color=00000000", f"--window-size={size},{size}", f"--screenshot={out}",
                    f"file://{f.name}"], check=True, capture_output=True)


def ico(pngs: list[tuple[int, bytes]]) -> bytes:
    """ICO container with embedded PNGs (supported by every current browser and crawler)."""
    head = struct.pack("<HHH", 0, 1, len(pngs))
    offset = 6 + 16 * len(pngs)
    entries, blobs = b"", b""
    for size, data in pngs:
        entries += struct.pack("<BBBBHHII", size % 256, size % 256, 0, 0, 1, 32, len(data), offset)
        blobs += data
        offset += len(data)
    return head + entries + blobs


def main() -> None:
    (STATIC / "favicon.svg").write_text(SVG)
    for name, size in PNGS.items():
        render(size, STATIC / name)
    for name, size in SQUARE_PNGS.items():
        render(size, STATIC / name, SQUARE)
    with tempfile.TemporaryDirectory() as tmp:
        parts = []
        for size in ICO_SIZES:
            p = Path(tmp) / f"{size}.png"
            render(size, p)
            parts.append((size, p.read_bytes()))
    (STATIC / "favicon.ico").write_bytes(ico(parts))
    print("wrote favicon.svg, favicon.ico,", ", ".join([*PNGS, *SQUARE_PNGS]))


if __name__ == "__main__":
    main()
