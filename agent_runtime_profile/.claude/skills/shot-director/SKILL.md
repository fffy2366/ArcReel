---
name: shot-director
description: Convert story-beat output into production-ready shot groups and video-generation shots/clips of at least 5 seconds. Use after story-beat and before 9-grid motion-guide image prompts and video prompts when Codex needs to define shot purpose, duration, boundaries, screen subject, action timeline, performance, camera position, camera movement, emotional rhythm, director-level film language, and optional repair-frame needs.
---

# Shot Director

## Purpose

Use this skill to transform story beats into shot groups and shots. A shot is a controllable video-generation unit, never below 5 seconds for real generation, with one main visible action and a clear ending state. This skill does not write final image prompts or video prompts.

The director must behave like a real film/animation director, not a plot summarizer. Each shot should explain how the camera, actors, space, action, edit, and emotion work together.

## Required references

Read these references before producing shot output:

- `references/output-schema.md` for shot group, shot, keyframe, and UI-label schema.
- `references/directing-rules.md` for merge/split, timing, gameplay boundary, and keyframe-role rules.
- `references/golden-1-1-shots.md` as the calibration sample when converting the `story-beat` golden sample for `1-1.md`.

## Workflow

1. Load upstream story beats.
   - Preserve `source_id`, `content_format`, `subtype`, parent beat IDs, micro beat IDs, visible actions, durations, and explicit boundaries.
   - Do not alter story meaning from upstream beats.

2. Create shot groups.
   - Usually one shot group maps to one parent beat.
   - Split groups at hard boundaries such as explicit gameplay entry and return-to-story markers.
   - A shot group is a user-visible分镜模块 cluster, not necessarily one video clip.

3. Create shots/clips.
   - Real generated shot duration must be at least 5 seconds.
   - Inserts, reactions, and comedy pauses may have a 2-3 second action core, but still produce a 5+ second shot by adding reaction, hold, breath, environmental after-motion, or emotional aftertaste.
   - Use 7-8 seconds only when one continuous action genuinely needs it.
   - Avoid 15 seconds except for slow ambience or special cases.

4. Merge compatible micro beats.
   - Merge only when subject, space, action direction, and emotional state are continuous.
   - Do not merge independent danger, comedy pause, prop failure, reveal, reaction, gameplay boundary, or cliffhanger beats.

5. Define visual-control notes.
   - First-pass visual control is a `guide_reference` 9-grid motion guide: a rough storyboard sheet showing how the shot performs.
   - Start/end keyframes are repair controls, not mandatory first-pass inputs.
   - Mark whether this shot may later need `repair_start_image`, `repair_end_image`, or `motion_guide_grid`.

6. Add director-level film language.
   - `cinematic_language`: why this framing exists and how it expresses tension, intimacy, comedy, reveal, speed, pressure, or hook.
   - `camera_blocking`: where the actor, prop, foreground, midground, background, and camera sit in space.
   - `movement_design`: the exact motion path: subject moves from where to where, camera moves from where to where, focus shifts from what to what, speed changes how.
   - `editing_strategy`: select the correct editing language, not a decorative term. Choose from single continuous shot, action match cut, foreground wipe, whip pan, reaction hold, or a specific montage type. Use Hitchcock/dolly zoom only for shock, realization, or spatial disorientation.
   - `transition_plan`: how this shot connects to the previous/next shot through action direction, eyeline, prop, sound, light, or emotional beat.
   - `micro_performance`: continuous tiny acting beats — eyebrows, eyelids, pupils/eyeline, nose/cheek tension, mouth corners, jaw, breath, shoulders, hands, fingers, weight shift.

7. Choose montage type deliberately when needed.
   - 时间压缩蒙太奇: travel, training, refining, searching, repeated effort, long process compressed into seconds.
   - 平行蒙太奇: two places/actions happen simultaneously without direct collision yet.
   - 交叉蒙太奇: two simultaneous lines are converging into danger, rescue, collision, or reveal.
   - 省略蒙太奇: skip an obvious process and preserve only setup/result.
   - 心理/回忆蒙太奇: memory fragments, inner fear, guilt, fantasy, decision pressure.
   - 隐喻/象征蒙太奇: use objects, weather, light, cracks, flowers, clocks, talismans, or recurring motifs to express fate or theme.
   - 对比蒙太奇: expose class/status/emotional contrast by cutting between opposing images.
   - 预兆蒙太奇: brief future danger, hidden observer, omen, power awakening, or unresolved hook.
   - 加速节奏蒙太奇: chase, countdown, fight escalation, panic, deadline pressure.
   - 减速蒙太奇: grief, aftershock, romance pause, shame, emotional sinking, quiet realization.
   - 冲击蒙太奇: very short high-impact inserts for rupture, attack impact, thunder, blade flash, eye close-up; use sparingly.
   - If no above condition is present, do not use montage; use single continuous shot, action match, or reaction hold.

