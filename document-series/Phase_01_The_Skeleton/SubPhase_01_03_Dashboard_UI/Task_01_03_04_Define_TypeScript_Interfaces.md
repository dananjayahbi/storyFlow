# Task 01.03.04 — Define TypeScript Interfaces

## Metadata

| Field                    | Value                                                                   |
| ------------------------ | ----------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.03 — Dashboard UI & Basic API                               |
| **Phase**                | Phase 01 — The Skeleton                                                 |
| **Document Type**        | Layer 3 — Task Document                                                 |
| **Estimated Complexity** | Low                                                                     |
| **Dependencies**         | None                                                                    |
| **Parent Document**      | [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2, §5.4)|

---

## Objective

Create TypeScript interface definitions that match the Django serializer output shapes, providing type safety across all frontend API interactions.

---

## Instructions

### Step 1: Create `lib/types.ts`

Create `frontend/lib/types.ts`:

```typescript
export interface Project {
  id: string;
  title: string;
  created_at: string;
  updated_at: string;
  status: 'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED';
  resolution_width: number;
  resolution_height: number;
  framerate: number;
  segment_count: number;
}

export interface Segment {
  id: string;
  project: string;
  sequence_index: number;
  text_content: string;
  image_prompt: string;
  image_file: string | null;
  audio_file: string | null;
  audio_duration: number | null;
  is_locked: boolean;
}

export interface GlobalSettings {
  default_voice_id: string;
  tts_speed: number;
  zoom_intensity: number;
  subtitle_font: string;
  subtitle_color: string;
}

export interface ProjectDetail extends Omit<Project, 'segment_count'> {
  output_path: string | null;
  segments: Segment[];
}

export interface CreateProjectPayload {
  title: string;
}

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}
```

---

## Expected Output

```
frontend/lib/
├── types.ts     ← NEW
├── api.ts       ← Created in Task 01.03.03
└── utils.ts     ← Existing (from Shadcn/UI init)
```

---

## Validation

- [ ] `frontend/lib/types.ts` exists.
- [ ] `Project` interface has 9 fields matching `ProjectSerializer` output.
- [ ] `Project.status` is a union type: `'DRAFT' | 'PROCESSING' | 'COMPLETED' | 'FAILED'`.
- [ ] `Segment` interface has 9 fields matching `SegmentSerializer` output.
- [ ] `Segment.image_file`, `audio_file` are `string | null`.
- [ ] `Segment.audio_duration` is `number | null`.
- [ ] `GlobalSettings` interface has 5 fields matching `GlobalSettingsSerializer` output.
- [ ] `ProjectDetail` extends `Omit<Project, 'segment_count'>` and adds `output_path` and `segments`.
- [ ] `CreateProjectPayload` has only `title: string`.
- [ ] `PaginatedResponse<T>` is generic with `count`, `next`, `previous`, `results`.
- [ ] All interfaces are exported.

---

## Notes

- **`ProjectDetail` uses `Omit`** — it is NOT a superset of `Project`. The detail serializer excludes `segment_count` and includes `segments` array and `output_path` instead.
- **`PaginatedResponse<T>`** matches DRF's `PageNumberPagination` output format. The frontend must access `response.results` to get the data array.
- **`Segment.project` is `string`** (UUID) — not a nested object. When serialized, the ForeignKey renders as the related Project's UUID.
- These interfaces will be extended in Phase 02 with additional types (import payloads, mutation types, etc.).
- `npx tsc --noEmit` should pass with zero errors after this file is created.

---

> **Parent:** [SubPhase_01_03_Overview.md](SubPhase_01_03_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_03_03_Setup_Frontend_API_Client.md](Task_01_03_03_Setup_Frontend_API_Client.md)
> **Next Task:** [Task_01_03_05_Build_Root_Layout.md](Task_01_03_05_Build_Root_Layout.md)
