# Feature 7.5 — Denoise Strength Implementation

> **Status:** Planned
> **Category:** Core Engine / Image Upscaling
> **Primary Target File:** `backend/core_engine/image_upscaler.py`
> **Secondary Target Files:** `backend/core_engine/video_renderer.py`, `backend/api/models.py`
> **Estimated Complexity:** Medium
> **Expected Impact:** Proper denoise control as advertised in the UI
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

The StoryFlow upscaling pipeline accepts a `denoise_strength` parameter
throughout its entire stack — from the frontend UI slider, through the
Django model, through the video renderer, and into the image upscaler
module — but the parameter is **completely ignored** at the point where
it would actually take effect. It exists as a pass-through placeholder
with no functional implementation.

Here is the exact path the parameter travels, and where it stops:

**Layer 1 — Frontend UI:**
The render settings panel in the frontend already includes a slider
for denoise strength that allows the user to select a value between
0.0 and 1.0. The user can adjust this slider, save the value, and it
is sent to the backend API when project settings are updated.

**Layer 2 — Django Model (backend/api/models.py):**

The Project model at approximately line 111 defines a field
`upscale_denoise_strength = models.FloatField(default=0.5)`. The
GlobalSettings model at approximately line 256 also defines the
same field. Both fields store the value correctly in the database.

**Layer 3 — Video Renderer (backend/core_engine/video_renderer.py):**

At line 732 of `render_project()`, the value is read from the project
via `upscale_denoise = getattr(project, "upscale_denoise_strength", 0.5)`.
This value is then passed to `upscale_images_batch()` at approximately
line 918 as `denoise_strength=upscale_denoise`. The value travels
correctly through this layer.

**Layer 4 — Image Upscaler (backend/core_engine/image_upscaler.py):**

The `upscale_image()` function at line 393 accepts the parameter:
`denoise_strength: float = 0.5`. The docstring at line 403 explicitly
states: "Currently informational; the model architecture determines
denoising." The parameter is accepted into the function, logged, but
never passed down to the actual inference method.

The `upscale_images_batch()` function at line 439 also accepts the
parameter and passes it to `upscale_image()`, but since `upscale_image()`
does nothing with it, the chain ends there.

**Layer 5 — Model Inference (_UpscalerInstance.enhance()):**

The `enhance()` method at line 247 of `image_upscaler.py` is the method
that actually performs the Real-ESRGAN inference. Its signature is
`enhance(self, img_bgr, tile_size=512, tile_pad=10, pre_pad=10)`. There
is no `denoise_strength` parameter in this method at all. The method
loads the image, runs it through the RRDBNet model, and returns the
upscaled result. The model architecture (RRDBNet with specific weights)
inherently applies whatever denoising is baked into the trained weights,
but there is no way for the user to control the degree of denoising.

**The result:**
A user who sets denoise_strength to 0.0 (expecting no denoising) or
1.0 (expecting maximum denoising) gets the exact same output in both
cases. The UI control is misleading — it promises functionality that
does not exist.

### 1.2 How Real-ESRGAN Denoise Works (Two Approaches)

**Approach A — DNoise Model Weight Interpolation (Official Approach):**

The official Real-ESRGAN project by xinntao provides specific model
variants designed for denoise control:

- A "clean" model (for example, `realesr-general-x4v3.pth`) trained to
  upscale with minimal denoising
- A "WDN" (With Denoise) model variant (for example,
  `realesr-general-wdn-x4v3.pth`) trained to upscale with aggressive
  denoising
- Both models share the exact same architecture (same number of layers,
  same tensor shapes) — only the trained weight values differ

To control denoise strength, the technique is weight interpolation:

- Load both sets of weights (clean and WDN) into memory
- For each weight tensor in the model, compute a weighted average:
  `final_weight = clean_weight * (1 - denoise_strength) + wdn_weight * denoise_strength`
- At `denoise_strength = 0.0`: The model uses pure clean weights (no denoising)
- At `denoise_strength = 0.5`: Equal mix of clean and denoise weights
- At `denoise_strength = 1.0`: The model uses pure WDN weights (full denoising)

This approach produces the highest quality results because the denoising
is integrated into the super-resolution process itself — the model
simultaneously upscales and denoises in a single forward pass.

However, this approach has significant requirements:

- A second model weight file must be downloaded (the WDN variant),
  which is the same size as the clean model (approximately 65 MB each
  for the x4v3 models)
- The specific model pair (`realesr-general-x4v3` and its WDN variant)
  uses a different architecture variant than the existing models in the
  StoryFlow registry. The current models (RealESRGAN_x4plus, x2plus,
  anime_6B) use the original ESRGAN RRDBNet architecture. The v3 general
  models use a slightly different architecture (SRVGGNetCompact) that
  would need to be added
- Weight interpolation requires loading two full model weight sets into
  memory, roughly doubling the memory needed during model initialization
- The current models in the registry (x4plus, x2plus, anime_6B) do NOT
  have WDN variants, so this approach only works with the general-v3
  model pair

**Approach B — OpenCV Pre-Processing Denoise (Simpler Approach):**

An alternative approach that works with ALL existing models is to apply
denoising as a pre-processing step on the input image before it is fed
into the upscaler:

- Use OpenCV's `cv2.fastNlMeansDenoisingColored()` function on the
  source image before upscaling
- This function performs non-local means denoising, which is highly
  effective at removing Gaussian noise while preserving edges
- The key parameter is `h` (filter strength for luminance component):
  - `h = 0`: No denoising (pass-through)
  - `h = 10`: Moderate denoising (good for typical photographic noise)
  - `h = 20`: Heavy denoising (smooths most noise, some detail loss)
- Map the user's `denoise_strength` (0.0–1.0) to the `h` parameter:
  `h = denoise_strength * 20`
- The function also takes `hForColorComponents` (typically set to `h`
  or slightly lower like `h * 0.8`), `templateWindowSize` (default 7),
  and `searchWindowSize` (default 21)
- When `denoise_strength` is 0 or very close to 0 (below a threshold
  like 0.01), skip the denoising step entirely to avoid any overhead

This approach has the following advantages:

- Works immediately with all three existing models in MODEL_REGISTRY
  (RealESRGAN_x4plus, RealESRGAN_x2plus, RealESRGAN_x4plus_anime_6B)
- No additional model weight files need to be downloaded
- No additional memory overhead
- OpenCV's fastNlMeansDenoisingColored is already available (cv2 is
  already a dependency of the project, imported at line 31 of
  image_upscaler.py)
- Simple to implement — a single function call before the existing
  upscale pipeline

And these disadvantages compared to Approach A:

- Denoising and upscaling are separate operations rather than integrated,
  which can produce slightly inferior results (denoising may remove fine
  detail that the upscaler would have otherwise enhanced)
- The pre-processing step adds computational overhead to every upscale
  operation (fastNlMeansDenoising is not trivial — it involves patch
  matching across the image)
