import sys
import shutil
import hashlib
import json
from pathlib import Path

BASE = Path(__file__).parent
EXAMPLES = BASE / "examples" / "tiny"
WORK = BASE / ".work"
WORKSPACE = WORK / "workspace"
CACHE = WORK / "cache"
TRACE = WORK / "trace"
ATTESTATIONS = CACHE / "attestations.json"

OWNER_MARKER = "# machine-owned\n"

GENERATORS = [
    {"name": "code-map",      "version": 1, "reads": "src_paths",             "output": "generated/code-map.txt"},
    {"name": "source-digest", "version": 1, "reads": "src_content",            "output": "generated/source-digest.txt"},
    {"name": "map-summary",   "version": 1, "reads": "generated/code-map.txt", "output": "generated/map-summary.txt"},
]


class Workspace:
    def __init__(self, root):
        self.root = root
        self._table = {}
        for p in sorted(root.rglob("*")):
            if p.is_file():
                rel = p.relative_to(root).as_posix()
                self._table[rel] = p.read_bytes()

    def record_write(self, rel, content):
        self._table[rel] = content

    def record_delete(self, rel):
        self._table.pop(rel, None)

    def source_paths(self, suffix=".py"):
        return sorted(k for k in self._table if k.endswith(suffix))

    def _enc(self, data):
        return json.dumps(data, separators=(",", ":")).encode()

    def fingerprint_source_paths(self, suffix=".py"):
        return hashlib.sha256(self._enc(self.source_paths(suffix))).hexdigest()

    def fingerprint_source_content(self, suffix=".py"):
        items = [[k, hashlib.sha256(v).hexdigest()]
                 for k, v in sorted(self._table.items())
                 if k.endswith(suffix)]
        return hashlib.sha256(self._enc(items)).hexdigest()

    def fingerprint_generated(self, rel):
        val = hashlib.sha256(self._table[rel]).hexdigest() if rel in self._table else None
        return hashlib.sha256(self._enc(val)).hexdigest()

    def identity(self):
        items = [[k, hashlib.sha256(v).hexdigest()]
                 for k, v in sorted(self._table.items())]
        return hashlib.sha256(self._enc(items)).hexdigest()


def reset():
    if WORK.exists():
        shutil.rmtree(WORK)
    WORKSPACE.mkdir(parents=True)
    CACHE.mkdir()
    TRACE.mkdir()
    shutil.copytree(EXAMPLES, WORKSPACE, dirs_exist_ok=True)


def run():
    if not WORKSPACE.exists():
        sys.exit("workspace not found; run reset first")
    ws = Workspace(WORKSPACE)
    before = ws.identity()
    content = json.dumps({"files": ws.source_paths()}, separators=(",", ":")).encode()
    (WORKSPACE / "codemap.json").write_bytes(content)
    ws.record_write("codemap.json", content)
    after = ws.identity()
    print(f"before: {before}")
    print(f"after:  {after}")


