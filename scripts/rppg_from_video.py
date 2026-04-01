"""
Estimate heart rate (BPM) from a face video using open-rppg,
extract the raw BVP signal, and plot it.

Install:
    pip install open-rppg matplotlib

Usage:
    python scripts/rppg_from_video.py --video path/to/face_video.mp4

Notes:
- open-rppg's process_video() automatically handles face detection.
- This is an experimental rPPG estimate from video, not a medical-grade reading.
"""

from __future__ import annotations

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(description="Estimate BPM and plot raw BVP from a face video.")
    parser.add_argument(
        "--video",
        type=str,
        default="input_video.mp4",
        help="Path to the input face video file",
    )
    parser.add_argument(
        "--model",
        type=str,
        default="FacePhys.rlap",
        help="open-rppg model name",
    )
    args = parser.parse_args()

    try:
        import matplotlib

        matplotlib.use("TkAgg")
        import matplotlib.pyplot as plt
        import rppg
    except Exception as exc:
        print(f"Missing dependency: {exc}", file=sys.stderr)
        print("Install with: pip install open-rppg matplotlib", file=sys.stderr)
        sys.exit(1)

    try:
        model = rppg.Model(args.model)
        results = model.process_video(args.video)
        raw_bvp, timestamps = model.bvp(raw=True)
    except Exception as exc:
        print(f"Error while processing video: {exc}", file=sys.stderr)
        sys.exit(1)

    heart_rate = results.get("hr")
    if heart_rate is None:
        print("Heart rate could not be estimated.", file=sys.stderr)
    else:
        print(f"Estimated Heart Rate: {float(heart_rate):.2f} BPM")

    if raw_bvp is None or timestamps is None or len(raw_bvp) == 0:
        print("No raw BVP signal was returned.", file=sys.stderr)
        sys.exit(1)

    plt.figure(figsize=(12, 5))
    plt.plot(timestamps, raw_bvp, color="crimson", linewidth=1.5, label="Raw BVP")
    plt.title("Raw BVP Signal from Face Video (open-rppg)")
    plt.xlabel("Time (seconds)")
    plt.ylabel("BVP Amplitude")
    plt.grid(True, alpha=0.3)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
