package dev.freerot.client;

import com.google.gson.JsonArray;
import com.google.gson.JsonDeserializationContext;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import com.google.gson.JsonParseException;
import net.minecraft.core.Direction;
import net.minecraft.util.GsonHelper;
import net.neoforged.neoforge.client.model.geometry.IGeometryLoader;

import java.util.ArrayList;
import java.util.List;

/**
 * Reads:
 * <pre>
 * {
 *   "loader": "freerot:mesh",
 *   "textures": { "0": "minecraft:item/foo", "particle": "minecraft:item/foo" },
 *   "display": { ... },
 *   "mesh": [
 *     { "texture": "#0", "tintindex": -1, "shade": false, "cullface": "down",
 *       "v": [x,y,z,u,v,  x,y,z,u,v,  x,y,z,u,v,  x,y,z,u,v] }
 *   ]
 * }
 * </pre>
 */
public class MeshLoader implements IGeometryLoader<MeshGeometry> {
    public static final MeshLoader INSTANCE = new MeshLoader();

    @Override
    public MeshGeometry read(JsonObject json, JsonDeserializationContext context) throws JsonParseException {
        JsonArray mesh = GsonHelper.getAsJsonArray(json, "mesh");
        List<MeshGeometry.Quad> quads = new ArrayList<>(mesh.size());
        for (JsonElement element : mesh) {
            JsonObject obj = element.getAsJsonObject();
            String texture = GsonHelper.getAsString(obj, "texture");
            int tint = GsonHelper.getAsInt(obj, "tintindex", -1);
            boolean shade = GsonHelper.getAsBoolean(obj, "shade", true);
            Direction cullface = null;
            if (obj.has("cullface")) {
                cullface = Direction.byName(GsonHelper.getAsString(obj, "cullface"));
                if (cullface == null) {
                    throw new JsonParseException("Unknown cullface in freerot:mesh quad");
                }
            }
            JsonArray verts = GsonHelper.getAsJsonArray(obj, "v");
            if (verts.size() != 20) {
                throw new JsonParseException("freerot:mesh quad needs 20 floats (4 vertices), got " + verts.size());
            }
            float[] values = new float[20];
            for (int i = 0; i < 20; i++) {
                values[i] = verts.get(i).getAsFloat();
            }
            quads.add(new MeshGeometry.Quad(texture, cullface, tint, shade, values));
        }
        return new MeshGeometry(quads);
    }
}
