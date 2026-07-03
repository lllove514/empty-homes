"""The only database access the model gets: three read-only tools.

Every function returns plain dicts straight from SQLite rows. The model
never sees SQL and never writes.
"""
import os
import sqlite3

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "empty_homes.db")


def _db():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    con.row_factory = sqlite3.Row
    return con


def search_parcels(zip=None, council_district=None, owner_kind=None,
                   min_years_owed=None, min_score=None, publicly_owned=None,
                   limit=25):
    where, params = ["1=1"], []
    if zip:
        where.append("p.zip = ?"); params.append(str(zip))
    if council_district:
        where.append("p.council_district = ?"); params.append(str(council_district))
    if owner_kind:
        where.append("o.kind = ?"); params.append(str(owner_kind))
    if publicly_owned:
        where.append("o.kind = 'public'")
    if min_years_owed is not None:
        where.append("p.years_owed >= ?"); params.append(int(min_years_owed))
    if min_score is not None:
        where.append("p.score >= ?"); params.append(int(min_score))
    limit = max(1, min(int(limit or 25), 50))
    con = _db()
    rows = [dict(r) for r in con.execute(
        "SELECT p.opa_id, p.address, p.zip, p.council_district,"
        " o.canonical_name AS owner, o.kind AS owner_kind, o.id AS owner_id,"
        " p.vacant_flag, p.delinquent, p.years_owed, p.total_due,"
        " p.open_violations, p.score"
        " FROM parcels p LEFT JOIN owners o ON o.id = p.owner_id"
        " WHERE %s ORDER BY p.score DESC LIMIT %d" % (" AND ".join(where), limit),
        params)]
    total = con.execute(
        "SELECT count(*) FROM parcels p LEFT JOIN owners o ON o.id = p.owner_id"
        " WHERE %s" % " AND ".join(where), params).fetchone()[0]
    con.close()
    return {"matching_total": total, "returned": len(rows), "parcels": rows}


def get_parcel(opa_id):
    con = _db()
    p = con.execute(
        "SELECT p.*, o.canonical_name AS owner_name, o.kind AS owner_kind,"
        " o.id AS oid FROM parcels p LEFT JOIN owners o ON o.id = p.owner_id"
        " WHERE p.opa_id = ?", (str(opa_id).zfill(9),)).fetchone()
    if not p:
        con.close()
        return {"error": "no parcel with that opa_id in the database"}
    out = dict(p)
    out["violations"] = [dict(r) for r in con.execute(
        "SELECT title, date FROM violations WHERE opa_id = ?", (out["opa_id"],))]
    con.close()
    return out


def get_owner(owner_id):
    con = _db()
    o = con.execute("SELECT * FROM owners WHERE id = ?",
                    (int(owner_id),)).fetchone()
    if not o:
        con.close()
        return {"error": "no owner with that id in the database"}
    out = dict(o)
    out["parcels"] = [dict(r) for r in con.execute(
        "SELECT opa_id, address, zip, delinquent, years_owed, total_due,"
        " open_violations, score FROM parcels WHERE owner_id = ?"
        " ORDER BY score DESC LIMIT 100", (out["id"],))]
    if out.get("cluster_id") is not None:
        out["shares_mailing_address_with"] = [dict(r) for r in con.execute(
            "SELECT id, canonical_name, kind, parcel_count FROM owners"
            " WHERE cluster_id = ? AND id != ?", (out["cluster_id"], out["id"]))]
    con.close()
    return out


TOOL_DEFS = [
    {
        "name": "search_parcels",
        "description": "Search likely-vacant Philadelphia parcels. All filters "
                       "optional. Returns up to 50 parcels plus the total match "
                       "count. Delinquency fields are a June 2022 snapshot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "zip": {"type": "string", "description": "5-digit ZIP, e.g. 19133"},
                "council_district": {"type": "string"},
                "owner_kind": {"type": "string",
                               "enum": ["public", "llc", "individual", "other"]},
                "publicly_owned": {"type": "boolean"},
                "min_years_owed": {"type": "integer",
                                   "description": "minimum years tax-delinquent"},
                "min_score": {"type": "integer"},
                "limit": {"type": "integer", "description": "max 50"},
            },
        },
    },
    {
        "name": "get_parcel",
        "description": "Full record for one parcel by 9-digit OPA account number, "
                       "including open violations.",
        "input_schema": {
            "type": "object",
            "properties": {"opa_id": {"type": "string"}},
            "required": ["opa_id"],
        },
    },
    {
        "name": "get_owner",
        "description": "Full record for one owner by numeric id: holdings, back "
                       "taxes, and any entities sharing its mailing address.",
        "input_schema": {
            "type": "object",
            "properties": {"owner_id": {"type": "integer"}},
            "required": ["owner_id"],
        },
    },
]

TOOL_FUNCS = {"search_parcels": search_parcels, "get_parcel": get_parcel,
              "get_owner": get_owner}
