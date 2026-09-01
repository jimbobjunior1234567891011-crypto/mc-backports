package dev.freerot.client.model;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import net.minecraft.client.renderer.block.model.ItemTransform;
import net.minecraft.client.renderer.block.model.ItemTransforms;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.client.resources.model.Material;
import net.minecraft.client.resources.model.ModelState;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.server.packs.resources.ResourceManager;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.inventory.InventoryMenu;
import org.joml.Vector3f;

import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Optional;
import java.util.function.Function;

/**
 * Reads a model JSON the way the game would, except that element rotations are not
 * restricted: any angle, around any combination of axes.
 *
 * <p>1.21.1 refuses those models at parse time, which is the whole reason packs written
 * for 1.21.4+ do not load. Everything here happens before the game's parser sees them, so
 * the geometry is baked directly into quads and handed over as a finished model.
 *
 * <p>The rotation maths mirrors the game exactly: a single axis is one rotation, several
 * axes compose as Matrix4f.rotationZYX(z, y, x) - X first, then Y, then Z - and rescale
 * divides each axis by the largest component of that axis under the rotation, applied
 * before it.
 */
public final class ModelSource {
    private static final int MAX_PARENTS = 16;

    private ModelSource() {
    }

    /**
     * Bake a model by id, or null when the model has no geometry of its own (item/generated
     * and friends). The caller substitutes the game's own baked model for those, which
     * avoids re-implementing sprite models and cannot recurse back into us.
     */
    public static BakedModel bake(ResourceLocation modelId, ResourceManager resources,
                                  Function<Material, TextureAtlasSprite> sprites, ModelState state) {
        List<JsonObject> chain = chain(modelId, resources);
        JsonObject withElements = null;
        for (JsonObject json : chain) {
            if (json.has("elements")) {
                withElements = json;
                break;
            }
        }
        if (withElements == null) {
            return null;                                       // caller falls back to vanilla
        }

        Map<String, String> textures = new HashMap<>();
        for (int i = chain.size() - 1; i >= 0; i--) {          // root first, child wins
            JsonObject table = chain.get(i).getAsJsonObject("textures");
            if (table == null) {
                continue;
            }
            for (Map.Entry<String, JsonElement> entry : table.entrySet()) {
                textures.put(entry.getKey(), entry.getValue().getAsString());
            }
        }

        List<Quad> quads = new ArrayList<>();
        for (JsonElement element : withElements.getAsJsonArray("elements")) {
            readElement(element.getAsJsonObject(), quads);
        }

        boolean gui3d = true;
        for (JsonObject json : chain) {
            if (json.has("gui_light")) {
                gui3d = !"front".equals(json.get("gui_light").getAsString());
                break;
            }
        }
        return QuadModel.build(quads, transforms(chain), textures, gui3d, resolver(textures, sprites), state);
    }

    private static Function<String, TextureAtlasSprite> resolver(Map<String, String> textures,
                                                                 Function<Material, TextureAtlasSprite> sprites) {
        return reference -> {
            String value = reference;
            for (int i = 0; i < 8 && value != null && value.startsWith("#"); i++) {
                value = textures.get(value.substring(1));
            }
            if (value == null) {
                value = "minecraft:missingno";
            }
            return sprites.apply(new Material(InventoryMenu.BLOCK_ATLAS, ResourceLocation.parse(value)));
        };
    }

    private static List<JsonObject> chain(ResourceLocation modelId, ResourceManager resources) {
        List<JsonObject> chain = new ArrayList<>();
        ResourceLocation current = modelId;
        for (int i = 0; i < MAX_PARENTS && current != null; i++) {
            JsonObject json = read(current, resources);
            if (json == null) {
                break;
            }
            chain.add(json);
            current = json.has("parent")
                    ? ResourceLocation.parse(json.get("parent").getAsString())
                    : null;
        }
        return chain;
    }

    private static JsonObject read(ResourceLocation modelId, ResourceManager resources) {
        ResourceLocation path = ResourceLocation.fromNamespaceAndPath(
                modelId.getNamespace(), "models/" + modelId.getPath() + ".json");
        Optional<Resource> resource = resources.getResource(path);
        if (resource.isEmpty()) {
            return null;
        }
        try (InputStreamReader reader = new InputStreamReader(resource.get().open())) {
            return JsonParser.parseReader(reader).getAsJsonObject();
        } catch (Exception exception) {
            return null;
        }
    }

