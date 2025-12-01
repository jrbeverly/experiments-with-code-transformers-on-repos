#!/usr/bin/env python3
import sys
import json
import hashlib
import subprocess
from pathlib import Path

BASE = Path(__file__).parent
ENGINE = BASE / "engine.py"
WORKSPACE = BASE / ".work" / "workspace"
CACHE = BASE / ".work" / "cache"
ATTESTATIONS = CACHE / "attestations.json"
EXAMPLES = BASE / "examples" / "tiny"
GENS = ["code-map", "source-digest", "map-summary"]


def e(*args, ok=(0,)):
    r = subprocess.run(
        [sys.executable, str(ENGINE)] + list(args),
        cwd=BASE, capture_output=True, text=True,
    )
    if r.returncode not in ok:
        sys.exit(f"engine {args} rc={r.returncode}: {r.stderr or r.stdout}")
    return r


def _action(out, want):
    result = []
    for line in out.splitlines():
        c = line.find(":")
        if c < 0:
            continue
        name = line[:c].strip()
        if name not in GENS:
            continue
        tok = line[c + 1:].strip().split()
        if tok and tok[0] == want:
            result.append(name)
    return result


def ran(out):
    return _action(out, "run")


def skipped(out):
    return _action(out, "skip")


def cache():
    if not ATTESTATIONS.exists():
        return []
    return json.loads(ATTESTATIONS.read_text())


def fixture_snap():
    return {p.relative_to(EXAMPLES).as_posix(): p.read_bytes()
            for p in sorted(EXAMPLES.rglob("*")) if p.is_file()}


def ws_snap():
    if not WORKSPACE.exists():
        return {}
    return {p.relative_to(WORKSPACE).as_posix(): p.read_bytes()
            for p in sorted(WORKSPACE.rglob("*")) if p.is_file()}


def ws_id():
    items = [[k, hashlib.sha256(v).hexdigest()] for k, v in sorted(ws_snap().items())]
    return hashlib.sha256(json.dumps(items, separators=(",", ":")).encode()).hexdigest()


def state_ids(out):
    ids = []
    for line in out.splitlines():
        if "before=" in line and "after=" in line:
            ids.append((line.split("before=")[1].split()[0],
                        line.split("after=")[1].split()[0]))
    return ids


def map_entries():
    path = WORKSPACE / "generated" / "code-map.txt"
    lines = path.read_bytes().decode().splitlines()
    return [l for l in lines if l and not l.startswith("#")]


_fails = 0


def check(label, cond, detail=""):
    global _fails
    if not cond:
        _fails += 1
    status = "PASS" if cond else "FAIL"
    print(f"  {status}  {label}" + (f"  ({detail})" if detail else ""))


# --- Scenario 1 -------------------------------------------------------
print("[1] Determinism: two fresh copied runs produce identical bytes and state IDs; fixture unchanged")
fx0 = fixture_snap()

e("reset")
r1 = e("attest")
s1 = ws_snap()
ids1 = state_ids(r1.stdout)

e("reset")
r2 = e("attest")
s2 = ws_snap()
ids2 = state_ids(r2.stdout)

check("fixture unchanged", fixture_snap() == fx0)
check("workspace bytes identical", s1 == s2)
check("state ID sequences match", ids1 == ids2, str(ids1))
print(f"  state IDs: {ids1}")


# --- Scenario 2 -------------------------------------------------------
print("[2] Fresh run executes all three; repeat process run executes none; cache unchanged")
e("reset")
r_new = e("attest")
n0 = len(cache())
r_rep = e("attest")
n1 = len(cache())

check("fresh: ran all three", ran(r_new.stdout) == GENS, str(ran(r_new.stdout)))
check("repeat: ran none", ran(r_rep.stdout) == [], str(ran(r_rep.stdout)))
check("repeat: skipped all", skipped(r_rep.stdout) == GENS, str(skipped(r_rep.stdout)))
check("repeat: cache count unchanged", n0 == n1, f"{n0}=={n1}")
print(f"  fresh: {len(ran(r_new.stdout))} run  repeat: {len(ran(r_rep.stdout))} run / {len(skipped(r_rep.stdout))} skip")


# --- Scenario 3 -------------------------------------------------------
print("[3] notes.txt edit shifts global state; zero transformations run")
e("reset")
e("attest")
id_before = ws_id()
(WORKSPACE / "notes.txt").write_bytes(b"changed\n")
id_after = ws_id()
r = e("attest")

check("global identity shifted", id_before != id_after, f"{id_before[:12]}→{id_after[:12]}")
check("ran none", ran(r.stdout) == [], str(ran(r.stdout)))
check("skipped all", skipped(r.stdout) == GENS, str(skipped(r.stdout)))
print(f"  id: {id_before[:12]} → {id_after[:12]}  run={len(ran(r.stdout))} skip={len(skipped(r.stdout))}")


