---
name: frontend-design
description: Create polished, production-grade UI design directions and UI image-generation prompts. Use before writing or revising prompts for game UI screens, app screens, web pages, dashboards, mobile interfaces, UI mockups, or any "界面/UI/页面/原型/按钮/导航/面板" visual asset.
---

# Frontend Design

Use this skill before generating UI concept images or UI mockups. The goal is to turn a rough interface request into a screen that looks designed, playable, and specific to the product instead of a generic prompt full of panels and labels.

## Core Judgment

Design the interface as a real usable screen first, then write the image prompt.

Before writing the prompt, decide:

1. **Primary user action**: what the player/user is doing on this screen.
2. **Information hierarchy**: what must be seen first, second, and only on demand.
3. **Interaction state**: selected tab, cooldown, disabled button, notification dot, progress, drag target, QTE timing, reward reveal, or empty state.
4. **Visual identity**: palette, material, typography feel, icon style, border brightness, density, motion/effect language.
5. **Anti-clutter rule**: remove any UI element that does not support the current screen.

## UI Prompt Structure

For UI image prompts, use this order:

1. **Use case and screen type**: e.g. portrait mobile game UI concept mockup, production interface screenshot.
2. **Product context**: genre, world, current feature, screen purpose.
3. **Main viewport**: the playable scene or central interaction area.
4. **UI layout**: exact position of bars, panels, buttons, tabs, cards, alerts, and selected states.
5. **Interaction details**: cooldown rings, progress bars, drag handles, highlighted targets, count badges, selected item, hover/pressed feel if relevant.
6. **Visual system**: materials, palette, borders, icons, typography contrast, spacing, density.
7. **Readability constraints**: high contrast Chinese labels, no overlapping text, stable button sizes, clear tap targets.
8. **Avoid list**: only include necessary exclusions; do not put sensitive or risky words in avoid lists if the image backend may reject them.

## Game UI Rules

- A game screen must show the playable state, not a poster or marketing hero.
- Do not fill the screen with explanatory text. Use icons, concise labels, meters, tabs, item cards, and state badges.
- Keep major controls in predictable reachable areas on mobile.
- Use stable button dimensions and clear selected/disabled/cooldown states.
- Resource bars should be compact and readable; do not let currencies dominate the composition.
- Repeated items may use cards or slots. Do not nest cards inside cards.
- If the screen is a battle, travel, QTE, alchemy, storage, forge, task, auction, or reward page, show the actual gameplay object in the center.
- Prefer specific interaction wording: "one circular button has a 60% cooldown ring" is better than "cool buttons".

## Visual Quality Rules

- Choose one clear aesthetic direction and execute it consistently.
- Avoid cheap mobile-game clutter, oversized text, excessive badges, heavy gradients, and random decoration.
- For refined xianxia UI, prefer moon-white, pale cyan jade, translucent glass/jade panels, soft gold accents, bright readable borders, restrained ink details, and generous empty air.
- Use richer contrast through material and light, not by flooding the screen with one color.
- Chinese UI labels must be legible: pure white or dark ink depending on background, bold enough, with subtle outline/shadow if needed.

## 修真外卖 UI Direction

For 《修真外卖员：丹药送到，师姐别乱来》 UI prompts:

- Overall style: high-end xianxia mobile game UI, moon-white celestial air, pale cyan jade, soft gold, clean translucent panels, readable Chinese text.
- Avoid heavy green, dirty dark markets, cheap page-game composition, modern delivery-app maps, sci-fi UI, guns, camera/photography gameplay, dragon-centipede ball gameplay, and cluttered bottom nav on screens that should be immersive.
- Homepage/idle travel: first screen is active 御剑游历, not a main menu. It should show flying-sword travel and only the necessary action buttons, such as 闪避 / 防护 / 雷符, unless the user asks for full navigation.
- Auction/trade: use 坊市 or 拍卖行 language, clean celestial night-market mood, visible treasure display, only essential buy/sell actions.
- Resonance/QTE draw: show a meditating female cultivator or inner-realm cultivation subject as the reward focus, not a casino machine, slot reel, or treasure chest-only page.

## Output Checklist

Before finalizing any UI prompt, verify:

- The current screen's single main purpose is obvious.
- The main gameplay object is visible.
- Buttons and tabs have clear states.
- The prompt says where UI elements sit on the screen.
- The palette is not one-note.
- The result would be usable as a mobile game UI concept, not just illustration art.
