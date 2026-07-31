# Story Beat Output Schema

## Top-level shape

Return a JSON-like structure plus a short human-readable summary when useful.

```json
{
  "content_format": "interactive_drama_game",
  "source_id": "episode_1",
  "granularity": "normal",
  "assumptions": [],
  "beats": []
}
```

## Content format enum

Use one of:

- `ad`
- `interactive_drama_game`
- `narrative_video`
- `narrated_drama`

## Granularity enum

- `coarse`: large chapter/episode beats.
- `normal`: production-ready beat breakdown.
- `detailed`: key-scene beat breakdown.

## Granularity selection rules

Use `normal` for broad production planning. Switch to `detailed` when a passage contains screen moments that need their own 2-3 seconds to be felt.

Prefer `detailed` for:

- Opening hooks.
- Chase, delivery, escape, combat, or obstacle sequences.
- Near misses that express danger.
- Comedy timing, failed props, pauses, reversals, or reaction beats.
- Romance proximity, hesitation, breath, gaze, touch, or embarrassment.
- Gameplay/tutorial entry.
- Identity reveal, ability leak, or cliffhanger setup.

In `detailed` mode, a beat may be 2-4 seconds if it has distinct screen value. Do not compress a danger route into one generic action beat when the source names multiple obstacles or escalating hazards.

## Beat shape

Each beat must use:

```json
{
  "beat_id": "B01",
  "common": {
    "source_span": "source excerpt or location",
    "one_sentence_summary": "one concise sentence",
    "beat_function": "opening_hook",
    "characters": [],
    "scene_hint": "",
    "props": [],
    "visible_action": "",
    "emotion_before": "",
    "emotion_after": "",
    "state_change": "",
    "visual_potential": [],
    "target_duration_sec": 6,
    "requires_split": false,
    "suggested_shot_count": 1,
    "notes_for_downstream": ""
  },
  "profile": {}
}
```

Optional grouping fields may be used in `detailed` mode:

```json
{
  "beat_id": "B02.3",
  "parent_beat_id": "B02",
  "beat_scale": "micro"
}
```

Use `parent_beat_id` to show that several micro beats belong to one larger dramatic movement.

## Required common fields

Require:

- `source_span`
- `one_sentence_summary`
- `beat_function`
- `visible_action`
- `state_change`
- `target_duration_sec`
- `requires_split`
- `suggested_shot_count`

Allow `characters`, `scene_hint`, `props`, `emotion_before`, `emotion_after`, `visual_potential`, and `notes_for_downstream` to be empty only when the source genuinely does not support them.

## Duration policy

Use beats for story time and shots/clips for generation time.

- Micro beat: 2-4 seconds.
- Normal beat: 6-10 seconds.
- Important beat: 10-20 seconds, usually split.
- Single generated clip default: 4-6 seconds.
- Practical clip upper bound: 8 seconds.
- 15 seconds: hard limit for special slow ambience only, not the normal target.

Mark `requires_split: true` when:

- `target_duration_sec` is greater than 6-8 seconds.
- The beat contains more than one main action.
- The beat contains dialogue exchange, romance escalation, combat, reveal, montage, or branch setup.
- The critical action would otherwise occur late in a long clip.

In `detailed` mode, `requires_split` can be `false` for a 2-4 second micro beat because that micro beat may already be one generated clip.

## Split guidance

When split is required, estimate:

```json
{
  "target_duration_sec": 13,
  "requires_split": true,
  "suggested_shot_count": 3
}
```

Do not design the final shots in this skill. Only indicate the likely count and why in `notes_for_downstream`.

## Validation checklist

Before final output, check:

- Does each beat have a clear function?
- Does each beat include a visible action or visualizable narration point?
- Does each beat include a real state/information/relationship/viewer-promise change?
- Are pure mood paragraphs merged into adjacent beats unless they create new screen value?
- Are camera, lens, lighting, and final prompt details omitted?
- Are long beats marked for splitting?
- Are interactive candidates marked only as candidates unless the user asked for full branch design?
