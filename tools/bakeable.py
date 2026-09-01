"""Which blocked items become fully 1.21.1-legal after baking 90-degree multiples out of
single-axis rotations?"""
import json, os, sys

SRC = sys.argv[1]
items = sys.argv[2].split(",")
LEGAL = {-45.0, -22.5, 0.0, 22.5, 45.0}


def load(p):
    return json.load(open(p, encoding="utf-8-sig"))


def mp(ref):
    return os.path.join(SRC, "assets/minecraft/models", ref.replace("minecraft:", "") + ".json")


def refs(node, out):
    if isinstance(node, dict):
        if node.get("type") == "minecraft:model" and isinstance(node.get("model"), str):
            out.add(node["model"].replace("minecraft:", ""))
        for v in node.values():
            refs(v, out)
    elif isinstance(node, list):
        for v in node:
            refs(v, out)


def closure(ref, seen):
    ref = ref.replace("minecraft:", "")
    if ref in seen or not os.path.exists(mp(ref)):
        return
    seen.add(ref)
    par = load(mp(ref)).get("parent")
    if isinstance(par, str):
        closure(par, seen)


def classify(ref):
    """-> 'ok' | 'bakeable' | 'multi' | 'odd-angle'"""
    d = load(mp(ref))
    verdict = "ok"
    for el in d.get("elements", []) or []:
        r = el.get("rotation")
        if not r:
            continue
        axes = [k for k in "xyz" if abs(float(r.get(k, 0))) > 1e-9]
        if len(axes) > 1:
            return "multi"
        if not axes:
            continue
        a = float(r[axes[0]])
        if a in LEGAL:
            continue
        residual = a - 90.0 * round(a / 90.0)
        if any(abs(residual - L) < 1e-6 for L in LEGAL):
            verdict = "bakeable" if verdict != "odd-angle" else verdict
        else:
            verdict = "odd-angle"
    return verdict


bakeable, multi, odd = [], [], []
for item in items:
    f = os.path.join(SRC, "assets/minecraft/items", item + ".json")
    if not os.path.exists(f):
        continue
    s = set()
    refs(load(f), s)
    models = set()
    for r in s:
        closure(r, models)
    verdicts = {m: classify(m) for m in models}
    vals = set(verdicts.values())
    if "multi" in vals:
        multi.append(item)
    elif "odd-angle" in vals:
        odd.append((item, [m for m, v in verdicts.items() if v == "odd-angle"]))
    elif "bakeable" in vals:
        bakeable.append(item)

print("FULLY RECOVERED BY BAKE (%d): %s" % (len(bakeable), " ".join(bakeable)))
print()
print("STILL BLOCKED - arbitrary angles (%d):" % len(odd))
for i, ms in odd:
    print("   %-28s %s" % (i, ",".join(sorted(ms)[:3])))
print()
print("STILL BLOCKED - multi-axis (%d): %s" % (len(multi), " ".join(multi)))
