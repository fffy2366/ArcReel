# Golden Sample: `1-1.md` Representative Reference Packs

Sources:

- Video sample: `agent_runtime_profile/.claude/skills/video-prompt/references/golden-1-1-videos.md`
- Keyframe sample: `agent_runtime_profile/.claude/skills/keyframe-prompt/references/golden-1-1-keyframes.md`

Purpose: representative examples for selecting role-aware image inputs for video generation.

## E1S35 淡金火焰能力泄露

Assumption: backend accepts up to 9 total images, supports start image and multiple reference images, does not support true end frame, and requires public image URLs.

```json
{
  "source_video_unit_id": "E1S35_V01",
  "shot_id": "E1S35",
  "pack_mode": "continuity_sensitive",
  "backend_caps": {
    "backend_name": "agnes-video-v2.0",
    "max_total_images": 9,
    "supports_start_image": true,
    "supports_end_image": false,
    "supports_multi_reference_images": true,
    "requires_public_image_url": true
  },
  "selected_images": [
    {
      "slot": 1,
      "image_id": "E1S35_KF_START",
      "source": "keyframe",
      "role": "start_image",
      "user_label": "起始帧",
      "submit_as": "start_image",
      "priority": "P0",
      "purpose": "确定调息起始构图、两人站位和校场环境",
      "public_url_required": true,
      "copy_background": true
    },
    {
      "slot": 2,
      "image_id": "E1S35_KF_GUIDE",
      "source": "keyframe",
      "role": "guide_reference",
      "user_label": "引导参考图",
      "submit_as": "reference_image",
      "priority": "P1",
      "purpose": "引导淡金火焰牵住青白药力后的动作结果",
      "public_url_required": true,
      "copy_background": false
    },
    {
      "slot": 3,
      "image_id": "男主_face_closeup",
      "source": "asset",
      "role": "character_face_closeup",
      "user_label": "资产参考图：男主面部特写",
      "submit_as": "reference_image",
      "priority": "P1",
      "purpose": "锁定男主脸、发型和年轻外卖员气质",
      "public_url_required": true,
      "copy_background": false
    },
    {
      "slot": 4,
      "image_id": "林小满_face_closeup",
      "source": "asset",
      "role": "character_face_closeup",
      "user_label": "资产参考图：林小满面部特写",
      "submit_as": "reference_image",
      "priority": "P1",
      "purpose": "锁定林小满的羞恼、震惊表情和面部身份",
      "public_url_required": true,
      "copy_background": false
    },
    {
      "slot": 5,
      "image_id": "林小满_turnaround",
      "source": "asset",
      "role": "character_turnaround",
      "user_label": "资产参考图：林小满三视图",
      "submit_as": "reference_image",
      "priority": "P2",
      "purpose": "锁定外门弟子服装和体态，避免调息姿势中服装漂移",
      "public_url_required": true,
      "copy_background": false
    }
  ],
  "unselected_candidates": [
    {
      "image_id": "男主_turnaround",
      "role": "character_turnaround",
      "user_label": "资产参考图：男主三视图",
      "reason": "本镜头男主以近景手部和表情为主，面部特写加起始帧已经足够"
    },
    {
      "image_id": "校场_scene",
      "role": "scene_reference",
      "user_label": "资产参考图：校场场景",
      "reason": "起始帧已经锁定校场环境，优先给角色和药力效果"
    }
  ],
  "prompt_guidance_from_unsubmitted_images": [
    "白底角色资产仅用于锁定脸、发型、服装和体型，不继承白色背景；剧情场景以起始帧为准。"
  ],
  "ui_submission_summary": [
    {"label": "起始帧", "image_id": "E1S35_KF_START", "submitted": true, "as": "start_image"},
    {"label": "引导参考图", "image_id": "E1S35_KF_GUIDE", "submitted": true, "as": "reference_image"},
    {"label": "资产参考图：男主面部特写", "image_id": "男主_face_closeup", "submitted": true, "as": "reference_image"},
    {"label": "资产参考图：林小满面部特写", "image_id": "林小满_face_closeup", "submitted": true, "as": "reference_image"},
    {"label": "资产参考图：林小满三视图", "image_id": "林小满_turnaround", "submitted": true, "as": "reference_image"}
  ],
  "execution_notes": [
    "所选5张图都需要先上传到公网图床，再把公网URL交给视频后端。"
  ]
}
```

## E1S32 进入游戏：摆筋脉

```json
{
  "source_video_unit_id": "E1S32_V01",
  "shot_id": "E1S32",
  "pack_mode": "review_only",
  "backend_caps": {
    "backend_name": "any",
    "max_total_images": 9,
    "supports_start_image": "unknown",
    "supports_end_image": "unknown",
    "supports_multi_reference_images": "unknown",
    "requires_public_image_url": "unknown"
  },
  "selected_images": [],
  "unselected_candidates": [],
  "prompt_guidance_from_unsubmitted_images": [],
  "ui_submission_summary": [
    {"label": "审核帧", "image_id": "E1S32_KF_REVIEW", "submitted": false, "as": "review_only"}
  ],
  "execution_notes": [
    "玩法入口标记不生成剧情视频，审核帧仅用于分镜模块显示和用户确认。"
  ]
}
```

## Evaluation checks

Candidate reference pack output should:

1. Keep 起始帧, 引导参考图, 结束帧, 审核帧, and 资产参考图 labels clear.
2. Stay under backend max image count.
3. Prefer fewer images on first pass.
4. Explain skipped candidates.
5. Mark public URL requirements without pretending upload has already happened.
6. Avoid submitting review-only gameplay frames.
7. Warn that white-background asset sheets must not replace the story scene.
