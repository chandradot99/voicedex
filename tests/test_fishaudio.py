"""Fish Audio: only official voices are published; volatile counters never stored."""

from naaviq.sync.fishaudio import FishAudioSyncer

OFFICIAL = {"nickname": "Fish Official"}


def test_only_official_trained_voices():
    v = FishAudioSyncer()._parse_voices([
        {"_id": "a", "title": "Official", "state": "trained", "author": OFFICIAL, "tags": ["female", "calm", "te-in", "cale_oct_26", "voice-factory"],
         "languages": ["en"], "like_count": 9, "task_count": 99},
        {"_id": "b", "title": "Celebrity clone", "state": "trained", "author": {"nickname": "someone"}},
        {"_id": "c", "title": "Untrained", "state": "training", "author": OFFICIAL},
        {"_id": "d", "title": "Taken down", "state": "trained", "author": OFFICIAL, "dmca_taken_down": True},
    ])
    assert [x.voice_id for x in v] == ["a"]
    assert v[0].gender == "female" and v[0].tags == ["calm"]
    assert "like_count" not in v[0].meta and "task_count" not in v[0].meta
