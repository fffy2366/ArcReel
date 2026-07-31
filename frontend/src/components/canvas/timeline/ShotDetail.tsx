import { useCallback, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import {
  ImageIcon,
  Film,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  ChevronDown,
  Check,
  Loader2,
  Plus,
  Sparkles,
  Undo2,
  X,
} from "lucide-react";
import type { DurationOutOfRangeReason } from "@/hooks/useModelCapabilities";
import type {
  NarrationSegment,
  DramaScene,
  AdShot,
  ImagePrompt,
  VideoPrompt,
  Dialogue,
  DraftVideoFrame,
  KeyframeImageFrame,
  KeyframePrompt,
  Utterance,
  VideoPromptPack,
  VideoPromptPackItem,
  VideoReferenceEntry,
  ProjectData,
} from "@/types";
import { AD_SECTION_VALUES } from "@/types";
import { ImagePromptEditor } from "./ImagePromptEditor";
import { VideoPromptEditor } from "./VideoPromptEditor";
import { DialogueListEditor } from "./DialogueListEditor";
import { UtteranceListEditor } from "./UtteranceListEditor";
import { ResponsiveDetailGrid } from "./ResponsiveDetailGrid";
import { MediaCard } from "./MediaCard";
import { EndFrameRow } from "./EndFrameRow";
import { NarrationAudioCard } from "./NarrationAudioCard";
import { NotesDrawer } from "./NotesDrawer";
import { ReferencesSection } from "./ReferencesSection";
import { StatusBadge, statusFromAssets } from "./StatusBadge";
import { Popover } from "@/components/ui/Popover";
import { API } from "@/api";
import { useAppStore } from "@/stores/app-store";
import { isResourceBusy, isScriptFileBusy } from "@/stores/tasks-store";
import { useCostStore } from "@/stores/cost-store";
import { useProjectsStore } from "@/stores/projects-store";
import { errMsg } from "@/utils/async";
import {
  isStructuredImagePrompt,
  isStructuredVideoPrompt,
} from "@/utils/prompt-shape";
import { isContinuousIntegerRange } from "@/utils/duration_format";

type Segment = NarrationSegment | DramaScene | AdShot;
type DetailContentMode = "narration" | "drama" | "ad";
type ImagePromptValue = ImagePrompt | string;
type VideoPromptValue = VideoPrompt | string;

interface ReferenceAssetOption {
  key: string;
  kind: "character" | "scene" | "prop";
  name: string;
  label: string;
  role: string;
  path: string;
}

const MAX_VIDEO_REFERENCE_IMAGES = 9;
const MAX_VIDEO_REFERENCE_MEDIA = 3;

interface ShotDetailProps {
  segment: Segment;
  segmentId: string;
  contentMode: DetailContentMode;
  aspectRatio: "9:16" | "16:9";
  projectName: string;
  episode?: number;
  /** 当前剧集剧本文件名，分镜图/视频自主上传需要它定位剧本条目 */
  scriptFile?: string;
  isGridMode?: boolean;
  /** Total shot count for "1/N" indicator */
  selectedIndex: number;
  totalCount: number;
  onPrev: () => void;
  onNext: () => void;
  onUpdatePrompt?: (
    segmentId: string,
    fieldOrPatch: string | Record<string, unknown>,
    value?: unknown,
  ) => void | Promise<void>;
  /** ad 模式镜头顺序调整（向前/向后移动一位） */
  onMoveShot?: (shotId: string, direction: "earlier" | "later") => void | Promise<void>;
  /** 镜头重排请求在途，移动按钮禁用 */
  movePending?: boolean;
  onGenerateStoryboard?: (segmentId: string) => void;
  onGenerateVideo?: (segmentId: string) => void;
  onGenerateNarration?: (segmentId: string) => void;
  onRestoreStoryboard?: () => Promise<void> | void;
  onRestoreVideo?: () => Promise<void> | void;
  generatingStoryboard?: boolean;
  generatingVideo?: boolean;
  generatingNarration?: boolean;
  durationOptions?: number[];
  /** 已保存时长越界的成因判定；缺省时退回不区分成因的通用警告文案。 */
  durationWarningReason?: (seconds: number) => DurationOutOfRangeReason | null;
  keyframePrompt?: KeyframePrompt | null;
  keyframeFrame?: KeyframeImageFrame | null;
  keyframeExists?: boolean;
  savingKeyframePrompt?: boolean;
  generatingKeyframe?: boolean;
  startKeyframePrompt?: KeyframePrompt | null;
  startKeyframeFrame?: KeyframeImageFrame | null;
  startKeyframeExists?: boolean;
  savingStartKeyframePrompt?: boolean;
  generatingStartKeyframe?: boolean;
  onSaveKeyframePrompt?: (
    keyframeId: string,
    patch: { prompt: string; negative_prompt?: string },
  ) => void | Promise<void>;
  onCreateStartKeyframePrompt?: (segmentId: string) => void | Promise<void>;
  onGenerateKeyframe?: (keyframeId: string) => void | Promise<void>;
  videoPrompt?: VideoPromptPackItem | null;
  draftVideo?: DraftVideoFrame | null;
  savingVideoPrompt?: boolean;
  generatingDraftVideo?: boolean;
  onSaveVideoPrompt?: (
    videoId: string,
    patch: { prompt?: string; reference_pack?: VideoPromptPack },
  ) => void | Promise<void>;
  onGenerateDraftVideo?: (videoId: string) => void | Promise<void>;
}

function getNovelText(seg: Segment, mode: DetailContentMode): string {
  if (mode === "narration") return (seg as NarrationSegment).novel_text || "";
  return "";
}

function keyframeTaskActive(frame?: KeyframeImageFrame | null): boolean {
  return frame?.task_status === "queued" || frame?.task_status === "running" || frame?.task_status === "cancelling";
}

function draftVideoTaskActive(draftVideo?: DraftVideoFrame | null): boolean {
  return (
    draftVideo?.task_status === "queued" ||
    draftVideo?.task_status === "running" ||
    draftVideo?.task_status === "cancelling"
  );
}

function statusBadge(
  exists: boolean,
  taskStatus?: string | null,
): { labelKey: string; tone: "ready" | "active" | "failed" | "missing" } {
  if (exists) return { labelKey: "director_pipeline_status_ready", tone: "ready" };
  if (taskStatus === "queued") return { labelKey: "director_pipeline_status_queued", tone: "active" };
  if (taskStatus === "running" || taskStatus === "cancelling") {
    return { labelKey: "director_pipeline_status_running", tone: "active" };
  }
  if (taskStatus === "failed") return { labelKey: "director_pipeline_status_failed", tone: "failed" };
  return { labelKey: "director_pipeline_status_missing", tone: "missing" };
}

function pipelineBadgeStyle(tone: "ready" | "active" | "failed" | "missing"): React.CSSProperties {
  if (tone === "ready") {
    return { background: "oklch(0.34 0.09 155 / 0.35)", color: "oklch(0.82 0.12 155)" };
  }
  if (tone === "active") {
    return { background: "oklch(0.34 0.08 250 / 0.35)", color: "oklch(0.82 0.12 250)" };
  }
  if (tone === "failed") {
    return { background: "oklch(0.34 0.09 25 / 0.35)", color: "oklch(0.82 0.12 25)" };
  }
  return { background: "oklch(0.24 0.012 265 / 0.65)", color: "var(--color-text-4)" };
}

function isSubmittedReferenceImage(entry: VideoReferenceEntry): boolean {
  const submitAs = entry.submit_as || "reference_image";
  if (["start_image", "end_image", "review_only", "prompt_guidance"].includes(submitAs)) return false;
  if (["start_image", "end_image", "review_frame"].includes(entry.role || "")) return false;
  return !submitAs || ["reference_image", "reference_image_or_prompt_guidance"].includes(submitAs);
}

function mediaEntryUrl(entry: VideoReferenceEntry): string {
  return (entry.url || entry.path || "").trim();
}

function getReferenceImageUrl(
  projectName: string,
  path: string | null | undefined,
  fingerprint?: number | string | null,
): string | null {
  if (!path) return null;
  if (path.startsWith("_global_assets/")) {
    return API.getGlobalAssetUrl(path, fingerprint == null ? null : String(fingerprint));
  }
  return API.getFileUrl(projectName, path, fingerprint);
}

function buildReferenceAssetOptions(projectData?: ProjectData | null): ReferenceAssetOption[] {
  const options: ReferenceAssetOption[] = [];
  for (const [name, character] of Object.entries(projectData?.characters ?? {})) {
    if (character.reference_image) {
      options.push({
        key: `character:${name}:face`,
        kind: "character",
        name,
        label: "face",
        role: "character_face_closeup",
        path: character.reference_image,
      });
    }
    if (character.character_sheet) {
      options.push({
        key: `character:${name}:sheet`,
        kind: "character",
        name,
        label: "sheet",
        role: "character_turnaround",
        path: character.character_sheet,
      });
    }
    if (character.character_combined_sheet) {
      options.push({
        key: `character:${name}:combined`,
        kind: "character",
        name,
        label: "combined",
        role: "character_combined_sheet",
        path: character.character_combined_sheet,
      });
    }
  }
  for (const [name, scene] of Object.entries(projectData?.scenes ?? {})) {
    if (scene.scene_sheet) {
      options.push({
        key: `scene:${name}`,
        kind: "scene",
        name,
        label: "scene",
        role: "scene_reference",
        path: scene.scene_sheet,
      });
    }
  }
  for (const [name, prop] of Object.entries(projectData?.props ?? {})) {
    if (prop.prop_sheet) {
      options.push({
        key: `prop:${name}`,
        kind: "prop",
        name,
        label: "prop",
        role: "prop_reference",
        path: prop.prop_sheet,
      });
    }
  }
  return options;
}

function videoReferenceRoleLabel(role: string): string {
  const map: Record<string, string> = {
    motion_guide_grid: "9-grid motion guide",
    guide_reference: "motion guide",
    character_face_closeup: "character face",
    character_turnaround: "character sheet",
    character_combined_sheet: "character combined sheet",
    scene_reference: "scene reference",
    prop_reference: "prop reference",
    style_reference: "style reference",
    start_image: "start frame",
    end_image: "end frame",
    repair_start_image: "repair start frame",
    repair_end_image: "repair end frame",
  };
  return map[role] ?? role;
}

interface DraftState {
  image_prompt: ImagePromptValue;
  video_prompt: VideoPromptValue;
  /** 仅 ad 模式：一等口播文案草稿 */
  voiceover_text?: string;
  /** 仅 ad 模式：带货框架段落标签草稿 */
  section?: string;
  /** 仅 drama 模式：场景级有序发声序列草稿（台词 + 画外音） */
  utterances?: Utterance[];
}

// 字段集合稳定（ImagePrompt/VideoPrompt/string），JSON.stringify 即可作等值签名：
// 任何字段顺序差异都来自我们自己的 setter 或上游同一构造路径，键序一致。
const stableSig = (value: unknown): string => JSON.stringify(value ?? null);

// 稳定空 utterances 引用：缺省 / 非 drama 时统一指向同一常量，避免每次渲染新建 `[]`
// 让 upstreamSig memo 依赖失效而做无谓 stringify。UtteranceListEditor 只经 map/filter/spread
// 产出新数组、从不就地改写，故共享此常量安全。
const EMPTY_UTTERANCES: Utterance[] = [];

// voiceover 的 speaker 允许缺省或 null，两种写法语义等价（无说话人）。签名前归一：
// voiceover speaker 统一为 null、并固定键序，避免 `{}` 与 `{ speaker: null }` 判成不同，
// 否则上游把画外音字段规范化后 dirty 清不掉，切镜与生成会持续被禁用。
const canonicalUtterance = (u: Utterance): Utterance =>
  u.kind === "dialogue"
    ? { kind: "dialogue", speaker: u.speaker, text: u.text }
    : { kind: "voiceover", speaker: null, text: u.text };

const utterancesSig = (list: Utterance[]): string => stableSig(list.map(canonicalUtterance));

/** 由上游值构造干净草稿（useState 初始化 / 上游静默跟随 / 取消编辑三处共用）。 */
function baselineDraft(
  ip: ImagePromptValue,
  vp: VideoPromptValue,
  isAd: boolean,
  voiceover: string,
  section: string,
  isDrama: boolean,
  utterances: Utterance[],
): DraftState {
  return {
    image_prompt: ip,
    video_prompt: vp,
    ...(isAd ? { voiceover_text: voiceover, section } : {}),
    ...(isDrama ? { utterances } : {}),
  };
}

/** 草稿等值签名：与上游基线签名同键形状（漂移会让"干净草稿静默跟随上游"失效）。 */
function draftSig(d: DraftState, isAd: boolean, isDrama: boolean): string {
  return stableSig({
    ip: d.image_prompt,
    vp: d.video_prompt,
    ...(isAd ? { voiceover_text: d.voiceover_text ?? "", section: d.section ?? "" } : {}),
    ...(isDrama ? { utterances: (d.utterances ?? EMPTY_UTTERANCES).map(canonicalUtterance) } : {}),
  });
}

interface DurationPillProps {
  seconds: number;
  segmentId: string;
  projectName: string;
  /** 本集剧本文件名；宫格任务按它做 scriptFile 粒度的占用判定。 */
  scriptFile?: string;
  durationOptions: number[];
  durationWarningReason?: ShotDetailProps["durationWarningReason"];
  onUpdatePrompt?: ShotDetailProps["onUpdatePrompt"];
  /** 该镜头有分镜 / 视频任务在跑；置真时禁止改时长（在跑的任务已捕获旧值，改了两边就不一致）。 */
  busy?: boolean;
}

function DurationPill({
  seconds,
  segmentId,
  projectName,
  scriptFile,
  durationOptions,
  durationWarningReason,
  onUpdatePrompt,
  busy = false,
}: DurationPillProps) {
  const { t } = useTranslation("dashboard");
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLButtonElement>(null);

  // 拖动 slider 期间用本地 state 跟随；松手 / 失焦 / 键盘抬起时再提交一次
  // 避免 onChange 每像素一次 onUpdatePrompt 产生并发写请求 + 乱序落库
  const [draftSeconds, setDraftSeconds] = useState<number | null>(null);
  const displaySeconds = draftSeconds ?? seconds;
  // 提交时刻复核占用态：面板打开后任务可能才启动，只查打开/渲染时刻会留一个竞态窗口。
  // 走 tasks-store 的 isResourceBusy 新鲜读而非 busy prop——prop 反映的是上次渲染，
  // store 更新到重渲染提交之间用户仍可能点下去。命中则拒绝并给可见反馈（与立绘上传的
  // rejectIfAssetBusy 同口径）。
  const rejectIfBusy = useCallback(() => {
    // 宫格任务另按 scriptFile 判：它的 resource_id 是 grid_id，归不进按分镜 resource_id 的
    // 判定，而切割阶段会覆写本集内多个分镜、与改时长并发写同一份剧本。
    const stillBusy =
      busy ||
      isResourceBusy("storyboard", projectName, segmentId) ||
      isResourceBusy("video", projectName, segmentId) ||
      isScriptFileBusy("grid", scriptFile, projectName);
    if (!stillBusy) return false;
    useAppStore.getState().pushToast(t("duration_locked_generating"), "info");
    return true;
  }, [busy, projectName, segmentId, scriptFile, t]);

  const commitDraft = useCallback(() => {
    if (draftSeconds == null) return;
    if (rejectIfBusy()) {
      setDraftSeconds(null);
      return;
    }
    if (draftSeconds !== seconds) {
      void onUpdatePrompt?.(segmentId, "duration_seconds", draftSeconds);
    }
    setDraftSeconds(null);
  }, [draftSeconds, seconds, segmentId, onUpdatePrompt, rejectIfBusy]);

  const editable = !!onUpdatePrompt;
  const noOptions = durationOptions.length === 0;
  const locked = noOptions || busy;

  // 转入锁定态时真正清掉面板与草稿，而不只是遮蔽：只派生可见性的话，任务结束、locked 回到
  // false 时旧面板会自行重现，未提交的 slider 草稿也一起回来、可能被误写回。
  // 用「prop 变化时于渲染期调整 state」这一 React 官方模式，而不是 effect——后者多一个渲染
  // 周期，且踩 react-hooks/set-state-in-effect。
  const [prevLocked, setPrevLocked] = useState(locked);
  if (locked !== prevLocked) {
    setPrevLocked(locked);
    if (locked) {
      setOpen(false);
      setDraftSeconds(null);
    }
  }
  const isIncompatible =
    durationOptions.length > 0 && !durationOptions.includes(seconds);
  // 越界文案按成因分开：模型全集就不含该值才是「模型不支持」，被分辨率 / 参考图路径的联动约束
  // 收窄掉时说清是哪一条——用户据此改对应设置，而不是被引去以为模型换不了这个时长。
  // 与项目默认时长的三种提示同一套判定（见 useModelCapabilities.durationOutOfRangeReason）。
  const incompatibleKey = {
    model: "duration_incompatible_warning",
    resolution: "duration_incompatible_resolution_warning",
    reference: "duration_incompatible_reference_warning",
  }[durationWarningReason?.(seconds) ?? "model"];
  const incompatibleLabel = t(incompatibleKey, {
    value: seconds,
    supported: durationOptions.join(", "),
  });
  const useSlider =
    isContinuousIntegerRange(durationOptions) && durationOptions.length >= 5;

  const baseClass =
    "inline-flex items-center gap-1.5 rounded-md px-2 py-[3px] text-[11.5px] focus-ring";
  const baseStyle: React.CSSProperties = {
    background: isIncompatible
      ? "oklch(0.32 0.10 75 / 0.35)"
      : "oklch(0.22 0.011 265 / 0.6)",
    border: isIncompatible
      ? "1px solid oklch(0.65 0.12 75 / 0.5)"
      : "1px solid var(--color-hairline-soft)",
    color: isIncompatible ? "oklch(0.85 0.12 80)" : "var(--color-text-2)",
  };

  if (!editable) {
    return (
      <span className={baseClass} style={baseStyle}>
        <span style={{ color: "var(--color-text-4)" }}>⏱</span>
        <span className="num">
          {t("duration_seconds_value_text", { value: seconds })}
        </span>
        {isIncompatible && (
          <span aria-label={incompatibleLabel} title={incompatibleLabel}>
            ⚠
          </span>
        )}
      </span>
    );
  }

  return (
    <>
      <button
        ref={ref}
        type="button"
        onClick={() => {
          if (locked) return;
          if (!open && rejectIfBusy()) return;
          setOpen((o) => !o);
        }}
        disabled={locked}
        aria-disabled={locked || undefined}
        title={
          busy
            ? t("duration_locked_generating")
            : noOptions
              ? t("duration_no_options")
              : undefined
        }
        className={`${baseClass} transition-colors disabled:cursor-not-allowed disabled:opacity-60`}
        style={baseStyle}
      >
        <span style={{ color: "var(--color-text-4)" }}>⏱</span>
        <span className="num">
          {t("duration_seconds_value_text", { value: seconds })}
        </span>
        {isIncompatible && (
          <span aria-label={incompatibleLabel} title={incompatibleLabel}>
            ⚠
          </span>
        )}
      </button>
      <Popover
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={ref}
        width="w-auto"
        align="start"
        sideOffset={6}
        backgroundColor="oklch(0.21 0.012 265 / 0.98)"
        className="rounded-lg p-2"
        style={{
          border: "1px solid var(--color-hairline)",
          boxShadow:
            "0 24px 60px -20px oklch(0 0 0 / 0.7), 0 0 0 1px var(--color-hairline-soft)",
          backdropFilter: "blur(12px)",
          WebkitBackdropFilter: "blur(12px)",
        }}
      >
        {useSlider ? (
          <div className="flex items-center gap-2 px-1 py-1">
            <input
              type="range"
              aria-label={t("duration_selector_aria")}
              aria-valuetext={t("duration_seconds_value_text", { value: displaySeconds })}
              min={durationOptions[0]}
              max={durationOptions[durationOptions.length - 1]}
              step={1}
              value={displaySeconds}
              onChange={(e) => setDraftSeconds(parseInt(e.target.value, 10))}
              onPointerUp={commitDraft}
              onKeyUp={(e) => {
                if (
                  e.key === "ArrowLeft" ||
                  e.key === "ArrowRight" ||
                  e.key === "ArrowUp" ||
                  e.key === "ArrowDown" ||
                  e.key === "Home" ||
                  e.key === "End" ||
                  e.key === "PageUp" ||
                  e.key === "PageDown"
                ) {
                  commitDraft();
                }
              }}
              onBlur={commitDraft}
              className="theme-slider w-40"
            />
            <span
              className="num min-w-[2.25rem] text-right text-[11.5px]"
              style={{ color: "var(--color-text-2)" }}
            >
              {t("duration_seconds_value_text", { value: displaySeconds })}
            </span>
          </div>
        ) : (
          <div
            className="flex flex-wrap gap-1"
            role="radiogroup"
            aria-label={t("duration_selector_aria")}
          >
            {durationOptions.map((d) => {
              const checked = d === seconds;
              return (
                <button
                  key={d}
                  role="radio"
                  type="button"
                  aria-checked={checked}
                  onClick={() => {
                    // 与 commitDraft 同口径：提交时刻再复核一次，不吃面板打开后才启动的任务。
                    if (rejectIfBusy()) {
                      setOpen(false);
                      return;
                    }
                    void onUpdatePrompt(segmentId, "duration_seconds", d);
                    setOpen(false);
                  }}
                  className="num rounded-md px-2.5 py-1 text-[11.5px] font-medium transition-colors focus-ring"
                  style={
                    checked
                      ? {
                          background:
                            "linear-gradient(180deg, var(--color-accent-2), var(--color-accent))",
                          color: "oklch(0.14 0 0)",
                          boxShadow:
                            "inset 0 1px 0 oklch(1 0 0 / 0.25), 0 2px 6px -2px var(--color-accent-glow)",
                        }
                      : {
                          background: "oklch(0.22 0.011 265 / 0.5)",
                          color: "var(--color-text-2)",
                          border: "1px solid var(--color-hairline-soft)",
                        }
                  }
                >
                  {t("duration_seconds_value_text", { value: d })}
                </button>
              );
            })}
          </div>
        )}
      </Popover>
    </>
  );
}

function DirectorPipelineMediaCard({
  kind,
  title,
  projectName,
  assetPath,
  posterPath,
  aspectRatio,
  generating,
  disabled,
  disabledHint,
  emptyLabel,
  generateLabel,
  onGenerate,
}: {
  kind: "image" | "video";
  title: string;
  projectName: string;
  assetPath?: string | null;
  posterPath?: string | null;
  aspectRatio: "9:16" | "16:9";
  generating?: boolean;
  disabled?: boolean;
  disabledHint?: string;
  emptyLabel: string;
  generateLabel: string;
  onGenerate?: () => void | Promise<void>;
}) {
  const { t } = useTranslation("dashboard");
  const assetFp = useProjectsStore((s) =>
    assetPath ? s.getAssetFingerprint(assetPath) : null,
  );
  const posterFp = useProjectsStore((s) =>
    posterPath ? s.getAssetFingerprint(posterPath) : null,
  );
  const assetUrl = assetPath ? API.getFileUrl(projectName, assetPath, assetFp) : null;
  const posterUrl = posterPath ? API.getFileUrl(projectName, posterPath, posterFp) : null;
  const Icon = kind === "image" ? ImageIcon : Film;

  return (
    <div>
      <div className="mb-2 flex items-center gap-1.5">
        <Icon className="h-3.5 w-3.5" style={{ color: "var(--color-text-3)" }} />
        <span className="text-[12px] font-semibold" style={{ color: "var(--color-text-2)" }}>
          {title}
        </span>
      </div>
      {assetUrl ? (
        kind === "image" ? (
          <div
            className="overflow-hidden rounded-[10px]"
            style={{
              boxShadow:
                "0 16px 40px -16px oklch(0 0 0 / 0.7), 0 0 0 1px var(--color-hairline)",
            }}
          >
            <img src={assetUrl} alt={title} className="h-auto w-full object-contain" loading="lazy" />
          </div>
        ) : (
          <div
            className="overflow-hidden rounded-[10px]"
            style={{
              boxShadow:
                "0 16px 40px -16px oklch(0 0 0 / 0.7), 0 0 0 1px var(--color-hairline)",
            }}
          >
            <div
              className={aspectRatio === "9:16" ? "aspect-[9/16]" : "aspect-video"}
              style={{ background: "oklch(0.13 0.010 265 / 0.72)" }}
            >
              {/* eslint-disable-next-line jsx-a11y/media-has-caption -- generated preview videos do not have caption tracks */}
              <video
                src={assetUrl}
                poster={posterUrl ?? undefined}
                controls
                playsInline
                preload="metadata"
                className="h-full w-full object-contain"
              />
            </div>
          </div>
        )
      ) : (
        <div className={aspectRatio === "9:16" ? "aspect-[9/16]" : "aspect-video"}>
          <div
            className="flex h-full w-full flex-col items-center justify-center gap-2 rounded-[10px]"
            style={{
              border: "1px dashed var(--color-hairline)",
              background: "oklch(0.18 0.010 265 / 0.4)",
              color: "var(--color-text-4)",
            }}
          >
            <Icon className="h-5 w-5" />
            <span className="px-3 text-center text-[11.5px] leading-4">{emptyLabel}</span>
          </div>
        </div>
      )}
      {onGenerate && (
        <button
          type="button"
          onClick={() => void onGenerate()}
          disabled={disabled || generating}
          title={disabled ? disabledHint : undefined}
          className="mt-2.5 inline-flex w-full items-center justify-center gap-1.5 rounded-[10px] px-3 py-2.5 text-[12.5px] font-semibold transition-opacity focus-ring disabled:cursor-not-allowed disabled:opacity-50"
          style={{
            color: "oklch(0.14 0 0)",
            background: "linear-gradient(180deg, var(--color-accent-2), var(--color-accent))",
            boxShadow:
              "inset 0 1px 0 oklch(1 0 0 / 0.3), 0 4px 14px -4px var(--color-accent-glow)",
          }}
        >
          {generating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Icon className="h-3.5 w-3.5" />}
          <span>{generating ? t("director_pipeline_generating") : generateLabel}</span>
        </button>
      )}
    </div>
  );
}

function DirectorPromptSection({
  title,
  statusLabel,
  statusTone,
  prompt,
  negativePrompt,
  promptPlaceholder,
  dirty,
  saving,
  generating,
  generated,
  saveLabel,
  regenerateLabel,
  generateLabel,
  generationError,
  onPromptChange,
  onNegativePromptChange,
  onSave,
  onGenerate,
}: {
  title: string;
  statusLabel: string;
  statusTone: "ready" | "active" | "failed" | "missing";
  prompt: string;
  negativePrompt: string;
  promptPlaceholder: string;
  dirty?: boolean;
  saving?: boolean;
  generating?: boolean;
  generated?: boolean;
  saveLabel: string;
  regenerateLabel: string;
  generateLabel: string;
  generationError?: string | null;
  onPromptChange: (value: string) => void;
  onNegativePromptChange: (value: string) => void;
  onSave?: () => void | Promise<void>;
  onGenerate?: () => void | Promise<void>;
}) {
  const { t } = useTranslation("dashboard");

  return (
    <section>
      <div className="mb-2 flex items-center gap-1.5">
        <ImageIcon className="h-3.5 w-3.5" style={{ color: "var(--color-accent)" }} />
        <span className="text-[12.5px] font-semibold" style={{ color: "var(--color-text-2)" }}>
          {title}
        </span>
        <span
          className="rounded px-1.5 py-0.5 font-mono text-[10px]"
          style={pipelineBadgeStyle(statusTone)}
        >
          {statusLabel}
        </span>
        <span className="flex-1" />
        <span className="num text-[10px]" style={{ color: "var(--color-text-4)" }}>
          {t("detail_field_chars_count", { count: prompt.length })}
        </span>
      </div>
      <textarea
        className="prompt-ta"
        value={prompt}
        onChange={(event) => onPromptChange(event.target.value)}
        placeholder={promptPlaceholder}
        style={{ minHeight: 220 }}
      />
      <textarea
        className="prompt-ta mt-2"
        value={negativePrompt}
        onChange={(event) => onNegativePromptChange(event.target.value)}
        placeholder={t("director_negative_prompt_placeholder")}
        style={{ minHeight: 72 }}
      />
      {generationError && (
        <div
          className="mt-2 rounded border px-2 py-1 text-[11px] leading-4"
          style={{
            borderColor: "oklch(0.5 0.12 25 / 0.35)",
            background: "oklch(0.24 0.08 25 / 0.22)",
            color: "oklch(0.82 0.12 25)",
          }}
        >
          {generationError}
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-2">
        {onSave && (
          <button
            type="button"
            disabled={!dirty || saving}
            onClick={() => void onSave()}
            className="sv-navbtn inline-flex items-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
            <span>{saving ? t("director_prompt_saving") : saveLabel}</span>
          </button>
        )}
        {onGenerate && (
          <button
            type="button"
            disabled={dirty || generating}
            title={dirty ? t("director_prompt_save_first") : undefined}
            onClick={() => void onGenerate()}
            className="sv-navbtn inline-flex items-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {generating ? <Loader2 className="h-3 w-3 animate-spin" /> : <ImageIcon className="h-3 w-3" />}
            <span>{generating ? statusLabel : generated ? regenerateLabel : generateLabel}</span>
          </button>
        )}
      </div>
    </section>
  );
}

function VideoReferencePackPanel({
  projectName,
  pack,
  startImagePath,
  dirty,
  saving,
  assetOptions,
  getFingerprint,
  onSave,
  onRemoveImage,
  onAddAsset,
  onAddMedia,
  onRemoveMedia,
}: {
  projectName: string;
  pack?: VideoPromptPack | null;
  startImagePath?: string | null;
  dirty?: boolean;
  saving?: boolean;
  assetOptions: ReferenceAssetOption[];
  getFingerprint: (path: string | null | undefined) => number | string | null;
  onSave: () => void | Promise<void>;
  onRemoveImage: (index: number) => void | Promise<void>;
  onAddAsset: (option: ReferenceAssetOption) => void | Promise<void>;
  onAddMedia: (kind: "video" | "audio", url: string) => void | Promise<void>;
  onRemoveMedia: (kind: "video" | "audio", index: number) => void | Promise<void>;
}) {
  const { t } = useTranslation("dashboard");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [videoUrlDraft, setVideoUrlDraft] = useState("");
  const [audioUrlDraft, setAudioUrlDraft] = useState("");
  const selected = pack?.selected_images ?? [];
  const selectedVideos = pack?.selected_videos ?? [];
  const selectedAudios = pack?.selected_audios ?? [];
  const selectedPaths = new Set(selected.map((entry) => entry.path || "").filter(Boolean));
  const referenceImageCount = selected.filter(isSubmittedReferenceImage).length;
  const startImageCount = startImagePath ? 1 : 0;
  const totalImageCount = startImageCount + referenceImageCount;
  const canAddMore = totalImageCount < MAX_VIDEO_REFERENCE_IMAGES;
  const canAddVideo = selectedVideos.length < MAX_VIDEO_REFERENCE_MEDIA;
  const canAddAudio = selectedAudios.length < MAX_VIDEO_REFERENCE_MEDIA;
  const submitMedia = (kind: "video" | "audio") => {
    const value = (kind === "video" ? videoUrlDraft : audioUrlDraft).trim();
    if (!value) return;
    void onAddMedia(kind, value);
    if (kind === "video") setVideoUrlDraft("");
    else setAudioUrlDraft("");
  };

  return (
    <section
      className="mt-3 rounded-lg p-3"
      style={{
        background: "oklch(0.18 0.010 265 / 0.42)",
        border: "1px solid var(--color-hairline-soft)",
      }}
    >
      <div className="mb-2 flex items-center justify-between gap-2">
        <div className="text-[12px] font-semibold text-[var(--color-text-2)]">
          {t("director_reference_pack_title")}
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void onSave()}
            disabled={!dirty || saving}
            className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10.5px] font-medium transition-colors focus-ring disabled:cursor-not-allowed disabled:opacity-45"
            style={{
              background: dirty ? "oklch(0.27 0.075 145 / 0.72)" : "oklch(0.20 0.012 265 / 0.6)",
              color: dirty ? "oklch(0.82 0.13 145)" : "var(--color-text-4)",
              border: dirty ? "1px solid oklch(0.46 0.10 145 / 0.45)" : "1px solid var(--color-hairline-soft)",
            }}
          >
            {saving ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
            {t("director_reference_pack_save")}
          </button>
          <button
            type="button"
            onClick={() => setPickerOpen((open) => !open)}
            disabled={!canAddMore}
            className="inline-flex items-center gap-1 rounded-full px-2 py-1 text-[10.5px] font-medium transition-colors focus-ring disabled:cursor-not-allowed disabled:opacity-45"
            style={{
              background: "oklch(0.24 0.055 255 / 0.65)",
              color: "oklch(0.82 0.10 250)",
              border: "1px solid oklch(0.44 0.09 250 / 0.45)",
            }}
          >
            <Plus className="h-3 w-3" />
            {t("director_reference_pack_add_image")}
          </button>
          <div className="num text-[10px] text-[var(--color-text-4)]">
            {t("director_reference_pack_count", {
              start: startImageCount,
              refs: referenceImageCount,
              total: totalImageCount,
              max: MAX_VIDEO_REFERENCE_IMAGES,
            })}
          </div>
        </div>
      </div>

      {pickerOpen && (
        <div
          className="mb-2 rounded-lg p-2"
          style={{
            background: "oklch(0.14 0.012 265 / 0.72)",
            border: "1px solid var(--color-hairline-soft)",
          }}
        >
          {assetOptions.length > 0 ? (
            <div className="grid max-h-56 grid-cols-2 gap-2 overflow-y-auto pr-1">
              {assetOptions.map((option) => {
                const src = getReferenceImageUrl(projectName, option.path, getFingerprint(option.path));
                const duplicate = selectedPaths.has(option.path);
                return (
                  <button
                    key={option.key}
                    type="button"
                    disabled={duplicate || !canAddMore}
                    onClick={() => void onAddAsset(option)}
                    className="group flex min-w-0 items-center gap-2 rounded-md p-1.5 text-left transition-colors focus-ring disabled:cursor-not-allowed disabled:opacity-45"
                    style={{
                      background: duplicate ? "oklch(0.18 0.010 265 / 0.45)" : "oklch(0.20 0.014 265 / 0.78)",
                      border: "1px solid var(--color-hairline-soft)",
                    }}
                  >
                    {src ? (
                      <img
                        src={src}
                        alt={`${option.name} ${option.label}`}
                        className="h-10 w-10 shrink-0 rounded object-cover"
                        style={{ border: "1px solid var(--color-hairline-soft)" }}
                      />
                    ) : (
                      <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded text-[10px] text-[var(--color-text-4)]">
                        {t("director_reference_pack_no_image")}
                      </div>
                    )}
                    <span className="min-w-0">
                      <span className="block truncate text-[11px] font-medium text-[var(--color-text-2)]">
                        {option.name}
                      </span>
                      <span className="block truncate text-[10px] text-[var(--color-text-4)]">
                        {option.label}
                        {duplicate ? ` · ${t("director_reference_pack_added")}` : ""}
                      </span>
                    </span>
                  </button>
                );
              })}
            </div>
          ) : (
            <div className="rounded border border-dashed border-gray-800 px-2 py-3 text-center text-[11px] text-[var(--color-text-4)]">
              {t("director_reference_pack_asset_empty")}
            </div>
          )}
        </div>
      )}

      {selected.length > 0 ? (
        <div className="grid grid-cols-3 gap-2">
          {selected.map((entry, index) => {
            const src = getReferenceImageUrl(projectName, entry.path, getFingerprint(entry.path));
            const label = videoReferenceRoleLabel(entry.role);
            return (
              <div
                key={`${entry.path ?? "missing"}-${index}`}
                className="group relative overflow-hidden rounded-md"
                style={{
                  border: "1px solid var(--color-hairline-soft)",
                  background: "oklch(0.15 0.010 265 / 0.6)",
                }}
              >
                {src ? (
                  <div className="aspect-square">
                    <img src={src} alt={label} className="h-full w-full object-cover" />
                  </div>
                ) : (
                  <div className="flex aspect-square items-center justify-center text-[10px] text-[var(--color-text-4)]">
                    {t("director_reference_pack_no_image")}
                  </div>
                )}
                <div className="p-1.5">
                  <div className="truncate text-[10.5px] font-medium text-[var(--color-text-2)]">{label}</div>
                  <div className="truncate font-mono text-[9.5px] text-[var(--color-text-4)]">
                    {entry.path || t("director_reference_pack_path_missing")}
                  </div>
                </div>
                <button
                  type="button"
                  aria-label={t("director_reference_pack_remove_image")}
                  onClick={() => void onRemoveImage(index)}
                  className="absolute right-1 top-1 rounded-full p-1 opacity-85 transition-opacity hover:opacity-100 focus-ring"
                  style={{
                    background: "oklch(0.12 0.010 265 / 0.82)",
                    color: "var(--color-text-2)",
                    border: "1px solid var(--color-hairline)",
                  }}
                >
                  <X className="h-3 w-3" />
                </button>
              </div>
            );
          })}
        </div>
      ) : (
        <div className="rounded border border-dashed border-gray-800 px-2 py-3 text-center text-[11px] text-[var(--color-text-4)]">
          {t("director_reference_pack_empty")}
        </div>
      )}

      <div className="mt-3 grid gap-2">
        {(["video", "audio"] as const).map((kind) => {
          const items = kind === "video" ? selectedVideos : selectedAudios;
          const draftValue = kind === "video" ? videoUrlDraft : audioUrlDraft;
          const canAdd = kind === "video" ? canAddVideo : canAddAudio;
          return (
            <div
              key={kind}
              className="rounded-lg p-2"
              style={{
                background: "oklch(0.14 0.012 265 / 0.55)",
                border: "1px solid var(--color-hairline-soft)",
              }}
            >
              <div className="mb-1.5 flex items-center justify-between text-[11px]">
                <span className="font-medium text-[var(--color-text-2)]">
                  {kind === "video" ? t("director_reference_video_url") : t("director_reference_audio_url")}
                </span>
                <span className="num text-[10px] text-[var(--color-text-4)]">{items.length}/3</span>
              </div>
              <div className="flex gap-1.5">
                <input
                  value={draftValue}
                  onChange={(event) =>
                    kind === "video"
                      ? setVideoUrlDraft(event.target.value)
                      : setAudioUrlDraft(event.target.value)
                  }
                  placeholder={kind === "video" ? "https://...mp4" : "https://...mp3 / wav"}
                  className="min-w-0 flex-1 rounded-md bg-black/25 px-2 py-1 text-[11px] text-[var(--color-text-2)] outline-none focus-ring"
                  style={{ border: "1px solid var(--color-hairline-soft)" }}
                />
                <button
                  type="button"
                  disabled={!canAdd || !draftValue.trim()}
                  onClick={() => submitMedia(kind)}
                  className="rounded-md px-2 py-1 text-[10.5px] disabled:cursor-not-allowed disabled:opacity-45"
                  style={{
                    background: "oklch(0.24 0.055 255 / 0.65)",
                    color: "oklch(0.82 0.10 250)",
                    border: "1px solid oklch(0.44 0.09 250 / 0.45)",
                  }}
                >
                  {t("director_reference_pack_add")}
                </button>
              </div>
              {items.length > 0 && (
                <div className="mt-1.5 space-y-1">
                  {items.map((entry, index) => (
                    <div
                      key={`${mediaEntryUrl(entry)}-${index}`}
                      className="flex items-center gap-1.5 rounded bg-black/20 px-2 py-1 text-[10px]"
                    >
                      <span className="min-w-0 flex-1 truncate font-mono text-[var(--color-text-4)]">
                        {mediaEntryUrl(entry)}
                      </span>
                      <button
                        type="button"
                        onClick={() => void onRemoveMedia(kind, index)}
                        className="text-[var(--color-text-3)] hover:text-[var(--color-text-1)]"
                      >
                        {t("delete")}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}

export function ShotDetail({
  segment,
  segmentId,
  contentMode,
  aspectRatio,
  projectName,
  episode,
  scriptFile,
  isGridMode,
  selectedIndex,
  totalCount,
  onPrev,
  onNext,
  onUpdatePrompt,
  onMoveShot,
  movePending,
  onGenerateStoryboard,
  onGenerateVideo,
  onGenerateNarration,
  onRestoreStoryboard,
  onRestoreVideo,
  generatingStoryboard,
  generatingVideo,
  generatingNarration,
  durationOptions = [],
  durationWarningReason,
  keyframePrompt,
  keyframeFrame,
  keyframeExists,
  savingKeyframePrompt,
  generatingKeyframe,
  startKeyframePrompt,
  startKeyframeFrame,
  startKeyframeExists,
  savingStartKeyframePrompt,
  generatingStartKeyframe,
  onSaveKeyframePrompt,
  onCreateStartKeyframePrompt,
  onGenerateKeyframe,
  videoPrompt,
  draftVideo,
  savingVideoPrompt,
  generatingDraftVideo,
  onSaveVideoPrompt,
  onGenerateDraftVideo,
}: ShotDetailProps) {
  const { t } = useTranslation("dashboard");
  const status = statusFromAssets(segment.generated_assets?.status);
  const novelText = getNovelText(segment, contentMode);
  const hasNarrationText = novelText.trim().length > 0;
  const segCost = useCostStore((s) => s.getSegmentCost(segmentId));
  // 尾帧能力按项目级视频后端解析：后端换了，门控要跟着换。
  const videoBackend = useProjectsStore((s) => s.currentProjectData?.video_backend ?? null);
  const currentProjectData = useProjectsStore((s) =>
    s.currentProjectName === projectName ? s.currentProjectData : null,
  );
  const assetFingerprints = useProjectsStore((s) => s.assetFingerprints);

  const ip = segment.image_prompt;
  const vp = segment.video_prompt;
  const note = segment.note ?? "";
  const isAd = contentMode === "ad";
  const adShot = isAd ? (segment as AdShot) : null;
  const upstreamVoiceover = adShot?.voiceover_text ?? "";
  const upstreamSection = adShot?.section ?? "";
  const isDrama = contentMode === "drama";
  const dramaScene = isDrama ? (segment as DramaScene) : null;
  // drama 场景级发声序列（迁移后存量数据可能缺省，读到空即无发声）。
  const upstreamUtterances = dramaScene?.utterances ?? EMPTY_UTTERANCES;

  // 草稿：本地编辑直到用户点击 Save。父级 ShotSplitView 通过 key={segmentId}
  // 在切镜头时硬重置整个组件，所以这里只需处理"上游同字段静默更新"的情况。
  // 备注不进入草稿，由 NotesDrawer 收起时直接落库。
  const [draft, setDraft] = useState<DraftState>(() =>
    baselineDraft(ip, vp, isAd, upstreamVoiceover, upstreamSection, isDrama, upstreamUtterances),
  );
  const [saving, setSaving] = useState(false);
  const [uploadingKind, setUploadingKind] = useState<"storyboard" | "video" | null>(null);
  const [endFrameSubmitting, setEndFrameSubmitting] = useState(false);

  const handleUpload = async (kind: "storyboard" | "video", file: File) => {
    // 单镜头同时只允许一个上传：两张卡写同一后端资源族，避免并发覆写
    if (!scriptFile || uploadingKind) return;
    setUploadingKind(kind);
    try {
      const result = await API.uploadShotMedia(projectName, scriptFile, segmentId, kind, file);
      useProjectsStore.getState().updateAssetFingerprints(result.asset_fingerprints);
      // 复用版本恢复的刷新管线（refreshProject 等由父级回调承载）
      if (kind === "storyboard") {
        await onRestoreStoryboard?.();
      } else {
        await onRestoreVideo?.();
      }
      useAppStore
        .getState()
        .pushToast(t("media_upload_success", { id: segmentId }), "success");
    } catch (err) {
      useAppStore
        .getState()
        .pushToast(t("media_upload_failed", { message: errMsg(err) }), "error");
    } finally {
      setUploadingKind(null);
    }
  };

  const upstreamSig = useMemo(
    () =>
      draftSig(
        baselineDraft(ip, vp, isAd, upstreamVoiceover, upstreamSection, isDrama, upstreamUtterances),
        isAd,
        isDrama,
      ),
    [isAd, ip, vp, upstreamVoiceover, upstreamSection, isDrama, upstreamUtterances],
  );
  // 上游发声序列签名单独记忆化：dirtyPatch 随每次 keystroke 重算，
  // 但上游极少变，避免逐键重复序列化整个 upstreamUtterances。
  const upstreamUtterancesSig = useMemo(() => utterancesSig(upstreamUtterances), [upstreamUtterances]);
  // 上游变更（保存完成 / agent 编辑）：草稿干净时静默跟随；脏时保留用户输入。
  // 渲染阶段状态同步（React 推荐）：本次渲染内直接比对上游签名并校正草稿，
  // 免去 useEffect 的额外渲染周期与依赖项管理。draft 直接读当前渲染值，无需 ref 镜像。
  const [syncedUpstreamSig, setSyncedUpstreamSig] = useState(upstreamSig);
  if (syncedUpstreamSig !== upstreamSig) {
    if (draftSig(draft, isAd, isDrama) === syncedUpstreamSig) {
      setDraft(baselineDraft(ip, vp, isAd, upstreamVoiceover, upstreamSection, isDrama, upstreamUtterances));
    }
    setSyncedUpstreamSig(upstreamSig);
  }

  // 引用相等优先：未编辑过的字段直接跳过 stringify。
  const dirtyPatch = useMemo<Record<string, unknown>>(() => {
    const patch: Record<string, unknown> = {};
    if (
      draft.image_prompt !== ip &&
      stableSig(draft.image_prompt) !== stableSig(ip)
    )
      patch.image_prompt = draft.image_prompt;
    if (
      draft.video_prompt !== vp &&
      stableSig(draft.video_prompt) !== stableSig(vp)
    )
      patch.video_prompt = draft.video_prompt;
    if (isAd) {
      if ((draft.voiceover_text ?? "") !== upstreamVoiceover)
        patch.voiceover_text = draft.voiceover_text ?? "";
      if ((draft.section ?? "") !== upstreamSection)
        patch.section = draft.section ?? "";
    }
    if (isDrama) {
      const draftUtterances = draft.utterances ?? EMPTY_UTTERANCES;
      if (draftUtterances !== upstreamUtterances && utterancesSig(draftUtterances) !== upstreamUtterancesSig)
        patch.utterances = draftUtterances;
    }
    return patch;
  }, [draft, ip, vp, isAd, upstreamVoiceover, upstreamSection, isDrama, upstreamUtterances, upstreamUtterancesSig]);

  const dirty = Object.keys(dirtyPatch).length > 0;


  const isStructIp = isStructuredImagePrompt(draft.image_prompt);
  const isStructVp = isStructuredVideoPrompt(draft.video_prompt);
  const imgDraft: ImagePrompt | null = isStructIp
    ? (draft.image_prompt as ImagePrompt)
    : null;
  const vidDraft: VideoPrompt | null = isStructVp
    ? (draft.video_prompt as VideoPrompt)
    : null;

  const handleImgUpdate = (patch: Partial<ImagePrompt>) => {
    setDraft((d) => {
      if (!isStructuredImagePrompt(d.image_prompt)) return d;
      const merged: ImagePrompt = {
        ...d.image_prompt,
        ...patch,
        composition: {
          ...d.image_prompt.composition,
          ...(patch.composition ?? {}),
        },
      };
      return { ...d, image_prompt: merged };
    });
  };

  const handleVidUpdate = (patch: Partial<VideoPrompt>) => {
    setDraft((d) => {
      if (!isStructuredVideoPrompt(d.video_prompt)) return d;
      const merged: VideoPrompt = { ...d.video_prompt, ...patch };
      return { ...d, video_prompt: merged };
    });
  };

  const handleDialogueChange = (dialogue: Dialogue[]) => {
    handleVidUpdate({ dialogue });
  };

  const handleUtterancesChange = (utterances: Utterance[]) => {
    setDraft((d) => ({ ...d, utterances }));
  };

  const handleImgStringChange = (val: string) => {
    setDraft((d) => ({ ...d, image_prompt: val }));
  };

  const handleVidStringChange = (val: string) => {
    setDraft((d) => ({ ...d, video_prompt: val }));
  };

  const handleNotesCommit = (value: string) => {
    if (value === note) return;
    void onUpdatePrompt?.(segmentId, "note", value);
  };

  const handleSave = async () => {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      await onUpdatePrompt?.(segmentId, dirtyPatch);
      // 上游会刷新 → 渲染阶段同步检测到上游签名变化 → 草稿等于新基线时保持干净
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    if (saving) return;
    setDraft(baselineDraft(ip, vp, isAd, upstreamVoiceover, upstreamSection, isDrama, upstreamUtterances));
  };

  const sbEstimate = segCost?.estimate?.image;
  const vidEstimate = segCost?.estimate?.video;
  const narrationEstimate = segCost?.estimate?.audio;

  const assets = segment.generated_assets;
  const hasStoryboard = !!assets?.storyboard_image;
  const keyframeReady = !!keyframeExists || !!keyframeFrame?.exists;
  const keyframeActive = !!generatingKeyframe || keyframeTaskActive(keyframeFrame);
  const startKeyframeReady = !!startKeyframeExists || !!startKeyframeFrame?.exists;
  const startKeyframeActive = !!generatingStartKeyframe || keyframeTaskActive(startKeyframeFrame);
  const draftVideoReady = !!draftVideo?.exists;
  const draftVideoActive = !!generatingDraftVideo || draftVideoTaskActive(draftVideo);
  const keyframeStatus = statusBadge(keyframeReady, keyframeFrame?.task_status);
  const startKeyframeStatus = statusBadge(startKeyframeReady, startKeyframeFrame?.task_status);
  const draftVideoStatus = statusBadge(draftVideoReady, draftVideo?.task_status);
  const keyframeImagePath = keyframeReady ? keyframeFrame?.file_path : null;
  const shouldShowVideoStartImageCard =
    !!videoPrompt &&
    (!!startKeyframePrompt || keyframePrompt?.role === "guide_reference") &&
    startKeyframePrompt?.keyframe_id !== keyframePrompt?.keyframe_id;
  const startKeyframeImagePath =
    videoPrompt?.start_image_status === "ready" && videoPrompt.start_image
      ? videoPrompt.start_image
      : startKeyframeReady
        ? startKeyframeFrame?.file_path
        : null;
  const directorPipelineAvailable = !!keyframePrompt || !!videoPrompt || !!draftVideo;
  const [keyframePromptDraft, setKeyframePromptDraft] = useState(keyframePrompt?.prompt ?? "");
  const [keyframeNegativeDraft, setKeyframeNegativeDraft] = useState(keyframePrompt?.negative_prompt ?? "");
  const [startKeyframePromptDraft, setStartKeyframePromptDraft] = useState(startKeyframePrompt?.prompt ?? "");
  const [startKeyframeNegativeDraft, setStartKeyframeNegativeDraft] = useState(startKeyframePrompt?.negative_prompt ?? "");
  const [directorVideoPromptDraft, setDirectorVideoPromptDraft] = useState(videoPrompt?.prompt ?? "");
  const [referencePackDraft, setReferencePackDraft] = useState<VideoPromptPack>(
    videoPrompt?.reference_pack ?? { selected_images: [] },
  );
  const [optimizingVideoPrompt, setOptimizingVideoPrompt] = useState(false);
  const [videoPromptOptimizeNote, setVideoPromptOptimizeNote] = useState<string | null>(null);
  const keyframeSourceDraftSig = stableSig({
    prompt: keyframePrompt?.prompt ?? "",
    negative_prompt: keyframePrompt?.negative_prompt ?? "",
  });
  const keyframeSourceSig = stableSig({
    keyframe_id: keyframePrompt?.keyframe_id ?? null,
    source: keyframeSourceDraftSig,
  });
  const keyframeCurrentDraftSig = stableSig({
    prompt: keyframePromptDraft,
    negative_prompt: keyframeNegativeDraft,
  });
  const [syncedKeyframePrompt, setSyncedKeyframePrompt] = useState({
    sourceSig: keyframeSourceSig,
    draftSig: keyframeSourceDraftSig,
  });
  if (syncedKeyframePrompt.sourceSig !== keyframeSourceSig) {
    if (keyframeCurrentDraftSig === syncedKeyframePrompt.draftSig) {
      setKeyframePromptDraft(keyframePrompt?.prompt ?? "");
      setKeyframeNegativeDraft(keyframePrompt?.negative_prompt ?? "");
    }
    setSyncedKeyframePrompt({
      sourceSig: keyframeSourceSig,
      draftSig: keyframeSourceDraftSig,
    });
  }

  const startKeyframeSourceDraftSig = stableSig({
    prompt: startKeyframePrompt?.prompt ?? "",
    negative_prompt: startKeyframePrompt?.negative_prompt ?? "",
  });
  const startKeyframeSourceSig = stableSig({
    keyframe_id: startKeyframePrompt?.keyframe_id ?? null,
    source: startKeyframeSourceDraftSig,
  });
  const startKeyframeCurrentDraftSig = stableSig({
    prompt: startKeyframePromptDraft,
    negative_prompt: startKeyframeNegativeDraft,
  });
  const [syncedStartKeyframePrompt, setSyncedStartKeyframePrompt] = useState({
    sourceSig: startKeyframeSourceSig,
    draftSig: startKeyframeSourceDraftSig,
  });
  if (syncedStartKeyframePrompt.sourceSig !== startKeyframeSourceSig) {
    if (startKeyframeCurrentDraftSig === syncedStartKeyframePrompt.draftSig) {
      setStartKeyframePromptDraft(startKeyframePrompt?.prompt ?? "");
      setStartKeyframeNegativeDraft(startKeyframePrompt?.negative_prompt ?? "");
    }
    setSyncedStartKeyframePrompt({
      sourceSig: startKeyframeSourceSig,
      draftSig: startKeyframeSourceDraftSig,
    });
  }

  const videoPromptSourceDraftSig = stableSig({
    prompt: videoPrompt?.prompt ?? "",
    reference_pack: videoPrompt?.reference_pack ?? { selected_images: [] },
  });
  const videoPromptSourceSig = stableSig({
    video_id: videoPrompt?.video_id ?? null,
    source: videoPromptSourceDraftSig,
  });
  const videoPromptCurrentDraftSig = stableSig({
    prompt: directorVideoPromptDraft,
    reference_pack: referencePackDraft,
  });
  const [syncedDirectorVideoPrompt, setSyncedDirectorVideoPrompt] = useState({
    sourceSig: videoPromptSourceSig,
    draftSig: videoPromptSourceDraftSig,
  });
  if (syncedDirectorVideoPrompt.sourceSig !== videoPromptSourceSig) {
    if (videoPromptCurrentDraftSig === syncedDirectorVideoPrompt.draftSig) {
      setDirectorVideoPromptDraft(videoPrompt?.prompt ?? "");
      setReferencePackDraft(videoPrompt?.reference_pack ?? { selected_images: [] });
      setVideoPromptOptimizeNote(null);
    }
    setSyncedDirectorVideoPrompt({
      sourceSig: videoPromptSourceSig,
      draftSig: videoPromptSourceDraftSig,
    });
  }

  const keyframePromptDirty =
    !!keyframePrompt &&
    (keyframePromptDraft !== keyframePrompt.prompt ||
      keyframeNegativeDraft !== (keyframePrompt.negative_prompt ?? ""));
  const startKeyframePromptDirty =
    !!startKeyframePrompt &&
    (startKeyframePromptDraft !== startKeyframePrompt.prompt ||
      startKeyframeNegativeDraft !== (startKeyframePrompt.negative_prompt ?? ""));
  const directorVideoPromptDirty = !!videoPrompt && directorVideoPromptDraft !== videoPrompt.prompt;
  const savedReferencePack = videoPrompt?.reference_pack ?? { selected_images: [] };
  const referencePackDirty = !!videoPrompt && stableSig(referencePackDraft) !== stableSig(savedReferencePack);
  const referenceAssetOptions = buildReferenceAssetOptions(currentProjectData);
  const effectiveVideoDuration = videoPrompt?.duration_seconds ?? segment.duration_seconds ?? 4;
  const getVideoReferenceFingerprint = (path: string | null | undefined): number | string | null => {
    if (!path) return null;
    if (path === keyframeImagePath && keyframeFrame?.fingerprint != null) return keyframeFrame.fingerprint;
    if (path === startKeyframeImagePath && startKeyframeFrame?.fingerprint != null) {
      return startKeyframeFrame.fingerprint;
    }
    return assetFingerprints[path] ?? null;
  };

  const handleSaveDirectorVideoPrompt = () => {
    if (!videoPrompt || !directorVideoPromptDirty || savingVideoPrompt) return;
    void onSaveVideoPrompt?.(videoPrompt.video_id, { prompt: directorVideoPromptDraft });
  };

  const handleSaveReferencePack = () => {
    if (!videoPrompt || !referencePackDirty || savingVideoPrompt) return;
    void onSaveVideoPrompt?.(videoPrompt.video_id, { reference_pack: referencePackDraft });
  };

  const handleAddVideoReference = (option: ReferenceAssetOption) => {
    if (!videoPrompt) return;
    const currentImages = referencePackDraft.selected_images ?? [];
    const submittedCount = currentImages.filter(isSubmittedReferenceImage).length;
    const startImageCount = videoPrompt.start_image ? 1 : 0;
    if (startImageCount + submittedCount >= MAX_VIDEO_REFERENCE_IMAGES) return;
    if (currentImages.some((entry) => entry.path === option.path)) return;
    setReferencePackDraft({
      ...referencePackDraft,
      selected_images: [
        ...currentImages,
        {
          role: option.role,
          path: option.path,
          submit_as: "reference_image",
          required: false,
          status: "ready",
          asset_type: option.kind,
          asset_name: option.name,
          source: "manual_asset_picker",
        },
      ],
    });
  };

  const handleRemoveVideoReference = (index: number) => {
    setReferencePackDraft({
      ...referencePackDraft,
      selected_images: (referencePackDraft.selected_images ?? []).filter((_, itemIndex) => itemIndex !== index),
    });
  };

  const handleAddVideoReferenceMedia = (kind: "video" | "audio", url: string) => {
    if (!videoPrompt) return;
    const key = kind === "video" ? "selected_videos" : "selected_audios";
    const currentItems = referencePackDraft[key] ?? [];
    if (currentItems.length >= MAX_VIDEO_REFERENCE_MEDIA) return;
    if (currentItems.some((entry) => mediaEntryUrl(entry) === url)) return;
    setReferencePackDraft({
      ...referencePackDraft,
      [key]: [
        ...currentItems,
        {
          role: kind === "video" ? "reference_video" : "reference_audio",
          url,
          submit_as: kind === "video" ? "reference_video" : "reference_audio",
          required: false,
          status: "ready",
          asset_type: kind,
          asset_name: kind === "video" ? "reference video" : "reference audio",
          source: "manual_url",
        },
      ],
    });
  };

  const handleRemoveVideoReferenceMedia = (kind: "video" | "audio", index: number) => {
    const key = kind === "video" ? "selected_videos" : "selected_audios";
    setReferencePackDraft({
      ...referencePackDraft,
      [key]: (referencePackDraft[key] ?? []).filter((_, itemIndex) => itemIndex !== index),
    });
  };

  const handleOptimizeVideoPrompt = async () => {
    if (!videoPrompt || episode == null || !directorVideoPromptDraft.trim()) return;
    setOptimizingVideoPrompt(true);
    setVideoPromptOptimizeNote(null);
    try {
      const result = await API.optimizeVideoPrompt(projectName, episode, {
        prompt: directorVideoPromptDraft,
        video_id: videoPrompt.video_id,
        shot_id: videoPrompt.shot_id,
        title: videoPrompt.title,
        duration_seconds: effectiveVideoDuration,
        reference_pack: videoPrompt.reference_pack,
      });
      setDirectorVideoPromptDraft(result.optimized_prompt);
      setVideoPromptOptimizeNote(
        result.within_limit
          ? t("director_video_prompt_optimized", { count: result.char_count, max: result.max_chars })
          : t("director_video_prompt_optimized_over_limit", { count: result.char_count, max: result.max_chars }),
      );
    } catch (error) {
      setVideoPromptOptimizeNote(t("director_video_prompt_optimize_failed", { message: errMsg(error) }));
    } finally {
      setOptimizingVideoPrompt(false);
    }
  };

  const dirtyHint = t("shot_detail_save_first");

  const characterNames =
    contentMode === "drama"
      ? (segment as DramaScene).characters_in_scene ?? []
      : contentMode === "ad"
        ? (segment as AdShot).characters_in_shot ?? []
        : (segment as NarrationSegment).characters_in_segment ?? [];
  const sceneNames = segment.scenes ?? [];
  const propNames = segment.props ?? [];
  // 展示用去重：products_in_shot 无唯一性约束（同一产品多次入画合法），重复名直接作 key 会撞
  const productNames = isAd ? Array.from(new Set(adShot?.products_in_shot ?? [])) : [];
  const refsReadOnly = !onUpdatePrompt;

  const handleRefsSave = async (patch: Record<string, string[]>) => {
    if (!onUpdatePrompt || Object.keys(patch).length === 0) return;
    await onUpdatePrompt(segmentId, patch);
  };

  const sectionHeaderStyle: React.CSSProperties = {
    color: "var(--color-text-4)",
    letterSpacing: "1px",
    fontFamily: "var(--font-mono)",
  };

  const leftColumn = (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto px-3.5 pb-5 pt-3.5">
      {isAd && (
        <>
          <div>
            <label
              htmlFor={`shot-section-${segmentId}`}
              className="mb-2 block text-[10.5px] font-bold uppercase"
              style={sectionHeaderStyle}
            >
              {t("detail_section_shot_section")}
            </label>
            <input
              id={`shot-section-${segmentId}`}
              type="text"
              list={`shot-section-options-${segmentId}`}
              value={draft.section ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, section: e.target.value }))}
              readOnly={refsReadOnly}
              placeholder={t("detail_shot_section_placeholder")}
              className="prompt-ta"
              style={{ minHeight: 0 }}
            />
            <datalist id={`shot-section-options-${segmentId}`}>
              {AD_SECTION_VALUES.map((v) => (
                <option key={v} value={v} />
              ))}
            </datalist>
          </div>

          <div>
            <div className="mb-2 flex items-center gap-1.5">
              <label
                htmlFor={`shot-voiceover-${segmentId}`}
                className="text-[10.5px] font-bold uppercase"
                style={sectionHeaderStyle}
              >
                {t("detail_section_voiceover")}
              </label>
              <span className="flex-1" />
              <span className="num text-[10px]" style={{ color: "var(--color-text-4)" }}>
                {t("detail_field_chars_count", { count: (draft.voiceover_text ?? "").length })}
              </span>
            </div>
            <textarea
              id={`shot-voiceover-${segmentId}`}
              className="prompt-ta"
              value={draft.voiceover_text ?? ""}
              onChange={(e) => setDraft((d) => ({ ...d, voiceover_text: e.target.value }))}
              readOnly={refsReadOnly}
              placeholder={t("detail_voiceover_placeholder")}
              style={{ minHeight: 96 }}
            />
          </div>

          {productNames.length > 0 && (
            <div>
              <div className="mb-2 text-[10.5px] font-bold uppercase" style={sectionHeaderStyle}>
                {t("detail_section_products")}
              </div>
              <div className="flex flex-wrap gap-1.5">
                {productNames.map((name) => (
                  <span
                    key={name}
                    className="rounded-md px-2 py-1 text-[11.5px]"
                    style={{
                      background: "oklch(0.22 0.011 265 / 0.6)",
                      border: "1px solid var(--color-hairline-soft)",
                      color: "var(--color-text-2)",
                    }}
                  >
                    {name}
                  </span>
                ))}
              </div>
            </div>
          )}
        </>
      )}
      <ReferencesSection
        projectName={projectName}
        contentMode={contentMode}
        characterNames={characterNames}
        sceneNames={sceneNames}
        propNames={propNames}
        onSave={handleRefsSave}
        disabled={dirty || saving || refsReadOnly}
        disabledHint={dirty ? dirtyHint : undefined}
      />
      {/* 对白编辑：narration / ad 编辑扁平 video_prompt.dialogue；drama 台词已迁到场景级
          utterances（判别式台词 + 画外音），此处直接编辑 scene.utterances 并双向保存同步。 */}
      {isDrama ? (
        <div>
          <div
            className="mb-2 text-[10.5px] font-bold uppercase"
            style={{
              color: "var(--color-text-4)",
              letterSpacing: "1px",
              fontFamily: "var(--font-mono)",
            }}
          >
            {t("detail_section_utterances")}
          </div>
          <UtteranceListEditor
            utterances={draft.utterances ?? EMPTY_UTTERANCES}
            onChange={handleUtterancesChange}
            disabled={saving || refsReadOnly}
          />
        </div>
      ) : (
        <div>
          <div
            className="mb-2 text-[10.5px] font-bold uppercase"
            style={{
              color: "var(--color-text-4)",
              letterSpacing: "1px",
              fontFamily: "var(--font-mono)",
            }}
          >
            {t("detail_section_dialogue")}
          </div>
          {vidDraft ? (
            <DialogueListEditor
              dialogue={vidDraft.dialogue ?? []}
              onChange={handleDialogueChange}
              readOnly={refsReadOnly}
            />
          ) : (
            <div
              className="rounded-md py-3 text-center text-[11.5px] italic"
              style={{
                border: "1px dashed var(--color-hairline)",
                color: "var(--color-text-4)",
              }}
            >
              {t("detail_dialogue_empty")}
            </div>
          )}
        </div>
      )}

      {(hasNarrationText || contentMode === "narration") && (
        <div>
          <div
            className="mb-2 text-[10.5px] font-bold uppercase"
            style={{
              color: "var(--color-text-4)",
              letterSpacing: "1px",
              fontFamily: "var(--font-mono)",
            }}
          >
            {t("detail_section_novel")}
          </div>
          <div
            className="rounded-md px-3 py-2.5"
            style={{
              background:
                "linear-gradient(180deg, oklch(0.22 0.012 265 / 0.5), oklch(0.20 0.012 265 / 0.35))",
              border: "1px solid var(--color-hairline-soft)",
              borderLeft: "3px solid var(--color-accent-soft)",
            }}
          >
            <p
              className="display-serif m-0 text-[13px]"
              style={{ lineHeight: 1.65, color: "var(--color-text)" }}
            >
              {hasNarrationText ? novelText.trim() : t("no_original_text")}
            </p>
          </div>
        </div>
      )}
    </div>
  );

  const midColumn = (
    <div className="flex h-full min-h-0 flex-col gap-3 overflow-y-auto px-5 pb-7 pt-3.5">
      <div
        className="text-[10.5px] font-bold uppercase"
        style={{
          color: "var(--color-text-4)",
          letterSpacing: "1px",
          fontFamily: "var(--font-mono)",
        }}
      >
        {directorPipelineAvailable ? t("director_prompt_chain_title") : t("detail_section_prompts")}
      </div>

      {directorPipelineAvailable ? (
        <>
          {keyframePrompt ? (
            <DirectorPromptSection
              title={
                keyframePrompt.role === "guide_reference"
                  ? t("director_motion_guide_prompt_title")
                  : t("director_keyframe_prompt_title")
              }
              statusLabel={t(keyframeStatus.labelKey)}
              statusTone={keyframeStatus.tone}
              prompt={keyframePromptDraft}
              negativePrompt={keyframeNegativeDraft}
              promptPlaceholder={
                keyframePrompt.role === "guide_reference"
                  ? t("director_motion_guide_prompt_placeholder")
                  : t("director_keyframe_prompt_placeholder")
              }
              dirty={keyframePromptDirty}
              saving={savingKeyframePrompt}
              generating={keyframeActive}
              generated={keyframeReady}
              saveLabel={
                keyframePrompt.role === "guide_reference"
                  ? t("director_save_motion_guide_prompt")
                  : t("director_save_keyframe_prompt")
              }
              regenerateLabel={t("director_pipeline_regenerate")}
              generateLabel={
                keyframePrompt.role === "guide_reference"
                  ? t("director_motion_guide_generate")
                  : t("director_keyframe_generate")
              }
              generationError={
                keyframeFrame?.task_status === "failed" && keyframeFrame.task_error_message
                  ? t("director_keyframe_error", { message: keyframeFrame.task_error_message })
                  : null
              }
              onPromptChange={setKeyframePromptDraft}
              onNegativePromptChange={setKeyframeNegativeDraft}
              onSave={() =>
                onSaveKeyframePrompt?.(keyframePrompt.keyframe_id, {
                  prompt: keyframePromptDraft,
                  negative_prompt: keyframeNegativeDraft,
                })
              }
              onGenerate={() => onGenerateKeyframe?.(keyframePrompt.keyframe_id)}
            />
          ) : (
            <section className="rounded-md border border-dashed border-gray-800 p-3 text-[11.5px] text-[var(--color-text-4)]">
              {t("director_pipeline_missing_prompt")}
            </section>
          )}

          {startKeyframePrompt ? (
            <DirectorPromptSection
              title={t("director_start_keyframe_prompt_title")}
              statusLabel={t(startKeyframeStatus.labelKey)}
              statusTone={startKeyframeStatus.tone}
              prompt={startKeyframePromptDraft}
              negativePrompt={startKeyframeNegativeDraft}
              promptPlaceholder={t("director_start_keyframe_prompt_placeholder")}
              dirty={startKeyframePromptDirty}
              saving={savingStartKeyframePrompt}
              generating={startKeyframeActive}
              generated={startKeyframeReady}
              saveLabel={t("director_save_start_keyframe_prompt")}
              regenerateLabel={t("director_pipeline_regenerate")}
              generateLabel={t("director_keyframe_generate")}
              generationError={
                startKeyframeFrame?.task_status === "failed" && startKeyframeFrame.task_error_message
                  ? t("director_keyframe_error", { message: startKeyframeFrame.task_error_message })
                  : null
              }
              onPromptChange={setStartKeyframePromptDraft}
              onNegativePromptChange={setStartKeyframeNegativeDraft}
              onSave={() =>
                onSaveKeyframePrompt?.(startKeyframePrompt.keyframe_id, {
                  prompt: startKeyframePromptDraft,
                  negative_prompt: startKeyframeNegativeDraft,
                })
              }
              onGenerate={() => onGenerateKeyframe?.(startKeyframePrompt.keyframe_id)}
            />
          ) : (
            shouldShowVideoStartImageCard && (
              <section className="rounded-md border border-dashed border-gray-800 p-3 text-[11.5px] text-[var(--color-text-4)]">
                <div>{t("director_start_keyframe_prompt_empty")}</div>
                {onCreateStartKeyframePrompt && (
                  <button
                    type="button"
                    onClick={() => void onCreateStartKeyframePrompt(segmentId)}
                    disabled={savingStartKeyframePrompt}
                    className="sv-navbtn mt-2 inline-flex items-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    {savingStartKeyframePrompt ? (
                      <Loader2 className="h-3 w-3 animate-spin" />
                    ) : (
                      <ImageIcon className="h-3 w-3" />
                    )}
                    <span>{t("director_start_keyframe_create")}</span>
                  </button>
                )}
              </section>
            )
          )}

          {videoPrompt ? (
            <section>
              <div className="mb-2 flex items-center gap-1.5">
                <Film className="h-3.5 w-3.5" style={{ color: "var(--color-accent)" }} />
                <span className="text-[12.5px] font-semibold" style={{ color: "var(--color-text-2)" }}>
                  {t("director_video_prompt_title")}
                </span>
                <span
                  className="rounded px-1.5 py-0.5 font-mono text-[10px]"
                  style={pipelineBadgeStyle(draftVideoStatus.tone)}
                >
                  {t(draftVideoStatus.labelKey)}
                </span>
                <span className="flex-1" />
                <span className="num text-[10px]" style={{ color: "var(--color-text-4)" }}>
                  {t("detail_field_chars_count", { count: directorVideoPromptDraft.length })}
                </span>
              </div>
              <textarea
                className="prompt-ta"
                value={directorVideoPromptDraft}
                onChange={(event) => setDirectorVideoPromptDraft(event.target.value)}
                placeholder={t("director_video_prompt_placeholder")}
                style={{ minHeight: 220 }}
              />
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  type="button"
                  disabled={optimizingVideoPrompt || savingVideoPrompt || episode == null || !directorVideoPromptDraft.trim()}
                  onClick={() => void handleOptimizeVideoPrompt()}
                  className="sv-navbtn inline-flex items-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {optimizingVideoPrompt ? (
                    <Loader2 className="h-3 w-3 animate-spin" />
                  ) : (
                    <Sparkles className="h-3 w-3" />
                  )}
                  <span>{optimizingVideoPrompt ? t("director_video_prompt_optimizing") : t("director_video_prompt_optimize")}</span>
                </button>
                <button
                  type="button"
                  disabled={!directorVideoPromptDirty || savingVideoPrompt}
                  onClick={handleSaveDirectorVideoPrompt}
                  className="sv-navbtn inline-flex items-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {savingVideoPrompt ? <Loader2 className="h-3 w-3 animate-spin" /> : <Check className="h-3 w-3" />}
                  <span>{savingVideoPrompt ? t("director_prompt_saving") : t("director_save_video_prompt")}</span>
                </button>
                <button
                  type="button"
                  disabled={directorVideoPromptDirty || referencePackDirty || savingVideoPrompt || draftVideoActive}
                  title={
                    directorVideoPromptDirty
                      ? t("director_video_prompt_save_first")
                      : referencePackDirty
                        ? t("director_reference_pack_save_first")
                        : undefined
                  }
                  onClick={() => void onGenerateDraftVideo?.(videoPrompt.video_id)}
                  className="sv-navbtn inline-flex items-center gap-1.5 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {draftVideoActive ? <Loader2 className="h-3 w-3 animate-spin" /> : <Film className="h-3 w-3" />}
                  <span>
                    {draftVideoActive
                      ? t("director_pipeline_generating")
                      : draftVideoReady
                        ? t("director_pipeline_regenerate")
                        : t("director_draft_video_generate")}
                  </span>
                </button>
              </div>
              {videoPromptOptimizeNote && (
                <div className="mt-1.5 text-[11px] leading-4 text-[var(--color-text-4)]">
                  {videoPromptOptimizeNote}
                </div>
              )}
              <div className="mt-2 text-[11px] leading-4 text-[var(--color-text-4)]">
                {t("director_video_prompt_meta", {
                  startImage: videoPrompt.start_image || t("director_video_prompt_no_start_image"),
                  duration: effectiveVideoDuration,
                })}
              </div>
              <VideoReferencePackPanel
                projectName={projectName}
                pack={referencePackDraft}
                startImagePath={videoPrompt.start_image}
                dirty={referencePackDirty}
                saving={savingVideoPrompt}
                assetOptions={referenceAssetOptions}
                getFingerprint={getVideoReferenceFingerprint}
                onSave={handleSaveReferencePack}
                onRemoveImage={handleRemoveVideoReference}
                onAddAsset={handleAddVideoReference}
                onAddMedia={handleAddVideoReferenceMedia}
                onRemoveMedia={handleRemoveVideoReferenceMedia}
              />
            </section>
          ) : (
            <section className="rounded-md border border-dashed border-gray-800 p-3 text-[11.5px] text-[var(--color-text-4)]">
              {t("director_video_prompt_missing")}
            </section>
          )}
        </>
      ) : (
        <>
          <section>
            <div className="mb-2 flex items-center gap-1.5">
              <ImageIcon
                className="h-3.5 w-3.5"
                style={{ color: "var(--color-text-3)" }}
              />
              <span
                className="text-[12.5px] font-semibold"
                style={{ color: "var(--color-text-2)" }}
              >
                {t("detail_image_prompt_title")}
              </span>
              <span className="flex-1" />
              {imgDraft && (
                <span
                  className="num text-[10px]"
                  style={{ color: "var(--color-text-4)" }}
                >
                  {t("detail_field_chars_count", { count: imgDraft.scene.length })}
                </span>
              )}
            </div>
            {imgDraft ? (
              <ImagePromptEditor prompt={imgDraft} onUpdate={handleImgUpdate} readOnly={refsReadOnly} />
            ) : (
              <textarea
                className="prompt-ta"
                value={
                  typeof draft.image_prompt === "string" ? draft.image_prompt : ""
                }
                onChange={(e) => handleImgStringChange(e.target.value)}
                readOnly={refsReadOnly}
                placeholder={t("detail_image_prompt_placeholder")}
                style={{ minHeight: 124 }}
              />
            )}
          </section>

          <section>
            <div className="mb-2 flex items-center gap-1.5">
              <Film
                className="h-3.5 w-3.5"
                style={{ color: "var(--color-text-3)" }}
              />
              <span
                className="text-[12.5px] font-semibold"
                style={{ color: "var(--color-text-2)" }}
              >
                {t("detail_video_prompt_title")}
              </span>
              <span className="flex-1" />
              {vidDraft && (
                <span
                  className="num text-[10px]"
                  style={{ color: "var(--color-text-4)" }}
                >
                  {t("detail_field_chars_count", { count: vidDraft.action.length })}
                </span>
              )}
            </div>
            {vidDraft ? (
              <VideoPromptEditor prompt={vidDraft} onUpdate={handleVidUpdate} readOnly={refsReadOnly} />
            ) : (
              <textarea
                className="prompt-ta"
                value={
                  typeof draft.video_prompt === "string" ? draft.video_prompt : ""
                }
                onChange={(e) => handleVidStringChange(e.target.value)}
                readOnly={refsReadOnly}
                placeholder={t("detail_video_prompt_placeholder")}
                style={{ minHeight: 88 }}
              />
            )}
          </section>
        </>
      )}
    </div>
  );

  const rightColumn = (
    <div className="flex h-full min-h-0 flex-col gap-4 overflow-y-auto px-[18px] pb-7 pt-3.5">
      {directorPipelineAvailable ? (
        <>
          <div
            className="rounded-[10px] px-3 py-2 text-[11px]"
            style={{
              background: "oklch(0.18 0.010 265 / 0.42)",
              border: "1px solid var(--color-hairline-soft)",
              color: "var(--color-text-4)",
            }}
          >
            <div className="flex items-center gap-2">
              <span className="font-semibold text-[var(--color-text-2)]">
                {t("director_pipeline_title")}
              </span>
              {keyframePrompt && (
                <span
                  className="rounded px-1.5 py-0.5 font-mono text-[10px]"
                  style={pipelineBadgeStyle(keyframeStatus.tone)}
                >
                  {t(keyframeStatus.labelKey)}
                </span>
              )}
              {videoPrompt && (
                <span
                  className="rounded px-1.5 py-0.5 font-mono text-[10px]"
                  style={pipelineBadgeStyle(draftVideoStatus.tone)}
                >
                  {t(draftVideoStatus.labelKey)}
                </span>
              )}
            </div>
          </div>
          <DirectorPipelineMediaCard
            kind="image"
            title={
              keyframePrompt?.role === "guide_reference"
                ? t("director_motion_guide_title")
                : t("director_keyframe_image_title")
            }
            projectName={projectName}
            assetPath={keyframeImagePath}
            aspectRatio={aspectRatio}
            generating={keyframeActive || !!generatingStoryboard}
            disabled={!keyframePrompt || !!savingKeyframePrompt || isGridMode}
            disabledHint={!keyframePrompt ? t("director_pipeline_missing_prompt") : undefined}
            emptyLabel={
              keyframePrompt?.role === "guide_reference"
                ? t("director_motion_guide_empty")
                : t("director_keyframe_image_empty")
            }
            generateLabel={
              keyframeReady
                ? t("director_pipeline_regenerate")
                : keyframePrompt?.role === "guide_reference"
                  ? t("director_motion_guide_generate")
                  : t("director_keyframe_generate")
            }
            onGenerate={keyframePrompt ? () => onGenerateKeyframe?.(keyframePrompt.keyframe_id) : undefined}
          />
          {shouldShowVideoStartImageCard && (
            <DirectorPipelineMediaCard
              kind="image"
              title={t("director_start_keyframe_title")}
              projectName={projectName}
              assetPath={startKeyframeImagePath}
              aspectRatio={aspectRatio}
              generating={startKeyframeActive}
              disabled={!!savingStartKeyframePrompt || (!startKeyframePrompt && !onCreateStartKeyframePrompt)}
              disabledHint={
                startKeyframePrompt
                  ? undefined
                  : t("director_start_keyframe_create_first")
              }
              emptyLabel={
                startKeyframePrompt
                  ? t("director_start_keyframe_empty")
                  : t("director_start_keyframe_prompt_empty")
              }
              generateLabel={
                startKeyframeImagePath
                  ? t("director_pipeline_regenerate")
                  : startKeyframePrompt
                    ? t("director_keyframe_generate")
                    : t("director_start_keyframe_create")
              }
              onGenerate={
                startKeyframePrompt
                  ? () => onGenerateKeyframe?.(startKeyframePrompt.keyframe_id)
                  : () => onCreateStartKeyframePrompt?.(segmentId)
              }
            />
          )}
          <DirectorPipelineMediaCard
            kind="video"
            title={t("director_draft_video_title")}
            projectName={projectName}
            assetPath={draftVideo?.exists ? draftVideo.file_path : null}
            posterPath={draftVideo?.generation_inputs?.video_thumbnail ?? null}
            aspectRatio={aspectRatio}
            generating={draftVideoActive || !!generatingVideo}
            disabled={!videoPrompt || directorVideoPromptDirty || referencePackDirty || !!savingVideoPrompt}
            disabledHint={
              !videoPrompt
                ? t("director_video_prompt_missing")
                : directorVideoPromptDirty
                  ? t("director_video_prompt_save_first")
                  : referencePackDirty
                    ? t("director_reference_pack_save_first")
                    : undefined
            }
            emptyLabel={t("director_draft_video_empty")}
            generateLabel={
              draftVideoReady
                ? t("director_pipeline_regenerate")
                : t("director_draft_video_generate")
            }
            onGenerate={videoPrompt ? () => onGenerateDraftVideo?.(videoPrompt.video_id) : undefined}
          />
          {keyframeFrame?.task_status === "failed" && keyframeFrame.task_error_message && (
            <div
              className="rounded-[10px] px-3 py-2 text-[11.5px] leading-4"
              style={{
                background: "oklch(0.22 0.045 30 / 0.46)",
                border: "1px solid oklch(0.48 0.12 30 / 0.32)",
                color: "oklch(0.84 0.12 35)",
              }}
            >
              {t("director_keyframe_error", { message: keyframeFrame.task_error_message })}
            </div>
          )}
          {draftVideo?.task_status === "failed" && draftVideo.task_error_message && (
            <div
              className="rounded-[10px] px-3 py-2 text-[11.5px] leading-4"
              style={{
                background: "oklch(0.22 0.045 30 / 0.46)",
                border: "1px solid oklch(0.48 0.12 30 / 0.32)",
                color: "oklch(0.84 0.12 35)",
              }}
            >
              {t("director_draft_video_error", { message: draftVideo.task_error_message })}
            </div>
          )}
        </>
      ) : (
        <>
          <MediaCard
            kind="storyboard"
            projectName={projectName}
            segmentId={segmentId}
            assetPath={assets?.storyboard_image ?? null}
            aspectRatio={aspectRatio}
            hideGenerateButton={isGridMode}
            generating={generatingStoryboard}
            estimatedCost={sbEstimate ?? undefined}
            onGenerate={onGenerateStoryboard ? () => onGenerateStoryboard(segmentId) : undefined}
            onRestore={onRestoreStoryboard}
            onUpload={
              scriptFile && !refsReadOnly ? (file) => handleUpload("storyboard", file) : undefined
            }
            uploading={uploadingKind === "storyboard"}
            uploadDisabled={uploadingKind !== null}
            editScriptFile={refsReadOnly ? undefined : scriptFile}
            generateDisabled={dirty || saving}
            generateDisabledHint={dirty ? dirtyHint : undefined}
          />
          <div className="flex flex-col">
            {scriptFile && onGenerateVideo && (
              <EndFrameRow
                projectName={projectName}
                segmentId={segmentId}
                scriptFile={scriptFile}
                contentMode={contentMode}
                aspectRatio={aspectRatio}
                endFramePath={segment.end_frame_image ?? null}
                videoBackend={videoBackend}
                readOnly={refsReadOnly}
                onSubmittingChange={setEndFrameSubmitting}
                videoUploadBusy={uploadingKind === "video"}
              />
            )}
            <MediaCard
              kind="video"
              projectName={projectName}
              segmentId={segmentId}
              assetPath={assets?.video_clip ?? null}
              posterPath={assets?.video_thumbnail ?? null}
              aspectRatio={aspectRatio}
              generating={generatingVideo}
              generateDisabled={!hasStoryboard || dirty || saving}
              generateDisabledHint={dirty ? dirtyHint : undefined}
              estimatedCost={vidEstimate ?? undefined}
              onGenerate={onGenerateVideo ? () => onGenerateVideo(segmentId) : undefined}
              onRestore={onRestoreVideo}
              onUpload={
                scriptFile && !refsReadOnly ? (file) => handleUpload("video", file) : undefined
              }
              uploading={uploadingKind === "video"}
              uploadDisabled={uploadingKind !== null || endFrameSubmitting}
            />
          </div>
        </>
      )}
      {contentMode === "narration" && (
        <NarrationAudioCard
          projectName={projectName}
          segmentId={segmentId}
          novelText={novelText}
          assetPath={assets?.narration_audio ?? null}
          generating={generatingNarration}
          generateDisabled={!hasNarrationText || dirty || saving}
          generateDisabledHint={!hasNarrationText ? t("no_original_text") : dirty ? dirtyHint : undefined}
          estimatedCost={narrationEstimate ?? undefined}
          onGenerate={onGenerateNarration ? () => onGenerateNarration(segmentId) : undefined}
        />
      )}
    </div>
  );

  // 重排在途也要锁定切镜：ShotSplitView 在移动完成回调里按当前 selectedIndex 偏移，
  // 在途切镜会让偏移作用到新选中项，选中态跳到错误镜头。
  const navDisabled = dirty || saving || !!movePending;
  // 禁用原因提示与禁用条件同源：重排在途与未保存修改分别给出对应说明
  const navDisabledHint = movePending ? t("shot_move_pending") : dirty || saving ? dirtyHint : undefined;

  return (
    <div
      className="flex min-h-0 min-w-0 flex-col overflow-hidden"
      style={{
        background:
          "radial-gradient(ellipse at top, oklch(0.20 0.012 270 / 0.35), oklch(0.17 0.010 265 / 0.2))",
      }}
    >
      <div
        className="relative flex items-center gap-2.5 px-5 py-3"
        style={{ borderBottom: "1px solid var(--color-hairline-soft)" }}
      >
        <span
          className="num rounded-md px-2.5 py-1 text-[12px] font-bold"
          style={{
            background:
              "linear-gradient(180deg, var(--color-accent-2), var(--color-accent))",
            color: "oklch(0.14 0 0)",
            letterSpacing: "0.3px",
            boxShadow:
              "inset 0 1px 0 oklch(1 0 0 / 0.3), 0 2px 6px -2px var(--color-accent-glow)",
          }}
        >
          {segmentId}
        </span>
        <DurationPill
          seconds={segment.duration_seconds ?? 0}
          segmentId={segmentId}
          projectName={projectName}
          scriptFile={scriptFile}
          durationOptions={durationOptions}
          durationWarningReason={durationWarningReason}
          onUpdatePrompt={onUpdatePrompt}
          busy={!!generatingStoryboard || !!generatingVideo}
        />
        <StatusBadge status={status} />
        <span className="flex-1" />

        <div className="flex items-center gap-1.5">
          <span
            className="num text-[10.5px]"
            style={{ color: "var(--color-text-4)" }}
          >
            {t("shot_detail_count", {
              current: selectedIndex + 1,
              total: totalCount,
            })}
          </span>
          {isAd && onMoveShot && (
            <>
              <button
                type="button"
                onClick={() => void onMoveShot(segmentId, "earlier")}
                disabled={navDisabled || selectedIndex === 0}
                title={navDisabledHint ?? t("shot_move_earlier")}
                className="sv-navbtn disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={t("shot_move_earlier")}
              >
                <ChevronUp className="h-3.5 w-3.5" />
              </button>
              <button
                type="button"
                onClick={() => void onMoveShot(segmentId, "later")}
                disabled={navDisabled || selectedIndex === totalCount - 1}
                title={navDisabledHint ?? t("shot_move_later")}
                className="sv-navbtn disabled:cursor-not-allowed disabled:opacity-50"
                aria-label={t("shot_move_later")}
              >
                <ChevronDown className="h-3.5 w-3.5" />
              </button>
            </>
          )}
          <button
            type="button"
            onClick={onPrev}
            disabled={navDisabled}
            title={navDisabledHint ?? t("shot_detail_prev")}
            className="sv-navbtn disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={t("shot_detail_prev")}
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={onNext}
            disabled={navDisabled}
            title={navDisabledHint ?? t("shot_detail_next")}
            className="sv-navbtn disabled:cursor-not-allowed disabled:opacity-50"
            aria-label={t("shot_detail_next")}
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
          {/* 备注抽屉只有落库才有意义：只读展示下不给入口，免得输入的备注静默丢弃 */}
          {refsReadOnly ? null : (
            <NotesDrawer
              shotId={segmentId}
              value={note}
              onCommit={handleNotesCommit}
            />
          )}
        </div>
      </div>

      {dirty && (
        <div
          role="status"
          aria-live="polite"
          className="flex items-center gap-2 px-5 py-2"
          style={{
            background:
              "linear-gradient(180deg, var(--color-accent-dim), oklch(0.20 0.012 270 / 0.35))",
            borderBottom: "1px solid var(--color-accent-soft)",
          }}
        >
          <span
            aria-hidden="true"
            className="h-1.5 w-1.5 rounded-full"
            style={{
              background: "var(--color-accent)",
              boxShadow: "0 0 6px var(--color-accent-glow)",
            }}
          />
          <span
            className="num text-[10.5px] uppercase"
            style={{
              letterSpacing: "1.0px",
              color: "var(--color-accent-2)",
            }}
          >
            {t("shot_detail_unsaved")}
          </span>
          <span className="flex-1" />
          <button
            type="button"
            onClick={handleCancel}
            disabled={saving}
            className="focus-ring inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11.5px] text-[var(--color-text-3)] transition-colors [&:not(:disabled)]:hover:bg-[oklch(0.26_0.013_265_/_0.7)] [&:not(:disabled)]:hover:text-[var(--color-text)] disabled:cursor-not-allowed disabled:opacity-50"
            style={{
              border: "1px solid var(--color-hairline)",
              background: "oklch(0.22 0.011 265 / 0.5)",
            }}
          >
            <Undo2 className="h-3.5 w-3.5" />
            <span>{t("shot_detail_cancel")}</span>
          </button>
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saving}
            className="focus-ring inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-[11.5px] font-medium transition-transform [&:not(:disabled)]:hover:-translate-y-px disabled:cursor-not-allowed disabled:opacity-60"
            style={{
              color: "oklch(0.14 0 0)",
              background:
                "linear-gradient(135deg, var(--color-accent-2), var(--color-accent))",
              boxShadow:
                "inset 0 1px 0 oklch(1 0 0 / 0.35), 0 6px 18px -6px var(--color-accent-glow), 0 0 0 1px var(--color-accent-soft)",
            }}
          >
            {saving ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <Check className="h-3.5 w-3.5" />
            )}
            <span>
              {saving ? t("shot_detail_saving") : t("shot_detail_save")}
            </span>
          </button>
        </div>
      )}

      <ResponsiveDetailGrid
        left={leftColumn}
        mid={midColumn}
        right={rightColumn}
      />
    </div>
  );
}
