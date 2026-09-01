package dev.freerot.client.item;

import com.google.gson.JsonArray;
import com.google.gson.JsonElement;
import com.google.gson.JsonObject;
import net.minecraft.client.Minecraft;
import net.minecraft.client.multiplayer.ClientLevel;
import net.minecraft.client.renderer.item.ItemProperties;
import net.minecraft.client.renderer.item.ItemPropertyFunction;
import net.minecraft.core.component.DataComponentType;
import net.minecraft.core.registries.BuiltInRegistries;
import net.minecraft.resources.ResourceLocation;
import net.minecraft.world.entity.LivingEntity;
import net.minecraft.world.entity.player.Player;
import net.minecraft.world.item.ItemDisplayContext;
import net.minecraft.world.item.ItemStack;

import java.util.ArrayList;
import java.util.EnumMap;
import java.util.List;
import java.util.Map;
import java.util.Set;

/**
 * The 1.21.4+ item model definition (assets/minecraft/items/&lt;id&gt;.json), read and
 * evaluated live.
 *
 * <p>1.21.1 does not have this layer at all - it maps an item id straight to
 * models/item/&lt;id&gt;.json - so every pack that uses it does nothing on its own. Here
 * the tree is walked per render against the real state of the stack, which is closer to
 * the original than pre-generating a model per reachable state.
 *
 * <p>Properties with no 1.21.1 equivalent are answered from the game where one exists
 * (compass angle, clock time) and from the mod's own item properties otherwise.
 */
public abstract class ItemDefinition {

    /** Everything an evaluation needs about the stack being drawn. */
    public record State(ItemStack stack, ClientLevel level, LivingEntity entity, int seed) {
        boolean usingThisStack() {
            return entity != null && entity.isUsingItem() && entity.getUseItem() == stack;
        }

        float property(String name) {
            ItemPropertyFunction function = ItemProperties.getProperty(stack, ResourceLocation.parse(name));
            return function == null ? 0f : function.call(stack, level, entity, seed);
        }
    }

    public abstract String resolve(ItemDisplayContext context, State state);

    public abstract void collect(Set<String> models);

    // ------------------------------------------------------------------ parsing
    public static ItemDefinition parse(JsonObject root) {
        JsonElement model = root.get("model");
        return model != null && model.isJsonObject() ? node(model.getAsJsonObject()) : null;
    }

    private static ItemDefinition node(JsonObject json) {
        String type = json.has("type") ? json.get("type").getAsString() : "";
        switch (type) {
            case "minecraft:model", "model" -> {
                return new Fixed(json.get("model").getAsString());
            }
            case "minecraft:select", "select" -> {
                return select(json);
            }
            case "minecraft:condition", "condition" -> {
                return new Condition(json,
                        child(json, "on_true"), child(json, "on_false"));
            }
            case "minecraft:range_dispatch", "range_dispatch" -> {
                return new Range(json);
            }
            default -> {
                return null;                                   // special, empty, bundles
            }
        }
    }

    private static ItemDefinition child(JsonObject json, String key) {
        JsonObject sub = json.getAsJsonObject(key);
        return sub == null ? null : node(sub);
    }

    private static ItemDefinition select(JsonObject json) {
        String property = json.has("property") ? json.get("property").getAsString() : "";
        JsonArray cases = json.getAsJsonArray("cases");
        ItemDefinition fallback = child(json, "fallback");

        if (property.endsWith("display_context")) {
            Map<ItemDisplayContext, ItemDefinition> byContext = new EnumMap<>(ItemDisplayContext.class);
            if (cases != null) {
                for (JsonElement element : cases) {
                    JsonObject entry = element.getAsJsonObject();
                    ItemDefinition target = child(entry, "model");
                    JsonElement when = entry.get("when");
                    if (when == null || target == null) {
                        continue;
                    }
                    if (when.isJsonArray()) {
                        for (JsonElement name : when.getAsJsonArray()) {
                            put(byContext, name.getAsString(), target);
                        }
                    } else {
                        put(byContext, when.getAsString(), target);
                    }
                }
            }
            return new ByContext(byContext, fallback);
        }

        // any other select (item components, dimension): no state for it, so take the
        // fallback, or the first branch when there is none
        if (fallback == null && cases != null && !cases.isEmpty()) {
            fallback = child(cases.get(0).getAsJsonObject(), "model");
        }
        return fallback;
    }

    private static void put(Map<ItemDisplayContext, ItemDefinition> map, String name, ItemDefinition target) {
        for (ItemDisplayContext context : ItemDisplayContext.values()) {
            if (context.getSerializedName().equals(name)) {
                map.put(context, target);
                return;
            }
        }
    }

    // ------------------------------------------------------------------ node types
    private static final class Fixed extends ItemDefinition {
        private final String model;

        Fixed(String model) {
            this.model = model.contains(":") ? model : "minecraft:" + model;
        }

        @Override
        public String resolve(ItemDisplayContext context, State state) {
            return model;
        }

        @Override
        public void collect(Set<String> models) {
            models.add(model);
        }
    }

    private static final class ByContext extends ItemDefinition {
        private final Map<ItemDisplayContext, ItemDefinition> cases;
        private final ItemDefinition fallback;

        ByContext(Map<ItemDisplayContext, ItemDefinition> cases, ItemDefinition fallback) {
            this.cases = cases;
            this.fallback = fallback;
        }

