#!/usr/bin/env python3
"""
SKA beat fan-out driver.  1 second = 1 beat = 1 trigger.

The platform's cascade decides WHAT runs and WHERE; this process only keeps
the beat and fires. Every 300 beats it pulls the sealed plan
(/api/beat/manifest). On each beat it fires one request per lane that has
work on that beat - all lanes of a beat at the same instant, each landing on
its own Cloudflare isolate (parallelism through the network). Beats with no
work cost nothing. Workflows due on the same lane and beat arrive joined as
one chained request.

Beat grid is anchored to genesis 1530403200 (2018-07-01T00:00:00Z).
"""
import os, time, json, urllib.request, urllib.error
from concurrent.futures import ThreadPoolExecutor

GENESIS = 1530403200
BASE = os.environ.get("SKA_WORKER_URL", "https://saleskingacademy.com").rstrip("/")
KEY = os.environ.get("SKA_HEARTBEAT_KEY", "")
RUN_MINUTES = float(os.environ.get("RUN_MINUTES", "300"))
BUDGET = int(os.environ.get("DAILY_REQUEST_BUDGET", "8000"))   # this run's cap
REFRESH = 300                                                   # beats between plans

def beat_now():
    return int(time.time()) - GENESIS

def call(method, path, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("X-Heartbeat-Key", KEY)
    req.add_header("User-Agent", "ska-beat-fanout/1.0")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read() or b"{}")
        except Exception: return e.code, {}
    except Exception as e:
        return 0, {"error": type(e).__name__}

if not KEY:
    raise SystemExit("SKA_HEARTBEAT_KEY missing")

pool = ThreadPoolExecutor(max_workers=26)
sent = ran = failed = 0
plan, plan_at, next_refresh = None, None, 0
deadline = time.time() + RUN_MINUTES * 60
print("SKA beat fan-out | base=%s | run=%smin | budget=%d" % (BASE, RUN_MINUTES, BUDGET), flush=True)

def fire_lane(entry):
    beat, lane, jobs = entry
    st, d = call("POST", "/api/beat/lane", {"start_beat": plan["start_beat"], "interlock16": plan["interlock16"],
                                            "seal": plan["seal"], "lane": lane, "jobs": jobs, "beat": beat})
    return beat, lane, st, d

by_beat = {}
while time.time() < deadline and sent < BUDGET:
    b = beat_now()
    if b >= next_refresh:
        st, m = call("GET", "/api/beat/manifest")
        sent += 1
        if st == 200 and m.get("ok"):
            plan = m
            by_beat = {}
            for e in m.get("schedule", []):
                by_beat.setdefault(e[0], []).append(e)
            print("plan beats %d-%d | active %s | placed %s | lane requests %s | carried failures %s | interlock %s" % (
                m["start_beat"], m["end_beat"], m.get("jobs_active"), m.get("placed"), m.get("lane_requests"),
                m.get("carried_failures"), m.get("interlock16")), flush=True)
            next_refresh = m["start_beat"] + REFRESH - 5
        else:
            print("manifest failed: HTTP %s %s" % (st, str(m)[:160]), flush=True)
            next_refresh = b + 30
    due = by_beat.pop(b, [])
    if due and plan:
        futs = [pool.submit(fire_lane, e) for e in due]          # all lanes of this beat, same instant
        sent += len(due)
        for f in futs:
            beat, lane, st, d = f.result()
            if st == 200:
                ran += d.get("ran", 0)
                print("beat %d L%02d ok ran=%s %s" % (beat, lane, d.get("ran"),
                      ",".join("%s:%s" % (j.get("type") or j.get("id"), j.get("result") or j.get("skipped")) for j in d.get("jobs", []))), flush=True)
            else:
                failed += 1
                print("beat %d L%02d HTTP %s %s" % (beat, lane, st, str(d)[:120]), flush=True)
    # sleep to the next beat boundary
    time.sleep(max(0.0, (GENESIS + b + 1) - time.time()))

print("done | requests %d | workflows ran %d | lane failures %d" % (sent, ran, failed), flush=True)