- The denoising effect may differ from what Real-ESRGAN's native DNoise
  approach would produce

### 1.3 Proposed Solution

This feature recommends implementing **Approach B (OpenCV pre-processing)
first** as the immediate solution, with **Approach A (DNoise weight
interpolation) documented as a future enhancement** that can be added
later without changing the API or user-facing behavior.

The core implementation adds a denoising pre-processing step inside the
`upscale_image()` function in `backend/core_engine/image_upscaler.py`.
When `denoise_strength` is greater than a threshold (0.01), the input
image is passed through `cv2.fastNlMeansDenoisingColored()` before
being sent to the upscaler model. The denoise_strength float (0.0–1.0)
is mapped to the OpenCV filter strength parameter.

The implementation also includes a fast-path optimization: when
`denoise_strength` is 0 or below the threshold, the denoising step is
completely skipped with zero performance overhead.

### 1.4 Scope

| In Scope | Out of Scope |
|----------|-------------|
| OpenCV-based pre-processing denoise in upscale_image() | Downloading or adding new model weight files |
| Mapping denoise_strength (0.0–1.0) to OpenCV h parameter | Implementing the DNoise weight interpolation (Approach A) |
| Fast-path skip when denoise_strength is 0 or near-zero | Adding the SRVGGNetCompact architecture |
| Updating the docstrings to reflect that denoise is functional | Changing the frontend UI slider behavior or range |
| Logging the denoise settings when denoising is applied | Changing the API or serializer fields |
| Unit tests for the denoising logic | Adding new model entries to MODEL_REGISTRY |
| Optional: helper function for denoise parameter mapping | Changing the upscale model caching strategy |
| Document Approach A as a future enhancement path | Implementing Approach A |

### 1.5 Key Files

| File | Lines | Role in Feature |
|------|-------|----------------|
| `backend/core_engine/image_upscaler.py` | 483 lines | Primary target — add denoising to `upscale_image()` and pass-through in `upscale_images_batch()` |
| `backend/core_engine/video_renderer.py` | 1218 lines | No functional changes needed — already passes denoise_strength correctly |
| `backend/api/models.py` | 279 lines | No changes needed — field already exists at L111 and L256 |
| Frontend render settings component | Varies | No changes needed — slider already exists |
| `models/upscalers/` | Directory | No changes — existing model files work with Approach B |
| `backend/tests/` | Varies | New test file for denoise functionality |

### 1.6 Metadata

| Property | Value |
|----------|-------|
| Idea Reference | IDEAS_01, Section 7.5 |
| Dependencies | OpenCV (already installed as cv2, imported at L31 of image_upscaler.py) |
| Risk Level | Low — additive change, existing behavior preserved when denoise_strength=0 |
| Rollback Strategy | Remove the denoise pre-processing conditional block, restore original docstrings |
| Estimated Lines Changed | ~50 new/modified in image_upscaler.py, ~80 new in test file |
| Model Downloads Required | None for Approach B |

### 1.7 Parameter Mapping Detail

The mapping from user-facing `denoise_strength` (0.0 to 1.0) to OpenCV
`fastNlMeansDenoisingColored()` parameters:

| denoise_strength | h (luma) | hForColorComponents | Effect |
|-----------------|----------|--------------------|----|
| 0.0 | Skip entirely | Skip entirely | No denoising — exact same as current behavior |
| 0.1 | 2 | 2 | Very light denoising, barely noticeable |
| 0.2 | 4 | 4 | Light denoising, subtle noise reduction |
| 0.3 | 6 | 6 | Light-moderate, good for low-noise images |
| 0.4 | 8 | 8 | Moderate denoising |
| 0.5 | 10 | 10 | Default — balanced noise reduction |
| 0.6 | 12 | 12 | Moderate-heavy denoising |
| 0.7 | 14 | 14 | Noticeable smoothing |
| 0.8 | 16 | 16 | Heavy denoising, some detail loss |
| 0.9 | 18 | 18 | Very heavy denoising |
| 1.0 | 20 | 20 | Maximum denoising, significant smoothing |

The formula is simply: `h = denoise_strength * 20`

The `templateWindowSize` should be 7 (default) and `searchWindowSize`
should be 21 (default). These can be left at defaults and do not need
to be exposed to the user.

---

## 2. Flow Diagram

### 2.1 Current Upscale Pipeline (Before This Feature)

```
    ┌──────────────────────────────────────────────────────────────────┐
    │           render_project()  [video_renderer.py L568]             │
    │                                                                  │
    │  L732: upscale_denoise = getattr(project,                        │
    │            "upscale_denoise_strength", 0.5)                      │
    │                                                                  │
    │  L918: path_map = upscale_images_batch(                          │
    │            image_paths=...,                                       │
    │            model_name=upscale_model,                              │
    │            denoise_strength=upscale_denoise,  ◄── passed through │
    │        )                                                         │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │      upscale_images_batch()  [image_upscaler.py L439]            │
    │                                                                  │
    │  Iterates over image_paths, calls:                               │
    │                                                                  │
    │  L471: results[src_path] = upscale_image(                        │
    │            src_path, out_path,                                    │
    │            model_name,                                           │
    │            denoise_strength,  ◄── passed through                 │
    │        )                                                         │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │        upscale_image()  [image_upscaler.py L393]                 │
    │                                                                  │
    │  Signature: upscale_image(image_path, output_path,               │
    │                           model_name, denoise_strength=0.5)      │
    │                                                                  │
    │  L403: docstring says "Currently informational"                  │
    │                                                                  │
    │  L407: upscaler = _get_upscaler(model_name)                      │
    │  L413: img = cv2.imread(image_path, ...)                         │
    │                                                                  │
    │  L420: output = upscaler.enhance(img, ...)                       │
    │                    │                                              │
    │                    │  denoise_strength is NOT passed              │
    │                    │  to enhance()                                │
    │                    ▼                                              │
    │          ┌─────────────────────────────────┐                     │
    │          │  _UpscalerInstance.enhance()     │                     │
    │          │  [image_upscaler.py L247]        │                     │
    │          │                                  │                     │
    │          │  No denoise_strength param       │                     │
    │          │  in signature at all.            │                     │
    │          │                                  │                     │
    │          │  Just runs: input → RRDBNet →    │                     │
    │          │  output (whatever denoising      │                     │
    │          │  is baked into the model          │                     │
    │          │  weights is always applied        │                     │
    │          │  identically)                    │                     │
    │          └─────────────────────────────────┘                     │
    │                                                                  │
    │  L427: cv2.imwrite(output_path, output)                          │
    └──────────────────────────────────────────────────────────────────┘
```

### 2.2 Proposed Upscale Pipeline (After This Feature — Approach B)

