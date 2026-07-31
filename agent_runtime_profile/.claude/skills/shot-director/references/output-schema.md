# Shot Director Output Schema

## Top-level shape

```json
{
  "source_id": "1-1",
  "content_format": "interactive_drama_game",
  "subtype": "mission_gameplay_comedy",
  "target_runtime_sec": 110,
  "estimated_total_duration_sec": 112,
  "shot_groups": []
}
```

## Shot group shape

```json
{
  "shot_group_id": "SG03",
  "source_parent_beat": "G03",
  "group_function": "route_danger_comedy",
  "group_purpose": "藤妖封路与受潮灵符形成危险+笑点的小段落",
  "boundary_type": "normal",
  "estimated_duration_sec": 12,
  "shots": []
}
```

`boundary_type` values:

- `normal`
- `gameplay_entry_end`
- `return_to_story_start`
- `cliffhanger_end`
- `montage`

## Shot shape

```json
{
  "shot_id": "E1S12",
  "source_beats": ["B03.4"],
  "shot_type": "comedy_pause",
  "shot_purpose": "制造灵符没反应的喜剧停顿，同时保留藤蔓逼近危险",
  "screen_subject": "男主、灵符、藤蔓",
  "characters": ["男主"],
  "scene_hint": "青岚宗外门山道竹林",
  "props": ["低阶灵符"],
  "visible_action": "男主甩出灵符大喊爆，灵符贴上藤蔓却没有反应",
  "duration_sec": 5,
  "clip_boundary": "single_action",
  "ending_state": "男主脸色僵住，藤蔓仍在逼近",
  "cinematic_language": "用手部插入特写和中近景反应形成喜剧反差，观众先期待爆炸，再被表情停顿接住。",
  "camera_blocking": "灵符位于前景，藤蔓从背景压近，男主在中景偏侧，脸、手和逼近危险同时可读。",
  "movement_design": "镜头从男主甩符的手部开始，跟随灵符飞到藤蔓贴符点，焦点从符纸转回男主眼睛，速度先跟随动作变快，符纸失效后减速停在僵住表情。",
  "editing_strategy": "单镜连续或动作顺切，不用装饰性蒙太奇；结尾保留反应 hold 接下一镜。",
  "transition_plan": "下一镜可沿藤蔓逼近方向顺切到危险升级，或沿男主眼神切到补救动作。",
  "micro_performance": "男主眉毛先扬后压，眼神从期待变空，嘴角僵住，下颌收紧，手指还保持掐诀姿势，肩颈微僵。",
  "action_timeline": [
    {"time": "0-1.5s", "action": "灵符飞向藤蔓"},
    {"time": "1.5-3.5s", "action": "灵符贴住藤蔓但没有反应"},
    {"time": "3.5-5s", "action": "男主脸色僵住，藤蔓继续逼近，保留反应和呼吸停顿"}
  ],
  "keyframe_plan": {},
  "notes_for_keyframe": "",
  "notes_for_video": "",
  "ui_module_notes": ""
}
```

## Shot type enum

- `establishing`
- `mission_info`
- `action_motion`
- `evasive_action`
- `near_miss`
- `comedy_pause`
- `comedy_action`
- `reaction`
- `insert`
- `reveal`
- `ability_leak`
- `gameplay_entry`
- `return_to_story`
- `cliffhanger`
- `transition`

## Keyframe plan shape

```json
{
  "strategy": "start_and_guide",
  "frames": [
    {
      "role": "start_image",
      "user_label": "起始帧",
      "frame_moment": "男主甩出灵符，藤蔓逼近",
      "submit_as": "start_image",
      "required": true,
      "purpose_for_user": "视频从这一帧开始"
    },
    {
      "role": "guide_reference",
      "user_label": "引导参考图",
      "frame_moment": "灵符贴在藤蔓上没反应，男主脸色僵住",
      "submit_as": "reference_image_or_prompt_guidance",
      "required": false,
      "purpose_for_user": "指导视频往这个动作结果发展"
    }
  ],
  "asset_references": [
    {
      "role": "asset_reference",
      "user_label": "资产参考图",
      "asset_type": "character",
      "name": "男主",
      "submit_as": "reference_image",
      "required": false
    }
  ]
}
```

## Keyframe strategy enum

- `start_only`: use only a start image.
- `start_and_guide`: start image plus a guide reference for action direction, emotion, or comedy landing.
- `start_and_end`: start image plus end image when the model supports first/last frame generation.
- `end_hook`: primarily define a final hook frame; useful for cliffhangers.
- `review_only`: generate image only for human review, not model submission.

## Frame role enum

- `start_image`: 起始帧；video starts here.
- `guide_reference`: 引导参考图；guides where motion/emotion should develop.
- `end_image`: 结束帧；video ends here when supported.
- `asset_reference`: 资产参考图；locks character/scene/prop/style consistency.
- `review_frame`: 审核帧；shown to user only.

## Submission role enum

- `start_image`
- `end_image`
- `reference_image`
- `prompt_guidance`
- `reference_image_or_prompt_guidance`
- `review_only`
