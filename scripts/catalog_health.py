"""
Catalog health report: what is stale, broken or due. Deterministic and offline (except --samples); no AI.

    uv run python scripts/catalog_health.py              # markdown report
    uv run python scripts/catalog_health.py --samples    # also check every voice-sample link (~2 min)
    uv run python scripts/catalog_health.py --json       # machine-readable, for the /catalog-refresh skill

Sections: sync freshness (per source type), lifecycle (shutdown dates passed or near), pricing age, registry gaps,
discovery pass due, and optionally dead sample links. Thresholds below are the house rules; the skill reads them
from this report rather than re-deriving them.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from voicedex.catalog.files import read_provider_dir  # noqa: E402
from voicedex.sync.registry import REGISTRY  # noqa: E402

# Re-sync when older than this many days. API data moves fast (voices, prices); docs extraction is costlier.
STALE_DAYS = {"api": 14, "mixed": 21, "docs": 45}
EOL_SOON_DAYS = 30
PRICING_STALE_DAYS = 120
INTEGRATIONS_STALE_DAYS = 90     # re-check each framework's integration list (scripts/apply_integrations.py)
DISCOVERY_EVERY_DAYS = 90
EXPANSION_DOC = ROOT / "docs" / "design" / "provider-expansion.md"
_DISCOVERY_MARK = re.compile(r"Last discovery pass:\s*(\d{4}-\d{2}-\d{2})")


@dataclass
class Report:
    today: str
    stale: list[dict] = field(default_factory=list)          # {provider, source, last_synced, age_days}
    never_synced: list[str] = field(default_factory=list)    # registered + syncable, no data/ dir
    unregistered: list[str] = field(default_factory=list)    # data/ dir without a registry entry
    eol_passed: list[dict] = field(default_factory=list)     # {provider, model, eol_date}
    eol_soon: list[dict] = field(default_factory=list)
    retired_due: list[dict] = field(default_factory=list)    # active provider whose retired_on has passed
    pricing_stale: list[dict] = field(default_factory=list)  # {provider, models, oldest}
    discovery: dict = field(default_factory=dict)            # {last, due}
    dead_samples: dict = field(default_factory=dict)         # provider -> count (only with --samples)
    integrations: dict = field(default_factory=dict)         # framework -> {providers, oldest}
    no_features: list[dict] = field(default_factory=list)    # {provider, models, active}: models with no capabilities
    uncommitted_data: bool = False


def build(today: date, samples: bool) -> Report:
    rep = Report(today=today.isoformat())
    data = ROOT / "data"
    registered = {e.provider_id: e for e in REGISTRY}
    on_disk = {p.name for p in data.iterdir() if (p / "provider.json").exists()}

    rep.never_synced = sorted(pid for pid, e in registered.items() if e.syncable and pid not in on_disk)
    rep.unregistered = sorted(on_disk - set(registered))

    for pid in sorted(on_disk):
        pd = read_provider_dir(data / pid)
        prov, entry = pd.provider, registered.get(pid)
        for i in prov.integrations:
            row = rep.integrations.setdefault(i.framework, {"providers": 0, "oldest": i.as_of.isoformat()})
            row["providers"] += 1
            row["oldest"] = min(row["oldest"], i.as_of.isoformat())
        if prov.status == "active" and prov.retired_on and prov.retired_on <= today:
            rep.retired_due.append({"provider": pid, "retired_on": prov.retired_on.isoformat()})
        if entry is None or not entry.syncable:
            continue
        source = str(prov.source or "docs")
        if prov.last_synced is None:
            rep.stale.append({"provider": pid, "source": source, "last_synced": None, "age_days": None})
        else:
            age = (today - prov.last_synced).days
            if age > STALE_DAYS.get(source, STALE_DAYS["docs"]):
                rep.stale.append({"provider": pid, "source": source, "last_synced": prov.last_synced.isoformat(),
                                  "age_days": age})
        old_prices, bare, active = [], 0, 0
        for m in pd.models:
            if m.deprecated_at is not None:
                continue
            active += 1
            bare += not m.capabilities
            if m.eol_date and m.eol_date <= today:
                rep.eol_passed.append({"provider": pid, "model": m.id, "eol_date": m.eol_date.isoformat()})
            elif m.eol_date and m.eol_date <= today + timedelta(days=EOL_SOON_DAYS):
                rep.eol_soon.append({"provider": pid, "model": m.id, "eol_date": m.eol_date.isoformat()})
            if m.pricing and m.pricing.as_of and (today - m.pricing.as_of).days > PRICING_STALE_DAYS:
                old_prices.append(m.pricing.as_of)
        if bare:
            rep.no_features.append({"provider": pid, "models": bare, "active": active})
        if old_prices:
            rep.pricing_stale.append({"provider": pid, "models": len(old_prices), "oldest": min(old_prices).isoformat()})

    rep.stale.sort(key=lambda r: -(r["age_days"] or 10**6))
    rep.no_features.sort(key=lambda r: (-r["models"], r["provider"]))
    text = EXPANSION_DOC.read_text() if EXPANSION_DOC.exists() else ""
    marks = _DISCOVERY_MARK.findall(text)
    last = max(marks) if marks else None
    due = last is None or (today - date.fromisoformat(last)).days > DISCOVERY_EVERY_DAYS
    rep.discovery = {"last": last, "due": due, "every_days": DISCOVERY_EVERY_DAYS}

    status = subprocess.run(["git", "status", "--porcelain", "data"], cwd=ROOT, capture_output=True, text=True)
    rep.uncommitted_data = bool(status.stdout.strip())

    if samples:
        from scripts.check_previews import _check, collect  # noqa: PLC0415 — optional, slow path
        rep.dead_samples = asyncio.run(_dead_samples(collect([]), _check))
    return rep


async def _dead_samples(rows, check) -> dict:
    from collections import Counter, defaultdict
    from urllib.parse import urlparse

    import httpx
    sems = defaultdict(lambda: asyncio.Semaphore(6))
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0), follow_redirects=True,
                                 headers={"User-Agent": "Mozilla/5.0 (voicedex preview check)"}) as client:
        results = await asyncio.gather(*(check(client, sems[urlparse(u).netloc], u) for _, _, u in rows))
    c = Counter(pid for (pid, _, _), r in zip(rows, results) if r != "ok")
    return dict(sorted(c.items()))


def render(rep: Report) -> str:
    out = [f"# Catalog health — {rep.today}", ""]
    def section(title: str, rows: list[str], empty: str = "none") -> None:
        out.append(f"## {title}")
        out.extend(rows or [f"- {empty}"])
        out.append("")

    section(f"Stale syncs (api >{STALE_DAYS['api']}d, mixed >{STALE_DAYS['mixed']}d, docs >{STALE_DAYS['docs']}d)",
            [f"- {r['provider']} ({r['source']}): last synced {r['last_synced'] or 'never'}"
             + (f", {r['age_days']} days" if r["age_days"] is not None else "") for r in rep.stale])
    section("Registered but never synced", [f"- {p}" for p in rep.never_synced])
    section("Data without a registry entry", [f"- {p}" for p in rep.unregistered])
    section("Shutdown date passed — re-sync so merge drops/deprecates them",
            [f"- {r['provider']} / {r['model']} (eol {r['eol_date']})" for r in rep.eol_passed])
    section(f"Shutting down within {EOL_SOON_DAYS} days", [f"- {r['provider']} / {r['model']} (eol {r['eol_date']})"
                                                            for r in rep.eol_soon])
    section("Active provider past its retired_on date", [f"- {r['provider']} ({r['retired_on']})" for r in rep.retired_due])
    section(f"Prices older than {PRICING_STALE_DAYS} days",
            [f"- {r['provider']}: {r['models']} model(s), oldest {r['oldest']}" for r in rep.pricing_stale])
    bare = sum(r["models"] for r in rep.no_features)
    section(f"Models with no features documented ({bare}; capability filters hide them — re-extract with a docs pass)",
            [f"- {r['provider']}: {r['models']} of {r['active']}" for r in rep.no_features[:15]]
            + ([f"- … {len(rep.no_features) - 15} more providers"] if len(rep.no_features) > 15 else []))
    section(f"Framework integrations (re-check every {INTEGRATIONS_STALE_DAYS} days)",
            [f"- {fw}: {r['providers']} providers, checked {r['oldest']}"
             + (" — DUE" if (date.fromisoformat(rep.today) - date.fromisoformat(r["oldest"])).days
                > INTEGRATIONS_STALE_DAYS else "") for fw, r in sorted(rep.integrations.items())],
            empty="none recorded")
    d = rep.discovery
    section("New-provider discovery", [f"- last pass: {d['last'] or 'never recorded'}; "
                                       f"{'DUE' if d['due'] else 'not due'} (every {d['every_days']} days)"])
    if rep.dead_samples:
        section("Dead sample links (re-sync these providers; sync drops dead links)",
                [f"- {p}: {n}" for p, n in rep.dead_samples.items()])
    if rep.uncommitted_data:
        out.append("> Note: data/ has uncommitted changes — review or commit them before a refresh.\n")
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--samples", action="store_true", help="Also check every voice-sample link (slow)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--today", help="Override today's date (YYYY-MM-DD), for testing")
    args = ap.parse_args()
    today = date.fromisoformat(args.today) if args.today else date.today()
    rep = build(today, args.samples)
    print(json.dumps(asdict(rep), indent=1) if args.json else render(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
