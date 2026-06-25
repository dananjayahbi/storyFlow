# Feature 1.7 — CLIP-Based Image-Prompt Matching

| Field | Value |
|---|---|
| Feature ID | 1.7 |
| Title | CLIP-Based Image-Prompt Matching |
| Status | 🟡 Planned |
| Priority | High |
| Complexity | Medium |
| Estimated Effort | 3–4 days |
| Dependencies | Feature 1.6 (image_style appended to prompt), CLIP ONNX model (~350 MB) available in `models/clip/` |
| Output Files (NEW) | `backend/core_engine/clip_scorer.py`, `frontend/components/MatchBadge.tsx` |
| Files Modified | `backend/core_engine/model_loader.py`, `backend/api/views.py`, `backend/api/urls.py`, `frontend/components/SegmentCard.tsx`, `frontend/app/projects/[id]/page.tsx` |

---

## 1. Document Overview

### 1.1 Problem Statement

When a user uploads an image for a segment in StoryFlow, there is currently no automated quality check to verify that the uploaded image is visually related to the segment's `image_prompt` text. A creator might accidentally import image assets in the wrong order, assigning a photograph of a mountain landscape to a segment whose prompt describes a busy city street. Likewise, AI-generated images returned from a third-party generation API can occasionally hallucinate scenes that bear no resemblance to the instructed prompt — and without an objective measure, these mismatches silently pass into the final video render. As the project scales to dozens or hundreds of segments, manually reviewing each image-to-prompt pairing is impractical and unreliable, making an automated similarity check a critical quality-of-life feature.

### 1.2 Proposed Solution

Integrate the CLIP (Contrastive Language-Image Pretraining) model into the backend rendering core to compute a semantic similarity score between each segment's uploaded image and the segment's `image_prompt` text. The score is a cosine similarity value in the range 0.0 to 1.0, where higher values indicate stronger semantic alignment between the visual content of the image and the textual description of the prompt. The score is exposed through an API endpoint and displayed in the frontend as a color-coded badge on the segment card, giving creators immediate, actionable feedback.

- Add a `load_clip_model()` function to `backend/core_engine/model_loader.py` that lazily loads a CLIP ONNX model file from `models/clip/clip.onnx` and caches it as a module-level singleton to avoid repeated disk reads
- Create a new utility module `backend/core_engine/clip_scorer.py` with a `compute_image_prompt_similarity(image_path, prompt_text)` function that prepares inputs, runs the ONNX inference, and returns a float cosine similarity score
- Implement a new Django REST endpoint `POST /api/segments/{id}/check-image-match/` in `backend/api/views.py` that fetches the segment, calls the scorer, and returns `{score, label, threshold_passed}` where label is "Good Match", "Fair Match", or "Low Match"
- Display the result in `frontend/components/SegmentCard.tsx` as a `MatchBadge` component with color-coded states: green for "Good Match" (score ≥ 0.40), amber for "Fair Match" (score 0.25–0.39), and red for "Low Match" (score < 0.25)
- Provide a project-level "Check All Matches" button on the project page that calls the endpoint for every segment and summarizes results, highlighting segments that fail the threshold
- Make the CLIP model optional — if `models/clip/clip.onnx` does not exist, the badge is hidden and the "Check All" button shows a tooltip explaining how to download the model
- Expose the similarity threshold (0.25) as a named constant in `backend/core_engine/clip_scorer.py` so future agents can tune it without searching through logic branches

### 1.3 Scope

| Category | In Scope |
|---|---|
| In Scope | Loading a pre-exported CLIP ONNX model from local disk |
| In Scope | Computing cosine similarity between image and text embeddings via ONNX runtime |
| In Scope | REST endpoint returning score, label, and threshold-passed flag per segment |
| In Scope | Frontend badge on SegmentCard reflecting the latest score, and a project-wide batch check button |

| Category | Out of Scope |
|---|---|
| Out of Scope | Fine-tuning or training the CLIP model on StoryFlow-specific domain data |
| Out of Scope | Blocking the render pipeline if image-prompt scores are low — checks are advisory only |
| Out of Scope | Automatically replacing low-scoring images with better-matched generated alternatives |
| Out of Scope | Storing historical match scores over time or showing score trends per segment |

