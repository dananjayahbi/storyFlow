"""
Image Upscaler — GAN-based image super-resolution using Real-ESRGAN.

Self-contained implementation that loads Real-ESRGAN ``.pth`` weights
directly via PyTorch, without requiring the ``realesrgan`` or ``basicsr``
packages (which have compatibility issues with Python ≥ 3.13).

The RRDB network architecture (Residual-in-Residual Dense Block) is
defined inline — it is a well-known architecture from the ESRGAN paper.

Supported models (pre-downloaded to ``models/upscalers/``):

- ``RealESRGAN_x4plus``           — 4× general-purpose (best quality)
- ``RealESRGAN_x2plus``           — 2× general-purpose
- ``RealESRGAN_x4plus_anime_6B``  — 4× optimised for anime / illustration

Dependencies:
    - ``torch`` (CPU or CUDA)
    - ``numpy``
    - ``opencv-python-headless``
"""

import logging
import math
import os
import threading
from pathlib import Path
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Registry of supported models
# ---------------------------------------------------------------------------

MODEL_REGISTRY = {
    "RealESRGAN_x4plus": {
        "filename": "RealESRGAN_x4plus.pth",
        "scale": 4,
        "num_block": 23,
        "num_grow_ch": 32,
        "description": "Real-ESRGAN x4 — Best general-purpose upscaler",
    },
    "RealESRGAN_x2plus": {
        "filename": "RealESRGAN_x2plus.pth",
        "scale": 2,
        "num_block": 23,
        "num_grow_ch": 32,
        "description": "Real-ESRGAN x2 — Moderate upscale, faster",
    },
    "RealESRGAN_x4plus_anime_6B": {
        "filename": "RealESRGAN_x4plus_anime_6B.pth",
        "scale": 4,
        "num_block": 6,
        "num_grow_ch": 32,
        "description": "Real-ESRGAN x4 Anime — Optimised for illustrations",
    },
}

# ---------------------------------------------------------------------------
# Resolve models directory
# ---------------------------------------------------------------------------

_MODELS_DIR = Path(__file__).resolve().parent.parent.parent / "models" / "upscalers"


def get_models_dir() -> Path:
    """Return the absolute path to the upscaler models directory."""
    return _MODELS_DIR


def get_available_models() -> list[dict]:
    """Return a list of models whose weight files are present on disk."""
    available = []
    for name, info in MODEL_REGISTRY.items():
        model_path = _MODELS_DIR / info["filename"]
        available.append({
            "name": name,
            "filename": info["filename"],
            "scale": info["scale"],
            "description": info["description"],
            "available": model_path.is_file(),
            "file_size": model_path.stat().st_size if model_path.is_file() else 0,
        })
    return available


# ═══════════════════════════════════════════════════════════════════════════
# RRDBNet Architecture (from ESRGAN paper, implemented inline)
# ═══════════════════════════════════════════════════════════════════════════

