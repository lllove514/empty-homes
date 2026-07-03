"""Shared helpers for the fetch pipeline. Stdlib only."""
import json
import os
import time
import urllib.parse
import urllib.request

CARTO_URL = "https://phl.carto.com/api/v2/sql"
RAW_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "raw")


def carto(sql):
    """Run one query against the city's Carto SQL API. POST so long IN
    lists never hit URL limits. Retries twice on transient failures."""
    body = urllib.parse.urlencode({"q": sql}).encode()
    last_err = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(CARTO_URL, data=body)
            with urllib.request.urlopen(req, timeout=120) as resp:
                out = json.load(resp)
            if "error" in out:
                raise RuntimeError("carto error: %s" % out["error"])
            return out["rows"]
        except RuntimeError:
            raise  # a SQL error will not fix itself, fail loud
        except Exception as err:  # network hiccup, retry
            last_err = err
            time.sleep(2 * (attempt + 1))
    raise last_err


def probe_columns(table, columns):
    """LIMIT 1 probe of the exact columns a fetcher needs. On a missing
    column, print the error and the real column list, then exit."""
    try:
        carto("SELECT %s FROM %s LIMIT 1" % (", ".join(columns), table))
    except RuntimeError as err:
        print("PROBE FAILED for %s: %s" % (table, err))
        row = carto("SELECT * FROM %s LIMIT 1" % table)
        print("columns actually present: %s" % sorted(row[0].keys()))
        raise SystemExit(1)


def batched(seq, size):
    for i in range(0, len(seq), size):
        yield seq[i:i + size]


def raw_path(name):
    os.makedirs(RAW_DIR, exist_ok=True)
    return os.path.join(RAW_DIR, name)


def save_rows(name, rows, source):
    path = raw_path(name)
    with open(path, "w") as f:
        json.dump({"source": source,
                   "fetched_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                   "rows": rows}, f)
    print("wrote %d rows -> %s" % (len(rows), path))


def load_rows(name):
    with open(raw_path(name)) as f:
        return json.load(f)["rows"]


def load_vpi_ids():
    """Unique zero-padded opa ids from the VPI spine."""
    with open(raw_path("vpi.json")) as f:
        fc = json.load(f)
    ids, seen = [], set()
    for feat in fc["features"]:
        opa = feat["properties"].get("opa_id")
        if opa is None:
            continue
        opa = str(opa).strip().zfill(9)
        if opa not in seen:
            seen.add(opa)
            ids.append(opa)
    return ids


def fixture_sized(n, full_min):
    """Fixture datasets (small real slices used in development) relax the
    full-run size assertions but still run every structural check."""
    if n >= full_min:
        return False
    print("NOTE: %d rows is fixture-sized (full run expects >= %d); "
          "size assertions relaxed, structural checks still enforced" % (n, full_min))
    return True