### 1.4 Key Files Reference

| File | Role | Current State |
|---|---|---|
| `backend/core_engine/model_loader.py` | Central model loader; loads TTS and upscaler ONNX models | Exists; add `load_clip_model()` here |
| `backend/core_engine/clip_scorer.py` | New utility for CLIP cosine similarity computation | Does not exist; must be created |
| `backend/api/views.py` | DRF viewsets and endpoints | Exists; add `CheckImageMatchView` class |
| `backend/api/urls.py` | URL routing for the API | Exists; register the new endpoint path |
| `frontend/components/SegmentCard.tsx` | Renders one segment's image, text, audio controls | Exists; add match badge and score trigger logic |
| `frontend/components/MatchBadge.tsx` | Color-coded score badge component | Does not exist; must be created |

---

## 2. Flow Diagram

```
User uploads image to segment
          │
          ▼
Frontend: POST /api/segments/{id}/check-image-match/
          │
          ▼
backend/api/views.py: CheckImageMatchView
          │
          ├── Fetch Segment from DB: get segment.image_file.path, segment.image_prompt
          │
          ▼
core_engine/clip_scorer.py: compute_image_prompt_similarity()
          │
          ├── Load image: PIL.Image.open(path) → resize 224×224 → normalize
          │
          ├── Tokenize prompt text: CLIP tokenizer → int32 token array
          │
          ├── ONNX session: clip.onnx
          │   ├── image_features = run(image_tensor)
          │   └── text_features  = run(text_tokens)
          │
          ├── cosine_similarity = dot(image_features, text_features) / (||img|| * ||txt||)
          │
          └── return score (0.0 – 1.0)
          │
          ▼
views.py: compute label from score thresholds
          │  ≥ 0.40 → "Good Match"
          │  0.25–0.39 → "Fair Match"
          │  < 0.25 → "Low Match"
          │
          ▼
Return JSON: { score, label, threshold_passed }
          │
          ▼
frontend: MatchBadge renders green / amber / red badge
```

---

## 3. Step-by-Step Instructions

### Step 1 — Prepare the CLIP ONNX model and extend model_loader.py

Place the exported CLIP ONNX model file at `models/clip/clip.onnx` alongside a `clip_tokenizer_vocab.json` and `clip_tokenizer_config.json` in the same folder. These files are obtained from a pre-existing CLIP ONNX export (e.g., exported from HuggingFace `openai/clip-vit-base-patch32`). In `backend/core_engine/model_loader.py`, add a module-level variable `_clip_session = None` initialized to `None`. Add the function `load_clip_model()` that checks if `_clip_session` is already populated; if not, it constructs the absolute path to `models/clip/clip.onnx` using `pathlib.Path`, verifies the file exists, creates an `onnxruntime.InferenceSession` with that path and appropriate session options (disable inter-op parallelism to avoid contending with video rendering workers), assigns it to `_clip_session`, and returns it. If the file does not exist, the function returns `None` without raising — callers must handle the `None` case gracefully to keep the feature optional.

### Step 2 — Build the clip_scorer.py utility module

Create `backend/core_engine/clip_scorer.py`. At the top, define the constants `LOW_MATCH_THRESHOLD = 0.25`, `FAIR_MATCH_THRESHOLD = 0.40`, and `CLIP_IMAGE_SIZE = 224`. Define the function `compute_image_prompt_similarity(image_path: str, prompt_text: str) -> float` as follows: first call `load_clip_model()` and if it returns `None`, return `0.0` (graceful degradation). Next, open the image at `image_path` using `PIL.Image.open`, convert to RGB, resize to `(CLIP_IMAGE_SIZE, CLIP_IMAGE_SIZE)`, and normalize pixel values to the float32 range expected by the model (mean=[0.48145466, 0.4578275, 0.40821073], std=[0.26862954, 0.26130258, 0.27577711]), constructing a NCHW float32 numpy array. Separately, tokenize `prompt_text` using the CLIP tokenizer (loaded from the vocab JSON); produce a 1×77 int32 numpy array padded with zeros and clipped to a max sequence length of 77 tokens. Run the ONNX session's `run()` with the image and text inputs to retrieve the image embedding vector and the text embedding vector. Compute cosine similarity as the dot product divided by the product of L2 norms of both vectors and return the resulting float, clamped to the range `[0.0, 1.0]` to handle any floating-point edge cases.

