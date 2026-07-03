"""Fetch the city's Vacant Property Indicators (Points layer).

Pages through the ArcGIS FeatureServer and saves one GeoJSON
FeatureCollection to data/raw/vpi.json. Fails loud on schema drift.

Run:    python3 pipeline/fetch_vpi.py
Check:  python3 pipeline/fetch_vpi.py --check
"""
import json
import sys
import time
import urllib.parse
import urllib.request

from common import raw_path

BASE = ("https://services.arcgis.com/fLeGjb7u4uXqeF9q/arcgis/rest/services/"
        "Vacant_Indicators_Points/FeatureServer/0/query")
PAGE = 2000
EXPECTED_KEYS = {"opa_id", "address", "owner1", "vacant_flag",
                 "councildistrict", "zipcode", "vacant_rank"}
# Philadelphia bounding box, generous
LON_MIN, LON_MAX = -75.29, -74.95
LAT_MIN, LAT_MAX = 39.86, 40.14


def fetch_page(offset):
    params = urllib.parse.urlencode({
        "where": "1=1", "outFields": "*", "outSR": "4326", "f": "geojson",
        "resultOffset": offset, "resultRecordCount": PAGE,
    })
    for attempt in range(3):
        try:
            with urllib.request.urlopen(BASE + "?" + params, timeout=120) as resp:
                return json.load(resp)["features"]
        except Exception:
            if attempt == 2:
                raise
            time.sleep(2 * (attempt + 1))


def fetch():
    features, offset = [], 0
    while True:
        page = fetch_page(offset)
        features.extend(page)
        print("  offset %d: %d features" % (offset, len(page)))
        if len(page) < PAGE:
            break
        offset += PAGE

    props = features[0]["properties"]
    missing = EXPECTED_KEYS - set(props)
    if missing:
        print("SCHEMA DRIFT: missing keys %s" % sorted(missing))
        print("keys actually present: %s" % sorted(props.keys()))
        sys.exit(1)

    kept, skipped = [], 0
    for feat in features:
        if feat["properties"].get("opa_id") is None:
            skipped += 1
        else:
            kept.append(feat)
    print("skipped %d features with null opa_id" % skipped)

    path = raw_path("vpi.json")
    with open(path, "w") as f:
        json.dump({"type": "FeatureCollection", "features": kept}, f)
    print("wrote %d features -> %s" % (len(kept), path))


def check():
    with open(raw_path("vpi.json")) as f:
        fc = json.load(f)
    feats = fc["features"]
    n = len(feats)
    fixture = n < 1000
    if fixture:
        print("NOTE: %d features is fixture-sized; full run expects > 30000" % n)
    else:
        assert n > 30000, "expected > 30000 features, got %d" % n

    seen, dups = set(), 0
    unique = []
    for feat in feats:
        opa = str(feat["properties"]["opa_id"]).zfill(9)
        if opa in seen:
            dups += 1
            continue
        seen.add(opa)
        unique.append(feat)
        lon, lat = feat["geometry"]["coordinates"][:2]
        assert LON_MIN < lon < LON_MAX and LAT_MIN < lat < LAT_MAX, \
            "point outside Philadelphia: %s at %s,%s" % (opa, lon, lat)
    print("features: %d, duplicate opa_ids: %d, unique: %d" % (n, dups, len(unique)))

    print("sample:")
    for feat in unique[:5]:
        p = feat["properties"]
        print("  %s | %s | %s | flag=%s rank=%s" % (
            str(p["opa_id"]).zfill(9), p["address"], p["owner1"],
            p["vacant_flag"], p["vacant_rank"]))
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    check() if "--check" in sys.argv else fetch()
