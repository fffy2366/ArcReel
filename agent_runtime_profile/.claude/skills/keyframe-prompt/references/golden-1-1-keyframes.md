# Golden Sample: `1-1.md` Representative Keyframe Prompts

Source shots: `agent_runtime_profile/.claude/skills/shot-director/references/golden-1-1-shots.md`

Purpose: representative calibration sample for role-aware keyframe prompting. This is not an exhaustive list of all 37 shots; it shows how to handle start frames, guide references, review frames, ability reveal, and cliffhanger end-hook frames.

## Shared assumptions

- Project style is inherited from project settings. Do not invent a conflicting style.
- Use concrete visible evidence.
- Label every generated frame role for the user.
- Asset references are separate from shot keyframes.

## E1S01 起始帧：修真外卖开场

```json
{
  "shot_id": "E1S01",
  "frames": [
    {
      "frame_id": "E1S01_KF_START",
      "role": "start_image",
      "user_label": "起始帧",
      "submit_as": "start_image",
      "frame_moment": "飞剑贴竹林低空掠过，男主红十字储物袋露出",
      "image_prompt_zh": "起始帧，青岚宗外门山道清晨，晨雾贴着竹林未散，一柄破旧狭窄飞剑贴近竹林低空掠过，男主踩在剑上，腰间灰扑扑储物袋露出醒目的红色十字送丹标志，衣摆被风吹起，画面要清楚表现“穷酸修真外卖员高速赶路”的开场信息，人物、飞剑、储物袋和竹林空间关系明确，继承项目画风。",
      "negative_prompt": "不要现代摩托车，不要科幻机甲，不要把储物袋画成普通背包，不要文字乱码"
    }
  ],
  "asset_references": [
    {"asset_type": "character", "name": "男主", "user_label": "资产参考图", "needed_for": "锁定男主外貌和送丹装备"},
    {"asset_type": "prop", "name": "破旧飞剑", "user_label": "资产参考图", "needed_for": "锁定飞剑破旧狭窄质感"}
  ]
}
```

## E1S07 起始帧 + 引导参考图：山魈爪子擦发

```json
{
  "shot_id": "E1S07",
  "frames": [
    {
      "frame_id": "E1S07_KF_START",
      "role": "start_image",
      "user_label": "起始帧",
      "submit_as": "start_image",
      "frame_moment": "山魈从侧面扑来，爪子即将靠近男主头发",
      "image_prompt_zh": "起始帧，青岚宗外门竹林山道，男主踩着破旧飞剑低空疾驰，侧面一只小山魈正扑向他，锋利爪子即将擦到男主头发，男主身体刚开始侧身闪躲，画面重点是近身危险距离，男主、山魈爪子、飞剑和竹林背景关系清晰，继承项目画风。",
      "negative_prompt": "不要已经躲完，不要血腥断肢，不要多余怪物挤满画面"
    },
    {
      "frame_id": "E1S07_KF_GUIDE",
      "role": "guide_reference",
      "user_label": "引导参考图",
      "submit_as": "reference_image_or_prompt_guidance",
      "frame_moment": "男主刚侧身躲过，头发被爪风削起一缕",
      "image_prompt_zh": "引导参考图，男主刚刚侧身躲过小山魈攻击，山魈爪子贴着他的头发擦过，几缕头发被爪风削起，男主表情惊险但仍稳住飞剑，背景竹林高速掠过，画面用于指导视频落到“擦身而过”的危险结果，不作为视频起始帧。",
      "negative_prompt": "不要表现成攻击命中，不要血腥伤口，不要换场景"
    }
  ]
}
```

## E1S11 起始帧 + 引导参考图：灵符没反应

```json
{
  "shot_id": "E1S11",
  "frames": [
    {
      "frame_id": "E1S11_KF_START",
      "role": "start_image",
      "user_label": "起始帧",
      "submit_as": "start_image",
      "frame_moment": "男主甩出灵符，藤蔓逼近",
      "image_prompt_zh": "起始帧，竹林山道中藤妖细藤从后方追来，男主站在破旧飞剑上甩出一张皱巴巴低阶灵符，嘴型像刚喊出“爆”，灵符刚飞向藤蔓，藤蔓距离很近，男主动作急促，画面同时保留危险和喜剧感，继承项目画风。",
      "negative_prompt": "不要灵符已经爆炸，不要把灵符画成现代纸条，不要画成静态摆拍"
    },
    {
      "frame_id": "E1S11_KF_GUIDE",
      "role": "guide_reference",
      "user_label": "引导参考图",
      "submit_as": "reference_image_or_prompt_guidance",
      "frame_moment": "灵符贴住藤蔓却没反应，男主脸色僵住",
      "image_prompt_zh": "引导参考图，皱巴巴灵符已经贴在藤蔓上却没有爆炸，藤蔓仍然逼近男主，男主脸色僵住、眼神尴尬又慌，飞剑仍在低空向前，画面用于指导喜剧停顿的落点，不作为起始帧。",
      "negative_prompt": "不要爆炸火光，不要藤蔓已经缩回，不要男主表情镇定"
    }
  ]
}
```

