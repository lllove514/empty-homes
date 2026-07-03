"""Export static JSON for the web frontend.

Run:  python3 pipeline/export_web.py
"""
import json
import os
import sqlite3
import time

from build_db import DB

WEB_DATA = os.path.join(os.path.dirname(__file__), "..", "web", "data")
KIND_CODE = {"public": 0, "llc": 1, "individual": 2, "other": 3}
SCORE_FORMULA = ("min(years tax-delinquent, 10) + min(open violations, 5) "
                 "+ 3 if publicly owned + 2 if flagged for sheriff sale. "
                 "Delinquency facts as of June 2022.")


def main():
    os.makedirs(WEB_DATA, exist_ok=True)
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)

    points = []
    for lon, lat, opa, score, kind in con.execute(
            "SELECT p.lon, p.lat, p.opa_id, p.score, coalesce(o.kind,'other') "
            "FROM parcels p LEFT JOIN owners o ON o.id = p.owner_id"):
        points.append([round(lon, 5), round(lat, 5), opa, score, KIND_CODE[kind]])
    with open(os.path.join(WEB_DATA, "points.json"), "w") as f:
        json.dump(points, f, separators=(",", ":"))

    meta = {
        "generated": time.strftime("%Y-%m-%d", time.gmtime()),
        "parcel_count": len(points),
        "delinquent_count": con.execute(
            "SELECT count(*) FROM parcels WHERE delinquent=1").fetchone()[0],
        "total_due": round(con.execute(
            "SELECT coalesce(sum(total_due),0) FROM parcels").fetchone()[0], 2),
        "delinquency_snapshot": "June 2022",
        "score_formula": SCORE_FORMULA,
    }
    with open(os.path.join(WEB_DATA, "meta.json"), "w") as f:
        json.dump(meta, f, indent=1)

    size = os.path.getsize(os.path.join(WEB_DATA, "points.json"))
    print("points.json: %d parcels, %.1f KB" % (len(points), size / 1024))
    print("meta.json:", meta)
    assert size < 3_000_000, "points.json too large to serve comfortably"
    con.close()


if __name__ == "__main__":
    main()