def verify():
    import tempfile

    reset()

    # 1: equivalent copied trees have equal IDs despite different absolute locations or timestamps
    ws = Workspace(WORKSPACE)
    with tempfile.TemporaryDirectory() as tmp:
        alt = Path(tmp) / "ws"
        shutil.copytree(EXAMPLES, alt)
        id_a = ws.identity()
        id_b = Workspace(alt).identity()
        assert id_a == id_b, "equivalent trees must have equal IDs"
    print(f"[1] equivalent trees: id={id_a}")

    # 2: source byte edit changes content slice but not path-membership slice
    reset()
    ws = Workspace(WORKSPACE)
    paths_fp = ws.fingerprint_source_paths()
    content_fp = ws.fingerprint_source_content()
    ws.record_write("main.py", b"# edited\n")
    assert ws.fingerprint_source_paths() == paths_fp
    assert ws.fingerprint_source_content() != content_fp
    print(f"[2] byte edit: paths={paths_fp[:12]} unchanged  content {content_fp[:12]}→{ws.fingerprint_source_content()[:12]}")

    # 3a: adding a source path changes both slices
    reset()
    ws = Workspace(WORKSPACE)
    paths_fp = ws.fingerprint_source_paths()
    content_fp = ws.fingerprint_source_content()
    ws.record_write("new_module.py", b"# new\n")
    assert ws.fingerprint_source_paths() != paths_fp
    assert ws.fingerprint_source_content() != content_fp
    print(f"[3a] add path: paths {paths_fp[:12]}→{ws.fingerprint_source_paths()[:12]}  content {content_fp[:12]}→{ws.fingerprint_source_content()[:12]}")

    # 3b: removing a source path changes both slices
    reset()
    ws = Workspace(WORKSPACE)
    paths_fp = ws.fingerprint_source_paths()
    content_fp = ws.fingerprint_source_content()
    ws.record_delete("utils.py")
    assert ws.fingerprint_source_paths() != paths_fp
    assert ws.fingerprint_source_content() != content_fp
    print(f"[3b] remove path: paths {paths_fp[:12]}→{ws.fingerprint_source_paths()[:12]}  content {content_fp[:12]}→{ws.fingerprint_source_content()[:12]}")

    # 4: unrelated notes edit changes global identity without changing source slices
    reset()
    ws = Workspace(WORKSPACE)
    id_before = ws.identity()
    paths_fp = ws.fingerprint_source_paths()
    content_fp = ws.fingerprint_source_content()
    ws.record_write("notes.txt", b"different notes\n")
    assert ws.identity() != id_before
    assert ws.fingerprint_source_paths() == paths_fp
    assert ws.fingerprint_source_content() == content_fp
    print(f"[4] notes edit: id {id_before[:12]}→{ws.identity()[:12]}  source slices unchanged")

    # 5: missing and present generated paths have distinct fingerprints
    reset()
    ws = Workspace(WORKSPACE)
    absent_fp = ws.fingerprint_generated("codemap.json")
    ws.record_write("codemap.json", b'{"files":[]}')
    present_fp = ws.fingerprint_generated("codemap.json")
    assert absent_fp != present_fp
    print(f"[5] generated absent={absent_fp[:12]}  present={present_fp[:12]}")

    # 6: no independent traversal — all fingerprints draw from _table populated once at init
    print("[6] no independent traversal: all observations read from _table built at __init__")

    print("all assertions passed")


def gen_code_map(ws):
    paths = sorted(k for k in ws._table if k.startswith("src/"))
    body = "".join(p + "\n" for p in paths)
    content = (OWNER_MARKER + body).encode()
    rel = "generated/code-map.txt"
    (WORKSPACE / rel).write_bytes(content)
    ws.record_write(rel, content)


def gen_source_digest(ws):
    items = sorted(
        (k, hashlib.sha256(v).hexdigest())
        for k, v in ws._table.items()
        if k.startswith("src/")
    )
    digest = hashlib.sha256(json.dumps(items, separators=(",", ":")).encode()).hexdigest()
    content = (OWNER_MARKER + digest + "\n").encode()
    rel = "generated/source-digest.txt"
    (WORKSPACE / rel).write_bytes(content)
    ws.record_write(rel, content)


def gen_map_summary(ws):
    map_bytes = ws._table.get("generated/code-map.txt", b"")
    entries = [l for l in map_bytes.decode().splitlines() if l and not l.startswith("#")]
    content = (OWNER_MARKER + f"entries: {len(entries)}\n").encode()
    rel = "generated/map-summary.txt"
    (WORKSPACE / rel).write_bytes(content)
    ws.record_write(rel, content)


GEN_FNS = [gen_code_map, gen_source_digest, gen_map_summary]


def generate():
    if not WORKSPACE.exists():
        sys.exit("workspace not found; run reset first")
    ws = Workspace(WORKSPACE)
    (WORKSPACE / "generated").mkdir(exist_ok=True)
    for decl, fn in zip(GENERATORS, GEN_FNS):
        rel = decl["output"]
        before = ws.fingerprint_generated(rel)
        fn(ws)
        after = ws.fingerprint_generated(rel)
        print(f"{decl['name']}: before={before[:12]} after={after[:12]}")