### Step 3 — Add the API endpoint in views.py and urls.py

In `backend/api/views.py`, create a new class `CheckImageMatchView(APIView)` decorated with `@permission_classes([IsAuthenticated])` if authentication is enforced, otherwise with `AllowAny` for development. The `post(self, request, segment_id)` method fetches the segment by `segment_id` (returning 404 if not found), checks that `segment.image_file` is not empty (returning a 400 response if no image is uploaded), calls `compute_image_prompt_similarity(segment.image_file.path, segment.image_prompt)`, and computes the label by comparing against `LOW_MATCH_THRESHOLD` and `FAIR_MATCH_THRESHOLD`. Additionally, add a `CheckAllImagesView(APIView)` that accepts `project_id`, iterates over all segments of the project where `image_file` is not empty, calls the scorer for each, and returns a list of `{segment_id, sequence_index, score, label, threshold_passed}` objects plus a `summary: {total, passed, failed}` field. In `backend/api/urls.py`, register `path("segments/<int:segment_id>/check-image-match/", CheckImageMatchView.as_view())` and `path("projects/<int:project_id>/check-all-images/", CheckAllImagesView.as_view())`.

### Step 4 — Create the MatchBadge component in the frontend

Create `frontend/components/MatchBadge.tsx` as a pure presentational component. It accepts props: `score: number`, `label: string`, `thresholdPassed: boolean`, and `loading: boolean`. When `loading` is `true`, render a small spinner or "Checking…" text. Otherwise: for "Good Match" render a green badge with a checkmark icon and the text `Good Match — {(score * 100).toFixed(0)}%`; for "Fair Match" render an amber badge with a warning icon and the text `Fair Match — {(score * 100).toFixed(0)}%`; for "Low Match" render a red badge with an exclamation icon, the text `Low Match — {(score * 100).toFixed(0)}%`, and a tooltip: "This image may not visually represent the segment prompt. Consider replacing it or adjusting the prompt." Use TailwindCSS utility classes for color and sizing, following the badge style patterns already used elsewhere in the component library.

### Step 5 — Wire the badge into SegmentCard and add the project-level batch check

