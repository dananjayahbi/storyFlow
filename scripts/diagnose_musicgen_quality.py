"""Diagnose MusicGen output quality (noise vs music) across dtypes."""
from __future__ import annotations

import argparse
import os
import sys
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

import numpy as np
import soundfile as sf
import torch
from transformers import AutoProcessor, MusicgenForConditionalGeneration

MODEL_DIR = os.path.join(PROJECT_ROOT, "models", "musicgen-small")
PROMPT = (
    "70 bpm, D minor, warm solo piano, soft strings, gentle cinematic "
    "documentary score, instrumental, no vocals"
)


def metrics(audio: np.ndarray, sr: int) -> dict:
    audio = np.asarray(audio, dtype=np.float64).reshape(-1)
    peak = float(np.max(np.abs(audio)))
    rms = float(np.sqrt(np.mean(audio ** 2)))
    # Spectral flatness (0 = tonal, 1 = white noise).
    frame = 4096
    count = len(audio) // frame
    flats = []
    for i in range(min(count, 40)):
        chunk = audio[i * frame:(i + 1) * frame]
        if not np.any(chunk):
            continue
        spec = np.abs(np.fft.rfft(chunk * np.hanning(frame))) ** 2 + 1e-12
        flats.append(float(np.exp(np.mean(np.log(spec))) / np.mean(spec)))
    flatness = float(np.mean(flats)) if flats else float("nan")
    # Zero crossing rate: noise is much higher than tonal music.
    zcr = float(np.mean(np.abs(np.diff(np.signbit(audio)))))
    return {
        "samples": len(audio),
        "seconds": round(len(audio) / sr, 3),
        "peak": round(peak, 4),
        "rms": round(rms, 4),
        "spectral_flatness": round(flatness, 5),
        "zero_crossing_rate": round(zcr, 5),
    }


def run(dtype_name: str, seconds: float, out_path: str) -> dict:
    dtype = torch.float16 if dtype_name == "fp16" else torch.float32
    started = time.time()
    model = MusicgenForConditionalGeneration.from_pretrained(
        MODEL_DIR, dtype=dtype, low_cpu_mem_usage=True
    ).to("cuda")
    model.eval()
    processor = AutoProcessor.from_pretrained(MODEL_DIR)
    inputs = processor(text=[PROMPT], padding=True, return_tensors="pt").to("cuda")
    with torch.inference_mode():
        audio = model.generate(
            **inputs,
            do_sample=True,
            guidance_scale=3.0,
            max_new_tokens=int(seconds * 50) + 3,
        )
    waveform = audio[0, 0].detach().float().cpu().numpy()
    sr = int(model.config.audio_encoder.sampling_rate)
    sf.write(out_path, np.clip(waveform, -1.0, 1.0), sr, subtype="PCM_16")
    info = metrics(waveform, sr)
    info.update({
        "dtype": dtype_name,
        "load_seconds": round(time.time() - started, 2),
        "vram_alloc_gb": round(torch.cuda.memory_allocated(0) / 1e9, 2),
        "out": out_path,
    })
    print(info, flush=True)
    del model, processor
    torch.cuda.empty_cache()
    return info


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seconds", type=float, default=4.0)
    parser.add_argument("--dtypes", default="fp16,fp32")
    args = parser.parse_args()
    for name in args.dtypes.split(","):
        out = os.path.join(PROJECT_ROOT, "models", f"diag-{name}.wav")
        run(name.strip(), args.seconds, out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
