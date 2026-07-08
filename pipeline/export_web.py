"""Export static JSON for the web frontend, plus the open-data downloads.

Run:  python3 pipeline/export_web.py
"""
import csv
import json
import os
import shutil
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

    # static fallbacks so the GitHub Pages demo works without the API server
    addresses = con.execute(
        "SELECT opa_id, address FROM parcels ORDER BY address").fetchall()
    with open(os.path.join(WEB_DATA, "addresses.json"), "w") as f:
        json.dump([[a, b] for a, b in addresses], f, separators=(",", ":"))

    lite = {}
    for r in con.execute(
            "SELECT p.opa_id, p.address, p.zip, p.council_district, p.vacant_flag,"
            " p.vacant_rank, o.canonical_name, o.kind, o.id, p.market_value,"
            " substr(p.sale_date,1,10), p.sale_price, p.mailing_addr, p.delinquent,"
            " p.years_owed, p.oldest_year_owed, p.total_due, p.sheriff_sale,"
            " p.open_violations, p.score"
            " FROM parcels p LEFT JOIN owners o ON o.id = p.owner_id"):
        lite[r[0]] = list(r[1:])
    with open(os.path.join(WEB_DATA, "parcels_lite.json"), "w") as f:
        json.dump(lite, f, separators=(",", ":"))

    def owner_rows(kind):
        where = "WHERE kind = '%s'" % kind if kind else ""
        return [dict(zip(("id", "canonical_name", "kind", "cluster_id",
                          "parcel_count", "total_due", "avg_years_owed"), r))
                for r in con.execute(
                    "SELECT id, canonical_name, kind, cluster_id, parcel_count,"
                    " total_due, avg_years_owed FROM owners %s"
                    " ORDER BY parcel_count DESC, total_due DESC LIMIT 100" % where)]
    top = {"all": owner_rows(""), "public": owner_rows("public"),
           "llc": owner_rows("llc"), "individual": owner_rows("individual")}
    with open(os.path.join(WEB_DATA, "owners_top.json"), "w") as f:
        json.dump(top, f, separators=(",", ":"))

    ids = {o["id"] for rows in top.values() for o in rows}
    for oid in list(ids):
        cid = con.execute("SELECT cluster_id FROM owners WHERE id=?", (oid,)).fetchone()[0]
        if cid is not None:
            ids.update(r[0] for r in con.execute(
                "SELECT id FROM owners WHERE cluster_id=?", (cid,)))
    owners_dir = os.path.join(WEB_DATA, "owners")
    os.makedirs(owners_dir, exist_ok=True)
    for oid in ids:
        o = con.execute("SELECT * FROM owners WHERE id=?", (oid,)).fetchone()
        cols = [d[0] for d in con.execute("SELECT * FROM owners LIMIT 0").description]
        out = dict(zip(cols, o))
        out["aliases"] = sorted({r[0] for r in con.execute(
            "SELECT alias FROM owner_aliases WHERE owner_id=?", (oid,))})
        out["parcels"] = [dict(zip(("opa_id", "address", "zip", "score", "delinquent",
                                    "years_owed", "total_due", "open_violations",
                                    "lat", "lon"), r))
                          for r in con.execute(
                              "SELECT opa_id, address, zip, score, delinquent,"
                              " years_owed, total_due, open_violations, lat, lon"
                              " FROM parcels WHERE owner_id=? ORDER BY score DESC"
                              " LIMIT 500", (oid,))]
        if out.get("cluster_id") is not None:
            out["cluster"] = [dict(zip(("id", "canonical_name", "kind", "parcel_count"), r))
                              for r in con.execute(
                                  "SELECT id, canonical_name, kind, parcel_count"
                                  " FROM owners WHERE cluster_id=? AND id!=?",
                                  (out["cluster_id"], oid))]
            addr = con.execute("SELECT mailing_addr FROM owner_aliases WHERE owner_id=?"
                               " AND mailing_addr IS NOT NULL LIMIT 1", (oid,)).fetchone()
            out["shared_mailing_addr"] = addr[0] if addr else None
        with open(os.path.join(owners_dir, "%d.json" % oid), "w") as f:
            json.dump(out, f, separators=(",", ":"))
    print("static fallbacks: %d addresses, %d lite parcels, %d owner files"
          % (len(addresses), len(lite), len(ids)))

    # open-data downloads
    csv_path = os.path.join(WEB_DATA, "empty_homes.csv")
    cur = con.execute(
        "SELECT p.opa_id, p.address, p.zip, p.council_district, p.lat, p.lon,"
        " p.vacant_flag, p.vacant_rank, o.canonical_name AS owner,"
        " o.kind AS owner_kind, p.owner_raw, p.market_value, p.sale_date,"
        " p.sale_price, p.delinquent, p.years_owed, p.oldest_year_owed,"
        " p.total_due, p.sheriff_sale, p.open_violations, p.score"
        " FROM parcels p LEFT JOIN owners o ON o.id = p.owner_id"
        " ORDER BY p.opa_id")
    with open(csv_path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([d[0] for d in cur.description])
        writer.writerows(cur)
    print("empty_homes.csv: %.1f KB" % (os.path.getsize(csv_path) / 1024))
    con.close()
    shutil.copyfile(DB, os.path.join(WEB_DATA, "empty_homes.sqlite"))
    print("empty_homes.sqlite copied")


if __name__ == "__main__":
    main()