        @Override
        public String resolve(ItemDisplayContext context, State state) {
            ItemDefinition chosen = cases.getOrDefault(context, fallback);
            return chosen == null ? null : chosen.resolve(context, state);
        }

        @Override
        public void collect(Set<String> models) {
            cases.values().forEach(node -> node.collect(models));
            if (fallback != null) {
                fallback.collect(models);
            }
        }
    }

    private static final class Condition extends ItemDefinition {
        private final String property;
        private final String component;
        private final String keybind;
        private final boolean ignoreDefault;
        private final ItemDefinition onTrue;
        private final ItemDefinition onFalse;

        Condition(JsonObject json, ItemDefinition onTrue, ItemDefinition onFalse) {
            this.property = json.has("property") ? json.get("property").getAsString() : "";
            this.component = json.has("component") ? json.get("component").getAsString() : null;
            this.keybind = json.has("keybind") ? json.get("keybind").getAsString() : null;
            this.ignoreDefault = json.has("ignore_default") && json.get("ignore_default").getAsBoolean();
            this.onTrue = onTrue;
            this.onFalse = onFalse;
        }

        @Override
        public String resolve(ItemDisplayContext context, State state) {
            ItemDefinition chosen = test(state) ? onTrue : onFalse;
            return chosen == null ? null : chosen.resolve(context, state);
        }

        private boolean test(State state) {
            return switch (property) {
                case "minecraft:using_item" -> state.usingThisStack();
                case "minecraft:keybind_down" -> "key.use".equals(keybind)
                        && Minecraft.getInstance().options.keyUse.isDown();
                case "minecraft:has_component" -> hasComponent(state);
                case "minecraft:fishing_rod/cast" -> state.entity() instanceof Player player
                        && player.fishing != null;
                case "minecraft:broken" -> state.stack().isDamageableItem()
                        && state.stack().getDamageValue() >= state.stack().getMaxDamage() - 1;
                case "minecraft:damaged" -> state.stack().isDamaged();
                default -> false;
            };
        }

        private boolean hasComponent(State state) {
            if (component == null) {
                return false;
            }
            DataComponentType<?> type = BuiltInRegistries.DATA_COMPONENT_TYPE
                    .get(ResourceLocation.parse(component));
            if (type == null) {
                return false;
            }
            Object value = state.stack().get(type);
            if (value == null) {
                return false;
            }
            if (!ignoreDefault) {
                return true;
            }
            Object standard = state.stack().getItem().components().get(type);
            return !value.equals(standard);
        }

        @Override
        public void collect(Set<String> models) {
            if (onTrue != null) {
                onTrue.collect(models);
            }
            if (onFalse != null) {
                onFalse.collect(models);
            }
        }
    }

    private static final class Range extends ItemDefinition {
        private record Entry(float threshold, ItemDefinition model) {
        }

        private final String property;
        private final float scale;
        private final boolean remaining;
        private final List<Entry> entries = new ArrayList<>();
        private final ItemDefinition fallback;

        Range(JsonObject json) {
            this.property = json.has("property") ? json.get("property").getAsString() : "";
            this.scale = json.has("scale") ? json.get("scale").getAsFloat() : 1f;
            this.remaining = json.has("remaining") && json.get("remaining").getAsBoolean();
            this.fallback = child(json, "fallback");
            JsonArray array = json.getAsJsonArray("entries");
            if (array != null) {
                for (JsonElement element : array) {
                    JsonObject entry = element.getAsJsonObject();
                    ItemDefinition target = child(entry, "model");
                    if (target != null) {
                        entries.add(new Entry(entry.get("threshold").getAsFloat(), target));
                    }
                }
            }
            entries.sort((a, b) -> Float.compare(a.threshold(), b.threshold()));
        }

        @Override
        public String resolve(ItemDisplayContext context, State state) {
            float value = value(state);
            ItemDefinition chosen = null;
            for (Entry entry : entries) {
                if (entry.threshold() <= value) {
                    chosen = entry.model();
                }
            }
            if (chosen == null) {
                // below every threshold: the game falls back, or shows the lowest entry
                chosen = fallback != null ? fallback : (entries.isEmpty() ? null : entries.get(0).model());
            }
            return chosen == null ? null : chosen.resolve(context, state);
        }

        private float value(State state) {
            return switch (property) {
                case "minecraft:use_duration" -> {
                    if (!state.usingThisStack()) {
                        yield 0f;
                    }
                    int ticks = remaining
                            ? state.entity().getUseItemRemainingTicks()
                            : state.stack().getUseDuration(state.entity()) - state.entity().getUseItemRemainingTicks();
                    yield ticks * scale;
                }
                case "minecraft:compass" -> state.property("minecraft:angle") * scale;
                case "minecraft:time" -> state.property("minecraft:time") * scale;
                case "minecraft:damage" -> state.stack().getMaxDamage() == 0 ? 0f
                        : (float) state.stack().getDamageValue() / state.stack().getMaxDamage() * scale;
                case "minecraft:count" -> state.stack().getMaxStackSize() == 0 ? 0f
                        : (float) state.stack().getCount() / state.stack().getMaxStackSize() * scale;
                case "minecraft:crossbow/pull", "minecraft:bow/pull" -> state.property("minecraft:pull") * scale;
                default -> 0f;
            };
        }

        @Override
        public void collect(Set<String> models) {
            entries.forEach(entry -> entry.model().collect(models));
            if (fallback != null) {
                fallback.collect(models);
            }
        }
    }
}
