package dev.freerot;

import net.neoforged.api.distmarker.Dist;
import net.neoforged.fml.common.Mod;

/**
 * Client-side support mod for resource packs authored for 1.21.4+ item models.
 *
 * <p>It adds two things 1.21.1 lacks:
 * <ul>
 *   <li>a model loader that accepts element rotations of any angle around any combination
 *       of axes, which vanilla 1.21.1 rejects outright;</li>
 *   <li>item model properties for "use key held", "is enchanted" and "use ticks
 *       remaining", so packs can swap models on those states through plain overrides.</li>
 * </ul>
 */
@Mod(value = FreeRot.MOD_ID, dist = Dist.CLIENT)
public class FreeRot {
    public static final String MOD_ID = "freerot";

    public FreeRot() {
    }
}
