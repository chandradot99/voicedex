# Provider verification

A provider page on [voicedex.dev](https://voicedex.dev) can say **"Verified by <provider> on <date>"**.
It means someone at that provider reviewed their listing (models, prices, features, as named on the
page) and confirmed it was accurate on that date.

## What it is not

- **Not an endorsement or a ranking.** Verified and unverified providers are listed, sorted and compared
  the same way. Verification is free and never paid for.
- **Not permanent.** The catalog keeps syncing from each provider's API and docs. Anything that changes
  after the review date is shown as "changed since" on the provider page and on the model page.

## How it works

1. We ask a provider (usually developer relations) to check their listing, or they open a
   [data correction issue](https://github.com/chandradot99/voicedex/issues/new?template=data-correction.yml).
2. We apply their corrections. Prices still come from the provider's own published pricing; when a
   provider asks us to show a different rate (for example a discounted one), the list rate stays visible
   next to it with a note.
3. When they confirm the listing is right, we set `verified` in `data/<provider>/provider.json`:

   ```json
   "verified": {
     "on": "2026-11-19",
     "by": "Speechmatics developer relations",
     "scope": ["models", "pricing", "features"],
     "evidence": "Email reply to our review request."
   }
   ```

   `by` is a team or role, never a person's name. The commit that sets it is the public record.

Providers can ask for a new review at any time, and the date moves forward when they confirm again.

## Want your listing verified?

Open a [data correction issue](https://github.com/chandradot99/voicedex/issues/new?template=data-correction.yml)
and choose "Yes, I work there".
