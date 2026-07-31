---
name: story-beat
description: Convert novels, scripts, ad copy, or narrated drama text into typed story beats before scene design, storyboard generation, keyframe prompts, or video prompts. Use when Codex needs to choose a content format, split source text into beat-level dramatic/marketing/narration units, identify visible actions, state changes, interaction opportunities, and duration/splitting guidance for PlayAsLife video generation.
---

# Story Beat

## Purpose

Use this skill to turn source text into beat-level structure. A beat is a narrative, marketing, or narration unit that carries a clear change, information point, viewer promise, or interactive setup. It is not a shot, not a keyframe prompt, and not a video prompt.

## Required references

Read these references before producing beat output:

- `references/output-schema.md` for the common beat schema, required fields, duration policy, and validation rules.
- `references/format-profiles.md` for content-format-specific beat functions and profile fields.

Use `references/golden-1-1-detailed.md` as the calibration sample when evaluating detailed beat splitting for mission/gameplay/comedy interactive drama.

## Workflow

1. Determine `content_format`.
   - Use the user-provided value when present.
   - If absent, infer likely candidates from the text and task context.
   - If two formats are plausible, report candidates and continue with the most likely one while flagging the assumption.

2. Select granularity.
   - `coarse`: chapter/episode structure, broad beats.
   - `normal`: default production breakdown.
   - `detailed`: key scene breakdown for openings, cliffhangers, romance, action, reveals, or choices.
   - Prefer `detailed` when the source contains chase/action delivery routes, near misses, comedy timing, tactile danger, delicate emotional beats, gameplay entry, or any moment where 2-3 seconds of screen time carries distinct value.

3. Split the text into beats.
   - Start a new beat when goal, emotion, relationship, information, risk, time/space, choice setup, or hook changes.
   - In `detailed` mode, also start a new beat for a distinct obstacle, dodge, near miss, comic pause, object failure, micro-reaction, or danger texture even if the larger goal remains unchanged.
   - Merge pure atmosphere or repeated description unless it creates a distinct visible action or information point.
   - Preserve traceability with `source_span` or a concise source excerpt.

4. Assign beat function and profile fields.
   - Use `references/format-profiles.md`.
   - Keep the `common` fields stable across all formats.
   - Put format-specific data under `profile`.

5. Convert internal writing into visible cues.
   - Transform psychological prose into observable behavior, facial expression, gesture, reaction, environmental sign, or narration point.
   - Do not leave important beat logic as abstract mood only.

6. Add time guidance.
   - A beat is a story unit, not a video generation unit.
   - Estimate `target_duration_sec`.
   - Mark `requires_split: true` when a beat should become multiple shots/clips.
   - Single generated clips should usually be 4-6 seconds; 15 seconds is a hard upper bound, not a target.

7. Self-check.
   - Ensure every beat has a reason to exist.
   - Ensure required fields are present.
   - Ensure the output does not drift into camera/lens/lighting/keyframe/video prompt writing.

## Boundaries

Do not:

- Write final image prompts or video prompts.
- Decide exact focal length, camera brand, color grading, lighting plan, or detailed shot movement.
- Design the concrete gameplay mechanic when the script already marks an "enter game" segment.
- Split every paragraph mechanically.
- Invent major plot not supported by the source.
- Treat a 15-second video model limit as the normal clip duration.

Do:

- Identify what changed.
- Identify what can be seen.
- Identify whether the beat likely needs multiple shots.
- Mark explicit gameplay-entry lines as the ending hook of the current beat/shot group.
- Identify candidate interaction points for interactive drama/game formats.
- Leave downstream notes for scene choice, performance, shot direction, and prompt compilation.
