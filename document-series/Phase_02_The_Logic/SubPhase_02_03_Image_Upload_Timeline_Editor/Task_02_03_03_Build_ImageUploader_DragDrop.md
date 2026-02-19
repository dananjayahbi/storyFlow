# Task 02.03.03 — Build ImageUploader Drag-and-Drop

> **Sub-Phase:** 02.03 — Image Upload & Timeline Editor UI
> **Phase:** Phase 02 — The Logic
> **Complexity:** High
> **Dependencies:** None
> **Parent Document:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md)

---

## Objective

Create a drag-and-drop image upload zone using native HTML5 drag events with click-to-browse fallback, client-side validation, upload progress, and image preview with removal.

---

## Instructions

### Step 1 — Create the component file

Create `frontend/components/ImageUploader.tsx`.

### Step 2 — Define props interface

```typescript
interface ImageUploaderProps {
  segmentId: number;
  currentImage: string | null;  // Relative path or null
  isLocked: boolean;
  onUpload: (segmentId: number, file: File) => Promise<void>;
  onRemove: (segmentId: number) => Promise<void>;
}
```

### Step 3 — Implement two visual states

**State A (No Image):** Dashed-border drop zone with upload icon and "Drop image here or click to browse" text.

**State B (Image Uploaded):** Image thumbnail preview with a "Remove" button visible on hover.

### Step 4 — Implement drag-and-drop with counter pattern

Use a `dragCounterRef` to track drag enter/leave across child elements:

```typescript
const dragCounterRef = useRef(0);
const [isDragging, setIsDragging] = useState(false);

const onDragEnter = (e: React.DragEvent) => {
  e.preventDefault();
  dragCounterRef.current++;
  setIsDragging(true);
};

const onDragOver = (e: React.DragEvent) => {
  e.preventDefault(); // REQUIRED — without this, onDrop won't fire
};

const onDragLeave = (e: React.DragEvent) => {
  dragCounterRef.current--;
  if (dragCounterRef.current === 0) setIsDragging(false);
};

const onDrop = (e: React.DragEvent) => {
  e.preventDefault();
  dragCounterRef.current = 0;
  setIsDragging(false);
  const file = e.dataTransfer.files[0];
  if (file) handleFile(file);
};
```

### Step 5 — Implement click-to-browse

```typescript
const fileInputRef = useRef<HTMLInputElement>(null);

// Hidden input
<input
  ref={fileInputRef}
  type="file"
  accept="image/jpeg,image/png,image/webp"
  className="hidden"
  onChange={(e) => {
    const file = e.target.files?.[0];
    if (file) handleFile(file);
  }}
/>

// Drop zone click handler
const handleZoneClick = () => fileInputRef.current?.click();
```

### Step 6 — Implement client-side validation

```typescript
const ALLOWED_TYPES = ['image/jpeg', 'image/png', 'image/webp'];
const MAX_SIZE = 20 * 1024 * 1024; // 20MB

const handleFile = async (file: File) => {
  if (!ALLOWED_TYPES.includes(file.type)) {
    setError('Only JPEG, PNG, and WebP images are allowed.');
    return;
  }
  if (file.size > MAX_SIZE) {
    setError('Image must be under 20MB.');
    return;
  }
  setError(null);
  setIsUploading(true);
  try {
    await onUpload(segmentId, file);
  } finally {
    setIsUploading(false);
  }
};
```

### Step 7 — Construct image URL for preview

```typescript
const imageUrl = currentImage
  ? `${process.env.NEXT_PUBLIC_API_BASE_URL || 'http://localhost:8000'}${currentImage}`
  : null;
```

### Step 8 — Add keyboard accessibility

- Drop zone: `tabIndex={0}`, `role="button"`, trigger file picker on `Enter`/`Space`.
- "Remove" button: Standard `<button>`, keyboard accessible by default.

### Step 9 — Disable entirely when locked

When `isLocked` is `true`, disable the drop zone click, drag events, and remove button.

---

## Expected Output

```
frontend/
└── components/
    └── ImageUploader.tsx       ← NEW
```

---

## Validation

- [ ] Drop zone renders when no image is set.
- [ ] Image preview renders when `currentImage` is provided.
- [ ] Drag-and-drop triggers upload callback with the file.
- [ ] Click-to-browse opens file picker and triggers upload.
- [ ] Non-image files are rejected with inline error message.
- [ ] Files over 20MB are rejected with inline error message.
- [ ] "Uploading..." indicator shows during API call.
- [ ] "Remove" button calls `onRemove` callback.
- [ ] `e.preventDefault()` on `onDragOver` — drop zone works correctly.
- [ ] Entire component disabled when `isLocked` is `true`.
- [ ] Keyboard accessible (`tabIndex`, `role`, Enter/Space triggers).

---

## Notes

- **No external drag-and-drop library** — native HTML5 drag events are sufficient.
- `e.preventDefault()` on `onDragOver` is **required** — without it, the browser navigates to the dropped file instead of triggering `onDrop`.
- Use the counter pattern for `onDragEnter`/`onDragLeave` because these events fire on every child element, causing flickering otherwise.
- Do NOT manually set `Content-Type` header when uploading via Axios — Axios auto-sets it with the correct multipart boundary.

---

> **Parent:** [SubPhase_02_03_Overview.md](./SubPhase_02_03_Overview.md) (Layer 2)
> **Phase:** [Phase_02_Overview.md](../Phase_02_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_02_03_02_Build_SegmentTextEditor.md](./Task_02_03_02_Build_SegmentTextEditor.md)
> **Next Task:** [Task_02_03_04_Build_ImagePromptDisplay.md](./Task_02_03_04_Build_ImagePromptDisplay.md)
