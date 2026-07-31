# Shot Directing Rules

## Unit definitions

- Story beat: narrative unit from `story-beat`.
- Micro beat: detailed story beat; its action core may be short, but real generated shots still use the project minimum duration.
- Shot group:分镜模块 cluster, usually aligned to a parent beat or hard boundary.
- Shot/clip: video-generation unit, never below 5 seconds for real generation, with one main action.
- Keyframe: visual control image with an explicit role such as 起始帧 or 引导参考图.

## Duration rules

- Practical minimum generated shot duration: 5 seconds.
- Short insert/reaction/comedy pause may have a 2-3 second action core, but keep the submitted shot at 5+ seconds by adding reaction, hold, breath, environmental after-motion, or emotional aftertaste.
- Complex single continuous action: 7-8 seconds.
- 15 seconds is a hard limit for special slow ambience, not a default.

Primary action timing:

- Put the main action in the first 70% of the clip.
- Use the final 30% for reaction, hold, debris, smoke, pause, breath, or emotional aftertaste.

## Merge rules

Merge micro beats only when all are true:

- Same scene or continuous movement through one space.
- Same primary screen subject.
- Same action direction.
- No independent reveal, danger, joke, failure, reaction, or boundary.
- Combined duration remains model-realistic.

Never merge:

- Near miss.
- Prop failure.
- Comedy pause.
- Reaction that creates a joke or relationship shift.
- Reveal or ability leak.
- Gameplay entry.
- Return-to-story marker.
- Cliffhanger.

## Gameplay boundary rules

- A line like `进入游戏：摆筋脉` ends the current shot group.
- Do not design the gameplay mechanic.
- A line like `回归剧情：` starts a new shot group.
- The marker itself can be a 0-second structural boundary or a 1-second transition card/visual cue if the product needs one.
- Follow source markers exactly; do not move boundaries unless the user asks.

## Comedy timing rules

Comedic beats often need separation:

- Setup / flag.
- Pause / failure.
- Reaction.
- Payoff.

Example:

```text
男主大喊“爆”
灵符没反应
男主脸色一僵
藤蔓快缠住
灵符突然炸开
```

Do not compress this into “男主用灵符炸退藤妖”. Preserve the failed-prop pause and delayed payoff.

## Montage selection rules

Use montage as a decision, not decoration. `editing_strategy` must name the type and why it fits the beat.

| Story need | Editing choice |
|---|---|
| Travel, training, refining, searching, repeated work, long process | 时间压缩蒙太奇 |
| Two places/actions happen at the same time | 平行蒙太奇 |
| Two simultaneous lines move toward collision, rescue, danger, or reveal | 交叉蒙太奇 |
| Skip an obvious process and keep only setup/result | 省略蒙太奇 |
| Memory fragments, fear, guilt, fantasy, decision pressure | 心理/回忆蒙太奇 |
| Fate, theme, omen, power awakening shown through object/weather/light motif | 隐喻/象征蒙太奇 |
| Class/status/emotional contrast between two images | 对比蒙太奇 |
| Hidden observer, future danger, unresolved hook | 预兆蒙太奇 |
| Chase, countdown, fight escalation, panic, urgent deadline | 加速节奏蒙太奇 |
| Grief, aftershock, romance pause, shame, quiet realization | 减速蒙太奇 |
| Attack impact, thunder, blade flash, eye close-up, rupture | 冲击蒙太奇 |

Forbidden:

- Do not write only `使用蒙太奇` or `轻量蒙太奇`.
- Do not use montage for ordinary dialogue or a single simple action.
- Do not use Hitchcock/dolly zoom unless the character experiences sudden inner shock, vertigo, impossible realization, or identity rupture.
- Do not pack several story events into one video clip just because montage is selected; a generated clip still needs one clear main action.

## Camera style and movement grammar

Director-style terms are allowed only as internal shorthand. Convert them into executable camera behavior.

| Story need | Style shorthand | Executable camera behavior |
|---|---|---|
| Fate, system, time, maze, judgment, giant structure | Nolan-like cold spatial pressure | axial push, symmetrical depth, low controlled track, scale contrast |
| First sight, miracle, monster/building reveal, emotional discovery | Spielberg-like wonder/reveal | character reaction first, eyeline guide, over-shoulder reveal, push-in or tilt-up |
| Ritual, corridor, institution, psychological unease | Kubrick-like symmetry | central perspective, slow tracking, rigid blocking |
| Hidden danger, audience knows more than character, voyeurism | Hitchcock-like suspense | POV, object insert, eyeline mismatch, rack focus, dolly zoom only for shock |
| Rain, neon, alley, cigarette, missed connection, intimacy | Wong Kar-wai-like urban intimacy | slow lateral drift, foreground blur, reflection, close body distance |
| Home, desk, food, care, restrained emotion | Kore-eda-like life observation | static/slow low camera, natural blocking, action enters frame |
| Wind, rain, dust, duel, group motion, forest | Kurosawa-like weather/action blocking | strong lateral motion, weather as action, clear directional staging |
| Ceremony, palace, banners, ranks, symbolic color | Zhang Yimou-like ritual/color block | frontal tableau, group geometry, red/gold/white color mass |
| Confession, shame, quiet love, moral choice | Ang Lee-like restraint | measured push/pull, distance between bodies, hand/eyeline detail |
| Investigation, monitor, corporate room, hidden calculation | Fincher-like precision/control | mechanical push/pull, locked composition, dark clean layers |
| Flying, wind, clouds, forest, creature movement, wonder | Miyazaki-like flight/environment | floating follow, wind-reactive hair/clothes, breathing environment |

Movement grammar choices:

- 道具揭示: prop close-up → hand/finger detail → eyeline/face.
- 人物登场: back/side silhouette → partial face → full reveal.
- 危险逼近: foreground threat → character reaction → escape/impact path.
- 追逐/飞行: low side-front tracking → background streak → controlled shake → reaction hold.
- 情绪变化: static/slow push → focus from hands/mouth to eyes → breath hold.
- 空间揭示: overhead/wide establish → descend/push to subject → lock orientation.
- 悬念窥视: foreground occlusion/POV → rack focus → hold before reveal.

Forbidden:

- Do not write only `诺兰运镜`, `斯皮尔伯格运镜`, or any director name as the final movement description.
- Do not force a famous-director style onto every shot. Ordinary action should use plain movement grammar.
- Do not use a living-director reference as the only model-facing instruction; always provide the actual camera path, focus, speed, and ending frame.

## Keyframe role rules

Every shot module must label image roles for the user:

- 起始帧: video starts here; submit as `start_image`.
- 引导参考图: guides the next state; submit as `reference_image` or convert to prompt guidance depending on model support.
- 结束帧: video ends here; submit as `end_image` only when supported.
- 资产参考图: character/scene/prop/style consistency; submit as `reference_image` when selected.
- 审核帧: human review only; do not submit by default.

Do not call all images “参考图”. Users must see which image controls the start, which guides motion, and which locks assets.

## Strategy selection

- `start_only`: simple movement, environment, ordinary action.
- `start_and_guide`: comedy pauses, near misses, facial reactions, object failures, delicate body positions, action result guidance.
- `start_and_end`: precise transformation or when the model supports first/last frames.
- `end_hook`: cliffhanger or reveal where final image matters most.
- `review_only`: planning image not intended for generation.

## Boundaries with downstream skills

This skill may decide broad shot type, subject, action, timeline, and keyframe roles.

It must not decide:

- Final prompt wording.
- Exact camera model/lens/aperture.
- Full lighting plan.
- Final reference image upload choices.
- Gameplay mechanics.
