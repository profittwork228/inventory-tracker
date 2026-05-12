#!/usr/bin/env python3
"""
Video Clipper — extract one or multiple clips from a video by time range.

Usage examples:
    # Single clip: 5s to 15s
    python3 clip_video.py input.mp4 --start 5 --end 15 --output clip.mp4

    # Multiple clips from a JSON clips file
    python3 clip_video.py input.mp4 --clips clips.json

    # Auto-split into N equal parts
    python3 clip_video.py input.mp4 --parts 3

    # Preview: show info about each clip without extracting
    python3 clip_video.py input.mp4 --clips clips.json --info
"""

import cv2
import numpy as np
import argparse
import json
import os
import sys
import subprocess
from pathlib import Path


def get_video_info(path: str) -> dict:
    cap = cv2.VideoCapture(path)
    if not cap.isOpened():
        sys.exit(f"Cannot open video: {path}")
    info = {
        "width": int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "height": int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "fps": cap.get(cv2.CAP_PROP_FPS),
        "frame_count": int(cap.get(cv2.CAP_PROP_FRAME_COUNT)),
    }
    info["duration"] = info["frame_count"] / info["fps"]
    cap.release()
    return info


def seconds_to_hms(s: float) -> str:
    h = int(s // 3600)
    m = int((s % 3600) // 60)
    sec = s % 60
    return f"{h:02d}:{m:02d}:{sec:05.2f}"


def parse_time(value) -> float:
    """Accept float seconds or HH:MM:SS.ss string."""
    if isinstance(value, (int, float)):
        return float(value)
    parts = str(value).split(":")
    if len(parts) == 3:
        return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
    if len(parts) == 2:
        return int(parts[0]) * 60 + float(parts[1])
    return float(value)


def extract_clip_opencv(input_path: str, output_path: str, start: float, end: float, info: dict) -> None:
    fps = info["fps"]
    w, h = info["width"], info["height"]
    start_frame = int(start * fps)
    end_frame = min(int(end * fps), info["frame_count"])

    cap = cv2.VideoCapture(input_path)
    cap.set(cv2.CAP_PROP_POS_FRAMES, start_frame)

    tmp = output_path + ".tmp.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(tmp, fourcc, fps, (w, h))

    for _ in range(end_frame - start_frame):
        ret, frame = cap.read()
        if not ret:
            break
        writer.write(frame)

    cap.release()
    writer.release()

    # Mux audio segment
    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg, "-y",
            "-i", tmp,
            "-i", input_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-ss", str(start),
            "-t", str(end - start),
            "-shortest",
            output_path,
        ]
        result = subprocess.run(cmd, capture_output=True)
        if result.returncode == 0:
            os.remove(tmp)
        else:
            os.rename(tmp, output_path)
    except Exception:
        os.rename(tmp, output_path)


def extract_clip_ffmpeg(ffmpeg: str, input_path: str, output_path: str, start: float, end: float) -> None:
    cmd = [
        ffmpeg, "-y",
        "-ss", str(start),
        "-to", str(end),
        "-i", input_path,
        "-c:v", "libx264",
        "-c:a", "aac",
        "-avoid_negative_ts", "make_zero",
        output_path,
    ]
    result = subprocess.run(cmd, capture_output=True)
    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr.decode()[-200:]}")


def process_clips(input_path: str, clips: list, out_dir: str, info: dict) -> None:
    os.makedirs(out_dir, exist_ok=True)
    stem = Path(input_path).stem

    try:
        import imageio_ffmpeg
        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
        use_ffmpeg = True
    except Exception:
        use_ffmpeg = False

    for i, clip in enumerate(clips):
        start = parse_time(clip.get("start", 0))
        end = parse_time(clip.get("end", info["duration"]))
        label = clip.get("label", f"clip{i+1:02d}")
        out_file = os.path.join(out_dir, f"{stem}_{label}.mp4")

        dur = end - start
        print(f"  [{i+1}/{len(clips)}] {label}: {seconds_to_hms(start)} -> {seconds_to_hms(end)} ({dur:.2f}s) -> {out_file}")

        if use_ffmpeg:
            extract_clip_ffmpeg(ffmpeg, input_path, out_file, start, end)
        else:
            extract_clip_opencv(input_path, out_file, start, end, info)

    print(f"\nAll clips saved to: {out_dir}/")


