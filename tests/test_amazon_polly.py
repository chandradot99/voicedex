"""Amazon Polly docs path: the developer guide's "Available voices" table → DescribeVoices-shaped rows."""

from voicedex.sync.amazon_polly import AmazonPollySyncer, parse_voice_table

# Recorded excerpt of https://docs.aws.amazon.com/polly/latest/dg/available-voices.md (2026-11-18).
TABLE = r"""
# Available voices

|  | Language and language variants | Language code | Name/ID | Gender | Generative voice | Long Form voice | Neural voice | Standard voice |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 1 | **Arabic** | arb | Zeina | Female | No | No | No | Yes |
| 12 |  **English (Indian)**  | en-IN | Aditi\* <br />Raveena<br />Kajal\* | Female<br />Female<br />Female | No<br />No<br />Yes | No<br />No<br />No | No<br />No<br />Yes | Yes<br />Yes<br />No |
| 17 |  **English (US)**  | en-US | Ivy<br />Joanna\*\*<br />Ruth | Female (child)<br />Female<br />Female | No<br />Yes<br />Yes | No<br />No<br />Yes | Yes<br />Yes<br />Yes | Yes<br />Yes<br />No |
| 18 |  **English (Welsh)**  | en-GB-WLS | Geraint | Male | No | No | No | Yes |
| 20 | **French** | fr-FR | Céline/Celine<br />Léa | Female<br />Female | Yes<br />Yes | No<br />No | No<br />Yes | Yes<br />Yes |
| 26 | **Hindi** | hi-IN | Aditi\*<br />Kajal\* | Female<br />Female | No<br />Yes | No<br />No | No<br />Yes | Yes<br />No |

\* This voice is bilingual.
"""


def _rows():
    return {r["Id"]: r for r in parse_voice_table(TABLE)}


def test_ids_are_ascii_and_bilingual_voices_merge():
    rows = _rows()
    assert set(rows) == {"Zeina", "Aditi", "Raveena", "Kajal", "Ivy", "Joanna", "Ruth", "Geraint", "Celine", "Lea"}
    assert rows["Celine"]["Name"] == "Céline"
    assert rows["Lea"]["Name"] == "Léa"
    assert rows["Aditi"]["LanguageCode"] == "en-IN"
    assert rows["Aditi"]["AdditionalLanguageCodes"] == ["hi-IN"]
    assert sorted(rows["Kajal"]["SupportedEngines"]) == ["generative", "neural"]
    assert rows["Ivy"]["Gender"] == "Female" and rows["Ivy"]["Age"] == "child"
    assert sorted(rows["Ruth"]["SupportedEngines"]) == ["generative", "long-form", "neural"]


def test_voices_and_models_match_api_shape():
    rows = parse_voice_table(TABLE)
    api = AmazonPollySyncer()
    voices = {v.voice_id: v for v in api._parse_voices(rows)}
    assert voices["Aditi"].languages == ["en-IN", "hi-IN"]
    assert voices["Zeina"].languages == ["ar"]
    assert voices["Geraint"].languages == ["en-GB"] and voices["Geraint"].accent == "welsh"
    assert sorted(voices["Celine"].compatible_models) == ["polly-generative", "polly-standard"]

    models = {m.model_id: m for m in api._derive_tts_models(rows)}
    assert set(models) == {"polly-generative", "polly-long-form", "polly-neural", "polly-standard"}
    assert models["polly-long-form"].languages == ["en-US"]
    assert "hi-IN" in models["polly-generative"].languages
    assert models["polly-generative"].is_default
