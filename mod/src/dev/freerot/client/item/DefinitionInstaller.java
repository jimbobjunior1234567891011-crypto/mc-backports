package dev.freerot.client.item;

import com.google.gson.JsonObject;
import com.google.gson.JsonParser;
import com.mojang.logging.LogUtils;
import dev.freerot.client.model.ModelSource;
import net.minecraft.client.Minecraft;
import net.minecraft.client.resources.model.BlockModelRotation;
import net.minecraft.client.renderer.texture.TextureAtlasSprite;
import net.minecraft.client.resources.model.BakedModel;
import net.minecraft.client.resources.model.Material;
import net.minecraft.client.resources.model.ModelResourceLocation;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.server.packs.resources.Resource;
import net.minecraft.server.packs.resources.ResourceManager;
import org.slf4j.Logger;

import java.io.InputStreamReader;
import java.util.HashMap;
import java.util.HashSet;
import java.util.Map;
import java.util.Set;
import java.util.function.Function;

/**
 * Finds every item a resource pack defines the 1.21.4+ way and replaces the baked model
 * for that item with one that understands it.
 *
 * <p>This runs after baking, which is what makes it cheap: the game has already produced
 * the ordinary 2D model for the item, so that is reused as-is for the inventory rather
 * than rebuilt, and the pack's own 3D models are baked here because the game refused to
 * parse them.
 */
public final class DefinitionInstaller {
    private static final Logger LOG = LogUtils.getLogger();

    private DefinitionInstaller() {
    }

    public static void install(Map<ModelResourceLocation, BakedModel> bakedModels,
                               Function<Material, TextureAtlasSprite> sprites) {
        ResourceManager resources = Minecraft.getInstance().getResourceManager();
        Map<ResourceLocation, Resource> definitions =
                resources.listResources("items", path -> path.getPath().endsWith(".json"));
        if (definitions.isEmpty()) {
            return;
        }

        Map<String, BakedModel> cache = new HashMap<>();
        int converted = 0;
        int skipped = 0;

        for (Map.Entry<ResourceLocation, Resource> entry : definitions.entrySet()) {
            ResourceLocation location = entry.getKey();
            String path = location.getPath();
            String itemId = path.substring("items/".length(), path.length() - ".json".length());
            ModelResourceLocation target = ModelResourceLocation.inventory(
                    ResourceLocation.fromNamespaceAndPath(location.getNamespace(), itemId));

            BakedModel vanilla = bakedModels.get(target);
            if (vanilla == null) {
                skipped++;                                     // item does not exist in this version
                continue;
            }

            ItemDefinition definition;
            try (InputStreamReader reader = new InputStreamReader(entry.getValue().open())) {
                JsonObject json = JsonParser.parseReader(reader).getAsJsonObject();
                definition = ItemDefinition.parse(json);
            } catch (Exception exception) {
                LOG.warn("[freerot] could not read {}: {}", location, exception.toString());
                continue;
            }
            if (definition == null) {
                continue;
            }

            Set<String> referenced = new HashSet<>();
            definition.collect(referenced);
            Map<String, BakedModel> models = new HashMap<>();
            for (String reference : referenced) {
                BakedModel model = cache.computeIfAbsent(reference, key -> {
                    try {
                        return ModelSource.bake(ResourceLocation.parse(key), resources, sprites,
                                BlockModelRotation.X0_Y0);
                    } catch (Exception exception) {
                        LOG.warn("[freerot] could not bake {}: {}", key, exception.toString());
                        return null;
                    }
                });
                if (model != null) {
                    models.put(reference, model);
                }
            }
            if (models.isEmpty()) {
                continue;                                      // nothing but flat models: leave it alone
            }

            bakedModels.put(target, new DefinitionModel(definition, models, vanilla));
            converted++;
        }

        LOG.info("[freerot] {} item definitions applied, {} skipped as not present in this version",
                converted, skipped);
    }
}
