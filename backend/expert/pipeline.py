"""The whole expert capture as one background job: extract steps, then keyframes.
The API starts it after an upload; job.json shows progress to the app."""
import traceback

from backend import media, store
from backend.expert.extract_guide import extract
from backend.expert.keyframes import build_keyframes


def run(guide_id: str, model: str = "wonder", domain: str = "two-wheeler") -> None:
    try:
        store.write_job(guide_id, status="processing", progress="Starting", error=None)
        video = store.folder(guide_id) / "video.mp4"
        if media.needs_transcode(video):
            store.write_job(guide_id, progress="Preparing the video for phones")
            media.transcode_h264(video)
        extract(guide_id, model, domain)
        build_keyframes(guide_id)
        store.write_job(guide_id, status="draft", progress="")
    except Exception as e:
        traceback.print_exc()
        store.write_job(guide_id, status="failed", progress="", error=f"{type(e).__name__}: {e}")
