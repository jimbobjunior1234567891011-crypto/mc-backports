"""Independent check of bake.py: a baked model must emit exactly the same textured quads
as the original, and must be loadable by 1.21.1 rules."""
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bake import LEGAL, bake_model, quads_of_element, element_rotation, _same, _dir_after

SRC = sys.argv[1]


def legal_model(m):
    for el in m.get("elements", []) or []:
        r = el.get("rotation")
        if not r:
            continue
        if "axis" not in r or "angle" not in r:
            return False
        if r["axis"] not in ("x", "y", "z"):
            return False
        if not any(abs(float(r["angle"]) - L) < 1e-9 for L in LEGAL):
            return False
    return True


def all_quads(model):
    out = []
    for el in model.get("elements", []) or []:
        q = quads_of_element(el)
        if q is None:
            return None
        for d, (tex, pairs, cull) in q.items():
            out.append((tex, pairs, cull))
    return out


baked_ok = baked_bad = untouched = 0
failures = []
for f in glob.glob(os.path.join(SRC, "assets/minecraft/models/**/*.json"), recursive=True):
    try:
        m = json.load(open(f, encoding="utf-8-sig"))
    except Exception:
        continue
    if not m.get("elements"):
        continue
    if legal_model(m):
        untouched += 1
        continue
    new, changed = bake_model(m)
    if new is None:
        baked_bad += 1
        continue
    if not legal_model(new):
        failures.append((f, "still illegal after bake"))
        continue
    before, after = all_quads(m), all_quads(new)
    if before is None or after is None:
        failures.append((f, "unrenderable"))
        continue
    if len(before) != len(after):
        failures.append((f, "quad count %d -> %d" % (len(before), len(after))))
        continue
    rest = list(after)
    bad = False
    for tex, pairs, cull in before:
        for i, (tex2, pairs2, cull2) in enumerate(rest):
            if tex == tex2 and _same(pairs, pairs2):
                rest.pop(i)
                break
        else:
            bad = True
            break
    if bad:
        failures.append((f, "quad mismatch"))
    else:
        baked_ok += 1

print("models already legal      :", untouched)
print("models baked + verified   :", baked_ok)
print("models bake cannot fix    :", baked_bad, "(multi-axis or arbitrary angle)")
print("VERIFICATION FAILURES     :", len(failures))
for f, why in failures[:15]:
    print("   ", os.path.relpath(f, SRC), "-", why)