```
    ┌──────────────────────────────────────────────────────────────────┐
    │           render_project()  [video_renderer.py L568]             │
    │                                                                  │
    │  (No changes to this layer)                                      │
    │                                                                  │
    │  L732: upscale_denoise = getattr(project,                        │
    │            "upscale_denoise_strength", 0.5)                      │
    │  L918: path_map = upscale_images_batch(                          │
    │            ..., denoise_strength=upscale_denoise)                 │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │      upscale_images_batch()  [image_upscaler.py L439]            │
    │                                                                  │
    │  (No changes to this layer — passes through to upscale_image)    │
    └──────────────────────────┬───────────────────────────────────────┘
                               │
                               ▼
    ┌──────────────────────────────────────────────────────────────────┐
    │        upscale_image()  [image_upscaler.py L393]                 │
    │                                                                  │
    │  L407: upscaler = _get_upscaler(model_name)                      │
    │  L413: img = cv2.imread(image_path, ...)                         │
    │  L418: (RGBA → BGR conversion if needed)                         │
    │                                                                  │
    │  ┌────────────────────────────────────────────────────────┐      │
    │  │  NEW: Denoise Pre-Processing Step                      │      │
    │  │                                                        │      │
    │  │  IF denoise_strength > 0.01:                           │      │
    │  │    h = denoise_strength * 20.0                         │      │
    │  │    img = cv2.fastNlMeansDenoisingColored(              │      │
    │  │              img,                                      │      │
    │  │              None,          (destination)              │      │
    │  │              h,             (luma filter strength)     │      │
    │  │              h,             (color filter strength)    │      │
    │  │              7,             (template window size)     │      │
    │  │              21             (search window size)       │      │
    │  │          )                                             │      │
    │  │    logger.info("Applied denoise pre-processing:       │      │
    │  │                 strength=%.2f, h=%.1f")                │      │
    │  │  ELSE:                                                 │      │
    │  │    (Skip denoising — zero overhead fast path)          │      │
    │  │                                                        │      │
    │  └────────────────────────────────────────────────────────┘      │
    │                                                                  │
    │  L420: output = upscaler.enhance(img, ...)                       │
    │                    │                                              │
    │                    │  (img is now pre-denoised if strength > 0)   │
    │                    ▼                                              │
    │          ┌─────────────────────────────────┐                     │
    │          │  _UpscalerInstance.enhance()     │                     │
    │          │  [image_upscaler.py L247]        │                     │
    │          │                                  │                     │
    │          │  No changes to this method.      │                     │
    │          │  Receives the (possibly          │                     │
    │          │  denoised) image and upscales    │                     │
    │          │  it as before.                   │                     │
    │          └─────────────────────────────────┘                     │
    │                                                                  │
    │  L427: cv2.imwrite(output_path, output)                          │
    └──────────────────────────────────────────────────────────────────┘
```

### 2.3 Decision Flow for Denoise Application

```
    ┌────────────────────────────┐
    │  upscale_image() called    │
    │  with denoise_strength     │
    └────────────┬───────────────┘
                 │
                 ▼
    ┌────────────────────────────┐
    │  Is denoise_strength       │
    │  > 0.01?                   │
    └────────┬──────────┬────────┘
             │          │
         YES │          │ NO
             │          │
             ▼          ▼
    ┌────────────────┐  ┌────────────────────────┐
    │  Clamp to      │  │  Skip denoising        │
    │  [0.0, 1.0]    │  │  completely.           │
    │  range         │  │  Log debug: "denoise   │
    └───────┬────────┘  │  skipped (strength     │
            │           │  ≈ 0)"                  │
            ▼           └───────────┬─────────────┘
    ┌────────────────┐              │
    │  Calculate h:  │              │
    │  h = strength  │              │
    │      * 20.0    │              │
    └───────┬────────┘              │
            │                       │
            ▼                       │
    ┌─────────────────────────┐     │
    │  cv2.fastNlMeans-       │     │
    │  DenoisingColored(      │     │
    │    img, None, h, h,     │     │
    │    7, 21                │     │
    │  )                      │     │
    │                         │     │
    │  Log info: applied      │     │
    │  denoise with h=X       │     │
    └───────┬─────────────────┘     │
            │                       │
            ▼                       │
    ┌────────────────────────────┐  │
    │  img is now denoised       │  │
    └───────┬────────────────────┘  │
            │                       │
            ├───────────────────────┘
            │
            ▼
    ┌────────────────────────────┐
    │  Proceed to upscale:       │
    │  upscaler.enhance(img)     │
    └────────────────────────────┘
```

### 2.4 Future Enhancement Path (Approach A — Weight Interpolation)

This diagram documents how the DNoise weight interpolation approach
would work if implemented in a future iteration. This is NOT implemented
in this feature.

```
    ┌──────────────────────────────────────────────────────────────────┐
    │           FUTURE: DNoise Weight Interpolation                     │
    ├──────────────────────────────────────────────────────────────────┤
    │                                                                  │
    │  MODEL_REGISTRY would add a new model pair:                      │
    │                                                                  │
    │  "RealESRGAN_general_x4v3": {                                    │
    │      filename: "realesr-general-x4v3.pth",                       │
    │      wdn_filename: "realesr-general-wdn-x4v3.pth",  ◄── NEW     │
    │      scale: 4,                                                   │
    │      architecture: "SRVGGNetCompact",   ◄── NEW arch needed      │
    │  }                                                               │
    │                                                                  │
    │  _UpscalerInstance.__init__() would:                              │
    │                                                                  │
    │  1. Load clean_state_dict from filename                          │
    │  2. Load wdn_state_dict from wdn_filename                        │
    │  3. For each key in clean_state_dict:                             │
    │       final[key] = clean[key] * (1 - ds) + wdn[key] * ds        │
    │       where ds = denoise_strength                                │
    │  4. Load interpolated weights into the model                     │
    │                                                                  │
    │  This means:                                                     │
    │  - _UpscalerInstance must be parameterized by denoise_strength    │
    │  - Cache key becomes (model_name, denoise_strength)              │
    │  - Changing denoise_strength requires re-loading the model       │
    │  - SRVGGNetCompact architecture must be implemented              │
    │  - Two .pth files must be downloaded per model                   │
    │                                                                  │
    └──────────────────────────────────────────────────────────────────┘
```

### 2.5 Where denoise_strength Lives in Each Layer