def equal_parts(input_path: str, n_parts: int, out_dir: str, info: dict) -> None:
    dur = info["duration"]
    part_dur = dur / n_parts
    clips = [
        {"start": i * part_dur, "end": min((i + 1) * part_dur, dur), "label": f"part{i+1:02d}"}
        for i in range(n_parts)
    ]
    print(f"Splitting {dur:.2f}s into {n_parts} parts of ~{part_dur:.2f}s each")
    process_clips(input_path, clips, out_dir, info)


def main():
    parser = argparse.ArgumentParser(description="Extract clips from a video by time range.")
    parser.add_argument("input", help="Input video file")
    parser.add_argument("--start", type=str, default=None, help="Start time in seconds or HH:MM:SS")
    parser.add_argument("--end", type=str, default=None, help="End time in seconds or HH:MM:SS")
    parser.add_argument("--output", type=str, default=None, help="Output file for single clip")
    parser.add_argument("--clips", type=str, default=None, help="JSON file with list of clips [{start, end, label}]")
    parser.add_argument("--parts", type=int, default=None, help="Auto-split into N equal parts")
    parser.add_argument("--out-dir", type=str, default="output_clips", help="Output directory (default: output_clips)")
    parser.add_argument("--info", action="store_true", help="Print video info and clip plan, no extraction")
    args = parser.parse_args()

    info = get_video_info(args.input)
    print(f"Input: {args.input}")
    print(f"  {info['width']}x{info['height']} @ {info['fps']:.2f}fps | {info['frame_count']} frames | {info['duration']:.2f}s ({seconds_to_hms(info['duration'])})")

    if args.info and not (args.start or args.clips or args.parts):
        return

    if args.parts:
        if args.info:
            dur = info["duration"]
            part_dur = dur / args.parts
            print(f"\n{args.parts} equal parts of ~{part_dur:.2f}s each:")
            for i in range(args.parts):
                s = i * part_dur
                e = min((i + 1) * part_dur, dur)
                print(f"  part{i+1:02d}: {seconds_to_hms(s)} -> {seconds_to_hms(e)}")
        else:
            equal_parts(args.input, args.parts, args.out_dir, info)
        return

    if args.clips:
        with open(args.clips) as f:
            clips = json.load(f)
        if args.info:
            print(f"\nClips from {args.clips}:")
            for i, c in enumerate(clips):
                s = parse_time(c.get("start", 0))
                e = parse_time(c.get("end", info["duration"]))
                print(f"  [{i+1}] {c.get('label', f'clip{i+1}')} : {seconds_to_hms(s)} -> {seconds_to_hms(e)} ({e-s:.2f}s)")
        else:
            process_clips(args.input, clips, args.out_dir, info)
        return

    if args.start is not None or args.end is not None:
        start = parse_time(args.start) if args.start else 0.0
        end = parse_time(args.end) if args.end else info["duration"]
        stem = Path(args.input).stem
        output = args.output or f"{stem}_clip_{start:.0f}s_{end:.0f}s.mp4"

        if args.info:
            print(f"\nSingle clip: {seconds_to_hms(start)} -> {seconds_to_hms(end)} ({end-start:.2f}s)")
            return

        print(f"\nExtracting: {seconds_to_hms(start)} -> {seconds_to_hms(end)} ({end-start:.2f}s)")
        clips = [{"start": start, "end": end, "label": Path(output).stem}]
        process_clips(args.input, clips, str(Path(output).parent), info)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