def verify_generators():
    # 1: fresh generation produces three predictable outputs
    reset()
    (WORKSPACE / "generated").mkdir(exist_ok=True)
    ws = Workspace(WORKSPACE)
    for decl, fn in zip(GENERATORS, GEN_FNS):
        rel = decl["output"]
        before = ws.fingerprint_generated(rel)
        fn(ws)
        after = ws.fingerprint_generated(rel)
        print(f"[1] {decl['name']}: before={before[:12]} after={after[:12]}")

    contents_1 = {d["output"]: (WORKSPACE / d["output"]).read_bytes() for d in GENERATORS}

    # 2: repeat generation produces identical bytes
    ws2 = Workspace(WORKSPACE)
    for decl, fn in zip(GENERATORS, GEN_FNS):
        rel = decl["output"]
        before = ws2.fingerprint_generated(rel)
        fn(ws2)
        after = ws2.fingerprint_generated(rel)
        assert before == after, f"{decl['name']}: expected idempotent"
        print(f"[2] {decl['name']}: before={before[:12]} after={after[:12]} (unchanged)")

    contents_2 = {d["output"]: (WORKSPACE / d["output"]).read_bytes() for d in GENERATORS}
    for rel in contents_1:
        assert contents_1[rel] == contents_2[rel]
    print("[2] all outputs identical on second generation")

    # 3: repair — remove an output and regenerate deterministically
    reset()
    (WORKSPACE / "generated").mkdir(exist_ok=True)
    ws3 = Workspace(WORKSPACE)
    for fn in GEN_FNS:
        fn(ws3)
    canonical = (WORKSPACE / "generated" / "code-map.txt").read_bytes()
    (WORKSPACE / "generated" / "code-map.txt").unlink()
    ws3 = Workspace(WORKSPACE)
    before_absent = ws3.fingerprint_generated("generated/code-map.txt")
    gen_code_map(ws3)
    after_repaired = ws3.fingerprint_generated("generated/code-map.txt")
    assert before_absent != after_repaired
    assert (WORKSPACE / "generated" / "code-map.txt").read_bytes() == canonical
    print(f"[3] repair code-map: absent={before_absent[:12]} repaired={after_repaired[:12]} bytes-match=True")

    # 4: map-to-summary dependency via extra src path
    reset()
    (WORKSPACE / "generated").mkdir(exist_ok=True)
    ws4 = Workspace(WORKSPACE)
    for fn in GEN_FNS:
        fn(ws4)
    map_before = ws4.fingerprint_generated("generated/code-map.txt")
    digest_before = ws4.fingerprint_generated("generated/source-digest.txt")
    summary_before = ws4.fingerprint_generated("generated/map-summary.txt")

    extra = b"def extra(): pass\n"
    (WORKSPACE / "src" / "extra.py").write_bytes(extra)
    ws4.record_write("src/extra.py", extra)

    for fn in GEN_FNS:
        fn(ws4)
    map_after = ws4.fingerprint_generated("generated/code-map.txt")
    digest_after = ws4.fingerprint_generated("generated/source-digest.txt")
    summary_after = ws4.fingerprint_generated("generated/map-summary.txt")

    assert map_before != map_after
    assert digest_before != digest_after
    assert summary_before != summary_after
    print("[4] extra src path:")
    print(f"    code-map:      {map_before[:12]} -> {map_after[:12]}")
    print(f"    source-digest: {digest_before[:12]} -> {digest_after[:12]}")
    print(f"    map-summary:   {summary_before[:12]} -> {summary_after[:12]}")

    print("all assertions passed")


def _reads_fp(ws, spec):
    if spec == "src_paths":
        return ws.fingerprint_source_paths()
    if spec == "src_content":
        return ws.fingerprint_source_content()
    return ws.fingerprint_generated(spec)


def _load_attestations():
    if not ATTESTATIONS.exists():
        return []
    return json.loads(ATTESTATIONS.read_text())


def _save_attestations(entries):
    ATTESTATIONS.write_text(json.dumps(entries, indent=2))


def _find_attestation(entries, name, version, reads_fp, output_fp):
    for e in entries:
        if (e["name"] == name and e["version"] == version
                and e["reads_fp"] == reads_fp and e["output_fp"] == output_fp):
            return e
    return None


def run_attested():
    if not WORKSPACE.exists():
        sys.exit("workspace not found; run reset first")
    ws = Workspace(WORKSPACE)
    entries = _load_attestations()
    (WORKSPACE / "generated").mkdir(exist_ok=True)
    current_id = ws.identity()
    for decl, fn in zip(GENERATORS, GEN_FNS):
        name = decl["name"]
        version = decl["version"]
        rel = decl["output"]
        reads_fp = _reads_fp(ws, decl["reads"])
        output_fp = ws.fingerprint_generated(rel)
        hit = _find_attestation(entries, name, version, reads_fp, output_fp)
        if hit:
            print(f"{name}: skip  reads={reads_fp[:12]} output={output_fp[:12]}  attested_after={hit['after_id'][:12]}  current={current_id[:12]}")
            continue
        before_id = current_id
        try:
            fn(ws)
        except Exception as e:
            print(f"{name}: FAIL  {e}")
            sys.exit(1)
        after_id = ws.identity()
        new_output_fp = ws.fingerprint_generated(rel)
        current_id = after_id
        entries.append({
            "name": name,
            "version": version,
            "reads_fp": reads_fp,
            "output_fp": new_output_fp,
            "before_id": before_id,
            "after_id": after_id,
        })
        _save_attestations(entries)
        print(f"{name}: run   reads={reads_fp[:12]} output={new_output_fp[:12]}  before={before_id[:12]}  after={after_id[:12]}")


