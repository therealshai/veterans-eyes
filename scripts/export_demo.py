"""Copy a finished guide into demo/ so it ships with the repo (for judges and fresh clones).

    python scripts/export_demo.py air-filter-1a2b3c

The video is re-encoded to 720p so the repo stays small (GitHub refuses files over 100 MB).
Refuses Ego-Exo4D guides: that footage can't be published.
"""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend import store  # noqa: E402
from backend.config import DEMO_DIR  # noqa: E402


def main(guide_id: str) -> None:
    if "egoexo" in guide_id.lower():
        sys.exit("Ego-Exo4D footage can't be published: export a guide made from your own video.")
    guide = store.load_guide(guide_id)
    if guide is None:
        sys.exit(f"No guide {guide_id} in data/guides/")
    src, dst = store.folder(guide_id), DEMO_DIR / guide_id
    if dst.exists():
        sys.exit(f"{dst} already exists; delete it first to re-export.")
    dst.mkdir(parents=True)
    guide.status = "published"
    (dst / "guide.json").write_text(guide.model_dump_json(indent=2))
    for jpg in src.glob("step_*.jpg"):
        shutil.copy(jpg, dst / jpg.name)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src / "video.mp4"), "-vf", "scale=-2:'min(720,ih)'",
                    "-c:v", "libx264", "-crf", "28", "-preset", "veryfast", "-c:a", "aac", "-b:a", "96k",
                    str(dst / "video.mp4")], check=True)
    size = sum(p.stat().st_size for p in dst.iterdir()) / 1e6
    print(f"Exported to demo/{guide_id}/ ({size:.0f} MB). Commit it: git add demo/{guide_id}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(sys.argv[1])
