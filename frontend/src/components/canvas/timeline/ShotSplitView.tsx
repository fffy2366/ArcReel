import { useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import type { DurationOutOfRangeReason } from "@/hooks/useModelCapabilities";
import type {
  AdShot,
  DraftVideoFrame,
  DraftVideoStatus,
  DramaScene,
  KeyframeImageFrame,
  KeyframePrompt,
  KeyframePromptPlan,
  NarrationSegment,
  VideoPromptPack,
  VideoPromptPackItem,
  VideoPromptPlan,
} from "@/types";
import { API } from "@/api";
import { useAppStore } from "@/stores/app-store";
import { useProjectsStore } from "@/stores/projects-store";
import { getScriptItemId, type EditorContentMode } from "@/utils/script-shape";
import { ShotList } from "./ShotList";
import { ShotDetail } from "./ShotDetail";
import { buildKeyframeReferenceImages } from "./keyframeReferences";

type Segment = NarrationSegment | DramaScene | AdShot;

interface ShotSplitViewProps {
  segments: Segment[];
  episode?: number;
  contentMode: EditorContentMode;
  aspectRatio: "9:16" | "16:9";
  projectName: string;
  /** 当前剧集剧本文件名，分镜图/视频自主上传需要它定位剧本条目 */
  scriptFile?: string;
  isGridMode?: boolean;
  onUpdatePrompt?: (
    segmentId: string,
    fieldOrPatch: string | Record<string, unknown>,
    value?: unknown,
  ) => void | Promise<void>;
  /** ad 模式镜头顺序调整，resolve 为是否移动成功 */
  onMoveShot?: (shotId: string, direction: "earlier" | "later") => Promise<boolean>;
  onGenerateStoryboard?: (segmentId: string) => void;
  onGenerateVideo?: (segmentId: string) => void;
  onGenerateNarration?: (segmentId: string) => void;
  onRestoreStoryboard?: () => Promise<void> | void;
  onRestoreVideo?: () => Promise<void> | void;
  generatingStoryboard?: (segmentId: string) => boolean;
  generatingVideo?: (segmentId: string) => boolean;
  generatingNarration?: (segmentId: string) => boolean;
  durationOptions?: number[];
  /** 已保存时长越界的成因判定；缺省时 ShotDetail 退回不区分成因的通用警告文案。 */
  durationWarningReason?: (seconds: number) => DurationOutOfRangeReason | null;
}

function isDraftVideoTaskActive(video?: DraftVideoFrame | null): boolean {
  return video?.task_status === "queued" || video?.task_status === "running" || video?.task_status === "cancelling";
}

function isKeyframeTaskActive(frame?: KeyframeImageFrame | null): boolean {
  return frame?.task_status === "queued" || frame?.task_status === "running" || frame?.task_status === "cancelling";
}

function segmentSourceText(segment: Segment, contentMode: EditorContentMode): string {
  if (contentMode === "narration") return (segment as NarrationSegment).novel_text || "";
  if (contentMode === "ad") return (segment as AdShot).voiceover_text || "";
  return "";
}

function buildStartKeyframePrompt(
  segmentId: string,
  segment: Segment,
  contentMode: EditorContentMode,
  videoPrompt: VideoPromptPackItem | null,
): KeyframePrompt | null {
  if (!videoPrompt) return null;
  const sourceText = segmentSourceText(segment, contentMode);
  return {
    keyframe_id: `KF-${segmentId}-start`,
    shot_id: segmentId,
    role: "start_image",
    title: `${videoPrompt.title || segmentId} | keyframe`,
    image_role_explanation: "Single start keyframe for video generation or repair; not a 9-grid motion guide.",
    prompt: [
      `Start keyframe | ${segmentId}`,
      "Create a single polished frame suitable as a video start_image, not a storyboard grid.",
      `Source: ${sourceText || videoPrompt.title || segmentId}`,
      `Frame: ${videoPrompt.prompt}`,
    ].join("\n"),
    negative_prompt:
      "grid, storyboard sketch, rough line art, readable UI text, watermark, malformed hands, malformed feet, detached limbs, overly dark frame",
    style_policy: "Use one finished image that can serve as the video start frame.",
    reference_policy: "Use available character, scene, and prop asset references when generating.",
    optional_reference_roles: ["asset_reference", "start_image"],
    review_checkpoints: [
      "It is a single complete start frame, not a 9-grid image.",
      "Characters, scene, and props match the asset references.",
      "It is suitable as a video start_image.",
    ],
  };
}


/**
 * 分镜分屏：左 ShotList + 右 ShotDetail。窄屏时左列折叠到 44px。
 */
export function ShotSplitView({
  segments,
  episode,
  contentMode,
  aspectRatio,
  projectName,
  scriptFile,
  isGridMode,
  onUpdatePrompt,
  onMoveShot,
  onGenerateStoryboard,
  onGenerateVideo,
  onGenerateNarration,
  onRestoreStoryboard,
  onRestoreVideo,
  generatingStoryboard,
  generatingVideo,
  generatingNarration,
  durationOptions,
  durationWarningReason,
}: ShotSplitViewProps) {
  const { t } = useTranslation("dashboard");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [keyframePlan, setKeyframePlan] = useState<KeyframePromptPlan | null>(null);
  const [keyframeStatus, setKeyframeStatus] = useState<Record<string, KeyframeImageFrame>>({});
  const [videoPromptPlan, setVideoPromptPlan] = useState<VideoPromptPlan | null>(null);
  const [draftVideoStatus, setDraftVideoStatus] = useState<DraftVideoStatus | null>(null);
  const [savingKeyframeId, setSavingKeyframeId] = useState<string | null>(null);
  const [savingVideoPromptId, setSavingVideoPromptId] = useState<string | null>(null);
  const [generatingKeyframeId, setGeneratingKeyframeId] = useState<string | null>(null);
  const [generatingDraftVideoId, setGeneratingDraftVideoId] = useState<string | null>(null);
  const [collapsed, setCollapsed] = useState(
    () => typeof window !== "undefined" && window.innerWidth < 1100,
  );
  const [movePending, setMovePending] = useState(false);
  const listScrollRef = useRef<HTMLDivElement>(null);
  const pushToast = useAppStore((s) => s.pushToast);
  const currentProjectData = useProjectsStore((s) =>
    s.currentProjectName === projectName ? s.currentProjectData : null,
  );

  useEffect(() => {
    if (episode == null) return;
    let disposed = false;
    void Promise.all([
      API.getKeyframePrompts(projectName, episode).catch(() => null),
      API.getKeyframes(projectName, episode).catch(() => null),
      API.getVideoPrompts(projectName, episode).catch(() => null),
      API.getDraftVideos(projectName, episode).catch(() => null),
    ]).then(([plan, status, videoPlan, draftVideos]) => {
      if (disposed) return;
      setKeyframePlan(plan);
      setKeyframeStatus(
        Object.fromEntries((status?.frames ?? []).map((frame) => [frame.keyframe_id, frame])),
      );
      setVideoPromptPlan(videoPlan);
      setDraftVideoStatus(draftVideos);
    });
    return () => {
      disposed = true;
    };
  }, [episode, projectName]);

  useEffect(() => {
    if (episode == null || !(draftVideoStatus?.videos ?? []).some(isDraftVideoTaskActive)) return;
    let disposed = false;
    const refresh = async () => {
      const status = await API.getDraftVideos(projectName, episode).catch(() => null);
      if (!disposed && status) setDraftVideoStatus(status);
    };
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [draftVideoStatus, episode, projectName]);

  useEffect(() => {
    if (episode == null || !Object.values(keyframeStatus).some(isKeyframeTaskActive)) return;
    let disposed = false;
    const refresh = async () => {
      const status = await API.getKeyframes(projectName, episode).catch(() => null);
      if (!disposed && status) {
        setKeyframeStatus(
          Object.fromEntries((status.frames ?? []).map((frame) => [frame.keyframe_id, frame])),
        );
      }
    };
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => {
      disposed = true;
      window.clearInterval(timer);
    };
  }, [episode, keyframeStatus, projectName]);

  // 镜头重排：请求在途时丢弃后续点击（快速连点会基于过期顺序计算出相同排列），
  // 移动成功后把选中态跟随到镜头的新位置——选中按索引存储，不跟随会静默切到被换位的邻居。
  const handleMoveShot = onMoveShot
    ? async (shotId: string, direction: "earlier" | "later") => {
        if (movePending) return;
        setMovePending(true);
        try {
          const moved = await onMoveShot(shotId, direction);
          if (moved) {
            setSelectedIndex((i) =>
              direction === "earlier" ? Math.max(0, i - 1) : Math.min(segments.length - 1, i + 1),
            );
          }
        } finally {
          setMovePending(false);
        }
      }
    : undefined;

  // 切镜时索引超界保护
  useEffect(() => {
    if (selectedIndex >= segments.length && segments.length > 0) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- 段数变更时夹紧索引
      setSelectedIndex(segments.length - 1);
    }
  }, [segments.length, selectedIndex]);

  // SSE 自动定位：分屏布局只需切换 selectedIndex，不做 DOM 滚动
  const scrollTarget = useAppStore((s) => s.scrollTarget);
  const clearScrollTarget = useAppStore((s) => s.clearScrollTarget);
  useEffect(() => {
    if (scrollTarget?.type !== "segment") return;
    const idx = segments.findIndex((s) => getScriptItemId(s, contentMode) === scrollTarget.id);
    if (idx !== -1) {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- 订阅 SSE 项目事件 store，触发后切换选中分镜
      setSelectedIndex(idx);
      clearScrollTarget(scrollTarget.request_id);
    } else if (Date.now() >= scrollTarget.expires_at) {
      // 当前 segments 不含该分镜（如事件指向其他剧集），过期后清理避免下次 segments 变更误触发
      clearScrollTarget(scrollTarget.request_id);
    }
  }, [scrollTarget, segments, contentMode, clearScrollTarget]);

  if (segments.length === 0) {
    return null;
  }

  const safeIndex = Math.min(selectedIndex, segments.length - 1);
  const segment = segments[safeIndex];
  const segmentId = getScriptItemId(segment, contentMode);
  const selectedKeyframePrompt =
    keyframePlan?.prompts.find((prompt) => prompt.shot_id === segmentId && prompt.role === "guide_reference") ??
    keyframePlan?.prompts.find((prompt) => prompt.shot_id === segmentId && prompt.role === "start_image") ??
    null;
  const selectedStartKeyframePrompt =
    keyframePlan?.prompts.find((prompt) => prompt.shot_id === segmentId && prompt.role === "start_image") ?? null;
  const selectedKeyframeExists = selectedKeyframePrompt
    ? (keyframeStatus[selectedKeyframePrompt.keyframe_id]?.exists ?? false)
    : false;
  const selectedKeyframeFrame = selectedKeyframePrompt
    ? (keyframeStatus[selectedKeyframePrompt.keyframe_id] ?? null)
    : null;
  const selectedStartKeyframeExists = selectedStartKeyframePrompt
    ? (keyframeStatus[selectedStartKeyframePrompt.keyframe_id]?.exists ?? false)
    : false;
  const selectedStartKeyframeFrame = selectedStartKeyframePrompt
    ? (keyframeStatus[selectedStartKeyframePrompt.keyframe_id] ?? null)
    : null;
  const selectedVideoPrompt = videoPromptPlan?.videos.find((video) => video.shot_id === segmentId) ?? null;
  const selectedDraftVideo = selectedVideoPrompt
    ? (draftVideoStatus?.videos.find((video) => video.video_id === selectedVideoPrompt.video_id) ?? null)
    : null;

  const handleSaveKeyframePrompt = async (
    keyframeId: string,
    patch: { prompt: string; negative_prompt?: string },
  ) => {
    if (!keyframePlan || episode == null) return;
    setSavingKeyframeId(keyframeId);
    try {
      const nextPlan: KeyframePromptPlan = {
        ...keyframePlan,
        prompts: keyframePlan.prompts.map((item) =>
          item.keyframe_id === keyframeId ? { ...item, ...patch } : item,
        ),
      };
      const saved = await API.updateKeyframePrompts(projectName, episode, nextPlan);
      setKeyframePlan(saved);
      pushToast(t("director_keyframe_prompt_saved"), "success");
    } catch {
      pushToast(t("director_keyframe_prompt_save_failed"), "error");
    } finally {
      setSavingKeyframeId(null);
    }
  };

  const handleCreateStartKeyframePrompt = async () => {
    if (!keyframePlan || !selectedVideoPrompt || episode == null) return;
    const existing = keyframePlan.prompts.find(
      (prompt) => prompt.shot_id === segmentId && prompt.role === "start_image",
    );
    if (existing) return;
    const created = buildStartKeyframePrompt(segmentId, segment, contentMode, selectedVideoPrompt);
    if (!created) return;
    setSavingKeyframeId(created.keyframe_id);
    try {
      const saved = await API.updateKeyframePrompts(projectName, episode, {
        ...keyframePlan,
        prompts: [...keyframePlan.prompts, created],
      });
      setKeyframePlan(saved);
      pushToast(t("director_start_keyframe_prompt_created"), "success");
    } catch {
      pushToast(t("director_start_keyframe_prompt_create_failed"), "error");
    } finally {
      setSavingKeyframeId(null);
    }
  };

  const handleGenerateKeyframe = async (keyframeId: string) => {
    const prompt = keyframePlan?.prompts.find((item) => item.keyframe_id === keyframeId);
    if (!prompt || episode == null) return;
    setGeneratingKeyframeId(keyframeId);
    try {
      const result = await API.generateKeyframe(projectName, keyframeId, {
        prompt: prompt.prompt,
        negative_prompt: prompt.negative_prompt ?? "",
        episode,
        shot_id: prompt.shot_id,
        role: prompt.role,
        reference_images:
          prompt.role === "guide_reference"
            ? []
            : buildKeyframeReferenceImages(currentProjectData, `${prompt.title}\n${prompt.prompt}`),
      });
      setKeyframeStatus((prev) => ({
        ...prev,
        [keyframeId]: {
          ...(prev[keyframeId] ?? {}),
          keyframe_id: keyframeId,
          shot_id: prompt.shot_id,
          role: prompt.role,
          file_path: `keyframes/${keyframeId}.png`,
          exists: prev[keyframeId]?.exists ?? false,
          fingerprint: prev[keyframeId]?.fingerprint ?? null,
          task_id: result.task_id,
          task_status: "queued",
          task_error_message: null,
        },
      }));
      pushToast(t("director_keyframe_generation_submitted"), "success");
      const status = await API.getKeyframes(projectName, episode);
      setKeyframeStatus(
        Object.fromEntries((status?.frames ?? []).map((frame) => [frame.keyframe_id, frame])),
      );
      const videoPlan = await API.getVideoPrompts(projectName, episode).catch(() => null);
      if (videoPlan) setVideoPromptPlan(videoPlan);
    } catch {
      pushToast(t("director_keyframe_generation_failed"), "error");
    } finally {
      setGeneratingKeyframeId(null);
    }
  };

  const handleSaveVideoPrompt = async (videoId: string, patch: { prompt?: string; reference_pack?: VideoPromptPack }) => {
    if (!videoPromptPlan || episode == null) return;
    setSavingVideoPromptId(videoId);
    const previousPlan = videoPromptPlan;
    const nextPlan: VideoPromptPlan = {
      ...videoPromptPlan,
      videos: videoPromptPlan.videos.map((item) =>
        item.video_id === videoId ? { ...item, ...patch } : item,
      ),
    };
    setVideoPromptPlan(nextPlan);
    try {
      const saved = await API.updateVideoPrompts(projectName, episode, nextPlan);
      setVideoPromptPlan(saved);
      pushToast(t("director_video_prompt_saved"), "success");
    } catch {
      setVideoPromptPlan(previousPlan);
      pushToast(t("director_video_prompt_save_failed"), "error");
    } finally {
      setSavingVideoPromptId(null);
    }
  };

  const handleGenerateDraftVideo = async (videoId: string) => {
    const video = videoPromptPlan?.videos.find((item) => item.video_id === videoId);
    if (!video || episode == null) return;
    const durationSeconds = segment.duration_seconds ?? video.duration_seconds ?? 4;
    setGeneratingDraftVideoId(videoId);
    try {
      const result = await API.generateDraftVideo(projectName, video.video_id, {
        prompt: video.prompt,
        episode,
        duration_seconds: durationSeconds,
        start_image: video.start_image,
        reference_pack: video.reference_pack,
        reference_images: null,
        seed: null,
      });
      setDraftVideoStatus((prev) => {
        const nextFrame: DraftVideoFrame = {
          video_id: video.video_id,
          shot_id: video.shot_id,
          keyframe_id: video.keyframe_id,
          file_path: `draft_videos/${video.video_id}.mp4`,
          exists: false,
          fingerprint: null,
          generation_inputs: null,
          task_id: result.task_id,
          task_status: "queued",
        };
        if (!prev) return { schema_version: 1, episode, videos: [nextFrame] };
        const found = prev.videos.some((item) => item.video_id === video.video_id);
        return {
          ...prev,
          videos: found
            ? prev.videos.map((item) =>
                item.video_id === video.video_id
                  ? { ...item, ...nextFrame, exists: item.exists, fingerprint: item.fingerprint }
                  : item,
              )
            : [...prev.videos, nextFrame],
        };
      });
      pushToast(t("director_draft_video_generation_submitted"), "success");
      const status = await API.getDraftVideos(projectName, episode);
      setDraftVideoStatus(status);
    } catch {
      pushToast(t("director_draft_video_generation_failed"), "error");
    } finally {
      setGeneratingDraftVideoId(null);
    }
  };

  return (
    <div
      className="grid h-full min-w-0 overflow-hidden"
      style={{
        gridTemplateColumns: collapsed ? "44px minmax(0, 1fr)" : "220px minmax(0, 1fr)",
        gridTemplateRows: "minmax(0, 1fr)",
      }}
    >
      <ShotList
        segments={segments}
        selectedIndex={safeIndex}
        onSelect={setSelectedIndex}
        contentMode={contentMode}
        projectName={projectName}
        collapsed={collapsed}
        onToggleCollapse={() => setCollapsed((c) => !c)}
        scrollContainerRef={listScrollRef}
      />
      <ShotDetail
        key={segmentId}
        segment={segment}
        segmentId={segmentId}
        contentMode={contentMode}
        aspectRatio={aspectRatio}
        projectName={projectName}
        episode={episode}
        scriptFile={scriptFile}
        isGridMode={isGridMode}
        selectedIndex={safeIndex}
        totalCount={segments.length}
        onPrev={() => setSelectedIndex((i) => Math.max(0, i - 1))}
        onNext={() => setSelectedIndex((i) => Math.min(segments.length - 1, i + 1))}
        onUpdatePrompt={onUpdatePrompt}
        onMoveShot={handleMoveShot}
        movePending={movePending}
        onGenerateStoryboard={onGenerateStoryboard}
        onGenerateVideo={onGenerateVideo}
        onGenerateNarration={onGenerateNarration}
        onRestoreStoryboard={onRestoreStoryboard}
        onRestoreVideo={onRestoreVideo}
        generatingStoryboard={generatingStoryboard?.(segmentId)}
        generatingVideo={generatingVideo?.(segmentId)}
        generatingNarration={generatingNarration?.(segmentId)}
        durationOptions={durationOptions}
        durationWarningReason={durationWarningReason}
        keyframePrompt={selectedKeyframePrompt}
        keyframeFrame={selectedKeyframeFrame}
        keyframeExists={selectedKeyframeExists}
        savingKeyframePrompt={selectedKeyframePrompt?.keyframe_id === savingKeyframeId}
        generatingKeyframe={
          selectedKeyframePrompt?.keyframe_id === generatingKeyframeId ||
          isKeyframeTaskActive(selectedKeyframeFrame)
        }
        startKeyframePrompt={selectedStartKeyframePrompt}
        startKeyframeFrame={selectedStartKeyframeFrame}
        startKeyframeExists={selectedStartKeyframeExists}
        savingStartKeyframePrompt={selectedStartKeyframePrompt?.keyframe_id === savingKeyframeId}
        generatingStartKeyframe={
          selectedStartKeyframePrompt?.keyframe_id === generatingKeyframeId ||
          isKeyframeTaskActive(selectedStartKeyframeFrame)
        }
        onSaveKeyframePrompt={handleSaveKeyframePrompt}
        onCreateStartKeyframePrompt={handleCreateStartKeyframePrompt}
        onGenerateKeyframe={handleGenerateKeyframe}
        videoPrompt={selectedVideoPrompt}
        draftVideo={selectedDraftVideo}
        savingVideoPrompt={selectedVideoPrompt?.video_id === savingVideoPromptId}
        generatingDraftVideo={
          selectedVideoPrompt?.video_id === generatingDraftVideoId || isDraftVideoTaskActive(selectedDraftVideo)
        }
        onSaveVideoPrompt={handleSaveVideoPrompt}
        onGenerateDraftVideo={handleGenerateDraftVideo}
      />
    </div>
  );
}
