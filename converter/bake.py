"""Bake 90-degree multiples out of element rotations so 1.21.1 can load the model.

1.21.1 only accepts a single-axis element rotation of -45/-22.5/0/22.5/45 degrees. An
angle like -90 or 135 is therefore rejected outright - but a rotation by a multiple of 90
maps an axis-aligned box to another axis-aligned box, so it can be applied to the
element's own coordinates and removed from the rotation field, leaving a residual in
range. This is exact, not an approximation.

Face directions, cullfaces and texture orientation all have to move with the geometry.
Rather than deriving the texture remap by hand, every candidate face rotation is tested
against the quads the original element produces, using the same uv/vertex mapping
Minecraft uses (mirrored from deepslate's BlockModel, which reimplements FaceBakery).
A model is only rewritten when every face reproduces its original quad exactly.
"""
import math

LEGAL = (-45.0, -22.5, 0.0, 22.5, 45.0)
SQRT2 = 1.41421356237

# vertex positions per face, as (corner selector) triples over (x0,y0,z0,x1,y1,z1)
FACE_POS = {
    "up":    lambda x0, y0, z0, x1, y1, z1: [(x0, y1, z1), (x1, y1, z1), (x1, y1, z0), (x0, y1, z0)],
    "down":  lambda x0, y0, z0, x1, y1, z1: [(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)],
    "south": lambda x0, y0, z0, x1, y1, z1: [(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)],
    "north": lambda x0, y0, z0, x1, y1, z1: [(x1, y0, z0), (x0, y0, z0), (x0, y1, z0), (x1, y1, z0)],
    "east":  lambda x0, y0, z0, x1, y1, z1: [(x1, y0, z1), (x1, y0, z0), (x1, y1, z0), (x1, y1, z1)],
    "west":  lambda x0, y0, z0, x1, y1, z1: [(x0, y0, z0), (x0, y0, z1), (x0, y1, z1), (x0, y1, z0)],
}

# default uv rect per face when the face omits "uv"
FACE_UV = {
    "up":    lambda x0, y0, z0, x1, y1, z1: [x0, 16 - z1, x1, 16 - z0],
    "down":  lambda x0, y0, z0, x1, y1, z1: [16 - z1, 16 - x1, 16 - z0, 16 - x0],
    "south": lambda x0, y0, z0, x1, y1, z1: [x0, 16 - y1, x1, 16 - y0],
    "north": lambda x0, y0, z0, x1, y1, z1: [16 - x1, 16 - y1, 16 - x0, 16 - y0],
    "east":  lambda x0, y0, z0, x1, y1, z1: [16 - z1, 16 - y1, 16 - z0, 16 - y0],
    "west":  lambda x0, y0, z0, x1, y1, z1: [z0, 16 - y1, z1, 16 - y0],
}

FACE_ROTATIONS = {
    0:   [0, 3, 2, 3, 2, 1, 0, 1],
    90:  [2, 3, 2, 1, 0, 1, 0, 3],
    180: [2, 1, 0, 1, 0, 3, 2, 3],
    270: [0, 1, 0, 3, 2, 3, 2, 1],
}

NORMALS = {"east": (1, 0, 0), "west": (-1, 0, 0), "up": (0, 1, 0),
           "down": (0, -1, 0), "south": (0, 0, 1), "north": (0, 0, -1)}

RESCALE = {"x": (1.0, SQRT2, SQRT2), "y": (SQRT2, 1.0, SQRT2), "z": (SQRT2, SQRT2, 1.0)}


def rot_axis(p, axis, deg):
    """Right-handed rotation of point p about the given axis by deg degrees."""
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    x, y, z = p
    if axis == "x":
        return (x, y * c - z * s, y * s + z * c)
    if axis == "y":
        return (x * c + z * s, y, -x * s + z * c)
    return (x * c - y * s, x * s + y * c, z)


def element_rotation(el):
    """Return (axis, angle) for either the modern per-axis form or the classic form."""
    r = el.get("rotation")
    if not r:
        return None, 0.0, None, False
    if "axis" in r and "angle" in r:
        axes = [r["axis"]] if abs(float(r["angle"])) > 1e-9 else []
        angle = float(r["angle"])
        axis = r["axis"]
    else:
        axes = [k for k in "xyz" if abs(float(r.get(k, 0))) > 1e-9]
        if len(axes) > 1:
            return "MULTI", 0.0, None, False
        axis = axes[0] if axes else "y"
        angle = float(r.get(axis, 0))
    return axis, angle, tuple(r.get("origin", [8, 8, 8])), bool(r.get("rescale"))


def apply_element_transform(points, axis, angle, origin, rescale):
    out = []
    for p in points:
        q = tuple(p[i] - origin[i] for i in range(3))
        if rescale:
            sx, sy, sz = RESCALE[axis]
            q = (q[0] * sx, q[1] * sy, q[2] * sz)
        q = rot_axis(q, axis, angle)
        out.append(tuple(round(q[i] + origin[i], 6) for i in range(3)))
    return out


