"""Census of illegal element rotations across the pack: which axes, which angles, and
how many decompose exactly into (multiple of 90) + (legal residual)."""
import collections, glob, json, os, sys

SRC = sys.argv[1]
LEGAL = {-45.0, -22.5, 0.0, 22.5, 45.0}

single = collections.Counter()
multi = collections.Counter()
exact = approx = 0

for f in glob.glob(os.path.join(SRC, "assets/minecraft/models/**/*.json"), recursive=True):
    try:
        d = json.load(open(f, encoding="utf-8-sig"))
    except Exception:
        continue
    for el in d.get("elements", []) or []:
        r = el.get("rotation")
        if not r:
            continue
        if "angle" in r and "axis" in r:            # already-legal vanilla form
            axes = [r["axis"]] if abs(float(r["angle"])) > 1e-9 else []
            vals = {r["axis"]: float(r["angle"])}
        else:
            axes = [k for k in "xyz" if abs(float(r.get(k, 0))) > 1e-9]
            vals = {k: float(r.get(k, 0)) for k in axes}
        if len(axes) > 1:
            multi[tuple(sorted(axes))] += 1
            continue
        if not axes:
            continue
        a = vals[axes[0]]
        if a in LEGAL:
            continue
        single[(axes[0], a)] += 1
        # decompose a = 90*k + residual, residual in [-45, 45]
        k = round(a / 90.0)
        residual = a - 90.0 * k
        if abs(residual) < 1e-6 or abs(abs(residual) - 22.5) < 1e-6 or abs(abs(residual) - 45.0) < 1e-6:
            exact += 1
        else:
            approx += 1

print("single-axis illegal rotations:", sum(single.values()),
      "| exactly recoverable via 90-deg bake:", exact, "| would need snapping:", approx)
for (ax, a), n in single.most_common(20):
    k = round(a / 90.0)
    print("   axis=%s angle=%-10s -> bake %4d deg + residual %-7s  x%d" % (ax, a, 90 * k, round(a - 90 * k, 4), n))
print()
print("multi-axis rotations by axis set:", dict(multi))
