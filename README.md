# Empty Homes

A public map of every likely-vacant property in Philadelphia: who owns it, how long it has sat empty and tax-delinquent, and a way for anyone to pull the receipts on a house, a block, or the landlord holding the most.

Built with and for [Poor People's Army](https://ppehrc.org) (PPEHRC), whose core fight is publicly owned homes sitting vacant while people sleep outside. Their argument has always been provable from public records; those records just live in four city datasets that do not talk to each other. This project joins them.

## What it does

- **Map + search your block.** Every parcel the city flags as likely vacant, colored by who owns it. Type an address, get the empty homes around it.
- **The receipt.** Each parcel page shows owner, years tax-delinquent, open violations, market value, and a transparent accountability score, every fact labeled with its source dataset.
- **Who owns the most.** A ranked leaderboard of owners, public agencies and private landlords alike. Owner names are entity-resolved: agency name variants merge, and LLCs sharing a mailing address are linked as a network. The fixture data alone surfaced one Center City address serving as the mailing address for 12 differently-named land-holding LLCs.
- **Ask the data.** A grounded Claude layer answers plain-language questions ("publicly owned, tax delinquent 5+ years in 19133"). The model can only speak from three read-only database tools, must cite every claim as `[opa:...]` or `[owner:...]`, and the server verifies each citation against that request's actual tool results. Unverifiable citation, no answer. The model never invents a property.
- **Take action.** One click drafts a Pennsylvania Right-to-Know request, a council office letter, or a testimony paragraph, filled from the parcel's record by plain template substitution. No model in that path on purpose: artifacts a person signs and sends should contain nothing a model could get wrong.
- **Open data give-back.** The cleaned, joined dataset is downloadable as CSV and SQLite from the Data page, with the method documented.

## Quickstart

Requires Python 3.10+. No packages to install; the pipeline is standard library only.

```
python3 pipeline/run_all.py     # fetch all four city datasets, build, verify (a few minutes)
python3 server/app.py           # serve the site at http://localhost:8080
```

For the AI layer, put a key in `.env` at the repo root: `ANTHROPIC_API_KEY=sk-...`. Everything except "Ask the data" works without it.

Each pipeline stage is also runnable and checkable on its own; every script has a `--check` mode that validates its output against the source, and `pipeline/check_db.py --live` re-fetches random parcels from the city's API and compares them to the built database to the cent.

## Data sources

All public, all City of Philadelphia, via OpenDataPhilly:

- Vacant Property Indicators (L&I), the parcel spine
- Properties and Assessment History (OPA), ownership, values, mailing addresses
- Real Estate Tax Delinquencies (Revenue), parcel-level snapshot
- L&I Violations, open violations only

## The score

Fixed, public, recomputable by anyone from the parcel page:

```
score = min(years tax-delinquent, 10)
      + min(open L&I violations, 5)
      + 3 if publicly owned
      + 2 if flagged for sheriff sale
```

Public ownership scores points because a public agency holding housing vacant carries a public duty that a private owner does not.

## Known limitations

- The city stopped publishing parcel-level tax delinquency in June 2022. Every delinquency fact is that snapshot and is labeled "as of June 2022" wherever it appears. The newer Revenue tax-balances dataset is aggregated to ZIP/district/tract and cannot support parcel-level claims.
- "Likely vacant" is the city's model-based indicator, not a field inspection. The project inherits its false positives and says "likely-vacant", never "abandoned".
- A shared mailing address links owners as a network. That is a documented fact, not proof of common control, and the UI says so.
- Owners appear exactly as the public record names them. Nothing is enriched beyond what the city publishes.

## Boundary

This is an accountability tool built entirely on public records, for lawful pressure: reporting, organizing, testimony, records requests, litigation. It does not and will not rank or select properties for entry or occupation, and the ask endpoint refuses that shape of question.

## Taking it to another city

Swap the four fetchers in `pipeline/` for your city's parcel, vacancy, delinquency, and violations datasets, keep the OPA-number equivalent as the join key, and edit `pipeline/agencies.json` for your local public agencies. Everything downstream is city-agnostic.
