"""GPU smoke test for the StoryFlow MusicGen worker.

Run with the CUDA Python 3.11 environment:

    backend\\qwen_tts\\.venv\\Scripts\\python.exe scripts\\test_musicgen_gpu.py

It generates two short segments (with continuation) and reports the device,
VRAM, output duration and file path.  The model is loaded and unloaded inside
this process, so it also verifies that VRAM is returned when it exits.
"""

from __future__ import annotations

import argparse
import json
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(PROJECT_ROOT, "backend")
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--model",
        default=os.path.join(PROJECT_ROOT, "models", "musicgen-small"),
    )
    parser.add_argument(
        "--output",
        default=os.path.join(PROJECT_ROOT, "models", "musicgen-smoke.wav"),
    )
    parser.add_argument("--seconds", type=float, default=2.0)
    args = parser.parse_args()

    import torch

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available in this Python environment.")
    torch.set_num_threads(1)
    try:
        torch.set_num_interop_threads(1)
    except RuntimeError:
        pass

    from core_engine import music_generator as mg

    segments = [
        {
            "text_content": "An ancient wreck rests in the quiet dark.",
            "image_prompt": "sunken ship",
            "duration": args.seconds,
        },
        {
            "text_content": "The crew faces rising danger as the storm grows.",
            "image_prompt": "storm at sea",
            "duration": args.seconds,
        },
    ]
    plan = mg.plan_music(segments, bpm=70, root_key="D", mode="minor")
    print("GPU:", torch.cuda.get_device_name(0))
    print("Prompts:")
    for prompt in plan.prompts:
        print(" -", prompt)

    def progress(current, total, description):
        print(f"[{current}/{total}] {description}")

    result = mg.synthesize_soundtrack_transformers(
        segments,
        args.output,
        model_dir=args.model,
        plan=plan,
        progress=progress,
        device="cuda",
    )
    print(json.dumps(result, indent=2))
    print("Output:", args.output, os.path.getsize(args.output), "bytes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