def quads_of_element(el):
    """{face_dir: (texture, [(pos, uv) x4], cullface)} with the element rotation applied."""
    x0, y0, z0 = el["from"]
    x1, y1, z1 = el["to"]
    axis, angle, origin, rescale = element_rotation(el)
    if axis == "MULTI":
        return None
    out = {}
    for d, face in (el.get("faces") or {}).items():
        if d not in FACE_POS:
            continue
        pos = FACE_POS[d](x0, y0, z0, x1, y1, z1)
        if angle:
            pos = apply_element_transform(pos, axis, angle, origin, rescale)
        else:
            pos = [tuple(round(c, 6) for c in p) for p in pos]
        uv = face.get("uv") or FACE_UV[d](x0, y0, z0, x1, y1, z1)
        r = FACE_ROTATIONS[int(face.get("rotation", 0)) % 360]
        uvs = [(uv[r[0]], uv[r[1]]), (uv[r[2]], uv[r[3]]),
               (uv[r[4]], uv[r[5]]), (uv[r[6]], uv[r[7]])]
        out[d] = (face.get("texture"), list(zip(pos, uvs)), face.get("cullface"))
    return out


def _dir_after(d, axis, k):
    n = NORMALS[d]
    rotated = rot_axis(n, axis, 90.0 * k)
    best, bestdot = None, -2
    for name, vec in NORMALS.items():
        dot = sum(rotated[i] * vec[i] for i in range(3))
        if dot > bestdot:
            best, bestdot = name, dot
    return best


def _same(q1, q2, tol=1e-4):
    """Same textured quad: same 4 (position, uv) pairs, order-insensitive."""
    if len(q1) != len(q2):
        return False
    remaining = list(q2)
    for p, uv in q1:
        for i, (p2, uv2) in enumerate(remaining):
            if (all(abs(p[j] - p2[j]) < tol for j in range(3))
                    and abs(uv[0] - uv2[0]) < tol and abs(uv[1] - uv2[1]) < tol):
                remaining.pop(i)
                break
        else:
            return False
    return True


def bake_element(el):
    """Return a rewritten element with a 1.21.1-legal rotation, or None."""
    axis, angle, origin, rescale = element_rotation(el)
    if axis == "MULTI":
        return None
    if not angle or any(abs(angle - L) < 1e-9 for L in LEGAL):
        return None if not angle else el          # already legal
    k = int(round(angle / 90.0))
    residual = round(angle - 90.0 * k, 6)
    if not any(abs(residual - L) < 1e-6 for L in LEGAL):
        return None                               # arbitrary angle, not our business
    if k == 0:
        return None

    original = quads_of_element(el)
    if original is None:
        return None

    # rotate the box itself by 90*k about the rotation origin
    x0, y0, z0 = el["from"]
    x1, y1, z1 = el["to"]
    corners = [(x, y, z) for x in (x0, x1) for y in (y0, y1) for z in (z0, z1)]
    moved = [rot_axis(tuple(c[i] - origin[i] for i in range(3)), axis, 90.0 * k) for c in corners]
    moved = [tuple(round(m[i] + origin[i], 6) for i in range(3)) for m in moved]
    new_from = [min(p[i] for p in moved) for i in range(3)]
    new_to = [max(p[i] for p in moved) for i in range(3)]

    new_el = {k2: v for k2, v in el.items() if k2 not in ("from", "to", "faces", "rotation")}
    new_el["from"] = [round(c, 5) for c in new_from]
    new_el["to"] = [round(c, 5) for c in new_to]
    if residual:
        new_el["rotation"] = {"angle": residual, "axis": axis, "origin": list(origin)}
        if rescale:
            new_el["rotation"]["rescale"] = True
    new_faces = {}

    for d, face in (el.get("faces") or {}).items():
        if d not in FACE_POS:
            continue
        nd = _dir_after(d, axis, k)
        # The baked box is the original rotated by 90*k and the residual rotation makes up
        # the difference, so the quad to reproduce is simply the original one.
        _tex, target, _cull = original[d]
        uv_rect = face.get("uv") or FACE_UV[d](x0, y0, z0, x1, y1, z1)
        chosen = None
        for r_deg in (0, 90, 180, 270):
            trial = dict(face)
            trial["uv"] = [round(c, 5) for c in uv_rect]
            trial["rotation"] = r_deg
            if face.get("cullface"):
                trial["cullface"] = _dir_after(face["cullface"], axis, k)
            probe = dict(new_el)
            probe["faces"] = {nd: trial}
            got = quads_of_element(probe)
            if got and _same(target, got[nd][1]):
                chosen = trial
                break
        if chosen is None:
            return None                            # could not reproduce it, do not guess
        if chosen["rotation"] == 0:
            chosen.pop("rotation")
        new_faces[nd] = chosen

    new_el["faces"] = new_faces
    return new_el


def bake_model(model):
    """Rewrite every bakeable element. Returns (model, changed) or (None, False) if the
    model still would not load on 1.21.1."""
    els = model.get("elements")
    if not els:
        return model, False
    out, changed = [], False
    for el in els:
        axis, angle, _origin, _rescale = element_rotation(el)
        if axis == "MULTI":
            return None, False
        if angle and not any(abs(angle - L) < 1e-9 for L in LEGAL):
            baked = bake_element(el)
            if baked is None:
                return None, False
            out.append(baked)
            changed = True
        else:
            # normalise the modern {"x": .., "y": ..} form to the classic one
            r = el.get("rotation")
            if r and "axis" not in r and angle:
                el = dict(el)
                el["rotation"] = {"angle": angle, "axis": axis,
                                  "origin": list(r.get("origin", [8, 8, 8]))}
                if r.get("rescale"):
                    el["rotation"]["rescale"] = True
                changed = True
            elif r and "axis" not in r:
                el = dict(el)
                el.pop("rotation")
                changed = True
            out.append(el)
    model = dict(model)
    model["elements"] = out
    return model, changed