# --- Scenario 4 -------------------------------------------------------
print("[4] Source byte edit (paths unchanged) runs only source-digest")
e("reset")
e("attest")
(WORKSPACE / "src" / "app.py").write_bytes(b"# edited\ndef main(): pass\n")
r = e("attest")

check("ran source-digest only", ran(r.stdout) == ["source-digest"], str(ran(r.stdout)))
check("skipped code-map and map-summary",
      skipped(r.stdout) == ["code-map", "map-summary"], str(skipped(r.stdout)))
print(f"  ran={ran(r.stdout)}  skipped={skipped(r.stdout)}")


# --- Scenario 5 -------------------------------------------------------
print("[5] Add then remove source path reruns all three each time; entry counts correct")
e("reset")
e("attest")
(WORKSPACE / "src" / "extra.py").write_bytes(b"def extra(): pass\n")
r_add = e("attest")
entries_add = map_entries()

(WORKSPACE / "src" / "extra.py").unlink()
r_rem = e("attest")
entries_rem = map_entries()

check("add: all three ran", ran(r_add.stdout) == GENS, str(ran(r_add.stdout)))
check("add: map has 3 entries", len(entries_add) == 3, str(entries_add))
check("remove: all three ran", ran(r_rem.stdout) == GENS, str(ran(r_rem.stdout)))
check("remove: map back to 2 entries", len(entries_rem) == 2, str(entries_rem))
print(f"  add ran={ran(r_add.stdout)} entries={len(entries_add)}")
print(f"  remove ran={ran(r_rem.stdout)} entries={len(entries_rem)}")


# --- Scenario 6 -------------------------------------------------------
print("[6] Output repair and tamper: owners rerun, independents skip")

for gen, rel in [("code-map", "generated/code-map.txt"),
                 ("source-digest", "generated/source-digest.txt"),
                 ("map-summary", "generated/map-summary.txt")]:
    e("reset")
    e("attest")
    (WORKSPACE / rel).unlink()
    r = e("attest")
    check(f"delete {gen}: only owner reruns", ran(r.stdout) == [gen], str(ran(r.stdout)))

e("reset")
e("attest")
(WORKSPACE / "generated" / "code-map.txt").write_bytes(b"# tampered\n")
r_tamp = e("attest")
r_post = e("attest")
check("tamper code-map: reruns on tamper", ran(r_tamp.stdout) == ["code-map"], str(ran(r_tamp.stdout)))
check("tamper code-map: summary skips after repair to attested bytes", ran(r_post.stdout) == [], str(ran(r_post.stdout)))
print(f"  tamper code-map: run={ran(r_tamp.stdout)}  post-repair run={ran(r_post.stdout)}")

e("reset")
e("attest")
(WORKSPACE / "generated" / "map-summary.txt").write_bytes(b"# tampered\n")
r_s = e("attest")
check("tamper summary: only map-summary reruns", ran(r_s.stdout) == ["map-summary"], str(ran(r_s.stdout)))
print(f"  tamper summary: run={ran(r_s.stdout)}")


# --- Scenario 7 -------------------------------------------------------
print("[7] Version change reruns owner; downstream skips when input bytes unchanged")
e("reset")
e("attest")
entries = cache()
for entry in entries:
    if entry["name"] == "source-digest":
        entry["version"] = 0
ATTESTATIONS.write_text(json.dumps(entries, indent=2))
r = e("attest")

check("source-digest reruns on version miss", ran(r.stdout) == ["source-digest"], str(ran(r.stdout)))
check("code-map skips (unchanged)", "code-map" in skipped(r.stdout))
check("map-summary skips (downstream bytes unchanged)", "map-summary" in skipped(r.stdout))
print(f"  ran={ran(r.stdout)}  skipped={skipped(r.stdout)}")


# --- Scenario 8 -------------------------------------------------------
print("[8] Controlled failure leaves no attestation; workspace discarded before continuing")
e("reset")
(WORKSPACE / "generated").mkdir()
(WORKSPACE / "generated" / "code-map.txt").mkdir()
n0 = len(cache())
r_fail = e("attest", ok=(1,))
n1 = len(cache())

check("engine exits 1", r_fail.returncode == 1, f"rc={r_fail.returncode}")
check("FAIL in output", "FAIL" in r_fail.stdout)
check("no attestation added", n0 == n1, f"{n0}=={n1}")
print(f"  fail output: {r_fail.stdout.strip()}")

e("reset")
r_rec = e("attest")
check("recovery: all three run after discard", ran(r_rec.stdout) == GENS, str(ran(r_rec.stdout)))
print(f"  recovery ran={ran(r_rec.stdout)}")


# --- Summary ----------------------------------------------------------
print()
print("=" * 48)
if _fails == 0:
    print("all checks passed")
else:
    print(f"{_fails} check(s) failed")
    sys.exit(1)