_TORCH_AVAILABLE = False

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F

    _TORCH_AVAILABLE = True

    class ResidualDenseBlock(nn.Module):
        """Residual Dense Block with 5 convolutional layers."""

        def __init__(self, num_feat=64, num_grow_ch=32):
            super().__init__()
            self.conv1 = nn.Conv2d(num_feat, num_grow_ch, 3, 1, 1)
            self.conv2 = nn.Conv2d(num_feat + num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv3 = nn.Conv2d(num_feat + 2 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv4 = nn.Conv2d(num_feat + 3 * num_grow_ch, num_grow_ch, 3, 1, 1)
            self.conv5 = nn.Conv2d(num_feat + 4 * num_grow_ch, num_feat, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        def forward(self, x):
            x1 = self.lrelu(self.conv1(x))
            x2 = self.lrelu(self.conv2(torch.cat((x, x1), 1)))
            x3 = self.lrelu(self.conv3(torch.cat((x, x1, x2), 1)))
            x4 = self.lrelu(self.conv4(torch.cat((x, x1, x2, x3), 1)))
            x5 = self.conv5(torch.cat((x, x1, x2, x3, x4), 1))
            return x5 * 0.2 + x

    class RRDB(nn.Module):
        """Residual in Residual Dense Block (3 cascaded RDBs)."""

        def __init__(self, num_feat, num_grow_ch=32):
            super().__init__()
            self.rdb1 = ResidualDenseBlock(num_feat, num_grow_ch)
            self.rdb2 = ResidualDenseBlock(num_feat, num_grow_ch)
            self.rdb3 = ResidualDenseBlock(num_feat, num_grow_ch)

        def forward(self, x):
            out = self.rdb1(x)
            out = self.rdb2(out)
            out = self.rdb3(out)
            return out * 0.2 + x

    def _pixel_unshuffle(x, scale):
        """Rearrange spatial dims into channels (inverse of pixel shuffle)."""
        b, c, h, w = x.shape
        assert h % scale == 0 and w % scale == 0
        h2, w2 = h // scale, w // scale
        x = x.view(b, c, h2, scale, w2, scale)
        x = x.permute(0, 1, 3, 5, 2, 4).contiguous()
        return x.view(b, c * scale * scale, h2, w2)

    class RRDBNet(nn.Module):
        """RRDBNet architecture used by Real-ESRGAN."""

        def __init__(self, num_in_ch=3, num_out_ch=3, scale=4,
                     num_feat=64, num_block=23, num_grow_ch=32):
            super().__init__()
            self.scale = scale

            # For scale==2: pixel-unshuffle input (3→12 ch, halve spatial),
            # then use scale=4 upsampling (net 2×)
            if scale == 2:
                num_in_ch = num_in_ch * 4
            num_upsample = int(math.log2(4))  # always 2 upsample steps

            self.conv_first = nn.Conv2d(num_in_ch, num_feat, 3, 1, 1)
            self.body = nn.Sequential(
                *[RRDB(num_feat, num_grow_ch) for _ in range(num_block)]
            )
            self.conv_body = nn.Conv2d(num_feat, num_feat, 3, 1, 1)

            # Upsampling layers — named conv_up1, conv_up2, etc.
            # to match the Real-ESRGAN checkpoint key names
            for i in range(1, num_upsample + 1):
                setattr(self, f'conv_up{i}',
                        nn.Conv2d(num_feat, num_feat, 3, 1, 1))
            self._num_upsample = num_upsample

            self.conv_hr = nn.Conv2d(num_feat, num_feat, 3, 1, 1)
            self.conv_last = nn.Conv2d(num_feat, num_out_ch, 3, 1, 1)
            self.lrelu = nn.LeakyReLU(negative_slope=0.2, inplace=True)

        def forward(self, x):
            if self.scale == 2:
                x = _pixel_unshuffle(x, scale=2)

            feat = self.conv_first(x)
            body_feat = self.conv_body(self.body(feat))
            feat = feat + body_feat

            for i in range(1, self._num_upsample + 1):
                feat = self.lrelu(getattr(self, f'conv_up{i}')(F.interpolate(
                    feat, scale_factor=2, mode='nearest',
                )))

            out = self.conv_last(self.lrelu(self.conv_hr(feat)))
            return out

except ImportError:
    logger.warning("PyTorch not installed — image upscaling disabled.")


# ═══════════════════════════════════════════════════════════════════════════
# Upscaler wrapper (tile-based inference)
# ═══════════════════════════════════════════════════════════════════════════

class _UpscalerInstance:
    """Wraps a loaded RRDBNet model and provides tile-based inference."""

    def __init__(self, model_name: str, device):
        info = MODEL_REGISTRY[model_name]
        self.scale = info["scale"]
        self.device = device

        # Build architecture
        self.model = RRDBNet(
            num_in_ch=3, num_out_ch=3, scale=info["scale"],
            num_feat=64, num_block=info["num_block"],
            num_grow_ch=info["num_grow_ch"],
        )

        # Load weights
        model_path = _MODELS_DIR / info["filename"]
        state_dict = torch.load(
            str(model_path), map_location=device, weights_only=True,
        )

        # Handle wrapped state dicts: {params_ema: ..., params: ...}
        if "params_ema" in state_dict:
            state_dict = state_dict["params_ema"]
        elif "params" in state_dict:
            state_dict = state_dict["params"]

        self.model.load_state_dict(state_dict, strict=True)
        self.model.eval().to(device)

        # FP16 on GPU for speed
        self.half = device.type == "cuda"
        if self.half:
            self.model.half()

        logger.info(
            "Loaded upscaler: %s on %s (scale=%d, half=%s)",
            model_name, device, self.scale, self.half,
        )

    @torch.no_grad()
    def enhance(self, img_bgr: np.ndarray,
                tile_size: int = 512, tile_pad: int = 10,
                pre_pad: int = 10) -> np.ndarray:
        """Upscale a BGR uint8 image using tiled inference."""
        # For scale==2, ensure pre_pad is even (pixel unshuffle needs it)
        if self.scale == 2 and pre_pad % 2 != 0:
            pre_pad += 1

        # BGR → RGB float32 tensor
        img = img_bgr.astype(np.float32) / 255.0
        img = img[:, :, ::-1].copy()  # BGR → RGB
        tensor = torch.from_numpy(img).permute(2, 0, 1).unsqueeze(0)

        if self.half:
            tensor = tensor.half()
        tensor = tensor.to(self.device)

        # For scale==2, ensure spatial dims are even for pixel unshuffle
        _, _, orig_h, orig_w = tensor.shape
        mod_h = orig_h % 2
        mod_w = orig_w % 2
        if mod_h or mod_w:
            tensor = F.pad(tensor, (0, mod_w, 0, mod_h), mode='reflect')

        # Pre-pad with reflection
        if pre_pad > 0:
            tensor = F.pad(tensor, (pre_pad,) * 4, mode='reflect')

        _, _, h, w = tensor.shape

        # Process in tiles or as a whole
        if tile_size <= 0 or (h <= tile_size and w <= tile_size):
            output = self.model(tensor)
        else:
            output = self._tile_process(tensor, tile_size, tile_pad)

        # Remove pre-pad from output
        if pre_pad > 0:
            pp = pre_pad * self.scale
            output = output[:, :, pp:-pp, pp:-pp]

        # Remove mod-pad if applied
        out_h = orig_h * self.scale
        out_w = orig_w * self.scale
        output = output[:, :, :out_h, :out_w]

        # Tensor → numpy BGR uint8
        result = output.squeeze(0).float().clamp(0, 1).cpu().numpy()
        result = result.transpose(1, 2, 0)       # CHW → HWC
        result = result[:, :, ::-1].copy()        # RGB → BGR
        result = (result * 255.0).round().astype(np.uint8)
        return result

    def _tile_process(self, img: 'torch.Tensor',
                      tile_size: int, tile_pad: int) -> 'torch.Tensor':
        """Process a large image in overlapping tiles."""
        _, _, h, w = img.shape
        out_h, out_w = h * self.scale, w * self.scale
        output = img.new_zeros((1, 3, out_h, out_w))

        tiles_y = math.ceil(h / tile_size)
        tiles_x = math.ceil(w / tile_size)

        for iy in range(tiles_y):
            for ix in range(tiles_x):
                ofs_y = min(iy * tile_size, h - tile_size) if h > tile_size else 0
                ofs_x = min(ix * tile_size, w - tile_size) if w > tile_size else 0

                inp_sy = max(ofs_y - tile_pad, 0)
                inp_ey = min(ofs_y + tile_size + tile_pad, h)
                inp_sx = max(ofs_x - tile_pad, 0)
                inp_ex = min(ofs_x + tile_size + tile_pad, w)

                tile_in = img[:, :, inp_sy:inp_ey, inp_sx:inp_ex]
                tile_out = self.model(tile_in)

                out_sy = (ofs_y - inp_sy) * self.scale
                out_sx = (ofs_x - inp_sx) * self.scale
                act_h = min(tile_size * self.scale, out_h - ofs_y * self.scale)
                act_w = min(tile_size * self.scale, out_w - ofs_x * self.scale)

                output[
                    :, :,
                    ofs_y * self.scale: ofs_y * self.scale + act_h,
                    ofs_x * self.scale: ofs_x * self.scale + act_w,
                ] = tile_out[
                    :, :,
                    out_sy: out_sy + act_h,
                    out_sx: out_sx + act_w,
                ]

        return output


# ═══════════════════════════════════════════════════════════════════════════
# Thread-safe singleton cache
# ═══════════════════════════════════════════════════════════════════════════

_upscaler_cache: dict[str, Optional[_UpscalerInstance]] = {}
_cache_lock = threading.Lock()


def _get_upscaler(model_name: str) -> Optional['_UpscalerInstance']:
    """Return a cached upscaler, creating one if needed."""
    if not _TORCH_AVAILABLE:
        return None

    if model_name in _upscaler_cache:
        return _upscaler_cache[model_name]

    with _cache_lock:
        if model_name in _upscaler_cache:
            return _upscaler_cache[model_name]

        info = MODEL_REGISTRY.get(model_name)
        if not info:
            logger.error("Unknown upscaler model: %s", model_name)
            return None

        model_path = _MODELS_DIR / info["filename"]
        if not model_path.is_file():
            logger.error("Model file not found: %s", model_path)
            return None

        try:
            device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
            inst = _UpscalerInstance(model_name, device)
            _upscaler_cache[model_name] = inst
            return inst
        except Exception as exc:
            logger.error("Failed to load upscaler %s: %s", model_name, exc)
            return None


# ═══════════════════════════════════════════════════════════════════════════
# Public API
# ═══════════════════════════════════════════════════════════════════════════

def upscale_image(
    image_path: str,
    output_path: str,
    model_name: str = "RealESRGAN_x4plus",
    denoise_strength: float = 0.5,
) -> str:
    """
    Upscale a single image using the specified Real-ESRGAN model.

    Args:
        image_path: Path to the source image.
        output_path: Path where the upscaled image will be saved.
        model_name: Which model to use (see ``MODEL_REGISTRY``).
        denoise_strength: Denoise strength (0–1). Currently informational;
            the model architecture determines denoising.

    Returns:
        ``output_path`` on success, or ``image_path`` if unavailable.
    """
    upscaler = _get_upscaler(model_name)
    if upscaler is None:
        logger.warning("Upscaler unavailable — returning original: %s", image_path)
        return image_path

    img = cv2.imread(image_path, cv2.IMREAD_UNCHANGED)
    if img is None:
        logger.error("Failed to read image for upscaling: %s", image_path)
        return image_path

    # Convert RGBA → BGR if needed
    if img.ndim == 3 and img.shape[2] == 4:
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    try:
        output = upscaler.enhance(img, tile_size=512, tile_pad=10, pre_pad=10)
    except Exception as exc:
        logger.error("Upscaling failed for %s: %s", image_path, exc)
        return image_path

    os.makedirs(os.path.dirname(output_path) or ".", exist_ok=True)
    cv2.imwrite(output_path, output)

    logger.info(
        "Upscaled %s → %s (%dx%d → %dx%d)",
        os.path.basename(image_path),
        os.path.basename(output_path),
        img.shape[1], img.shape[0],
        output.shape[1], output.shape[0],
    )

    return output_path


def upscale_images_batch(
    image_paths: list[str],
    output_dir: str,
    model_name: str = "RealESRGAN_x4plus",
    denoise_strength: float = 0.5,
    on_progress: Optional[callable] = None,
) -> dict[str, str]:
    """
    Upscale a batch of images, returning a mapping of original → upscaled paths.

    Args:
        image_paths: List of source image paths.
        output_dir: Directory for upscaled outputs.
        model_name: Model name key.
        denoise_strength: Denoise strength (0–1).
        on_progress: Optional callback ``(current, total, message)``.

    Returns:
        Dict mapping each original path to its upscaled output path.
    """
    total = len(image_paths)
    results: dict[str, str] = {}

    os.makedirs(output_dir, exist_ok=True)

    for idx, src_path in enumerate(image_paths):
        filename = os.path.basename(src_path)
        name, ext = os.path.splitext(filename)
        out_path = os.path.join(output_dir, f"{name}_upscaled{ext}")

        if on_progress:
            on_progress(idx, total, f"Upscaling image {idx + 1}/{total}")

        results[src_path] = upscale_image(
            src_path, out_path, model_name, denoise_strength,
        )

    if on_progress:
        on_progress(total, total, "Image upscaling complete")

    return results


def clear_cache():
    """Clear all cached upscaler instances to free memory."""
    with _cache_lock:
        _upscaler_cache.clear()
    logger.info("Upscaler cache cleared")
