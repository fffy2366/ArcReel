---
name: video-prompt
description: Compile shot-director shots, optional 9-grid motion-guide images, and asset references into role-aware video generation prompts. Use after shot-director when Codex needs to build director-grade video prompts of at least 5 seconds with detailed action paths, camera blocking, cinematic language, micro-performance, reference-pack behavior, and optional repair-frame fallbacks.
---

# Video Prompt

## Purpose

Use this skill to turn a shot module into a video-generation unit. It consumes shot timing, motion-guide references, and asset/reference information, then outputs model-facing video prompts and clear user-facing submission behavior.

This skill specializes the PlayAsLife story pipeline: first-pass video generation should be possible directly from director shots plus references. Start/end keyframes are repair tools, not mandatory prerequisites.

## Required references

Read these references before producing video prompt output:

- `references/output-schema.md` for video unit and model input shape.
- `references/video-rules.md` for timing, frame-role handling, continuity, and fallback rules.
- `references/golden-1-1-videos.md` as representative calibration examples.

## Workflow

1. Load shot modules and optional motion-guide modules.
   - Preserve `shot_id`, `duration_sec`, `visible_action`, `action_timeline`, performance, camera, emotional rhythm, motion-guide roles, and asset references.
   - Keep user-facing image labels intact.

2. Resolve model input behavior.
   - `motion_guide_grid` / `guide_reference` guides action direction, pose rhythm, and camera movement; use as reference if supported, otherwise convert to prompt guidance.
   - `asset_reference` images lock character, scene, prop, and style consistency.
   - `start_image` and `end_image` are used mainly in revision/repair passes, or when the user explicitly locks first/last frames.
   - `review_frame` is not submitted by default.

3. Write a controlled video prompt.
   - One clip, one main action.
   - Real submitted video duration is never below 5 seconds.
   - Critical action occurs in the first 70%; final 30% is hold/reaction/aftertaste.
   - Lock identity, clothing, scene layout, props, and style inherited from assets and references.
   - Only write filmable content: visible subjects, action, performance, props, environment, light, camera, continuity, and ending state.
   - Must include director-grade sections: `镜头语言`, `镜头调度`, `运镜设计`, `剪辑策略`, `细节表演`.
   - `运镜设计` must describe where the camera starts and ends, where the subject moves, how focus shifts, how speed changes, and where the final hold lands.
   - `细节表演` must describe eyebrows, eyeline, mouth/jaw, breath, shoulders/neck, hands/fingers, and weight shift when a person is present.
   - `剪辑策略` must choose continuous shot, action match, whip pan, foreground wipe, montage, or reaction hold according to story need. Do not decorate prompts with montage, dolly zoom, or Hitchcock zoom unless the shot genuinely needs psychological rupture, time compression, or a reveal.
   - Never copy script-document metadata into the model-facing prompt. Forbidden examples: episode/project title, "第3集", "最终剧本", "完整剧本", "125秒加长版", "分镜1", "约0-8s", Markdown heading, file name, or "最终版" label.
   - If upstream text is `第3集《...》最终剧本 分镜1（约0-8s）｜特写至近景｜第一人称视角＋窗户渐显`, keep `特写至近景｜第一人称视角＋窗户渐显` and discard the document header.

4. Add negative constraints.
   - Prevent face drift, outfit change, scene jump, extra limbs, chaotic camera, random zoom, subtitles/text, watermark, and action overrun.
   - Keep negative constraints concise.

5. Mark UI submission summary.
   - Show exactly which image is submitted as motion guide, asset reference, start/end repair frame, or not submitted.
   - Include one summary row for every non-null `model_inputs` image role.
   - Do not call all images “参考图”.

6. Self-check.
   - The prompt must not contain multiple story events.
   - It must not rely on model inference for important action timing; write the action timing into the prompt.
   - It must not put the key action in the last seconds.
   - It must not collapse camera direction into a vague phrase like `镜头运动：轻微推进/跟拍`.
   - It must not output internal labels such as `原文依据` or `内容依据原文呈现` into image/video model-facing prompts.
   - It must not submit review-only frames unless explicitly requested.
   - `起始状态` must be the first visible frame, not a story title, episode title, script heading, or document summary.
   - The final prompt must not contain "最终剧本", "加长版", "分镜1", "约0-8s", or equivalent document bookkeeping.

## Boundaries

Do not:

- Generate or edit images.
- Design gameplay mechanics.
- Change shot order or story meaning.
- Decide final asset reference pack limits unless asked.
- Write long multi-shot prompts in one video unit.
- Put script-document metadata, source headings, episode labels, or editing bookkeeping into the video model prompt.

Do:

- Compile one shot into one video unit.
- Convert motion-guide, asset, and optional repair frames into model-appropriate input behavior.
- Write precise action timing.
- Write director-level camera language, blocking, movement path, editing strategy, and micro-performance.
- Preserve continuity from keyframes and asset references.
