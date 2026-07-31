# Story Beat Format Profiles

Choose the profile by `content_format`. Keep shared data in `common`; put only format-specific fields in `profile`.

## `interactive_drama_game`

Use for interactive drama games, romance games, first-person story games, branching FMV games, and PlayAsLife-style 剧游.

Primary logic:

- Player perspective.
- Relationship change.
- Choice setup and consequence.
- Emotional reward.
- Branch or cliffhanger potential.
- Mission/gameplay/comedy beats when the project is built around tasks, mechanics, delivery pressure, or comic failure.

Recommended `beat_function` values:

- `opening_hook`
- `arrival`
- `first_encounter`
- `intimacy_probe`
- `relationship_shift`
- `choice_setup`
- `choice_result`
- `secret_reveal`
- `threat_arrival`
- `branch_cliffhanger`
- `transition`
- `delivery_mission`
- `route_danger`
- `evasive_maneuver`
- `near_miss`
- `comedy_action`
- `comedy_gag`
- `gameplay_entry`
- `tutorial_mechanic`
- `service_success`
- `ability_leak`

Profile fields:

```json
{
  "pov": "first_person",
  "player_role": "男主",
  "subtype": "romance_interactive",
  "heroine_focus": "",
  "relationship_change": "",
  "emotional_reward": "",
  "mission_context": "",
  "gameplay_trigger": "",
  "mechanic_introduced": "",
  "service_outcome": "",
  "comedy_payload": "",
  "ability_foreshadowing": "",
  "interaction_potential": {
    "has_choice": false,
    "choice_timing": "",
    "choice_question": "",
    "choice_types": [],
    "variable_impacts": []
  },
  "branch_risk": "",
  "cliffhanger_potential": ""
}
```

Rules:

- Do not fully design branches unless asked.
- Identify choice candidates when the beat naturally ends with player agency.
- Track affection/relationship implications as candidates, not final balance math.
- Preserve first-person experience when the source supports it.
- Use `subtype: romance_interactive` for romance-forward interactive stories.
- Use `subtype: mission_gameplay_comedy` for task-based comedic game stories such as delivery missions, tutorial mechanics, service ratings, and slapstick failure.
- In `mission_gameplay_comedy`, do not collapse a dangerous route into one beat; split named hazards, near misses, prop failures, and comic pauses into micro beats when they need 2-3 seconds of screen time.
- When the script explicitly says "进入游戏", "进入玩法", or names a playable segment, do not infer or design which mechanic it enters. Copy/mark the explicit gameplay entry as `gameplay_trigger` and treat it as the ending hook of the current beat or shot group.
- If the source does not explicitly name the gameplay segment, only mark `interaction_potential` or `gameplay_trigger` as a candidate.

## `narrative_video`

Use for linear short dramas, film scenes, web drama episodes, trailers with story continuity, and non-interactive剧情视频.

Primary logic:

- Protagonist goal.
- Obstacle.
- Conflict escalation.
- Reveal/reversal.
- Emotional arc.

Recommended `beat_function` values:

- `opening_hook`
- `setup`
- `inciting_incident`
- `goal_established`
- `obstacle`
- `conflict`
- `escalation`
- `reveal`
- `reversal`
- `climax`
- `resolution`
- `cliffhanger`
- `transition`

Profile fields:

```json
{
  "protagonist_goal": "",
  "obstacle": "",
  "conflict_type": "",
  "stakes": "",
  "turning_point": "",
  "reveal": "",
  "emotional_arc": "",
  "cliffhanger": ""
}
```

Rules:

- Focus on dramatic state changes, not player choice.
- Keep causality clear.
- Mark weak beats when a scene has atmosphere but no conflict, information, or emotional change.

## `ad`

Use for advertisements, trailers focused on selling a product, feature promos, app/game ads, or performance marketing scripts.

Primary logic:

- Attention.
- Pain or desire.
- Product/solution.
- Benefit.
- Proof/demo.
- CTA.

Recommended `beat_function` values:

- `attention_hook`
- `pain_or_desire`
- `solution_reveal`
- `benefit_showcase`
- `proof_demo`
- `offer`
- `cta`
- `transition`

Profile fields:

```json
{
  "marketing_goal": "",
  "target_audience": "",
  "viewer_pain_or_desire": "",
  "selling_point": "",
  "product_moment": "",
  "proof_or_demo": "",
  "cta": "",
  "retention_hook": ""
}
```

Rules:

- Beat duration is usually 1-4 seconds.
- Prefer direct viewer promise over literary plot detail.
- Every beat must earn attention or persuasion value.

## `narrated_drama`

Use for 解说剧, narrated recaps, novel narration videos, story explanation videos, and voiceover-led content.

Primary logic:

- Narration information point.
- Visual support.
- B-roll.
- Subtitle/voiceover rhythm.
- Information density.

Recommended `beat_function` values:

- `context_intro`
- `character_intro`
- `world_explanation`
- `cause_effect`
- `contrast`
- `suspense_question`
- `emotional_punch`
- `transition`

Profile fields:

```json
{
  "narration_text": "",
  "narration_point": "",
  "visual_support": "",
  "b_roll": [],
  "subtitle_density": "normal",
  "voiceover_tone": "",
  "sync_mode": "narration_leads_visual",
  "information_density": "medium"
}
```

Rules:

- Time follows narration first.
- Estimate Chinese narration at roughly 4-6 characters per second unless the user provides pacing.
- Visuals may be reenactments, inserts, atmosphere, or B-roll rather than literal continuous action.
- Keep each beat aligned to one narration point.
