# SOTA Microwave S2S Explorer

Streamlit app for browsing Summits On The Air summit-to-summit QSOs on the
microwave bands (1240MHz, 2.3GHz/13cm, 3.4GHz, 5.6GHz, 10GHz, 24GHz).

## How it fits together

1. **`fetch_data.py`** — run once a night (see the included GitHub Action).
   - Pulls the list of activators who have logged a 2.3GHz (13cm) QSO from
     `api-db2.sota.org.uk/rolls/...` — this is the seed list of
     microwave-active operators.
   - For each of them, fetches their *full* S2S log and keeps only QSOs on
     a microwave band.
   - De-duplicates QSOs that appear in both operators' logs.
   - Also refreshes `summitslist.csv` from SOTA's public download.
   - Writes everything to `data/s2s_microwave.json`.
2. **`app.py`** — the Streamlit app. Only ever reads the local JSON + CSV,
   never calls the SOTA API itself, so it stays fast and doesn't hammer
   their servers.
3. **`sota_utils.py`** — shared helpers (summit CSV loading, haversine
   distance, callsign normalisation) used by both scripts.

## Local setup

```bash
pip install -r requirements.txt
python fetch_data.py        # first run: populates data/ and summitslist.csv
streamlit run app.py
```

## Notes / things to check

- **Distance calculation**: computed with the haversine formula from each
  summit's lat/lon in `summitslist.csv`, using `SummitCode` (the other
  operator's summit) and `Summit2Code` (the activator whose log the QSO
  came from). The S2S API also returns its own `Distance` field — that's
  kept in the data as `ReportedDistanceKm` in case you want to sanity-check
  the two against each other.
- **Callsign grouping**: portable/mobile suffixes (`/P`, `/M`, etc.) and
  country prefixes are stripped for the leaderboard, so `MM0EFI/P` and
  `MM0EFI` count as the same operator.
- **Untested network calls**: I built this without being able to reach
  `api-db2.sota.org.uk` or `sotadata.org.uk` from my sandbox, so the fetch
  script is written carefully against the JSON/CSV shapes you provided but
  hasn't been run against the live API. Worth doing a first manual run
  (`python fetch_data.py`) and eyeballing `data/s2s_microwave.json` before
  relying on the scheduled Action.
- **`summitslist.csv`**: the fetch script tries to download the latest copy
  itself from `https://www.sotadata.org.uk/summitslist.csv`. If that URL
  has changed, grab it manually from the SOTA site and drop it next to
  `app.py`.
- The GitHub Action needs `permissions: contents: write` (already set) to
  push the updated data file back to the repo.
