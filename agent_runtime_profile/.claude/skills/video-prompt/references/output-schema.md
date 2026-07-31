# Video Prompt Output Schema

## Top-level shape

```json
{
  "source_id": "1-1",
  "video_units": []
}
```

## Video unit shape

```json
{
  "video_unit_id": "E1S11_V01",
  "shot_id": "E1S11",
  "duration_sec": 5,
  "model_mode": "image_to_video_start_plus_refs",
  "model_inputs": {},
  "video_prompt_zh": "",
  "video_prompt_en": "",
  "negative_prompt": "",
  "action_timeline": [],
  "continuity_locks": [],
  "ui_submission_summary": [],
  "notes_for_generation": ""
}
```

## Model mode enum

- `image_to_video_start_only`
- `image_to_video_start_plus_refs`
- `image_to_video_start_end`
- `text_to_video`
- `review_only_no_generation`

## Model inputs shape

```json
{
  "start_image": {
    "frame_id": "E1S11_KF_START",
    "user_label": "起始帧",
    "required": true
  },
  "guide_references": [
    {
      "frame_id": "E1S11_KF_GUIDE",
      "user_label": "引导参考图",
      "submit_as": "reference_image_or_prompt_guidance",
      "behavior": "use_as_reference_if_supported_else_prompt_guidance"
    }
  ],
  "end_image": null,
  "asset_references": [
    {
      "asset_type": "character",
      "name": "男主",
      "user_label": "资产参考图",
      "required": false
    }
  ],
  "review_frames": []
}
```

## Action timeline shape

```json
[
  {"time": "0-2s", "action": "灵符飞向藤蔓"},
  {"time": "2-3.5s", "action": "灵符贴住藤蔓但没有反应"},
  {"time": "3.5-5s", "action": "男主脸色僵住，藤蔓继续逼近，保留反应和呼吸停顿"}
]
```

## Required director content in `video_prompt_zh`

`video_prompt_zh` must include these model-facing sections, with filmable content only:

- `起始状态`: first visible frame, never a script title or episode header.
- `动作发展`: what physically changes during this clip.
- `动作节奏`: time allocation; key action in first 70%, final 30% for hold/reaction/after-motion.
- `结束状态`: the exact image/emotional state to hold at the end.
- `镜头语言`: framing/angle purpose and viewer attention path.
- `镜头调度`: character/prop/environment blocking and spatial relationship.
- `运镜设计`: camera start/end, subject path, focus shift, speed change, final hold.
- `剪辑策略`: continuous shot/action match/whip pan/foreground wipe/montage/reaction hold as needed.
- `演员表演`: main visible performance.
- `细节表演`: eyebrows, eyeline, mouth/jaw, breath, shoulders/neck, hands/fingers, body weight.
- `灯光氛围`: light source, color, contrast, atmospheric motion.

Do not include internal production notes such as `原文依据`, source file names, episode labels, Markdown headings, or script bookkeeping in `video_prompt_zh`.

## UI submission summary

For user clarity, output:

```json
[
  {"label": "起始帧", "frame_id": "E1S11_KF_START", "submitted": true, "as": "start_image"},
  {"label": "引导参考图", "frame_id": "E1S11_KF_GUIDE", "submitted": "depends_on_model", "as": "reference_or_prompt_guidance"},
  {"label": "审核帧", "frame_id": "E1S32_KF_REVIEW", "submitted": false, "as": "review_only"}
]
```

If `model_inputs.start_image`, `model_inputs.end_image`, `model_inputs.guide_references`, `model_inputs.asset_references`, or `model_inputs.review_frames` is non-empty, include a matching row here. This field is the user-facing explanation of what will be submitted, conditionally submitted, or kept for review only.

## Required output fields

Require:

- `video_unit_id`
- `shot_id`
- `duration_sec`
- `model_mode`
- `model_inputs`
- `video_prompt_zh`
- `negative_prompt`
- `action_timeline`
- `continuity_locks`
- `ui_submission_summary`

`video_prompt_en` is optional.