```
    ┌────────────────────────────────────────────────────────────────┐
    │  LAYER                    │  WHERE denoise_strength EXISTS      │
    ├───────────────────────────┼────────────────────────────────────┤
    │                           │                                    │
    │  Frontend UI              │  Render settings slider            │
    │        │                  │  (no change needed)                │
    │        ▼                  │                                    │
    │  API Serializer           │  Serialized with project settings  │
    │        │                  │  (no change needed)                │
    │        ▼                  │                                    │
    │  Django Project Model     │  models.py L111:                   │
    │        │                  │  FloatField(default=0.5)           │
    │        ▼                  │  (no change needed)                │
    │  Django GlobalSettings    │  models.py L256:                   │
    │        │                  │  FloatField(default=0.5)           │
    │        ▼                  │  (no change needed)                │
    │  video_renderer.py        │  L732: getattr() read              │
    │        │                  │  L918: passed to batch function    │
    │        ▼                  │  (no change needed)                │
    │  upscale_images_batch()   │  L439: parameter accepted          │
    │        │                  │  L471: passed to upscale_image()   │
    │        ▼                  │  (no change needed)                │
    │  upscale_image()          │  L393: parameter accepted          │
    │        │                  │  *** CHANGE HERE ***               │
    │        │                  │  Add cv2.fastNlMeansDenoising-     │
    │        │                  │  Colored() pre-processing step     │
    │        ▼                  │                                    │
    │  enhance()                │  L247: no parameter                │
    │                           │  (no change needed — receives      │
    │                           │   pre-denoised image)              │
    └────────────────────────────────────────────────────────────────┘
```

---

## 3. Step-by-Step Instructions

### Step 1: Understand the Current upscale_image() Function

Open `backend/core_engine/image_upscaler.py` and review the
`upscale_image()` function starting at line 393.

The function currently does the following in order:

1. Gets a cached upscaler instance via `_get_upscaler(model_name)` at L407
2. Returns the original image path if the upscaler is unavailable at L409
3. Reads the image from disk using `cv2.imread()` at L413
4. Returns the original if the read fails at L415
5. Converts RGBA to BGR if the image has 4 channels at L418–L419
6. Calls `upscaler.enhance(img, tile_size=512, tile_pad=10, pre_pad=10)` at L420–L421
7. Creates the output directory if needed at L426
8. Writes the upscaled image to disk at L427
9. Logs the result at L429–L434
10. Returns the output path at L436

The denoise_strength parameter exists in the function signature but is
not referenced anywhere in the function body after being accepted.

### Step 2: Add a Denoise Helper Function

At the module level in `image_upscaler.py`, before the public API section
(before `upscale_image()`, after the `_get_upscaler()` function), add a
new helper function.

The function should be named `_apply_denoise_preprocessing` and accept
two parameters: the input image (a NumPy BGR uint8 array) and the
denoise_strength float.

The function should implement the following logic:

First, check if denoise_strength is below a threshold of 0.01. If it
is, return the input image unchanged — this is the fast path that adds
zero overhead when denoising is disabled or negligible.

Second, clamp denoise_strength to the range 0.0 to 1.0 to prevent
invalid values. If the value is below 0.0, set it to 0.0. If above
1.0, set it to 1.0.

Third, calculate the OpenCV filter strength parameter h by multiplying
denoise_strength by 20.0. This maps the 0.0–1.0 user range to the
0–20 range that OpenCV's fastNlMeansDenoisingColored expects.

Fourth, call the OpenCV denoising function with the following parameters:
- The source image (BGR uint8 numpy array)
- None for the destination (function returns a new array)
- h for the filter strength on the luminance component
- h for the filter strength on color components (same as luma for
  simplicity — this can be refined later if needed)
- 7 for the templateWindowSize (OpenCV default, size of the patch used
  for weight computation)
- 21 for the searchWindowSize (OpenCV default, size of the area where
  the search is performed)

Fifth, log an info-level message stating that denoise pre-processing was
applied, including the denoise_strength and the calculated h value.

Sixth, return the denoised image.

The function should handle exceptions from OpenCV gracefully — if the
denoising call fails for any reason (for example, an image with an
unexpected number of channels or data type), log a warning and return
the original image unchanged. Wrap the denoising call in a try/except
block for robustness.

### Step 3: Integrate Denoise into upscale_image()

In the `upscale_image()` function at line 393, add the denoising step
between the RGBA-to-BGR conversion (line 418–419) and the upscaler.enhance()
call (line 420–421).

After the line that converts RGBA to BGR (the `cv2.cvtColor` call), and
before the try block that calls `upscaler.enhance()`, insert a call to
the helper function created in Step 2. Pass the image and the
denoise_strength parameter.

The result of the helper function replaces the `img` variable, so the
subsequent `upscaler.enhance(img, ...)` call receives the denoised image.

The insertion point is between the current lines 419 and 420 of the file.

### Step 4: Update the upscale_image() Docstring

Update the docstring of `upscale_image()` to reflect that denoise_strength
is now functional. The docstring at lines 398–406 currently says:

"denoise_strength: Denoise strength (0–1). Currently informational;
the model architecture determines denoising."

Change this to describe the actual behavior: the parameter controls the
strength of OpenCV non-local means denoising applied as a pre-processing
step before upscaling. A value of 0.0 skips denoising entirely. A value
of 0.5 applies moderate denoising. A value of 1.0 applies maximum
denoising. The denoising uses cv2.fastNlMeansDenoisingColored with the
h parameter set to denoise_strength multiplied by 20.

### Step 5: Update the upscale_images_batch() Docstring

Update the docstring of `upscale_images_batch()` at line 439 similarly.
The current docstring for the denoise_strength parameter at approximately
line 455 says "Denoise strength (0–1)." — update it to match the
description written in Step 4, noting that the denoising is applied as
a pre-processing step before each image is upscaled.

### Step 6: Add Logging to upscale_image() for Denoise Status

In the logging statement at lines 429–434 of `upscale_image()` which
currently logs the upscale result with input/output dimensions, add the
denoise_strength to the log message so operators can see whether
denoising was applied and at what strength when reviewing render logs.

The current log message is:
"Upscaled source.png → source_upscaled.png (1920x1080 → 7680x4320)"

Enhance it to include the denoise information:
"Upscaled source.png → source_upscaled.png (1920x1080 → 7680x4320, denoise=0.50)"

### Step 7: Consider Performance Implications

The `cv2.fastNlMeansDenoisingColored()` function is not trivial — for a
typical 1920x1080 image, it can take 2–5 seconds depending on CPU speed.
For a 4K image, it could take 10+ seconds. This overhead is additive to
the already-expensive GAN upscale step.

To mitigate this, ensure the fast-path skip in the helper function
(Step 2) is implemented correctly so that denoise_strength=0 adds
zero overhead.

Additionally, consider logging the time taken for the denoising step
separately so that developers and users can understand the performance
breakdown. Capture the wall-clock time before and after the denoising
call and include it in the log message.

No changes to the function signatures are needed for this — it is purely
about internal logging.

### Step 8: Add a Module-Level Constant for the Denoise Threshold

At the top of `image_upscaler.py`, near the MODEL_REGISTRY definition
(around line 40), add a module-level constant for the minimum denoise
strength threshold below which denoising is skipped. Set this to 0.01.
Name it something clear like `_DENOISE_MIN_THRESHOLD`.

Also add a constant for the maximum OpenCV h parameter value. Set this
to 20.0. Name it `_DENOISE_MAX_H`.

Using named constants rather than magic numbers in the helper function
makes the mapping logic self-documenting and easy to tune later.

