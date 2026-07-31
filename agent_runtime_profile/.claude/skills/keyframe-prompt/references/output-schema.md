# Keyframe Prompt Output Schema

## Top-level shape

```json
{
  "source_id": "1-1",
  "shot_source": "golden-1-1-shots",
  "project_style": "inherited_or_unspecified",
  "keyframe_modules": []
}
```

## Keyframe module shape

One module maps to one shot and should appear inside the same分镜模块 in the UI.

```json
{
  "shot_id": "E1S11",
  "shot_type": "comedy_pause",
  "shot_purpose": "制造灵符没反应的喜剧停顿",
  "duration_sec": 3,
  "source_beats": ["B03.4"],
  "frames": [],
  "asset_references": [],
  "notes_for_video_prompt": ""
}
```

## Frame shape

```json
{
  "frame_id": "E1S11_KF_START",
  "role": "start_image",
  "user_label": "起始帧",
  "submit_as": "start_image",
  "required": true,
  "frame_moment": "男主甩出灵符，藤蔓逼近",
  "image_prompt_zh": "",
  "image_prompt_en": "",
  "negative_prompt": "",
  "purpose_for_user": "视频从这一帧开始",
  "continuity_notes": "",
  "asset_reference_notes": ""
}
```

## Frame role enum

- `start_image`: 起始帧；video starts here.
- `guide_reference`: 引导参考图；guides desired direction/result.
- `end_image`: 结束帧；used only when the model supports end frames.
- `review_frame`: 审核帧；user review only.

Asset references are not generated shot keyframes by default. Represent them under `asset_references`.

## Submit-as enum

- `start_image`
- `end_image`
- `reference_image`
- `prompt_guidance`
- `reference_image_or_prompt_guidance`
- `review_only`

## Asset reference shape

```json
{
  "asset_type": "character",
  "name": "男主",
  "user_label": "资产参考图",
  "submit_as": "reference_image",
  "needed_for": "锁定男主脸、发型、服装、外卖储物袋",
  "required": false
}
```

## Prompt fields

`image_prompt_zh` should be directly usable for Chinese prompt workflows.

`image_prompt_en` is optional but recommended for models that perform better with English.

`negative_prompt` should stay minimal and role-specific. Prefer positive desired descriptions over long negative lists.

