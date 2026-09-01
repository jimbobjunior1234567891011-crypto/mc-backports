"""For each blocked item, report why: which models, and whether the offending rotations
are single-axis (snappable to 22.5 with small visual error) or multi-axis (not
expressible in 1.21.1 at all)."""
import json, os, sys

SRC = sys.argv[1]
items = sys.argv[2].split(",")
LEGAL = [-45.0, -22.5, 0.0, 22.5, 45.0]


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


def audit(ref):
    """returns (n_elements, n_multi_axis, [(angle, nearest_legal, delta)])"""
    d = load(mp(ref))
    multi, offs = 0, []
    els = d.get("elements", []) or []
    for el in els:
        r = el.get("rotation")
        if not r:
            continue
        ax = [k for k in "xyz" if abs(float(r.get(k, 0))) > 1e-9]
        if len(ax) > 1:
            multi += 1
        elif ax:
            a = float(r[ax[0]])
            if a not in LEGAL:
                near = min(LEGAL, key=lambda x: abs(x - a))
                offs.append((a, near, abs(near - a)))
    return len(els), multi, offs


snappable, hard = [], []
for item in items:
    f = os.path.join(SRC, "assets/minecraft/items", item + ".json")
    if not os.path.exists(f):
        continue
    s = set()
    refs(load(f), s)
    models = []
    stack = [m for m in s if os.path.exists(mp(m))]
    while stack:                                   # follow parents too
        m = stack.pop()
        if m in models:
            continue
        models.append(m)
        par = load(mp(m)).get("parent")
        if isinstance(par, str) and os.path.exists(mp(par)):
            stack.append(par.replace("minecraft:", ""))
    tot_multi, worst, n_off = 0, 0.0, 0
    for m in models:
        _n, multi, offs = audit(m)
        tot_multi += multi
        n_off += len(offs)
        for _a, _near, delta in offs:
            worst = max(worst, delta)
    if tot_multi:
        hard.append((item, tot_multi, n_off))
    else:
        snappable.append((item, n_off, round(worst, 2)))

print("SNAPPABLE (single-axis only, angle can be rounded to 22.5 steps):", len(snappable))
for i in snappable:
    print("   %-28s off-angle elements=%-4d worst error=%s deg" % i)
print()
print("HARD (multi-axis rotation, impossible in 1.21.1):", len(hard))
for i in hard:
    print("   %-28s multi-axis elements=%-4d off-angle elements=%d" % i)
