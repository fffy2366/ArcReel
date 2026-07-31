# Continuity QA Output Schema

## Top-level shape

```json
{
  "source_video_unit_id": "E1S35_V01",
  "shot_id": "E1S35",
  "qa_status": "major_repair",
  "confidence": "high",
  "observations": [],
  "repair_plan": {},
  "next_generation_settings": {},
  "ui_summary": ""
}
```

## QA status enum

- `pass`
- `minor_repair`
- `major_repair`
- `regenerate_same_clip`
- `regenerate_keyframe_first`
- `split_shot`
- `review_only_no_generation`
- `needs_user_review`

## Confidence enum

- `high`: video or sampled frames were inspected.
- `medium`: partial frames, thumbnail, or strong user report.
- `low`: no visual evidence; diagnosis based only on source data.

## Observation shape

```json
{
  "category": "identity_face",
  "severity": "major",
  "evidence": "2.8s 中景，林小满五官变成陌生脸",
  "expected": "林小满应保持资产图里的外门弟子脸和羞恼表情",
  "observed": "脸型、眼距和发型都漂移",
  "likely_cause": "reference-pack 未提交林小满面部特写，或资产权重不够",
  "recommended_fix": "add_character_face_closeup"
}
```

## Category enum

- `identity_face`
- `hair_clothing_body`
- `scene_layout`
- `prop_design`
- `action_timing`
- `action_result`
- `camera_motion`
- `composition`
- `performance_emotion`
- `lighting_style`
- `effect_shape_color`
- `continuity_prev_next`
- `technical_artifact`
- `text_watermark`
- `white_background_contamination`
- `gameplay_marker_error`

## Severity enum

- `blocker`
- `major`
- `minor`
- `pass`

## Repair plan shape

```json
{
  "primary_action": "update_reference_pack_and_regenerate",
  "why": "脸和药力效果是本镜头核心，必须重试",
  "reference_pack_changes": [],
  "video_prompt_changes": [],
  "keyframe_changes": [],
  "shot_changes": [],
  "regeneration_scope": "same_video_unit"
}
```

## Primary action enum

- `accept`
- `update_reference_pack_and_regenerate`
- `rewrite_video_prompt_and_regenerate`
- `regenerate_keyframe_first`
- `shorten_duration_and_regenerate`
- `split_shot_then_regenerate`
- `mark_review_only`
- `ask_user_decision`

## Next generation settings shape

```json
{
  "duration_sec": 4,
  "pack_mode": "revision_repair",
  "must_include_images": ["林小满_face_closeup"],
  "must_exclude_images": [],
  "prompt_constraints": ["淡金火焰只能是一缕，不要变成大火球"]
}
```

## Required fields

Require:

- `source_video_unit_id`
- `shot_id`
- `qa_status`
- `confidence`
- `observations`
- `repair_plan`
- `ui_summary`