### Step 9: Add a Module-Level Constant for Default Window Sizes

Add constants for the template window size (7) and search window size
(21) used in the denoising function call. These OpenCV defaults work
well for most images but should be easily adjustable if needed in the
future. Name them `_DENOISE_TEMPLATE_WINDOW` and `_DENOISE_SEARCH_WINDOW`.

### Step 10: Document the Future DNoise Enhancement Path

At the bottom of `image_upscaler.py`, before the `clear_cache()` function
(currently at approximately line 479), add a comment block describing the
future enhancement path for Approach A (DNoise weight interpolation).

The comment should explain:
- The concept of loading paired model weights (clean + WDN)
- The weight interpolation formula
- That this would require adding `SRVGGNetCompact` architecture support
- That the cache key would need to include denoise_strength
- That model files would need to be downloaded separately
- A reference to this feature document for full details

This serves as a breadcrumb for future developers who want to implement
the more sophisticated approach.

### Step 11: Write Unit Tests for the Denoise Helper

Create a new test file at `backend/tests/test_denoise.py` or add tests
to an existing test file.

Write the following test cases:

**Test 1: Fast path — denoise_strength = 0.0.**
Create a simple synthetic test image using NumPy (for example, a solid
color 100x100 image). Call the helper function with denoise_strength=0.0.
Verify that the returned image is identical to the input (same array,
or same pixel values). This confirms the fast path returns the image
unchanged.

**Test 2: Fast path — denoise_strength very small (0.005).**
Similar to Test 1, but with a value below the 0.01 threshold. Verify
the image is returned unchanged.

**Test 3: Moderate denoise — denoise_strength = 0.5.**
Create a synthetic noisy image by generating a base pattern and adding
Gaussian noise using NumPy random. Call the helper with
denoise_strength=0.5. Verify that the returned image is different from
the input (denoising was applied). Also verify the returned image is
still a valid uint8 BGR array with the same dimensions.

**Test 4: Maximum denoise — denoise_strength = 1.0.**
Similar to Test 3 but with maximum strength. Verify the output is
different from the input. Optionally verify that the output has less
variance (noise) than the moderate denoise output, though this is
harder to assert precisely.

**Test 5: Clamping — denoise_strength > 1.0.**
Call the helper with denoise_strength=1.5. Verify it does not raise
an exception and returns a valid image. The strength should be
internally clamped to 1.0.

**Test 6: Clamping — denoise_strength < 0.0.**
Call the helper with denoise_strength=-0.5. Verify it either returns
the image unchanged (treating negative as "no denoise") or clamps
to 0.0 and skips. Either behavior is acceptable as long as no
exception is raised.

**Test 7: Image type preservation.**
Verify that the output image has the same dtype (uint8) and shape
(HxWx3) as the input.

**Test 8: Full pipeline test — upscale_image with denoise.**
This test is only possible if PyTorch and the model weights are
available. If the test environment has them, create a small test
image (64x64), save it to a temporary file, and call `upscale_image()`
with denoise_strength=0.5. Verify the output file exists and is a
valid image. Mark this test with a skip decorator if PyTorch is not
available.

**Test 9: Integration with upscale_images_batch.**
Similar to Test 8 but testing the batch function with multiple images
and a non-zero denoise_strength. Verify all output files exist.

**Test 10: Denoise has no effect on pure white image.**
Create a perfectly clean (all white, value 255) test image. Apply
denoise with strength=1.0. The result should be very close to the
original since there is no noise to remove. Verify pixel values are
within a small tolerance (plus/minus 1 due to rounding).

### Step 12: Update the MODULE_REGISTRY Docstring

The module-level docstring at the top of `image_upscaler.py` (lines 1–19)
should be updated to mention that denoise pre-processing is supported
via OpenCV's non-local means denoising. Add a brief note after the
"Supported models" list explaining that all models support denoise
strength control as a pre-processing step.

### Step 13: Verify No Changes Needed in video_renderer.py

Confirm by re-reading the upscale section in `video_renderer.py`
(lines 898–943 and line 732) that the denoise_strength value is
already being correctly read from the project and passed through to
`upscale_images_batch()`. Since the change is entirely within the
`upscale_image()` function's internal behavior, the renderer does
not need any modification.

### Step 14: Verify No Changes Needed in models.py

Confirm that the `upscale_denoise_strength` field on the Project model
(line 111 of models.py) and GlobalSettings model (line 256) already
exist with the correct type (FloatField) and default (0.5). No migration
is needed.

### Step 15: Verify No Changes Needed in the Frontend

Confirm that the frontend already has a denoise strength slider in the
render settings panel. The slider should already send values in the
0.0–1.0 range. No frontend changes are needed.

### Step 16: Verify No Changes Needed in API Serializers

Check the API serializer in `backend/api/serializers.py` to confirm
that `upscale_denoise_strength` is already included in the serialized
fields. Since the field already exists on the model and is already
being passed through the API, no serializer changes are needed.

### Step 17: Consider Edge Case — RGBA Images

The current `upscale_image()` function converts RGBA images to BGR
before upscaling (lines 418–419). The denoise helper function should
be called AFTER this conversion, so it always receives a 3-channel
BGR uint8 image. Verify that the insertion point in Step 3 is after
the RGBA conversion.

If for some reason the denoising is called before the RGBA conversion,
`cv2.fastNlMeansDenoisingColored()` would fail or produce unexpected
results on a 4-channel image.

### Step 18: Consider Edge Case — Grayscale Images

If a grayscale image (1 channel or 2 channels with alpha) is loaded,
`cv2.fastNlMeansDenoisingColored()` expects a 3-channel image and will
raise an error. The helper function should check the number of channels
before calling the denoising function. If the image has fewer than 3
channels, either skip denoising (with a warning log) or convert to
3-channel first using cv2.cvtColor. The simplest approach is to skip
denoising and log a warning, since grayscale images are unusual in the
StoryFlow context (all segment images are expected to be color).

Add a channel count check at the beginning of the helper function,
after the threshold check and before the denoising call. If
`img.ndim != 3 or img.shape[2] != 3`, log a warning and return the
image unchanged.

### Step 19: Consider Edge Case — Very Small Images

For very small images (smaller than the search window size of 21x21
pixels), `cv2.fastNlMeansDenoisingColored()` may fail or produce
artifacts. Add a size check in the helper function: if the image
width or height is less than the search window size (21 pixels),
skip denoising and return the image unchanged with a debug-level
log message.

### Step 20: Performance Timing Integration

In the `upscale_image()` function, capture timing information for the
denoise step separately from the upscale step. After inserting the
denoise call (Step 3), wrap it with time measurement. Log the time
taken for denoising as a debug-level message.

This allows developers to understand how much of the per-image upscale
time is spent on denoising versus the actual GAN inference.

