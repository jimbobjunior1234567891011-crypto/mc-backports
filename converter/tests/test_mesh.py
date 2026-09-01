"""Cross-check mesh.py against bake.py.

bake.quads_of_element is the vertex/uv mapping Minecraft uses (mirrored from deepslate)
and is already verified by test_bake.py. For every model whose rotations are simple
enough for that path to handle, the quad soup mesh.py emits must be the same geometry.
"""
import glob, json, os, sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bake import quads_of_element
from mesh import model_to_mesh

SRC = sys.argv[1]
TOL = 1e-3

checked = skipped = 0
failures = []

for path in glob.glob(os.path.join(SRC, "assets/minecraft/models/**/*.json"), recursive=True):
    try:
        model = json.load(open(path, encoding="utf-8-sig"))
    except Exception:
        continue
    elements = model.get("elements")
    if not elements:
        continue

    expected = []
    ok = True
    for el in elements:
        quads = quads_of_element(el)
        if quads is None:                          # multi-axis: bake.py cannot do it
            ok = False
            break
        for _d, (tex, pairs, cull) in quads.items():
            expected.append((tex, cull, pairs))
    if not ok:
        skipped += 1
        continue

    got = []
    for quad in model_to_mesh(model):
        v = quad["v"]
        pairs = [((v[i * 5], v[i * 5 + 1], v[i * 5 + 2]), (v[i * 5 + 3], v[i * 5 + 4]))
                 for i in range(4)]
        got.append((quad["texture"], quad.get("cullface"), pairs))

    checked += 1
    if len(expected) != len(got):
        failures.append((path, "quad count %d vs %d" % (len(expected), len(got))))
        continue
    for (tex1, cull1, p1), (tex2, cull2, p2) in zip(expected, got):
        if tex1 != tex2 or cull1 != cull2:
            failures.append((path, "texture/cullface mismatch"))
            break
        bad = False
        for (pos1, uv1), (pos2, uv2) in zip(p1, p2):
            if any(abs(a - b) > TOL for a, b in zip(pos1, pos2)) or \
               any(abs(a - b) > TOL for a, b in zip(uv1, uv2)):
                bad = True
                break
        if bad:
            failures.append((path, "vertex mismatch"))
            break

print("models cross-checked :", checked)
print("skipped (multi-axis) :", skipped)
print("MISMATCHES           :", len(failures))
for path, why in failures[:10]:
    print("   ", os.path.relpath(path, SRC), "-", why)
