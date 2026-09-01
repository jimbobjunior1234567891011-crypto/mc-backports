"""Backport a 1.21.4+ item-model resource pack to 1.21.1 + NeoForge.

Two output modes:

  plain - vanilla-legal geometry only. Models whose elements 1.21.1 cannot parse are
          dropped, along with the items that need them. Nothing but NeoForge required.
  mod   - anything 1.21.1 rejects is re-emitted as a freerot:mesh quad soup, and item
          states that 1.21.1 has no property for (eating, use key held, enchanted) are
          restored through model overrides driven by the freerot mod's item properties.

In both modes the 1.21.4 item definition layer (assets/minecraft/items/) is flattened
into models/item/<id>.json, and "2D in the inventory, 3D in the hand" is preserved with
NeoForge's neoforge:separate_transforms loader.
"""
import itertools, json, os, shutil, sys, zipfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from bake import bake_model
from mesh import model_to_mesh

SRC, OUT, VANILLA_JAR = sys.argv[1], sys.argv[2], sys.argv[3]
MODE = sys.argv[4] if len(sys.argv) > 4 else "plain"
MODID = "freerot"

LEGAL_ANGLES = {-45.0, -22.5, 0.0, 22.5, 45.0}
CONTEXTS = ["none", "thirdperson_lefthand", "thirdperson_righthand",
            "firstperson_lefthand", "firstperson_righthand",
            "head", "gui", "ground", "fixed"]
MAX_STATES = 96

# state key -> item model predicate used in "overrides"
PREDICATE = {
    "using": MODID + ":using",
    "use_key": MODID + ":use_key",
    "enchanted": MODID + ":enchanted",
    "use_ticks": MODID + ":use_ticks",
    "cast": "cast",                 # vanilla, registered for fishing rods
    "angle": "angle",               # vanilla, registered for compasses
    "time": "time",                 # vanilla, registered for clocks
}
VANILLA_KEYS = {"cast", "angle", "time"}


def load(p):
    with open(p, encoding="utf-8-sig") as f:
        return json.load(f)


def model_path(ref):
    return os.path.join(SRC, "assets/minecraft/models", ref.replace("minecraft:", "") + ".json")


# ---------------------------------------------------------------- model classification
_class_cache, baked_models, mesh_models = {}, {}, {}


def raw_legal(d):
    for el in d.get("elements", []) or []:
        r = el.get("rotation")
        if not r:
            continue
        if "axis" in r and "angle" in r:
            if float(r["angle"]) not in LEGAL_ANGLES or r["axis"] not in ("x", "y", "z"):
                return False
            continue
        axes = [k for k in "xyz" if abs(float(r.get(k, 0))) > 1e-9]
        if len(axes) > 1 or (axes and float(r[axes[0]]) not in LEGAL_ANGLES):
            return False
    return True


def classify(ref):
    """'ok' | 'baked' | 'mesh' | 'no' | None (not shipped by the pack)."""
    if ref in _class_cache:
        return _class_cache[ref]
    _class_cache[ref] = "ok"                       # break parent cycles
    p = model_path(ref)
    if not os.path.exists(p):
        _class_cache[ref] = None
        return None
    try:
        d = load(p)
    except Exception:
        _class_cache[ref] = "no"
        return "no"

    # Even a legal-looking model may use the 1.21.11 {"x":..,"y":..,"z":..} rotation form,
    # which 1.21.1 cannot parse at all, so everything goes through the normaliser.
    baked, changed = bake_model(d)
    if baked is not None and raw_legal(baked):
        if changed:
            baked_models[ref] = baked
            verdict = "baked"
        else:
            verdict = "ok"
    elif MODE == "mod":
        converted = dict(d)
        converted.pop("elements", None)
        converted["loader"] = MODID + ":mesh"
        converted["mesh"] = model_to_mesh(d)
        mesh_models[ref] = converted
        verdict = "mesh"
    else:
        verdict = "no"

    if verdict != "no" and isinstance(d.get("parent"), str):
        if classify(d["parent"]) == "no":
            verdict = "no"
    _class_cache[ref] = verdict
    return verdict


def usable(ref):
    return classify(ref) in ("ok", "baked", "mesh")


