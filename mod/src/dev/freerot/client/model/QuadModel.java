package dev.freerot.client.model;

import net.minecraft.client.renderer.block.model.BakedQuad;
import net.minecraft.client.renderer.block.model.ItemOverrides;
import net.minecraft.client.renderer.block.model.ItemTransforms;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.client.resources.model.ModelState;
import net.minecraft.client.resources.model.SimpleBakedModel;
import net.minecraft.core.Direction;
import net.neoforged.neoforge.client.model.pipeline.QuadBakingVertexConsumer;
import org.joml.Vector3f;
import org.joml.Vector4f;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

/** Turns already-transformed quads into a BakedModel. */
public final class QuadModel {
    private QuadModel() {
    }

    public static BakedModel build(List<ModelSource.Quad> quads, ItemTransforms transforms,
                                   Map<String, String> textures, boolean gui3d,
                                   Function<String, TextureAtlasSprite> sprites, ModelState state) {
        List<BakedQuad> unculled = new ArrayList<>();
        // SimpleBakedModel.getQuads does a bare culledFaces.get(side) with no fallback, so
        // every direction needs an entry or rendering NPEs on the missing ones.
        Map<Direction, List<BakedQuad>> culled = new EnumMap<>(Direction.class);
        for (Direction direction : Direction.values()) {
            culled.put(direction, new ArrayList<>());
        }

        TextureAtlasSprite particle = sprites.apply("#particle");
        for (ModelSource.Quad quad : quads) {
            TextureAtlasSprite sprite = sprites.apply(quad.texture());
            if (particle == null) {
                particle = sprite;
            }
            BakedQuad baked = bake(quad, sprite, state);
            Direction cull = quad.cullface() == null ? null : Direction.byName(quad.cullface());
            if (cull != null) {
                culled.get(Direction.rotate(state.getRotation().getMatrix(), cull)).add(baked);
            } else {
                unculled.add(baked);
            }
        }
        return new SimpleBakedModel(unculled, culled, true, gui3d, true, particle,
                transforms, ItemOverrides.EMPTY);
    }

    private static BakedQuad bake(ModelSource.Quad quad, TextureAtlasSprite sprite, ModelState state) {
        float[] v = quad.vertices();
        float[][] positions = new float[4][3];
        boolean identity = state.getRotation().isIdentity();
        for (int i = 0; i < 4; i++) {
            positions[i][0] = v[i * 5] / 16f;
            positions[i][1] = v[i * 5 + 1] / 16f;
            positions[i][2] = v[i * 5 + 2] / 16f;
            if (!identity) {
                Vector4f point = new Vector4f(positions[i][0] - 0.5f, positions[i][1] - 0.5f,
                        positions[i][2] - 0.5f, 1f);
                state.getRotation().getMatrix().transform(point);
                positions[i][0] = point.x() + 0.5f;
                positions[i][1] = point.y() + 0.5f;
                positions[i][2] = point.z() + 0.5f;
            }
        }

        Vector3f normal = normalOf(positions);
        QuadBakingVertexConsumer consumer = new QuadBakingVertexConsumer();
        consumer.setSprite(sprite);
        consumer.setDirection(Direction.getNearest(normal.x(), normal.y(), normal.z()));
        consumer.setTintIndex(quad.tintIndex());
        consumer.setShade(quad.shade());
        for (int i = 0; i < 4; i++) {
            consumer.addVertex(positions[i][0], positions[i][1], positions[i][2])
                    .setColor(255, 255, 255, 255)
                    .setUv(sprite.getU(v[i * 5 + 3] / 16f), sprite.getV(v[i * 5 + 4] / 16f))
                    .setUv2(0, 0)
                    .setNormal(normal.x(), normal.y(), normal.z());
        }
        return consumer.bakeQuad();
    }

    /** Newell normal, so a degenerate corner does not produce a zero vector. */
    private static Vector3f normalOf(float[][] positions) {
        float nx = 0f, ny = 0f, nz = 0f;
        for (int i = 0; i < 4; i++) {
            float[] a = positions[i];
            float[] b = positions[(i + 1) % 4];
            nx += (a[1] - b[1]) * (a[2] + b[2]);
            ny += (a[2] - b[2]) * (a[0] + b[0]);
            nz += (a[0] - b[0]) * (a[1] + b[1]);
        }
        Vector3f normal = new Vector3f(nx, ny, nz);
        return normal.lengthSquared() < 1.0e-8f ? new Vector3f(0f, 1f, 0f) : normal.normalize();
    }
}
