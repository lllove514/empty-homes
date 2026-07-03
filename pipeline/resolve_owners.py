"""Owner entity resolution.

Pass 1 groups parcels by normalized owner name, resolving public agencies
through the hand-curated aliases in agencies.json.
Pass 2 links non-public owners that share a mailing address into clusters.
This surfaces shell-LLC networks as the fact they are: shared addresses.

Run:    python3 pipeline/resolve_owners.py
Check:  python3 pipeline/resolve_owners.py --check
"""
import json
import os
import re
import sqlite3
import sys

from build_db import DB

AGENCIES = os.path.join(os.path.dirname(__file__), "agencies.json")
SUFFIXES = {"LLC", "LP", "INC", "CORP", "LTD", "CO", "COMPANY", "LLP", "TR", "TRUST"}
BIZ_WORDS = {"PROPERTIES", "PROPERTY", "REALTY", "REAL", "ESTATE", "HOMES",
             "INVESTMENT", "INVESTMENTS", "HOLDINGS", "GROUP", "PARTNERS",
             "DEVELOPMENT", "CAPITAL", "VENTURES", "MANAGEMENT", "ASSOCIATES",
             "CHURCH", "MINISTRIES", "BAPTIST", "TEMPLE", "MOSQUE", "CDC",
             "ASSOCIATION", "FOUNDATION", "VILLAGE", "COMMUNITY"}
# Mailing addresses used by mass mail-forwarders or servicers; sharing one of
# these proves nothing, so they never form clusters.
CLUSTER_MIN_SHARED = 2
NOISE_ADDR_THRESHOLD = 40  # ponytail: fixture-scale; tune upward for full city


def normalize(name):
    s = re.sub(r"[^A-Z0-9 ]", " ", str(name).upper())
    return " ".join(s.split())


def classify(norm, had_suffix, agency_lookup):
    if norm in agency_lookup:
        return agency_lookup[norm], "public"
    if had_suffix:
        return norm, "llc"
    tokens = norm.split()
    # owner strings are truncated at 50 chars, so match business words by
    # prefix too (INVESTM, PROPERT, MANAGEM survive truncation that way)
    if any(t in BIZ_WORDS or any(w.startswith(t) for w in BIZ_WORDS if len(t) >= 6)
           for t in tokens):
        return norm, "other"
    if 2 <= len(tokens) <= 4:
        return norm, "individual"
    return norm, "other"


def strip_suffix(norm):
    tokens = norm.split()
    had = False
    while tokens and tokens[-1] in SUFFIXES:
        tokens.pop()
        had = True
    return " ".join(tokens), had


def build_agency_lookup():
    with open(AGENCIES) as f:
        agencies = json.load(f)
    lookup = {}
    for canonical, variants in agencies.items():
        for v in [canonical] + variants:
            lookup[normalize(v)] = canonical
    return lookup