# ---------------------------------------------------------------- item definition tree
def state_key(node):
    """Which state does this node branch on? (key, values, scale) or None.

    Values stay in the definition's own threshold space; `scale` converts them to the
    0-1 space the vanilla item properties use (a compass dispatch has scale 32, a clock
    64), and the mod's use_ticks property is raw ticks with scale 1."""
    t = node.get("type")
    prop = node.get("property")
    if t == "minecraft:condition":
        if prop == "minecraft:using_item":
            return "using", (0, 1), 1.0
        if prop == "minecraft:keybind_down" and node.get("keybind") == "key.use":
            return "use_key", (0, 1), 1.0
        if prop == "minecraft:has_component" and node.get("component") == "minecraft:enchantments":
            return "enchanted", (0, 1), 1.0
        if prop == "minecraft:fishing_rod/cast":
            return "cast", (0, 1), 1.0
    if t == "minecraft:range_dispatch":
        scale = float(node.get("scale", 1)) or 1.0
        thresholds = tuple(sorted({0.0} | {float(e.get("threshold", 0))
                                           for e in node.get("entries", [])}))
        if prop == "minecraft:use_duration" and node.get("remaining"):
            return "use_ticks", thresholds, scale
        if prop == "minecraft:compass":
            return "angle", thresholds, scale
        if prop == "minecraft:time":
            return "time", thresholds, scale
    return None


def collect_states(node, acc, scales):
    if isinstance(node, dict):
        got = state_key(node) if node.get("type") else None
        if got:
            key, values, scale = got
            if MODE == "mod" or key in VANILLA_KEYS:
                acc.setdefault(key, set()).update(values)
                scales[key] = scale
        for v in node.values():
            collect_states(v, acc, scales)
    elif isinstance(node, list):
        for v in node:
            collect_states(v, acc, scales)


def resolve(node, ctx, state):
    """Resolve an item-model node to a model ref for one display context and state."""
    if not isinstance(node, dict):
        return None
    t = node.get("type")
    if t == "minecraft:model":
        return node.get("model")
    if t == "minecraft:select":
        cases = node.get("cases", [])
        if node.get("property") == "minecraft:display_context":
            for case in cases:
                when = case.get("when")
                when = when if isinstance(when, list) else [when]
                if ctx in when:
                    return resolve(case.get("model"), ctx, state)
        elif "fallback" not in node and cases:
            # e.g. context_dimension: no state for it, so take the first branch
            return resolve(cases[0].get("model"), ctx, state)
        return resolve(node.get("fallback"), ctx, state)
    if t == "minecraft:condition":
        got = state_key(node)
        on = bool(state.get(got[0], 0)) if got and got[0] in state else False
        return resolve(node.get("on_true") if on else node.get("on_false"), ctx, state)
    if t == "minecraft:range_dispatch":
        got = state_key(node)
        entries = node.get("entries", [])
        if got and got[0] in state:
            value = state[got[0]]
            best, best_threshold = None, None
            for entry in entries:
                threshold = float(entry.get("threshold", 0))
                if threshold <= value and (best_threshold is None or threshold > best_threshold):
                    best, best_threshold = entry.get("model"), threshold
            if best is not None:
                return resolve(best, ctx, state)
        if "fallback" not in node and entries:
            # below every threshold and no fallback: the lowest entry is what shows
            lowest = min(entries, key=lambda e: float(e.get("threshold", 0)))
            return resolve(lowest.get("model"), ctx, state)
        return resolve(node.get("fallback"), ctx, state)
    if t in ("minecraft:special", "minecraft:empty", "minecraft:bundle/selected_item"):
        return None
    for key in ("model", "fallback"):
        if isinstance(node.get(key), dict):
            return resolve(node[key], ctx, state)
    return None


# ---------------------------------------------------------------- vanilla reference
jar = zipfile.ZipFile(VANILLA_JAR)
jar_names = set(jar.namelist())
vanilla = {}
for name in jar_names:
    if name.startswith("assets/minecraft/models/item/") and name.endswith(".json"):
        vanilla[os.path.basename(name)[:-5]] = json.loads(jar.read(name))

# ---------------------------------------------------------------- copy assets
if os.path.exists(OUT):
    shutil.rmtree(OUT)
os.makedirs(OUT)
if os.path.exists(os.path.join(SRC, "pack.png")):
    shutil.copy2(os.path.join(SRC, "pack.png"), os.path.join(OUT, "pack.png"))

