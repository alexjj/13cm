"""SOTA Microwave Summit-to-Summit explorer.

Reads data/s2s_microwave.json (produced nightly by fetch_data.py) and
summitslist.csv (summit coordinates), and shows:
  - a leaderboard of callsigns by number of microwave S2S QSOs
  - all QSOs sorted by distance, largest first
  - a map of a selected QSO's summit-to-summit line
"""
import json
from pathlib import Path

import pandas as pd
import pydeck as pdk
import streamlit as st

from sota_utils import base_callsign, haversine_km, load_summits

ROOT = Path(__file__).parent
DATA_PATH = ROOT / "data" / "s2s_microwave.json"
SUMMITS_PATH = ROOT / "summitslist.csv"

MICROWAVE_BANDS = ["1240MHz", "2.3GHz", "3.4GHz", "5.6GHz", "10GHz", "24GHz"]

st.set_page_config(page_title="SOTA Microwave S2S", page_icon="📡", layout="wide")


@st.cache_data
def load_data():
    if not DATA_PATH.exists():
        return pd.DataFrame(), "missing_data"
    if not SUMMITS_PATH.exists():
        return pd.DataFrame(), "missing_summits"

    with open(DATA_PATH) as f:
        qsos = json.load(f)
    summits = load_summits(SUMMITS_PATH)

    rows = []
    skipped_no_coords = 0
    for q in qsos:
        own_code = q.get("Summit2Code")   # the activator whose log this came from
        other_code = q.get("SummitCode")  # the summit they worked S2S
        own_summit = summits.get(own_code)
        other_summit = summits.get(other_code)
        if not own_summit or not other_summit:
            skipped_no_coords += 1
            continue

        dist_km = haversine_km(
            own_summit["lat"], own_summit["lon"],
            other_summit["lat"], other_summit["lon"],
        )

        rows.append({
            "Date": q.get("ActivationDate"),
            "Time": q.get("TimeOfDay"),
            "Band": q.get("Band"),
            "Mode": q.get("Mode"),
            "OwnCallsign": q.get("OwnCallsign"),
            "OtherCallsign": q.get("OtherCallsign"),
            "OwnCallsignBase": base_callsign(q.get("OwnCallsign")),
            "OtherCallsignBase": base_callsign(q.get("OtherCallsign")),
            "OwnSummitCode": own_code,
            "OwnSummitName": q.get("ActivatedSummit"),
            "OtherSummitCode": other_code,
            "OtherSummitName": q.get("ChasedSummit"),
            "DistanceKm": round(dist_km, 1),
            "ReportedDistanceKm": q.get("Distance"),
            "OwnLat": own_summit["lat"],
            "OwnLon": own_summit["lon"],
            "OtherLat": other_summit["lat"],
            "OtherLon": other_summit["lon"],
        })

    df = pd.DataFrame(rows)
    if skipped_no_coords:
        st.sidebar.caption(f"⚠️ {skipped_no_coords} QSO(s) skipped — summit not found in summitslist.csv")
    return df, None


def zoom_for_distance(km):
    if km < 20:
        return 9
    if km < 50:
        return 8
    if km < 100:
        return 7
    if km < 250:
        return 6
    if km < 500:
        return 5
    return 4


df, error = load_data()

st.title("📡 SOTA Microwave Summit-to-Summit QSOs")
st.caption("1240MHz · 2.3GHz · 3.4GHz · 5.6GHz · 10GHz · 24GHz")

if error == "missing_data":
    st.error(f"No data file found at `{DATA_PATH}`. Run `fetch_data.py` first.")
    st.stop()
if error == "missing_summits":
    st.error(f"No summit list found at `{SUMMITS_PATH}`. Download summitslist.csv and place it alongside app.py.")
    st.stop()
if df.empty:
    st.warning("No microwave S2S QSOs found in the data file.")
    st.stop()

# --- Sidebar filters ---
st.sidebar.header("Filters")
selected_bands = st.sidebar.multiselect("Band", MICROWAVE_BANDS, default=MICROWAVE_BANDS)
filtered = df[df["Band"].isin(selected_bands)] if selected_bands else df.iloc[0:0]
st.sidebar.write(f"{len(filtered)} QSOs match filters")

if filtered.empty:
    st.info("No QSOs match the current filters.")
    st.stop()

# --- Section 1: callsigns by S2S count ---
st.header("Callsigns by number of S2S QSOs")
counts = (
    pd.concat([filtered["OwnCallsignBase"], filtered["OtherCallsignBase"]])
    .value_counts()
    .rename_axis("Callsign")
    .reset_index(name="S2S QSOs")
)
col1, col2 = st.columns([2, 1])
with col1:
    st.bar_chart(counts.set_index("Callsign")["S2S QSOs"])
with col2:
    st.dataframe(counts, use_container_width=True, hide_index=True, height=350)

# --- Section 2: QSOs sorted by distance ---
st.header("S2S QSOs by distance")
sorted_df = filtered.sort_values("DistanceKm", ascending=False).reset_index(drop=True)
display_cols = [
    "Date", "Band", "DistanceKm", "OwnCallsign", "OwnSummitName",
    "OtherCallsign", "OtherSummitName",
]
st.dataframe(
    sorted_df[display_cols].rename(columns={"DistanceKm": "Distance (km)"}),
    use_container_width=True,
    hide_index=True,
)

# --- Section 3: map of a selected QSO ---
st.header("Map")
options = [
    f"{i}: {row.OwnCallsign} @ {row.OwnSummitName} \u2194 {row.OtherCallsign} @ {row.OtherSummitName} "
    f"({row.DistanceKm} km, {row.Band})"
    for i, row in sorted_df.iterrows()
]
choice = st.selectbox("Select a QSO to show on the map", options)
idx = int(choice.split(":")[0])
sel = sorted_df.loc[idx]

line_data = [{"start": [sel.OwnLon, sel.OwnLat], "end": [sel.OtherLon, sel.OtherLat]}]
point_data = [
    {"lon": sel.OwnLon, "lat": sel.OwnLat, "name": sel.OwnSummitName, "callsign": sel.OwnCallsign},
    {"lon": sel.OtherLon, "lat": sel.OtherLat, "name": sel.OtherSummitName, "callsign": sel.OtherCallsign},
]

mid_lat = (sel.OwnLat + sel.OtherLat) / 2
mid_lon = (sel.OwnLon + sel.OtherLon) / 2

view_state = pdk.ViewState(latitude=mid_lat, longitude=mid_lon, zoom=zoom_for_distance(sel.DistanceKm))

line_layer = pdk.Layer(
    "LineLayer",
    data=line_data,
    get_source_position="start",
    get_target_position="end",
    get_width=3,
    get_color=[200, 30, 0, 180],
)
point_layer = pdk.Layer(
    "ScatterplotLayer",
    data=point_data,
    get_position=["lon", "lat"],
    get_radius=2000,
    get_fill_color=[0, 100, 200, 200],
    pickable=True,
)

st.pydeck_chart(pdk.Deck(
    layers=[line_layer, point_layer],
    initial_view_state=view_state,
    tooltip={"text": "{callsign}\n{name}"},
))
st.caption(
    f"{sel.OwnCallsign} on {sel.OwnSummitName} ({sel.OwnSummitCode}) \u2194 "
    f"{sel.OtherCallsign} on {sel.OtherSummitName} ({sel.OtherSummitCode}) "
    f"\u2014 {sel.DistanceKm} km on {sel.Band}, {sel.Date}"
)
