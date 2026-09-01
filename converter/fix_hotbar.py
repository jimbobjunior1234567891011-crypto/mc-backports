"""Fix Animated Hotbar RGB for 1.21.1.

The shipped .mcmeta files list frames 1..40 plus an explicit {"index": 0}. Each sprite
only has 40 frames (indices 0..39), so index 40 is out of range and Minecraft rejects the
whole sprite. Rewriting the animation to the implicit full-frame cycle fixes it and keeps
the intended 1 tick per frame.
"""
import json, os, shutil, struct, sys

SRC, OUT = sys.argv[1], sys.argv[2]

if os.path.exists(OUT):
    shutil.rmtree(OUT)
shutil.copytree(SRC, OUT)


def png_size(path):
    with open(path, "rb") as f:
        head = f.read(33)
    return struct.unpack(">II", head[16:24])


fixed = []
sprites = os.path.join(OUT, "assets/minecraft/textures")
for root, _dirs, files in os.walk(sprites):
    for fn in files:
        if not fn.endswith(".png.mcmeta"):
            continue
        meta_path = os.path.join(root, fn)
        png_path = meta_path[:-len(".mcmeta")]
        meta = json.load(open(meta_path, encoding="utf-8-sig"))
        anim = meta.get("animation")
        if not anim:
            continue
        w, h = png_size(png_path)
        fh = anim.get("height", w)
        frames = h // fh
        old = anim.get("frames")
        new_anim = {"frametime": anim.get("frametime", 1), "height": fh}
        if anim.get("width"):
            new_anim["width"] = anim["width"]
        if anim.get("interpolate"):
            new_anim["interpolate"] = True
        json.dump({"animation": new_anim}, open(meta_path, "w", encoding="utf-8"), indent=2)
        fixed.append((os.path.relpath(meta_path, OUT), "%dx%d" % (w, h), frames, len(old) if old else None))

meta = json.load(open(os.path.join(OUT, "pack.mcmeta"), encoding="utf-8-sig"))
meta["pack"]["pack_format"] = 34
meta["pack"].pop("supported_formats", None)
meta["pack"].pop("min_format", None)
meta["pack"].pop("max_format", None)
json.dump(meta, open(os.path.join(OUT, "pack.mcmeta"), "w", encoding="utf-8"), indent=2)

for rel, size, frames, old in fixed:
    print("%-64s %-10s real frames=%-4d old frame list=%s" % (rel, size, frames, old))
