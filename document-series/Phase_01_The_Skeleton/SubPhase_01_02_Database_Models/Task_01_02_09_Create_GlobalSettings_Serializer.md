# Task 01.02.09 — Create GlobalSettingsSerializer

## Metadata

| Field                    | Value                                                                                                     |
| ------------------------ | --------------------------------------------------------------------------------------------------------- |
| **Sub-Phase**            | SubPhase 01.02 — Database Models & Migrations                                                             |
| **Phase**                | Phase 01 — The Skeleton                                                                                   |
| **Document Type**        | Layer 3 — Task Document                                                                                   |
| **Estimated Complexity** | Low                                                                                                       |
| **Dependencies**         | [Task_01_02_03](Task_01_02_03_Create_GlobalSettings_Model.md), [Task_01_02_06](Task_01_02_06_Configure_DRF_Settings.md) |
| **Parent Document**      | [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2, §5.9)                                  |

---

## Objective

Add the `GlobalSettingsSerializer` to `backend/api/serializers.py` for serializing all GlobalSettings model fields.

---

## Instructions

### Step 1: Add GlobalSettingsSerializer

Open `backend/api/serializers.py` and add the `GlobalSettings` import and serializer class:

```python
from .models import Project, Segment, GlobalSettings


class GlobalSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GlobalSettings
        fields = [
            'default_voice_id', 'tts_speed', 'zoom_intensity',
            'subtitle_font', 'subtitle_color',
        ]
```

> Update the existing import line to include `GlobalSettings`. Place the class after `SegmentSerializer`.

---

## Expected Output

```
backend/api/serializers.py
├── from rest_framework import serializers
├── from .models import Project, Segment, GlobalSettings
├── class ProjectSerializer(...)           ← Task 01.02.07
├── class SegmentSerializer(...)           ← Task 01.02.08
└── class GlobalSettingsSerializer(...)    ← NEW
```

---

## Validation

- [ ] `GlobalSettings` is imported from `.models`.
- [ ] `GlobalSettingsSerializer` extends `serializers.ModelSerializer`.
- [ ] `fields` includes exactly 5 items: `default_voice_id`, `tts_speed`, `zoom_intensity`, `subtitle_font`, `subtitle_color`.
- [ ] No `read_only_fields` — all settings are editable via the API.

---

## Notes

- The `id` field is intentionally **excluded** from the serializer. Since `GlobalSettings` is a singleton (always `pk=1`), the ID is not meaningful to API consumers.
- All 5 fields are writable — the user can update voice, TTS speed, zoom intensity, subtitle font, and subtitle color through the settings panel (built in Phase 05).
- The API endpoint for this serializer (`GET/PUT /api/settings/`) will be created in SubPhase 01.03.

---

> **Parent:** [SubPhase_01_02_Overview.md](SubPhase_01_02_Overview.md) (Layer 2)
> **Previous Task:** [Task_01_02_08_Create_Segment_Serializer.md](Task_01_02_08_Create_Segment_Serializer.md)
> **Next Task:** [Task_01_02_10_Create_ProjectDetail_Serializer.md](Task_01_02_10_Create_ProjectDetail_Serializer.md)
