"""Fetch open L&I violations for vacant parcels.

Run:    python3 pipeline/fetch_violations.py
Check:  python3 pipeline/fetch_violations.py --check
"""
import sys
from collections import Counter

from common import (batched, carto, load_rows, load_vpi_ids, probe_columns,
                    save_rows)

TABLE = "violations"
COLUMNS = ["opa_account_num", "violationcodetitle", "violationdate"]
BATCH = 1000


def fetch():
    ids = load_vpi_ids()
    probe_columns(TABLE, COLUMNS + ["violationstatus"])

    rows = []
    for i, chunk in enumerate(batched(ids, BATCH)):
        in_list = ", ".join("'%s'" % opa for opa in chunk)
        rows.extend(carto(
            "SELECT %s FROM %s WHERE violationstatus = 'OPEN' "
            "AND opa_account_num IN (%s)"
            % (", ".join(COLUMNS), TABLE, in_list)))
        print("  batch %d: %d rows so far" % (i + 1, len(rows)))
    save_rows("violations.json", rows, TABLE + " (status OPEN)")


def check():
    rows = load_rows("violations.json")
    assert rows, "no violation rows at all"
    parcels = {r["opa_account_num"] for r in rows}
    print("rows: %d across %d parcels" % (len(rows), len(parcels)))
    print("top 10 violation titles:")
    for title, n in Counter(r["violationcodetitle"] for r in rows).most_common(10):
        print("  %5d  %s" % (n, title))
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    check() if "--check" in sys.argv else fetch()