def main():
    agency_lookup = build_agency_lookup()
    con = sqlite3.connect(DB)
    con.executescript("""
    DROP TABLE IF EXISTS owners;
    DROP TABLE IF EXISTS owner_aliases;
    CREATE TABLE owners (
      id INTEGER PRIMARY KEY,
      canonical_name TEXT UNIQUE,
      kind TEXT,
      cluster_id INTEGER,
      parcel_count INTEGER,
      total_due REAL,
      avg_years_owed REAL
    );
    CREATE TABLE owner_aliases (alias TEXT, mailing_addr TEXT, owner_id INTEGER);
    """)

    owner_ids = {}

    def owner_id_for(canonical, kind):
        if canonical not in owner_ids:
            cur = con.execute("INSERT INTO owners (canonical_name, kind) VALUES (?,?)",
                              (canonical, kind))
            owner_ids[canonical] = cur.lastrowid
        return owner_ids[canonical]

    for opa_id, owner_raw, mailing in con.execute(
            "SELECT opa_id, owner_raw, mailing_addr FROM parcels").fetchall():
        raw_first = (owner_raw or "").split(" / ")[0]
        if not raw_first.strip():
            continue
        norm = normalize(raw_first)
        stripped, had_suffix = strip_suffix(norm)
        canonical, kind = classify(stripped if had_suffix else norm,
                                   had_suffix, agency_lookup)
        oid = owner_id_for(canonical, kind)
        con.execute("UPDATE parcels SET owner_id=? WHERE opa_id=?", (oid, opa_id))
        con.execute("INSERT INTO owner_aliases VALUES (?,?,?)",
                    (raw_first.strip(), mailing, oid))

    # pass 2: mailing-address clusters among non-public, non-individual owners
    addr_owners = {}
    for addr, oid in con.execute(
            "SELECT a.mailing_addr, a.owner_id FROM owner_aliases a "
            "JOIN owners o ON o.id = a.owner_id "
            "WHERE a.mailing_addr IS NOT NULL AND o.kind IN ('llc','other')"):
        addr_owners.setdefault(addr, set()).add(oid)

    cluster_n = 0
    assigned = {}
    for addr, oids in sorted(addr_owners.items()):
        if len(oids) < CLUSTER_MIN_SHARED or len(oids) > NOISE_ADDR_THRESHOLD:
            continue
        existing = {assigned[o] for o in oids if o in assigned}
        if existing:
            cid = min(existing)
        else:
            cluster_n += 1
            cid = cluster_n
        for o in oids:
            assigned[o] = cid
    for oid, cid in assigned.items():
        con.execute("UPDATE owners SET cluster_id=? WHERE id=?", (cid, oid))

    con.execute("""
      UPDATE owners SET
        parcel_count = (SELECT count(*) FROM parcels p WHERE p.owner_id = owners.id),
        total_due = (SELECT coalesce(sum(total_due),0) FROM parcels p WHERE p.owner_id = owners.id),
        avg_years_owed = (SELECT round(avg(years_owed),1) FROM parcels p
                          WHERE p.owner_id = owners.id AND years_owed IS NOT NULL)
    """)
    con.execute("UPDATE parcels SET score = score + 3 WHERE owner_id IN "
                "(SELECT id FROM owners WHERE kind='public')")
    con.commit()

    n_owners = con.execute("SELECT count(*) FROM owners").fetchone()[0]
    n_clusters = len(set(assigned.values())) if assigned else 0
    print("owners: %d, mailing-address clusters: %d" % (n_owners, n_clusters))
    con.close()


def check():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    print("top 20 owners by parcel count:")
    for name, kind, n, due in con.execute(
            "SELECT canonical_name, kind, parcel_count, total_due FROM owners "
            "ORDER BY parcel_count DESC LIMIT 20"):
        print("  %4d  %-10s %-45s due=$%s" % (n, kind, name, format(due or 0, ",.0f")))

    print("largest mailing-address clusters:")
    rows = con.execute(
        "SELECT cluster_id, group_concat(canonical_name, ' | '), count(*) c "
        "FROM owners WHERE cluster_id IS NOT NULL GROUP BY cluster_id "
        "ORDER BY c DESC LIMIT 5").fetchall()
    for cid, names, c in rows:
        addr = con.execute(
            "SELECT mailing_addr FROM owner_aliases a JOIN owners o ON o.id=a.owner_id "
            "WHERE o.cluster_id=? LIMIT 1", (cid,)).fetchone()[0]
        print("  cluster %d (%d owners) @ %s" % (cid, c, addr))
        print("    %s" % names)

    print("parcels per owner kind:")
    for kind, n in con.execute("SELECT o.kind, count(*) FROM parcels p "
                               "JOIN owners o ON o.id=p.owner_id GROUP BY 1 ORDER BY 2 DESC"):
        print("  %5d  %s" % (n, kind))

    pha = con.execute("SELECT count(*), coalesce(sum(parcel_count),0) FROM owners "
                      "WHERE canonical_name='PHILADELPHIA HOUSING AUTHORITY'").fetchone()
    assert pha[0] == 1, "PHA resolved to %d owners, expected exactly 1" % pha[0]
    min_parcels = 20  # fixture-sized floor; full city expects > 100
    assert pha[1] >= min_parcels, "PHA has %d parcels, expected >= %d" % (pha[1], min_parcels)
    print("PASS  PHA resolves to a single owner with %d parcels" % pha[1])
    con.close()


if __name__ == "__main__":
    check() if "--check" in sys.argv else main()
