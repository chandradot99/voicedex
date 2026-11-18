"""What changed in the catalog, from git history: new models, price changes, shutdown announcements, deprecations.

The catalog's history *is* git (data/<provider>/*.json, one reviewed commit per sync), so the changes feed is
derived by replaying that history and diffing each provider's records commit by commit. The deployed image has no
.git, so CI runs `scripts/build_changes.py` (full-history checkout) and bakes the result into `data/.changes.json`;
local dev computes it straight from git on first use.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import date
from functools import lru_cache
from pathlib import Path

from voicedex.catalog.schema import Model

CHANGES_FILE = ".changes.json"
# History before this date is the v2 import and its first-sync clean-ups (ids, schema, vocabulary churn), not real
# upstream changes. Providers already present by then are the baseline; everything after is a real event.
FEED_STARTS = date(2026, 11, 17)
# Commits that fix our own data rather than record an upstream change are not "changes": mark them with
# SKIP_MARKER in the commit message. Listed here: corrections made before the marker existed.
SKIP_MARKER = "[skip changes]"
SKIP_COMMITS = {
    "960e920",   # Kitten: headline price corrected from the Pro-plan promo to pay-as-you-go (PR #3)
}

KIND_LABELS = {
    "price_changed": "Price changed", "price_published": "Price published", "model_added": "Added to the catalog",
    "shutdown_announced": "Shutdown announced", "model_deprecated": "Deprecated upstream",
    "model_removed": "Shut down", "now_ga": "Now generally available", "provider_added": "New provider",
    "provider_retired": "Provider retired",
}


@dataclass
class Change:
    date: str                     # ISO date of the commit that recorded it
    kind: str
    provider_id: str
    commit: str = ""
    model_type: str = ""
    model_id: str = ""
    model_name: str = ""
    before: str = ""
    after: str = ""

    @property
    def model_key(self) -> str:
        return f"{self.provider_id}/{self.model_type}/{self.model_id}" if self.model_id else ""


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True, text=True).stdout


def _price(raw: dict) -> str:
    from voicedex.web.views import price_label
    try:
        return price_label(Model.model_validate(raw)) or ""
    except Exception:                                   # an older schema version: compare what we can
        p = raw.get("pricing") or {}
        return f"{p.get('price_usd') or p.get('price')} per {p.get('unit')}" if p else ""


def _models(text: str | None) -> dict[tuple[str, str], dict]:
    if not text:
        return {}
    try:
        return {(m.get("type", ""), m["id"]): m for m in json.loads(text)}
    except (ValueError, KeyError, TypeError):
        return {}


def diff_models(old: dict, new: dict, day: str, provider_id: str, commit: str) -> list[Change]:
    out: list[Change] = []
    base = dict(date=day, provider_id=provider_id, commit=commit)
    for key, m in new.items():
        ident = dict(model_type=key[0], model_id=key[1], model_name=m.get("name") or key[1])
        o = old.get(key)
        if o is None:
            if not m.get("deprecated_at"):
                out.append(Change(**base, **ident, kind="model_added"))
            continue
        if m.get("deprecated_at") and not o.get("deprecated_at"):
            out.append(Change(**base, **ident, kind="model_deprecated"))
            continue
        if m.get("eol_date") and m.get("eol_date") != o.get("eol_date"):
            out.append(Change(**base, **ident, kind="shutdown_announced", before=o.get("eol_date") or "",
                              after=m["eol_date"]))
        before, after = _price(o), _price(m)
        if after and before != after:
            out.append(Change(**base, **ident, kind="price_changed" if before else "price_published",
                              before=before, after=after))
        if m.get("lifecycle") == "ga" and o.get("lifecycle") in ("alpha", "beta"):
            out.append(Change(**base, **ident, kind="now_ga", before=o["lifecycle"], after="ga"))
    for key, o in old.items():
        if key not in new and not o.get("deprecated_at"):
            out.append(Change(**base, kind="model_removed", model_type=key[0], model_id=key[1],
                              model_name=o.get("name") or key[1]))
    return out


def build_changes(repo: Path, feed_starts: date = FEED_STARTS) -> list[Change]:
    """Replay data/ history oldest-first; newest change first in the result."""
    log = _git(repo, "log", "--reverse", "--format=@%H %cs %s", "--name-only", "--",
               "data/*/models.json", "data/*/provider.json")
    commits: list[tuple[str, str, bool, list[str]]] = []
    for line in log.splitlines():
        if line.startswith("@"):
            sha, day, subject = (line[1:].split(" ", 2) + [""])[:3]
            skip = SKIP_MARKER in subject or any(sha.startswith(c) for c in SKIP_COMMITS)
            commits.append((sha, day, skip, []))
        elif line.strip() and commits:
            commits[-1][3].append(line.strip())
    state: dict[str, dict] = {}            # path -> last parsed content
    seen_providers: set[str] = set()
    per_commit: list[list[Change]] = []
    for sha, day, skip, paths in commits:
        changes: list[Change] = []
        per_commit.append(changes)
        live = date.fromisoformat(day) >= feed_starts and not skip   # skipped commits still advance the state
        for path in paths:
            parts = Path(path).parts
            if len(parts) != 3:
                continue
            pid, name = parts[1], parts[2]
            try:
                text = _git(repo, "show", f"{sha}:{path}")
            except subprocess.CalledProcessError:
                text = None                                   # file deleted in this commit
            if name == "models.json":
                new = _models(text)
                if pid not in seen_providers:
                    seen_providers.add(pid)
                    if live and new:
                        changes.append(Change(date=day, kind="provider_added", provider_id=pid, commit=sha,
                                              after=f"{len(new)} models"))
                elif live:
                    changes += diff_models(state.get(path, {}), new, day, pid, sha)
                state[path] = new
            else:
                try:
                    prov = json.loads(text) if text else {}
                except ValueError:
                    prov = {}
                was = state.get(path, {})
                if live and was and was.get("status") != "deprecated" and prov.get("status") == "deprecated":
                    changes.append(Change(date=day, kind="provider_retired", provider_id=pid, commit=sha,
                                          after=prov.get("retired_on") or ""))
                state[path] = prov
    return [c for batch in reversed(per_commit) for c in batch]      # newest commit first, in-commit order kept


def write_changes(repo: Path, out: Path) -> int:
    changes = build_changes(repo)
    out.write_text(json.dumps([asdict(c) for c in changes], indent=1) + "\n")
    return len(changes)


@lru_cache(maxsize=4)
def load_changes(data_dir: Path) -> tuple[Change, ...]:
    """Baked file if present (deployed image), else computed from git (local dev), else empty."""
    f = data_dir / CHANGES_FILE
    if f.exists():
        return tuple(Change(**c) for c in json.loads(f.read_text()))
    repo = data_dir.parent
    if (repo / ".git").exists():
        try:
            return tuple(build_changes(repo))
        except (subprocess.CalledProcessError, FileNotFoundError):
            return ()
    return ()