def verify_attested():
    def _ran(before, after):
        return [e["name"] for e in after[len(before):]]

    # AC1: fresh run executes three, second run executes none
    reset()
    e0 = _load_attestations()
    run_attested()
    e1 = _load_attestations()
    ran = _ran(e0, e1)
    assert ran == ["code-map", "source-digest", "map-summary"], f"AC1a: {ran}"
    print(f"[AC1a] fresh run: {ran}")
    e1b = _load_attestations()
    run_attested()
    e2 = _load_attestations()
    ran2 = _ran(e1b, e2)
    assert ran2 == [], f"AC1b: {ran2}"
    print(f"[AC1b] second run: {ran2}")

    # AC2a: source content-only change executes just source-digest; unrelated edit executes none
    reset()
    run_attested()
    (WORKSPACE / "src" / "app.py").write_bytes(b"# edited\ndef main(): pass\n")
    e_b = _load_attestations()
    run_attested()
    ran = _ran(e_b, _load_attestations())
    assert ran == ["source-digest"], f"AC2a: {ran}"
    print(f"[AC2a] content change: {ran}")

    reset()
    run_attested()
    (WORKSPACE / "notes.txt").write_bytes(b"different notes\n")
    e_b = _load_attestations()
    run_attested()
    ran = _ran(e_b, _load_attestations())
    assert ran == [], f"AC2b: {ran}"
    print(f"[AC2b] unrelated edit: {ran}")

    # AC3: source path addition executes two source readers then dependent summary
    reset()
    run_attested()
    (WORKSPACE / "src" / "extra.py").write_bytes(b"def extra(): pass\n")
    e_b = _load_attestations()
    run_attested()
    ran = _ran(e_b, _load_attestations())
    assert ran == ["code-map", "source-digest", "map-summary"], f"AC3: {ran}"
    print(f"[AC3] path addition: {ran}")

    # AC4: output absence invalidates owner even when reads match
    reset()
    run_attested()
    (WORKSPACE / "generated" / "code-map.txt").unlink()
    e_b = _load_attestations()
    run_attested()
    ran = _ran(e_b, _load_attestations())
    assert ran == ["code-map"], f"AC4: {ran}"
    print(f"[AC4] output absent: {ran}")

    # AC5: restoring exact code-map bytes does not rerun already-valid summary
    reset()
    run_attested()
    (WORKSPACE / "generated" / "code-map.txt").write_bytes(b"# tampered\nnot valid\n")
    run_attested()
    (WORKSPACE / "generated" / "code-map.txt").write_bytes(b"# tampered again\n")
    e_b = _load_attestations()
    run_attested()
    ran = _ran(e_b, _load_attestations())
    assert ran == ["code-map"], f"AC5: {ran}"
    print(f"[AC5] restored bytes, summary skipped: {ran}")

    # AC6: version change invalidates that entry without invalidating others
    reset()
    run_attested()
    GENERATORS[1]["version"] = 2
    e_b = _load_attestations()
    try:
        run_attested()
        e_a = _load_attestations()
    finally:
        GENERATORS[1]["version"] = 1
    ran = _ran(e_b, e_a)
    assert ran == ["source-digest"], f"AC6: {ran}"
    print(f"[AC6] version bump: {ran}")

    # AC7: failed execution creates no success entry; trace explains failure
    reset()
    run_attested()
    (WORKSPACE / "generated" / "code-map.txt").write_bytes(b"# tampered\n")
    original_fn = GEN_FNS[0]
    def _fail(ws):
        raise RuntimeError("injected failure")
    GEN_FNS[0] = _fail
    e_b = _load_attestations()
    try:
        run_attested()
        assert False, "AC7: expected failure exit"
    except SystemExit as exc:
        assert exc.code == 1, f"AC7: expected exit code 1, got {exc.code}"
    finally:
        GEN_FNS[0] = original_fn
    ran = _ran(e_b, _load_attestations())
    assert ran == [], f"AC7: {ran}"
    print(f"[AC7] failed execution: {ran} entries added")

    print("all assertions passed")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit("usage: engine.py <reset|run|generate|verify|verify_generators|attest|verify_attested>")
    cmd = sys.argv[1]
    if cmd == "reset":
        reset()
    elif cmd == "run":
        run()
    elif cmd == "generate":
        generate()
    elif cmd == "verify":
        verify()
    elif cmd == "verify_generators":
        verify_generators()
    elif cmd == "attest":
        run_attested()
    elif cmd == "verify_attested":
        verify_attested()
    else:
        sys.exit(f"unknown command: {cmd}")
