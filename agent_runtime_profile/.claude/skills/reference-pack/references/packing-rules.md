# Reference Pack Rules

## Core principle

Do not submit more images than the shot needs. Extra references can confuse video models, especially when asset sheets use white backgrounds or show poses that conflict with the storyboard.

## Default max images

If the backend supports up to 9 images, treat 9 as a limit, not a target.

Recommended first-pass range:

- Simple shot: 1-2 images.
- Character-sensitive shot: 3-5 images.
- Multi-character, special prop, or effect-heavy shot: 5-7 images.
- Use 8-9 only for revision or complex continuity repair.

## Priority order

1. 起始帧 / `start_image`.
2. 结束帧 / `end_image`, only if supported or important as final-state guidance.
3. 引导参考图 / `guide_reference`, only if it adds motion/result clarity.
4. Main visible character face closeup.
5. Main visible character turnaround when full-body outfit, silhouette, or action pose matters.
6. Secondary visible character face closeup.
7. Critical prop, monster, mechanism, or法宝 reference.
8. Scene/environment reference if the start image does not already lock the location.
9. Style/effect reference, only if visual style or effect behavior is unstable.

Revise this order for the actual shot. For example, a prop close-up can outrank a secondary character asset.

## Character asset handling

Character assets may have two separate images:

- `face_closeup`: white-background clear face or head close-up.
- `turnaround`: white-background front/side/back three-view.

Use both only when the shot benefits from both identity and clothing/body consistency. If only one can fit:

- Prefer `face_closeup` for close-ups, emotional beats, dialogue, and romance.
- Prefer `turnaround` for full-body action, costume continuity, fight movement, or unusual posture.

When submitting white-background assets, add guidance:

```text
白底角色资产仅用于锁定脸、发型、服装和体型，不继承白色背景；剧情场景以起始帧为准。
```

## Scene and prop handling

- Use scene references when location architecture, geography, lighting, or era is unstable.
- Use prop references when the object has a defined design that must not mutate.
- Treat monsters and effect forms as `prop_reference` or `effect_reference` unless the project models them as characters.

## First pass versus revision

### First pass

Favor minimal packs:

- Start image.
- End image or guide image only when needed.
- One or two critical assets.

### Revision repair

Add references based on the actual failure:

- Face drift: add `character_face_closeup`.
- Outfit/body drift: add `character_turnaround`.
- Wrong location: add `scene_reference`.
- Wrong object: add `prop_reference`.
- Wrong action result: add `guide_reference` or `end_image`.
- Wrong effect color/shape: add `effect_reference`.

## Backend fallback

If the backend does not support a role:

- Unsupported `end_image`: convert the end state into prompt guidance.
- Unsupported multi-reference images: keep only start image plus the highest-priority asset; convert the rest into prompt guidance.
- Public URL required: mark every submitted local image with `public_url_required: true` and add an execution note for uploader/image host.

This skill does not upload files. It only produces a pack that later code can upload.

## Review-only frames

Do not submit `review_frame` to the video backend unless the user explicitly asks for a transition video or gameplay preview. Show it in UI as review-only.
