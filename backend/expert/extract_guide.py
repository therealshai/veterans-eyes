"""
Expert video in, validated guide out.

    video --upload--> file_id --Wonder + prompt + schema--> raw JSON --save--> validate --> Guide
                                       ^                                        | fails
                                       +------ once more, with the error <------+

Run alone:
    python -m backend.expert.extract_guide fixtures/egoexo_repair_clip.mp4            # Wonder
    python -m backend.expert.extract_guide fixtures/egoexo_repair_clip.mp4 --from-raw # re-check saved answer, free
Learn note: docs/learn/02-extract-guide.md
"""
import argparse
import shutil
from pathlib import Path

from pydantic import ValidationError

from backend import meta, media, store
from backend.config import PROMPTS_DIR, SPARK_MODEL, WONDER_MODEL
from backend.models import Guide, GuideDraft, strict_schema

MODELS = {"wonder": WONDER_MODEL, "spark": SPARK_MODEL}
RETRY_NOTE = "\n\nYour previous answer failed validation with this error:\n{error}\nReturn the corrected JSON only."


def build_prompt(video_name: str, domain: str, duration: float) -> str:
    # .replace, not .format: the prompt may one day contain JSON braces.
    text = (PROMPTS_DIR / "extract_guide.md").read_text()
    return (text.replace("{domain}", domain).replace("{duration_s}", str(duration))
                .replace("{source_video}", video_name))


def extract(guide_id: str, model: str = "wonder", domain: str = "two-wheeler") -> Guide:
    """data/guides/<id>/video.mp4 -> data/guides/<id>/guide.json"""
    d = store.folder(guide_id)
    video = d / "video.mp4"
    duration = media.duration_s(video)
    prompt = build_prompt(store.read_job(guide_id).get("source_name", video.name), domain, duration)
    schema = strict_schema(GuideDraft)

    store.write_job(guide_id, progress="Uploading the video")
    file_id = meta.upload_file(video)                       # once; the retry reuses it

    store.write_job(guide_id, progress="Watching the video and writing steps")
    raw = meta.respond(MODELS[model], [meta.text_part(prompt), meta.file_part(file_id)],
                       schema=schema, schema_name="guide")
    (d / "raw_1.json").write_text(raw)
    try:
        draft = GuideDraft.model_validate_json(raw)
    except ValidationError as e:
        print(f"[extract] answer failed validation, retrying once:\n{e}")
        store.write_job(guide_id, progress="Fixing the step list")
        raw = meta.respond(MODELS[model], [meta.text_part(prompt + RETRY_NOTE.replace("{error}", str(e))),
                                           meta.file_part(file_id)], schema=schema, schema_name="guide")
        (d / "raw_2.json").write_text(raw)
        draft = GuideDraft.model_validate_json(raw)            # a second failure raises: both answers are saved

    draft.duration_s = duration                                 # trust ffprobe, not the model
    if user_title := store.read_job(guide_id).get("user_title"):
        draft.title = user_title                                # the senior's name for the job wins
    guide = Guide.from_draft(draft, guide_id)
    store.save_guide(guide)
    return guide


def from_raw(guide_id: str) -> Guide:
    raws = sorted(store.folder(guide_id).glob("raw_*.json"))
    if not raws:
        raise SystemExit("No saved answer yet: run without --from-raw first.")
    guide = Guide.from_draft(GuideDraft.model_validate_json(raws[-1].read_text()), guide_id)
    store.save_guide(guide)
    return guide


def import_video(path: Path, guide_id: str | None = None) -> str:
    """Copy a video into a new guide folder; returns the guide id."""
    guide_id = guide_id or path.stem.replace(" ", "-")
    d = store.folder(guide_id)
    d.mkdir(parents=True, exist_ok=True)
    if not (d / "video.mp4").exists():
        shutil.copyfile(path, d / "video.mp4")
    store.write_job(guide_id, source_name=path.name, title=path.stem)
    return guide_id


def print_guide(guide: Guide) -> None:
    print(f"\n{guide.title}: {len(guide.steps)} steps, {guide.duration_s:.0f}s")
    for s in guide.steps:
        flag = "!" if s.critical else " "
        print(f" {flag} {s.step_no:>2}. {s.start_s:6.1f}-{s.end_s:6.1f}s  {s.instruction}  [{', '.join(s.parts)}]")


def main() -> None:
    ap = argparse.ArgumentParser(description="Narrated repair video -> guide.json")
    ap.add_argument("video", type=Path)
    ap.add_argument("--id", help="guide id (default: the video's file name)")
    ap.add_argument("--model", choices=list(MODELS), default="wonder")
    ap.add_argument("--domain", default="two-wheeler")
    ap.add_argument("--from-raw", action="store_true", help="re-validate the saved answer, no API call")
    args = ap.parse_args()
    guide_id = import_video(args.video.resolve(), args.id)
    guide = from_raw(guide_id) if args.from_raw else extract(guide_id, args.model, args.domain)
    store.write_job(guide_id, status="draft", progress="")
    print_guide(guide)
    print(f"\nSaved data/guides/{guide_id}/guide.json   next: python -m backend.expert.keyframes {guide_id}")


if __name__ == "__main__":
    main()
