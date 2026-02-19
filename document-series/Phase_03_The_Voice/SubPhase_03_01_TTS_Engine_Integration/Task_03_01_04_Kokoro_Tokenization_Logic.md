# Task 03.01.04 — Kokoro Tokenization Logic

> **Sub-Phase:** 03.01 — TTS Engine Integration
> **Phase:** Phase 03 — The Voice
> **Complexity:** High
> **Dependencies:** Task 03.01.01 (Model Loader)
> **Parent Document:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md)

---

## Objective

Implement the text-to-token conversion specific to the Kokoro-82M model, including text cleaning, special token insertion, input tensor preparation, and text chunking for long inputs.

---

## Instructions

### Step 1 — Discover model input format

Before writing any tokenization code, load the model and inspect its inputs using `session.get_inputs()`. Print each input's name, shape, and type. This step determines whether tokenization is character-level, phoneme-level, or subword-level, and identifies any special tokens (BOS, EOS, PAD) and their IDs.

### Step 2 — Implement `tokenize_text(text) → numpy array`

Create a function (within `tts_wrapper.py` or as a private helper) that:

1. **Cleans input text:** Strip leading/trailing whitespace, handle special characters, and normalize Unicode.
2. **Converts to tokens:** Map the cleaned text to the model's expected token format based on the discovered input schema.
3. **Adds special tokens:** Insert BOS, EOS, and padding tokens as required by the model's training-time format.
4. **Pads or truncates:** If the model expects fixed-length input, pad with the PAD token or truncate to the maximum length.
5. **Returns a numpy array** with the correct dtype (typically int64 or int32) and shape matching the model's expected input.

### Step 3 — Handle text preprocessing edge cases

- **Numbers:** Convert digits to their word equivalents if the model doesn't handle numeric characters (e.g., "42" → "forty-two").
- **Special characters:** Remove or replace characters the model can't process.
- **Punctuation:** Preserve sentence-ending punctuation (periods, exclamation marks, question marks) as these often affect prosody. Strip or normalize other punctuation based on model requirements.
- **Empty or whitespace-only text:** Return early with an appropriate error before tokenization.

### Step 4 — Implement text chunking for long segments

If the Kokoro model has a maximum input length, implement `split_text_into_chunks(text, max_length) → list of strings`:

1. Split text at sentence boundaries (periods, exclamation marks, question marks followed by whitespace).
2. Accumulate sentences into chunks without exceeding `max_length`.
3. If a single sentence exceeds `max_length`, include it as its own chunk (let the model handle or truncate).
4. Return a list of text chunks.

When chunking is used, `generate_audio()` must: generate audio for each chunk separately, insert a small silence gap (~100ms of zeros) between chunk audio arrays, concatenate all arrays, then normalize the concatenated result as a whole.

### Step 5 — Integrate with `generate_audio()`

Wire the tokenization function into the TTS wrapper pipeline: after input validation and voice ID validation, call `tokenize_text()` to prepare the input tensor before inference.

---

## Expected Output

```
backend/
└── core_engine/
    └── tts_wrapper.py          ← MODIFIED (tokenization logic added)
```

---

## Validation

- [ ] `tokenize_text()` converts text to a numpy array matching the model's expected input format.
- [ ] Special tokens (BOS, EOS, PAD) are correctly inserted.
- [ ] Padding/truncation works for fixed-length models.
- [ ] Special characters and numbers are handled without errors.
- [ ] Text chunking splits at sentence boundaries.
- [ ] Chunk audio arrays are concatenated with silence gaps.
- [ ] Concatenated audio is normalized as a whole (not per-chunk).

---

## Notes

- This is the most model-specific task — it requires hands-on experimentation with the actual `kokoro-v0_19.onnx` file. The implementer MUST inspect the model's metadata.
- If the Kokoro model includes a built-in tokenizer or vocabulary file, use it directly rather than reimplementing.
- The exact tokenization approach (character-level vs. phoneme-level vs. subword) depends on the specific Kokoro version. Reference the Kokoro project's official documentation or source code.
- The silence gap between chunks should use the model's native sample rate (e.g., `np.zeros(int(0.1 * sample_rate))` for 100ms).

---

> **Parent:** [SubPhase_03_01_Overview.md](./SubPhase_03_01_Overview.md) (Layer 2)
> **Phase:** [Phase_03_Overview.md](../Phase_03_Overview.md) (Layer 1)
> **Layer 0:** [00_Project_Overview.md](../../00_Project_Overview.md)
> **Previous Task:** [Task_03_01_03_Implement_TTS_Wrapper.md](./Task_03_01_03_Implement_TTS_Wrapper.md)
> **Next Task:** [Task_03_01_05_Voice_ID_Validation_Fallback.md](./Task_03_01_05_Voice_ID_Validation_Fallback.md)
