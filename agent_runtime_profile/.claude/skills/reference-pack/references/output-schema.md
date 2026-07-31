# Reference Pack Output Schema

## Top-level shape

```json
{
  "source_video_unit_id": "E1S35_V01",
  "shot_id": "E1S35",
  "pack_mode": "continuity_sensitive",
  "backend_caps": {},
  "selected_images": [],
  "unselected_candidates": [],
  "prompt_guidance_from_unsubmitted_images": [],
  "ui_submission_summary": [],
  "execution_notes": []
}
```

## Backend caps shape

```json
{
  "backend_name": "agnes-video-v2.0",
  "max_total_images": 9,
  "supports_start_image": true,
  "supports_end_image": false,
  "supports_multi_reference_images": true,
  "requires_public_image_url": true
}
```

If caps are unknown, set unknown fields to `"unknown"` and produce a conservative pack.

## Selected image shape

```json
{
  "slot": 1,
  "image_id": "E1S35_KF_START",
  "source": "keyframe",
  "role": "start_image",
  "user_label": "起始帧",
  "submit_as": "start_image",
  "priority": "P0",
  "purpose": "确定视频第一帧构图、人物站位和场景",
  "public_url_required": true,
  "copy_background": true,
  "notes": ""
}
```

## Role enum

- `start_image`
- `end_image`
- `guide_reference`
- `character_face_closeup`
- `character_turnaround`
- `scene_reference`
- `prop_reference`
- `style_reference`
- `effect_reference`
- `review_frame`

## Priority enum

- `P0`: required for this backend/mode.
- `P1`: high-value consistency or action reference.
- `P2`: useful if slots remain.
- `P3`: usually skip unless fixing a specific problem.

## Unselected candidate shape

```json
{
  "image_id": "林小满_turnaround",
  "role": "character_turnaround",
  "user_label": "资产参考图：三视图",
  "reason": "本镜头是近景表情和手部药力，三视图服装信息优先级低于面部特写和起始帧"
}
```

## UI submission summary shape

```json
[
  {"label": "起始帧", "image_id": "E1S35_KF_START", "submitted": true, "as": "start_image"},
  {"label": "资产参考图：面部特写", "image_id": "林小满_face", "submitted": true, "as": "reference_image"},
  {"label": "审核帧", "image_id": "E1S32_KF_REVIEW", "submitted": false, "as": "review_only"}
]
```

## Required fields

Require:

- `source_video_unit_id`
- `shot_id`
- `pack_mode`
- `backend_caps`
- `selected_images`
- `unselected_candidates`
- `ui_submission_summary`

Use `execution_notes` to pass image-host requirements or uploader needs to later implementation layers.
