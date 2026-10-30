"""Check a running deployment end to end.

    python scripts/smoke.py --api https://<api host> [--web https://<web host>]

Standard library only, so it runs from any machine. Prints one line per check
and stops at the first failure (exit code 1).
"""

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


class Failure(Exception):
    pass


def call(method, url, body=None, headers=None, timeout=90):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=headers or {})
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, res.headers, res.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.headers, e.read().decode()


def check(name, ok, why):
    if not ok:
        raise Failure(f"{name}: {why}")
    print(f"ok  {name}")


def wait_for_health(api, seconds):
    # a free Render instance takes about a minute to wake up
    deadline = time.monotonic() + seconds
    last = "no answer"
    while True:
        try:
            status, _, text = call("GET", f"{api}/api/health/", timeout=30)
            if status == 200:
                return
            last = f"{status} {text[:80]}"
        except OSError as e:
            last = str(e)
        if time.monotonic() > deadline:
            raise Failure(f"health: {last}")
        time.sleep(5)


def city(api, query, label):
    status, _, text = call("GET", f"{api}/api/cities/?q={query}")
    found = [c for c in json.loads(text) if c["label"] == label] if status == 200 else []
    check(f"cities {label}", found, f"{status}, not in {text[:120]}")
    return found[0]["id"]


def run(api, web, wait):
    wait_for_health(api, wait)
    print("ok  health")

    status, _, text = call("GET", f"{api}/api/prices/active/")
    count = json.loads(text).get("station_count", 0) if status == 200 else 0
    check("prices", count > 0, f"{status} {text[:120]}")

    austin = city(api, "austin", "Austin, TX")
    chicago = city(api, "chicago", "Chicago, IL")

    status, headers, text = call(
        "POST", f"{api}/api/plans/", {"from_city": austin, "to_city": chicago}
    )
    doc = json.loads(text) if status == 201 else {}
    check("plan", status == 201 and doc.get("savings", -1) >= 0, f"{status} {text[:200]}")
    location = headers.get("Location", "")
    status, _, text = call("GET", api + location)
    check("saved plan", status == 200 and json.loads(text)["id"] == doc["id"], f"{status}")

    if not web:
        return
    status, headers, _ = call(
        "OPTIONS",
        f"{api}/api/plans/",
        headers={"Origin": web, "Access-Control-Request-Method": "POST"},
    )
    allowed = headers.get("Access-Control-Allow-Origin") if headers else None
    check("cors", allowed == web, f"{web} not allowed")

    status, _, text = call("GET", f"{web}/")
    check("web home", status == 200 and "Haulfill" in text, f"{status}")
    status, _, _ = call("GET", f"{web}/plans/{doc['id']}")
    check("web plan page", status == 200, f"{status}")


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check a deployed Haulfill.")
    parser.add_argument("--api", required=True)
    parser.add_argument("--web")
    parser.add_argument("--wait", type=int, default=120, help="seconds to wait for health")
    args = parser.parse_args(argv)
    try:
        run(args.api.rstrip("/"), args.web.rstrip("/") if args.web else None, args.wait)
    except Failure as e:
        print(f"FAIL {e}")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
