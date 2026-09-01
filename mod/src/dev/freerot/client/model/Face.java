package dev.freerot.client.model;

/**
 * The vertex order and default uv rectangle the game uses for each face of an element,
 * plus the vertex permutation applied by a face's "rotation" field.
 *
 * <p>These tables have to match FaceBakery exactly or textures land rotated or mirrored.
 * They were verified against the converter's Python implementation, which reproduces the
 * original quads of 653 models with no mismatches.
 */
public enum Face {
    UP, DOWN, NORTH, SOUTH, EAST, WEST;

    private static final int[][] ROTATIONS = {
            {0, 3, 2, 3, 2, 1, 0, 1},        // 0
            {2, 3, 2, 1, 0, 1, 0, 3},        // 90
            {2, 1, 0, 1, 0, 3, 2, 3},        // 180
            {0, 1, 0, 3, 2, 3, 2, 1},        // 270
    };

    public static Face byName(String name) {
        return switch (name) {
            case "up" -> UP;
            case "down" -> DOWN;
            case "north" -> NORTH;
            case "south" -> SOUTH;
            case "east" -> EAST;
            case "west" -> WEST;
            default -> null;
        };
    }

    public static int[] rotationOrder(int degrees) {
        int index = ((degrees % 360) + 360) % 360 / 90;
        return ROTATIONS[index];
    }

    /** The four corners, in the order the game emits them. */
    public float[][] corners(float[] from, float[] to) {
        float x0 = from[0], y0 = from[1], z0 = from[2];
        float x1 = to[0], y1 = to[1], z1 = to[2];
        return switch (this) {
            case UP -> new float[][]{{x0, y1, z1}, {x1, y1, z1}, {x1, y1, z0}, {x0, y1, z0}};
            case DOWN -> new float[][]{{x0, y0, z0}, {x1, y0, z0}, {x1, y0, z1}, {x0, y0, z1}};
            case SOUTH -> new float[][]{{x0, y0, z1}, {x1, y0, z1}, {x1, y1, z1}, {x0, y1, z1}};
            case NORTH -> new float[][]{{x1, y0, z0}, {x0, y0, z0}, {x0, y1, z0}, {x1, y1, z0}};
            case EAST -> new float[][]{{x1, y0, z1}, {x1, y0, z0}, {x1, y1, z0}, {x1, y1, z1}};
            case WEST -> new float[][]{{x0, y0, z0}, {x0, y0, z1}, {x0, y1, z1}, {x0, y1, z0}};
        };
    }

    /** The uv rectangle used when a face does not declare one. */
    public float[] defaultUv(float[] from, float[] to) {
        float x0 = from[0], y0 = from[1], z0 = from[2];
        float x1 = to[0], y1 = to[1], z1 = to[2];
        return switch (this) {
            case UP -> new float[]{x0, 16 - z1, x1, 16 - z0};
            case DOWN -> new float[]{16 - z1, 16 - x1, 16 - z0, 16 - x0};
            case SOUTH -> new float[]{x0, 16 - y1, x1, 16 - y0};
            case NORTH -> new float[]{16 - x1, 16 - y1, 16 - x0, 16 - y0};
            case EAST -> new float[]{16 - z1, 16 - y1, 16 - z0, 16 - y0};
            case WEST -> new float[]{z0, 16 - y1, z1, 16 - y0};
        };
    }
}
