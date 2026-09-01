package dev.freerot.client.item;

import com.mojang.blaze3d.vertex.PoseStack;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.block.model.BakedQuad;
import net.minecraft.client.renderer.block.model.ItemOverrides;
import net.minecraft.client.renderer.block.model.ItemTransforms;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.core.Direction;
import net.minecraft.util.RandomSource;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;
import net.minecraft.world.level.block.state.BlockState;

import javax.annotation.Nullable;
import java.util.List;
import java.util.Map;

/**
 * The model an item gets when a pack defines it the 1.21.4+ way.
 *
 * <p>The game asks for a model once per stack (through the overrides) and only then tells
 * it which display context it is drawing. That is exactly the shape the new definitions
 * need: {@link Bound} captures the stack, and picks the geometry when the context finally
 * arrives - 2D sprite in the inventory, the pack's 3D model in hand, an eating frame while
 * the stack is being eaten.
 */
public class DefinitionModel implements BakedModel {
    private final ItemDefinition definition;
    private final Map<String, BakedModel> models;
    private final BakedModel vanilla;
    private final ItemOverrides overrides;

    public DefinitionModel(ItemDefinition definition, Map<String, BakedModel> models, BakedModel vanilla) {
        this.definition = definition;
        this.models = models;
        this.vanilla = vanilla;
        this.overrides = new ItemOverrides() {
            @Override
            public BakedModel resolve(BakedModel model, ItemStack stack, @Nullable ClientLevel level,
                                      @Nullable LivingEntity entity, int seed) {
                return new Bound(DefinitionModel.this, new ItemDefinition.State(stack, level, entity, seed));
            }
        };
    }

    BakedModel modelFor(ItemDisplayContext context, ItemDefinition.State state) {
        String path = definition.resolve(context, state);
        if (path == null) {
            return vanilla;
        }
        BakedModel model = models.get(path);
        return model == null ? vanilla : model;
    }

    @Override
    public List<BakedQuad> getQuads(@Nullable BlockState state, @Nullable Direction side, RandomSource random) {
        return vanilla.getQuads(state, side, random);
    }

    @Override
    public boolean useAmbientOcclusion() {
        return vanilla.useAmbientOcclusion();
    }

    @Override
    public boolean isGui3d() {
        return vanilla.isGui3d();
    }

    @Override
    public boolean usesBlockLight() {
        return vanilla.usesBlockLight();
    }

    @Override
    public boolean isCustomRenderer() {
        return false;
    }

    @Override
    public TextureAtlasSprite getParticleIcon() {
        return vanilla.getParticleIcon();
    }

    @Override
    public ItemTransforms getTransforms() {
        return ItemTransforms.NO_TRANSFORMS;
    }

    @Override
    public ItemOverrides getOverrides() {
        return overrides;
    }

    /** One stack's worth of state, waiting to be told which display context to draw in. */
    private static final class Bound implements BakedModel {
        private final DefinitionModel parent;
        private final ItemDefinition.State state;
        private final BakedModel gui;

        Bound(DefinitionModel parent, ItemDefinition.State state) {
            this.parent = parent;
            this.state = state;
            this.gui = parent.modelFor(ItemDisplayContext.GUI, state);
        }

        @Override
        public BakedModel applyTransform(ItemDisplayContext context, PoseStack poseStack, boolean leftHand) {
            BakedModel model = parent.modelFor(context, state);
            return model.applyTransform(context, poseStack, leftHand);
        }

        @Override
        public List<BakedQuad> getQuads(@Nullable BlockState blockState, @Nullable Direction side, RandomSource random) {
            return gui.getQuads(blockState, side, random);
        }

        @Override
        public boolean useAmbientOcclusion() {
            return gui.useAmbientOcclusion();
        }

        @Override
        public boolean isGui3d() {
            return gui.isGui3d();
        }

        @Override
        public boolean usesBlockLight() {
            return gui.usesBlockLight();
        }

        @Override
        public boolean isCustomRenderer() {
            return false;
        }

        @Override
        public TextureAtlasSprite getParticleIcon() {
            return gui.getParticleIcon();
        }

        @Override
        public ItemTransforms getTransforms() {
            return ItemTransforms.NO_TRANSFORMS;
        }

        @Override
        public ItemOverrides getOverrides() {
            return ItemOverrides.EMPTY;
        }
    }
}
