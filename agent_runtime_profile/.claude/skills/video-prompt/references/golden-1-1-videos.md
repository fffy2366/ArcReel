# Golden Sample: `1-1.md` Representative Video Prompts

Sources:

- Shot sample: `agent_runtime_profile/.claude/skills/shot-director/references/golden-1-1-shots.md`
- Keyframe sample: `agent_runtime_profile/.claude/skills/keyframe-prompt/references/golden-1-1-keyframes.md`

Purpose: representative examples for converting keyframe roles and shot timing into video prompts.

## E1S07 山魈爪子擦发

```json
{
  "video_unit_id": "E1S07_V01",
  "shot_id": "E1S07",
  "duration_sec": 5,
  "model_mode": "image_to_video_start_plus_refs",
  "model_inputs": {
    "start_image": {"frame_id": "E1S07_KF_START", "user_label": "起始帧"},
    "guide_references": [
      {"frame_id": "E1S07_KF_GUIDE", "user_label": "引导参考图", "behavior": "use_as_reference_if_supported_else_prompt_guidance"}
    ],
    "end_image": null,
    "asset_references": [
      {"asset_type": "character", "name": "男主", "user_label": "资产参考图"},
      {"asset_type": "prop", "name": "破旧飞剑", "user_label": "资产参考图"}
    ]
  },
  "video_prompt_zh": "基于起始帧生成5秒视频。起始状态：男主踩着破旧飞剑贴着竹梢疾驰，侧方竹影里有小山魈扑击前的黑影。动作发展：0-3.5秒，小山魈从侧面横扑，爪子擦着男主头发掠过，男主从直立重心压低到侧身避让，飞剑仍向前冲；3.5-5秒，几缕头发和竹叶被爪风削起，男主刚躲过但还没完全松气。镜头语言：用侧向近景和前景竹叶拖影制造擦身危险。镜头调度：飞剑始终在脚下，山魈爪影从前景斜切，男主脸和肩颈保持可读。运镜设计：镜头从飞剑侧前方同速跟拍开始，冲击点短促甩动并追焦到男主脸侧，最后减速停在惊险反应。剪辑策略：单镜连续呈现，结尾反应停顿接下一镜。细节表演：男主瞳孔一缩，眉头压低，牙关咬住，肩颈瞬间绷紧，手指扣住剑身边缘。保持男主脸、发型、服装、破旧飞剑和竹林山道一致。",
  "negative_prompt": "不要变脸，不要换衣服，不要跳场景，不要攻击命中，不要血腥伤口，不要新增怪物，不要多肢体，不要随机镜头乱晃，不要字幕水印",
  "action_timeline": [
    {"time": "0-1.5s", "action": "山魈从侧面扑近，男主开始侧身"},
    {"time": "1.5-3.5s", "action": "爪子擦着头发掠过，飞剑继续低空前冲"},
    {"time": "3.5-5s", "action": "男主刚躲过，头发被削起一缕，表情惊险地稳住"}
  ],
  "continuity_locks": ["男主身份和服装", "破旧飞剑", "竹林山道", "山魈位置和近身危险"],
  "ui_submission_summary": [
    {"label": "起始帧", "frame_id": "E1S07_KF_START", "submitted": true, "as": "start_image"},
    {"label": "引导参考图", "frame_id": "E1S07_KF_GUIDE", "submitted": "depends_on_model", "as": "reference_or_prompt_guidance"}
  ]
}
```

## E1S11 灵符没反应

