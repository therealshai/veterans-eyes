"""Turn one IndustReal recording (JPEG frames, 10 fps, no audio) into an MP4 the app can use.

    python scripts/industreal_video.py <recording folder>                    # -> fixtures/industreal_<name>.mp4
    python scripts/industreal_video.py <recording folder> --voice narration.m4a
        adds your recorded narration as the audio track (IndustReal has none), so Wonder
        hears a "senior" explaining the assembly. Say on screen that the narration is yours.

IndustReal is Apache-2.0: this video may appear in the public demo, with credit.
"""
import argparse
import subprocess
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("recording", type=Path, help="folder that contains rgb/")
    ap.add_argument("--voice", type=Path, help="optional narration audio to add")
    ap.add_argument("--out", type=Path)
    ap.add_argument("--fps", type=float, default=10, help="10 = real time; 20 = twice as fast")
    a = ap.parse_args()

    rgb = a.recording / "rgb"
    frames = sorted(p for p in rgb.iterdir() if p.suffix.lower() in (".jpg", ".jpeg", ".png"))
    if not frames:
        raise SystemExit(f"No frames in {rgb}")
    out = a.out or Path("fixtures") / f"industreal_{a.recording.name}.mp4"
    out.parent.mkdir(parents=True, exist_ok=True)
    listing = out.with_suffix(".frames.txt")          # concat list: works whatever the file names are
    listing.write_text("".join(f"file '{f.resolve()}'\nduration {1 / a.fps}\n" for f in frames))

    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(listing)]
    if a.voice:
        cmd += ["-i", str(a.voice), "-map", "0:v", "-map", "1:a", "-c:a", "aac", "-shortest"]
    cmd += ["-vf", "scale=-2:720,format=yuv420p", "-r", str(a.fps), "-c:v", "libx264", "-crf", "23", str(out)]
    subprocess.run(cmd, check=True)
    listing.unlink()
    print(f"{out}  ({len(frames)} frames, {len(frames) / a.fps:.0f} s)")
    print(f"Make a guide:  bash scripts/run_capture.sh {out} industreal-{a.recording.name.replace('_', '-')} industrial-assembly")


if __name__ == "__main__":
    main()
