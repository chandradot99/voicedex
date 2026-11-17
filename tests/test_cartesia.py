"""Cartesia /voices mapping under Cartesia-Version 2026-08-14 (access + accents[] fields)."""

from voicedex.sync.cartesia import _is_public, _to_sync_voice

ITEM = {
    "id": "v1", "name": "Daniel", "gender": "masculine", "description": "Clear assistant voice",
    "language": "en", "access": "public", "status": "active", "is_pro": False, "tagline": "Modern Assistant",
    "preview_file_url": None,
    "accents": [
        {"accent": "castilian", "locale": "es-ES", "is_native": False},
        {"accent": "general-american", "locale": "en-US", "is_native": True},
        {"accent": "standard-hindi", "locale": "hi-IN", "is_native": False},
    ],
}


def test_native_locale_first_and_accent_from_native():
    v = _to_sync_voice(ITEM)
    assert v.languages == ["en-US", "es-ES", "hi-IN"]
    assert v.accent == "american"
    assert v.gender == "male"
    assert v.capabilities == []  # only one native locale
    assert v.meta["locale_accents"]["es-ES"] == "castilian"
    assert v.meta["tagline"] == "Modern Assistant"


def test_multiple_native_locales_flag_multilingual_native():
    item = dict(ITEM, accents=[{"locale": "en-US", "is_native": True}, {"locale": "hi-IN", "is_native": True}])
    assert _to_sync_voice(item).capabilities == ["multilingual_native"]


def test_legacy_language_field_fallback():
    item = {k: v for k, v in ITEM.items() if k != "accents"}
    assert _to_sync_voice(item).languages == ["en"]


def test_public_detection_both_versions():
    assert _is_public({"access": "public"})
    assert not _is_public({"access": "private", "is_public": True})
    assert _is_public({"is_public": True})
    assert not _is_public({})