```json
{
  "video_unit_id": "E1S11_V01",
  "shot_id": "E1S11",
  "duration_sec": 5,
  "model_mode": "image_to_video_start_plus_refs",
  "model_inputs": {
    "start_image": {"frame_id": "E1S11_KF_START", "user_label": "起始帧"},
    "guide_references": [
      {"frame_id": "E1S11_KF_GUIDE", "user_label": "引导参考图", "behavior": "use_as_reference_if_supported_else_prompt_guidance"}
    ],
    "end_image": null
  },
  "video_prompt_zh": "基于起始帧生成5秒视频。起始状态：藤蔓逼近飞剑后方，男主从腰间甩出皱巴巴低阶灵符。动作发展：0-3.5秒，灵符飞向藤蔓并贴住，男主像刚喊完“爆”一样短暂期待；灵符却潮湿发软、灵光卡顿，没有爆炸。3.5-5秒，藤蔓继续逼近，男主脸色从自信滑向僵住的尴尬和慌张。镜头语言：先给手和灵符的插入特写，再把喜剧反差落到脸。镜头调度：灵符位于前景，藤蔓从背景压近，男主脸和手同时可读。运镜设计：镜头从手部甩符跟到藤蔓贴符点，焦点从符纸转回男主眼睛，最后停在表情僵住。剪辑策略：动作顺切或单镜连续，保留反应停顿。细节表演：眉毛先扬后压，眼神从期待变空，嘴角僵住，下颌收紧，手指还保持掐诀姿势。保持男主、破旧飞剑、藤妖和竹林山道一致。",
  "negative_prompt": "不要立刻爆炸，不要藤蔓缩回，不要换场景，不要新增人物，不要表情镇定，不要字幕文字，不要水印，不要动作过载",
  "action_timeline": [
    {"time": "0-1.5s", "action": "灵符飞向藤蔓"},
    {"time": "1.5-3.5s", "action": "灵符贴住藤蔓但没有爆炸"},
    {"time": "3.5-5s", "action": "男主脸色僵住，藤蔓继续逼近"}
  ],
  "continuity_locks": ["男主", "低阶灵符", "藤妖", "竹林山道", "破旧飞剑"],
  "ui_submission_summary": [
    {"label": "起始帧", "frame_id": "E1S11_KF_START", "submitted": true, "as": "start_image"},
    {"label": "引导参考图", "frame_id": "E1S11_KF_GUIDE", "submitted": "depends_on_model", "as": "reference_or_prompt_guidance"}
  ]
}
```

## E1S32 进入游戏

```json
{
  "video_unit_id": "E1S32_V01",
  "shot_id": "E1S32",
  "duration_sec": 0,
  "model_mode": "review_only_no_generation",
  "model_inputs": {
    "start_image": null,
    "guide_references": [],
    "end_image": null,
    "review_frames": [
      {"frame_id": "E1S32_KF_REVIEW", "user_label": "审核帧"}
    ]
  },
  "video_prompt_zh": "不生成剧情视频。此单元为玩法入口标记：进入游戏：摆筋脉。审核帧仅用于分镜模块显示和用户确认，不默认提交给视频模型。",
  "negative_prompt": "",
  "action_timeline": [],
  "continuity_locks": [],
  "ui_submission_summary": [
    {"label": "审核帧", "frame_id": "E1S32_KF_REVIEW", "submitted": false, "as": "review_only"}
  ]
}
```

## E1S35 淡金火焰能力泄露

```json
{
  "video_unit_id": "E1S35_V01",
  "shot_id": "E1S35",
  "duration_sec": 5,
  "model_mode": "image_to_video_start_plus_refs",
  "model_inputs": {
    "start_image": {"frame_id": "E1S35_KF_START", "user_label": "起始帧"},
    "guide_references": [
      {"frame_id": "E1S35_KF_GUIDE", "user_label": "引导参考图", "behavior": "use_as_reference_if_supported_else_prompt_guidance"}
    ],
    "end_image": null,
    "asset_references": [
      {"asset_type": "character", "name": "男主", "user_label": "资产参考图"},
      {"asset_type": "character", "name": "林小满", "user_label": "资产参考图"}
    ]
  },
  "video_prompt_zh": "基于起始帧生成5秒视频。男主认真协助林小满调理紊乱药力，指尖一缕极淡淡金色火焰出现，轻轻牵住林小满体内乱窜的青白药力；药力被拨开形成清晰流向，男主掌心极淡火焰纹路一闪即逝。林小满从羞恼紧张逐渐变成震惊，察觉这不是护脉丹的药力。动作发展到引导参考图中的能力泄露状态，最后停在林小满睁大眼察觉异常的瞬间。保持两人外貌、服装、姿势、校场环境和淡金/青白药力区分一致。",
  "negative_prompt": "不要变脸，不要换衣服，不要大火球，不要爆炸，不要过度神化，不要新增角色，不要把淡金火焰画成护脉丹青白药力，不要跳场景，不要字幕水印",
  "action_timeline": [
    {"time": "0-1.5s", "action": "淡金火焰从男主指尖出现，靠近紊乱药力"},
    {"time": "1.5-3.5s", "action": "淡金火焰牵住青白药力，药力流向被拨开"},
    {"time": "3.5-5s", "action": "掌心火焰纹路一闪即逝，林小满睁大眼察觉异常"}
  ],
  "continuity_locks": ["男主", "林小满", "别扭调息姿势", "淡金火焰", "青白药力", "校场环境"],
  "ui_submission_summary": [
    {"label": "起始帧", "frame_id": "E1S35_KF_START", "submitted": true, "as": "start_image"},
    {"label": "引导参考图", "frame_id": "E1S35_KF_GUIDE", "submitted": "depends_on_model", "as": "reference_or_prompt_guidance"}
  ]
}
```

