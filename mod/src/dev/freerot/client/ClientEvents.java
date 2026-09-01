package dev.freerot.client;

import dev.freerot.FreeRot;
import net.minecraft.client.Minecraft;
import net.minecraft.client.renderer.item.ItemProperties;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.item.ItemStack;
import net.neoforged.api.distmarker.Dist;
import net.neoforged.bus.api.SubscribeEvent;
import net.neoforged.fml.common.EventBusSubscriber;
import net.neoforged.fml.event.lifecycle.FMLClientSetupEvent;
import net.neoforged.neoforge.client.event.ModelEvent;

@EventBusSubscriber(modid = FreeRot.MOD_ID, bus = EventBusSubscriber.Bus.MOD, value = Dist.CLIENT)
public final class ClientEvents {
    private ClientEvents() {
    }

    @SubscribeEvent
    public static void registerGeometryLoaders(ModelEvent.RegisterGeometryLoaders event) {
        event.register(id("mesh"), MeshLoader.INSTANCE);
    }

    @SubscribeEvent
    public static void clientSetup(FMLClientSetupEvent event) {
        event.enqueueWork(() -> {
            // 1 while the use key is held. 1.21.6+ packs express this as
            // "minecraft:keybind_down" with keybind "key.use".
            ItemProperties.registerGeneric(id("use_key"),
                    (stack, level, entity, seed) -> Minecraft.getInstance().options.keyUse.isDown() ? 1f : 0f);

            // 1 while this exact stack is the one being used (eating, drinking, blocking).
            ItemProperties.registerGeneric(id("using"),
                    (stack, level, entity, seed) -> isUsing(stack, entity) ? 1f : 0f);

            // Ticks of use left on this stack, mirroring "minecraft:use_duration" with
            // remaining = true. 0 when the stack is not in use.
            ItemProperties.registerGeneric(id("use_ticks"),
                    (stack, level, entity, seed) -> isUsing(stack, entity) ? entity.getUseItemRemainingTicks() : 0f);

            // 1 when the stack carries any enchantment, for packs that ship a separate
            // enchanted model ("minecraft:has_component" on minecraft:enchantments).
            ItemProperties.registerGeneric(id("enchanted"),
                    (stack, level, entity, seed) -> stack.isEnchanted() ? 1f : 0f);
        });
    }

    private static boolean isUsing(ItemStack stack, LivingEntity entity) {
        return entity != null && entity.isUsingItem() && entity.getUseItem() == stack;
    }

    private static ResourceLocation id(String path) {
        return ResourceLocation.fromNamespaceAndPath(FreeRot.MOD_ID, path);
    }
}
