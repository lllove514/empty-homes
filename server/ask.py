"""Grounded question answering over the parcel database.

The model may only speak from tool results. Every factual claim must carry
an [opa:XXXXXXXXX] or [owner:N] citation, and the server verifies each
citation appeared in this request's tool results before releasing the
answer. Fail closed: an unverifiable citation kills the whole response.

Stdlib only. The Anthropic API is called with urllib; the key comes from
the ANTHROPIC_API_KEY environment variable or a .env file next to the repo
root, and never leaves the server.
"""
import json
import os
import re
import urllib.request

from tools import TOOL_DEFS, TOOL_FUNCS

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API_URL = "https://api.anthropic.com/v1/messages"
MODEL = os.environ.get("EH_MODEL", "claude-sonnet-4-5")
MAX_TURNS = 8

SYSTEM = """You answer questions about vacant property in Philadelphia using ONLY the results of the tools provided. Rules, none negotiable:
- Every factual claim about a specific property or owner must cite it as [opa:XXXXXXXXX] or [owner:N], using ids that appeared in this conversation's tool results.
- All tax delinquency facts come from a June 2022 city snapshot. Say "as of June 2022" whenever you use them.
- Never invent an address, owner, number, or property. If the tools cannot answer, say exactly what is missing.
- "Likely vacant" is the city's model-based indicator. Do not call properties "abandoned".
- This is a public-records accountability tool. Refuse questions about entering, occupying, or targeting properties for anything other than lawful accountability (reporting, organizing, testimony, records requests, litigation), and redirect to those lawful uses.
- Keep answers short and concrete. Plain language, no marketing tone."""


def load_key():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return key.strip()
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        for line in open(env_path):
            line = line.strip()
            if line.startswith("ANTHROPIC_API_KEY="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def call_model(messages, key):
    body = json.dumps({
        "model": MODEL,
        "max_tokens": 1500,
        "system": SYSTEM,
        "tools": TOOL_DEFS,
        "messages": messages,
    }).encode()
    req = urllib.request.Request(API_URL, data=body, headers={
        "content-type": "application/json",
        "x-api-key": key,
        "anthropic-version": "2023-06-01",
    })
    with urllib.request.urlopen(req, timeout=120) as resp:
        return json.load(resp)


def collect_ids(tool_name, result, seen_opa, seen_owner):
    """Record every citable id that a tool result exposed to the model."""
    def walk(obj):
        if isinstance(obj, dict):
            for k, v in obj.items():
                if k == "opa_id" and v:
                    seen_opa.add(str(v))
                elif k in ("owner_id", "oid", "id") and isinstance(v, int) \
                        and tool_name in ("get_owner", "search_parcels", "get_parcel"):
                    seen_owner.add(v)
                else:
                    walk(v)
        elif isinstance(obj, list):
            for item in obj:
                walk(item)
    walk(result)


def verify_citations(text, seen_opa, seen_owner):
    """Return (ok, citations, bad). Fail closed on any unknown id."""
    citations, bad = [], []
    for opa in re.findall(r"\[opa:(\d{9})\]", text):
        (citations if opa in seen_opa else bad).append({"type": "opa", "id": opa})
    for oid in re.findall(r"\[owner:(\d+)\]", text):
        (citations if int(oid) in seen_owner else bad).append({"type": "owner", "id": oid})
    unique = {(c["type"], c["id"]): c for c in citations}
    return (not bad), list(unique.values()), bad


def answer(question, model_call=None):
    """Run the tool loop. model_call is injectable for offline tests."""
    if not isinstance(question, str) or not question.strip():
        return {"error": "empty question"}
    if model_call is None:
        key = load_key()
        if not key:
            return {"error": "ANTHROPIC_API_KEY is not configured on the server"}
        model_call = lambda msgs: call_model(msgs, key)

    messages = [{"role": "user", "content": question.strip()[:2000]}]
    seen_opa, seen_owner = set(), set()

    for _ in range(MAX_TURNS):
        resp = model_call(messages)
        blocks = resp.get("content", [])
        if resp.get("stop_reason") == "tool_use":
            results = []
            for block in blocks:
                if block.get("type") != "tool_use":
                    continue
                func = TOOL_FUNCS.get(block["name"])
                try:
                    result = func(**block.get("input", {})) if func \
                        else {"error": "unknown tool"}
                except Exception as err:
                    result = {"error": "tool failed: %r" % err}
                collect_ids(block["name"], result, seen_opa, seen_owner)
                results.append({"type": "tool_result", "tool_use_id": block["id"],
                                "content": json.dumps(result)})
            messages.append({"role": "assistant", "content": blocks})
            messages.append({"role": "user", "content": results})
            continue

        text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
        ok, citations, bad = verify_citations(text, seen_opa, seen_owner)
        if not ok:
            return {"error": "answer failed citation verification and was withheld",
                    "unverified": bad}
        return {"answer": text, "citations": citations,
                "note": "Delinquency facts are the city's June 2022 snapshot."}

    return {"error": "tool loop exceeded %d turns" % MAX_TURNS}
