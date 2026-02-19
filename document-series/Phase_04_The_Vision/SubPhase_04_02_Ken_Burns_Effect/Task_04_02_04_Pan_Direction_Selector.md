# Task 04.02.04 — Pan Direction Selector

## Metadata

| Field         | Value                                                                |
| ------------- | -------------------------------------------------------------------- |
| **Task ID**   | 04.02.04                                                             |
| **Task Name** | Pan Direction Selector                                               |
| **Sub-Phase** | 04.02 — Ken Burns Effect Implementation                              |
| **Phase**     | Phase 04 — The Vision: Video Rendering Engine                        |
| **Complexity**| Medium                                                               |
| **Dependencies** | Task 04.02.01 (DIRECTIONS constant and ken_burns.py module must exist) |
| **Parent**    | [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md)           |

---

## Objective

Implement the get_pan_direction function within the ken_burns.py module. This function selects the camera pan direction for a given segment by cycling through the predefined DIRECTIONS constant using the segment's index modulo the number of available directions. The selection mechanism is deterministic, ensuring that re-rendering the same project always produces identical camera motion patterns, while still providing visual variety across consecutive segments.

---

## Instructions

### Step 1 — Define the Function Signature

Create a function named get_pan_direction within backend/core_engine/ken_burns.py. The function accepts one parameter:

- segment_index (int): the zero-based sequence index of the current segment within the project. This value comes from the Segment model's sequence_index field.

The function returns a tuple of two strings: (start_position_name, end_position_name), where each name is one of the five recognized position identifiers: center, top_left, top_right, bottom_left, or bottom_right.

Add a docstring explaining the cycling mechanism and the deterministic nature of the selection.

### Step 2 — Implement the Cycling Logic

The implementation uses the modulo operator to cycle through the DIRECTIONS constant. The index into the DIRECTIONS tuple is computed as segment_index modulo the length of DIRECTIONS (which is 7). This produces a repeating sequence: for segment indices 0 through 6, the directions are selected sequentially; for indices 7 through 13, the same sequence repeats; and so on indefinitely.

The function returns the tuple at the computed index position from the DIRECTIONS constant. No additional transformation or validation of the direction values is needed since the DIRECTIONS constant is defined within the same module and is guaranteed to contain valid position name pairs.

### Step 3 — Verify Determinism

The function must be purely deterministic: the same segment_index input must always produce the same direction output. There must be no use of random.choice, random.randint, or any other source of randomness. This is a deliberate architectural decision to ensure reproducible video rendering, even though the Phase 04 Overview document mentions "randomly select" in its high-level description. The detailed design overrides that with deterministic cycling.

### Step 4 — Handle Edge Cases

While segment_index should always be a non-negative integer in practice (coming from database records with sequential indices), the modulo operation naturally handles negative values and large values correctly in Python. Negative indices would cycle backward through the DIRECTIONS tuple, and very large indices would wrap around as expected. No special edge-case handling is required.

---

## Expected Output

The function get_pan_direction is defined in backend/core_engine/ken_burns.py. Given the DIRECTIONS constant defined in Task 04.02.01:

- get_pan_direction(0) returns ("center", "center").
- get_pan_direction(1) returns ("top_left", "bottom_right").
- get_pan_direction(2) returns ("bottom_right", "top_left").
- get_pan_direction(3) returns ("top_right", "bottom_left").
- get_pan_direction(4) returns ("bottom_left", "top_right").
- get_pan_direction(5) returns ("center", "top_left").
- get_pan_direction(6) returns ("center", "bottom_right").
- get_pan_direction(7) returns ("center", "center") — cycle repeats.
- get_pan_direction(14) returns ("center", "center") — second cycle repeat.

Calling the function twice with the same index always returns the same result.

---

## Validation

- [ ] The function get_pan_direction exists in ken_burns.py.
- [ ] It accepts segment_index as its parameter.
- [ ] It returns a tuple of two strings representing start and end position names.
- [ ] The cycling follows segment_index modulo 7.
- [ ] Consecutive segment indices (0, 1, 2, ..., 6) each produce a different direction.
- [ ] The cycle repeats starting at index 7.
- [ ] The function is deterministic — same input always produces same output.
- [ ] No randomness (random module, secrets, etc.) is used.
- [ ] The function has a docstring and type hints.

---

## Notes

- The seven-direction set provides a good balance of visual variety without requiring complex configuration. The center-to-center direction (segment 0, 7, 14, ...) produces a static zoomed-in shot, which acts as a visual "breathing" moment between the more dynamic pan shots. This is an intentional creative choice.
- Future enhancements could allow per-segment direction configuration via the Segment model or a user interface, but this is explicitly out of scope for Phase 04. The current automatic cycling provides sufficient variety for the MVP.
- The modulo operator in Python handles negative integers correctly (for example, -1 % 7 equals 6), so even if a segment index were somehow negative, the function would not crash. However, segment indices in StoryFlow are always non-negative by database constraint.

---

> **Parent:** [SubPhase_04_02_Overview.md](./SubPhase_04_02_Overview.md) (Layer 2)
> **Phase:** [Phase_04_Overview.md](../Phase_04_Overview.md) (Layer 1)
> **Master:** [00_Project_Overview.md](../../00_Project_Overview.md) (Layer 0)
