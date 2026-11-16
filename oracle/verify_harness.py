#!/usr/bin/env python3
"""One command that establishes whether the harness can be trusted.

Runs every property the harness must have, each as a positive AND negative
control, and prints a single verdict. If this is not green, no renderer result
produced by the harness means anything.

  1. version pin       a wrong expected version must be REFUSED (exit 4), not
                       silently rendered with a different runtime
  2. blank guard       a genuinely empty frame must be REJECTED (exit 3) and
                       must not leave a file behind
  3. determinism       the same render twice must be byte-identical
  4. cross-backend     two independent renderers must agree on a known fixture
                       (their disagreement is the noise floor, not a verdict)
  5. check selftest    every pixel check must fail its mutant (19 cases)
  6. verdict selftest  band.py must pass, fail and refuse on the right inputs

  python3 oracle/verify_harness.py [--json]
Exit 0 = the harness is trustworthy. Non-zero = it is not, and the failing
property is named.
"""
import argparse
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
PY = sys.executable
NODE = os.environ.get("DSH_NODE") or "node"
FIX = os.path.join(REPO, "rive-cpp/tests/unit_tests/assets")
CLFP = os.path.join(FIX, "component_list_follow_path.riv")
DSM = os.path.join(FIX, "component_list_default_state_machine.riv")

A = "/tmp/vh_canvas_t1.png"
B = "/tmp/vh_webgl_t1.png"
A2 = "/tmp/vh_canvas_t1_2.png"
AMIS = "/tmp/vh_canvas_t2.png"
REF = "/tmp/vh_ref_t1.png"


def run(cmd, env=None, timeout=240):
    e = dict(os.environ)
    if env:
        e.update(env)
    return subprocess.run(cmd, capture_output=True, text=True, env=e, timeout=timeout)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    results = []

    def step(name, ok, detail):
        results.append({"step": name, "ok": bool(ok), "detail": detail})

    # 0. produce the reference pair we compare against (also proves the
    #    renderer runs at all)
    r = run([NODE, "oracle/render_browser.mjs", "rive_canvas", "1", A, "500", "Main", "State Machine 1"],
            env={"RIVE_FIXTURE": CLFP})
    step("render_runs", r.returncode == 0, (r.stdout or r.stderr).strip().splitlines()[-1][:160])

    # 1. version pin must refuse a wrong version
    r = run([NODE, "oracle/render_browser.mjs", "rive_canvas", "1", "/tmp/vh_never.png", "500", "Main", "State Machine 1"],
            env={"RIVE_FIXTURE": CLFP, "RIVE_EXPECT": "9.9.9"})
    step("version_pin_refuses", r.returncode == 4, "exit=%d" % r.returncode)

    # 2. blank guard must reject an empty frame and write nothing
    never = "/tmp/vh_blank.png"
    if os.path.exists(never):
        os.remove(never)
    r = run([NODE, "oracle/render_browser.mjs", "rive_canvas", "1", never, "200", "Main", "Main Machine"],
            env={"RIVE_FIXTURE": DSM})
    step("blank_guard_rejects", r.returncode == 3 and not os.path.exists(never),
         "exit=%d file_written=%s" % (r.returncode, os.path.exists(never)))

    # 3. determinism
    run([NODE, "oracle/render_browser.mjs", "rive_canvas", "1", A2, "500", "Main", "State Machine 1"],
        env={"RIVE_FIXTURE": CLFP})
    same = os.path.exists(A) and os.path.exists(A2) and open(A, "rb").read() == open(A2, "rb").read()
    step("determinism", same, "two renders byte-identical=%s" % same)

    # 4. cross-backend agreement (their band is the noise floor)
    run([NODE, "oracle/render_browser.mjs", "rive_webgl", "1", B, "500", "Main", "State Machine 1"],
        env={"RIVE_FIXTURE": CLFP})
    r = run([PY, "oracle/band.py", "--a", A, "--b", B, "--ours", A, "--inset", "2"])
    step("cross_backend_agrees", r.returncode == 0,
         (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip())[:160])

    # 4b. pairing must be REFUSED across ticks -- the original bug
    import shutil
    shutil.copy(A, AMIS)
    r = run([PY, "oracle/band.py", "--a", A, "--b", B, "--ours", AMIS, "--inset", "2"])
    step("pairing_refuses_mismatch", r.returncode == 2, "exit=%d" % r.returncode)

    # 5. check-level selftest (needs a deterministic node-side reference)
    if not os.path.exists(REF):
        r = run([NODE, "oracle/render_ref.mjs", CLFP, "Main", "1", REF, "500"])
        if r.returncode != 0:
            step("check_selftest", False, "could not build reference: " + r.stderr.strip()[:160])
            REF_READY = False
        else:
            REF_READY = True
    else:
        REF_READY = True
    if REF_READY:
        r = run([PY, "oracle/selftest.py", "--ref", REF, "--inset", "2"])
        step("check_selftest", r.returncode == 0,
             (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip())[:160])

    # 6. verdict-level selftest
    r = run([PY, "oracle/band_selftest.py", "--a", A, "--b", B, "--inset", "2"])
    step("verdict_selftest", r.returncode == 0,
         (r.stdout.strip().splitlines()[-1] if r.stdout.strip() else r.stderr.strip())[:160])

    failed = [s for s in results if not s["ok"]]
    if args.json:
        print(json.dumps({"harness_trustworthy": not failed, "steps": results}, indent=2))
    else:
        print("HARNESS VERIFICATION")
        for s in results:
            print("  [%s] %-22s %s" % ("PASS" if s["ok"] else "FAIL", s["step"], s["detail"]))
        print()
        print("VERDICT:", "harness trustworthy" if not failed else
              "HARNESS NOT TRUSTWORTHY -- %s" % ", ".join(s["step"] for s in failed))
    sys.exit(0 if not failed else 1)


if __name__ == "__main__":
    main()
