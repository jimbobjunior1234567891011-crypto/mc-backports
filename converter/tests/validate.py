"""Validate a backported pack: reference resolution, 1.21.1 rotation rules, loader shapes.

Checks every model in the pack, following parents into the vanilla jar, and resolves
texture variables the way the game does before deciding a texture is missing.
"""
import json, os, sys, zipfile

PACK = sys.argv[1]
jar = zipfile.ZipFile(sys.argv[2])
JAR_NAMES = set(jar.namelist())
LEGAL = {-45.0, -22.5, 0.0, 22.5, 45.0}
CONTEXTS = {"none", "thirdperson_lefthand", "thirdperson_righthand", "firstperson_lefthand",
            "firstperson_righthand", "head", "gui", "ground", "fixed"}

errors, warnings = [], []
_models = {}


def get_model(ref):
    """Model json by ref, pack first then vanilla jar."""
    ref = ref.replace("minecraft:", "")
    if ref in _models:
        return _models[ref]
    if ref.startswith("builtin/"):                 # builtin/generated & co are not files
        _models[ref] = {}
        return {}
    local = os.path.join(PACK, "assets/minecraft/models", ref + ".json")
    data = None
    if os.path.exists(local):
        try:
            data = json.load(open(local, encoding="utf-8-sig"))
        except Exception as exc:
            errors.append("%s: unparseable JSON: %s" % (ref, exc))
    else:
        name = "assets/minecraft/models/%s.json" % ref
        if name in JAR_NAMES:
            data = json.loads(jar.read(name))
    _models[ref] = data
    return data


def texture_exists(path):
    path = path.replace("minecraft:", "")
    return (os.path.exists(os.path.join(PACK, "assets/minecraft/textures", path + ".png"))
            or "assets/minecraft/textures/%s.png" % path in JAR_NAMES)


def chain(ref, seen=None):
    """[model, parent, grandparent, ...] with cycle detection."""
    seen = seen or []
    out = []
    while ref is not None:
        ref = ref.replace("minecraft:", "")
        if ref in seen:
            errors.append("%s: parent cycle" % ref)
            break
        seen.append(ref)
        model = get_model(ref)
        if model is None:
            errors.append("%s: missing model" % ref)
            break
        out.append(model)
        ref = model.get("parent") if isinstance(model.get("parent"), str) else None
    return out


def resolve_texture(var, models, origin):
    """Follow #variable references up the parent chain like the game does."""
    seen = 0
    value = var
    while isinstance(value, str) and value.startswith("#") and seen < 8:
        key = value[1:]
        value = None
        for model in models:
            candidate = (model.get("textures") or {}).get(key)
            if candidate is not None:
                value = candidate
                break
        seen += 1
    if not isinstance(value, str):
        return                                     # template model, a child supplies it
    if not texture_exists(value):
        warnings.append("%s: missing texture %s" % (origin, value))


def check_inline(model, origin, parents):
    """A model json that may be a file, a separate_transforms sub-model, or a mesh."""
    parent_ref = model.get("parent")
    models = [model] + (chain(parent_ref) if isinstance(parent_ref, str) else [])
    if isinstance(parent_ref, str) and get_model(parent_ref) is None:
        errors.append("%s: missing parent %s" % (origin, parent_ref))

    loader = model.get("loader")
    if loader == "neoforge:separate_transforms":
        if not isinstance(model.get("base"), dict):
            errors.append("%s: separate_transforms without base" % origin)
        else:
            check_inline(model["base"], origin + "[base]", parents)
        for name, sub in (model.get("perspectives") or {}).items():
            if name not in CONTEXTS:
                errors.append("%s: unknown perspective %s" % (origin, name))
            check_inline(sub, "%s[%s]" % (origin, name), parents)
    elif loader == "freerot:mesh":
        quads = model.get("mesh")
        if not isinstance(quads, list) or not quads:
            errors.append("%s: freerot:mesh with no quads" % origin)
        else:
            for i, quad in enumerate(quads):
                verts = quad.get("v")
                if not isinstance(verts, list) or len(verts) != 20:
                    errors.append("%s: quad %d does not have 20 floats" % (origin, i))
                    continue
                resolve_texture(quad.get("texture", ""), models, origin)
                if quad.get("cullface") and quad["cullface"] not in (
                        "north", "south", "east", "west", "up", "down"):
                    errors.append("%s: quad %d bad cullface" % (origin, i))
    elif loader is not None and loader not in ("neoforge:item_layers",):
        warnings.append("%s: unknown loader %s" % (origin, loader))

    for i, element in enumerate(model.get("elements", []) or []):
        for key in ("from", "to"):
            for c in element.get(key, []):
                if c < -16 or c > 32:
                    errors.append("%s: element %d %s out of range (%s)" % (origin, i, key, c))
        rot = element.get("rotation")
        if rot:
            if "axis" not in rot or "angle" not in rot:
                errors.append("%s: element %d rotation is not 1.21.1 form" % (origin, i))
            else:
                if rot["axis"] not in ("x", "y", "z"):
                    errors.append("%s: element %d bad axis" % (origin, i))
                if float(rot["angle"]) not in LEGAL:
                    errors.append("%s: element %d illegal angle %s" % (origin, i, rot["angle"]))
        for face in (element.get("faces") or {}).values():
            if face.get("texture"):
                resolve_texture(face["texture"], models, origin)

    for override in model.get("overrides", []) or []:
        target = override.get("model")
        if not isinstance(target, str) or get_model(target) is None:
            errors.append("%s: override points at missing model %s" % (origin, target))


count = 0
for root, _dirs, files in os.walk(os.path.join(PACK, "assets/minecraft/models")):
    for fn in files:
        if not fn.endswith(".json"):
            continue
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, PACK).replace(os.sep, "/")
        try:
            model = json.load(open(full, encoding="utf-8-sig"))
        except Exception as exc:
            errors.append("%s: unparseable JSON: %s" % (rel, exc))
            continue
        count += 1
        check_inline(model, rel, [])

try:
    meta = json.load(open(os.path.join(PACK, "pack.mcmeta"), encoding="utf-8-sig"))
    if meta["pack"]["pack_format"] != 34:
        errors.append("pack.mcmeta: pack_format %s, expected 34" % meta["pack"]["pack_format"])
except Exception as exc:
    errors.append("pack.mcmeta: %s" % exc)

print("models checked :", count)
print("ERRORS         :", len(errors))
for e in errors[:25]:
    print("   ", e)
print("WARNINGS       :", len(warnings))
seen = set()
for w in warnings:
    key = w.split(":")[-1]
    if key in seen:
        continue
    seen.add(key)
    print("   ", w)
    if len(seen) > 12:
        break
