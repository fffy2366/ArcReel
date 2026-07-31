# Continuity QA Rules

## Evidence first

Compare the generated result to:

1. Story beat intent.
2. Shot-director shot.
3. Keyframe roles.
4. Video prompt action timeline.
5. Reference-pack selected images.
6. Previous/next clip continuity when available.

Separate observed facts from likely causes.

## Repair decision table

| Failure | Usually fix in | Action |
|---|---|---|
| Face drift | reference-pack | Add `character_face_closeup`; regenerate same clip |
| Hair, outfit, body drift | reference-pack | Add `character_turnaround`; regenerate same clip |
| White background appears in story scene | reference-pack + video prompt | Mark asset `copy_background: false`; add “不继承白底背景” constraint; reduce asset refs if needed |
| Wrong scene or location | keyframe-prompt or reference-pack | If start frame is wrong, regenerate/edit keyframe; if video drifts, add scene reference |
| Prop/法宝 shape wrong | reference-pack | Add prop reference and prop lock |
| Effect color/shape wrong | video-prompt + reference-pack | Tighten effect wording; add effect reference if available |
| Key action missing or wrong | video-prompt | Rewrite action timeline; add guide/end frame if useful |
| Action happens too late | video-prompt or shot-director | Put key action in first 70%; shorten clip |
| Last seconds lose control | shot-director/video-prompt | Reduce to 4-5s or split into two clips |
| Too many story events | shot-director | Split shot |
| Camera moves randomly | video-prompt | Simplify camera move; add negative “不要随机镜头乱晃/不要突然推拉” |
| Composition wrong from first frame | keyframe-prompt | Regenerate or edit start keyframe |
| Emotion/performance wrong | performance-director + video-prompt | Rewrite visible expression, pause, breath, gaze, body tension |
| Gameplay entry generated as video | video-prompt/reference-pack | Mark `review_only_no_generation`; do not send to video backend |
| Subtitles/watermark/text | video-prompt negative | Add text/watermark negatives and regenerate |

## Do not overuse references

If the problem is action timing or camera motion, adding more asset images usually will not fix it. Change the video prompt or split the shot.

If the problem is wrong first-frame composition, reference images will not reliably fix it. Regenerate or edit the keyframe first.

## Model-duration reality

For weak control after 5 seconds:

- Put the important action earlier.
- Add a hold/reaction in the final 30%.
- Shorten to 4-5 seconds.
- Split into two clips if two real story actions are required.

15 seconds is not a normal target; it is a hard upper bound.

## User-facing judgement

Use plain judgement:

- “可接受”：only minor issues.
- “建议小修”：prompt/reference tweak is enough.
- “建议重生”：core action or identity is wrong.
- “建议先重做关键帧”：start composition is wrong.
- “建议拆镜头”：too much is happening for one clip.

Do not bury this judgement in long technical text.
