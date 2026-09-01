# FreeRot

Backports resource packs written for the **1.21.4+ item model system** to **Minecraft 1.21.1 + NeoForge**, including the geometry and the animated item states that 1.21.1 has no way to express.

Built for [Weskerson's 3D Items](https://modrinth.com/resourcepack/tools-and-utils) 2.5, but the converter is generic — it reads any pack that uses `assets/minecraft/items/`.

| | items covered |
|---|---|
| Weskerson's 3D Items 2.5 on stock 1.21.1 | 0 |
| converted, no mod | 223 |
| converted, with the FreeRot mod | **336** of 338 possible |

---

## Why the packs break

Two independent problems, and most "just change pack_format" advice fixes neither.

**1. The item definition layer.** Since 1.21.4 an item's model is chosen by a JSON file in `assets/minecraft/items/`, which can branch on display context, item components, and use state. 1.21.1 does not read that directory at all — it maps item id straight to `models/item/<id>.json`. Every item silently stays vanilla.

**2. The geometry.** Element rotation rules loosened twice after 1.21.1:

| | multiple axes at once | angles off the 22.5° grid |
|---|---|---|
| 1.21.1 | no | no |
| 1.21.6 | no | yes |
| 1.21.11 | yes | yes |

Weskerson's 2.5 uses 1473 multi-axis elements and 924 free-angle ones. 1.21.1 rejects those models outright — not a visual glitch, a load failure.

## How it is fixed

**Item definitions → plain models.** Each definition is flattened into `models/item/<id>.json`.

**2D in the inventory, 3D in the hand** survives via NeoForge's `neoforge:separate_transforms`: the `gui`/`ground`/`fixed` perspectives get the vanilla 1.21.1 model (inlined, so it cannot recurse into the file that replaced it), the hand perspectives get the pack's 3D models. `gui_light` is forced to `front` wherever the inventory shows a flat sprite, or it renders with block shading.

**Geometry, three tiers:**

| tier | what happens | models |
|---|---|---|
| legal as-is | copied unchanged | 467 |
| rotation is 90/180/270 plus a legal remainder | the right-angle part is applied to the box's own coordinates, the remainder stays in the rotation field. Faces, cullfaces and texture orientation move with it | 26 |
| anything else | emitted as a `freerot:mesh` quad soup with the rotation already applied — needs the mod | 393 |

The right-angle bake is exact, and proven so: every rewritten face is compared against the textured quad the original element produced, and a model is only rewritten when all of them match.

**Item states → overrides.** States 1.21.1 has no property for are rebuilt as ordinary `overrides` driven by properties the mod registers — one generated model per reachable state, ordered so Minecraft's "last matching override wins" picks the right one.

| pack asks for | 1.21.1 gets |
|---|---|
| `minecraft:use_duration` (remaining) | `freerot:use_ticks` + `freerot:using` → eating and drinking frames |
| `minecraft:keybind_down` (`key.use`) | `freerot:use_key` → flint & steel / shears strike pose |
| `minecraft:has_component` (enchantments) | `freerot:enchanted` |
| `minecraft:fishing_rod/cast` | vanilla `cast` |
| `minecraft:compass` / `minecraft:time` | vanilla `angle` / `time`, rescaled from the dispatch's own `scale` |

## The mod

`freerot` is a client-only NeoForge 21.1.x mod, about 200 lines. It has no config, no commands and no registry objects; without a pack asking for it, it does nothing.

- **`freerot:mesh` model loader** — takes pre-transformed quads (positions in model space, uvs in texture space) and bakes them. Because the converter applies rotations up front, the game never sees a rotation it would refuse.
- **four item properties** — `freerot:use_key`, `freerot:using`, `freerot:use_ticks`, `freerot:enchanted`.

### Getting the rotation math right

The mesh converter reproduces the game's own transform rather than approximating it:

- single axis → `Matrix4f.rotation(angle, axis)`
- several axes → `Matrix4f.rotationZYX(z, y, x)`, i.e. **X first, then Y, then Z**
- `rescale` → `1 / max(|component|)` of each axis under the rotation, applied *before* it (this generalises the familiar `sqrt(2)` for a 45° turn)

That composition order was read out of the 1.21.11 client jar (`hqd$a`), not guessed. The vertex and UV mapping mirrors `FaceBakery` via [deepslate](https://github.com/misode/deepslate)'s reimplementation.

## Layout

```
converter/
  backport.py        pack -> 1.21.1 pack, mode "plain" or "mod"
  bake.py            right-angle bake + the FaceBakery-equivalent quad mapping
  mesh.py            arbitrary rotations -> freerot:mesh quad soup
  fix_hotbar.py      unrelated: repairs an out-of-range animation frame list
  tests/
    test_bake.py     baked models must emit the original's quads
    test_mesh.py     mesh output cross-checked against the verified mapping
    validate.py      references, rotation legality, loader shapes, pack_format
mod/
  src/               the mod
  build.ps1          javac + jar, no Gradle
tools/               analysis: angle census, per-item blockers, bake feasibility
```

## Usage

```bash
python converter/backport.py <unpacked-pack> <out-dir> <path-to-1.21.1.jar> mod
python converter/tests/validate.py <out-dir> <path-to-1.21.1.jar>
```

Use `plain` instead of `mod` for the build that needs no mod. Both tests are worth running after any change to `bake.py` or `mesh.py`:

```bash
python converter/tests/test_bake.py <unpacked-pack>
python converter/tests/test_mesh.py <unpacked-pack>
```

Building the mod (needs a NeoForge install to compile against — it uses the jars already on disk):

```powershell
powershell -ExecutionPolicy Bypass -File mod\build.ps1
```

## Status

Static verification is thorough: 0 reference or rotation errors across 1579 models, 26/26 baked models quad-identical to their originals, 653 models cross-checked between the two independent geometry paths with 0 mismatches.

Nothing has been rendered in game yet. The untested surfaces, most to least likely to bite: the mod's quad upload path (normals and winding), texture orientation on the 226 multi-axis models, and particle sprite fallback on models that declare no `particle`.

## Not covered

- 72 items in the source pack do not exist in 1.21.1 (copper lanterns, harnesses, coloured bundles, nautilus armor, pale oak boats and signs, newer spawn eggs and discs).
- `crimson_hanging_sign` and `warped_hanging_sign` — version 2.5 references hand models it does not ship.
- A state change swaps the whole model, so an item mid-eat also shows its chew stage in the inventory slot for those few ticks.
