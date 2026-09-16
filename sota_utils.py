"""Shared helpers for the SOTA microwave S2S app.

Used by both fetch_data.py (nightly data pull) and app.py (Streamlit UI).
"""
import csv
import math


def load_summits(csv_path):
    """Load summitslist.csv into a dict: SummitCode -> {"lat", "lon", "name"}.

    The official SOTA summitslist.csv has columns including SummitCode,
    SummitName, Longitude, Latitude (note: Longitude comes before Latitude
    in the file header, so we read by column name, not position).
    """
    summits = {}
    with open(csv_path, newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            code = (row.get("SummitCode") or "").strip()
            if not code:
                continue
            try:
                lat = float(row["Latitude"])
                lon = float(row["Longitude"])
            except (KeyError, ValueError, TypeError):
                continue
            summits[code] = {
                "lat": lat,
                "lon": lon,
                "name": (row.get("SummitName") or "").strip(),
            }
    return summits


def haversine_km(lat1, lon1, lat2, lon2):
    """Great-circle distance between two lat/lon points, in kilometres."""
    R = 6371.0088  # mean Earth radius, km
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlambda / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def base_callsign(cs):
    """Normalise a callsign for grouping: MM0EFI/P -> MM0EFI, DL/G4ABC/P -> G4ABC.

    Picks the '/'-separated segment that contains a digit (the actual
    callsign), preferring the longest such segment if more than one
    qualifies. Falls back to the first segment if none contain a digit.
    """
    if not cs:
        return cs
    parts = cs.upper().strip().split("/")
    candidates = [p for p in parts if any(ch.isdigit() for ch in p)]
    if candidates:
        return max(candidates, key=len)
    return parts[0]
