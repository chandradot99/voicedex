"""The health report runs against the real data/ and flags passed / upcoming shutdown dates."""

import importlib.util
import sys
from datetime import date
from pathlib import Path

_spec = importlib.util.spec_from_file_location("catalog_health", Path(__file__).parents[1] / "scripts" / "catalog_health.py")
health = importlib.util.module_from_spec(_spec)
sys.modules["catalog_health"] = health   # dataclasses resolve their module at class creation
_spec.loader.exec_module(health)


def test_report_flags_shutdowns_and_staleness():
    far = health.build(date(2030, 1, 1), samples=False)
    assert far.stale and far.discovery["due"]
    assert all(r["eol_date"] < "2030-01-01" for r in far.eol_passed)
    text = health.render(far)
    assert "Stale syncs" in text and "New-provider discovery" in text
