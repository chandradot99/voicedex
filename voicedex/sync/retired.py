"""Placeholder syncer for retired providers that never had a syncer (sync skips retired entries)."""

from voicedex.sync.base import ProviderSyncer, SyncResult


class RetiredSyncer(ProviderSyncer):
    source = "docs"

    async def sync(self) -> SyncResult:
        raise RuntimeError(f"{self.provider_id} is retired; see data/<id>/provider.json")