## E1S32 审核帧：进入游戏

```json
{
  "shot_id": "E1S32",
  "frames": [
    {
      "frame_id": "E1S32_KF_REVIEW",
      "role": "review_frame",
      "user_label": "审核帧",
      "submit_as": "review_only",
      "frame_moment": "进入游戏：摆筋脉",
      "image_prompt_zh": "审核帧，玩法入口转场画面，用于标记剧情分镜结束并进入“摆筋脉”玩法，可表现为简洁清楚的玩法入口视觉，不默认提交给视频生成模型。",
      "negative_prompt": "不要误作为剧情起始帧，不要混入后续回归剧情"
    }
  ]
}
```

## E1S35 起始帧 + 引导参考图：淡金火焰能力泄露

```json
{
  "shot_id": "E1S35",
  "frames": [
    {
      "frame_id": "E1S35_KF_START",
      "role": "start_image",
      "user_label": "起始帧",
      "submit_as": "start_image",
      "frame_moment": "淡金火焰刚从男主指尖出现",
      "image_prompt_zh": "起始帧，回归剧情后，林小满保持别扭调息姿势，男主靠近协助调理药力，他的指尖刚刚闪出一缕极淡淡金色火焰，青白药力在林小满经脉附近紊乱游走，男主表情认真，林小满仍带着羞恼和紧张，画面重点是隐藏能力即将暴露，继承项目画风。",
      "negative_prompt": "不要画成大火球，不要夸张爆炸，不要换成战斗场景"
    },
    {
      "frame_id": "E1S35_KF_GUIDE",
      "role": "guide_reference",
      "user_label": "引导参考图",
      "submit_as": "reference_image_or_prompt_guidance",
      "frame_moment": "淡金火焰牵住药力，掌心纹路一闪即逝",
      "image_prompt_zh": "引导参考图，男主指尖淡金火焰已经牵住林小满体内紊乱的青白药力，药力被拨开形成清晰流向，男主掌心浮现极淡火焰纹路又快要消失，林小满睁大眼睛察觉异常，画面用于指导能力泄露的结果，不作为起始帧。",
      "negative_prompt": "不要把火焰画成护脉丹药力，不要过度神化，不要新增其他角色"
    }
  ]
}
```

## E1S37 结束钩子帧：血红眼睛

```json
{
  "shot_id": "E1S37",
  "frames": [
    {
      "frame_id": "E1S37_KF_END",
      "role": "end_image",
      "user_label": "结束帧",
      "submit_as": "end_image_or_prompt_guidance",
      "frame_moment": "青白灯火里的血红眼睛钻入地缝",
      "image_prompt_zh": "结束帧，校场边缘极不显眼的位置，一丝极淡青白灯火贴近地面，灯火中隐约露出一双血红眼睛，像刚看懂了什么，正钻入地缝消失；前景仍保留林小满震惊羞恼、男主挠头强装镇定的余韵，画面重点是暗线钩子和隐藏观察者，继承项目画风。",
      "negative_prompt": "不要把血红眼睛画成巨大怪兽正脸，不要抢走主场景，不要变成恐怖血腥画面"
    }
  ]
}
```

## Evaluation checks

Candidate keyframe prompt output should:

1. Preserve user-facing labels: 起始帧, 引导参考图, 结束帧, 审核帧, 资产参考图.
2. Keep start image and guide reference distinct.
3. Avoid multi-step video motion inside a still-image prompt.
4. Convert guide/end frames into result-state images.
5. Keep `进入游戏` as review-only unless the product explicitly wants a transition visual.
6. Preserve `回归剧情` as the start of returned story/cutscene context.
7. Keep asset references separate from generated shot keyframes.
8. Use concrete visible details and avoid vague prompt filler.