    private static ItemTransforms transforms(List<JsonObject> chain) {
        Map<ItemDisplayContext, ItemTransform> found = new LinkedHashMap<>();
        for (JsonObject json : chain) {                        // child wins
            JsonObject display = json.getAsJsonObject("display");
            if (display == null) {
                continue;
            }
            for (Map.Entry<String, JsonElement> entry : display.entrySet()) {
                ItemDisplayContext context = context(entry.getKey());
                if (context != null && !found.containsKey(context)) {
                    found.put(context, transform(entry.getValue().getAsJsonObject()));
                }
            }
        }
        if (found.isEmpty()) {
            return ItemTransforms.NO_TRANSFORMS;
        }
        return new ItemTransforms(
                found.getOrDefault(ItemDisplayContext.THIRD_PERSON_LEFT_HAND, ItemTransform.NO_TRANSFORM),
                found.getOrDefault(ItemDisplayContext.THIRD_PERSON_RIGHT_HAND, ItemTransform.NO_TRANSFORM),
                found.getOrDefault(ItemDisplayContext.FIRST_PERSON_LEFT_HAND, ItemTransform.NO_TRANSFORM),
                found.getOrDefault(ItemDisplayContext.FIRST_PERSON_RIGHT_HAND, ItemTransform.NO_TRANSFORM),
                found.getOrDefault(ItemDisplayContext.HEAD, ItemTransform.NO_TRANSFORM),
                found.getOrDefault(ItemDisplayContext.GUI, ItemTransform.NO_TRANSFORM),
                found.getOrDefault(ItemDisplayContext.GROUND, ItemTransform.NO_TRANSFORM),
                found.getOrDefault(ItemDisplayContext.FIXED, ItemTransform.NO_TRANSFORM));
    }

    private static ItemDisplayContext context(String name) {
        for (ItemDisplayContext context : ItemDisplayContext.values()) {
            if (context.getSerializedName().equals(name.toLowerCase(Locale.ROOT))) {
                return context;
            }
        }
        return null;
    }

    private static ItemTransform transform(JsonObject json) {
        return new ItemTransform(
                vector(json, "rotation", 0f),
                vector(json, "translation", 0f),
                vector(json, "scale", 1f));
    }

    private static Vector3f vector(JsonObject json, String key, float fallback) {
        JsonArray array = json.getAsJsonArray(key);
        if (array == null) {
            return new Vector3f(fallback, fallback, fallback);
        }
        return new Vector3f(array.get(0).getAsFloat(), array.get(1).getAsFloat(), array.get(2).getAsFloat());
    }

    // ------------------------------------------------------------------ geometry
    /** One textured quad: 4 vertices of x,y,z,u,v, positions in model space, uv in 0-16. */
    public record Quad(String texture, String cullface, int tintIndex, boolean shade, float[] vertices) {
    }

    private static void readElement(JsonObject element, List<Quad> out) {
        float[] from = triple(element.getAsJsonArray("from"));
        float[] to = triple(element.getAsJsonArray("to"));
        boolean shade = !element.has("shade") || element.get("shade").getAsBoolean();
        JsonObject faces = element.getAsJsonObject("faces");
        if (faces == null) {
            return;
        }
        float[][] matrix = null;
        float[] origin = null;
        JsonObject rotation = element.getAsJsonObject("rotation");
        if (rotation != null) {
            matrix = rotationMatrix(rotation);
            origin = rotation.has("origin") ? triple(rotation.getAsJsonArray("origin")) : new float[]{8, 8, 8};
        }

        for (Map.Entry<String, JsonElement> entry : faces.entrySet()) {
            Face face = Face.byName(entry.getKey());
            if (face == null) {
                continue;
            }
            JsonObject json = entry.getValue().getAsJsonObject();
            if (!json.has("texture")) {
                continue;
            }
            float[][] positions = face.corners(from, to);
            if (matrix != null) {
                for (float[] point : positions) {
                    apply(matrix, origin, point);
                }
            }
            float[] uv = json.has("uv")
                    ? quad(json.getAsJsonArray("uv"))
                    : face.defaultUv(from, to);
            int[] order = Face.rotationOrder(json.has("rotation") ? json.get("rotation").getAsInt() : 0);
            float[] vertices = new float[20];
            for (int i = 0; i < 4; i++) {
                vertices[i * 5] = positions[i][0];
                vertices[i * 5 + 1] = positions[i][1];
                vertices[i * 5 + 2] = positions[i][2];
                vertices[i * 5 + 3] = uv[order[i * 2]];
                vertices[i * 5 + 4] = uv[order[i * 2 + 1]];
            }
            out.add(new Quad(
                    json.get("texture").getAsString(),
                    json.has("cullface") ? json.get("cullface").getAsString() : null,
                    json.has("tintindex") ? json.get("tintindex").getAsInt() : -1,
                    shade,
                    vertices));
        }
    }

