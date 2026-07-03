"""Join the four raw sources into one SQLite database.

Run:  python3 pipeline/build_db.py
"""
import json
import os
import sqlite3

from common import raw_path

DB = os.path.join(os.path.dirname(__file__), "..", "data", "empty_homes.db")

SCHEMA = """
DROP TABLE IF EXISTS parcels;
DROP TABLE IF EXISTS violations;
CREATE TABLE parcels (
  opa_id TEXT PRIMARY KEY,
  address TEXT, zip TEXT, council_district TEXT,
  lat REAL, lon REAL,
  vacant_flag TEXT, vacant_rank REAL, bldg_desc TEXT,
  owner_raw TEXT,
  owner_id INTEGER,
  market_value INTEGER, sale_date TEXT, sale_price INTEGER, category TEXT,
  mailing_addr TEXT,
  delinquent INTEGER DEFAULT 0,
  years_owed INTEGER, oldest_year_owed INTEGER, total_due REAL,
  sheriff_sale TEXT, payment_agreement TEXT,
  open_violations INTEGER DEFAULT 0,
  score INTEGER DEFAULT 0
);
CREATE TABLE violations (opa_id TEXT, title TEXT, date TEXT);
CREATE INDEX idx_parcels_zip ON parcels(zip);
CREATE INDEX idx_parcels_owner ON parcels(owner_id);
CREATE INDEX idx_violations_opa ON violations(opa_id);
"""


def norm_mailing(*parts):
    joined = " ".join(str(p).strip().upper() for p in parts if p)
    return " ".join(joined.split()) or None


def main():
    with open(raw_path("vpi.json")) as f:
        vpi = json.load(f)["features"]
    with open(raw_path("opa.json")) as f:
        opa = {r["parcel_number"]: r for r in json.load(f)["rows"]}
    with open(raw_path("delinquency.json")) as f:
        dlq = {r["opa_number"]: r for r in json.load(f)["rows"]}
    with open(raw_path("violations.json")) as f:
        vio = json.load(f)["rows"]

    os.makedirs(os.path.dirname(DB), exist_ok=True)
    con = sqlite3.connect(DB)
    con.executescript(SCHEMA)

    vio_by_parcel = {}
    for r in vio:
        vio_by_parcel.setdefault(str(r["opa_account_num"]).zfill(9), []).append(r)

    seen = set()
    n_opa = n_dlq = n_vio = 0
    for feat in vpi:
        p = feat["properties"]
        opa_id = str(p["opa_id"]).strip().zfill(9)
        if opa_id in seen:
            continue
        seen.add(opa_id)
        lon, lat = feat["geometry"]["coordinates"][:2]

        o = opa.get(opa_id, {})
        d = dlq.get(opa_id, {})
        v = vio_by_parcel.get(opa_id, [])
        if o:
            n_opa += 1
        if d:
            n_dlq += 1
        n_vio += len(v)

        # prefer OPA owner strings over the VPI copy when present
        owner_parts = [o.get("owner_1"), o.get("owner_2")] if o.get("owner_1") \
            else [p.get("owner1"), p.get("owner2")]
        owner_raw = " / ".join(s.strip() for s in owner_parts if s and str(s).strip())

        years = d.get("num_years_owed")
        score = min(years or 0, 10) + min(len(v), 5) \
            + (2 if str(d.get("sheriff_sale", "")).upper() in ("Y", "TRUE") else 0)

        con.execute(
            "INSERT INTO parcels (opa_id, address, zip, council_district, lat, lon,"
            " vacant_flag, vacant_rank, bldg_desc, owner_raw, market_value, sale_date,"
            " sale_price, category, mailing_addr, delinquent, years_owed,"
            " oldest_year_owed, total_due, sheriff_sale, payment_agreement,"
            " open_violations, score) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (opa_id, p.get("address"), str(p.get("zipcode") or "") or None,
             str(p.get("councildistrict") or "") or None, lat, lon,
             p.get("vacant_flag"), p.get("vacant_rank"), p.get("bldg_desc"),
             owner_raw or None, o.get("market_value"), o.get("sale_date"),
             o.get("sale_price"), o.get("category_code_description"),
             norm_mailing(o.get("mailing_street"), o.get("mailing_zip"))
             or norm_mailing(d.get("mailing_address"), d.get("mailing_zip")),
             1 if d else 0, years, d.get("oldest_year_owed"), d.get("total_due"),
             d.get("sheriff_sale"), d.get("payment_agreement"), len(v), score))

        for r in v:
            con.execute("INSERT INTO violations VALUES (?,?,?)",
                        (opa_id, str(r["violationcodetitle"]).strip(), r["violationdate"]))

    con.commit()
    total = len(seen)
    print("parcels: %d" % total)
    print("joined OPA: %d (%.1f%%)" % (n_opa, 100.0 * n_opa / total))
    print("joined delinquency: %d (%.1f%%)" % (n_dlq, 100.0 * n_dlq / total))
    print("violation rows: %d" % n_vio)
    con.close()


if __name__ == "__main__":
    main()
