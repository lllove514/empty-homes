"""Verify the built database against the raw source files.

Run:         python3 pipeline/check_db.py
With --live: also refetches 3 random delinquent parcels from the city's
             Carto API and compares total_due exactly (needs network).
"""
import json
import random
import sqlite3
import sys

from common import carto, raw_path
from build_db import DB

failures = []


def report(name, ok, detail=""):
    print("%s  %s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        failures.append(name)


def main():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    q = lambda sql: con.execute(sql).fetchone()[0]

    with open(raw_path("vpi.json")) as f:
        vpi_ids = {str(ft["properties"]["opa_id"]).zfill(9)
                   for ft in json.load(f)["features"]}
    report("parcel count matches unique VPI opa_ids",
           q("SELECT count(*) FROM parcels") == len(vpi_ids),
           "(db %d, vpi %d)" % (q("SELECT count(*) FROM parcels"), len(vpi_ids)))

    with open(raw_path("delinquency.json")) as f:
        dlq = json.load(f)["rows"]
    src_total = round(sum(r["total_due"] or 0 for r in dlq if r["opa_number"] in vpi_ids), 2)
    db_total = round(q("SELECT coalesce(sum(total_due),0) FROM parcels"), 2)
    report("delinquency total_due matches to the cent", db_total == src_total,
           "(db $%s, source $%s)" % (db_total, src_total))

    with open(raw_path("violations.json")) as f:
        vio = [r for r in json.load(f)["rows"]
               if str(r["opa_account_num"]).zfill(9) in vpi_ids]
    report("open_violations sum equals violation rows",
           q("SELECT sum(open_violations) FROM parcels") == len(vio)
           and q("SELECT count(*) FROM violations") == len(vio),
           "(%d rows)" % len(vio))

    report("no delinquent parcel has null years_owed",
           q("SELECT count(*) FROM parcels WHERE delinquent=1 AND years_owed IS NULL") == 0)

    report("every parcel has coordinates and an address",
           q("SELECT count(*) FROM parcels WHERE lat IS NULL OR lon IS NULL "
             "OR address IS NULL") == 0)

    report("score never exceeds its documented maximum (20)",
           q("SELECT max(score) FROM parcels") <= 20)

    if "--live" in sys.argv:
        rows = con.execute("SELECT opa_id, total_due FROM parcels "
                           "WHERE delinquent=1 ORDER BY random() LIMIT 3").fetchall()
        for opa_id, total_due in rows:
            live = carto("SELECT total_due FROM real_estate_tax_delinquencies "
                         "WHERE opa_number = %d" % int(opa_id))
            ok = live and round(live[0]["total_due"], 2) == round(total_due, 2)
            report("live spot-check %s" % opa_id, bool(ok),
                   "(db %s, live %s)" % (total_due, live and live[0]["total_due"]))
    else:
        print("SKIP  live spot-checks (pass --live on a machine with network access)")

    con.close()
    if failures:
        sys.exit(1)
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    main()
