#!/usr/bin/env python3
"""
Watermark Remover — removes watermarks from video using OpenCV inpainting.
Supports automatic detection (temporal + gradient analysis) and manual coordinates.

Usage:
    # Auto-detect watermark position
    python remove_watermark.py input.mp4 output.mp4 --auto

    # Auto-detect + preview before processing
    python remove_watermark.py input.mp4 --auto --preview

    # Manual coordinates
    python remove_watermark.py input.mp4 output.mp4 --x1 500 --y1 262 --x2 718 --y2 385

    # Manual preview
    python remove_watermark.py input.mp4 --preview
"""

import cv2
import numpy as np
import argparse
import sys
import os
from pathlib import Path


# ── Auto Detection ────────────────────────────────────────────────────────────

def _score_candidate(contour, grad_mean: np.ndarray, std: np.ndarray,
                     frame_h: int, frame_w: int) -> float:
    """
    Score a contour region as a watermark candidate.
    Higher = more likely to be a watermark.

    Watermarks tend to:
      - Have sharp, persistent edges (high gradient in the temporal mean)
      - Be in a corner (logos/brand tags are placed away from center)
      - Be smaller than ~8% of the frame
      - Not be too tiny (> 0.1% of frame)
    """
    frame_area = frame_h * frame_w
    area = cv2.contourArea(contour)

    if area < frame_area * 0.001 or area > frame_area * 0.08:
        return -1.0

    x, y, w, h = cv2.boundingRect(contour)
    cx, cy = x + w / 2, y + h / 2

    # Gradient density inside the bounding box
    roi_grad = grad_mean[y:y+h, x:x+w]
    roi_std  = std[y:y+h, x:x+w]
    grad_density = float(np.mean(roi_grad))
    stability    = 1.0 / (1.0 + float(np.mean(roi_std)))  # lower std = more stable

    # Corner preference: distance from nearest corner normalized by frame diagonal
    diag = (frame_h**2 + frame_w**2) ** 0.5
    corner_dists = [
        ((cx**2 + cy**2) ** 0.5),                              # top-left
        (((frame_w - cx)**2 + cy**2) ** 0.5),                  # top-right
        ((cx**2 + (frame_h - cy)**2) ** 0.5),                  # bottom-left
        (((frame_w - cx)**2 + (frame_h - cy)**2) ** 0.5),      # bottom-right
    ]
    corner_score = 1.0 - min(corner_dists) / diag  # higher = closer to a corner

    return grad_density * stability * (0.5 + corner_score)


