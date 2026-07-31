import type { ProjectData } from "@/types";

const MAX_KEYFRAME_REFERENCE_IMAGES = 2;

interface ReferenceCandidate {
  path: string | null | undefined;
  priority: number;
}

function normalizeReferenceText(text: string): string {
  return text.replace(/\s+/g, "").replace(/红色/g, "红").toLowerCase();
}

function addCandidate(candidates: ReferenceCandidate[], path: string | null | undefined, priority: number): void {
  if (!path) return;
  candidates.push({ path, priority });
}

function characterNameMatchesPrompt(characterName: string, promptText: string): boolean {
  const name = normalizeReferenceText(characterName);
  const text = normalizeReferenceText(promptText);
  if (!name || !text) return false;
  if (text.includes(name)) return true;
  if (name === "陆泰源" && (text.includes("男主") || text.includes("主角") || text.includes("御剑送丹"))) {
    return true;
  }
  return false;
}

function sceneNameMatchesPrompt(sceneName: string, promptText: string): boolean {
  const name = normalizeReferenceText(sceneName);
  const text = normalizeReferenceText(promptText);
  if (!name || !text) return false;
  if (text.includes(name)) return true;
  if (name.includes("山道") && (text.includes("山道") || text.includes("竹林") || text.includes("竹梢"))) {
    return true;
  }
  return false;
}

function propNameMatchesPrompt(propName: string, promptText: string): boolean {
  const name = normalizeReferenceText(propName);
  const text = normalizeReferenceText(promptText);
  if (!name || !text) return false;
  if (text.includes(name)) return true;
  if (name.includes("木牌")) return text.includes("木牌");
  if (name.includes("飞剑") && text.includes("飞剑")) return true;
  if (name.includes("储物袋") && text.includes("储物袋")) return true;
  if (name.includes("药瓶") && text.includes("药瓶")) return true;
  if (name.includes("丹") && text.includes("丹")) return true;
  if (name.includes("灵符") && text.includes("灵符")) return true;
  if (name.includes("玉简") && text.includes("玉简")) return true;
  return false;
}

export function buildKeyframeReferenceImages(project: ProjectData | null, promptText: string): string[] {
  const candidates: ReferenceCandidate[] = [];
  const seen = new Set<string>();
  const text = normalizeReferenceText(promptText);
  const isSwordFlight = text.includes("飞剑") || text.includes("御剑");
  for (const [name, character] of Object.entries(project?.characters ?? {})) {
    if (!characterNameMatchesPrompt(name, promptText)) continue;
    addCandidate(candidates, character.reference_image, 10);
    addCandidate(candidates, character.character_sheet, isSwordFlight ? 40 : 20);
  }
  for (const [name, scene] of Object.entries(project?.scenes ?? {})) {
    if (!sceneNameMatchesPrompt(name, promptText)) continue;
    addCandidate(candidates, scene.scene_sheet, isSwordFlight ? 70 : 50);
  }
  for (const [name, prop] of Object.entries(project?.props ?? {})) {
    if (!propNameMatchesPrompt(name, promptText)) continue;
    const normalizedName = normalizeReferenceText(name);
    const priority = isSwordFlight && normalizedName.includes("飞剑") ? 20 : 30;
    addCandidate(candidates, prop.prop_sheet, priority);
  }
  return candidates
    .sort((a, b) => a.priority - b.priority)
    .map((candidate) => candidate.path)
    .filter((path): path is string => {
      if (!path || seen.has(path)) return false;
      seen.add(path);
      return true;
    })
    .slice(0, MAX_KEYFRAME_REFERENCE_IMAGES);
}
