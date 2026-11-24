"""Fetch each provider's icon from its own website into voicedex/web/static/logos/<id>.png (64x64, transparent).

The site shows these beside provider names. Source = the provider's own site (provider.json `website`): its
apple-touch-icon, then its largest declared icon, then /favicon.ico. Everything is re-encoded as PNG; SVG icons
are rasterized with headless Chrome and never served as SVG (an SVG from another site can carry script).
Icons smaller than MIN_PX are skipped, so the page falls back to a lettered tile instead of a blurry upscale.

    uv run --with pillow python scripts/fetch_logos.py              # only providers without a logo yet
    uv run --with pillow python scripts/fetch_logos.py --force deepgram cartesia
    uv run --with pillow python scripts/fetch_logos.py --report     # which providers have none

A wrong or ugly icon can be replaced by hand: drop a 64x64 PNG at static/logos/<id>.png (the provider's press
kit is the best source) and the fetcher leaves it alone unless --force is passed.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin

import httpx
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
OUT = ROOT / "voicedex" / "web" / "static" / "logos"
SIZE = 64
MIN_PX = 32
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
HEADERS = {"User-Agent": "Mozilla/5.0 (compatible; voicedex-logo-fetch)"}


class _Icons(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.icons: list[tuple[int, str, str]] = []      # (priority, size_px, href)

    def handle_starttag(self, tag, attrs):
        if tag != "link":
            return
        a = dict(attrs)
        rel = (a.get("rel") or "").lower()
        href = a.get("href")
        if not href or "icon" not in rel or "mask-icon" in rel:
            return
        m = re.search(r"(\d+)x\d+", a.get("sizes") or "")
        px = int(m.group(1)) if m else (999 if href.lower().endswith(".svg") or "svg" in (a.get("type") or "") else 0)
        prio = 0 if "apple-touch-icon" in rel else 1
        self.icons.append((prio, px, href))


def _platform_avatar(client: httpx.Client, site: str) -> list[str]:
    """Providers whose website is a GitHub or Hugging Face org page: the org's own avatar, not the platform's icon."""
    m = re.match(r"https?://(?:www\.)?(github\.com|huggingface\.co)/([^/?#]+)", site)
    if not m:
        return []
    host, org = m.groups()
    if host == "github.com":
        return [f"https://github.com/{org}.png?size=128"]
    try:
        url = client.get(f"https://huggingface.co/api/organizations/{org}/avatar").json().get("avatarUrl")
    except (httpx.HTTPError, ValueError):
        return []
    return [urljoin("https://huggingface.co", url)] if url else []


def _candidates(client: httpx.Client, site: str) -> list[str]:
    if re.match(r"https?://(?:www\.)?(github\.com|huggingface\.co)/", site):
        return _platform_avatar(client, site)          # never the platform's own favicon
    try:
        r = client.get(site)
        base = str(r.url)
        p = _Icons()
        p.feed(r.text[:400_000])
    except (httpx.HTTPError, UnicodeDecodeError):
        return [urljoin(site, "/favicon.ico")]
    ranked = sorted(p.icons, key=lambda t: (t[0], -t[1]))
    urls = [urljoin(base, h) for _, _, h in ranked
            if not re.search(r"/(vite|next|react|vercel|favicon-default)\.svg$", h.split("?")[0])]   # framework defaults
    return urls + [urljoin(base, "/apple-touch-icon.png"), urljoin(base, "/favicon.ico")]


def _rasterize_svg(svg: bytes) -> Image.Image | None:
    if not Path(CHROME).exists():
        return None
    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / "icon.svg"
        src.write_bytes(svg)
        page = Path(tmp) / "page.html"
        page.write_text(f'<html><body style="margin:0;background:transparent"><img src="{src.as_uri()}" '
                        f'style="width:{SIZE * 2}px;height:{SIZE * 2}px;object-fit:contain"></body></html>')
        shot = Path(tmp) / "shot.png"
        subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--default-background-color=00000000",
                        f"--window-size={SIZE * 2},{SIZE * 2}", "--allow-file-access-from-files",
                        f"--screenshot={shot}", page.as_uri()], capture_output=True, timeout=60)
        return Image.open(shot).convert("RGBA") if shot.exists() else None


def _decode(body: bytes, ctype: str, url: str) -> Image.Image | None:
    if "svg" in ctype or url.lower().split("?")[0].endswith(".svg") or body.lstrip()[:5] in (b"<svg ", b"<?xml"):
        return _rasterize_svg(body)
    try:
        img = Image.open(io.BytesIO(body))
        if getattr(img, "format", "") == "ICO":            # pick the largest frame
            sizes = sorted(img.info.get("sizes", {img.size}), reverse=True)
            img.size = sizes[0]
        return img.convert("RGBA")
    except Exception:                                          # noqa: BLE001 - any undecodable body is just skipped
        return None


def _normalize(img: Image.Image) -> Image.Image:
    bbox = img.getbbox()                                       # trim transparent margins so marks fill the tile
    if bbox:
        img = img.crop(bbox)
    w, h = img.size
    side = max(w, h)
    square = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    square.paste(img, ((side - w) // 2, (side - h) // 2))
    return _flatten(square.resize((SIZE, SIZE), Image.LANCZOS))


def _flatten(img: Image.Image) -> Image.Image:
    """Make every logo an opaque tile so it reads on both themes: a transparent icon is laid on white when its mark
    is dark and on near-black when its mark is light (a black mark on our dark page would otherwise vanish)."""
    img = img.convert("RGBA")
    alpha = img.getchannel("A")
    if alpha.getextrema()[0] >= 250:                           # already opaque
        return img
    raw = img.tobytes()
    px = [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 4) if raw[i + 3] > 128]
    lum = sum(0.2126 * r + 0.7152 * g + 0.0722 * b for r, g, b in px) / (255 * len(px)) if px else 0
    tile = Image.new("RGBA", img.size, (255, 255, 255, 255) if lum < 0.55 else (24, 23, 21, 255))
    inner = img.resize((round(SIZE * 0.78),) * 2, Image.LANCZOS)          # breathing room inside the tile
    off = (SIZE - inner.size[0]) // 2
    tile.alpha_composite(inner, (off, off))
    return tile


def fetch(pid: str, site: str, client: httpx.Client) -> str:
    for url in _candidates(client, site):
        try:
            r = client.get(url)
        except httpx.HTTPError:
            continue
        if r.status_code != 200 or not r.content or len(r.content) > 2_000_000:
            continue
        img = _decode(r.content, r.headers.get("content-type", ""), url)
        if img is None or min(img.size) < MIN_PX:
            continue
        _normalize(img).save(OUT / f"{pid}.png", optimize=True)
        return url
    return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ids", nargs="*")
    ap.add_argument("--force", action="store_true", help="re-fetch even if a logo exists")
    ap.add_argument("--report", action="store_true", help="list providers without a logo and exit")
    ap.add_argument("--reprocess", action="store_true", help="re-run tile flattening on the logos already saved")
    args = ap.parse_args()
    OUT.mkdir(parents=True, exist_ok=True)
    if args.reprocess:
        for f in sorted(OUT.glob("*.png")):
            _flatten(Image.open(f)).save(f, optimize=True)
        print("reprocessed", len(list(OUT.glob("*.png"))))
        return 0
    providers = {}
    for f in sorted(DATA.glob("*/provider.json")):
        p = json.loads(f.read_text())
        providers[f.parent.name] = p.get("website") or ""
    if args.report:
        missing = [pid for pid in providers if not (OUT / f"{pid}.png").exists()]
        print(f"{len(providers) - len(missing)}/{len(providers)} providers have a logo")
        print("missing:", " ".join(missing) or "none")
        return 0
    todo = args.ids or [pid for pid in providers if args.force or not (OUT / f"{pid}.png").exists()]
    ok = 0
    with httpx.Client(headers=HEADERS, follow_redirects=True, timeout=15) as client:
        for pid in todo:
            site = providers.get(pid)
            if not site:
                print(f"  {pid}: no website in provider.json")
                continue
            src = fetch(pid, site, client)
            ok += bool(src)
            print(f"  {'✓' if src else '✗'} {pid}: {src or 'no icon of at least %dpx' % MIN_PX}")
    print(f"{ok}/{len(todo)} fetched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
