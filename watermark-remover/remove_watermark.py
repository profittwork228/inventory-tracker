#!/usr/bin/env python3
"""
Watermark Remover — removes a fixed-position watermark from a video using OpenCV inpainting.

Usage:
    python3 remove_watermark.py input.mp4 output.mp4 [options]

Options:
    --x1 X1         Left edge of watermark region (default: 500)
    --y1 Y1         Top edge of watermark region (default: 262)
    --x2 X2         Right edge of watermark region (default: 718)
    --y2 Y2         Bottom edge of watermark region (default: 385)
    --radius RADIUS Inpaint radius (default: 5)
    --preview       Save a before/after comparison image instead of processing full video
"""

import cv2
import numpy as np
import argparse
import sys
import os
from pathlib import Path


def build_mask(height: int, width: int, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y1:y2, x1:x2] = 255
    return mask


def remove_watermark_frame(frame: np.ndarray, mask: np.ndarray, radius: int) -> np.ndarray:
    return cv2.inpaint(frame, mask, radius, cv2.INPAINT_TELEA)


def preview(input_path: str, x1: int, y1: int, x2: int, y2: int, radius: int) -> None:
    cap = cv2.VideoCapture(input_path)
    ret, frame = cap.read()
    cap.release()
    if not ret:
        sys.exit("Could not read frame from video.")

    h, w = frame.shape[:2]
    mask = build_mask(h, w, x1, y1, x2, y2)
    cleaned = remove_watermark_frame(frame, mask, radius)

    # Draw rectangle on original to show region
    marked = frame.copy()
    cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 0, 255), 2)

    comparison = np.hstack([marked, cleaned])
    out_path = Path(input_path).stem + "_preview.jpg"
    cv2.imwrite(out_path, comparison)
    print(f"Preview saved to: {out_path}")
    print(f"Left = original with watermark region marked | Right = inpainted result")


def process_video(input_path: str, output_path: str, x1: int, y1: int, x2: int, y2: int, radius: int) -> None:
    cap = cv2.VideoCapture(input_path)
    if not cap.isOpened():
        sys.exit(f"Cannot open: {input_path}")

    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    # Write to a temp file first, then mux audio in
    tmp_video = output_path + ".tmp.mp4"
    writer = cv2.VideoWriter(tmp_video, fourcc, fps, (w, h))
    mask = build_mask(h, w, x1, y1, x2, y2)

    print(f"Processing {total} frames ({w}x{h} @ {fps:.1f}fps)")
    print(f"Watermark region: ({x1},{y1}) -> ({x2},{y2})")

    for i in range(total):
        ret, frame = cap.read()
        if not ret:
            break
        cleaned = remove_watermark_frame(frame, mask, radius)
        writer.write(cleaned)
        if (i + 1) % 50 == 0:
            pct = (i + 1) / total * 100
            print(f"  {i+1}/{total} frames ({pct:.1f}%)")

    cap.release()
    writer.release()

    # Mux original audio back using imageio-ffmpeg
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        import subprocess
        cmd = [
            ffmpeg, "-y",
            "-i", tmp_video,
            "-i", input_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            os.remove(tmp_video)
            print(f"\nDone! Output with audio: {output_path}")
        else:
            os.rename(tmp_video, output_path)
            print(f"\nDone (no audio mux): {output_path}")
    except Exception:
        os.rename(tmp_video, output_path)
        print(f"\nDone (no audio mux): {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Remove a fixed watermark from a video via inpainting.")
    parser.add_argument("input", help="Input video file")
    parser.add_argument("output", nargs="?", default=None, help="Output video file")
    parser.add_argument("--x1", type=int, default=500, help="Watermark left edge (default: 500)")
    parser.add_argument("--y1", type=int, default=262, help="Watermark top edge (default: 262)")
    parser.add_argument("--x2", type=int, default=718, help="Watermark right edge (default: 718)")
    parser.add_argument("--y2", type=int, default=385, help="Watermark bottom edge (default: 385)")
    parser.add_argument("--radius", type=int, default=5, help="Inpaint radius (default: 5)")
    parser.add_argument("--preview", action="store_true", help="Generate a before/after preview image only")
    args = parser.parse_args()

    if args.preview:
        preview(args.input, args.x1, args.y1, args.x2, args.y2, args.radius)
        return

    if args.output is None:
        stem = Path(args.input).stem
        args.output = f"{stem}_no_watermark.mp4"

    process_video(args.input, args.output, args.x1, args.y1, args.x2, args.y2, args.radius)


if __name__ == "__main__":
    main()
