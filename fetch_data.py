"""Nightly data pull for the SOTA microwave S2S Streamlit app.

1. Gets the list of activators who have at least one 2.3GHz (13cm) QSO
   from the SOTA "rolls" endpoint (used as a seed list of microwave-active
   operators).
2. For each of those activators, fetches their full S2S log.
3. Keeps only QSOs on a microwave band (1240MHz/2.3GHz/3.4GHz/5.6GHz/10GHz/24GHz).
4. De-duplicates QSOs that show up in both operators' logs.
5. Writes the combined result to data/s2s_microwave.json.

Run this once a night (e.g. via the included GitHub Action). The Streamlit
app just reads the JSON this script produces - it never calls the SOTA API
directly.
"""
import json
import sys
import time
from pathlib import Path

import requests

ROLLS_URL = "https://api-db2.sota.org.uk/rolls/activator/-1/0/2.3GHz/all"
S2S_URL_TEMPLATE = "https://api-db2.sota.org.uk/logs/s2s/{user_id}/9999/0"
SUMMITSLIST_URL = "https://www.sotadata.org.uk/summitslist.csv"

MICROWAVE_BANDS = {"1240MHz", "2.3GHz", "3.4GHz", "5.6GHz", "10GHz", "24GHz"}

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
OUTPUT_PATH = DATA_DIR / "s2s_microwave.json"
SUMMITSLIST_PATH = ROOT / "summitslist.csv"

REQUEST_TIMEOUT = 30
REQUEST_DELAY = 0.2  # seconds between requests, be polite to the API
MAX_RETRIES = 3


def _get_json(url):
    last_exc = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT)
            resp.raise_for_status()
            return resp.json()
        except (requests.RequestException, ValueError) as exc:
            last_exc = exc
            if attempt < MAX_RETRIES:
                time.sleep(1.5 * attempt)
    raise last_exc


def get_activators():
    """List of activators with a 2.3GHz (13cm) QSO on record."""
    return _get_json(ROLLS_URL)


def get_s2s_log(user_id):
    """Full S2S log (all bands) for a given activator UserID."""
    return _get_json(S2S_URL_TEMPLATE.format(user_id=user_id))


def dedupe_key(qso):
    """A QSO logged by both parties should collapse to a single entry.

    Build a key from the two base callsigns (order-independent), the date,
    time, and band - that combination should be unique per real-world QSO
    regardless of which side's log it came from.
    """
    from sota_utils import base_callsign

    a = base_callsign(qso.get("OwnCallsign", ""))
    b = base_callsign(qso.get("OtherCallsign", ""))
    return (
        tuple(sorted([a, b])),
        qso.get("ActivationDate"),
        qso.get("TimeOfDay"),
        qso.get("Band"),
    )


def download_summitslist():
    """Best-effort refresh of summitslist.csv. Keeps the existing file on failure."""
    try:
        resp = requests.get(SUMMITSLIST_URL, timeout=REQUEST_TIMEOUT)
        resp.raise_for_status()
        SUMMITSLIST_PATH.write_bytes(resp.content)
        print(f"Refreshed {SUMMITSLIST_PATH.name} ({len(resp.content)} bytes)")
    except requests.RequestException as exc:
        print(f"Could not refresh summitslist.csv ({exc}); keeping existing copy.", file=sys.stderr)


def main():
    #download_summitslist()

    activators = get_activators()
    print(f"Found {len(activators)} activators with 13cm (2.3GHz) activity")

    all_qsos = []
    seen_keys = set()
    failures = []

    for i, activator in enumerate(activators, start=1):
        user_id = activator["UserID"]
        callsign = activator.get("Callsign", user_id)
        print(f"[{i}/{len(activators)}] {callsign} (UserID {user_id})...", end=" ")

        try:
            log = get_s2s_log(user_id)
        except (requests.RequestException, ValueError) as exc:
            print(f"FAILED ({exc})")
            failures.append(callsign)
            continue

        kept = 0
        for qso in log:
            if qso.get("Band") not in MICROWAVE_BANDS:
                continue

            key = dedupe_key(qso)
            if key in seen_keys:
                continue
            seen_keys.add(key)

            qso["_LookupUserID"] = user_id
            qso["_LookupCallsign"] = callsign
            all_qsos.append(qso)
            kept += 1

        print(f"{kept} new microwave S2S QSOs")
        time.sleep(REQUEST_DELAY)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(all_qsos, f, indent=2)

    print(f"\nSaved {len(all_qsos)} unique microwave S2S QSOs to {OUTPUT_PATH}")
    if failures:
        print(f"Failed to fetch logs for {len(failures)} activator(s): {', '.join(failures)}", file=sys.stderr)


if __name__ == "__main__":
    main()