For example, before the denoise call, capture the current time. After
the call, calculate the elapsed time. Log at debug level:
"Denoise pre-processing took X.XXs for image WxH"

### Step 21: Run Full Test Suite

After all code changes are complete, run the existing test suite:
- Any existing upscaler tests
- The end-to-end render test in `backend/tests/test_e2e.py`
- The new denoise unit tests

Verify that all tests pass. Pay special attention to the E2E test
which exercises the full render pipeline — it should continue to pass
because the default denoise_strength of 0.5 now actually applies
denoising (which is a visible change in the output, but should not
cause test failures if the test only checks for successful render
completion and valid output file).

### Step 22: Manual Visual Verification

For a final verification, render two copies of the same project:
1. One with denoise_strength = 0.0
2. One with denoise_strength = 1.0

Compare the output images in the `upscaled_images/` directory. The
difference should be visually apparent:
- The 0.0 version should look identical to the current behavior
  (before this feature)
- The 1.0 version should appear noticeably smoother with reduced
  noise grain, possibly with slight loss of fine texture detail

---

## 4. Expected Outcome

### 4.1 Functional Changes

**Before this feature:**
- The denoise_strength slider in the UI is a non-functional control
- Setting denoise_strength to 0.0 and 1.0 produces identical output
- The upscale pipeline applies whatever denoising is baked into the
  model weights, with no user control
- The `upscale_image()` docstring explicitly states that denoise_strength
  is "currently informational"

**After this feature:**
- The denoise_strength slider in the UI is fully functional
- Setting denoise_strength to 0.0 produces output with no additional
  denoising (identical to current behavior)
- Setting denoise_strength to 0.5 applies moderate denoising before
  upscaling, reducing visible noise in the upscaled result
- Setting denoise_strength to 1.0 applies maximum denoising, producing
  a noticeably smoother result with some fine detail reduction
- The `upscale_image()` docstring accurately describes the behavior
- All log messages reflect the denoise settings being applied

### 4.2 Visual Quality Impact

The denoise pre-processing step has the following visual effects on
the upscaled output:

**For clean source images (high-quality photographs, digital art):**
- denoise_strength = 0.0 to 0.2: No visible difference (images are
  already clean, denoising has nothing to remove)
- denoise_strength = 0.3 to 0.7: Very subtle smoothing, barely
  noticeable on clean sources
- denoise_strength = 0.8 to 1.0: Slight softening of fine textures,
  which may or may not be desirable

**For noisy source images (low-light photos, compressed JPEGs, AI-generated images with artifacts):**
- denoise_strength = 0.0: Noise is amplified by the upscaler (this is
  the current behavior — Real-ESRGAN tends to amplify noise in
  noisy inputs because it was trained primarily on clean images)
- denoise_strength = 0.3 to 0.5: Most visible noise is removed while
  preserving important detail. This is the recommended setting for
  typical AI-generated story images.
- denoise_strength = 0.7 to 1.0: Heavy denoising that removes almost
  all noise but may also remove fine detail like hair strands, fabric
  texture, or text edges

**For AI-generated images (Stable Diffusion, DALL-E, Midjourney):**
AI-generated images often have subtle artifacts that are not exactly
noise but can benefit from light denoising. A denoise_strength of 0.3
to 0.5 is generally optimal for these images. The non-local means
algorithm is particularly effective at smoothing the kind of
high-frequency artifacts that AI image generators produce.

### 4.3 Performance Impact

**When denoise_strength = 0 (fast path):**
Zero performance impact. The threshold check short-circuits before any
OpenCV function is called. This means users who do not want denoising
(or projects that have the default 0.5 strength lowered to 0.0) will
see no change in render time.

**When denoise_strength > 0 (denoising active):**
The `cv2.fastNlMeansDenoisingColored()` function adds processing time
proportional to the image size:

| Image Resolution | Approximate Denoise Time | Upscale Time (typical) | Overhead |
|-----------------|-------------------------|----------------------|---------|
| 512 x 512 | ~0.5s | ~2s | +25% |
| 1024 x 1024 | ~2s | ~5s | +40% |
| 1920 x 1080 | ~3.5s | ~8s | +44% |
| 3840 x 2160 | ~12s | ~25s | +48% |

For a typical 20-segment project at 1920x1080 with denoise_strength=0.5:
- Before: ~160s (8s per image × 20 images) for upscaling alone
- After: ~230s (11.5s per image × 20 images) for upscaling + denoise
- Additional time: ~70s total, or ~3.5s per image

This is a meaningful overhead but acceptable given that upscaling is
already a slow operation and the user has explicitly opted into it.

### 4.4 Backward Compatibility

**For projects with denoise_strength = 0.0:**
Output is byte-for-byte identical to the pre-feature behavior.

**For projects with the default denoise_strength = 0.5:**
Output will be visually different — images will be pre-denoised before
upscaling. This is a deliberate functional change. The new behavior is
what the UI has been advertising all along. The default of 0.5 applies
moderate denoising which should improve quality for most typical
AI-generated story images.

**For projects with denoise_strength = 1.0:**
Output will be significantly smoother. Users who explicitly set maximum
denoise now get what they asked for.

### 4.5 File Changes Summary

| File | Type of Change | Lines Affected |
|------|---------------|---------------|
| `backend/core_engine/image_upscaler.py` | New helper function | ~25 lines added near L385 |
| `backend/core_engine/image_upscaler.py` | Integration in upscale_image() | ~3 lines added near L420 |
| `backend/core_engine/image_upscaler.py` | Updated docstrings | ~6 lines modified at L398 and L455 |
| `backend/core_engine/image_upscaler.py` | New module constants | ~5 lines added near L40 |
| `backend/core_engine/image_upscaler.py` | Future enhancement comment | ~15 lines added near L475 |
| `backend/core_engine/image_upscaler.py` | Updated module docstring | ~3 lines modified at L1 |
| `backend/tests/test_denoise.py` | New test file | ~120 lines |
| **Total** | | ~175 lines |

### 4.6 No Changes Required

The following files and components require zero modifications:

- `backend/core_engine/video_renderer.py` — already passes denoise_strength
  correctly through the entire call chain
- `backend/api/models.py` — field already exists at L111 and L256
- `backend/api/serializers.py` — field already serialized
- `backend/api/views.py` — no changes needed
- Frontend components — slider already exists and sends correct values
- Database schema — no migrations needed
- `models/upscalers/` model files — existing models all work with Approach B
- `backend/core_engine/fast_compositor.py` — not involved in upscaling
- `backend/core_engine/video_renderer.py` — no changes needed

---

## 5. Verification Checklist

### 5.1 Functional Tests

- [ ] When denoise_strength = 0.0, the upscaled output is identical to
      the output produced before this feature was implemented
- [ ] When denoise_strength = 0.5, the upscaled output shows visible
      noise reduction compared to denoise_strength = 0.0
- [ ] When denoise_strength = 1.0, the upscaled output shows heavy
      noise reduction and some detail smoothing
