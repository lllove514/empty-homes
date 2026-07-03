"""Fetch OPA assessment rows for exactly the parcels in the VPI spine.

Run:    python3 pipeline/fetch_opa.py
Check:  python3 pipeline/fetch_opa.py --check
"""
import sys
from collections import Counter

from common import (batched, carto, fixture_sized, load_rows, load_vpi_ids,
                    probe_columns, save_rows)

TABLE = "opa_properties_public"
COLUMNS = ["parcel_number", "owner_1", "owner_2", "market_value", "sale_date",
           "sale_price", "category_code_description", "mailing_street",
           "mailing_city_state", "mailing_zip"]
BATCH = 1000


def fetch():
    ids = load_vpi_ids()
    print("fetching OPA rows for %d vacant parcels" % len(ids))
    probe_columns(TABLE, COLUMNS)

    rows = []
    for i, chunk in enumerate(batched(ids, BATCH)):
        in_list = ", ".join("'%s'" % opa for opa in chunk)
        rows.extend(carto("SELECT %s FROM %s WHERE parcel_number IN (%s)"
                          % (", ".join(COLUMNS), TABLE, in_list)))
        print("  batch %d: %d rows so far" % (i + 1, len(rows)))
    save_rows("opa.json", rows, TABLE)


def check():
    rows = load_rows("opa.json")
    ids = set(load_vpi_ids())
    matched = {r["parcel_number"] for r in rows}
    assert len(matched) == len(rows), \
        "duplicate parcel_number rows: %d rows, %d unique" % (len(rows), len(matched))
    rate = 100.0 * len(matched & ids) / len(ids)
    print("match rate: %.1f%% (%d of %d vacant parcels have an OPA row)"
          % (rate, len(matched & ids), len(ids)))
    if not fixture_sized(len(ids), 30000):
        assert rate >= 90.0, "match rate below 90%%: %.1f%%" % rate

    print("sample:")
    for r in rows[:5]:
        print("  %s | %s | value=%s" % (r["parcel_number"], r["owner_1"], r["market_value"]))
    print("top 10 owners:")
    for owner, n in Counter(r["owner_1"] for r in rows).most_common(10):
        print("  %5d  %s" % (n, owner))
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    check() if "--check" in sys.argv else fetch()