counts = {"ok": 0, "baked": 0, "mesh": 0, "no": 0}
for root, dirs, files in os.walk(os.path.join(SRC, "assets")):
    dirs[:] = [d for d in dirs if d != "__MACOSX"]
    for fn in files:
        if fn == ".DS_Store":
            continue
        full = os.path.join(root, fn)
        rel = os.path.relpath(full, SRC).replace(os.sep, "/")
        if rel.startswith("assets/minecraft/items/"):
            continue                               # 1.21.4+ only layer, flattened below
        dst = os.path.join(OUT, rel)
        if rel.startswith("assets/minecraft/models/") and rel.endswith(".json"):
            ref = rel[len("assets/minecraft/models/"):-5]
            verdict = classify(ref)
            counts[verdict] = counts.get(verdict, 0) + 1
            if verdict == "no":
                continue
            if verdict in ("baked", "mesh"):
                payload = baked_models[ref] if verdict == "baked" else mesh_models[ref]
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                with open(dst, "w", encoding="utf-8") as f:
                    if verdict == "mesh":          # quad soups are big; keep them compact
                        json.dump(payload, f, separators=(",", ":"))
                    else:
                        json.dump(payload, f, indent=2)
                continue
        os.makedirs(os.path.dirname(dst), exist_ok=True)
        shutil.copy2(full, dst)

# ---------------------------------------------------------------- dead parents
def available(ref):
    ref = ref.replace("minecraft:", "")
    return (os.path.exists(os.path.join(OUT, "assets/minecraft/models", ref + ".json"))
            or "assets/minecraft/models/%s.json" % ref in jar_names)


stripped_parents, dropped_models = [], []
changed = True
while changed:
    changed = False
    for root, _dirs, files in os.walk(os.path.join(OUT, "assets/minecraft/models")):
        for fn in files:
            if not fn.endswith(".json"):
                continue
            full = os.path.join(root, fn)
            rel = os.path.relpath(full, OUT).replace(os.sep, "/")
            try:
                d = load(full)
            except Exception:
                continue
            par = d.get("parent")
            if not isinstance(par, str) or available(par):
                continue
            if d.get("elements") or d.get("mesh"):
                d.pop("parent")
                with open(full, "w", encoding="utf-8") as f:
                    json.dump(d, f, indent=2)
                stripped_parents.append((rel, par))
            else:
                os.remove(full)
                dropped_models.append((rel, par))
            changed = True

# ---------------------------------------------------------------- flatten items
def build_model(per_context, flat):
    """One model json for a resolved {context: ref} map."""
    refs = {v for v in per_context.values() if v}
    if len(refs) == 1 and all(per_context[c] for c in CONTEXTS):
        return {"parent": "minecraft:" + next(iter(refs))}
    tally = {}
    for c in CONTEXTS:
        tally[per_context[c]] = tally.get(per_context[c], 0) + 1
    base_ref = max(tally, key=tally.get)
    model = {"loader": "neoforge:separate_transforms",
             "gui_light": "front" if per_context["gui"] is None else "side",
             "base": {"parent": "minecraft:" + base_ref} if base_ref else flat,
             "perspectives": {}}
    for c in CONTEXTS:
        if per_context[c] != base_ref:
            model["perspectives"][c] = ({"parent": "minecraft:" + per_context[c]}
                                        if per_context[c] else flat)
    return model


def inlined(model):
    """A vanilla model copied into a perspective must lose its own overrides.

    Vanilla clock/compass models start their override chain with an entry pointing at
    themselves (item/compass -> item/compass). Once this pack replaces that file, an
    inlined copy of the chain resolves straight back into the model that contains it,
    and resolveParents recurses until the reload dies with a StackOverflowError. The
    state overrides this converter writes at the top level replace that chain anyway."""
    copy = dict(model)
    copy.pop("overrides", None)
    return copy


def vanilla_flat(item, state, scales):
    """The flat 1.21.1 model for this item in this state.

    Clocks and compasses carry their own vanilla override chain (item/clock_37, ...), so
    evaluate it against the state instead of freezing the inventory icon on frame 0."""
    base = inlined(vanilla[item])
    overrides = base.get("overrides")
    if not overrides or not state:
        return base
    chosen = None
    for override in overrides:
        predicates = override.get("predicate", {})
        if not predicates:
            continue
        ok = True
        for name, threshold in predicates.items():
            if name not in state:
                ok = False
                break
            if state[name] / scales.get(name, 1.0) < float(threshold) - 1e-9:
                ok = False
                break
        if ok:
            chosen = override.get("model")
    if not chosen:
        return base
    ref = chosen.replace("minecraft:", "")
    if ref == "item/" + item:                      # vanilla points at itself; we replaced it
        return base
    if "assets/minecraft/models/%s.json" % ref in jar_names or available(ref):
        return {"parent": "minecraft:" + ref}
    return base


