"""Generate StoryFlow brand and favicon assets from a source logo mark.

Usage (from the repository root)::

    backend\\venv\\Scripts\\python.exe scripts\\generate_brand_assets.py ^
        path\\to\\logo.png

The source may have a transparent or solid background; the mark is cropped to
its visible bounds, centred on a transparent square and exported at the sizes
used by the app shell, login screen and browser tabs.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from PIL import Image

PADDING_RATIO = 0.06


def square_mark(source: Image.Image, size: int) -> Image.Image:
    """Crop *source* to its content and centre it on a square transparent canvas."""
    image = source.convert('RGBA')
    bbox = image.getbbox()
    if bbox:
        image = image.crop(bbox)

    available = max(1, int(size * (1 - 2 * PADDING_RATIO)))
    scale = min(available / image.width, available / image.height)
    resized = image.resize(
        (max(1, round(image.width * scale)), max(1, round(image.height * scale))),
        Image.LANCZOS,
    )

    canvas = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    canvas.paste(
        resized,
        ((size - resized.width) // 2, (size - resized.height) // 2),
        resized,
    )
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path, help='Source logo image')
    parser.add_argument(
        '--public',
        type=Path,
        default=Path('frontend/public'),
        help='Directory for public logo assets',
    )
    parser.add_argument(
        '--app',
        type=Path,
        default=Path('frontend/app'),
        help='Next.js app directory for icon/favicon files',
    )
    args = parser.parse_args()

    source = Image.open(args.source)
    args.public.mkdir(parents=True, exist_ok=True)
    args.app.mkdir(parents=True, exist_ok=True)

    # In-app logo marks. The wordmark stays as text in the shell.
    square_mark(source, 1024).save(args.public / 'logo.png', optimize=True)
    square_mark(source, 512).save(args.public / 'logo-mark.png', optimize=True)

    # Next.js metadata files: browser tab, install icon and Apple touch icon.
    square_mark(source, 512).save(args.app / 'icon.png', optimize=True)
    square_mark(source, 180).save(args.app / 'apple-icon.png', optimize=True)

    # Multi-resolution .ico for older browsers and direct /favicon.ico hits.
    favicon = square_mark(source, 256)
    favicon.save(
        args.app / 'favicon.ico',
        format='ICO',
        sizes=[(16, 16), (32, 32), (48, 48), (64, 64)],
    )

    print('Brand assets written to', args.public, 'and', args.app)


if __name__ == '__main__':
    main()