## E1S37 血红眼睛暗线钩子

```json
{
  "video_unit_id": "E1S37_V01",
  "shot_id": "E1S37",
  "duration_sec": 5,
  "model_mode": "image_to_video_start_end",
  "model_inputs": {
    "start_image": {"frame_id": "E1S37_KF_START_OR_PREVIOUS", "user_label": "起始帧"},
    "guide_references": [],
    "end_image": {
      "frame_id": "E1S37_KF_END",
      "user_label": "结束帧",
      "required_if_supported": true,
      "fallback": "prompt_guidance_if_unsupported"
    }
  },
  "video_prompt_zh": "生成5秒结尾钩子视频。画面先保留林小满震惊羞恼、男主挠头强装镇定的余韵，注意力逐渐落到画面边缘一丝极淡青白灯火；灯火里隐约露出一双血红眼睛，像看懂了什么，随后迅速钻入地缝消失。镜头语言：用边缘信息制造暗线，不让怪物抢主画面。镜头调度：人物余韵在中景，青白灯火藏在画面边角前景。运镜设计：镜头从人物反应慢慢微移到边缘灯火，焦点从人物眼神转到地缝，最后停在灯火消失后的空地缝。剪辑策略：单镜悬念 hold，下一镜可直接切新事件。细节表演：人物呼吸还没平复，眼神余震未散，男主手指停在挠头动作末端。若模型支持结束帧，最终停在结束帧的血红眼睛钻入地缝状态；若不支持，将结束帧作为动作结果引导。保持校场环境、人物余韵和暗线钩子的隐蔽感，不要把血眼变成主画面巨大怪物。",
  "negative_prompt": "不要巨大怪兽正脸，不要血腥恐怖，不要抢走主场景，不要跳场景，不要新增大批怪物，不要字幕水印，不要随机镜头乱晃",
  "action_timeline": [
    {"time": "0-2s", "action": "人物余韵保持，画面边缘青白灯火微弱出现"},
    {"time": "2-3.5s", "action": "灯火中血红眼睛一闪，像观察到了什么"},
    {"time": "3.5-5s", "action": "血红眼睛钻入地缝消失，留下暗线钩子"}
  ],
  "continuity_locks": ["校场环境", "林小满震惊羞恼", "男主强装镇定", "青白灯火", "血红眼睛隐蔽感"],
  "ui_submission_summary": [
    {"label": "起始帧", "frame_id": "E1S37_KF_START_OR_PREVIOUS", "submitted": true, "as": "start_image"},
    {"label": "结束帧", "frame_id": "E1S37_KF_END", "submitted": "if_supported", "as": "end_image; otherwise prompt_guidance"}
  ]
}
```

## Evaluation checks

Candidate video prompt output should:

1. Keep one shot as one video unit.
2. Preserve keyframe role labels in UI submission summary.
3. Use start image as true start.
4. Use guide/end frames as direction/end state, not mistaken starts.
5. Keep key action in first 70% of clip.
6. Keep gameplay entry as `review_only_no_generation` unless the user asks for transition video.
7. Include continuity locks and concise negative constraints.
8. Avoid multi-shot or multi-event overloaded prompts.