In `frontend/components/SegmentCard.tsx`, import `MatchBadge` and add local state variables `matchScore`, `matchLabel`, `matchLoading`, and `matchChecked` (all `null` / `false` by default). After the existing image upload handler successfully saves the image (in the upload callback's success branch), trigger an API call to `POST /api/segments/{segmentId}/check-image-match/`, setting `matchLoading = true` while awaiting the response, then storing the returned `score` and `label` in state and setting `matchLoading = false`. Render `<MatchBadge score={matchScore} label={matchLabel} loading={matchLoading} />` below the segment's image preview, but only when an image is present. In `frontend/app/projects/[id]/page.tsx`, add a "Check All Image Matches" button in the project action toolbar. The button calls `POST /api/projects/{id}/check-all-images/` and on success displays a toast summary notification: "12 segments matched well, 3 flagged as low match" with a link to scroll to the first flagged segment. If the CLIP model file is unavailable (endpoint returns HTTP 503 with `{clip_unavailable: true}`), the button shows a "CLIP model not installed" tooltip explaining where to place the model file.

---

## 4. Expected Outcome

1. After uploading an image to any segment, a color-coded badge (green, amber, or red) appears below the image preview within 1–3 seconds showing the CLIP similarity score and a human-readable label.
2. Creators can identify mismatched images immediately after upload without waiting until the video renders to discover the visual inconsistency.
3. The "Check All Image Matches" button on the project page produces a batch report for the entire project, highlighting all segments that fall below the minimum threshold.
4. The matching feature degrades gracefully — if the CLIP ONNX model file is not present on disk, the badge is simply absent and no errors are surfaced; the render pipeline is unaffected.
5. The CLIP model is loaded once and cached in memory as a session singleton, so repeated scoring calls within the same worker process do not incur repeated disk I/O or model initialization overhead.
6. The similarity thresholds are defined as named constants, making them easy to tune — for example, raising `FAIR_MATCH_THRESHOLD` from 0.40 to 0.45 to enforce a stricter quality standard on a per-deployment basis.
7. The API endpoints are REST-compliant and return well-structured JSON, making them reusable by future automation workflows or bulk quality-checking scripts.

---

## 5. Verification Checklist

### 5.1 Unit Tests

- [ ] `compute_image_prompt_similarity` returns `0.0` when the CLIP model file is not found (None returned from `load_clip_model`)
- [ ] `compute_image_prompt_similarity` returns a float in `[0.0, 1.0]` for a valid image path and a short prompt string
- [ ] Label derivation logic returns "Good Match" for score `0.45`, "Fair Match" for score `0.30`, and "Low Match" for score `0.20`
- [ ] `CheckImageMatchView.post()` returns HTTP 404 when the `segment_id` does not exist in the database
- [ ] `CheckImageMatchView.post()` returns HTTP 400 when the segment has no `image_file` attached

### 5.2 Integration / Manual Tests

- [ ] Upload an image that clearly matches the prompt text (e.g., a photo of the Eiffel Tower with prompt "Eiffel Tower in Paris at night") and confirm the badge shows green "Good Match" with a score above 0.40
- [ ] Upload an image that clearly mismatches the prompt (e.g., a photo of a beach for a prompt about "ancient Roman ruins") and confirm the badge shows red "Low Match"
- [ ] Verify the "Check All Image Matches" button calls the batch endpoint and returns results for all segments with uploaded images, skipping segments that have no image
- [ ] Remove `models/clip/clip.onnx` from disk and confirm the badge is absent in the UI and no 500 errors are thrown — the endpoint returns HTTP 200 with `{clip_unavailable: true}`
- [ ] Confirm that the CLIP ONNX session is only initialized once across two rapid sequential scoring calls to the same endpoint (check that `_clip_session` is not `None` after the first call and `load_clip_model()` does not reload the model)
- [ ] Verify the batch endpoint correctly populates the `summary.failed` count when at least one segment scores below `LOW_MATCH_THRESHOLD`

### 5.3 Regression Tests

- [ ] Existing segment upload flow continues to work without errors when the CLIP model is absent — image saves normally and the only difference is the absence of the badge
- [ ] The render pipeline (`POST /api/projects/{id}/render/`) is not blocked or delayed if CLIP scoring has previously flagged segments as low match
- [ ] The project page loads within its normal time budget even when 30+ segments each have previously computed match scores — confirm no N+1 query is introduced by the batch score endpoint

---

## 6. Notes for AI Agent

- The CLIP ONNX model file and its associated tokenizer files are not included in the repository and must be downloaded separately or generated by exporting `openai/clip-vit-base-patch32` from HuggingFace using `transformers` and `optimum` — document this requirement clearly in the backend `README.md` or a `SETUP.md` file so contributors know to perform this step before the feature is usable
- The CLIP text tokenizer implemented in Python must match the vocabulary used when the ONNX model was exported — mixing tokenizers from different versions of CLIP will produce incorrect embeddings and nonsensical scores, so always use the vocab file packaged alongside the exported model rather than importing a tokenizer from the `transformers` library which may reflect a different version
- Cosine similarity between CLIP embeddings has known distribution characteristics: most unrelated image-text pairs score between 0.15 and 0.28, while genuinely matching pairs score between 0.30 and 0.55 — thresholds below 0.25 and above 0.40 are reasonable starting points, but they may need adjustment after observing real user data
- When implementing the ONNX inference session for CLIP, set `ExecutionProvider` to `CPUExecutionProvider` as the default to avoid dependency on optional CUDA libraries; if a GPU is available, agents can optionally add `CUDAExecutionProvider` as a first-priority provider with a `CPUExecutionProvider` fallback
- The `CheckAllImagesView` endpoint should use a simple Python loop rather than parallelizing CLIP scoring with threads, to avoid overwhelming memory on machines with limited RAM — each CLIP inference is fast enough (< 200 ms per segment on CPU) that sequential processing of 20–30 segments completes in under 10 seconds total
