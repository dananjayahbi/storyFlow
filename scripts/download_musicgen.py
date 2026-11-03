"""Download and verify the MusicGen-Small checkpoint used by StoryFlow.

Run with any Python that has ``huggingface_hub`` (the CUDA TTS venv has it):

    backend\\qwen_tts\\.venv\\Scripts\\python.exe scripts\\download_musicgen.py

Only the files needed by Transformers are fetched (about 2.4 GB), not the
duplicate AudioCraft ``.bin`` / state-dict files.  The destination defaults to
``models/musicgen-small`` and can be overridden with ``--dest``.

The weights are verified against Hugging Face's SHA-256 after downloading.
This matters: a truncated or partially-resumed ``model.safetensors`` still
loads without error, but MusicGen then generates pure noise.  Use
``--verify-only`` to check an existing download.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys

MODEL_ID = "facebook/musicgen-small"
PATTERNS = [
    "config.json",
    "generation_config.json",
    "preprocessor_config.json",
    "tokenizer.json",
    "tokenizer_config.json",
    "special_tokens_map.json",
    "spiece.model",
    "model.safetensors",
]

# Hugging Face LFS object id for facebook/musicgen-small/model.safetensors.
EXPECTED_WEIGHTS_SHA256 = (
    "1bdc99d43eb6c775967df24b65b0a9f847c0907e95664698d93b5a1c35f5090d"
)
WEIGHTS_SIZE = 2364427288
WEIGHTS_FILE = "model.safetensors"


def sha256_file(path: str, chunk_size: int = 8 * 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(chunk_size), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_weights(dest: str, *, expected: str = EXPECTED_WEIGHTS_SHA256) -> bool:
    """Return True when the local weights match Hugging Face's checksum."""
    path = os.path.join(dest, WEIGHTS_FILE)
    if not os.path.isfile(path):
        print(f"MISSING {path}", file=sys.stderr)
        return False

    size = os.path.getsize(path)
    if size != WEIGHTS_SIZE:
        print(
            f"INVALID {path}: size {size} != expected {WEIGHTS_SIZE} "
            "(truncated download)",
            file=sys.stderr,
        )
        return False

    print(f"Verifying SHA-256 of {path} ({size / 1e9:.2f} GB)…", flush=True)
    actual = sha256_file(path)
    if actual.lower() != expected.lower():
        print(
            f"INVALID {path}: SHA-256 {actual} != expected {expected}. "
            "Delete the file and download it again.",
            file=sys.stderr,
        )
        return False

    print(f"OK {path}: SHA-256 matches Hugging Face.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dest",
        default=os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "models",
            "musicgen-small",
        ),
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Check an existing download without fetching anything.",
    )
    args = parser.parse_args()

    if args.verify_only:
        return 0 if verify_weights(args.dest) else 1

    from huggingface_hub import snapshot_download

    path = snapshot_download(
        repo_id=MODEL_ID,
        local_dir=args.dest,
        allow_patterns=PATTERNS,
    )
    print("DOWNLOADED", path)

    if not verify_weights(path):
        print(
            "The downloaded checkpoint is corrupt and would generate noise. "
            "Remove models/musicgen-small/model.safetensors and run again.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