def write_model(rel_name, payload):
    dst = os.path.join(OUT, "assets/minecraft/models/item", rel_name + ".json")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(dst, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


converted, dropped, not_in_1211, stateful = [], [], [], []
items_dir = os.path.join(SRC, "assets/minecraft/items")
for fn in sorted(os.listdir(items_dir)):
    if not fn.endswith(".json"):
        continue
    item = fn[:-5]
    if item not in vanilla:
        not_in_1211.append(item)
        continue
    try:
        definition = load(os.path.join(items_dir, fn))
    except Exception as exc:
        dropped.append((item, "unparseable definition: %s" % exc))
        continue
    node = definition.get("model")
    flat = inlined(vanilla[item])

    found, scales = {}, {}
    collect_states(node, found, scales)
    keys = sorted(found)
    combos = 1
    for k in keys:
        combos *= len(found[k])
    if combos > MAX_STATES:
        keys, found = [], {}                       # too many, keep the resting model only

    default_state = {k: 0 for k in keys}
    states = [dict(zip(keys, values)) for values in
              itertools.product(*[sorted(found[k]) for k in keys])] or [{}]

    resolved, flats = {}, {}
    bad = None
    for state in states:
        flats[tuple(sorted(state.items()))] = vanilla_flat(item, state, scales)
        per = {}
        for ctx in CONTEXTS:
            ref = resolve(node, ctx, state)
            if ref is None:
                per[ctx] = None
                continue
            ref = ref.replace("minecraft:", "")
            verdict = classify(ref)
            if verdict == "no" or (verdict in ("ok", "baked", "mesh") and not available(ref)):
                if state == default_state:
                    bad = ref
                    break
                per[ctx] = None                    # non-default state falls back to flat
            else:
                per[ctx] = ref if verdict is not None else None
        if bad:
            break
        resolved[tuple(sorted(state.items()))] = per
    if bad:
        dropped.append((item, "model %s cannot be loaded on 1.21.1" % bad))
        continue

    base_per = resolved[tuple(sorted(default_state.items()))]
    if not any(base_per.values()):
        dropped.append((item, "no 3D model resolved"))
        continue

    default_key = tuple(sorted(default_state.items()))
    base_flat = flats.get(default_key, flat)
    base_model = build_model(base_per, base_flat)
    overrides, index = [], 0
    for state_items, per in resolved.items():
        state = dict(state_items)
        if state == default_state:
            continue
        state_flat = flats.get(state_items, flat)
        if per == base_per and state_flat == base_flat:
            continue
        predicate = {PREDICATE[k]: round(v / scales.get(k, 1.0), 6)
                     for k, v in state.items() if v}
        if not predicate:
            continue
        index += 1
        name = "%s__state%d" % (item, index)
        write_model(name, build_model(per, state_flat))
        overrides.append({"predicate": predicate, "model": "minecraft:item/" + name})
    if overrides:
        # Minecraft takes the last override whose predicates all match, so the most
        # specific combinations have to come last.
        overrides.sort(key=lambda o: (len(o["predicate"]), sum(o["predicate"].values())))
        base_model["overrides"] = overrides
        stateful.append("%s(%d)" % (item, len(overrides)))

    write_model(item, base_model)
    converted.append(item)

# ---------------------------------------------------------------- pack metadata
description = ("Weskerson 3D Items 2.5 - 1.21.1 NeoForge backport"
               if MODE == "plain" else
               "Weskerson 3D Items 2.5 - 1.21.1 NeoForge backport (requires FreeRot)")
with open(os.path.join(OUT, "pack.mcmeta"), "w", encoding="utf-8") as f:
    json.dump({"pack": {"pack_format": 34, "description": description}}, f, indent=2)

print("mode            :", MODE)
print("models          :", counts)
print("parents stripped:", len(stripped_parents), "| models dropped:", len(dropped_models))
print("items converted :", len(converted))
print("items with state overrides:", len(stateful))
print("items dropped   :", len(dropped))
print("not in 1.21.1   :", len(not_in_1211))

with open(OUT.rstrip("/\\") + "-report.txt", "w", encoding="utf-8") as f:
    f.write("mode: %s\n\nconverted (%d):\n%s\n\n" % (MODE, len(converted), " ".join(converted)))
    f.write("state overrides (%d):\n%s\n\n" % (len(stateful), " ".join(stateful)))
    f.write("dropped (%d):\n%s\n\n" % (len(dropped), "\n".join("%s - %s" % x for x in dropped)))
    f.write("not in 1.21.1 (%d):\n%s\n" % (len(not_in_1211), " ".join(not_in_1211)))
