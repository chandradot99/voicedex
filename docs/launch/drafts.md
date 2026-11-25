# Voicedex launch drafts

All numbers are from the catalog on 2026-11-18. Re-check them on the day you post (the site updates as
providers change). Every post is in the first person; edit the voice to taste.

**Data caveat used throughout:** Kitten TTS 2's $0.65 per 1M chars is a limited-time promo on a
$14.99/month plan (pay-as-you-go is $15), so it's left out of every "cheapest" claim below.

Suggested order: Show HN (Tue–Thu, ~8–10am US Eastern) → r/speechtech and r/LocalLLaMA the same or next
day → the article a few days later (it gives you a second wave) → awesome-list PRs any time.

---

## 1. Show HN

**Title** (80 char limit):

> Show HN: Voicedex – open catalog of 800 speech AI models with comparable prices

**URL:** https://voicedex.dev

**First comment** (post it yourself right after submitting):

> Hi HN. I kept needing answers like "which TTS APIs support Tamil, and what do they cost?" or "is this
> STT model about to be shut down?", and every provider documents it differently: prices per character,
> per minute, per second or per token; languages as names, codes or "100+"; deprecations buried in
> changelogs. So I built a catalog that normalizes all of it.
>
> What's in it right now: 815 models (444 speech-to-text, 297 text-to-speech, 74 speech-to-speech),
> 15,499 voices (2,784 with audio samples) from 126 providers, plus 13 providers that shut down or
> stopped selling, kept with dates and evidence.
>
> How it works:
>
> - The data is plain JSON in git. Each provider has a syncer that uses its API where one exists and its
>   docs where not (docs extraction is LLM-assisted; every change lands as a reviewed diff). Price history
>   is literally `git log -p`.
> - Prices are normalized (TTS per 1M characters, STT per hour) and only taken from vendor pages. Non-USD
>   prices are shown as published, never converted. Unknown stays empty rather than guessed.
> - Models that disappear upstream are marked deprecated, not deleted. Announced shutdown dates are
>   tracked: 26 models shut down in the next 90 days.
>
> A few things I didn't expect: published TTS prices span roughly $1 to $250 per 1M characters (median
> $30); STT spans $0.03 to $4.68 per hour (median $0.72). And there's a "language tax" on TTS: the
> cheapest listed price is $4/1M chars for Hindi, Arabic or Tamil, but $15 for Swahili, Amharic or Zulu
> and $40 for Yoruba. STT barely has one (Swahili and Hindi both start at $0.10/hr).
>
> There's a free read-only API (`/v1/models?type=stt&capabilities=speaker_diarization&region=eu`), the
> whole catalog as one JSON file, and an llms.txt. Code and data are Apache 2.0:
> https://github.com/chandradot99/voicedex
>
> I'd love to hear what's wrong or missing. Wrong prices and missing providers are the most useful reports.

---

## 2. Reddit

### r/speechtech

**Title:** I built an open catalog of 815 STT/TTS/speech-to-speech models with normalized prices and shutdown dates

