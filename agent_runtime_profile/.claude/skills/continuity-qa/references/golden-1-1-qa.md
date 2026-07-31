# Golden Sample: `1-1.md` Representative Continuity QA

Purpose: representative examples for diagnosing generated video problems and mapping them to the correct repair layer.

## E1S35 淡金火焰能力泄露：脸漂移 + 火焰过大

```json
{
  "source_video_unit_id": "E1S35_V01",
  "shot_id": "E1S35",
  "qa_status": "major_repair",
  "confidence": "medium",
  "observations": [
    {
      "category": "identity_face",
      "severity": "major",
      "evidence": "用户反馈林小满不像，3s 后近景脸型明显变化",
      "expected": "林小满保持资产图身份，表情从羞恼转为震惊",
      "observed": "五官漂移，表情变成陌生女修的惊讶",
      "likely_cause": "未提交林小满面部特写，或参考包里身份锁定不够",
      "recommended_fix": "add_character_face_closeup"
    },
    {
      "category": "effect_shape_color",
      "severity": "major",
      "evidence": "淡金火焰扩成大火团",
      "expected": "指尖一缕极淡淡金火焰，只是能力泄露",
      "observed": "火焰像攻击特效，破坏低调泄露感",
      "likely_cause": "视频提示词对火焰规模约束不够",
      "recommended_fix": "tighten_effect_prompt"
    }
  ],
  "repair_plan": {
    "primary_action": "update_reference_pack_and_regenerate",
    "why": "身份和能力泄露都是本镜头核心，不能接受直接过片",
    "reference_pack_changes": [
      "must_include: 林小满_face_closeup",
      "must_include: 男主_face_closeup if slots remain",
      "keep: E1S35_KF_START",
      "keep: E1S35_KF_GUIDE"
    ],
    "video_prompt_changes": [
      "把“大火/火团/爆燃”改成“指尖一缕极淡淡金火焰，一闪即逝”",
      "新增负面：不要大火球，不要爆炸，不要攻击特效"
    ],
    "keyframe_changes": [],
    "shot_changes": [],
    "regeneration_scope": "same_video_unit"
  },
  "next_generation_settings": {
    "duration_sec": 5,
    "pack_mode": "revision_repair",
    "must_include_images": ["E1S35_KF_START", "E1S35_KF_GUIDE", "林小满_face_closeup"],
    "must_exclude_images": [],
    "prompt_constraints": ["淡金火焰只能是一缕，不要变成大火球"]
  },
  "ui_summary": "建议重生同一镜头：先补林小满面部特写，再把淡金火焰约束成极淡一缕。"
}
```

## E1S11 灵符没反应：模型自己爆炸了

```json
{
  "source_video_unit_id": "E1S11_V01",
  "shot_id": "E1S11",
  "qa_status": "regenerate_same_clip",
  "confidence": "medium",
  "observations": [
    {
      "category": "action_result",
      "severity": "blocker",
      "evidence": "灵符贴上藤蔓后发生爆炸",
      "expected": "灵符贴住藤蔓但毫无反应，形成喜剧停顿",
      "observed": "爆炸让男主像成功施法，反转笑点消失",
      "likely_cause": "模型按常见符咒逻辑补完了爆炸结果",
      "recommended_fix": "rewrite_video_prompt_and_negative"
    }
  ],
  "repair_plan": {
    "primary_action": "rewrite_video_prompt_and_regenerate",
    "why": "动作结果和戏剧功能完全相反",
    "reference_pack_changes": [
      "keep: E1S11_KF_START",
      "include_if_supported: E1S11_KF_GUIDE"
    ],
    "video_prompt_changes": [
      "强调灵符贴住后没有任何反应",
      "把最后1秒写成男主脸色僵住、藤蔓继续逼近",
      "负面加入：不要爆炸，不要藤蔓缩回，不要成功施法"
    ],
    "keyframe_changes": [],
    "shot_changes": [],
    "regeneration_scope": "same_video_unit"
  },
  "next_generation_settings": {
    "duration_sec": 3,
    "pack_mode": "revision_repair",
    "must_include_images": ["E1S11_KF_START", "E1S11_KF_GUIDE"],
    "must_exclude_images": [],
    "prompt_constraints": ["灵符必须失败，不能爆炸，喜剧停顿要保留"]
  },
  "ui_summary": "建议重生同一镜头：这是动作结果错误，不是脸或场景问题，主要改视频提示词。"
}
```

## E1S32 进入游戏：误生成剧情视频

```json
{
  "source_video_unit_id": "E1S32_V01",
  "shot_id": "E1S32",
  "qa_status": "review_only_no_generation",
  "confidence": "high",
  "observations": [
    {
      "category": "gameplay_marker_error",
      "severity": "blocker",
      "evidence": "玩法入口标记被派发成视频生成任务",
      "expected": "进入游戏：摆筋脉 应作为分镜结尾和 UI 审核帧，不生成剧情视频",
      "observed": "系统尝试生成玩法入口剧情视频",
      "likely_cause": "video-prompt 或 reference-pack 执行层未识别 review_only_no_generation",
      "recommended_fix": "mark_review_only"
    }
  ],
  "repair_plan": {
    "primary_action": "mark_review_only",
    "why": "这是流程边界错误，不是视频质量问题",
    "reference_pack_changes": ["selected_images: []", "review_frame only"],
    "video_prompt_changes": ["model_mode: review_only_no_generation"],
    "keyframe_changes": [],
    "shot_changes": [],
    "regeneration_scope": "none"
  },
  "next_generation_settings": {
    "duration_sec": 0,
    "pack_mode": "review_only",
    "must_include_images": [],
    "must_exclude_images": ["E1S32_KF_REVIEW from video backend"],
    "prompt_constraints": []
  },
  "ui_summary": "不要重生。这条是玩法入口审核帧，应该阻止派单。"
}
```

## Evaluation checks

Candidate QA output should:

1. Name the visible or reported failure.
2. Map it to the right upstream layer.
3. Avoid solving timing problems by blindly adding references.
4. Use `review_only_no_generation` for gameplay markers.
5. State whether to accept, repair, regenerate, remake keyframe, or split shot.
6. Provide exact next-generation constraints.