8. Choose camera style and movement combinations deliberately.
   - Nolan-like cold spatial pressure: fate, system, time, maze, judgment, giant structure, rational pressure; use axial push, symmetrical depth, low controlled track, scale contrast.
   - Spielberg-like wonder/reveal: first sight, miracle, giant creature/building, emotional discovery; show character reaction/eyeline first, then reveal the spectacle through push-in, tilt-up, or over-shoulder reveal.
   - Kubrick-like symmetrical pressure: ritual, corridor, institutional power, psychological unease; use central perspective, slow tracking, rigid composition.
   - Hitchcock-like suspense: audience knows danger before the character, voyeurism, hidden threat; use POV, object insert, eyeline mismatch, dolly zoom only for shock/vertigo.
   - Wong Kar-wai-like urban intimacy: rain, neon, alley, cigarette, missed connection, erotic tension; use slow lateral drift, foreground blur, reflective surfaces, close body distance.
   - Kore-eda-like life observation: family, breakfast, room, desk, quiet care, restrained emotion; use static or very slow low camera, natural blocking, action entering frame.
   - Kurosawa-like weather/action blocking: wind, rain, dust, forest, group movement, duel; use strong lateral motion, weather-driven composition, clear action direction.
   - Zhang Yimou-like ritual/color block: palace, ceremony, ranks, banners, red/gold/white symbolic color; use frontal tableau, high/low contrast, group geometry.
   - Ang Lee-like restrained emotion: confession, shame, distance, quiet love, moral choice; use measured push/pull, body distance, hand and eyeline detail.
   - Fincher-like precision/control: investigation, monitor, corporate room, crime, plan, hidden calculation; use mechanical push/pull, locked composition, dark clean layers.
   - Miyazaki-like flight/environment: flying, wind, clouds, forest, creature movement, wonder; use floating follow, wind-reactive clothing/hair, environment breathing.
   - Do not output only a director name. Always translate style into concrete camera path, blocking, focus shift, speed, and final hold.

9. Choose basic movement grammar.
   - 道具揭示: prop close-up → hand/finger detail → eyeline/face.
   - 人物登场: back/side silhouette → partial face → full reveal.
   - 危险逼近: foreground threat → character reaction → escape/impact path.
   - 追逐/飞行: low side-front tracking → background streak → controlled shake → reaction hold.
   - 情绪变化: static/slow push → focus from hands/mouth to eyes → breath hold.
   - 空间揭示: overhead/wide establish → descend/push to subject → lock orientation.
   - 悬念窥视: foreground occlusion/POV → rack focus → hold before reveal.

10. Add action timeline.
   - Keep the primary action in the first 70% of the clip.
   - Use the final 30% for reaction, pause, hold, smoke, debris, breath, or emotional aftertaste.

11. Strip script-document metadata.
   - Never put episode titles, project titles, "最终剧本", "完整剧本", "125秒加长版", "分镜1", "约0-8s", Markdown headings, or file/document labels into `title`, `screen_subject`, `start_state`, `action`, or `video_motion`.
   - If the source text mixes document metadata with filmable content, e.g. `第3集《...》最终剧本 分镜1（约0-8s）｜特写至近景｜第一人称视角＋窗户渐显`, discard the document header and keep only filmable content such as shot size, POV, visible subject, action, environment, light, and camera movement.
   - `start_state` must describe the first visible frame: who/what is visible, where they are, posture, props, environment, and light. It must not summarize the script document.

12. Self-check.
   - Ensure each shot has one main action.
   - Ensure real generation durations are model-realistic and never below 5 seconds.
   - Ensure gameplay entry ends a group and return-to-story starts a new group.
   - Ensure motion-guide / repair-frame roles are explicit for the UI.
   - Ensure no shot field contains script-document metadata that would be useless or harmful to image/video generation.
   - Ensure `camera_movement` is not a bare phrase such as "推近" or "跟拍"; the detailed version must live in `movement_design`.
   - Ensure montage choices name the type and reason, e.g. `交叉蒙太奇：男主赶路与女主遇险两线逼近` rather than `使用蒙太奇`.
   - Ensure style references are translated into executable movement; do not output only `诺兰式运镜` or `斯皮尔伯格式运镜`.

## Boundaries

Do not:

- Write final image prompts or video prompts.
- Decide exact camera brand, lens, aperture, color grade, or detailed lighting plan.
- Design gameplay mechanics.
- Invent new plot beats not present upstream.
- Treat start/end keyframes as mandatory before video generation.
- Copy script headers, episode titles, final-script labels, markdown headings, or timing bookkeeping into filmable shot fields.
- Use film terms as decoration. Montage, dolly zoom, whip pan, match cut, or foreground wipe must serve a visible story/emotion purpose.

Do:

- Define shot purpose, action, duration, ending state, performance, camera position, camera movement, and emotional rhythm.
- Define cinematic language, actor/camera blocking, precise movement path, editing strategy, transition logic, and micro-performance.
- Decide whether a shot should have a 9-grid motion guide and whether later repair may need start/end keyframes.
- Leave useful notes for `text-to-image-prompt`, `video-prompt`, `reference-pack`, and UI rendering.
