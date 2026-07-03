"""Letter and testimony drafts, filled from the database record itself.

Deliberately no model in this path. These are artifacts a person will
sign and send, so every word is either a fixed template or a value read
straight from a city record. The person adds their own name and address
and reviews before sending.
"""
import datetime
import os
import sqlite3

from tools import get_parcel

TEMPLATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "templates")
TYPES = ("foia", "council", "testimony")


def _load(name):
    with open(os.path.join(TEMPLATE_DIR, name + ".txt")) as f:
        return f.read()


def _dollars(n):
    return "$" + format(n, ",.2f")


def draft(payload):
    kind = payload.get("type")
    opa_id = str(payload.get("opa_id", "")).strip()
    if kind not in TYPES:
        return {"error": "type must be one of %s" % (TYPES,)}
    if not opa_id.isdigit() or len(opa_id) != 9:
        return {"error": "opa_id must be a 9-digit OPA account number"}

    p = get_parcel(opa_id)
    if "error" in p:
        return {"error": p["error"]}

    owner = p.get("owner_name") or p.get("owner_raw") or "the owner of record"
    delinquency_line = ""
    if p.get("delinquent"):
        delinquency_line = (
            "\nAs of the city's June 2022 tax snapshot, the last parcel-level "
            "release, this property was %s year(s) tax-delinquent with %s due."
            % (p["years_owed"], _dollars(p["total_due"] or 0)))
    violations_line = ""
    if p.get("open_violations"):
        titles = sorted({v["title"] for v in p.get("violations", [])})[:3]
        violations_line = (
            "\nIt currently carries %d open L&I violation(s), including: %s."
            % (p["open_violations"], "; ".join(titles).lower()))

    agency = owner if p.get("owner_kind") == "public" else \
        "Department of Licenses and Inspections, City of Philadelphia"

    con = sqlite3.connect("file:%s?mode=ro" % os.path.join(
        os.path.dirname(TEMPLATE_DIR), "..", "data", "empty_homes.db"), uri=True)
    total_vacant = con.execute("SELECT count(*) FROM parcels").fetchone()[0]
    con.close()

    text = _load(kind).format(
        address=p["address"],
        opa_id=p["opa_id"],
        owner=owner,
        agency=agency,
        district=p.get("council_district") or "[district]",
        vacant_flag=(p.get("vacant_flag") or "flagged").lower() + " flagged by L&I",
        delinquency_line=delinquency_line,
        violations_line=violations_line,
        total_vacant=format(total_vacant, ","),
        date=datetime.date.today().strftime("%B %d, %Y"),
        your_name="[YOUR NAME]",
        your_address="[YOUR ADDRESS]",
    )
    return {
        "draft": text,
        "type": kind,
        "opa_id": p["opa_id"],
        "review_notice": "Draft generated from public records. Review every "
                         "fact, add your name and address, and send it "
                         "yourself. Verify the current councilmember at "
                         "phila.gov/council before mailing district letters.",
    }