- [ ] When denoise_strength is not provided (default 0.5), denoising
      is applied with moderate strength
- [ ] The denoise pre-processing applies to all three supported models:
      RealESRGAN_x4plus, RealESRGAN_x2plus, RealESRGAN_x4plus_anime_6B

### 5.2 Edge Case Tests

- [ ] denoise_strength = 0.0 triggers the fast path (no OpenCV call)
- [ ] denoise_strength = 0.005 (below threshold) triggers the fast path
- [ ] denoise_strength = 0.01 (at threshold) skips denoising
- [ ] denoise_strength = 0.02 (above threshold) applies denoising
- [ ] denoise_strength = -0.5 is handled gracefully (clamped or skipped)
- [ ] denoise_strength = 1.5 is handled gracefully (clamped to 1.0)
- [ ] Grayscale image input does not crash (skipped with warning)
- [ ] Very small image (10x10 pixels) does not crash (skipped with warning)
- [ ] RGBA image is correctly converted to BGR before denoising

### 5.3 Performance Tests

- [ ] Measure upscale time for a 1920x1080 image with denoise_strength=0.0
      and verify it is within 1% of the pre-feature baseline
- [ ] Measure upscale time for a 1920x1080 image with denoise_strength=0.5
      and verify the overhead is reasonable (under 5 seconds per image)
- [ ] Verify that the denoise timing is logged separately so operators can
      see the performance breakdown

### 5.4 Integration Tests

- [ ] Run the full E2E render test (`backend/tests/test_e2e.py`) with
      upscaling enabled and denoise_strength=0 — verify pass
- [ ] Run the full E2E render test with upscaling enabled and
      denoise_strength=0.5 — verify pass
- [ ] Verify that the render log output includes denoise information
      in the upscale log messages
- [ ] Verify that `upscale_images_batch()` correctly passes denoise
      through to each `upscale_image()` call

### 5.5 Docstring and Documentation Tests

- [ ] The `upscale_image()` docstring no longer says "currently informational"
- [ ] The `upscale_image()` docstring correctly describes the denoise behavior
- [ ] The `upscale_images_batch()` docstring correctly describes denoise
- [ ] The module-level docstring mentions denoise support
- [ ] The future enhancement comment block is present and accurate

### 5.6 Manual Visual Verification

- [ ] Create a project with a noisy AI-generated image as one segment
- [ ] Render with upscaling enabled, denoise_strength = 0.0
- [ ] Check the upscaled image in the upscaled_images/ output directory
- [ ] Re-render with denoise_strength = 0.5 and compare visually
- [ ] Re-render with denoise_strength = 1.0 and compare visually
- [ ] The 0.0 version should show visible noise (especially in flat areas)
- [ ] The 0.5 version should show reduced noise with preserved detail
- [ ] The 1.0 version should show smooth areas with reduced fine detail

### 5.7 Code Quality Checks

- [ ] No new dependencies added (cv2 already imported at line 31)
- [ ] All new code follows existing logging patterns (using module logger)
- [ ] All new constants are clearly named with underscore prefix
      for module-private scope
- [ ] The helper function is defensive (try/except around OpenCV call)
- [ ] No changes to public API signatures
- [ ] All existing tests still pass

---

## 6. Notes for AI Agent

### 6.1 Implementation Order

Follow this exact sequence:

1. Add new module-level constants to `image_upscaler.py` (Steps 8–9).
   These are standalone additions near the top of the file.
2. Add the `_apply_denoise_preprocessing()` helper function (Step 2).
   This is a standalone function with no dependencies on other changes.
3. Write and run the unit tests for the helper function (Step 11,
   Tests 1–7). Verify the helper works correctly in isolation.
4. Integrate the helper into `upscale_image()` (Step 3). This is the
   core change — a single call inserted at the right location.
5. Update docstrings (Steps 4–5, 12).
6. Add logging enhancements (Steps 6, 20).
7. Add the future enhancement comment block (Step 10).
8. Write and run integration tests (Step 11, Tests 8–10).
9. Run the full test suite (Step 21).
10. Perform manual visual verification if possible (Step 22).

### 6.2 Critical File Locations and Line Numbers

**`backend/core_engine/image_upscaler.py`** (483 lines total):

- Module docstring: lines 1–19
- Imports: lines 21–32 (cv2 imported at line 31)
- MODEL_REGISTRY: lines 40–63 (defines 3 models with their config dicts)
- `_MODELS_DIR` constant: line 69
- `get_models_dir()`: line 72
- `get_available_models()`: line 77
- PyTorch conditional import: lines 96–99
- `ResidualDenseBlock`: lines 106–121
- `RRDB`: lines 123–135
- `_pixel_unshuffle()`: lines 137–144
- `RRDBNet`: lines 146–190
- `_UpscalerInstance` class: line 203
  - `__init__()`: lines 207–241
  - `enhance()`: lines 247–296 (this is the tile-based inference method)
  - `_tile_process()`: lines 298–340
- `_upscaler_cache` and `_cache_lock`: lines 346–347
- `_get_upscaler()`: lines 350–380
- **PUBLIC API SECTION**: lines 385 onwards
- `upscale_image()`: lines 393–436
  - Signature: lines 393–397
  - Docstring: lines 398–406
  - Get upscaler: line 407
  - Read image: line 413
  - RGBA conversion: lines 418–419
  - **INSERT DENOISE HERE: between L419 and L420**
  - enhance() call: lines 420–421 (inside try block)
  - Write output: line 427
  - Log result: lines 429–434
- `upscale_images_batch()`: lines 439–477
  - Signature: lines 439–445
  - Docstring: lines 446–456
- `clear_cache()`: lines 479–483

**Insertion points:**
- New constants: Add after MODEL_REGISTRY block (after line 63) or just
  before the PUBLIC API section (before line 385)
- New helper function: Add just before `upscale_image()` at line 393 —
  between _get_upscaler() and the PUBLIC API comment line
- Denoise call in upscale_image(): Between lines 419 and 420

**`backend/api/models.py`** (279 lines):
- Project.upscale_denoise_strength at line 111 — DO NOT MODIFY
- GlobalSettings.upscale_denoise_strength at line 256 — DO NOT MODIFY

**`backend/core_engine/video_renderer.py`** (1218 lines):
- L732: reads denoise from project — DO NOT MODIFY
- L918: passes to upscale_images_batch — DO NOT MODIFY

### 6.3 The Exact Function to Call

The OpenCV function to use is `cv2.fastNlMeansDenoisingColored`.

Its full signature with the relevant parameters:

- `src`: The input image. Must be 8-bit 3-channel (BGR uint8).
- `dst`: The destination image. Pass None to have the function create
  and return a new array.
- `h`: Filter strength for the luminance component. Higher value removes
  more noise but also removes detail. A good range is 3 to 20.
- `hForColorComponents`: Filter strength for color components. Usually
  set to the same value as h or slightly lower.