def detect_watermark(cap, n_samples: int = 50, std_thresh: float = 45.0,
                     grad_thresh: float = 15.0):
    """
    Detect watermark bounding box using temporal gradient analysis.

    Algorithm:
      1. Sample N frames evenly across the video.
      2. Compute per-pixel temporal mean and std.
      3. Compute gradient of the mean image (persistent edges = watermark outline).
      4. Candidate mask = (gradient high) AND (std low) = stable visual element.
      5. Score each contour by gradient density × stability × corner proximity.
      6. Return bbox of best candidate, or None.
    """
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    indices = np.linspace(0, total - 1, min(n_samples, total), dtype=int)

    frames = []
    for idx in indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
        ret, frame = cap.read()
        if ret:
            frames.append(cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32))

    if len(frames) < 5:
        return None

    stack    = np.stack(frames, axis=0)
    mean_img = np.mean(stack, axis=0)
    std_img  = np.std(stack,  axis=0)
    frame_h, frame_w = stack.shape[1], stack.shape[2]

    # Gradient magnitude of the temporal mean
    mean_u8 = mean_img.astype(np.uint8)
    gx = cv2.Sobel(mean_u8, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(mean_u8, cv2.CV_32F, 0, 1, ksize=3)
    grad = np.sqrt(gx**2 + gy**2)

    # Binary mask: persistent edge + temporally stable
    persistent = (grad    > grad_thresh).astype(np.uint8)
    stable     = (std_img < std_thresh ).astype(np.uint8)
    candidate  = (persistent & stable) * 255

    # Morphological cleanup
    close_k = cv2.getStructuringElement(cv2.MORPH_RECT, (30, 30))
    open_k  = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_CLOSE, close_k)
    candidate = cv2.morphologyEx(candidate, cv2.MORPH_OPEN,  open_k)

    contours, _ = cv2.findContours(candidate, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours:
        return None

    # Score each candidate and pick the best
    scored = []
    for c in contours:
        s = _score_candidate(c, grad, std_img, frame_h, frame_w)
        if s > 0:
            scored.append((s, c))

    if not scored:
        return None

    scored.sort(key=lambda x: -x[0])
    best = scored[0][1]
    x, y, w, h = cv2.boundingRect(best)

    pad = 10
    x1 = max(0, x - pad)
    y1 = max(0, y - pad)
    x2 = min(frame_w, x + w + pad)
    y2 = min(frame_h, y + h + pad)

    return x1, y1, x2, y2


# ── Mask / Inpaint ────────────────────────────────────────────────────────────

def build_mask(height: int, width: int, x1: int, y1: int, x2: int, y2: int) -> np.ndarray:
    mask = np.zeros((height, width), dtype=np.uint8)
    mask[y1:y2, x1:x2] = 255
    return mask


def remove_watermark_frame(frame: np.ndarray, mask: np.ndarray, radius: int) -> np.ndarray:
    return cv2.inpaint(frame, mask, radius, cv2.INPAINT_TELEA)


# ── Preview ───────────────────────────────────────────────────────────────────

def preview(cap, x1: int, y1: int, x2: int, y2: int, radius: int, input_path: str) -> None:
    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    ret, frame = cap.read()
    if not ret:
        sys.exit("Could not read frame from video.")

    h, w = frame.shape[:2]
    mask    = build_mask(h, w, x1, y1, x2, y2)
    cleaned = remove_watermark_frame(frame, mask, radius)

    marked = frame.copy()
    cv2.rectangle(marked, (x1, y1), (x2, y2), (0, 0, 255), 3)
    cv2.putText(marked, f"({x1},{y1})-({x2},{y2})", (x1, max(y1 - 8, 15)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)

    comparison = np.hstack([marked, cleaned])
    out_path = Path(input_path).stem + "_preview.jpg"
    cv2.imwrite(out_path, comparison)
    print(f"Preview saved: {out_path}")
    print(f"  Region: x1={x1} y1={y1} x2={x2} y2={y2}")
    print(f"  Left = original (red box) | Right = inpainted result")


# ── Full video processing ─────────────────────────────────────────────────────

def process_video(cap, input_path: str, output_path: str,
                  x1: int, y1: int, x2: int, y2: int, radius: int) -> None:
    w     = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h     = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps   = cap.get(cv2.CAP_PROP_FPS)
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    tmp_video = output_path + ".tmp.mp4"
    writer = cv2.VideoWriter(tmp_video, fourcc, fps, (w, h))
    mask   = build_mask(h, w, x1, y1, x2, y2)

    cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
    print(f"Processing {total} frames ({w}x{h} @ {fps:.1f}fps)")
    print(f"Watermark region: ({x1},{y1}) -> ({x2},{y2})")

    for i in range(total):
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(remove_watermark_frame(frame, mask, radius))
        if (i + 1) % 100 == 0:
            print(f"  {i+1}/{total} frames ({(i+1)/total*100:.1f}%)")

    writer.release()

    try:
        import imageio_ffmpeg, subprocess
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg, "-y",
            "-i", tmp_video, "-i", input_path,
            "-c:v", "copy", "-c:a", "aac",
            "-map", "0:v:0", "-map", "1:a:0",
            "-shortest", output_path,
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


# ── CLI ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Remove a watermark from video via inpainting (auto or manual).",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Auto-detect + preview:
    python remove_watermark.py input.mp4 --auto --preview

  Auto-detect + process full video:
    python remove_watermark.py input.mp4 output.mp4 --auto

  Manual coordinates + preview:
    python remove_watermark.py input.mp4 --preview --x1 500 --y1 262 --x2 718 --y2 385

  Manual coordinates:
    python remove_watermark.py input.mp4 output.mp4 --x1 500 --y1 262 --x2 718 --y2 385
        """
    )
    parser.add_argument("input",  help="Input video file")
    parser.add_argument("output", nargs="?", default=None, help="Output video file")
    parser.add_argument("--auto",    action="store_true", help="Auto-detect watermark position")
    parser.add_argument("--preview", action="store_true", help="Save before/after preview image only")
    parser.add_argument("--x1",     type=int,   default=500,  help="Watermark left edge (manual)")
    parser.add_argument("--y1",     type=int,   default=262,  help="Watermark top edge (manual)")
    parser.add_argument("--x2",     type=int,   default=718,  help="Watermark right edge (manual)")
    parser.add_argument("--y2",     type=int,   default=385,  help="Watermark bottom edge (manual)")
    parser.add_argument("--radius", type=int,   default=5,    help="Inpaint radius (default: 5)")
    parser.add_argument("--samples",type=int,   default=50,   help="Frames sampled for auto-detect (default: 50)")
    parser.add_argument("--stable", type=float, default=45.0, help="Max temporal std for auto-detect (default: 45)")
    parser.add_argument("--grad",   type=float, default=15.0, help="Min gradient for auto-detect (default: 15)")
    args = parser.parse_args()

    cap = cv2.VideoCapture(args.input)
    if not cap.isOpened():
        sys.exit(f"Cannot open: {args.input}")

    x1, y1, x2, y2 = args.x1, args.y1, args.x2, args.y2

    if args.auto:
        print(f"Auto-detecting watermark (sampling {args.samples} frames)...")
        result = detect_watermark(cap, n_samples=args.samples,
                                  std_thresh=args.stable, grad_thresh=args.grad)
        if result is None:
            print("Warning: auto-detect found nothing. Using manual coordinates.")
            print(f"  Fallback: x1={x1} y1={y1} x2={x2} y2={y2}")
        else:
            x1, y1, x2, y2 = result
            print(f"Detected: x1={x1} y1={y1} x2={x2} y2={y2}")

    if args.preview:
        preview(cap, x1, y1, x2, y2, args.radius, args.input)
        cap.release()
        return

    if args.output is None:
        args.output = Path(args.input).stem + "_no_watermark.mp4"

    process_video(cap, args.input, args.output, x1, y1, x2, y2, args.radius)
    cap.release()


if __name__ == "__main__":
    main()
