"""
crop_label.py — Auto-crop a shipping label PDF to just the label content.

eBay, USPS, UPS, FedEx, and Pitney Bowes all hand you a full letter-size PDF
with a 4x6 label tucked somewhere on the page. This script renders each page,
finds the bounding box of non-white content, and crops the PDF to that region
so it prints cleanly on a 4x6 thermal label printer.

Usage:
    python crop_label.py input.pdf
    python crop_label.py input.pdf --output my_label_cropped.pdf
    python crop_label.py input.pdf --margin 12      # padding in pts (default: 8)
    python crop_label.py input.pdf --rotate 90      # rotate after crop (90, 180, 270)
    python crop_label.py input.pdf --threshold 240  # white cutoff 0-255 (default: 240)

Install dependencies:
    pip install pymupdf numpy
"""

import argparse
from pathlib import Path

import numpy as np
import pymupdf


def find_content_box(page, threshold=240):
    """Render a page at 72dpi and return its non-white bbox in image coords.

    Image coords are top-left origin; at 72dpi 1 image pixel == 1 PDF point,
    which is what PyMuPDF's set_cropbox expects.

    Returns (x0, y0, x1, y1) or None if the page is blank at this threshold.
    """
    pix = page.get_pixmap(dpi=72, colorspace=pymupdf.csGRAY)
    arr = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width)

    rows = np.any(arr < threshold, axis=1)
    cols = np.any(arr < threshold, axis=0)

    if not rows.any() or not cols.any():
        return None

    row_min, row_max = np.where(rows)[0][[0, -1]]
    col_min, col_max = np.where(cols)[0][[0, -1]]
    return int(col_min), int(row_min), int(col_max), int(row_max)


def crop_pdf(input_path, output_path, margin=8, rotate=None, threshold=240):
    doc = pymupdf.open(input_path)
    try:
        any_cropped = False
        for i, page in enumerate(doc):
            box = find_content_box(page, threshold=threshold)
            if box is None:
                print(f"  Page {i + 1}: no content detected, skipping crop")
                continue

            x0, y0, x1, y1 = box
            x0 -= margin
            y0 -= margin
            x1 += margin
            y1 += margin

            crop = pymupdf.Rect(x0, y0, x1, y1) & page.rect
            page.set_cropbox(crop)

            if rotate:
                page.set_rotation((page.rotation + rotate) % 360)

            w_in = (crop.x1 - crop.x0) / 72
            h_in = (crop.y1 - crop.y0) / 72
            print(f'  Page {i + 1}: cropped to {w_in:.2f}" x {h_in:.2f}"')
            any_cropped = True

        if not any_cropped:
            raise ValueError(
                "No content detected on any page — try lowering --threshold."
            )

        doc.save(output_path, garbage=4, deflate=True)
    finally:
        doc.close()

    print(f"Saved: {output_path}")
    if rotate:
        print(f"  Rotated: {rotate} degrees")


def default_output_path(input_path: Path) -> Path:
    """Append _cropped before the extension, preserving the original suffix."""
    return input_path.with_name(f"{input_path.stem}_cropped{input_path.suffix}")


def main():
    parser = argparse.ArgumentParser(
        description="Auto-crop a shipping label PDF to just the label content."
    )
    parser.add_argument("input", type=Path, help="Input PDF path")
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Output path (default: <input>_cropped.pdf)",
    )
    parser.add_argument(
        "--margin", type=int, default=8,
        help="Padding around label in pts, 1pt = 1/72\" (default: 8)",
    )
    parser.add_argument(
        "--rotate", type=int, default=None, choices=[90, 180, 270],
        help="Rotate page after crop",
    )
    parser.add_argument(
        "--threshold", type=int, default=240,
        help="Grayscale cutoff for 'white' 0-255 (default: 240)",
    )
    args = parser.parse_args()

    if not args.input.is_file():
        parser.error(f"Input file not found: {args.input}")

    output = args.output or default_output_path(args.input)
    if output.resolve() == args.input.resolve():
        output = default_output_path(args.input)

    crop_pdf(
        str(args.input), str(output),
        margin=args.margin, rotate=args.rotate, threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
