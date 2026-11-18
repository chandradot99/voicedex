"""A retired API seller that still publishes open weights keeps its open-weights models served."""

from voicedex.catalog.files import ProviderData
from voicedex.catalog.schema import Model, Provider


def test_retired_with_open_weights_is_served():
    ow = Model(id="org/tts", type="tts", name="tts", open_weights={"license": "mit", "url": "u", "commercial_use": True})
    closed = Model(id="api-tts", type="tts", name="api-tts")
    from voicedex.catalog import store
    cat = store.Catalog.__new__(store.Catalog)
    cat.providers = {"gone": ProviderData(Provider(id="gone", name="Gone", type="tts", status="deprecated"), [ow], [])}
    assert cat.active_provider_ids() == {"gone"}
    cat.providers["gone"].models = [closed]
    assert cat.active_provider_ids() == set()
