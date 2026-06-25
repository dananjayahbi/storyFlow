# Feature 1.5 — ONNX Runtime Path for Image Upscaling

> **Status:** Planned  
> **Category:** Core Engine / Upscaling Performance & Dependency Reduction  
> **Target Files:** `backend/core_engine/image_upscaler.py`, `backend/core_engine/export_upscaler_onnx.py` (new)  
> **Estimated Complexity:** Medium–High  
> **Expected Speedup:** 2–3× CPU inference; eliminates ~2 GB PyTorch runtime dependency  
> **Date Created:** March 10, 2026  

---

## Table of Contents

1. [Document Overview](#1-document-overview)
2. [Flow Diagram](#2-flow-diagram)
3. [Step-by-Step Instructions](#3-step-by-step-instructions)
4. [Expected Outcome](#4-expected-outcome)
5. [Verification Checklist](#5-verification-checklist)
6. [Notes for AI Agent](#6-notes-for-ai-agent)

---

## 1. Document Overview

### 1.1 Problem Statement

The current image upscaler in `backend/core_engine/image_upscaler.py`
(483 lines) uses **PyTorch** as its sole inference backend for
Real-ESRGAN super-resolution.  This creates two significant problems:

1. **Heavy dependency** — PyTorch weighs ~2 GB on disk (CPU build) or
   ~3.5 GB (CUDA build).  It is the single heaviest dependency in the
   entire StoryFlow project.  For users who only need CPU inference
   (the common case for upscaling small story images), this is an
   enormous cost for a single feature.

2. **Slow CPU inference** — PyTorch's CPU backend, while functional,
   is noticeably slower than ONNX Runtime for the same model
   architecture.  ONNX Runtime is specifically optimised for inference
   with graph-level optimisations, operator fusion, and platform-
   specific SIMD (AVX2/AVX-512) acceleration that PyTorch does not
   apply to eager-mode execution.

The project already has ONNX Runtime installed and actively used:

- `onnxruntime>=1.17.0` is listed in `backend/requirements.txt`
- `backend/core_engine/model_loader.py` (163 lines) implements a
  thread-safe singleton ONNX session loader for the Kokoro TTS model
- `backend/core_engine/tts_wrapper.py` uses `kokoro_onnx.Kokoro`
  which wraps ONNX Runtime sessions internally
- The `models/` directory already holds `kokoro-v0_19.onnx`

Therefore, the ONNX Runtime dependency is **zero additional cost** —
it is already installed and battle-tested in the codebase.

### 1.2 Proposed Solution

Add an **ONNX Runtime inference path** alongside the existing PyTorch
path in `image_upscaler.py`, with automatic selection based on which
model files are available on disk:

| Condition | Backend Used |
|---|---|
| `.onnx` file exists in `models/upscalers/` | ONNX Runtime |
| `.onnx` missing, `.pth` exists, PyTorch available | PyTorch (existing code) |
| Neither file available | Upscaling unavailable |

This approach:
- **Preserves backward compatibility** — existing `.pth` workflows
  remain completely untouched
- **Eliminates PyTorch as a required dependency** — once `.onnx` files
  are generated, users can uninstall PyTorch entirely
- **Achieves 2–3× faster CPU inference** — via ONNX Runtime's graph
  optimisations and operator fusion
- **Supports GPU via ONNX Runtime** — `CUDAExecutionProvider` gives
  GPU acceleration without PyTorch

Additionally, a new **export utility script** will be created at
`backend/core_engine/export_upscaler_onnx.py` to convert the existing
`.pth` weights to `.onnx` format.  This script requires PyTorch (one-
time usage) but the exported `.onnx` files can then be used without
PyTorch at runtime.

### 1.3 Current Architecture Reference

The existing PyTorch inference chain in `image_upscaler.py`:

```
_get_upscaler(model_name)                         # L349 — singleton cache
  └─ _UpscalerInstance.__init__(model_name, device) # L206
       ├─ RRDBNet(num_in_ch=3, ..., scale=4)        # L132 — inline architecture
       ├─ torch.load(weights_path)                   # L221 — load .pth
       ├─ model.load_state_dict(state_dict)          # L231
       └─ model.eval().to(device).half()             # L232-237

upscale_image(image_path, output_path, ...)        # L389
  ├─ cv2.imread()                                    # L409
  ├─ upscaler.enhance(img_bgr)                       # L419
  │    ├─ numpy → float32 → torch.Tensor             # L253-260
  │    ├─ Pre-pad with reflection                     # L270-271
  │    ├─ model(tensor) or _tile_process()            # L275-278
  │    ├─ Remove padding, tensor → numpy              # L281-296
  │    └─ Return BGR uint8 ndarray
  └─ cv2.imwrite()                                   # L426
```

Key line references in `image_upscaler.py` (483 lines total):

| Symbol | Line | Description |
|---|---|---|
| `MODEL_REGISTRY` | L39-62 | Dict of 3 model configs (scale, num_block, etc.) |
| `_MODELS_DIR` | L68 | `models/upscalers/` absolute path |
| `_TORCH_AVAILABLE` | L96 | Flag set by try/except import |
| `ResidualDenseBlock` | L96 | 5-conv dense block (PyTorch nn.Module) |
| `RRDB` | L112 | 3 × ResidualDenseBlock cascade |
| `RRDBNet` | L132 | Full network: conv_first → body(RRDB×N) → upsample → conv_last |
| `_UpscalerInstance` | L203 | Wrapper: loads weights, provides enhance() |
| `enhance()` | L243-296 | Preprocess → inference → postprocess |
| `_tile_process()` | L299-336 | 512×512 tile grid with 10px overlap |
| `_upscaler_cache` | L345 | Dict cache for singleton instances |
| `_cache_lock` | L346 | Threading lock for cache |
| `_get_upscaler()` | L349 | Double-checked locking factory |
| `upscale_image()` | L389 | Public: upscale single image file |
| `upscale_images_batch()` | L436 | Public: upscale list of images |
| `clear_cache()` | L478 | Public: free all cached instances |

### 1.4 ONNX Runtime in the Codebase

The existing ONNX Runtime pattern in `model_loader.py`:

```python
import onnxruntime as ort

class KokoroModelLoader:
    _session = None
    _lock = threading.Lock()

    @classmethod
    def get_session(cls):
        if cls._session is not None:      # Fast path
            return cls._session
        with cls._lock:                    # Slow path
            if cls._session is None:
                cls._load_model()
        return cls._session

    @classmethod
    def _load_model(cls):
        import onnxruntime as ort
        model_path = cls._resolve_model_path()
        cls._session = ort.InferenceSession(str(model_path))
```

This pattern — double-checked locking, lazy load, thread-safe
singleton — will be replicated for the ONNX upscaler sessions.

### 1.5 Model Details

Each Real-ESRGAN model has specific architecture parameters that
affect ONNX export:

| Model | Scale | Num RRDB Blocks | Params | .pth Size | Est. .onnx Size |
|---|---|---|---|---|---|
| `RealESRGAN_x4plus` | 4× | 23 | ~16.7M | ~67 MB | ~67 MB |
| `RealESRGAN_x2plus` | 2× | 23 | ~16.7M | ~67 MB | ~67 MB |
| `RealESRGAN_x4plus_anime_6B` | 4× | 6 | ~4.5M | ~18 MB | ~18 MB |

ONNX files are roughly the same size as `.pth` files because both
store the same weights — the difference is the graph representation
overhead, which is negligible for large models.

### 1.6 Files Involved

| File | Role | Changes |
|---|---|---|
| `backend/core_engine/image_upscaler.py` | Main upscaler module | Add `_OnnxUpscalerInstance`, modify `_get_upscaler()` selection logic |
| `backend/core_engine/export_upscaler_onnx.py` | **New file** — export utility | Create: loads PyTorch model, exports to ONNX |
| `backend/requirements.txt` | Python deps | Already has `onnxruntime>=1.17.0` — no changes needed |
| `models/upscalers/` | Model storage | Will contain new `.onnx` files after export |

### 1.7 Dependencies

| Package | Version | Status | Purpose |
|---|---|---|---|
| `onnxruntime` | ≥1.17.0 | Already installed | CPU inference |
| `onnxruntime-gpu` | ≥1.17.0 | Optional | GPU inference via CUDA EP |
| `torch` | any | Already installed (becomes **optional** after ONNX export) | Export only |
| `numpy` | any | Already installed | Array manipulation |
| `opencv-python-headless` | any | Already installed | Image I/O |

### 1.8 Important Constraints

1. **Backward compatibility** — The existing PyTorch path must remain
   fully functional.  Zero changes to `RRDBNet`, `_UpscalerInstance`,
   or `enhance()` method for the PyTorch code path.

2. **Dynamic input shapes** — Real-ESRGAN processes images of
   arbitrary sizes (or 512×512 tiles).  The ONNX export must use
   `dynamic_axes` for the spatial dimensions (H, W).

3. **Tile-based processing** — The `_tile_process()` logic must work
   identically with ORT sessions.  Each tile is a `(1, 3, H, W)`
   tensor where H and W vary per tile.

4. **Thread safety** — The `_OnnxUpscalerInstance` must be thread-safe.
   ONNX Runtime sessions are thread-safe for concurrent `run()` calls
   by default (unlike PyTorch CUDA), which is a significant advantage.

5. **FP16 on GPU** — When using `CUDAExecutionProvider`, the model
   should use FP16 for speed parity with the PyTorch CUDA path.
   This requires either exporting the model in FP16 or using ORT's
   `GraphOptimizationLevel` with FP16 conversion.

6. **Memory management** — ONNX Runtime sessions consume memory
   proportional to model size.  The cache should be shared with the
   PyTorch cache to prevent loading the same model via both backends.

7. **Error handling** — If ONNX Runtime fails (corrupted file,
   unsupported op), fall back to PyTorch if available, or return the
   original image path (never crash).

8. **ONNX opset version** — Use opset 17 (latest stable with full
   support for all RRDBNet operations: Conv2d, LeakyReLU, PixelShuffle,
   reflection padding).

---

## 2. Flow Diagram

### 2.1 Current Architecture (PyTorch Only)

```
                    ┌─────────────────────┐
                    │  upscale_image()     │
                    │  L389                │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  _get_upscaler()     │
                    │  L349                │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  PyTorch available?  │
                    └──────────┬──────────┘
                          Yes  │  No → return None
                    ┌──────────▼──────────┐
                    │  Load .pth weights   │
                    │  RRDBNet model       │
                    │  _UpscalerInstance    │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  enhance()           │
                    │  numpy → tensor      │
                    │  model(tensor)       │
                    │  tensor → numpy      │
                    └──────────┬──────────┘
                               │
                    ┌──────────▼──────────┐
                    │  cv2.imwrite()       │
                    └─────────────────────┘
```

### 2.2 Proposed Architecture (Dual Backend)

```
                    ┌─────────────────────────┐
                    │  upscale_image()         │
                    │  L389 (unchanged API)    │
                    └────────────┬────────────┘
                                 │
                    ┌────────────▼────────────┐
                    │  _get_upscaler()         │
                    │  (modified selection)     │
                    └────────────┬────────────┘
                                 │
              ┌──────────────────┼──────────────────┐
              │                  │                   │
    ┌─────────▼─────────┐       │     ┌─────────────▼─────────────┐
    │ .onnx file exists? │       │     │ .pth file + PyTorch avail? │
    └─────────┬─────────┘       │     └─────────────┬─────────────┘
         Yes  │                 │                Yes │
    ┌─────────▼─────────┐       │     ┌─────────────▼─────────────┐
    │ _OnnxUpscaler-     │       │     │ _UpscalerInstance          │
    │  Instance          │       │     │ (existing PyTorch path)    │
    │                    │       │     │                             │
    │ ort.Inference-     │       │     │ RRDBNet + torch.load()     │
    │  Session(onnx)     │       │     │ model(tensor)              │
    └─────────┬─────────┘       │     └─────────────┬─────────────┘
              │                 │                    │
              │ Both implement  │                    │
              │ .enhance() with │                    │
              │ same interface  │                    │
              └────────┬────────┘────────────────────┘
                       │
            ┌──────────▼──────────┐
            │  enhance()           │
            │  (common interface)  │
            │                      │
            │  Input:  BGR uint8   │
            │  Output: BGR uint8   │
            └──────────┬──────────┘
                       │
            ┌──────────▼──────────┐
            │  cv2.imwrite()       │
            └─────────────────────┘
```

### 2.3 Auto-Selection Decision Tree

```
_get_upscaler(model_name)
│
├─ model_name in MODEL_REGISTRY?
│  └─ No → log error, return None
│
├─ onnx_path = _MODELS_DIR / f"{model_name}.onnx"
│
├─ onnx_path.is_file()?
│  ├─ Yes ──────────────────────────────────────────────────────┐
│  │   Is model_name in _upscaler_cache?                        │
│  │   ├─ Yes → return cached instance                          │
│  │   └─ No  → create _OnnxUpscalerInstance(model_name)        │
│  │            cache it, return                                 │
│  │                                                             │
│  └─ No ───────────────────────────────────────────────┐       │
│       pth_path = _MODELS_DIR / info["filename"]        │       │
│       pth_path.is_file() AND _TORCH_AVAILABLE?         │       │
│       ├─ Yes → create _UpscalerInstance (existing)     │       │
│       │        cache it, return                        │       │
│       └─ No  → log warning, return None                │       │
│                                                        │       │
└──── return instance ◄──────────────────────────────────┘───────┘
```

### 2.4 ONNX Export Pipeline

```
export_upscaler_onnx.py (one-time utility)
│
├─ For each model_name in MODEL_REGISTRY:
│   │
│   ├─ Build RRDBNet(num_in_ch=3, num_out_ch=3, ...)
│   │
│   ├─ Load .pth weights (torch.load)
│   │   ├─ Handle params_ema / params wrapper
│   │   └─ model.load_state_dict(state_dict)
│   │
│   ├─ model.eval()
│   │
│   ├─ Create dummy input: torch.randn(1, 3, 64, 64)
│   │
│   ├─ torch.onnx.export(
│   │     model, dummy_input,
│   │     output_path=f"models/upscalers/{model_name}.onnx",
│   │     opset_version=17,
│   │     input_names=["input"],
│   │     output_names=["output"],
│   │     dynamic_axes={
│   │         "input":  {0: "batch", 2: "height", 3: "width"},
│   │         "output": {0: "batch", 2: "height", 3: "width"}
│   │     }
│   │   )
│   │
│   ├─ Verify: ort.InferenceSession(onnx_path)
│   │   └─ session.run(None, {"input": np.random.randn(1,3,64,64)})
│   │
│   └─ Print: ✓ Exported {model_name}.onnx ({size} MB)
│
└─ Done — .onnx files ready for distribution
```

### 2.5 ONNX Runtime Inference Flow (Inside _OnnxUpscalerInstance)

```
enhance(img_bgr, tile_size=512, tile_pad=10, pre_pad=10)
│
├─ img_bgr (H, W, 3) uint8
│
├─ BGR → RGB float32 /255.0
│   img = img_bgr[:, :, ::-1].astype(np.float32) / 255.0
│
├─ HWC → NCHW
│   tensor = img.transpose(2, 0, 1)[np.newaxis, ...]  # (1, 3, H, W)
│
├─ Ensure even dims for scale=2
│   if scale == 2: pad to even H, W
│
├─ Pre-pad with reflection (numpy)
│   tensor = np.pad(tensor, [...], mode='reflect')
│
├─ Tile decision:
│   ├─ Single tile (H ≤ tile_size and W ≤ tile_size):
│   │   output = session.run(None, {"input": tensor})[0]
│   │
│   └─ Multi-tile (_tile_process_ort):
│       ├─ Allocate output array: np.zeros((1, 3, H*scale, W*scale))
│       ├─ For each tile in grid:
│       │   tile_in = tensor[:, :, sy:ey, sx:ex]
│       │   tile_out = session.run(None, {"input": tile_in})[0]
│       │   Stitch tile_out into output array
│       └─ Return output
│
├─ Remove pre-pad from output
│   pp = pre_pad * scale
│   output = output[:, :, pp:-pp, pp:-pp]
│
├─ Remove mod-pad if applied
│   output = output[:, :, :out_h, :out_w]
│
├─ NCHW → HWC → BGR uint8
│   result = output[0].transpose(1, 2, 0)[:, :, ::-1]
│   result = (result * 255.0).clip(0, 255).astype(np.uint8)
│
└─ Return result (H*scale, W*scale, 3) uint8 BGR
```

### 2.6 Execution Provider Selection

```
_select_execution_providers()
│
├─ providers = ort.get_available_providers()
│
├─ "CUDAExecutionProvider" in providers?
│   ├─ Yes → return ["CUDAExecutionProvider", "CPUExecutionProvider"]
│   └─ No  → continue
│
├─ "DmlExecutionProvider" in providers?      (Windows DirectML)
│   ├─ Yes → return ["DmlExecutionProvider", "CPUExecutionProvider"]
│   └─ No  → continue
│
└─ return ["CPUExecutionProvider"]
```

---

## 3. Step-by-Step Instructions

### Step 1: Create the ONNX Export Utility Script

**File:** `backend/core_engine/export_upscaler_onnx.py` (NEW)

**Purpose:** One-time script that loads each PyTorch `.pth` model,
builds the RRDBNet architecture, loads weights, and exports to ONNX
format with dynamic spatial axes.

**1.1** Create the file with these imports:

```python
"""
ONNX Export Utility for Real-ESRGAN Upscaler Models.

Converts .pth PyTorch weights to .onnx format for inference via
ONNX Runtime.  This script requires PyTorch but the resulting .onnx
files do NOT require PyTorch for inference.

Usage:
    python -m core_engine.export_upscaler_onnx
    python -m core_engine.export_upscaler_onnx --model RealESRGAN_x4plus
    python -m core_engine.export_upscaler_onnx --all --verify
"""

import argparse
import logging
import os
import sys
import time
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)
```

**1.2** Import the existing architecture and registry from
`image_upscaler.py`:

```python
# Import the inline RRDBNet architecture and model registry
# from the existing upscaler module
from image_upscaler import MODEL_REGISTRY, _MODELS_DIR

# Lazy import of torch — only needed for export
try:
    import torch
    import torch.nn as nn
except ImportError:
    print("ERROR: PyTorch is required for ONNX export.")
    print("Install with: pip install torch")
    sys.exit(1)

# Also import the network class
from image_upscaler import RRDBNet
```

**1.3** Implement the core export function:

```python
def export_model_to_onnx(
    model_name: str,
    output_dir: Path | None = None,
    opset_version: int = 17,
    verify: bool = True,
    dummy_h: int = 64,
    dummy_w: int = 64,
) -> Path:
    """
    Export a single Real-ESRGAN model from .pth to .onnx format.

    Args:
        model_name: Key from MODEL_REGISTRY (e.g. "RealESRGAN_x4plus").
        output_dir: Directory for .onnx output. Defaults to _MODELS_DIR.
        opset_version: ONNX opset version (17 recommended).
        verify: If True, load the exported ONNX and run a test inference.
        dummy_h: Height of dummy input tensor for tracing.
        dummy_w: Width of dummy input tensor for tracing.

    Returns:
        Path to the exported .onnx file.

    Raises:
        KeyError: If model_name is not in MODEL_REGISTRY.
        FileNotFoundError: If the .pth weights file is missing.
        RuntimeError: If export or verification fails.
    """
    if model_name not in MODEL_REGISTRY:
        raise KeyError(
            f"Unknown model: {model_name}. "
            f"Available: {list(MODEL_REGISTRY.keys())}"
        )

    info = MODEL_REGISTRY[model_name]
    pth_path = _MODELS_DIR / info["filename"]

    if not pth_path.is_file():
        raise FileNotFoundError(
            f"PyTorch weights not found: {pth_path}\n"
            f"Download from https://github.com/xinntao/Real-ESRGAN"
        )

    if output_dir is None:
        output_dir = _MODELS_DIR
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    onnx_path = output_dir / f"{model_name}.onnx"

    logger.info("Exporting %s to ONNX...", model_name)
    print(f"\n{'='*60}")
    print(f"Exporting: {model_name}")
    print(f"  Source:  {pth_path}")
    print(f"  Target:  {onnx_path}")
    print(f"  Scale:   {info['scale']}x")
    print(f"  Blocks:  {info['num_block']}")
    print(f"  Opset:   {opset_version}")
    print(f"{'='*60}")

    # ------ 1. Build the PyTorch model ------
    model = RRDBNet(
        num_in_ch=3, num_out_ch=3, scale=info["scale"],
        num_feat=64, num_block=info["num_block"],
        num_grow_ch=info["num_grow_ch"],
    )

    # ------ 2. Load weights ------
    state_dict = torch.load(str(pth_path), map_location="cpu", weights_only=True)
    if "params_ema" in state_dict:
        state_dict = state_dict["params_ema"]
    elif "params" in state_dict:
        state_dict = state_dict["params"]

    model.load_state_dict(state_dict, strict=True)
    model.eval()

    # ------ 3. Create dummy input ------
    dummy_input = torch.randn(1, 3, dummy_h, dummy_w)

    # ------ 4. Export to ONNX ------
    t0 = time.perf_counter()

    torch.onnx.export(
        model,
        dummy_input,
        str(onnx_path),
        opset_version=opset_version,
        input_names=["input"],
        output_names=["output"],
        dynamic_axes={
            "input":  {0: "batch", 2: "height", 3: "width"},
            "output": {0: "batch", 2: "out_height", 3: "out_width"},
        },
        do_constant_folding=True,
    )

    export_time = time.perf_counter() - t0
    file_size_mb = onnx_path.stat().st_size / (1024 * 1024)

    print(f"  Exported in {export_time:.1f}s — {file_size_mb:.1f} MB")

    # ------ 5. Verify (optional) ------
    if verify:
        _verify_onnx_export(onnx_path, model, info["scale"], dummy_h, dummy_w)

    return onnx_path
```

**1.4** Implement the verification function:

```python
def _verify_onnx_export(
    onnx_path: Path,
    pytorch_model: 'torch.nn.Module',
    scale: int,
    dummy_h: int,
    dummy_w: int,
):
    """
    Verify the ONNX export by comparing outputs with the PyTorch model.

    Loads the ONNX file via ONNX Runtime, runs a random input through
    both backends, and checks that the outputs are numerically close.
    """
    import onnxruntime as ort

    print("  Verifying ONNX export...")

    # Run PyTorch inference
    dummy_np = np.random.rand(1, 3, dummy_h, dummy_w).astype(np.float32)
    dummy_torch = torch.from_numpy(dummy_np)

    with torch.no_grad():
        pytorch_out = pytorch_model(dummy_torch).numpy()

    # Run ONNX Runtime inference
    session = ort.InferenceSession(
        str(onnx_path),
        providers=["CPUExecutionProvider"],
    )
    ort_out = session.run(None, {"input": dummy_np})[0]

    # Compare outputs
    max_diff = np.abs(pytorch_out - ort_out).max()
    mean_diff = np.abs(pytorch_out - ort_out).mean()

    print(f"  Output shape:  {ort_out.shape}")
    print(f"  Expected:      (1, 3, {dummy_h * scale}, {dummy_w * scale})")
    print(f"  Max diff:      {max_diff:.6f}")
    print(f"  Mean diff:     {mean_diff:.6f}")

    if max_diff > 1e-3:
        print(f"  ⚠ WARNING: Max diff exceeds 1e-3 — outputs may diverge")
    else:
        print(f"  ✓ Verification passed — outputs match within tolerance")

    # Shape check
    expected_shape = (1, 3, dummy_h * scale, dummy_w * scale)
    assert ort_out.shape == expected_shape, (
        f"Shape mismatch: got {ort_out.shape}, expected {expected_shape}"
    )
```

**1.5** Add the CLI entry point:

```python
def export_all(verify: bool = True):
    """Export all models in MODEL_REGISTRY that have .pth files."""
    results = {}
    for model_name in MODEL_REGISTRY:
        pth_path = _MODELS_DIR / MODEL_REGISTRY[model_name]["filename"]
        if pth_path.is_file():
            try:
                path = export_model_to_onnx(model_name, verify=verify)
                results[model_name] = ("OK", str(path))
            except Exception as e:
                results[model_name] = ("FAILED", str(e))
                logger.error("Failed to export %s: %s", model_name, e)
        else:
            results[model_name] = ("SKIPPED", f".pth not found: {pth_path}")

    print(f"\n{'='*60}")
    print("Export Summary:")
    print(f"{'='*60}")
    for name, (status, detail) in results.items():
        print(f"  {status:8s}  {name:40s}  {detail}")
    print(f"{'='*60}\n")
    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Export Real-ESRGAN models from .pth to .onnx",
    )
    parser.add_argument(
        "--model", type=str, default=None,
        help="Model name to export (default: all available)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Export all models with available .pth files",
    )
    parser.add_argument(
        "--no-verify", action="store_true",
        help="Skip verification after export",
    )
    parser.add_argument(
        "--opset", type=int, default=17,
        help="ONNX opset version (default: 17)",
    )
    parser.add_argument(
        "--output-dir", type=str, default=None,
        help="Output directory (default: models/upscalers/)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    verify = not args.no_verify
    output_dir = Path(args.output_dir) if args.output_dir else None

    if args.model:
        export_model_to_onnx(
            args.model, output_dir=output_dir,
            opset_version=args.opset, verify=verify,
        )
    else:
        export_all(verify=verify)
```

---

### Step 2: Add ONNX Runtime Availability Flag to `image_upscaler.py`

**File:** `backend/core_engine/image_upscaler.py`

**Location:** After the existing `_TORCH_AVAILABLE` block (~L96–102)

**2.1** Add an ONNX Runtime availability flag immediately after the
PyTorch availability block:

```python
# After the existing block:
#   _TORCH_AVAILABLE = False
#   try:
#       import torch
#       ...
#       _TORCH_AVAILABLE = True
#   except ImportError:
#       ...

# ---- ADD THIS BLOCK ----

_ORT_AVAILABLE = False

try:
    import onnxruntime as ort
    _ORT_AVAILABLE = True
    logger.info("ONNX Runtime available — version %s", ort.__version__)
except ImportError:
    logger.debug("ONNX Runtime not available — ONNX upscaling disabled")
```

**2.2** Add a helper function to select the best execution providers.

Place this after the `_ORT_AVAILABLE` block, before the RRDBNet
architecture definition:

```python
def _get_ort_providers() -> list[str]:
    """
    Return the best available ONNX Runtime execution providers.

    Prefers CUDA > DirectML > CPU.
    """
    if not _ORT_AVAILABLE:
        return []

    available = ort.get_available_providers()
    selected = []

    if "CUDAExecutionProvider" in available:
        selected.append("CUDAExecutionProvider")
    elif "DmlExecutionProvider" in available:
        selected.append("DmlExecutionProvider")

    selected.append("CPUExecutionProvider")
    return selected
```

---

### Step 3: Extend MODEL_REGISTRY with ONNX Filenames

**File:** `backend/core_engine/image_upscaler.py`

**Location:** `MODEL_REGISTRY` dict at L39–62

**3.1** Add an `"onnx_filename"` key to each entry in the registry.
This maps each model to its expected `.onnx` file name:

```python
MODEL_REGISTRY = {
    "RealESRGAN_x4plus": {
        "filename": "RealESRGAN_x4plus.pth",
        "onnx_filename": "RealESRGAN_x4plus.onnx",      # ← NEW
        "scale": 4,
        "num_block": 23,
        "num_grow_ch": 32,
        "description": "Real-ESRGAN x4 — Best general-purpose upscaler",
    },
    "RealESRGAN_x2plus": {
        "filename": "RealESRGAN_x2plus.pth",
        "onnx_filename": "RealESRGAN_x2plus.onnx",      # ← NEW
        "scale": 2,
        "num_block": 23,
        "num_grow_ch": 32,
        "description": "Real-ESRGAN x2 — Moderate upscale, faster",
    },
    "RealESRGAN_x4plus_anime_6B": {
        "filename": "RealESRGAN_x4plus_anime_6B.pth",
        "onnx_filename": "RealESRGAN_x4plus_anime_6B.onnx",  # ← NEW
        "scale": 4,
        "num_block": 6,
        "num_grow_ch": 32,
        "description": "Real-ESRGAN x4 Anime — Optimised for illustrations",
    },
}
```

**3.2** Update `get_available_models()` (~L77) to also report ONNX
availability:

```python
def get_available_models() -> list[dict]:
    """Return a list of models whose weight files are present on disk."""
    available = []
    for name, info in MODEL_REGISTRY.items():
        pth_path = _MODELS_DIR / info["filename"]
        onnx_path = _MODELS_DIR / info["onnx_filename"]
        available.append({
            "name": name,
            "filename": info["filename"],
            "onnx_filename": info["onnx_filename"],
            "scale": info["scale"],
            "description": info["description"],
            "pth_available": pth_path.is_file(),
            "onnx_available": onnx_path.is_file(),
            "available": pth_path.is_file() or onnx_path.is_file(),
            "backend": "onnx" if onnx_path.is_file() else (
                "pytorch" if pth_path.is_file() else "none"
            ),
            "file_size": (
                onnx_path.stat().st_size if onnx_path.is_file()
                else pth_path.stat().st_size if pth_path.is_file()
                else 0
            ),
        })
    return available
```

---

### Step 4: Implement `_OnnxUpscalerInstance` Class

**File:** `backend/core_engine/image_upscaler.py`

**Location:** After the existing `_UpscalerInstance` class (~L203–336),
before the cache section (~L345).

**4.1** Create the `_OnnxUpscalerInstance` class.  It must implement
the exact same public interface as `_UpscalerInstance`:

```python
# ═══════════════════════════════════════════════════════════════════════════
# ONNX Runtime Upscaler wrapper (tile-based inference, no PyTorch needed)
# ═══════════════════════════════════════════════════════════════════════════

class _OnnxUpscalerInstance:
    """
    Wraps an ONNX Runtime InferenceSession for Real-ESRGAN inference.

    Provides the same enhance() / _tile_process() interface as
    _UpscalerInstance, but uses ONNX Runtime instead of PyTorch.
    No PyTorch dependency at runtime.
    """

    def __init__(self, model_name: str):
        info = MODEL_REGISTRY[model_name]
        self.scale = info["scale"]
        self.model_name = model_name

        onnx_path = _MODELS_DIR / info["onnx_filename"]
        if not onnx_path.is_file():
            raise FileNotFoundError(f"ONNX model not found: {onnx_path}")

        providers = _get_ort_providers()
        self.session = ort.InferenceSession(
            str(onnx_path),
            providers=providers,
        )

        # Determine which provider was actually selected
        active_providers = self.session.get_providers()
        self.device_name = active_providers[0] if active_providers else "unknown"
        self.is_gpu = "CUDA" in self.device_name or "Dml" in self.device_name

        # Input/output metadata
        inp = self.session.get_inputs()[0]
        out = self.session.get_outputs()[0]
        self.input_name = inp.name
        self.output_name = out.name

        logger.info(
            "Loaded ONNX upscaler: %s (scale=%d, provider=%s)",
            model_name, self.scale, self.device_name,
        )
```

**4.2** Implement the `enhance()` method — pure NumPy, no PyTorch:

```python
    def enhance(self, img_bgr: np.ndarray,
                tile_size: int = 512, tile_pad: int = 10,
                pre_pad: int = 10) -> np.ndarray:
        """Upscale a BGR uint8 image using tiled ONNX inference."""
        # For scale==2, ensure pre_pad is even
        if self.scale == 2 and pre_pad % 2 != 0:
            pre_pad += 1

        # BGR → RGB float32
        img = img_bgr.astype(np.float32) / 255.0
        img = img[:, :, ::-1].copy()  # BGR → RGB

        # HWC → NCHW
        tensor = np.ascontiguousarray(
            img.transpose(2, 0, 1)[np.newaxis, ...]
        )

        orig_h, orig_w = tensor.shape[2], tensor.shape[3]

        # For scale==2, ensure spatial dims are even
        mod_h = orig_h % 2
        mod_w = orig_w % 2
        if mod_h or mod_w:
            tensor = np.pad(
                tensor,
                ((0, 0), (0, 0), (0, mod_h), (0, mod_w)),
                mode='reflect',
            )

        # Pre-pad with reflection
        if pre_pad > 0:
            tensor = np.pad(
                tensor,
                ((0, 0), (0, 0),
                 (pre_pad, pre_pad), (pre_pad, pre_pad)),
                mode='reflect',
            )

        _, _, h, w = tensor.shape

        # Process in tiles or as a whole
        if tile_size <= 0 or (h <= tile_size and w <= tile_size):
            output = self.session.run(
                None, {self.input_name: tensor}
            )[0]
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

        # NCHW → HWC → BGR uint8
        result = output[0].transpose(1, 2, 0)  # CHW → HWC
        result = result[:, :, ::-1].copy()      # RGB → BGR
        result = np.clip(result * 255.0, 0, 255).round().astype(np.uint8)
        return result
```

**4.3** Implement `_tile_process()` for ONNX — same algorithm as the
PyTorch version at L299–336, but using `session.run()`:

```python
    def _tile_process(self, img: np.ndarray,
                      tile_size: int, tile_pad: int) -> np.ndarray:
        """Process a large image in overlapping tiles via ONNX Runtime."""
        import math

        _, _, h, w = img.shape
        out_h, out_w = h * self.scale, w * self.scale
        output = np.zeros((1, 3, out_h, out_w), dtype=np.float32)

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

                tile_in = np.ascontiguousarray(
                    img[:, :, inp_sy:inp_ey, inp_sx:inp_ex]
                )
                tile_out = self.session.run(
                    None, {self.input_name: tile_in}
                )[0]

                out_sy = (ofs_y - inp_sy) * self.scale
                out_sx = (ofs_x - inp_sx) * self.scale
                act_h = min(tile_size * self.scale,
                            out_h - ofs_y * self.scale)
                act_w = min(tile_size * self.scale,
                            out_w - ofs_x * self.scale)

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
```

---

### Step 5: Modify `_get_upscaler()` for Dual-Backend Selection

**File:** `backend/core_engine/image_upscaler.py`

**Location:** `_get_upscaler()` function at L349

**5.1** Replace the current implementation with the auto-selection
logic.  The function currently only tries PyTorch.  After this change,
it will prefer ONNX when available:

```python
def _get_upscaler(model_name: str):
    """
    Return a cached upscaler instance, creating one if needed.

    Selection priority:
    1. ONNX Runtime (if .onnx file exists and ORT is available)
    2. PyTorch (if .pth file exists and torch is available)
    3. None (upscaling unavailable)
    """
    if model_name in _upscaler_cache:
        return _upscaler_cache[model_name]

    with _cache_lock:
        if model_name in _upscaler_cache:
            return _upscaler_cache[model_name]

        info = MODEL_REGISTRY.get(model_name)
        if not info:
            logger.error("Unknown upscaler model: %s", model_name)
            return None

        onnx_path = _MODELS_DIR / info["onnx_filename"]
        pth_path = _MODELS_DIR / info["filename"]

        # ---- ONNX Runtime path (preferred) ----
        if _ORT_AVAILABLE and onnx_path.is_file():
            try:
                inst = _OnnxUpscalerInstance(model_name)
                _upscaler_cache[model_name] = inst
                logger.info(
                    "Using ONNX Runtime backend for %s", model_name
                )
                return inst
            except Exception as exc:
                logger.warning(
                    "ONNX load failed for %s, trying PyTorch: %s",
                    model_name, exc,
                )
                # Fall through to PyTorch path

        # ---- PyTorch path (fallback) ----
        if _TORCH_AVAILABLE and pth_path.is_file():
            try:
                device = torch.device(
                    "cuda" if torch.cuda.is_available() else "cpu"
                )
                inst = _UpscalerInstance(model_name, device)
                _upscaler_cache[model_name] = inst
                logger.info(
                    "Using PyTorch backend for %s on %s",
                    model_name, device,
                )
                return inst
            except Exception as exc:
                logger.error(
                    "Failed to load upscaler %s: %s", model_name, exc
                )
                return None

        # ---- Neither available ----
        if not pth_path.is_file() and not onnx_path.is_file():
            logger.error(
                "No model files found for %s. "
                "Expected .onnx at %s or .pth at %s",
                model_name, onnx_path, pth_path,
            )
        elif not _ORT_AVAILABLE and not _TORCH_AVAILABLE:
            logger.error(
                "Neither ONNX Runtime nor PyTorch is available. "
                "Install one: pip install onnxruntime  or  pip install torch"
            )
        return None
```

---

### Step 6: Update `clear_cache()` to Handle Both Backend Types

**File:** `backend/core_engine/image_upscaler.py`

**Location:** `clear_cache()` at L478

**6.1** The existing `clear_cache()` simply clears the dict.  This is
sufficient because both `_UpscalerInstance` and `_OnnxUpscalerInstance`
are cleaned up by Python's garbage collector.  However, for
explicitness, add logging about what was cleared:

```python
def clear_cache():
    """Clear all cached upscaler instances to free memory."""
    with _cache_lock:
        count = len(_upscaler_cache)
        backends = set()
        for inst in _upscaler_cache.values():
            if isinstance(inst, _OnnxUpscalerInstance):
                backends.add("ONNX")
            else:
                backends.add("PyTorch")
        _upscaler_cache.clear()
    logger.info(
        "Upscaler cache cleared — released %d instance(s) [%s]",
        count, ", ".join(sorted(backends)) if backends else "empty",
    )
```

---

### Step 7: Add a Public Backend Query Function

**File:** `backend/core_engine/image_upscaler.py`

**Location:** After `clear_cache()`, before end of file.

**7.1** Add a utility function for the API layer to query which
backend is active:

```python
def get_upscaler_backend_info() -> dict:
    """
    Return runtime info about the upscaler backend.

    Useful for the API status endpoint and debugging.
    """
    return {
        "ort_available": _ORT_AVAILABLE,
        "ort_version": ort.__version__ if _ORT_AVAILABLE else None,
        "ort_providers": (
            ort.get_available_providers() if _ORT_AVAILABLE else []
        ),
        "torch_available": _TORCH_AVAILABLE,
        "torch_version": (
            torch.__version__ if _TORCH_AVAILABLE else None
        ),
        "torch_cuda": (
            torch.cuda.is_available()
            if _TORCH_AVAILABLE else False
        ),
        "models_dir": str(_MODELS_DIR),
        "cached_models": {
            name: type(inst).__name__
            for name, inst in _upscaler_cache.items()
        },
    }
```

---

### Step 8: Handle FP16 Inference on CUDA with ONNX Runtime

**File:** `backend/core_engine/image_upscaler.py`

**Location:** Inside `_OnnxUpscalerInstance.__init__()`

**8.1** When CUDA EP is available and selected, configure the session
for FP16 inference.  There are two approaches:

**Approach A — Export-time FP16 (recommended for production):**

In `export_upscaler_onnx.py`, add a `--fp16` flag that converts the
model to FP16 during export:

```python
# In export_model_to_onnx(), after the standard export:
if fp16:
    from onnxruntime.transformers import float16
    import onnx

    print("  Converting to FP16...")
    onnx_model = onnx.load(str(onnx_path))
    onnx_fp16 = float16.convert_float_to_float16(onnx_model)
    fp16_path = output_dir / f"{model_name}_fp16.onnx"
    onnx.save(onnx_fp16, str(fp16_path))
    print(f"  FP16 model: {fp16_path}")
```

**Approach B — Runtime FP16 via session options (simpler):**

In `_OnnxUpscalerInstance.__init__()`, add graph optimisation:

```python
        sess_options = ort.SessionOptions()
        sess_options.graph_optimization_level = (
            ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        )

        # Enable FP16 on GPU for faster inference
        provider_options = []
        if "CUDAExecutionProvider" in providers:
            provider_options.append({
                "device_id": 0,
                "arena_extend_strategy": "kSameAsRequested",
                "gpu_mem_limit": 4 * 1024 * 1024 * 1024,  # 4 GB
                "cudnn_conv_algo_search": "DEFAULT",
            })
        if provider_options:
            # Pad provider_options to match providers length
            while len(provider_options) < len(providers):
                provider_options.append({})

        self.session = ort.InferenceSession(
            str(onnx_path),
            sess_options=sess_options,
            providers=providers,
            provider_options=provider_options if provider_options else None,
        )
```

**Recommendation:** Implement **Approach B** as the default (zero
extra steps for users), and offer **Approach A** as an optional flag
in the export script for maximum performance.

---

### Step 9: Ensure numpy Array Contiguity for ONNX Runtime

**File:** `backend/core_engine/image_upscaler.py`

**Location:** Inside `_OnnxUpscalerInstance.enhance()` and
`_tile_process()`

**9.1** ONNX Runtime requires input arrays to be **C-contiguous**.
NumPy slicing and transposing can produce non-contiguous views.  The
implementation in Step 4 already includes `np.ascontiguousarray()`
calls, but verify these are present at every `session.run()` call:

- In `enhance()`: after `img.transpose(2, 0, 1)[np.newaxis, ...]`
- In `_tile_process()`: after `img[:, :, inp_sy:inp_ey, inp_sx:inp_ex]`

Both locations are covered in Step 4.  If you see `ValueError: input
is not C-contiguous` during testing, add `np.ascontiguousarray()`
around the tensor being passed to `session.run()`.

---

### Step 10: Implement Reflection Padding in Pure NumPy

**File:** `backend/core_engine/image_upscaler.py`

**Location:** Inside `_OnnxUpscalerInstance.enhance()`

**10.1** The PyTorch path uses `F.pad(tensor, ..., mode='reflect')`.
The ONNX path must replicate this using `np.pad()`.  The
implementation in Step 4.2 already uses `np.pad(..., mode='reflect')`,
which is the numpy equivalent.

Key difference from PyTorch: `np.pad()` takes a pad-width tuple for
each axis, not a flat tuple.  The mapping is:

```python
# PyTorch:   F.pad(tensor, (left, right, top, bottom), mode='reflect')
# NumPy:     np.pad(tensor,
#                    ((0,0), (0,0), (top, bottom), (left, right)),
#                    mode='reflect')
```

The Step 4.2 code handles this correctly with:
```python
np.pad(tensor,
       ((0, 0), (0, 0), (pre_pad, pre_pad), (pre_pad, pre_pad)),
       mode='reflect')
```

---

### Step 11: Add Integration Test

**File:** `backend/core_engine/tests/test_onnx_upscaler.py` (NEW)

**11.1** Create a test file that verifies both backends produce
equivalent results:

```python
"""
Tests for the ONNX Runtime upscaler path.

These tests verify:
1. _OnnxUpscalerInstance loads and runs correctly
2. Output matches PyTorch path within tolerance
3. Tile-based processing works with ORT
4. Auto-selection logic picks the right backend
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import cv2
import numpy as np

from core_engine.image_upscaler import (
    MODEL_REGISTRY,
    _MODELS_DIR,
    _ORT_AVAILABLE,
    _TORCH_AVAILABLE,
    clear_cache,
    get_available_models,
    get_upscaler_backend_info,
    upscale_image,
)


class TestOnnxUpscalerInstance(unittest.TestCase):
    """Tests for _OnnxUpscalerInstance class."""

    def setUp(self):
        clear_cache()

    def tearDown(self):
        clear_cache()

    @unittest.skipUnless(_ORT_AVAILABLE, "ONNX Runtime not available")
    def test_onnx_model_loads(self):
        """Test that ONNX model loads without error."""
        from core_engine.image_upscaler import _OnnxUpscalerInstance

        for model_name, info in MODEL_REGISTRY.items():
            onnx_path = _MODELS_DIR / info["onnx_filename"]
            if onnx_path.is_file():
                inst = _OnnxUpscalerInstance(model_name)
                self.assertEqual(inst.scale, info["scale"])
                self.assertIsNotNone(inst.session)

    @unittest.skipUnless(_ORT_AVAILABLE, "ONNX Runtime not available")
    def test_onnx_enhance_small_image(self):
        """Test enhance() with a small image (no tiling)."""
        from core_engine.image_upscaler import _OnnxUpscalerInstance

        for model_name, info in MODEL_REGISTRY.items():
            onnx_path = _MODELS_DIR / info["onnx_filename"]
            if not onnx_path.is_file():
                continue

            inst = _OnnxUpscalerInstance(model_name)

            # Create a small test image (64x64 BGR)
            img = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
            result = inst.enhance(img, tile_size=0)

            expected_h = 64 * info["scale"]
            expected_w = 64 * info["scale"]
            self.assertEqual(result.shape, (expected_h, expected_w, 3))
            self.assertEqual(result.dtype, np.uint8)

    @unittest.skipUnless(_ORT_AVAILABLE, "ONNX Runtime not available")
    def test_onnx_tiled_processing(self):
        """Test tile-based processing with ONNX Runtime."""
        from core_engine.image_upscaler import _OnnxUpscalerInstance

        model_name = "RealESRGAN_x4plus_anime_6B"  # Smallest model
        info = MODEL_REGISTRY[model_name]
        onnx_path = _MODELS_DIR / info["onnx_filename"]
        if not onnx_path.is_file():
            self.skipTest(f"ONNX model not available: {model_name}")

        inst = _OnnxUpscalerInstance(model_name)

        # Large enough to trigger tiling (> 512)
        img = np.random.randint(0, 256, (600, 800, 3), dtype=np.uint8)
        result = inst.enhance(img, tile_size=512)

        expected_h = 600 * 4
        expected_w = 800 * 4
        self.assertEqual(result.shape, (expected_h, expected_w, 3))


class TestAutoSelection(unittest.TestCase):
    """Tests for the auto-selection logic in _get_upscaler()."""

    def setUp(self):
        clear_cache()

    def tearDown(self):
        clear_cache()

    def test_prefers_onnx_over_pytorch(self):
        """When both .onnx and .pth exist, ONNX should be selected."""
        from core_engine.image_upscaler import (
            _get_upscaler, _OnnxUpscalerInstance, _UpscalerInstance,
        )

        for model_name, info in MODEL_REGISTRY.items():
            onnx_path = _MODELS_DIR / info["onnx_filename"]
            pth_path = _MODELS_DIR / info["filename"]
            if onnx_path.is_file() and _ORT_AVAILABLE:
                clear_cache()
                inst = _get_upscaler(model_name)
                self.assertIsInstance(inst, _OnnxUpscalerInstance)
            elif pth_path.is_file() and _TORCH_AVAILABLE:
                clear_cache()
                inst = _get_upscaler(model_name)
                self.assertIsInstance(inst, _UpscalerInstance)

    def test_backend_info_reports_correctly(self):
        """get_upscaler_backend_info() returns valid data."""
        info = get_upscaler_backend_info()
        self.assertIn("ort_available", info)
        self.assertIn("torch_available", info)
        self.assertIn("models_dir", info)


class TestEndToEndUpscale(unittest.TestCase):
    """End-to-end test: upscale_image() with ONNX backend."""

    def setUp(self):
        clear_cache()

    def tearDown(self):
        clear_cache()

    @unittest.skipUnless(_ORT_AVAILABLE, "ONNX Runtime not available")
    def test_upscale_image_file_onnx(self):
        """Test full upscale_image() pipeline with ONNX backend."""
        # Check if any ONNX model is available
        has_onnx = any(
            (_MODELS_DIR / info["onnx_filename"]).is_file()
            for info in MODEL_REGISTRY.values()
        )
        if not has_onnx:
            self.skipTest("No ONNX models available")

        # Find the first available ONNX model
        model_name = None
        for name, info in MODEL_REGISTRY.items():
            if (_MODELS_DIR / info["onnx_filename"]).is_file():
                model_name = name
                break

        # Create temp input image
        with tempfile.TemporaryDirectory() as tmpdir:
            in_path = os.path.join(tmpdir, "test_input.png")
            out_path = os.path.join(tmpdir, "test_output.png")

            img = np.random.randint(0, 256, (64, 64, 3), dtype=np.uint8)
            cv2.imwrite(in_path, img)

            result_path = upscale_image(
                in_path, out_path, model_name=model_name
            )

            self.assertEqual(result_path, out_path)
            self.assertTrue(os.path.isfile(out_path))

            result_img = cv2.imread(out_path)
            scale = MODEL_REGISTRY[model_name]["scale"]
            self.assertEqual(
                result_img.shape[:2],
                (64 * scale, 64 * scale),
            )


if __name__ == "__main__":
    unittest.main()
```

---

### Step 12: Update the Serializer / API (Optional Enhancement)

**File:** `backend/api/serializers.py` and `backend/api/views.py`

**12.1** If the API has a status or models endpoint, update it to
include the `backend` field from `get_available_models()`.  This allows
the frontend to display which backend is in use.

This step is optional and depends on existing API endpoints.  The core
engine changes in Steps 1–11 are self-contained and do not require API
changes to function.

---

## 4. Expected Outcome

### 4.1 Functional Outcomes

| # | Outcome | Verification Method |
|---|---|---|
| 1 | `.onnx` files are generated from `.pth` weights by the export script | Run `python -m core_engine.export_upscaler_onnx --all --verify` |
| 2 | ONNX Runtime is automatically selected when `.onnx` files are present | Check log output: `"Using ONNX Runtime backend for ..."` |
| 3 | PyTorch is used as fallback when only `.pth` files exist | Delete `.onnx` file, re-run upscaler, check log |
| 4 | Images are upscaled identically (within tolerance) by both backends | Run verification in export script, compare outputs |
| 5 | Tile-based processing works with ONNX Runtime | Upscale a large image (e.g., 1920×1080) |
| 6 | Thread safety is maintained | Run `upscale_images_batch()` from multiple threads |
| 7 | Error handling gracefully falls back | Corrupt `.onnx` file, verify fallback to PyTorch |
| 8 | `clear_cache()` releases both ONNX and PyTorch instances | Call `clear_cache()`, check log message |
| 9 | `get_available_models()` reports ONNX availability | Check output contains `"onnx_available": true` |
| 10 | `get_upscaler_backend_info()` reports runtime state | Call function, inspect dict |

### 4.2 Performance Outcomes

| Metric | PyTorch CPU | ONNX Runtime CPU | Expected Improvement |
|---|---|---|---|
| 720p → 2880p (x4, single) | ~35s | ~12–15s | **2–3×** |
| 720p → 2880p (x4, 20 batch) | ~700s | ~240–300s | **2–3×** |
| 512p → 1024p (x2, single) | ~8s | ~3–4s | **2×** |
| Model load time | ~3s | ~1s | **3×** |
| Memory (model resident) | ~500 MB | ~350 MB | **30% less** |

These are approximate figures based on typical Real-ESRGAN benchmarks.
Actual performance depends on hardware (CPU model, cache size, SIMD
support).

### 4.3 Dependency Outcome

| Scenario | Before | After |
|---|---|---|
| CPU-only user (most common) | Must install PyTorch (~2 GB) | Only needs onnxruntime (~50 MB) |
| GPU user who wants PyTorch | No change | No change (PyTorch path remains) |
| Minimal install (no upscaling) | Still needs PyTorch imported | Clean skip — no heavy imports |

### 4.4 File Inventory After Implementation

```
backend/core_engine/
├── image_upscaler.py          ← MODIFIED: +_OnnxUpscalerInstance, +_get_ort_providers,
│                                 +modified _get_upscaler, +get_upscaler_backend_info
├── export_upscaler_onnx.py    ← NEW: export utility script
├── model_loader.py            ← UNCHANGED (Kokoro TTS)
├── tts_wrapper.py             ← UNCHANGED
└── tests/
    └── test_onnx_upscaler.py  ← NEW: integration tests

models/upscalers/
├── RealESRGAN_x4plus.pth               ← existing
├── RealESRGAN_x2plus.pth               ← existing
├── RealESRGAN_x4plus_anime_6B.pth      ← existing
├── RealESRGAN_x4plus.onnx              ← NEW (generated by export script)
├── RealESRGAN_x2plus.onnx              ← NEW (generated by export script)
└── RealESRGAN_x4plus_anime_6B.onnx     ← NEW (generated by export script)
```

---

## 5. Verification Checklist

### 5.1 Pre-Implementation Checks

- [ ] Confirm `onnxruntime>=1.17.0` is in `backend/requirements.txt`
- [ ] Confirm `models/upscalers/` directory exists and contains at
      least one `.pth` file
- [ ] Confirm `backend/core_engine/image_upscaler.py` is at 483 lines
      with `MODEL_REGISTRY` at L39 and `_UpscalerInstance` at L203
- [ ] Confirm `backend/core_engine/model_loader.py` exists (reference
      for ONNX Runtime patterns)
- [ ] Read the current `_get_upscaler()` function at L349 to
      understand the existing cache/lock flow

### 5.2 Export Script Verification

- [ ] `export_upscaler_onnx.py` created at
      `backend/core_engine/export_upscaler_onnx.py`
- [ ] Script imports `RRDBNet` and `MODEL_REGISTRY` from
      `image_upscaler.py`
- [ ] `export_model_to_onnx()` handles all 3 model variants
- [ ] ONNX export uses `opset_version=17` and `dynamic_axes` for
      spatial dimensions
- [ ] `do_constant_folding=True` is set for export optimisation
- [ ] Verification function compares ORT vs PyTorch outputs
- [ ] Max diff between backends is < 1e-3
- [ ] CLI supports `--model`, `--all`, `--no-verify`, `--opset`
- [ ] Script runs successfully:
      `cd backend && python -m core_engine.export_upscaler_onnx --all`

### 5.3 `_OnnxUpscalerInstance` Verification

- [ ] Class is defined after `_UpscalerInstance`, before cache section
- [ ] `__init__()` creates `ort.InferenceSession` with auto-detected
      providers
- [ ] `enhance()` accepts `(img_bgr: np.ndarray)` and returns
      `np.ndarray` (same as PyTorch version)
- [ ] `enhance()` handles BGR→RGB, float32, NCHW conversion in pure
      NumPy
- [ ] Pre-padding uses `np.pad(..., mode='reflect')`
- [ ] Mod-padding for scale=2 is handled
- [ ] Single-tile path: `session.run(None, {input_name: tensor})[0]`
- [ ] Multi-tile path: `_tile_process()` uses same grid algorithm as
      PyTorch version
- [ ] All arrays passed to `session.run()` are C-contiguous
      (`np.ascontiguousarray()`)
- [ ] Post-processing: remove padding, NCHW→HWC, RGB→BGR, clip,
      uint8

### 5.4 Auto-Selection Verification

- [ ] `_get_upscaler()` checks `.onnx` file FIRST, then `.pth`
- [ ] If `.onnx` load fails, falls back to `.pth` with a warning log
- [ ] If neither is available, returns `None` with an error log
- [ ] Double-checked locking is preserved (_cache_lock)
- [ ] Cache key is `model_name` (shared between both backend types)
- [ ] `upscale_image()` and `upscale_images_batch()` are **unchanged**
      in their public API

### 5.5 MODEL_REGISTRY Verification

- [ ] Each model entry has `"onnx_filename"` key
- [ ] ONNX filenames follow `{model_name}.onnx` convention
- [ ] `get_available_models()` reports `onnx_available` and `backend`
      fields

### 5.6 Thread Safety Verification

- [ ] `_OnnxUpscalerInstance` is created inside `_cache_lock` in
      `_get_upscaler()`
- [ ] ORT `InferenceSession.run()` is thread-safe by default (no
      extra locking needed)
- [ ] `clear_cache()` handles both instance types under lock
- [ ] No global mutable state outside the cache dict

### 5.7 Error Handling Verification

- [ ] Missing `.onnx` file → fall through to PyTorch
- [ ] Corrupted `.onnx` file → catch exception, fall through to PyTorch
- [ ] Missing both files → return `None`, log error
- [ ] Neither ORT nor PyTorch installed → return `None`, log error
- [ ] `upscale_image()` returns original path on any failure (never
      crashes)

### 5.8 Integration Test Verification

- [ ] `test_onnx_upscaler.py` created at
      `backend/core_engine/tests/test_onnx_upscaler.py`
- [ ] Test class `TestOnnxUpscalerInstance` tests model loading,
      small image enhance, tiled processing
- [ ] Test class `TestAutoSelection` tests ONNX preference and
      backend info
- [ ] Test class `TestEndToEndUpscale` tests full file-based pipeline
- [ ] Tests use `@unittest.skipUnless` for optional dependencies
- [ ] All tests pass: `cd backend && python -m pytest core_engine/tests/`

### 5.9 Backward Compatibility Verification

- [ ] Existing `_UpscalerInstance` class is **UNCHANGED**
- [ ] Existing `RRDBNet` architecture is **UNCHANGED**
- [ ] `upscale_image()` signature is **UNCHANGED**
- [ ] `upscale_images_batch()` signature is **UNCHANGED**
- [ ] Deleting all `.onnx` files reverts to pure PyTorch behaviour
- [ ] No new required dependencies (onnxruntime already installed)

### 5.10 Documentation & Cleanup

- [ ] Docstring updated at top of `image_upscaler.py` to mention
      dual-backend support
- [ ] `_OnnxUpscalerInstance` has complete docstrings
- [ ] `export_upscaler_onnx.py` has module docstring with usage
      examples
- [ ] No debug `print()` statements left (use `logger.info/debug`)
- [ ] No unused imports

---

## 6. Notes for AI Agent

### 6.1 Critical Implementation Details

1. **Do NOT modify existing PyTorch code.**  The `RRDBNet`,
   `ResidualDenseBlock`, `RRDB`, `_UpscalerInstance` classes must
   remain exactly as they are.  All new code is **additive**.

2. **The `_OnnxUpscalerInstance` must be a drop-in replacement.**
   It must have the same `enhance(img_bgr, tile_size, tile_pad,
   pre_pad) -> np.ndarray` signature so that `upscale_image()` at
   L389 works without changes.

3. **Import guards are critical.**  The `_ORT_AVAILABLE` flag must
   use try/except just like `_TORCH_AVAILABLE`.  Never assume ONNX
   Runtime is installed — it may be missing in some environments.

4. **Array contiguity is the #1 source of ONNX Runtime errors.**
   Every array passed to `session.run()` must be C-contiguous.  NumPy
   slice views (e.g., `array[:, :, 10:20, 30:40]`) produce non-
   contiguous arrays.  Always wrap with `np.ascontiguousarray()`.

5. **The `_get_upscaler()` cache is keyed by `model_name`.**  This
   means the same model cannot be cached with both backends
   simultaneously.  This is intentional — only one backend is active
   per model.  If you need to switch backends, call `clear_cache()`
   first.

6. **ONNX export needs `dynamic_axes`.**  Without this, the exported
   model only accepts the exact input shape used during tracing
   (e.g., 64×64).  The `dynamic_axes` dict must include dimensions
   2 and 3 (height and width) for both input and output.

7. **`do_constant_folding=True`** during `torch.onnx.export()` is
   important — it pre-computes constant expressions in the graph,
   reducing runtime overhead.

8. **The reflection padding in NumPy uses different pad syntax than
   PyTorch.**  PyTorch `F.pad` takes `(left, right, top, bottom)` as
   a flat tuple.  NumPy `np.pad` takes `((before, after), ...)` per
   axis.  The conversion:
   ```python
   # PyTorch: F.pad(x, (p, p, p, p), mode='reflect')
   # NumPy:   np.pad(x, ((0,0), (0,0), (p,p), (p,p)), mode='reflect')
   ```

9. **The scale=2 mod-padding is subtle.**  For `RealESRGAN_x2plus`,
   the network uses pixel unshuffle which requires even spatial
   dimensions.  The PyTorch path pads with `F.pad(..., mode='reflect')`
   to make dims even.  The ONNX path must do the same with `np.pad()`.

### 6.2 Code Location Summary

When implementing, insert new code at these specific locations in
`image_upscaler.py`:

| What | Where | Reference |
|---|---|---|
| `_ORT_AVAILABLE` flag | After L102 (after `_TORCH_AVAILABLE` block) | Between imports and RRDBNet |
| `_get_ort_providers()` | After `_ORT_AVAILABLE` block | Before RRDBNet class |
| `"onnx_filename"` in `MODEL_REGISTRY` | L39–62 | Add key to each dict entry |
| Updated `get_available_models()` | L77 | Replace existing function |
| `_OnnxUpscalerInstance` class | After L336 (after `_tile_process`) | Before `_upscaler_cache` |
| Modified `_get_upscaler()` | L349 | Replace existing function |
| Updated `clear_cache()` | L478 | Replace existing function |
| `get_upscaler_backend_info()` | After `clear_cache()` | New function at end |

### 6.3 Testing Strategy

1. **Unit test the export script first** — this validates that the
   ONNX graph is correct and numerically equivalent to PyTorch.

2. **Test `_OnnxUpscalerInstance` in isolation** — create an instance
   directly and call `enhance()` with small synthetic images.

3. **Test auto-selection** — manipulate which files exist on disk to
   verify the selection logic.

4. **Test the full pipeline** — call `upscale_image()` and
   `upscale_images_batch()` to verify end-to-end behaviour.

5. **Test error paths** — rename/delete `.onnx` files and verify
   graceful fallback.

### 6.4 Common Pitfalls to Avoid

| Pitfall | Consequence | Prevention |
|---|---|---|
| Forgetting `np.ascontiguousarray()` | `ValueError` from ORT | Wrap every `session.run()` input |
| Wrong `np.pad` axis order | Image corruption, wrong dimensions | Use `((0,0), (0,0), (top,bot), (left,right))` for NCHW |
| Missing `dynamic_axes` in export | Model only works for one input size | Always include `{2: "h", 3: "w"}` |
| Not handling `params_ema` wrapper | `load_state_dict` error | Check and unwrap as existing code does |
| Importing `torch` at module level in ORT path | Import error if torch missing | Guard with `_TORCH_AVAILABLE` |
| Modifying `_UpscalerInstance` | Regression in PyTorch path | All changes are additive only |
| Using Python `float16` with CPU EP | ORT CPU provider doesn't support FP16 well | Only use FP16 with CUDA EP |
| Not making tile arrays contiguous | Silent corruption or crash | `np.ascontiguousarray()` on every tile slice |

### 6.5 Execution Order

Implement the steps in this order for minimal risk:

1. **Step 3** — Add `onnx_filename` to `MODEL_REGISTRY` (low risk,
   backward compatible)
2. **Step 2** — Add `_ORT_AVAILABLE` flag and `_get_ort_providers()`
3. **Step 4** — Implement `_OnnxUpscalerInstance` class
4. **Step 5** — Modify `_get_upscaler()` for dual-backend selection
5. **Step 6** — Update `clear_cache()`
6. **Step 7** — Add `get_upscaler_backend_info()`
7. **Step 1** — Create `export_upscaler_onnx.py` (can be done at any
   time since it's a standalone script)
8. **Step 8** — FP16 support (enhancement, can be deferred)
9. **Step 11** — Integration tests (run after Steps 1–7)
10. **Steps 9, 10** — Verification of edge cases

### 6.6 Rollback Plan

If ONNX Runtime integration causes issues:

1. Delete all `.onnx` files from `models/upscalers/`
2. The auto-selection logic will fall back to PyTorch automatically
3. No code changes needed for rollback — the PyTorch path is untouched

To fully remove ONNX upscaler code:

1. Remove `_OnnxUpscalerInstance` class
2. Remove `_ORT_AVAILABLE` and `_get_ort_providers()`
3. Revert `_get_upscaler()` to original version
4. Remove `"onnx_filename"` from `MODEL_REGISTRY`
5. Delete `export_upscaler_onnx.py`
6. Delete `test_onnx_upscaler.py`

### 6.7 Future Enhancements (Out of Scope)

These are NOT part of this feature but may be implemented later:

- **Quantized ONNX models (INT8)** — further reduce model size and
  improve CPU speed at slight quality cost
- **ONNX Runtime Web** — run upscaler in the browser via WebAssembly
- **TensorRT EP** — NVIDIA-optimised inference for maximum GPU speed
- **Model caching with mmap** — memory-map ONNX files for instant
  loading on subsequent runs
- **Batch inference** — process multiple tiles in a single
  `session.run()` call for GPU throughput

### 6.8 Reference: Key ONNX Runtime APIs

```python
import onnxruntime as ort

# ------- Session Creation -------
session = ort.InferenceSession(
    "model.onnx",
    sess_options=None,                    # Optional: SessionOptions
    providers=["CPUExecutionProvider"],    # Execution providers
)

# ------- Session Options -------
opts = ort.SessionOptions()
opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
opts.intra_op_num_threads = 4            # Thread parallelism within ops
opts.inter_op_num_threads = 2            # Thread parallelism between ops
opts.execution_mode = ort.ExecutionMode.ORT_PARALLEL

# ------- Inference -------
input_name = session.get_inputs()[0].name
output = session.run(None, {input_name: numpy_array})[0]

# ------- Provider Query -------
available = ort.get_available_providers()
# → ['CUDAExecutionProvider', 'CPUExecutionProvider']

active = session.get_providers()
# → ['CPUExecutionProvider']

# ------- Input/Output Metadata -------
inp = session.get_inputs()[0]
# inp.name → "input"
# inp.shape → [1, 3, 'height', 'width']  (dynamic dims are strings)
# inp.type → 'tensor(float)'

out = session.get_outputs()[0]
# out.name → "output"
# out.shape → [1, 3, 'out_height', 'out_width']
```

### 6.9 Reference: torch.onnx.export API

```python
torch.onnx.export(
    model,                          # PyTorch model (nn.Module)
    args,                           # Tuple of example inputs
    f,                              # Output file path (str or file-like)
    export_params=True,             # Store trained weights in the model
    opset_version=17,               # ONNX opset version
    do_constant_folding=True,       # Fold constants for optimisation
    input_names=["input"],          # Names for input tensors
    output_names=["output"],        # Names for output tensors
    dynamic_axes={                  # Dict: tensor_name → {dim: name}
        "input": {0: "batch", 2: "height", 3: "width"},
        "output": {0: "batch", 2: "out_height", 3: "out_width"},
    },
    verbose=False,                  # Print export log
)
```

---

*End of Feature 1.5 — ONNX Runtime Path for Image Upscaling*
