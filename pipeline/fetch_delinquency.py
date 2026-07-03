"""Fetch the parcel-level tax delinquency snapshot for vacant parcels.

The city stopped updating this dataset in June 2022. The fetch asserts
that fact so any resumption of publication is noticed immediately.

Run:    python3 pipeline/fetch_delinquency.py
Check:  python3 pipeline/fetch_delinquency.py --check
"""
import sys

from common import (batched, carto, load_rows, load_vpi_ids, probe_columns,
                    save_rows)

TABLE = "real_estate_tax_delinquencies"
COLUMNS = ["opa_number", "owner", "total_due", "num_years_owed",
           "oldest_year_owed", "most_recent_year_owed", "sheriff_sale",
           "payment_agreement", "mailing_address", "mailing_city",
           "mailing_state", "mailing_zip"]
BATCH = 1000
SNAPSHOT = "202206"


def fetch():
    ids = load_vpi_ids()
    probe_columns(TABLE, COLUMNS)

    latest = carto("SELECT max(year_month) AS latest FROM %s" % TABLE)[0]["latest"]
    if latest != SNAPSHOT:
        print("DATA CHANGED: max(year_month) is %s, expected %s. The city may "
              "have resumed parcel-level publication. Update SNAPSHOT and the "
              "as-of labels across the project." % (latest, SNAPSHOT))
        sys.exit(1)
    print("confirmed: delinquency snapshot frozen at %s" % latest)

    rows = []
    for i, chunk in enumerate(batched(ids, BATCH)):
        # opa_number is numeric in this table; strip the zero padding
        in_list = ", ".join(str(int(opa)) for opa in chunk)
        rows.extend(carto("SELECT %s FROM %s WHERE opa_number IN (%s)"
                          % (", ".join(COLUMNS), TABLE, in_list)))
        print("  batch %d: %d rows so far" % (i + 1, len(rows)))
    for r in rows:
        r["opa_number"] = str(int(r["opa_number"])).zfill(9)
    save_rows("delinquency.json", rows, "%s (snapshot %s)" % (TABLE, SNAPSHOT))


def check():
    rows = load_rows("delinquency.json")
    assert rows, "no delinquency rows at all"
    ids = set(load_vpi_ids())
    joined = [r for r in rows if r["opa_number"] in ids]
    assert len(joined) == len(rows), \
        "%d rows do not belong to the VPI spine" % (len(rows) - len(joined))
    for r in rows:
        assert r["num_years_owed"] is not None, \
            "row with null num_years_owed: %s" % r["opa_number"]
    total = sum(r["total_due"] or 0 for r in rows)
    print("rows: %d, total due (as of June 2022): $%s" % (len(rows), format(total, ",.2f")))
    print("ALL CHECKS PASS")


if __name__ == "__main__":
    check() if "--check" in sys.argv else fetch()
