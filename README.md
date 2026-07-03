# Empty Homes

A public map of every likely-vacant property in Philadelphia: who owns it, how long it has sat empty and tax-delinquent, with cited accountability briefs.

## Data sources

All public, all from OpenDataPhilly:

- Vacant Property Indicators (Department of Licenses and Inspections)
- Philadelphia Properties and Assessment History (Office of Property Assessment)
- Real Estate Tax Delinquencies (Department of Revenue)
- L&I Violations (Department of Licenses and Inspections)

## Known limitations

The city's parcel-level tax delinquency dataset stopped updating in June 2022. All delinquency facts in this project are labeled "as of June 2022". The newer Real Estate Tax Balances dataset updates monthly but is aggregated to ZIP, council district, and census tract, so it cannot support parcel-level claims.

"Likely vacant" is the city's own model-based indicator, not a field inspection. This project inherits its false positives and says "likely-vacant" everywhere for that reason.
