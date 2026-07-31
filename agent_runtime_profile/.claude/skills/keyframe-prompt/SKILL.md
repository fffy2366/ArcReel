---
name: keyframe-prompt
description: Create repair keyframe prompts after video review. Use after first-pass video generation and human QA when Codex needs to fix a bad clip with 起始帧/start_image, 结束帧/end_image, 局部重绘参考, 动作重导向, or targeted asset-reference-aware frames. Do not use this as a mandatory step before first-pass video generation.
---

# Keyframe Prompt

## Purpose

Use this skill to create repair images after a generated video has a concrete problem. Each repair image must have a clear role: 修复起始帧, 修复结束帧, 局部重绘参考, 动作重导向参考, 资产参考图, or 审核帧. This skill follows `text-to-image-prompt` principles: use visible evidence, concrete space, subjects, actions, objects, expressions, and composition instead of abstract mood words.

## Required references

Read these references before producing keyframe prompt output:

- `references/output-schema.md` for keyframe prompt data shape.
- `references/frame-role-rules.md` for role-specific prompt rules and model-submission behavior.
- `references/golden-1-1-keyframes.md` as a representative calibration sample for `1-1.md` shots.

## Workflow

1. Load video QA / user feedback and shot-director output.
   - Identify the exact failure: face drift, scene mismatch, prop orientation, action wrong, camera wrong, bad body mechanics, missing speed, wrong ending, etc.
   - Preserve `shot_id`, `source_beats`, `shot_type`, `visible_action`, `duration_sec`, `keyframe_plan`, and user labels.
   - Do not change shot order or story content.

2. Resolve frame roles.
   - `start_image` becomes 修复起始帧 only when the first frame must be locked.
   - `end_image` becomes 修复结束帧 only when the final state/hook must be locked and backend support exists.
   - `guide_reference` / 动作重导向参考 is used when the clip acted wrong but does not need a new first frame.
   - `asset_reference` points to existing assets; do not generate as a shot keyframe unless missing and explicitly requested.
   - `review_frame` is for human/module review and may not be submitted to video generation.

3. Inherit context.
   - Use project visual style when available.
   - Use character, scene, and prop asset descriptions when available.
   - Do not invent a new style when absent; mark style as inherited/unspecified.

4. Write role-aware repair image prompts.
   - Start frames should show the action about to begin or the first stable state.
   - Guide references should show the desired action result, emotion, pose, or comedy landing.
   - End frames should show the exact final state when supported.
   - Review frames should be clear for user approval, not necessarily generation-ready.

5. Add UI labels and submission behavior.
   - The user must see which image is 修复起始帧, 修复结束帧, or 动作重导向参考.
   - Do not label all frame images as “参考图”.
   - Include `submit_as` for every frame.

6. Self-check.
   - Every prompt must be static-image-safe.
   - Avoid writing video motion instructions such as “then”, “after that”, or multi-step action sequences.
   - Avoid final video prompt wording.
   - Ensure repair images address the observed failure instead of re-generating broad generic keyframes.

## Boundaries

Do not:

- Write final video prompts.
- Decide final reference image packing.
- Design gameplay mechanics.
- Generate asset sheets unless explicitly asked.
- Change keyframe roles from shot-director unless the role is impossible.

Do:

- Compile clean image prompts for each required keyframe.
- Explain frame role to users.
- Include asset references by name and purpose.
- Leave notes for video-prompt on how guide/end frames should be used.
