"""Render the share image (voicedex/web/static/og.png, 1200x630) in the site's "Datasheet" style (Instrument Sans + Geist Mono, warm ink).

The price strip is drawn from the live catalog's text-to-speech prices, so re-run this after big
catalog changes. Needs Google Chrome (headless) and network access for the Instrument Sans / Geist Mono web fonts.

    uv run python scripts/make_og_image.py                      # writes voicedex/web/static/og.png
    uv run python scripts/make_og_image.py --size 1280x640 --out /tmp/og-github.png   # GitHub social preview
"""

from __future__ import annotations

import argparse
import math
import subprocess
import tempfile
from pathlib import Path

from voicedex.catalog.store import Catalog
from voicedex.config import settings
from voicedex.web import views

CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
ROOT = Path(__file__).resolve().parent.parent


def tts_prices(catalog: Catalog) -> list[float]:
    return sorted(n[0] for r in views.active_models(catalog)
                  if r.model.type == "tts" and (n := views.normalized_price(r.model)) and n[0] > 0)


def page(prices: list[float], W: int, H: int) -> str:
    pad = round(W * 0.056)
    lo, hi = math.log10(0.5), math.log10(400)
    width, ncol, sq, gap, base = W - 2 * pad, 64, 7, 2, 92
    colw = width / ncol
    cols: dict[int, int] = {}
    for p in prices:
        i = max(0, min(ncol - 1, int((math.log10(p) - lo) / (hi - lo) * ncol)))
        cols[i] = cols.get(i, 0) + 1
    rects = "".join(
        f'<rect x="{colw * (i + .5) - sq / 2:.1f}" y="{base - 6 - (k + 1) * (sq + gap) + gap:.1f}" '
        f'width="{sq}" height="{sq}" fill="#f5a524"/>' for i, n in cols.items() for k in range(n))
    ticks = "".join(
        f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{base}" y2="{base + 6}" stroke="#33312d"/>'
        f'<text x="{x:.1f}" y="{base + 24}" text-anchor="middle">${v}</text>'
        for v in (1, 10, 100) for x in [(math.log10(v) - lo) / (hi - lo) * width])
    svg = (f'<svg width="{width}" height="{base + 30}" font-family="Instrument Sans" font-size="15" fill="#a19e99">'
           f'{rects}<line x1="0" x2="{width}" y1="{base}" y2="{base}" stroke="#33312d"/>{ticks}</svg>')
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:wdth,wght@75..100,400..700&family=Geist+Mono:wght@400;500&display=block" rel="stylesheet">
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{width:{W}px;height:{H}px;background:#0b0a08;color:#f6f5f2;font-family:'Instrument Sans',sans-serif;overflow:hidden}}
.wrap{{position:absolute;inset:0;padding:{pad - 8}px {pad}px {pad - 16}px;display:flex;flex-direction:column}}
.top{{display:flex;align-items:center;justify-content:space-between;padding-bottom:22px;border-bottom:1px solid #22211e}}
.brand{{display:flex;align-items:center;gap:16px;font-weight:600;font-size:34px;letter-spacing:-.02em}}
.url{{font-family:'Geist Mono';font-size:20px;color:#f5a524}}
h1{{margin-top:{int(H * .075)}px;font-weight:700;letter-spacing:-.04em;font-size:{int(H * .1)}px;line-height:1.04;letter-spacing:-.025em}}
.facts{{margin-top:22px;font-size:22px;font-variant-numeric:tabular-nums;color:#c9c7c3}}
.facts b{{color:#f6f5f2;font-weight:600}}
.spec{{margin-top:auto}}
.label{{font-size:15px;font-weight:500;color:#a19e99;margin-bottom:8px;display:flex;justify-content:space-between}}
</style></head><body><div class="wrap">
<div class="top"><div class="brand"><svg width="40" height="40" viewBox="0 0 64 64"><rect width="64" height="64" rx="15" fill="#17140f"/><rect x=".5" y=".5" width="63" height="63" rx="14.5" fill="none" stroke="#fff" stroke-opacity=".09"/><rect x="10.0" y="13" width="6" height="38" rx="3" fill="#f5a524"/><rect x="19.5" y="24" width="6" height="27" rx="3" fill="#f5a524"/><rect x="29.0" y="35" width="6" height="16" rx="3" fill="#f5a524"/><rect x="38.5" y="24" width="6" height="27" rx="3" fill="#f5a524"/><rect x="48.0" y="13" width="6" height="38" rx="3" fill="#f5a524"/></svg>Voicedex</div><div class="url">voicedex.dev</div></div>
<h1>Every speech model and voice,<br>compared.</h1>
<p class="facts"><b>800+</b> models · <b>15,000+</b> voices · <b>120+</b> providers · STT · TTS · S2S</p>
<div class="spec"><div class="label"><span>Text-to-speech prices</span><span>USD per 1M characters, log scale</span></div>{svg}</div>
</div></body></html>"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--size", default="1200x630")
    ap.add_argument("--out", default=str(ROOT / "voicedex/web/static/og.png"))
    args = ap.parse_args()
    W, H = (int(x) for x in args.size.split("x"))
    html = page(tts_prices(Catalog.load(settings.data_path)), W, H)
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
    subprocess.run([CHROME, "--headless=new", "--disable-gpu", "--hide-scrollbars", "--force-device-scale-factor=1",
                    "--virtual-time-budget=6000", f"--window-size={W},{H}", f"--screenshot={args.out}",
                    f"file://{f.name}"], check=True, capture_output=True)
    print(f"wrote {args.out} ({W}x{H})")


if __name__ == "__main__":
    main()
