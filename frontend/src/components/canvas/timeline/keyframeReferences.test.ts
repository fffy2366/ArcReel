import { describe, expect, it } from "vitest";
import type { ProjectData } from "@/types";
import { buildKeyframeReferenceImages } from "./keyframeReferences";

describe("buildKeyframeReferenceImages", () => {
  it("keeps sword-flight start keyframes lightweight and prioritizes face plus sword", () => {
    const project = {
      title: "demo",
      content_mode: "narration",
      style: "",
      episodes: [],
      characters: {
        陆泰源: {
          description: "男主",
          reference_image: "characters/refs/陆泰源.png",
          character_sheet: "characters/陆泰源.png",
        },
      },
      scenes: {
        青岚宗外门山道: {
          description: "竹林山道",
          scene_sheet: "scenes/青岚宗外门山道.png",
        },
      },
      props: {
        破旧飞剑: {
          description: "旧飞剑",
          prop_sheet: "props/破旧飞剑.png",
        },
        传音玉简: {
          description: "玉简",
          prop_sheet: "props/传音玉简.png",
        },
      },
    } satisfies ProjectData;

    expect(
      buildKeyframeReferenceImages(
        project,
        "陆泰源正在清晨竹林冠层上方御剑飞行，破旧飞剑前段可见，右手抬起传音玉简。",
      ),
    ).toEqual(["characters/refs/陆泰源.png", "props/破旧飞剑.png"]);
  });
});
