"""Turn a 1.21.4+/1.21.11 model into a freerot:mesh quad soup.

Element rotations are applied here, in Python, exactly the way the game does it:

  * single axis  -> Matrix4f.rotation(angle, axis)
  * multiple axes-> Matrix4f.rotationZYX(z, y, x), i.e. X first, then Y, then Z
    (read straight out of the 1.21.11 client jar, class hqd$a)
  * rescale      -> for each axis, 1 / max(|component|) of that axis transformed by the
    rotation, applied before the rotation (M = R * S). For a 45 degree single-axis
    rotation this reproduces the familiar sqrt(2).

The result only has to be uploaded by the mod, so the game never sees a rotation it
would reject.
"""
import math

from bake import FACE_POS, FACE_UV, FACE_ROTATIONS


def _matmul(a, b):
    return [[sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)] for i in range(3)]


def _rot_matrix(axis, deg):
    a = math.radians(deg)
    c, s = math.cos(a), math.sin(a)
    if axis == "x":
        return [[1, 0, 0], [0, c, -s], [0, s, c]]
    if axis == "y":
        return [[c, 0, s], [0, 1, 0], [-s, 0, c]]
    return [[c, -s, 0], [s, c, 0], [0, 0, 1]]


def _apply(m, p):
    return tuple(sum(m[i][j] * p[j] for j in range(3)) for i in range(3))


def rotation_matrix(rot):
    """Full 3x3 matrix for an element rotation object, rescale included."""
    if "axis" in rot and "angle" in rot:
        m = _rot_matrix(rot["axis"], float(rot["angle"]))
    else:
        rx = _rot_matrix("x", float(rot.get("x", 0)))
        ry = _rot_matrix("y", float(rot.get("y", 0)))
        rz = _rot_matrix("z", float(rot.get("z", 0)))
        m = _matmul(rz, _matmul(ry, rx))          # X, then Y, then Z
    if rot.get("rescale"):
        scale = []
        for i in range(3):
            e = [0.0, 0.0, 0.0]
            e[i] = 1.0
            d = _apply(m, e)
            biggest = max(abs(d[0]), abs(d[1]), abs(d[2]))
            scale.append(1.0 / biggest if biggest > 1e-9 else 1.0)
        m = [[m[i][j] * scale[j] for j in range(3)] for i in range(3)]
    return m


def model_to_mesh(model):
    """[{texture, cullface, tintindex, shade, v:[20 floats]}] for every face."""
    quads = []
    for el in model.get("elements", []) or []:
        x0, y0, z0 = el["from"]
        x1, y1, z1 = el["to"]
        rot = el.get("rotation")
        matrix = origin = None
        if rot and (abs(float(rot.get("angle", 0))) > 1e-9
                    or any(abs(float(rot.get(k, 0))) > 1e-9 for k in "xyz")):
            matrix = rotation_matrix(rot)
            origin = tuple(rot.get("origin", [8, 8, 8]))
        shade = bool(el.get("shade", True))
        for d, face in (el.get("faces") or {}).items():
            if d not in FACE_POS or not face.get("texture"):
                continue
            pos = FACE_POS[d](x0, y0, z0, x1, y1, z1)
            if matrix:
                pos = [tuple(round(c + origin[i], 5) for i, c in
                             enumerate(_apply(matrix, tuple(p[j] - origin[j] for j in range(3)))))
                       for p in pos]
            uv = face.get("uv") or FACE_UV[d](x0, y0, z0, x1, y1, z1)
            r = FACE_ROTATIONS[int(face.get("rotation", 0)) % 360]
            uvs = [(uv[r[0]], uv[r[1]]), (uv[r[2]], uv[r[3]]),
                   (uv[r[4]], uv[r[5]]), (uv[r[6]], uv[r[7]])]
            flat = []
            for (px, py, pz), (u, v) in zip(pos, uvs):
                flat += [round(float(px), 5), round(float(py), 5), round(float(pz), 5),
                         round(float(u), 5), round(float(v), 5)]
            quad = {"texture": face["texture"], "v": flat}
            if face.get("cullface"):
                quad["cullface"] = face["cullface"]
            if face.get("tintindex", -1) != -1:
                quad["tintindex"] = face["tintindex"]
            if not shade:
                quad["shade"] = False
            quads.append(quad)
    return quads
