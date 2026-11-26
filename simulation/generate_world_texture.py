#!/usr/bin/env python3
"""Generate a high-contrast multi-scale ground texture for Gazebo Harmonic optical flow."""

from pathlib import Path
import numpy as np
from PIL import Image


def generate_ground_texture(output_path: Path, size: int = 2048) -> None:
    rng = np.random.default_rng(42)

    # Base warm concrete/soil tone
    base = np.zeros((size, size, 3), dtype=np.float32)
    base[:, :, 0] = 115.0
    base[:, :, 1] = 122.0
    base[:, :, 2] = 104.0

    # Multi-scale smooth value noise for natural terrain variation
    for scale, amp in [(16, 26.0), (64, 22.0), (256, 16.0), (512, 12.0)]:
        coarse = rng.uniform(-amp, amp, size=(scale, scale, 1)).astype(np.float32)
        pil_noise = Image.fromarray(np.clip(coarse[:, :, 0] + 128.0, 0, 255).astype(np.uint8), mode="L")
        upsampled = np.asarray(pil_noise.resize((size, size), Image.Resampling.BILINEAR), dtype=np.float32) - 128.0
        base += upsampled[:, :, None]

    # Fine aggregate grain for close-range (0.5m - 5m) optical flow tracking
    grain = rng.normal(0.0, 14.0, size=(size, size, 1)).astype(np.float32)
    base += grain

    # Crisp geometric tile/runway grid lines + checker contrast blocks
    step = size // 16  # 128 px grid
    for i in range(0, size, step):
        base[i:i + 4, :, :] *= 0.62
        base[:, i:i + 4, :] *= 0.62

    sub_step = size // 32  # 64 px sub-grid
    for i in range(0, size, sub_step):
        base[i:i + 2, :, :] *= 0.84
        base[:, i:i + 2, :] *= 0.84

    # Scatter high-contrast textured patches (simulated turf / gravel / markers)
    for _ in range(320):
        cx = int(rng.integers(0, size))
        cy = int(rng.integers(0, size))
        rx = int(rng.integers(8, 36))
        ry = int(rng.integers(8, 36))
        tint = rng.choice([-38.0, 34.0])
        x0, x1 = max(0, cx - rx), min(size, cx + rx)
        y0, y1 = max(0, cy - ry), min(size, cy + ry)
        base[y0:y1, x0:x1, 0] += tint * 0.8
        base[y0:y1, x0:x1, 1] += tint * 1.0
        base[y0:y1, x0:x1, 2] += tint * 0.7

    img_u8 = np.clip(base, 0, 255).astype(np.uint8)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img_u8, mode="RGB").save(output_path)
    print(f"Generated ground texture: {output_path} ({size}x{size})")


if __name__ == "__main__":
    out = Path(__file__).resolve().parent / "models" / "textured_ground" / "materials" / "textures" / "ground_albedo.png"
    generate_ground_texture(out)