    private static float[][] rotationMatrix(JsonObject rotation) {
        float[][] matrix;
        if (rotation.has("axis") && rotation.has("angle")) {
            matrix = axis(rotation.get("axis").getAsString(), rotation.get("angle").getAsFloat());
        } else {
            float x = rotation.has("x") ? rotation.get("x").getAsFloat() : 0f;
            float y = rotation.has("y") ? rotation.get("y").getAsFloat() : 0f;
            float z = rotation.has("z") ? rotation.get("z").getAsFloat() : 0f;
            matrix = multiply(axis("z", z), multiply(axis("y", y), axis("x", x)));
        }
        if (rotation.has("rescale") && rotation.get("rescale").getAsBoolean()) {
            for (int i = 0; i < 3; i++) {
                float[] unit = new float[3];
                unit[i] = 1f;
                float[] mapped = transform(matrix, unit);
                float biggest = Math.max(Math.abs(mapped[0]), Math.max(Math.abs(mapped[1]), Math.abs(mapped[2])));
                float scale = biggest > 1.0e-6f ? 1f / biggest : 1f;
                for (int row = 0; row < 3; row++) {
                    matrix[row][i] *= scale;
                }
            }
        }
        return matrix;
    }

    private static float[][] axis(String axis, float degrees) {
        double radians = Math.toRadians(degrees);
        float c = (float) Math.cos(radians);
        float s = (float) Math.sin(radians);
        return switch (axis) {
            case "x" -> new float[][]{{1, 0, 0}, {0, c, -s}, {0, s, c}};
            case "y" -> new float[][]{{c, 0, s}, {0, 1, 0}, {-s, 0, c}};
            default -> new float[][]{{c, -s, 0}, {s, c, 0}, {0, 0, 1}};
        };
    }

    private static float[][] multiply(float[][] a, float[][] b) {
        float[][] out = new float[3][3];
        for (int i = 0; i < 3; i++) {
            for (int j = 0; j < 3; j++) {
                out[i][j] = a[i][0] * b[0][j] + a[i][1] * b[1][j] + a[i][2] * b[2][j];
            }
        }
        return out;
    }

    private static float[] transform(float[][] matrix, float[] point) {
        return new float[]{
                matrix[0][0] * point[0] + matrix[0][1] * point[1] + matrix[0][2] * point[2],
                matrix[1][0] * point[0] + matrix[1][1] * point[1] + matrix[1][2] * point[2],
                matrix[2][0] * point[0] + matrix[2][1] * point[1] + matrix[2][2] * point[2]};
    }

    private static void apply(float[][] matrix, float[] origin, float[] point) {
        float[] local = {point[0] - origin[0], point[1] - origin[1], point[2] - origin[2]};
        float[] moved = transform(matrix, local);
        point[0] = moved[0] + origin[0];
        point[1] = moved[1] + origin[1];
        point[2] = moved[2] + origin[2];
    }

    private static float[] triple(JsonArray array) {
        return new float[]{array.get(0).getAsFloat(), array.get(1).getAsFloat(), array.get(2).getAsFloat()};
    }

    private static float[] quad(JsonArray array) {
        return new float[]{array.get(0).getAsFloat(), array.get(1).getAsFloat(),
                array.get(2).getAsFloat(), array.get(3).getAsFloat()};
    }
}