> Every provider prices and documents things differently, so comparing STT or TTS APIs means a dozen
> tabs. I put it all in one place: https://voicedex.dev
>
> - 444 STT, 297 TTS and 74 speech-to-speech models from 126 providers, 15.5k voices
> - Prices normalized: TTS per 1M chars, STT per hour, only from vendor pages
> - Filter by language and feature, e.g. [STT with speaker diarization](https://voicedex.dev/speech-to-text/speaker-diarization)
>   (227 models) or [Swahili STT](https://voicedex.dev/speech-to-text/swahili) (47)
> - Scheduled shutdowns tracked: 26 models in the next 90 days
> - Free JSON API, data in git (Apache 2.0): https://github.com/chandradot99/voicedex
>
> If you spot a wrong number or a missing provider, tell me. Corrections are the whole point.

### r/LocalLLaMA

**Title:** 86 open-weights speech models (61 TTS, 22 STT, 3 speech-to-speech) in one comparable list, with licences

> I maintain an open catalog of speech models and the open-weights slice turned out bigger than I
> expected, so I made it easy to browse: https://voicedex.dev/text-to-speech/open-source
>
> Each entry links to the Hugging Face repo, shows the licence and whether commercial use is allowed
> (derived from the licence; blank when unclear), plus languages and features. Open-weights models are
> synced from the Hugging Face Hub automatically with a popularity bar, not hand-picked.
>
> It also lists the hosted APIs for the same tasks, so you can see what you'd pay instead of self-hosting:
> TTS APIs run from about $1 to $250 per 1M characters (median $30).
>
> Data and code are Apache 2.0: https://github.com/chandradot99/voicedex. Missing a model you use? Tell me.

### r/MachineLearning (weekend "[P]" project flair; check the sub's current self-promo rules first)

**Title:** [P] Voicedex: an open, git-versioned dataset of 815 speech models (STT/TTS/S2S) with normalized pricing

> A structured dataset of speech AI models across 126 providers: languages (BCP-47), features from a
> controlled vocabulary, prices normalized to per-1M-chars / per-hour, regions, interfaces, lifecycle and
> shutdown dates, and provenance (source URLs + date) on every record. Synced from provider APIs and docs;
> every change is a reviewed git diff, so it doubles as a price-history dataset.
>
> Browse: https://voicedex.dev · JSON: https://voicedex.dev/v1/catalog.json ·
> Repo (Apache 2.0): https://github.com/chandradot99/voicedex
>
> Feedback on the schema especially welcome.

---

## 3. Data article

Post on your own blog, dev.to or Hashnode (set the canonical URL to wherever it's first published),
then share the link. ~650 words.

### The language tax: what text-to-speech costs once you leave English

I track prices for 297 text-to-speech models across 126 providers in an open catalog,
[Voicedex](https://voicedex.dev). Prices are normalized to US dollars per 1 million characters and taken
only from the vendors' own pricing pages. When I sorted them by language, a pattern jumped out.

**The cheapest listed TTS price, by language** (excluding promotional pricing):

| Language | TTS models listing it | Priced | Cheapest listed |
|---|---:|---:|---:|
| Spanish, French, German, Hindi, Arabic, Japanese, Chinese | 103–139 | 47–63 | $4 |
| Bengali, Tamil, Vietnamese | 67–85 | 28–44 | $4 |
| Swahili | 35 | 13 | $15 |
| Amharic | 17 | 6 | $15 |
| Zulu | 13 | 7 | $15 |
| Hausa | 12 | 5 | $15 |
| Yoruba | 9 | 2 | $40 |

For the world's largest languages, competition pushes the floor to $4 per million characters (the
"standard" voice tiers from the big clouds). For Swahili, spoken by well over 100 million people, the floor
is almost four times higher. For Yoruba it is ten times higher, and only two models publish a price at all.

**Speech-to-text doesn't have the same tax.** The cheapest listed STT for Swahili is $0.10 per hour,
the same as for Hindi, Arabic or Tamil, and Yoruba starts at $0.13. Multilingual speech-recognition
models trained on huge mixed-language datasets made recognition cheap almost everywhere at once.
Synthesis still depends much more on voices built language by language.

**The overall spread is huge in both directions:**

- TTS: about $1 to $250 per 1M characters, median $30 (94 of 297 models publish a comparable price).
- STT: $0.03 to $4.68 per hour, median $0.72 (223 of 444).
- Speech-to-speech: $0.78 to $60 per hour, median $3 (13 of 74).

Most models don't publish a comparable per-unit price at all: they're credit plans, enterprise-only or
per-token. That's a pricing problem of its own.

**Models disappear fast.** 36 speech models currently have an announced shutdown date, 26 of them within
the next 90 days. Thirteen providers in the catalog have shut down or stopped selling entirely, including
PlayHT, Coqui, LMNT and Resemble AI.

**Caveats:**

- "Cheapest listed" is the lowest published tier. The $4 tiers are older-generation voices; newer
  neural voices cost more, and quality differs a lot.
- Language support is what each provider claims. A model listing a language doesn't guarantee it sounds
  native.
- Prices move. These are from 18 November 2026; the live numbers are at
  [voicedex.dev](https://voicedex.dev), and every change is in the
  [git history](https://github.com/chandradot99/voicedex).

If you build voice products for African or South Asian markets, the comparison pages are the fastest way
to see your real options: [Swahili TTS](https://voicedex.dev/text-to-speech/swahili),
[Hindi TTS](https://voicedex.dev/text-to-speech/hindi),
[STT by language](https://voicedex.dev/speech-to-text).

Corrections welcome: if a price here is wrong, open an issue with the vendor's link and it gets fixed
in the open.

---

## 4. Awesome-list entries

Open these as PRs to each list (I can open them from your account once you approve each one).

### ishandutta2007/Awesome-Text-to-Speech (229★, updated daily)

No section fits a comparison tool exactly. Propose it under **"Notable Research Papers & Community
Discussions"** or ask in the PR whether the maintainer wants a "Comparison & Pricing" subsection. Its
tables have different columns per section, so match whichever section the maintainer picks.

> PR title: Add Voicedex (open TTS/STT model catalog with normalized pricing)
>
> PR body: Voicedex is a free, open (Apache 2.0) catalog of 297 TTS models across 126 providers with
> prices normalized per 1M characters, languages, features and shutdown dates. Data is versioned in git.
> Happy to move it to whichever section fits best.

### ALLBOTSIO/awesome-voice-ai (tables, alphabetical; CONTRIBUTING requires factual, non-marketing text)

Best fit: **Frameworks & SDKs** (it's an open dataset + API). If they prefer, use their
[Submit a Tool](https://github.com/ALLBOTSIO/awesome-voice-ai/issues/new?template=submit-tool.yml)
issue form instead of a PR.

> Row (adapt to that section's columns): **[Voicedex](https://voicedex.dev)**: Open catalog and free
> API of 815 STT/TTS/speech-to-speech models from 126 providers with normalized prices, languages,
> features and shutdown dates. Apache 2.0.

### ai4s-research/awesome-text-to-speech · submitaitools/awesome-voice-ai-tools

Smaller lists; same one-liner. Check each README's format before opening.

---

## 5. Short posts (X / LinkedIn / Bluesky)

> Text-to-speech has a language tax. The cheapest listed TTS price is $4 per 1M characters for Hindi or
> Arabic, $15 for Swahili or Zulu, and $40 for Yoruba. Speech-to-text barely has one ($0.10/hr for both
> Swahili and Hindi).
>
> From an open catalog of 815 speech models I maintain: voicedex.dev

> 26 speech AI models shut down in the next 90 days, including Speechify's Simba models (Nov 21) and
> Rime's Mist v1/v2 (Dec 3). Every announced date, with the replacement model, in one list:
> voicedex.dev/models?status=ending
