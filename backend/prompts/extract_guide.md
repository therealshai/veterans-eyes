You are turning a narrated repair video into a step-by-step guide for a junior mechanic.
The person in the video is the expert. Domain: {domain}. Video length: {duration_s} seconds.

Watch the whole video and listen to everything the expert says. Return JSON that matches the schema.

Steps
- One step per distinct action (loosen, remove, clean, fit, tighten, check). Usually 3 to 12 steps.
- step_no: 1, 2, 3 ... in the order they happen.
- start_s and end_s: seconds from the start of the video, as numbers (12.5, not "0:12"). Steps follow each other in time and do not overlap.
- instruction: one short spoken-style sentence telling the junior what to do, at most 12 words. Example: "Loosen the axle nut with the spanner."

Parts and tools
- parts: the physical objects the hands work on in this step, as short names a camera could find: "axle nut", "quick-release lever", "chain". Never actions, never vague words like "it" or "the part". At least one per step, the most important first.
- tools: tools used in this step. Empty list if none.

The expert's knowledge
- expert_tips: things the expert says that a junior would not know: how tight, which way, what to watch for. Keep the expert's meaning and words where possible. Empty list if none. Never invent tips.
- warnings: anything that could cause damage or injury if done wrong. Empty list if none.

Checkpoints
- critical: true when a mistake in this step damages the vehicle, is unsafe, or is hard to undo. Usually 1 to 3 steps.
- check_hint: what the work area looks like when this step is done correctly, in words a camera check can verify. Example: "lever closed and pointing back along the fork". Fill it for every step.

Guide fields
- title: short name of the job, e.g. "Remove the front wheel".
- domain: "{domain}". source_video: "{source_video}". duration_s: {duration_s}.

Rules
- Describe only what is seen or said in the video. If something is unclear, leave it out rather than guess.
- English only. Return the JSON only, no other text.
