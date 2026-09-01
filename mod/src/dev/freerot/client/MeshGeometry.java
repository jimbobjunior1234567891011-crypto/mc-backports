package dev.freerot.client;

import com.mojang.math.Transformation;
import net.minecraft.client.renderer.block.model.BakedQuad;
import net.minecraft.client.renderer.block.model.ItemOverrides;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.client.resources.model.Material;
import net.minecraft.client.resources.model.ModelBaker;
import net.minecraft.client.resources.model.ModelState;
import net.minecraft.client.resources.model.SimpleBakedModel;
import net.minecraft.core.Direction;
import net.neoforged.neoforge.client.model.geometry.IGeometryBakingContext;
import net.neoforged.neoforge.client.model.geometry.IUnbakedGeometry;
import net.neoforged.neoforge.client.model.pipeline.QuadBakingVertexConsumer;
import org.joml.Vector3f;
import org.joml.Vector4f;

import javax.annotation.Nullable;
import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.function.Function;

/**
 * A model that is already a triangulation-free quad soup: the pack's converter has
 * applied every element rotation up front, so nothing here has to obey the vanilla
 * "one axis, multiples of 22.5 degrees" rule.
 */
public class MeshGeometry implements IUnbakedGeometry<MeshGeometry> {
    /** Positions are in model space (0-16); uvs are in texture space (0-16). */
    public record Quad(String texture, @Nullable Direction cullface, int tintIndex, boolean shade, float[] vertices) {
    }

    private final List<Quad> quads;

    public MeshGeometry(List<Quad> quads) {
        this.quads = quads;
    }

    @Override
    public BakedModel bake(IGeometryBakingContext context, ModelBaker baker,
                           Function<Material, TextureAtlasSprite> spriteGetter,
                           ModelState modelState, ItemOverrides overrides) {
        List<BakedQuad> unculled = new ArrayList<>();
        // SimpleBakedModel.getQuads does a plain culledFaces.get(side) with no fallback,
        // so every direction needs an entry or item rendering NPEs on the missing ones.
        // Vanilla's own Builder pre-fills all six for the same reason.
        Map<Direction, List<BakedQuad>> culled = new EnumMap<>(Direction.class);
        for (Direction direction : Direction.values()) {
            culled.put(direction, new ArrayList<>());
        }
        Transformation transform = modelState.getRotation();

        for (Quad quad : quads) {
            TextureAtlasSprite sprite = spriteGetter.apply(context.getMaterial(quad.texture()));
            BakedQuad baked = bake(quad, sprite, transform);
            Direction cull = quad.cullface();
            if (cull != null) {
                Direction rotated = Direction.rotate(transform.getMatrix(), cull);
                culled.get(rotated).add(baked);
            } else {
                unculled.add(baked);
            }
        }

        TextureAtlasSprite particle = spriteGetter.apply(context.getMaterial("particle"));
        return new SimpleBakedModel(unculled, culled, context.useAmbientOcclusion(),
                context.isGui3d(), context.useBlockLight(), particle,
                context.getTransforms(), overrides);
    }

    private static BakedQuad bake(Quad quad, TextureAtlasSprite sprite, Transformation transform) {
        float[] v = quad.vertices();
        float[][] pos = new float[4][3];
        for (int i = 0; i < 4; i++) {
            pos[i][0] = v[i * 5] / 16f;
            pos[i][1] = v[i * 5 + 1] / 16f;
            pos[i][2] = v[i * 5 + 2] / 16f;
            if (!transform.isIdentity()) {
                Vector4f p = new Vector4f(pos[i][0] - 0.5f, pos[i][1] - 0.5f, pos[i][2] - 0.5f, 1f);
                transform.getMatrix().transform(p);
                pos[i][0] = p.x() + 0.5f;
                pos[i][1] = p.y() + 0.5f;
                pos[i][2] = p.z() + 0.5f;
            }
        }

        Vector3f normal = normalOf(pos);
        Direction facing = Direction.getNearest(normal.x(), normal.y(), normal.z());

        QuadBakingVertexConsumer consumer = new QuadBakingVertexConsumer();
        consumer.setSprite(sprite);
        consumer.setDirection(facing);
        consumer.setTintIndex(quad.tintIndex());
        consumer.setShade(quad.shade());
        for (int i = 0; i < 4; i++) {
            consumer.addVertex(pos[i][0], pos[i][1], pos[i][2])
                    .setColor(255, 255, 255, 255)
                    .setUv(sprite.getU(v[i * 5 + 3] / 16f), sprite.getV(v[i * 5 + 4] / 16f))
                    .setUv2(0, 0)
                    .setNormal(normal.x(), normal.y(), normal.z());
        }
        return consumer.bakeQuad();
    }

    /** Newell-style normal, so degenerate edges in one corner do not produce a zero vector. */
    private static Vector3f normalOf(float[][] pos) {
        float nx = 0f, ny = 0f, nz = 0f;
        for (int i = 0; i < 4; i++) {
            float[] a = pos[i];
            float[] b = pos[(i + 1) % 4];
            nx += (a[1] - b[1]) * (a[2] + b[2]);
            ny += (a[2] - b[2]) * (a[0] + b[0]);
            nz += (a[0] - b[0]) * (a[1] + b[1]);
        }
        Vector3f normal = new Vector3f(nx, ny, nz);
        if (normal.lengthSquared() < 1.0e-8f) {
            return new Vector3f(0f, 1f, 0f);
        }
        return normal.normalize();
    }
}
