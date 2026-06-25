# StoryFlow Ideas — Document 2: Audio, TTS & Music

> **Category:** Text-to-Speech, Background Music, Sound Effects, Audio Processing  
> **Last Updated:** March 1, 2026  
> **Purpose:** Ideas for making the audio pipeline richer, more versatile, and social-media-ready

---

## Table of Contents

- [1. TTS Engine Improvements](#1-tts-engine-improvements)
- [2. Background Music System](#2-background-music-system)
- [3. Sound Effects & Audio Layers](#3-sound-effects--audio-layers)
- [4. Audio Processing & Quality](#4-audio-processing--quality)
- [5. Voice & Narration Flexibility](#5-voice--narration-flexibility)
- [6. Subtitle & Audio Sync](#6-subtitle--audio-sync)

---

## 1. TTS Engine Improvements

### 1.1 Multi-Language TTS Support
- **Current:** Hardcoded to `en-us` only.
- **Idea:** Add language parameter support. Kokoro supports multiple languages — expose language selection per project.
- **Languages to prioritize:** Spanish, French, German, Portuguese, Japanese, Korean, Hindi.
- **Impact:** Massive audience expansion — non-English content markets are huge on YouTube/TikTok.
- **Complexity:** Medium — Kokoro may support phoneme sets for other languages; also explore alternative models.

### 1.2 SSML-Like Markup Support
- **Current:** Plain text only — no pauses, emphasis, or pronunciation control.
- **Idea:** Support lightweight markup in narration text:
  - `[pause 0.5s]` — insert a half-second pause
  - `*emphasis*` — stressed pronunciation
  - `{word: pronunciation}` — custom phoneme override
  - `[speed 0.8]...[/speed]` — local speed adjustment
- **Impact:** Much more expressive narration — dramatic pauses, emphasis on key words.
- **Complexity:** Medium — need a text preprocessor that strips markup before TTS and inserts silence/adjustments.

### 1.3 Per-Segment Voice Selection
- **Current:** Single voice per project.
- **Idea:** Allow different voices per segment (e.g., narrator vs. character, or male vs. female for dialogue scenes).
- **Impact:** Enables dialogue-style narration and character voices.
- **Complexity:** Low — add `voice_id` field to Segment model, use in TTS wrapper.

### 1.4 Per-Segment Speed Override
- **Current:** Single speed per project.
- **Idea:** Allow speed override per segment (fast for exciting scenes, slow for dramatic moments).
- **Impact:** Better pacing and emotional control.
- **Complexity:** Low — add `tts_speed` field to Segment model.

### 1.5 Streaming / Chunked TTS for Long Segments
- **Current:** Entire text synthesized at once before writing.
- **Idea:** Split long segments at sentence boundaries, generate each chunk, and concatenate WAV files.
- **Impact:** Lower peak memory usage for very long narration segments.
- **Complexity:** Low — `split_text_into_chunks()` already exists but is unused.

### 1.6 Alternative TTS Engine Support
- **Current:** Kokoro-82M ONNX only.
- **Idea:** Add support for pluggable TTS engines:
  - **Piper TTS** — fast, lightweight, many languages
  - **Coqui TTS** — open source, high quality
  - **ElevenLabs** (optional cloud) — ultra-realistic voices
  - **Bark** — can generate laughter, singing, sound effects in speech
  - **Edge TTS** — Microsoft's free TTS API (no local model needed)
- **Impact:** Voice variety, quality tiers, offline + online options.
- **Complexity:** Medium — need a TTS engine abstraction layer / plugin system.

### 1.7 Voice Cloning / Custom Voice Training
- **Current:** Fixed set of pre-trained voices.
- **Idea:** Allow uploading a voice sample (30–60s WAV) and fine-tuning the TTS model to clone that voice.
- **Impact:** Unique brand voice for each creator. Huge differentiator.
- **Complexity:** High — requires fine-tuning pipeline (Coqui or Tortoise TTS can do this).

### 1.8 TTS Audio Preview in Editor
- **Current:** Must generate full audio to hear how a segment sounds.
- **Idea:** Quick preview — generate TTS for a selected text snippet (first sentence only) for instant preview.
- **Impact:** Faster iteration on text wording and voice selection.
- **Complexity:** Low — just limit TTS input to first sentence.

---

## 2. Background Music System

### 2.1 Background Music Track Support
- **Current:** No background music — TTS narration only.
- **Idea:** Add a background music layer to the project:
  - Upload an MP3/WAV music file
  - Select from a built-in library (royalty-free tracks)
  - Set music volume level (e.g., 20% during narration)
  - Music plays throughout the entire video
- **Impact:** CRITICAL for social media — every viral video has background music. TTS-only narration sounds flat and sterile.
- **Complexity:** Medium — FFmpeg audio mixing during render, UI for music selection and volume.

### 2.2 Auto-Ducking (Smart Volume)
- **Current:** N/A (no music layer).
- **Idea:** When narration audio is playing, automatically reduce music volume (duck). During silence gaps between segments, bring music volume back up.
- **Impact:** Professional audio mix — narration is always clear, music fills the gaps.
- **Complexity:** Medium — detect narration silence regions, apply volume envelope to music track.

### 2.3 Built-In Royalty-Free Music Library
- **Current:** No music at all.
- **Idea:** Bundle 20–50 royalty-free music tracks categorized by mood:
  - **Dramatic** — cinematic, intense
  - **Happy/Upbeat** — fun, energetic
  - **Calm/Ambient** — relaxing, meditative
  - **Motivational** — inspiring, uplifting
  - **Suspenseful** — mystery, thriller
  - **Sad/Emotional** — touching, heartfelt
  - **Educational** — neutral, informative
- **Impact:** Instant professional audio without sourcing music externally.
- **Complexity:** Low (technical), Medium (licensing — need truly free-use tracks).

### 2.4 Music Fade-In / Fade-Out
- **Current:** N/A.
- **Idea:** Auto fade-in music at video start (2s) and fade-out at end (3s). Configurable durations.
- **Impact:** Polished audio transitions.
- **Complexity:** Low — FFmpeg `afade` filter.

### 2.5 Per-Segment Music Override
- **Current:** N/A.
- **Idea:** Allow changing the background music track at specific segment boundaries (e.g., mood shift mid-video).
- **Impact:** Complex video compositions with emotional arcs.
- **Complexity:** Medium — need crossfade between music tracks at segment boundaries.

### 2.6 Music Tempo Matching
- **Current:** N/A.
- **Idea:** Analyze the music BPM and suggest segment transitions that align with beat drops.
- **Impact:** Videos that "feel" perfectly timed with the music (like TikTok trend videos).
- **Complexity:** High — need beat detection (librosa) and timing suggestion system.

---

## 3. Sound Effects & Audio Layers

### 3.1 Sound Effect Library
- **Current:** No SFX support.
- **Idea:** Add optional sound effects per segment:
  - Whoosh (transitions)
  - Ding/notification (highlights)
  - Ambient sounds (rain, city, forest)
  - Drama stingers (reveal, plot twist)
  - Pop/click (text appearance)
- **Impact:** Adds professional polish that keeps viewers engaged.
- **Complexity:** Medium — need audio layering in the render pipeline.

### 3.2 Transition Sound Effects
- **Current:** Visual transitions only (crossfade).
- **Idea:** Pair visual transitions with audio SFX automatically (whoosh on slide, soft tone on dissolve).
- **Impact:** Multi-sensory transitions feel more professional.
- **Complexity:** Low (once SFX library exists) — map transition type to SFX.

### 3.3 Segment-Level Audio Overlay
- **Current:** Only TTS audio per segment.
- **Idea:** Allow uploading an additional audio clip per segment (ambient sound, SFX, or alternative narration) that plays alongside the TTS.
- **Impact:** Rich audio landscapes for immersive content.
- **Complexity:** Medium — audio mixing per segment in render pipeline.

### 3.4 Silent Segment Support
- **Current:** Empty segments have no audio.
- **Idea:** Explicitly support "pause" or "visual-only" segments that show an image for a configurable duration with only background music (no narration).
- **Impact:** Breathing room in videos — let the visuals speak.
- **Complexity:** Low — treat segments with empty text_content as visual-only with configurable display duration.

---

## 4. Audio Processing & Quality

### 4.1 LUFS Loudness Normalization
- **Current:** Peak normalization only.
- **Idea:** Implement LUFS normalization per platform standard:
  - YouTube: -14 LUFS
  - TikTok/Instagram: -14 LUFS
  - Facebook: -16 LUFS
  - Podcast: -16 LUFS
- **Impact:** Videos sound consistent volume-wise — no jarring volume differences. Platform algorithms favor properly normalized audio.
- **Complexity:** Medium — need `pyloudnorm` library or FFmpeg `loudnorm` filter.

### 4.2 Audio Compression / Limiting
- **Current:** No dynamic range compression.
- **Idea:** Apply light compression to TTS output to ensure consistent volume throughout narration.
- **Impact:** Smoother listening experience, especially at lower volumes.
- **Complexity:** Low — FFmpeg `acompressor` filter.

### 4.3 De-Essing
- **Current:** No post-processing of TTS audio.
- **Idea:** Apply ​de-essing filter to reduce sibilance ('s' sounds that are too sharp).
- **Impact:** More pleasant narration audio quality.
- **Complexity:** Low — FFmpeg EQ filter or bandpass reduction.

### 4.4 Room Reverb / Ambience
- **Current:** Dry TTS output only.
- **Idea:** Optional light reverb or room ambience to make TTS sound more natural (like recording in a real room).
- **Impact:** Less "robotic" sounding narration.
- **Complexity:** Low — FFmpeg `aecho` or `reverb` filter.

### 4.5 Noise Floor Addition
- **Current:** Dead silence between narration words.
- **Idea:** Add a very subtle noise floor (pink noise at -60dB) to prevent the uncomfortable "digital silence" feel.
- **Impact:** More natural-sounding audio.
- **Complexity:** Low.

### 4.6 Output Audio Resampling Fix
- **Current:** Kokoro outputs 24kHz, MoviePy exports at 44.1kHz — implicit resampling.
- **Idea:** Explicitly resample to 44.1kHz with high-quality algorithm (SoX resampling) before mixing.
- **Impact:** Cleaner audio without interpolation artifacts.
- **Complexity:** Low — `soundfile` or `librosa` resampling.

---

## 5. Voice & Narration Flexibility

### 5.1 Voiceover Upload (Custom Narration)
- **Current:** TTS-only — no option for human-recorded narration.
- **Idea:** Allow uploading a pre-recorded WAV/MP3 per segment as an alternative to TTS.
- **Impact:** Creators with good voices can record themselves. Professional voiceover artists can be used.
- **Complexity:** Low — segment already has `audio_file` field, just need upload UI alongside the TTS generate button.

### 5.2 Voice A/B Testing
- **Current:** Must regenerate audio to compare voices.
- **Idea:** Quick-generate the same text with 2–3 different voices and let the user compare side-by-side.
- **Impact:** Faster voice selection for optimal video feel.
- **Complexity:** Low — generate to temp files, play both, user picks.

### 5.3 Narration Pacing Analysis
- **Current:** No feedback on narration speed/pacing.
- **Idea:** After generating audio, show estimated words-per-minute and compare against ideal ranges:
  - Calm/educational: 130–150 WPM
  - Normal: 150–170 WPM
  - Energetic/fast: 170–200 WPM
- **Impact:** Helps creators optimize pacing for their content type.
- **Complexity:** Low — simple math from word count and audio duration.

### 5.4 Pronunciation Dictionary
- **Current:** No custom pronunciation overrides.
- **Idea:** A project-level or global pronunciation dictionary: `{"NVIDIA": "en-VID-ee-uh", "GIF": "JIF"}`.
- **Impact:** Correct pronunciation of brand names, technical terms, proper nouns.
- **Complexity:** Medium — text preprocessing before TTS.

---

## 6. Subtitle & Audio Sync

### 6.1 Forced Alignment (Word-Level Timing)
- **Current:** Subtitle timing is character-count-proportional — drift is noticeable on long segments.
- **Idea:** Use Whisper or wav2vec2 to do forced alignment: match each word to its exact timestamp in the generated audio.
- **Impact:** Perfectly synced subtitles — professional quality. Essential for social media videos.
- **Complexity:** Medium — need Whisper model, post-TTS alignment pass.

### 6.2 Word-by-Word Highlighting (Karaoke Style)
- **Current:** Full subtitle chunk displayed at once.
- **Idea:** With word-level timing, highlight each word as it's spoken (like karaoke or TikTok auto-captions).
- **Impact:** Massively engaging — this is the standard for viral TikTok/YouTube Shorts videos.
- **Complexity:** Medium — need per-word timing data, per-frame subtitle rendering with highlight state.

### 6.3 SRT/VTT Subtitle Export
- **Current:** Subtitles are burned into the video only.
- **Idea:** Export standalone SRT or VTT files alongside the video.
- **Impact:** Useful for YouTube (closed captions), accessibility compliance, repurposing content.
- **Complexity:** Low — write timing data to SRT format.

### 6.4 Subtitle Auto-Translation
- **Current:** Subtitles always match narration language.
- **Idea:** Auto-translate subtitles to other languages (viewer in France sees French subtitles while hearing English narration).
- **Impact:** Reach global audiences without re-recording narration.
- **Complexity:** Medium — need translation API/model, dual subtitle rendering.

---

## Priority Matrix

| Idea | Impact | Effort | Recommended Priority |
|------|--------|--------|---------------------|
| 2.1 Background Music Track | CRITICAL | MEDIUM | 🔴 Do First |
| 2.2 Auto-Ducking | HIGH | MEDIUM | 🔴 Do First |
| 4.1 LUFS Normalization | HIGH | LOW | 🔴 Do First |
| 6.1 Forced Alignment | HIGH | MEDIUM | 🔴 Do First |
| 5.1 Voiceover Upload | HIGH | LOW | 🔴 Do First |
| 1.3 Per-Segment Voice | MEDIUM | LOW | 🟡 Do Soon |
| 1.4 Per-Segment Speed | MEDIUM | LOW | 🟡 Do Soon |
| 2.3 Royalty-Free Library | HIGH | MEDIUM | 🟡 Do Soon |
| 2.4 Music Fade-In/Out | MEDIUM | LOW | 🟡 Do Soon |
| 3.4 Silent Segment Support | MEDIUM | LOW | 🟡 Do Soon |
| 6.3 SRT/VTT Export | MEDIUM | LOW | 🟡 Do Soon |
| 1.1 Multi-Language TTS | HIGH | MEDIUM | 🟠 Plan Ahead |
| 1.2 SSML Markup | MEDIUM | MEDIUM | 🟠 Plan Ahead |
| 1.6 Alternative TTS Engines | HIGH | MEDIUM | 🟠 Plan Ahead |
| 6.2 Karaoke Word Highlights | HIGH | MEDIUM | 🟠 Plan Ahead |
| 3.1 Sound Effect Library | MEDIUM | MEDIUM | 🟠 Plan Ahead |
| 1.7 Voice Cloning | HIGH | HIGH | 🔵 Future |
| 2.6 Music Tempo Matching | MEDIUM | HIGH | 🔵 Future |
| 6.4 Subtitle Auto-Translation | MEDIUM | MEDIUM | 🔵 Future |
