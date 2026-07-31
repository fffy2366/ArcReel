---
name: reference-pack
description: Select, prioritize, label, and expose image inputs for video generation requests. Use after video-prompt when Codex needs to build a role-aware pack with 9宫格动作引导图/motion_guide_grid, optional repair 起始帧/start_image, optional 结束帧/end_image, and asset references such as character face closeups, character turnarounds, scenes, props, and style refs, especially when a backend supports up to nine reference images or requires public image URLs.
---

# Reference Pack

## Purpose

Use this skill to turn a video unit into an explicit image submission pack. It decides which images are actually sent to the video backend, which images are converted into prompt guidance, and which images stay visible only for user review.

This skill is part of the PlayAsLife novel-to-video pipeline after `video-prompt`. The UI must show the exact images selected for submission, allow preview/enlarge, and allow users to remove optional references before generation.

## Required references

Read these references before producing a reference pack:

- `references/output-schema.md` for the pack shape.
- `references/packing-rules.md` for priority, max-image, backend, and revision rules.
- `references/golden-1-1-reference-pack.md` as representative calibration examples.

## Workflow

1. Load the video unit.
   - Preserve `video_unit_id`, `shot_id`, `model_mode`, motion-guide roles, repair-frame roles, continuity locks, and UI labels from `video-prompt`.
   - Do not rename 9宫格动作引导图, 修复起始帧, 结束帧, 审核帧, or 资产参考图 into a generic “参考图”.

2. Load available assets.
   - Character assets may include `face_closeup` and `turnaround` images.
   - Scene assets may include environment sheets or key location stills.
   - Prop/mechanism assets may include weapons,法宝, 丹药瓶, monsters, UI/gameplay markers, or special effects references.
   - Style references are optional and low priority unless the shot lacks a stable style source.

3. Resolve backend capability.
   - Use the real backend capability if provided: max images, start image support, end image support, multi-reference support, and public URL requirement.
   - If unknown, assume max 9 total images, `start_image` supported, `end_image` conditional, and multi-reference conditional.

4. Choose pack mode.
   - `first_pass_minimal`: use fewer images; rely on video prompt + essential asset references first.
   - `continuity_sensitive`: add character, scene, or prop assets because identity or object consistency is fragile.
   - `motion_guided_first_pass`: add the 9-grid motion guide because action/body mechanics/camera direction are fragile.
   - `revision_repair`: add targeted references after an unsatisfactory generation.
   - `review_only`: no generation; keep frames for UI/user confirmation.

5. Build the selected image list.
   - Slot 1 should usually be the most important control image: 9宫格动作引导图 for action control, or repair start_image during a repair pass.
   - Add start/end repair frames only when the user is fixing a failed/unsatisfactory video or the backend explicitly needs first/last frames.
   - Add 9宫格动作引导图 when it clarifies motion, body mechanics, camera direction, or comedy timing.
   - Add only assets visible or causally important inside this clip.
   - Stay under the backend max image count, normally 9.

6. Write submission behavior.
   - For every selected image, state its role, submission target, priority, purpose, and whether a public URL is required.
   - For every unselected candidate, state why it was skipped.
   - If an image has a white background, state that the background must not be copied into the story scene.
   - In UI, selected images must be visible as thumbnails, clickable for enlargement, and removable from the pack before submission.

7. Produce user-facing summary.
   - Show a compact list of what will be sent to the backend.
   - Separate “提交给模型” from “仅审核显示” and “转成提示词说明”.
   - Do not imply that optional references are mandatory.

## Boundaries

Do not:

- Generate images.
- Upload files to a public image host.
- Rewrite the video prompt except for short reference-derived guidance.
- Invent assets that are not in the shot, project asset registry, or user input.
- Fill all nine slots just because nine are available.

Do:

- Prioritize the storyboard/keyframe over loose asset sheets.
- Treat character face closeup and character turnaround as separate asset roles.
- Keep image role labels clear for UI and debugging.
- Mark public URL needs for execution layers.
