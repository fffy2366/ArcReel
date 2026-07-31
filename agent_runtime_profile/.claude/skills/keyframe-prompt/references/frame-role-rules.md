# Frame Role Rules

## General image prompt formula

Use concrete visible evidence:

```text
frame role + scene/time/place + primary subject + exact frozen action moment + spatial relationship + expression/body state + key props + composition intent + inherited visual style + avoid list
```

Do not write multi-step video action. A keyframe is one frozen moment.

## 起始帧 / start_image

Purpose: video starts here.

Rules:

- Show the action before or at the first stable moment.
- Keep subject identity and scene layout clear.
- Avoid showing the action already completed unless the shot starts after completion.
- Make it stable enough for video continuation.

Good start frame:

```text
男主甩出皱巴巴灵符，藤蔓正在逼近，灵符刚离手。
```

Bad start frame:

```text
灵符已经爆炸，藤蔓缩回。
```

## 引导参考图 / guide_reference

Purpose: guide where motion, emotion, pose, danger, or joke should land.

Rules:

- Show the desired result/landing state.
- Do not call it a start frame.
- If the video model supports multiple references, it may be submitted as reference.
- If not, convert it into prompt guidance for `video-prompt`.

Good guide reference:

```text
灵符贴在藤蔓上没有反应，男主脸色僵住，藤蔓仍在逼近。
```

## 结束帧 / end_image

Purpose: video ends here when model supports first/last frame.

Rules:

- Use only when the backend supports end frames or when planning a future end-frame pass.
- Show the exact final state.
- Do not use end image as start image by mistake.

## 审核帧 / review_frame

Purpose: user checks a UI card, transition, title, or non-video planning image.

Rules:

- May include information useful to user workflow.
- Do not submit to video generation unless manually selected.
- For gameplay entry markers, usually use `review_only` unless a visual transition card is required.

## 资产参考图 / asset_reference

Purpose: consistency lock for character, scene, prop, or style.

Rules:

- Asset references live outside shot keyframes.
- Do not rewrite them as shot prompts unless the asset is missing.
- Label them clearly in UI.

## Role confusion checks

Before final output, verify:

- Start image starts the clip.
- Guide reference guides development.
- End image ends the clip when supported.
- Review frame is not submitted by default.
- Asset references are separate from shot keyframes.
- The user label is present and clear for every frame.

