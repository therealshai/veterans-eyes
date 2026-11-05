"""Upload edge cases: files that are not usable videos fail the job with a
readable error. The job must never hang in "processing" or save half a guide."""
import json
import subprocess

from backend import media, meta, store
from backend.expert import pipeline
from backend.models import Box
from tests.conftest import guide_dict, step


def _guide_with_video(tmp_guides, video_bytes: bytes) -> str:
    gid = "broken-upload"
    d = tmp_guides / gid
    d.mkdir(parents=True)
    (d / "video.mp4").write_bytes(video_bytes)
    store.write_job(gid, status="processing", progress="Queued", title="broken")
    return gid


def _failed_cleanly(gid: str) -> str:
    job = store.read_job(gid)
    assert job["status"] == "failed", f"job stuck: {job}"
    assert store.load_guide(gid) is None, "a failed job must not leave a guide behind"
    assert job.get("error"), "a failed job must say why"
    return job["error"]


def test_non_video_file_fails_readably(tmp_guides):
    gid = _guide_with_video(tmp_guides, b"This is a text file wearing a .mp4 name." * 20)
    pipeline.run(gid)
    assert "Could not read" in _failed_cleanly(gid)


def test_empty_file_fails_readably(tmp_guides):
    gid = _guide_with_video(tmp_guides, b"")
    pipeline.run(gid)
    assert "Could not read" in _failed_cleanly(gid)


def test_zero_second_video_fails_readably(tmp_guides):
    tmp_guides.mkdir(parents=True, exist_ok=True)
    zero = tmp_guides / "zero.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=10",
                    "-t", "0", "-pix_fmt", "yuv420p", str(zero)], check=True)
    gid = _guide_with_video(tmp_guides, zero.read_bytes())
    pipeline.run(gid)
    assert "Could not read" in _failed_cleanly(gid)


def _tiny_clip(path, video_codec, with_audio=False):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc=size=64x64:rate=10"]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", "sine=frequency=440:duration=2"]
    cmd += ["-t", "2", "-c:v", video_codec, "-pix_fmt", "yuv420p"]
    cmd += ["-c:a", "aac", "-shortest"] if with_audio else ["-an"]
    subprocess.run(cmd + [str(path)], check=True)


def test_non_h264_is_transcoded_h264_is_left_alone(tmp_path):
    other = tmp_path / "other.mp4"
    _tiny_clip(other, "mpeg4")                       # any non-H.264 video codec
    assert media.needs_transcode(other)
    media.transcode_h264(other)
    assert not media.needs_transcode(other)
    assert abs(media.duration_s(other) - 2.0) < 0.2  # same timing

    phone = tmp_path / "phone.mp4"
    _tiny_clip(phone, "libx264", with_audio=True)     # already phone-playable
    assert not media.needs_transcode(phone)


def test_short_silent_upload_reaches_draft(tmp_guides, monkeypatch):
    """A 2 s silent clip (mismatched codec too) runs the whole pipeline with fakes."""
    tmp_guides.mkdir(parents=True, exist_ok=True)
    clip = tmp_guides / "short.mp4"
    _tiny_clip(clip, "mpeg4")
    gid = _guide_with_video(tmp_guides, clip.read_bytes())

    def fake_respond(model, parts, **kw):
        return json.dumps(guide_dict(duration_s=2.0, steps=[step(1, 0.0, 1.0), step(2, 1.0, 2.0)]))

    monkeypatch.setattr(meta, "upload_file", lambda path: "file-fake")
    monkeypatch.setattr(meta, "respond", fake_respond)
    monkeypatch.setattr(meta, "spark", lambda parts, **kw: "ok")
    monkeypatch.setattr(meta, "sam_boxes",
                        lambda jpeg, c: [Box(x1=1, y1=1, x2=10, y2=10, w=64, h=64, score=0.9)])
    pipeline.run(gid)
    assert store.read_job(gid)["status"] == "draft"
    assert not media.needs_transcode(tmp_guides / gid / "video.mp4")
    assert store.load_guide(gid).steps[0].keyframe == "step_1.jpg"
