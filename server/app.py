"""Empty Homes server: static files plus a small read-only JSON API.

Run:  python3 server/app.py          (port 8080, override with PORT env)
"""
import json
import os
import re
import sqlite3
import sys
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse, parse_qs

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB = os.path.join(ROOT, "data", "empty_homes.db")
WEB = os.path.join(ROOT, "web")
SNAPSHOT_NOTE = "as of June 2022"


def db():
    con = sqlite3.connect("file:%s?mode=ro" % DB, uri=True)
    con.row_factory = sqlite3.Row
    return con


def score_components(p, kind):
    parts = []
    years = min(p["years_owed"] or 0, 10)
    if years:
        parts.append({"points": years,
                      "reason": "%d year(s) tax-delinquent (capped at 10, %s)"
                                % (p["years_owed"], SNAPSHOT_NOTE)})
    v = min(p["open_violations"] or 0, 5)
    if v:
        parts.append({"points": v,
                      "reason": "%d open L&I violation(s) (capped at 5)"
                                % p["open_violations"]})
    if kind == "public":
        parts.append({"points": 3, "reason": "publicly owned"})
    if str(p["sheriff_sale"] or "").upper() in ("Y", "TRUE"):
        parts.append({"points": 2, "reason": "flagged for sheriff sale (%s)" % SNAPSHOT_NOTE})
    return parts


def api_search(qs):
    q = (qs.get("q", [""])[0] or "").strip().upper()
    if len(q) < 2:
        return {"results": []}
    like = " ".join(q.split()) + "%"
    con = db()
    rows = con.execute(
        "SELECT p.opa_id, p.address, p.zip, p.score, p.lat, p.lon,"
        " coalesce(o.canonical_name, p.owner_raw) AS owner"
        " FROM parcels p LEFT JOIN owners o ON o.id = p.owner_id"
        " WHERE p.address LIKE ? OR p.opa_id = ?"
        " ORDER BY p.address LIMIT 25", (like, q)).fetchall()
    con.close()
    return {"results": [dict(r) for r in rows]}


def api_parcel(opa_id):
    con = db()
    p = con.execute(
        "SELECT p.*, o.canonical_name AS owner_name, o.kind AS owner_kind,"
        " o.id AS oid, o.cluster_id"
        " FROM parcels p LEFT JOIN owners o ON o.id = p.owner_id"
        " WHERE p.opa_id = ?", (opa_id,)).fetchone()
    if not p:
        con.close()
        return None
    violations = [dict(r) for r in con.execute(
        "SELECT title, date FROM violations WHERE opa_id = ? ORDER BY date DESC",
        (opa_id,))]
    con.close()
    out = dict(p)
    out["violations"] = violations
    out["score_components"] = score_components(p, p["owner_kind"])
    out["delinquency_snapshot"] = SNAPSHOT_NOTE
    return out


def api_owner(owner_id):
    con = db()
    o = con.execute("SELECT * FROM owners WHERE id = ?", (owner_id,)).fetchone()
    if not o:
        con.close()
        return None
    out = dict(o)
    out["aliases"] = sorted({r["alias"] for r in con.execute(
        "SELECT alias FROM owner_aliases WHERE owner_id = ?", (owner_id,))})
    out["parcels"] = [dict(r) for r in con.execute(
        "SELECT opa_id, address, zip, score, delinquent, years_owed, total_due,"
        " open_violations, lat, lon FROM parcels WHERE owner_id = ?"
        " ORDER BY score DESC LIMIT 500", (owner_id,))]
    if o["cluster_id"] is not None:
        out["cluster"] = [dict(r) for r in con.execute(
            "SELECT id, canonical_name, kind, parcel_count FROM owners"
            " WHERE cluster_id = ? AND id != ?", (o["cluster_id"], owner_id))]
        addr = con.execute(
            "SELECT mailing_addr FROM owner_aliases WHERE owner_id = ?"
            " AND mailing_addr IS NOT NULL LIMIT 1", (owner_id,)).fetchone()
        out["shared_mailing_addr"] = addr["mailing_addr"] if addr else None
    con.close()
    return out


def api_owners(qs):
    kind = (qs.get("kind", [""])[0] or "").strip()
    where, params = "", []
    if kind in ("public", "llc", "individual", "other"):
        where = "WHERE kind = ?"
        params = [kind]
    con = db()
    rows = con.execute(
        "SELECT id, canonical_name, kind, cluster_id, parcel_count, total_due,"
        " avg_years_owed FROM owners %s ORDER BY parcel_count DESC, total_due DESC"
        " LIMIT 100" % where, params).fetchall()
    con.close()
    return {"owners": [dict(r) for r in rows], "note": SNAPSHOT_NOTE}


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=WEB, **kwargs)

    def log_message(self, fmt, *args):
        sys.stderr.write("%s\n" % (fmt % args))

    def send_json(self, obj, status=200):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        qs = parse_qs(url.query)
        try:
            if url.path == "/api/search":
                return self.send_json(api_search(qs))
            if url.path == "/api/owners":
                return self.send_json(api_owners(qs))
            m = re.fullmatch(r"/api/parcel/(\d{9})", url.path)
            if m:
                out = api_parcel(m.group(1))
                return self.send_json(out or {"error": "no such parcel"},
                                      200 if out else 404)
            m = re.fullmatch(r"/api/owner/(\d+)", url.path)
            if m:
                out = api_owner(int(m.group(1)))
                return self.send_json(out or {"error": "no such owner"},
                                      200 if out else 404)
            if url.path.startswith("/api/"):
                return self.send_json({"error": "unknown endpoint"}, 404)
        except Exception as err:  # never leak a traceback to the client
            sys.stderr.write("api error: %r\n" % err)
            return self.send_json({"error": "server error"}, 500)
        return super().do_GET()

    def do_POST(self):
        url = urlparse(self.path)
        try:
            length = min(int(self.headers.get("Content-Length", 0)), 100_000)
            payload = json.loads(self.rfile.read(length) or b"{}")
            if url.path == "/api/ask":
                import ask
                return self.send_json(ask.answer(payload.get("question", "")))
            if url.path == "/api/draft":
                import draft
                return self.send_json(draft.draft(payload))
            return self.send_json({"error": "unknown endpoint"}, 404)
        except Exception as err:
            sys.stderr.write("api error: %r\n" % err)
            return self.send_json({"error": "server error"}, 500)


def main():
    port = int(os.environ.get("PORT", "8080"))
    server = ThreadingHTTPServer(("0.0.0.0", port), Handler)
    print("serving on http://localhost:%d" % port)
    server.serve_forever()


if __name__ == "__main__":
    main()
