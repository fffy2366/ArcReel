# Video Prompt Rules

## One clip, one main action

Do not pack multiple story events into one video prompt. A video unit should express one main visible action or one focused emotional/comedy beat.

Good:

```text
男主甩出灵符，灵符贴上藤蔓却没有反应，男主僵住。
```

Bad:

```text
男主甩符，灵符没反应，随后爆炸，藤蔓缩回，男主继续飞向校场。
```

## Timing rules

- Practical clip minimum: 5 seconds. Never submit a real video generation unit shorter than 5 seconds.
- Short insert/reaction/comedy beats may have a 2-3 second core action, but the actual clip remains at least 5 seconds; use the remaining time for reaction, breath, hold, environmental after-motion, or emotional aftertaste.
- Practical upper bound: 8 seconds.
- 15 seconds is a hard upper limit, not a target.
- Put key action in the first 70%.
- Use the final 30% for pause, hold, reaction, smoke, debris, breath, eye movement, or emotional aftertaste.

## Director-grade camera language

Every generated prompt must make the shot executable, not merely summarize the story.

- `镜头语言`: explain why the framing/angle exists, what the viewer should notice first, and how the shot creates tension, reveal, intimacy, speed, comedy, or suspense.
- `镜头调度`: place character, prop, and environment in readable spatial layers; state how the actor and key props move through the frame.
- `运镜设计`: describe camera start position, camera end position, subject path, focus shift, movement speed change, and final hold.
- `剪辑策略`: choose continuous shot, action match, whip pan, foreground wipe, match cut, montage, reaction hold, or simple straight cut according to actual story need.
- `细节表演`: for visible characters, include eyebrows, eyeline, mouth/jaw, breath, shoulders/neck, hands/fingers, and body weight shift.

If the director shot uses a style shorthand such as Nolan-like, Spielberg-like, Kubrick-like, Hitchcock-like, Wong Kar-wai-like, Kore-eda-like, Kurosawa-like, Zhang Yimou-like, Ang Lee-like, Fincher-like, or Miyazaki-like, preserve the executable camera behavior, not just the name. The final video prompt must still state the actual movement path, focus shift, speed change, and ending frame.

Do not use montage, dolly zoom / Hitchcock zoom, whip pan, or match cut as decoration. Use them only when they serve a real beat:

- montage: time compression, repeated effort, parallel actions, memory fragments;
- dolly zoom / Hitchcock zoom: sudden inner shock, vertigo, identity rupture, impossible realization;
- whip pan: fast directional reveal or chase energy;
- foreground wipe: hiding a cut while preserving continuous movement;
- match cut: linking two similar shapes/actions across shots.

When director shots specify montage, preserve the exact montage type and reason. If the director shot does not specify one, choose only when clearly justified:

| Story need | Montage type |
|---|---|
| Travel, training, refining, searching, repeated work | 时间压缩蒙太奇 |
| Simultaneous actions in separate places | 平行蒙太奇 |
| Simultaneous lines converging into rescue, danger, collision, or reveal | 交叉蒙太奇 |
| Obvious process can be skipped | 省略蒙太奇 |
| Memory, fear, fantasy, inner pressure | 心理/回忆蒙太奇 |
| Fate/theme/omen/power awakening through visual motif | 隐喻/象征/预兆蒙太奇 |
| Identity/status/emotional contrast | 对比蒙太奇 |
| Chase, countdown, fight escalation | 加速节奏蒙太奇 |
| Grief, aftershock, romance pause, quiet realization | 减速蒙太奇 |
| Attack impact, blade flash, thunder, eye close-up | 冲击蒙太奇 |

Never replace a concrete director strategy with generic `使用蒙太奇`.

## Frame role handling

### 起始帧 / start_image

- Submit as `start_image`.
- The prompt must continue naturally from this exact frame.
- Do not describe a different starting composition.

### 引导参考图 / guide_reference

- Use as reference if the model supports multiple reference images.
- If unsupported, translate into prompt guidance.
- Do not treat it as the first frame.
- Use language like “动作发展到……的状态” or “最后停在……的感觉”.

### 结束帧 / end_image

- Use as `end_image` only when backend supports first/last frames.
- If unsupported, use it as prompt guidance or a low-priority reference depending on backend capability.

### 审核帧 / review_frame

- Do not submit by default.
- Use for UI/transition approval.

### 资产参考图 / asset_reference

- Optional consistency references.
- Select in downstream reference-pack logic.
- Mention continuity locks even when not submitted.

## Continuity locks

Always lock:

- Character identity.
- Face/hair/clothing.
- Scene layout.
- Key props.
- Visual style/color continuity.
- Start frame composition unless the shot explicitly moves away.

For `1-1.md`, common locks include:

- 男主的修真外卖员身份、储物袋红十字标志、破旧飞剑。
- 林小满的外门弟子状态、经脉失控、羞恼反应。
- 竹林山道、校场、藤妖、小山魈、护脉丹药瓶。

## Negative constraints

Keep concise:

```text
不要变脸，不要换衣服，不要跳场景，不要新增人物，不要多肢体，不要手指畸形，不要字幕文字，不要水印，不要随机镜头乱晃，不要动作过载
```

Add role-specific negatives only when needed.

## Gameplay markers

- `进入游戏` review frames usually produce `review_only_no_generation`.
- `回归剧情` starts normal video generation again.
- Do not generate gameplay mechanics unless the shot explicitly requires a transition video.

## Output language

Use Chinese prompt by default for this project. Add English only when the target backend or user asks.
