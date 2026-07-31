---
name: continuity-qa
description: Inspect generated video clips or sampled frames against story beats, shots, keyframes, video prompts, and reference packs, then produce a structured continuity QA report and repair prescription. Use after video generation when Codex needs to diagnose face drift, outfit drift, scene drift, prop errors, wrong action timing, weak camera control, style mismatch, white-background contamination, gameplay marker mistakes, or decide whether to add references, rewrite prompts, edit keyframes, shorten, split, or regenerate a clip.
---

# Continuity QA

## Purpose

Use this skill after a video clip or sampled frames are generated. It compares the result with the intended shot and outputs a concrete repair plan.

This is a diagnosis skill, not a generation skill. It should say what went wrong, why it likely went wrong, and which upstream layer should be changed.

## Required references

Read these references before producing QA output:

- `references/output-schema.md` for QA report shape.
- `references/qa-rules.md` for failure taxonomy and repair decision rules.
- `references/golden-1-1-qa.md` as representative calibration examples.

## Workflow

1. Gather evidence.
   - Use generated video, sampled frames, or user-described failure.
   - Load the source `video_unit`, keyframe roles, reference pack, continuity locks, and original shot intent.
   - If visual evidence is missing, mark confidence lower and base the report on the user complaint plus source data.

2. Compare expected versus observed.
   - Check identity, clothing, scene, props, action, camera, performance, lighting/style, effects, technical artifacts, and gameplay markers.
   - Cite the evidence time or frame when available.

3. Classify severity.
   - `blocker`: story meaning, identity, or gameplay boundary is wrong.
   - `major`: usable only after regeneration or key upstream repair.
   - `minor`: acceptable with small prompt/reference adjustment.
   - `pass`: no repair needed.

4. Prescribe the upstream fix.
   - Face drift usually changes `reference-pack`.
   - Wrong composition usually changes `keyframe-prompt` or regenerates the keyframe.
   - Wrong action usually changes `video-prompt`.
   - Overloaded or late action usually changes `shot-director` by shortening or splitting.
   - Gameplay markers usually stay `review_only_no_generation`.

5. Write repair plan.
   - Include one primary action.
   - Include exact changes to prompts, reference pack, keyframes, or shot duration.
   - Include whether to regenerate the same clip, regenerate keyframe first, or split into new shots.

6. Produce user-facing summary.
   - Be direct: “这条能救 / 不值得救 / 应该拆镜头”.
   - Explain the smallest useful repair, not every possible repair.

## Boundaries

Do not:

- Generate replacement video.
- Upload images.
- Rewrite the entire story beat or shot sequence unless the clip is structurally impossible.
- Add references blindly when the real issue is timing, camera, or shot overload.
- Call a review-only gameplay frame a video generation failure.

Do:

- Separate visual evidence from inference.
- Map each failure to the right upstream layer.
- Prefer targeted repair over broad regeneration.
- Preserve the user-visible distinction between 起始帧, 引导参考图, 结束帧, 审核帧, and 资产参考图.