- `templateWindowSize`: Size of the template patch. Should be odd.
  Default 7 is standard.
- `searchWindowSize`: Size of the area where the search is performed.
  Should be odd. Default 21 is standard. Larger values are slower but
  produce better results.

The function returns the denoised image as a new numpy array with the
same shape and dtype as the input.

### 6.4 Do NOT Change

- Do NOT modify `_UpscalerInstance.enhance()`. The denoising happens
  BEFORE the image reaches this method.
- Do NOT modify `_UpscalerInstance.__init__()`. No changes to model
  loading are needed for Approach B.
- Do NOT modify `MODEL_REGISTRY`. No new model entries needed.
- Do NOT modify `_get_upscaler()`. No changes to caching needed.
- Do NOT modify `backend/api/models.py`. No schema changes.
- Do NOT modify `backend/core_engine/video_renderer.py`. The
  denoise_strength already travels correctly through the pipeline.
- Do NOT modify any frontend code. The slider already works.
- Do NOT download any new model files. Approach B uses only OpenCV.
- Do NOT implement Approach A (weight interpolation) in this feature.
  Only document it as a future enhancement path.

### 6.5 OpenCV Import Verification

The `cv2` module is already imported at line 31 of `image_upscaler.py`:
`import cv2`

No new import is needed for the denoising function. The function
`cv2.fastNlMeansDenoisingColored` is part of the standard OpenCV
package (`opencv-python` or `opencv-python-headless`), which is
already listed in `backend/requirements.txt` and already used
extensively in the image upscaler module.

### 6.6 Testing Without PyTorch

The helper function `_apply_denoise_preprocessing()` only uses OpenCV
(cv2) and NumPy — it does NOT require PyTorch. Unit tests for the
helper function (Tests 1–7 in Step 11) can be run on any machine with
OpenCV installed, even without PyTorch.

The integration tests (Tests 8–9) that call `upscale_image()` DO
require PyTorch and the model weight files. These tests should be
decorated with an appropriate skip condition (skip if PyTorch not
available or if model file does not exist).

### 6.7 Keeping the Behavior Deterministic

`cv2.fastNlMeansDenoisingColored()` is deterministic — given the same
input image and parameters, it always produces the same output. This
means that renders with the same denoise_strength will produce
identical results, which is important for reproducibility.

### 6.8 Thread Safety

The helper function `_apply_denoise_preprocessing()` creates no shared
state and only operates on the input numpy array. It is inherently
thread-safe and will work correctly if `upscale_images_batch()` is
later parallelized (Feature 1.4).

The OpenCV function `cv2.fastNlMeansDenoisingColored()` is also
thread-safe as it operates on input/output arrays without modifying
global state.

### 6.9 Memory Considerations

The denoising function creates a copy of the image internally (it
does not modify the input in-place when `dst=None`). For a 1920x1080
BGR uint8 image, this is approximately 6 MB of additional memory.
This is negligible compared to the memory used by the PyTorch model
(hundreds of MB for the RRDBNet weights and intermediate tensors).

The denoised image replaces the `img` local variable in
`upscale_image()`, so the original un-denoised image is eligible for
garbage collection once the replacement happens.

### 6.10 Logging Patterns to Follow

The existing `image_upscaler.py` uses these logging patterns:

- `logger.info(...)` for important operational messages (model loaded,
  image upscaled successfully)
- `logger.warning(...)` for recoverable issues (model file not found,
  upscaler unavailable)
- `logger.error(...)` for failures (failed to read image, upscaling
  failed)
- `logger.debug(...)` for verbose details (not currently used much)

For the denoise feature, use:
- `logger.info(...)` when denoising is applied, including parameters
- `logger.debug(...)` for the fast-path skip and timing details
- `logger.warning(...)` if the denoising call fails (with fallback
  to returning the original image)

### 6.11 Docstring Style to Follow

The existing docstrings in `image_upscaler.py` use NumPy/Google-hybrid
style with Args and Returns sections. Follow this same style when
updating the docstrings. Use four-space indentation within the
docstring. Use double backticks for inline code references in the
docstring text.

### 6.12 Test File Location

Place the test file at `backend/tests/test_denoise.py`. The
`backend/tests/` directory already contains `__init__.py`,
`test_e2e.py`, and `test_settings.py`. Follow the existing patterns
in those files.

If preferred, the tests can be added to
`backend/core_engine/tests/test_image_upscaler.py` if that file
exists, or created at that path if it does not. Check the
`backend/core_engine/tests/` directory for existing test files.

### 6.13 Verification Commands

After implementation, run from the `backend/` directory:

1. Verify the helper function works:
   `python -c "from core_engine.image_upscaler import _apply_denoise_preprocessing; print('OK')"`

2. Run unit tests:
   `python manage.py test tests.test_denoise -v 2`

3. Run all tests:
   `python manage.py test -v 2`

4. If model weights are available, test a real upscale:
   `python -c "from core_engine.image_upscaler import upscale_image; upscale_image('test.png', 'out.png', denoise_strength=0.5)"`

### 6.14 Future Enhancement Notes (Approach A)

When Approach A (DNoise weight interpolation) is eventually implemented,
the following changes would be needed (NOT part of this feature):

1. Add `SRVGGNetCompact` architecture class alongside the existing
   `RRDBNet` class. This is a simpler architecture (no sub-pixel
   convolution, uses PixelShuffle directly). It has fewer parameters
   and is faster to run.

2. Add new entries to MODEL_REGISTRY for the general-v3 model pair:
   - `"RealESRGAN_general_x4v3"` with filename
     `"realesr-general-x4v3.pth"` and an additional `wdn_filename`
     field pointing to `"realesr-general-wdn-x4v3.pth"`
   - Mark these entries with `"architecture": "SRVGGNetCompact"` to
     distinguish from the existing RRDB models

3. Modify `_UpscalerInstance.__init__()` to accept a `denoise_strength`
   parameter. When a `wdn_filename` is present in the model info dict,
   load both weight files and interpolate:
   - `final_state_dict = {}`
   - For each key: `final_state_dict[key] = clean[key] * (1 - ds) + wdn[key] * ds`
   - Load the interpolated state dict into the model

4. Modify the cache key in `_get_upscaler()` from just `model_name`
   to `(model_name, denoise_strength)`, since different denoise
   strengths produce different weight sets

5. The OpenCV pre-processing from Approach B would still be kept as
   an option for models without WDN variants (the existing x4plus,
   x2plus, anime_6B models), or removed if all models are migrated
   to have WDN variants

6. Download and add the model weight files to `models/upscalers/`:
   - `realesr-general-x4v3.pth` (~65 MB)
   - `realesr-general-wdn-x4v3.pth` (~65 MB)

This is documented here for future reference. None of these changes
are part of the current Feature 7.5 implementation.

---

*End of Feature 7.5 — Denoise Strength Implementation*
