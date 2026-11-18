#!/usr/bin/env python3
"""provenance.py -- record and check render provenance for ours assets.

Why this exists: a gate verdict is only as current as the render it
measured. The iba/deam/hff adjudication ruled "renderer bug" on ours_*.bmp
files that predated the bg-fill fix already on master -- the evidence was
real, the renderer was fine. A verdict about code requires evidence
produced by that code.

Model:
  stamp  <gate> --driver PATH   write oracle/images/<ours>.prov.json
                                {driver, commit, ts}
  check                      classify every manifest ours asset:
                                fresh          prov exists, deps older than asset
                                stale          prov exists, a dep is newer
                                unprovenanced  no prov sidecar (all current assets)
  --selftest                mutant-backed check of the classifier itself

Staleness is mtime-based: a dep file newer than the render means the
render may not reflect current renderer code. Deps = the gate's prov
driver + oracle/render_deps.json "shared" paths (dirs scanned
recursively). mtime is a heuristic -- a checkout can refresh it -- so
"stale" means "re-render before trusting this verdict", not "wrong".
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
IMG = os.path.join(HERE, "images")
DEPS_JSON = os.path.join(HERE, "render_deps.json")


def load_gates():
    return json.load(open(os.path.join(HERE, "gates.json")))


def prov_path(ours_name):
    return os.path.join(IMG, ours_name + ".prov.json")


def shared_deps():
    if not os.path.isfile(DEPS_JSON):
        return []
    cfg = json.load(open(DEPS_JSON))
    return cfg.get("shared", [])


def iter_dep_files(deps):
    for d in deps:
        p = d if os.path.isabs(d) else os.path.join(REPO, d)
        if os.path.isfile(p):
            yield p
        elif os.path.isdir(p):
            for root, _dirs, files in os.walk(p):
                for f in files:
                    yield os.path.join(root, f)


def newest_dep_mtime(deps):
    newest = 0.0
    newest_path = None
    for p in iter_dep_files(deps):
        try:
            m = os.path.getmtime(p)
        except OSError:
            continue
        if m > newest:
            newest, newest_path = m, p
    return newest, newest_path


def classify(g, repo=REPO):
    """-> (state, detail). state in fresh|stale|unprovenanced|missing."""
    ours = os.path.join(IMG, g["ours"])
    if not os.path.isfile(ours):
        return "missing", "ours asset absent"
    pp = prov_path(g["ours"])
    if not os.path.isfile(pp):
        return "unprovenanced", "no .prov.json sidecar"
    prov = json.load(open(pp))
    deps = list(shared_deps())
    drv = prov.get("driver")
    if drv:
        deps.append(drv if os.path.isabs(drv) else os.path.join(repo, drv))
    newest, npath = newest_dep_mtime(deps)
    om = os.path.getmtime(ours)
    if newest > om:
        return "stale", "dep %s newer than render" % os.path.relpath(npath, repo)
    # git-anchored check for in-repo deps: mtime lies after checkouts;
    # commit-diff does not. ".." paths and abs paths are other repos --
    # mtime covers those.
    commit = prov.get("commit")
    if commit and commit != "unknown":
        for d in deps:
            if os.path.isabs(d) or d.startswith(".."):
                continue
            for args in (["diff", "--name-only", commit, "HEAD", "--", d],
                         ["status", "--porcelain", "--", d]):
                try:
                    r = subprocess.run(["git", "-C", repo] + args,
                                       capture_output=True, text=True, timeout=10)
                except Exception:
                    continue
                if r.returncode == 0 and r.stdout.strip():
                    verb = "changed since" if args[0] == "diff" else "dirty in"
                    return "stale", "dep %s %s artifact commit %s" % (
                        d, verb, str(commit)[:8])
    return "fresh", "commit %s driver %s" % (str(prov.get("commit"))[:8], drv or "?")


def stamp(gate_name, driver):
    gates = {g["gate"]: g for g in load_gates()}
    if gate_name not in gates:
        sys.exit("REFUSING: no gate %r in manifest" % gate_name)
    g = gates[gate_name]
    try:
        commit = subprocess.check_output(
            ["git", "-C", REPO, "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        commit = "unknown"
    drv = os.path.relpath(os.path.abspath(driver), REPO)
    if not os.path.isfile(driver):
        sys.exit("REFUSING: driver %r is not a file" % driver)
    pp = prov_path(g["ours"])
    json.dump({"driver": drv, "commit": commit, "ts": time.time()},
              open(pp, "w"), indent=1)
    print("stamped %s -> %s (commit %s)" % (g["ours"], os.path.basename(pp), commit[:8]))


def selftest():
    """Mutant-backed: fresh passes, stale fires, unprovenanced is named."""
    fails = []
    with tempfile.TemporaryDirectory() as td:
        img = os.path.join(td, "images")
        os.makedirs(img)
        depdir = os.path.join(td, "deps")
        os.makedirs(depdir)
        dep = os.path.join(depdir, "renderer.k")
        open(dep, "w").write("x")
        ours = os.path.join(img, "ours_t1.bmp")
        open(ours, "w").write("px")

        # case 1: dep older than asset -> fresh
        os.utime(dep, (1000, 1000))
        os.utime(ours, (2000, 2000))
        json.dump({"driver": dep, "commit": "abc"},
                  open(prov_path.__wrapped__(ours) if hasattr(prov_path, "__wrapped__") else os.path.join(img, "ours_t1.bmp.prov.json"), "w"))
        # exercise classify() against the tmp tree via monkeypatched paths
        global IMG, REPO
        old_img, old_repo = IMG, REPO
        IMG, REPO = img, td
        try:
            g = {"ours": "ours_t1.bmp"}
            st, _ = classify(g)
            if st != "fresh":
                fails.append("fresh case got %s" % st)
            # case 2: dep newer -> stale (the mutant: bump dep mtime)
            os.utime(dep, (3000, 3000))
            st, det = classify(g)
            if st != "stale":
                fails.append("stale case got %s (%s)" % (st, det))
            # case 3: no sidecar -> unprovenanced
            os.remove(os.path.join(img, "ours_t1.bmp.prov.json"))
            st, _ = classify(g)
            if st != "unprovenanced":
                fails.append("unprovenanced case got %s" % st)
        finally:
            IMG, REPO = old_img, old_repo
    if fails:
        for f in fails:
            print("FAIL", f)
        sys.exit(1)
    print("provenance selftest: 3/3 PASS (fresh, stale, unprovenanced)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", choices=["stamp", "check"])
    ap.add_argument("gate", nargs="?")
    ap.add_argument("--driver")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return selftest()
    if a.cmd == "stamp":
        if not a.gate or not a.driver:
            sys.exit("usage: provenance.py stamp GATE --driver PATH")
        return stamp(a.gate, a.driver)
    # default: check
    gates = load_gates()
    counts = {}
    for g in gates:
        st, det = classify(g)
        counts[st] = counts.get(st, 0) + 1
        if st != "fresh":
            print("%-13s %-14s %s" % (g["gate"], st, det))
    print("provenance: %s" % ", ".join("%s=%d" % kv for kv in sorted(counts.items())))


if __name__ == "__main__":
    main()
