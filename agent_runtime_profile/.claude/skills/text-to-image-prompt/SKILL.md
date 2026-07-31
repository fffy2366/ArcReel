---
name: text-to-image-prompt
description: Create, expand, reverse-engineer, and refine AI text-to-image prompts from rough scene ideas, image descriptions, character concepts, or user drafts. Use when the user asks for 文生图提示词, 生图关键词, AI image prompts, prompt expansion, prompt cleanup, image-to-prompt analysis, character image prompt modules, or avoiding prompt pollution for tools such as Doubao, Jimeng, Midjourney, Stable Diffusion, DALL-E, or similar image generators.
---

# Text-To-Image Prompt

## Core Rule

Turn vague intent into visible evidence. Prefer concrete space, subject, action, object relationships, light, composition, color, and final medium over abstract words such as "cinematic", "healing", "premium", or "atmospheric".

When the task is a UI, game interface, app screen, web page, dashboard, menu, panel, button layout, or any prompt containing "界面/UI/页面/原型/按钮/导航/面板", first apply the `frontend-design` skill. Treat the UI as a usable product screen before writing the image prompt: define the primary action, hierarchy, interaction states, layout positions, visual system, readability constraints, and anti-clutter rules.

When the user provides only a short idea, ask at most one clarifying question if a required creative direction is missing. Otherwise make a reasonable choice and produce a usable prompt.

## Workflow

1. Identify the task type:
   - **Generate from idea**: expand a rough scene into a complete prompt.
   - **Refine draft**: remove abstraction, contradiction, weak negation, and template words.
   - **Character prompt**: build modular role, face, hair, outfit, pose, scene, light, and texture blocks.
   - **UI prompt**: apply `frontend-design`, then specify screen purpose, playable viewport, exact UI layout, interaction states, visual system, readability rules, and a minimal avoid list.
   - **9-grid motion guide**: from a director shot, create a rough black-and-white pencil storyboard sheet that explains how a video clip should perform; this is a guide reference for the video model, not a final keyframe.
   - **Reverse image prompt**: analyze a provided image or user-described image into a recreatable prompt.
   - **Keyword groups**: output comma-separated keyword strings, often in 5 style variants.

2. Choose a structure:
  - For general scenes, use: time/place + subject identity/appearance + action + key objects/spatial relationships + expression/body state + light/composition/shot + final medium/texture.
   - For 9-grid motion guides, use: white-background 3x3 storyboard sheet + pencil sketch style + one action state per panel + camera arrows/motion lines + start/development/landing rhythm + minimal labels only if the image model handles them well.
   - For UI/game interface prompts, use: screen type + product context + main viewport/playable object + positioned UI layout + interaction states + visual system + readable text constraints + minimal exclusions.
   - For cinematic/photo prompts, use the 5-part formula: camera and composition, subject, environment, light, color and texture.
   - For image-generation "agent" style keyword output, use the 12-part structure from `references/prompt-patterns.md`.
   - For people/characters, use modular blocks so individual modules can be edited without rewriting the entire prompt.

3. Clean the prompt:
   - Replace abstract feeling words with visible evidence.
   - Replace negative phrasing with the desired positive result.
   - Replace template words such as "创业", "约会", "直播", "商务", "旅行" with specific people, places, actions, objects, and natural states.
   - Specify spatial relationships for directional objects such as phones, tablets, screens, mirrors, books, drawings, car doors, weapons, and cup handles.

4. Output in the format the user needs. If no format is specified, provide:
   - **中文提示词**
   - **English Prompt** when useful for the target tool
   - **可调参数/可替换模块** only when it helps the user iterate

## Output Rules

- Make prompts directly pasteable into image tools.
- Use rich concrete detail, but avoid bloating with repeated synonyms.
- Keep negative prompts minimal; prefer positive replacement language.
- For 9-grid motion guides, prioritize readable body mechanics, action order, camera direction, and prop orientation over beauty or final rendering quality.
- For UI prompts, do not generate poster-like art. The output must describe an actual interface with clear hierarchy, state, controls, and readable Chinese labels.
- If the user asks for multiple options, vary meaningful creative choices such as style, camera, light, palette, environment, and mood evidence.
- For generated image prompts involving real people, brands, copyrighted characters, or sensitive content, follow normal safety and copyright rules.

## Reference

Read `references/prompt-patterns.md` when you need formulas, examples, reverse-prompt instructions, modular character prompting, or the pre-generation checklist.
