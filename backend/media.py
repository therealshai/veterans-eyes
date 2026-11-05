"""Video and image helpers: length, frames, highlight drawing. No AI here.
Uses ffmpeg/ffprobe (installed with Homebrew) and Pillow."""
import io
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from backend.models import Box

HIGHLIGHT = (245, 158, 11)        # amber-500: the one accent color for "look here"


def duration_s(video: Path) -> float:
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
            capture_output=True, text=True, check=True)
        return round(float(out.stdout.strip()), 2)
    except (subprocess.CalledProcessError, ValueError):
        raise RuntimeError(f"Could not read {video.name} as a video: "
                           "the file is empty, damaged, or not a video.") from None


def frame_at(video: Path, t: float, max_width: int = 960) -> bytes:
    """One JPEG frame at time t (seconds). Scaled down: SAM and Spark don't need 4K,
    and smaller images upload faster."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", f"{t:.2f}", "-i", str(video), "-frames:v", "1",
         "-vf", f"scale='min({max_width},iw)':-2", "-f", "image2pipe", "-vcodec", "mjpeg", "-q:v", "3", "pipe:1"],
        capture_output=True, check=True)
    if not out.stdout:
        raise RuntimeError(f"No frame at {t:.2f}s in {video.name}")
    return out.stdout


def sample_times(start: float, end: float, n: int) -> list[float]:
    """n times spread evenly inside [start, end], away from the edges
    (the edges of a step are often the hands moving in or out)."""
    if n <= 1 or end <= start:
        return [round((start + end) / 2, 2)]
    step = (end - start) / (n + 1)
    return [round(start + step * (i + 1), 2) for i in range(n)]


def draw_highlight(jpeg: bytes, box: Box | None, label: str = "") -> bytes:
    """The keyframe the junior sees: a thick amber box and a label on the part."""
    img = Image.open(io.BytesIO(jpeg)).convert("RGB")
    if box is not None:
        sx, sy = img.width / box.w, img.height / box.h          # box may be from a scaled copy
        x1, y1, x2, y2 = box.x1 * sx, box.y1 * sy, box.x2 * sx, box.y2 * sy
        pad = max(6, int(img.width * 0.01))
        x1, y1, x2, y2 = x1 - pad, y1 - pad, x2 + pad, y2 + pad
        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        d = ImageDraw.Draw(overlay)
        d.rectangle([x1, y1, x2, y2], fill=HIGHLIGHT + (40,), outline=HIGHLIGHT + (255,),
                    width=max(3, img.width // 200))
        if label:
            font = ImageFont.load_default(size=max(14, img.width // 40))
            tb = d.textbbox((0, 0), label, font=font)
            tw, th = tb[2] - tb[0], tb[3] - tb[1]
            ty = y1 - th - 10 if y1 - th - 10 > 0 else y2 + 4
            d.rectangle([x1, ty, x1 + tw + 12, ty + th + 8], fill=HIGHLIGHT + (255,))
            d.text((x1 + 6, ty + 2), label, fill=(23, 23, 23), font=font)
        img = Image.alpha_composite(img.convert("RGBA"), overlay).convert("RGB")
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88)
    return buf.getvalue()


def image_size(jpeg: bytes) -> tuple[int, int]:
    return Image.open(io.BytesIO(jpeg)).size


# Phones must play the video in replay mode. H.264 + AAC plays everywhere;
# AV1/VP9/HEVC and Opus don't on older iPhones, so those are transcoded on upload.
PHONE_VIDEO, PHONE_AUDIO = {"h264"}, {"aac", "mp3"}


def needs_transcode(video: Path) -> bool:
    """True when the clip isn't phone-playable (checked with ffprobe, no re-encode)."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "stream=codec_name,codec_type",
             "-of", "csv=p=0", str(video)], capture_output=True, text=True, check=True)
    except subprocess.CalledProcessError:
        return False  # unreadable: extract() reports it with the readable error
    kinds = {}
    for line in out.stdout.strip().splitlines():
        name, _, kind = line.strip().partition(",")
        kinds.setdefault(kind or "video", []).append(name)
    if any(c not in PHONE_VIDEO for c in kinds.get("video", [])):
        return True
    return any(c not in PHONE_AUDIO for c in kinds.get("audio", []))


def transcode_h264(video: Path) -> None:
    """Re-encode to H.264 + AAC in place (same timing; replay works on any phone)."""
    tmp = video.with_suffix(".h264.mp4")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video), "-c:v", "libx264",
         "-preset", "veryfast", "-crf", "23", "-c:a", "aac", "-movflags", "+faststart",
         str(tmp)], check=True)
    tmp.replace(video)
