import { useState, useEffect, useCallback, useId, type ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { Edit3, Save, Sparkles, X } from "lucide-react";
import { API } from "@/api";
import { errMsg, voidPromise } from "@/utils/async";
import { useAppStore } from "@/stores/app-store";
import { useProjectsStore } from "@/stores/projects-store";
import { StreamMarkdown } from "@/components/copilot/StreamMarkdown";
import { buildKeyframeReferenceImages } from "./keyframeReferences";
import type {
  DirectorShotPlan,
  DraftVideoFrame,
  DraftVideoQaPlan,
  DraftVideoStatus,
  KeyframeImageFrame,
  KeyframeImageStatus,
  KeyframePromptPlan,
  ProjectData,
  StoryAnalysisNamedItem,
  StoryBeatPlan,
  StoryImportAnalysis,
  VideoReferenceEntry,
  VideoGenerationInputs,
  VideoPromptPlan,
  VideoPromptPackItem,
} from "@/types";

/** Editing 控制 + 状态，`renderToolbar` 用这个接口把 toolbar 渲染抬升给调用方。 */
export interface PreprocessingToolbarContext {
  editing: boolean;
  saving: boolean;
  startEdit: () => void;
  save: () => void;
  cancel: () => void;
}

function compactNames(items: Array<{ name: string }>, fallback: string): string {
  const names = items.map((item) => item.name).filter(Boolean).slice(0, 6);
  return names.length ? names.join("、") : fallback;
}

function interactiveNodeLabel(kind: string): string {
  if (kind === "gameplay_entry") return "玩法入口";
  if (kind === "return_to_story") return "回归剧情";
  if (kind === "choice_point") return "选择点";
  if (kind === "hook") return "钩子";
  return kind || "交互节点";
}

type CandidateKind = "character" | "scene" | "prop";

interface CandidateDraft {
  selected: boolean;
  name: string;
  description: string;
}

type CandidateDraftMap = Record<string, CandidateDraft>;

interface AssetCandidate {
  kind: CandidateKind;
  item: StoryAnalysisNamedItem;
}

interface SourceFileOption {
  name: string;
  size: number;
}

function isDraftVideoTaskActive(video?: DraftVideoFrame | null): boolean {
  return video?.task_status === "queued" || video?.task_status === "running" || video?.task_status === "cancelling";
}

function isKeyframeTaskActive(frame?: KeyframeImageFrame | null): boolean {
  return frame?.task_status === "queued" || frame?.task_status === "running" || frame?.task_status === "cancelling";
}

type ChoicePointDraft = NonNullable<StoryImportAnalysis["choice_points"]>[number];
type ChoiceOptionDraft = ChoicePointDraft["options"][number];

interface ReferenceAssetOption {
  key: string;
  kind: CandidateKind;
  name: string;
  labelKey: string;
  role: string;
  path: string;
}

const MAX_REFERENCE_PACK_IMAGES = 9;

function candidateKey(kind: CandidateKind, name: string): string {
  return `${kind}:${name}`;
}

function collectAssetCandidates(analysis: StoryImportAnalysis): AssetCandidate[] {
  return [
    ...analysis.characters.map((item) => ({ kind: "character" as const, item })),
    ...analysis.scenes.map((item) => ({ kind: "scene" as const, item })),
    ...analysis.props.map((item) => ({ kind: "prop" as const, item })),
  ].filter(({ item }) => !!item.name?.trim());
}

function existingAssetNameSets(project: ProjectData | null): Record<CandidateKind, Set<string>> {
  return {
    character: new Set(Object.keys(project?.characters ?? {})),
    scene: new Set(Object.keys(project?.scenes ?? {})),
    prop: new Set(Object.keys(project?.props ?? {})),
  };
}

function isExistingCandidate(existingNames: Record<CandidateKind, Set<string>>, candidate: AssetCandidate): boolean {
  return existingNames[candidate.kind].has(candidate.item.name);
}

function buildReferenceAssetOptions(project: ProjectData | null): ReferenceAssetOption[] {
  const options: ReferenceAssetOption[] = [];
  for (const [name, character] of Object.entries(project?.characters ?? {})) {
    if (character.reference_image) {
      options.push({
        key: `character:${name}:face`,
        kind: "character",
        name,
        labelKey: "reference_pack_asset_face",
        role: "character_face_closeup",
        path: character.reference_image,
      });
    }
    if (character.character_sheet) {
      options.push({
        key: `character:${name}:turnaround`,
        kind: "character",
        name,
        labelKey: "reference_pack_asset_turnaround",
        role: "character_turnaround",
        path: character.character_sheet,
      });
    }
    if (character.character_combined_sheet) {
      options.push({
        key: `character:${name}:combined`,
        kind: "character",
        name,
        labelKey: "reference_pack_asset_combined",
        role: "character_combined_sheet",
        path: character.character_combined_sheet,
      });
    }
  }
  for (const [name, scene] of Object.entries(project?.scenes ?? {})) {
    if (scene.scene_sheet) {
      options.push({
        key: `scene:${name}`,
        kind: "scene",
        name,
        labelKey: "reference_pack_asset_scene",
        role: "scene_reference",
        path: scene.scene_sheet,
      });
    }
  }
  for (const [name, prop] of Object.entries(project?.props ?? {})) {
    if (prop.prop_sheet) {
      options.push({
        key: `prop:${name}`,
        kind: "prop",
        name,
        labelKey: "reference_pack_asset_prop",
        role: "prop_reference",
        path: prop.prop_sheet,
      });
    }
  }
  return options;
}

function referenceImageUrl(projectName: string, path: string | null | undefined): string | null {
  if (!path) return null;
  if (path.startsWith("_global_assets/")) {
    return API.getGlobalAssetUrl(path);
  }
  return API.getFileUrl(projectName, path);
}

function stringFromUnknown(value: unknown, fallback: string): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return fallback;
}

function normalizeReferenceEntries(raw: unknown): VideoReferenceEntry[] {
  if (!Array.isArray(raw)) {
    throw new Error("selected_images must be an array");
  }
  return raw.map((item) => {
    const record = item && typeof item === "object" && !Array.isArray(item) ? item as Record<string, unknown> : {};
    const path = stringFromUnknown(record.path, "");
    return {
      ...record,
      role: stringFromUnknown(record.role, "asset_reference"),
      path: path || null,
      submit_as: stringFromUnknown(record.submit_as, "reference_image"),
      required: Boolean(record.required),
      status: stringFromUnknown(record.status, path ? "ready" : "missing"),
    };
  });
}

function selectedImagePaths(entries: VideoReferenceEntry[]): Set<string> {
  return new Set(entries.map((entry) => entry.path || "").filter(Boolean));
}

function AssetCandidateList({
  kind,
  title,
  items,
  drafts,
  existingNames,
  creating,
  onToggle,
  onChangeDraft,
}: {
  kind: CandidateKind;
  title: string;
  items: StoryAnalysisNamedItem[];
  drafts: CandidateDraftMap;
  existingNames: Record<CandidateKind, Set<string>>;
  creating: boolean;
  onToggle: (key: string, checked: boolean) => void;
  onChangeDraft: (key: string, patch: Partial<Pick<CandidateDraft, "name" | "description">>) => void;
}) {
  const { t } = useTranslation(["dashboard", "common"]);
  if (!items.length) return null;
  return (
    <div className="rounded bg-gray-950/30 p-2">
      <div className="mb-1 text-xs font-medium text-gray-400">{title}</div>
      <div className="space-y-1">
        {items.map((item) => {
          const key = candidateKey(kind, item.name);
          const exists = existingNames[kind].has(item.name);
          const draft = drafts[key];
          return (
            <div
              key={key}
              className={`rounded px-1.5 py-1 text-xs ${
                exists ? "text-gray-500" : "text-gray-300"
              }`}
            >
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={!exists && !!draft?.selected}
                  disabled={exists || creating}
                  onChange={(event) => onToggle(key, event.currentTarget.checked)}
                  className="h-3.5 w-3.5 rounded border-gray-600 bg-gray-900 text-indigo-500"
                />
                <span className="min-w-0 flex-1 truncate">{item.name}</span>
                {typeof item.evidence_count === "number" && item.evidence_count > 0 && (
                  <span className="font-mono text-[10px] text-gray-500">×{item.evidence_count}</span>
                )}
                {exists && (
                  <span className="rounded bg-gray-800 px-1.5 py-0.5 text-[10px] text-gray-500">
                    {t("dashboard:story_analysis_asset_exists")}
                  </span>
                )}
              </label>
              {!exists && draft?.selected && (
                <div className="mt-1.5 grid gap-1">
                  <input
                    type="text"
                    value={draft.name}
                    disabled={creating}
                    aria-label={t("dashboard:story_analysis_asset_name_label", { name: item.name })}
                    onChange={(event) => onChangeDraft(key, { name: event.currentTarget.value })}
                    placeholder={t("dashboard:story_analysis_asset_name_placeholder")}
                    className="w-full rounded border border-gray-800 bg-gray-950/50 px-2 py-1 text-[11px] text-gray-200 outline-none focus:border-indigo-500"
                  />
                  <textarea
                    value={draft.description}
                    disabled={creating}
                    aria-label={t("dashboard:story_analysis_asset_description_label", { name: item.name })}
                    onChange={(event) => onChangeDraft(key, { description: event.currentTarget.value })}
                    placeholder={t("dashboard:story_analysis_asset_description_placeholder")}
                    rows={2}
                    className="w-full resize-y rounded border border-gray-800 bg-gray-950/50 px-2 py-1 text-[11px] leading-4 text-gray-300 outline-none focus:border-indigo-500"
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

function StoryAnalysisPanel({
  analysis,
  loading,
  generating,
  sourceFiles,
  sourceFilesLoading,
  selectedSourceFilename,
  onSelectSourceFilename,
  creatingAssets,
  candidateDrafts,
  existingNames,
  onGenerate,
  onToggleCandidate,
  onChangeCandidateDraft,
  onCreateSelectedAssets,
  savingChoicePoints,
  onSaveChoicePoints,
}: {
  analysis: StoryImportAnalysis | null;
  loading: boolean;
  generating: boolean;
  sourceFiles: SourceFileOption[];
  sourceFilesLoading: boolean;
  selectedSourceFilename: string;
  onSelectSourceFilename: (filename: string) => void;
  creatingAssets: boolean;
  candidateDrafts: CandidateDraftMap;
  existingNames: Record<CandidateKind, Set<string>>;
  onGenerate: () => void;
  onToggleCandidate: (key: string, checked: boolean) => void;
  onChangeCandidateDraft: (key: string, patch: Partial<Pick<CandidateDraft, "name" | "description">>) => void;
  onCreateSelectedAssets: () => void;
  savingChoicePoints: boolean;
  onSaveChoicePoints: (choicePoints: ChoicePointDraft[]) => Promise<void>;
}) {
  const { t } = useTranslation(["dashboard", "common"]);
  const [editingChoicePoints, setEditingChoicePoints] = useState(false);
  const [choicePointDrafts, setChoicePointDrafts] = useState<ChoicePointDraft[]>([]);

  const startChoicePointEdit = useCallback(() => {
    setChoicePointDrafts(analysis?.choice_points ?? []);
    setEditingChoicePoints(true);
  }, [analysis?.choice_points]);

  const updateChoicePointDraft = useCallback(
    (choiceIndex: number, patch: Partial<Pick<ChoicePointDraft, "prompt">>) => {
      setChoicePointDrafts((prev) =>
        prev.map((choice, index) => (index === choiceIndex ? { ...choice, ...patch } : choice)),
      );
    },
    [],
  );

  const updateChoiceOptionDraft = useCallback(
    (choiceIndex: number, optionIndex: number, patch: Partial<Pick<ChoiceOptionDraft, "label" | "branch_key" | "next_hint">>) => {
      setChoicePointDrafts((prev) =>
        prev.map((choice, index) => {
          if (index !== choiceIndex) return choice;
          return {
            ...choice,
            options: choice.options.map((option, nestedIndex) =>
              nestedIndex === optionIndex ? { ...option, ...patch } : option,
            ),
          };
        }),
      );
    },
    [],
  );

  const cancelChoicePointEdit = useCallback(() => {
    setChoicePointDrafts(analysis?.choice_points ?? []);
    setEditingChoicePoints(false);
  }, [analysis?.choice_points]);

  const saveChoicePointDrafts = useCallback(async () => {
    await onSaveChoicePoints(choicePointDrafts);
    setEditingChoicePoints(false);
  }, [choicePointDrafts, onSaveChoicePoints]);

  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-900/40 p-3 text-xs text-gray-500">
        {t("dashboard:story_analysis_loading")}
      </div>
    );
  }

  if (!analysis) {
    return (
      <div className="rounded-lg border border-dashed border-gray-700 bg-gray-900/35 p-3">
        <div className="mb-3 flex flex-wrap items-center gap-2 border-b border-gray-800 pb-3 text-xs">
          <span className="text-gray-500">分析源剧本</span>
          {sourceFiles.length > 0 ? (
            <select
              value={selectedSourceFilename}
              onChange={(event) => onSelectSourceFilename(event.target.value)}
              disabled={generating || sourceFilesLoading}
              className="rounded border border-gray-700 bg-gray-950 px-2 py-1 font-mono text-[11px] text-gray-200 outline-none focus:border-indigo-500 disabled:opacity-60"
              aria-label="选择分析源剧本"
            >
              {sourceFiles.map((file) => (
                <option key={file.name} value={file.name}>
                  {file.name}
                </option>
              ))}
            </select>
          ) : (
            <span className="rounded bg-gray-950 px-2 py-1 text-[11px] text-amber-300">
              {sourceFilesLoading ? "读取源剧本中…" : "未找到 source 剧本，将回退读取 step1 草稿"}
            </span>
          )}
        </div>
        <div>
          <div className="text-sm font-medium text-gray-200">{t("dashboard:story_analysis_empty_title")}</div>
          <div className="mt-1 text-xs text-gray-500">{t("dashboard:story_analysis_empty_desc")}</div>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:story_analysis_generating") : t("dashboard:story_analysis_generate")}
        </button>
      </div>
    );
  }

  const candidates = collectAssetCandidates(analysis);
  const selectedCount = candidates.filter(
    (candidate) =>
      !isExistingCandidate(existingNames, candidate) &&
      !!candidateDrafts[candidateKey(candidate.kind, candidate.item.name)]?.selected &&
      !!candidateDrafts[candidateKey(candidate.kind, candidate.item.name)]?.name.trim(),
  ).length;
  const interactiveNodes = analysis.interactive_nodes ?? [];
  const choicePoints = editingChoicePoints ? choicePointDrafts : analysis.choice_points ?? [];

  return (
    <section className="rounded-lg border border-gray-800 bg-gray-900/45 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-200">{t("dashboard:story_analysis_title")}</div>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-[10.5px] text-gray-500">
            <span>当前分析来源</span>
            {sourceFiles.length > 0 ? (
              <select
                value={selectedSourceFilename}
                onChange={(event) => onSelectSourceFilename(event.target.value)}
                disabled={generating || sourceFilesLoading}
                className="rounded border border-gray-700 bg-gray-950 px-1.5 py-0.5 font-mono text-[10.5px] text-gray-200 outline-none focus:border-indigo-500 disabled:opacity-60"
                aria-label="选择分析源剧本"
              >
                {sourceFiles.map((file) => (
                  <option key={file.name} value={file.name}>
                    {file.name}
                  </option>
                ))}
              </select>
            ) : (
              <span className="font-mono" translate="no">
                {analysis.source_filename || "step1 草稿"}
              </span>
            )}
            {analysis.source_filename && selectedSourceFilename && analysis.source_filename !== selectedSourceFilename && (
              <span className="rounded bg-amber-500/10 px-1.5 py-0.5 text-amber-300">
                已切换源文件，点击重新分析后生效
              </span>
            )}
          </div>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-xs text-indigo-300 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:story_analysis_generating") : t("dashboard:story_analysis_regenerate")}
        </button>
      </div>
      {analysis.summary && <p className="mb-3 text-xs leading-relaxed text-gray-400">{analysis.summary}</p>}
      {analysis.template_name && (
        <div className="mb-3 rounded border border-indigo-500/20 bg-indigo-500/5 px-2 py-1.5 text-xs text-indigo-200">
          类型模板：{analysis.template_name}
          {analysis.template_focus ? <span className="ml-2 text-indigo-200/70">{analysis.template_focus}</span> : null}
        </div>
      )}
      {interactiveNodes.length > 0 && (
        <div className="mb-3 rounded border border-purple-500/20 bg-purple-500/5 p-2 text-xs">
          <div className="mb-1 font-medium text-purple-200">剧游节点</div>
          <ul className="m-0 space-y-1 p-0">
            {interactiveNodes.slice(0, 5).map((node) => (
              <li key={node.node_id} className="list-none text-gray-400">
                <span className="mr-1 rounded bg-purple-500/10 px-1.5 py-0.5 text-purple-200">
                  {interactiveNodeLabel(node.kind)}
                </span>
                <span>{node.text}</span>
                {node.options?.length ? (
                  <span className="ml-1 text-gray-500">选项：{node.options.join(" / ")}</span>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
      {choicePoints.length > 0 && (
        <div className="mb-3 rounded border border-amber-500/20 bg-amber-500/5 p-2 text-xs">
          <div className="mb-2 flex items-center justify-between gap-2">
            <div className="font-medium text-amber-200">分支结构</div>
            {editingChoicePoints ? (
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  onClick={voidPromise(saveChoicePointDrafts)}
                  disabled={savingChoicePoints}
                  className="rounded bg-amber-500 px-2 py-1 text-[11px] font-medium text-gray-950 transition-colors hover:bg-amber-400 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {savingChoicePoints ? "保存中" : "保存分支"}
                </button>
                <button
                  type="button"
                  onClick={cancelChoicePointEdit}
                  disabled={savingChoicePoints}
                  className="rounded bg-gray-800 px-2 py-1 text-[11px] text-gray-300 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  取消
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={startChoicePointEdit}
                className="rounded bg-amber-500/10 px-2 py-1 text-[11px] text-amber-200 transition-colors hover:bg-amber-500/20"
              >
                编辑分支
              </button>
            )}
          </div>
          <ul className="m-0 space-y-1 p-0">
            {choicePoints.slice(0, 5).map((choice, choiceIndex) => (
              <li key={choice.choice_id} className="list-none rounded bg-gray-950/20 p-2 text-gray-400">
                <span className="mr-1 rounded bg-amber-500/10 px-1.5 py-0.5 font-mono text-amber-200">
                  {choice.choice_id}
                </span>
                {editingChoicePoints ? (
                  <input
                    aria-label={`${choice.choice_id} 选择提示`}
                    value={choice.prompt}
                    onChange={(event) => updateChoicePointDraft(choiceIndex, { prompt: event.target.value })}
                    className="mt-2 w-full rounded border border-gray-800 bg-gray-950/60 px-2 py-1 text-[11px] text-gray-300 outline-none focus:border-amber-500"
                  />
                ) : (
                  <span>{choice.prompt}</span>
                )}
                {choice.options.length > 0 && !editingChoicePoints ? (
                  <div className="mt-1 flex flex-wrap gap-1">
                    {choice.options.map((option) => (
                      <span key={option.option_id} className="rounded bg-gray-950/40 px-1.5 py-0.5 text-gray-500">
                        {option.option_id} · {option.branch_key} · {option.label}
                      </span>
                    ))}
                  </div>
                ) : null}
                {choice.options.length > 0 && editingChoicePoints ? (
                  <div className="mt-2 space-y-1.5">
                    {choice.options.map((option, optionIndex) => (
                      <div key={option.option_id} className="grid gap-1 md:grid-cols-[1fr_120px_1fr]">
                        <input
                          aria-label={`${option.option_id} 选项文案`}
                          value={option.label}
                          onChange={(event) =>
                            updateChoiceOptionDraft(choiceIndex, optionIndex, { label: event.target.value })
                          }
                          className="rounded border border-gray-800 bg-gray-950/60 px-2 py-1 text-[11px] text-gray-300 outline-none focus:border-amber-500"
                        />
                        <input
                          aria-label={`${option.option_id} 分支键`}
                          value={option.branch_key}
                          onChange={(event) =>
                            updateChoiceOptionDraft(choiceIndex, optionIndex, { branch_key: event.target.value })
                          }
                          className="rounded border border-gray-800 bg-gray-950/60 px-2 py-1 font-mono text-[11px] text-gray-300 outline-none focus:border-amber-500"
                        />
                        <input
                          aria-label={`${option.option_id} 后续提示`}
                          value={option.next_hint ?? ""}
                          placeholder="后续剧情提示"
                          onChange={(event) =>
                            updateChoiceOptionDraft(choiceIndex, optionIndex, { next_hint: event.target.value })
                          }
                          className="rounded border border-gray-800 bg-gray-950/60 px-2 py-1 text-[11px] text-gray-300 outline-none focus:border-amber-500"
                        />
                      </div>
                    ))}
                  </div>
                ) : null}
              </li>
            ))}
          </ul>
        </div>
      )}
      <dl className="grid gap-2 text-xs md:grid-cols-2">
        <div className="rounded bg-gray-950/35 p-2">
          <dt className="mb-1 text-gray-500">{t("dashboard:story_analysis_beats")}</dt>
          <dd className="text-gray-300">{analysis.story_beats.length}</dd>
        </div>
        <div className="rounded bg-gray-950/35 p-2">
          <dt className="mb-1 text-gray-500">{t("dashboard:story_analysis_characters")}</dt>
          <dd className="text-gray-300">{compactNames(analysis.characters, t("dashboard:story_analysis_none"))}</dd>
        </div>
        <div className="rounded bg-gray-950/35 p-2">
          <dt className="mb-1 text-gray-500">{t("dashboard:story_analysis_scenes")}</dt>
          <dd className="text-gray-300">{compactNames(analysis.scenes, t("dashboard:story_analysis_none"))}</dd>
        </div>
        <div className="rounded bg-gray-950/35 p-2">
          <dt className="mb-1 text-gray-500">{t("dashboard:story_analysis_props")}</dt>
          <dd className="text-gray-300">{compactNames(analysis.props, t("dashboard:story_analysis_none"))}</dd>
        </div>
      </dl>
      {analysis.hard_points.length > 0 && (
        <div className="mt-3">
          <div className="mb-1 text-xs text-gray-500">{t("dashboard:story_analysis_hard_points")}</div>
          <ul className="m-0 list-disc space-y-1 pl-4 text-xs text-gray-400">
            {analysis.hard_points.slice(0, 4).map((point) => (
              <li key={`${point.type}:${point.label}`}>{point.label}</li>
            ))}
          </ul>
        </div>
      )}
      {candidates.length > 0 && (
        <div className="mt-3 rounded-lg border border-gray-800 bg-gray-900/35 p-2.5">
          <div className="mb-2 flex items-center justify-between gap-3">
            <div>
              <div className="text-xs font-semibold text-gray-300">
                {t("dashboard:story_analysis_asset_candidates")}
              </div>
              <div className="mt-0.5 text-[11px] text-gray-500">
                {t("dashboard:story_analysis_asset_candidates_desc")}
              </div>
            </div>
            <button
              type="button"
              onClick={onCreateSelectedAssets}
              disabled={creatingAssets || selectedCount === 0}
              className="shrink-0 rounded bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {creatingAssets
                ? t("dashboard:story_analysis_asset_creating")
                : t("dashboard:story_analysis_asset_create_selected", { count: selectedCount })}
            </button>
          </div>
          <div className="grid gap-2 md:grid-cols-3">
            <AssetCandidateList
              kind="character"
              title={t("dashboard:story_analysis_characters")}
              items={analysis.characters}
              drafts={candidateDrafts}
              existingNames={existingNames}
              creating={creatingAssets}
              onToggle={onToggleCandidate}
              onChangeDraft={onChangeCandidateDraft}
            />
            <AssetCandidateList
              kind="scene"
              title={t("dashboard:story_analysis_scenes")}
              items={analysis.scenes}
              drafts={candidateDrafts}
              existingNames={existingNames}
              creating={creatingAssets}
              onToggle={onToggleCandidate}
              onChangeDraft={onChangeCandidateDraft}
            />
            <AssetCandidateList
              kind="prop"
              title={t("dashboard:story_analysis_props")}
              items={analysis.props}
              drafts={candidateDrafts}
              existingNames={existingNames}
              creating={creatingAssets}
              onToggle={onToggleCandidate}
              onChangeDraft={onChangeCandidateDraft}
            />
          </div>
        </div>
      )}
    </section>
  );
}

function StoryBeatPanel({
  plan,
  loading,
  generating,
  analysisReady,
  onGenerate,
}: {
  plan: StoryBeatPlan | null;
  loading: boolean;
  generating: boolean;
  analysisReady: boolean;
  onGenerate: () => void;
}) {
  const { t } = useTranslation(["dashboard", "common"]);
  if (!analysisReady) return null;
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-900/40 p-3 text-xs text-gray-500">
        {t("dashboard:story_beats_loading")}
      </div>
    );
  }
  if (!plan) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-gray-700 bg-gray-900/35 p-3">
        <div>
          <div className="text-sm font-medium text-gray-200">{t("dashboard:story_beats_empty_title")}</div>
          <div className="mt-1 text-xs text-gray-500">{t("dashboard:story_beats_empty_desc")}</div>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:story_beats_generating") : t("dashboard:story_beats_generate")}
        </button>
      </div>
    );
  }
  return (
    <section className="rounded-lg border border-gray-800 bg-gray-900/45 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-200">{t("dashboard:story_beats_title")}</div>
          <div className="mt-0.5 text-[11px] text-gray-500">
            {t("dashboard:story_beats_meta", {
              beats: plan.beats.length,
              seconds: plan.total_estimated_seconds,
            })}
          </div>
          {plan.template_name && (
            <div className="mt-0.5 text-[11px] text-indigo-300">
              类型模板：{plan.template_name}
              {plan.template_focus ? ` · ${plan.template_focus}` : ""}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-xs text-indigo-300 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:story_beats_generating") : t("dashboard:story_beats_regenerate")}
        </button>
      </div>
      <div className="space-y-2">
        {plan.beats.slice(0, 8).map((beat) => (
          <div key={beat.beat_id} className="rounded bg-gray-950/35 p-2 text-xs">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-mono text-[10px] text-indigo-300">{beat.beat_id}</div>
                <div className="mt-0.5 truncate font-medium text-gray-200">{beat.title}</div>
              </div>
              <div className="shrink-0 font-mono text-[10px] text-gray-500">
                {beat.estimated_seconds}s · {beat.micro_beats.length}
              </div>
            </div>
            {beat.summary && <div className="mt-1 line-clamp-2 text-gray-500">{beat.summary}</div>}
          </div>
        ))}
      </div>
    </section>
  );
}

function DirectorShotPanel({
  plan,
  loading,
  generating,
  storyBeatsReady,
  onGenerate,
}: {
  plan: DirectorShotPlan | null;
  loading: boolean;
  generating: boolean;
  storyBeatsReady: boolean;
  onGenerate: () => void;
}) {
  const { t } = useTranslation(["dashboard", "common"]);
  if (!storyBeatsReady) return null;
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-900/40 p-3 text-xs text-gray-500">
        {t("dashboard:director_shots_loading")}
      </div>
    );
  }
  if (!plan) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-gray-700 bg-gray-900/35 p-3">
        <div>
          <div className="text-sm font-medium text-gray-200">{t("dashboard:director_shots_empty_title")}</div>
          <div className="mt-1 text-xs text-gray-500">{t("dashboard:director_shots_empty_desc")}</div>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:director_shots_generating") : t("dashboard:director_shots_generate")}
        </button>
      </div>
    );
  }

  const shotCount = plan.shot_groups.reduce((total, group) => total + group.shots.length, 0);

  return (
    <section className="rounded-lg border border-gray-800 bg-gray-900/45 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-200">{t("dashboard:director_shots_title")}</div>
          <div className="mt-0.5 text-[11px] text-gray-500">
            {t("dashboard:director_shots_meta", {
              groups: plan.shot_groups.length,
              shots: shotCount,
              seconds: plan.total_duration_seconds,
            })}
          </div>
          {plan.template_name && (
            <div className="mt-0.5 text-[11px] text-indigo-300">
              类型模板：{plan.template_name}
              {plan.template_focus ? ` · ${plan.template_focus}` : ""}
            </div>
          )}
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-xs text-indigo-300 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:director_shots_generating") : t("dashboard:director_shots_regenerate")}
        </button>
      </div>
      <div className="space-y-2">
        {plan.shot_groups.map((group) => (
          <div key={group.group_id} className="rounded bg-gray-950/35 p-2 text-xs">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-mono text-[10px] text-purple-300">{group.group_id}</div>
                <div className="mt-0.5 truncate font-medium text-gray-200">{group.title}</div>
              </div>
              <div className="shrink-0 font-mono text-[10px] text-gray-500">
                {group.duration_seconds}s · {group.shots.length}
              </div>
            </div>
            <div className="mt-2 space-y-1">
              {group.shots.map((shot) => (
                <div key={shot.shot_id} className="rounded border border-gray-800/80 bg-gray-900/45 px-2 py-1.5">
                  <div className="flex items-center justify-between gap-2">
                    <div className="min-w-0 truncate">
                      <span className="font-mono text-[10px] text-indigo-300">{shot.shot_id}</span>
                      <span className="ml-2 text-gray-300">{shot.title}</span>
                    </div>
                    <span className="shrink-0 font-mono text-[10px] text-gray-500">{shot.duration_seconds}s</span>
                  </div>
                  <div className="mt-1 line-clamp-1 text-[11px] text-gray-500">
                    {shot.shot_size} · {shot.camera_movement} · {shot.image_roles.join(" / ")}
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function KeyframePromptPanel({
  projectName,
  plan,
  loading,
  generating,
  imageStatus,
  imageStatusLoading,
  imageGenerating,
  directorShotsReady,
  onGenerate,
  onGenerateImages,
}: {
  projectName: string;
  plan: KeyframePromptPlan | null;
  loading: boolean;
  generating: boolean;
  imageStatus: KeyframeImageStatus | null;
  imageStatusLoading: boolean;
  imageGenerating: boolean;
  directorShotsReady: boolean;
  onGenerate: () => void;
  onGenerateImages: () => void;
}) {
  const { t } = useTranslation(["dashboard", "common"]);
  if (!directorShotsReady) return null;
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-900/40 p-3 text-xs text-gray-500">
        {t("dashboard:keyframe_prompts_loading")}
      </div>
    );
  }
  if (!plan) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-gray-700 bg-gray-900/35 p-3">
        <div>
          <div className="text-sm font-medium text-gray-200">{t("dashboard:keyframe_prompts_empty_title")}</div>
          <div className="mt-1 text-xs text-gray-500">{t("dashboard:keyframe_prompts_empty_desc")}</div>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:keyframe_prompts_generating") : t("dashboard:keyframe_prompts_generate")}
        </button>
      </div>
    );
  }

  const frameById = new Map((imageStatus?.frames ?? []).map((frame) => [frame.keyframe_id, frame]));
  const generatablePrompts = plan.prompts.filter((prompt) => prompt.role !== "review_frame");
  const generatedCount = generatablePrompts.filter((prompt) => frameById.get(prompt.keyframe_id)?.exists).length;
  const activeCount = generatablePrompts.filter((prompt) => isKeyframeTaskActive(frameById.get(prompt.keyframe_id))).length;

  return (
    <section className="rounded-lg border border-gray-800 bg-gray-900/45 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-200">{t("dashboard:keyframe_prompts_title")}</div>
          <div className="mt-0.5 text-[11px] text-gray-500">
            {t("dashboard:keyframe_prompts_meta", {
              prompts: plan.prompts.length,
              shots: plan.source_shot_count,
              seconds: plan.total_duration_seconds,
            })}
          </div>
          <div className="mt-0.5 text-[11px] text-gray-500">
            {imageStatusLoading
              ? t("dashboard:keyframe_images_loading")
              : t("dashboard:keyframe_images_meta", {
                  generated: generatedCount,
                  total: generatablePrompts.length,
                }) + (activeCount > 0 ? ` · ${activeCount} 个生成中` : "")}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={onGenerateImages}
            disabled={imageGenerating || generatablePrompts.length === 0}
            className="flex items-center gap-1.5 rounded bg-indigo-500 px-2 py-1 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {imageGenerating ? t("dashboard:keyframe_images_generating") : t("dashboard:keyframe_images_generate_all")}
          </button>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating}
            className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-indigo-300 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {generating ? t("dashboard:keyframe_prompts_generating") : t("dashboard:keyframe_prompts_regenerate")}
          </button>
        </div>
      </div>
      <div className="space-y-2">
        {plan.prompts.map((prompt) => {
          const frame = frameById.get(prompt.keyframe_id);
          const active = isKeyframeTaskActive(frame);
          const failed = frame?.task_status === "failed";
          const imageUrl = frame?.exists && frame.file_path
            ? API.getFileUrl(projectName, frame.file_path, frame.fingerprint)
            : null;
          return (
            <div key={prompt.keyframe_id} className="rounded bg-gray-950/35 p-2 text-xs">
              <div className="flex gap-2">
                {imageUrl ? (
                  <img
                    src={imageUrl}
                    alt={prompt.title}
                    className="h-20 w-14 shrink-0 rounded border border-gray-800 object-cover"
                  />
                ) : (
                  <div className="flex h-20 w-14 shrink-0 items-center justify-center rounded border border-dashed border-gray-800 bg-gray-950/60 text-[10px] text-gray-600">
                    {active
                      ? "生成中"
                      : failed
                        ? "失败"
                        : prompt.role === "start_image"
                          ? t("dashboard:keyframe_images_missing")
                          : t("dashboard:keyframe_images_review_only")}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-mono text-[10px] text-emerald-300">{prompt.keyframe_id}</div>
                      <div className="mt-0.5 truncate font-medium text-gray-200">{prompt.title}</div>
                    </div>
                    <div
                      className={`shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] ${
                        frame?.exists
                          ? "bg-emerald-500/15 text-emerald-300"
                          : active
                            ? "bg-sky-500/15 text-sky-300"
                            : failed
                              ? "bg-red-500/15 text-red-300"
                              : "bg-gray-800 text-gray-400"
                      }`}
                    >
                      {frame?.exists ? "已生成" : active ? "生成中" : failed ? "失败" : prompt.role}
                    </div>
                  </div>
                  {failed && frame?.task_error_message && (
                    <div className="mt-1 rounded border border-red-500/20 bg-red-500/10 px-2 py-1 text-[11px] text-red-300">
                      {frame.task_error_message}
                    </div>
                  )}
                  <div className="mt-1 whitespace-pre-wrap break-words text-[11px] leading-4 text-gray-500">
                    {prompt.prompt}
                  </div>
                  {prompt.reference_policy && (
                    <div className="mt-1 text-[11px] text-gray-500">{prompt.reference_policy}</div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

function VideoPromptPanel({
  projectName,
  projectData,
  plan,
  loading,
  generating,
  videoStatus,
  videoStatusLoading,
  videoGenerating,
  keyframesReady,
  onGenerate,
  onGenerateVideos,
  savingReferencePackId,
  onSaveReferencePack,
}: {
  projectName: string;
  projectData: ProjectData | null;
  plan: VideoPromptPlan | null;
  loading: boolean;
  generating: boolean;
  videoStatus: DraftVideoStatus | null;
  videoStatusLoading: boolean;
  videoGenerating: boolean;
  keyframesReady: boolean;
  onGenerate: () => void;
  onGenerateVideos: () => void;
  savingReferencePackId: string | null;
  onSaveReferencePack: (videoId: string, selectedImages: VideoReferenceEntry[]) => Promise<void>;
}) {
  const { t } = useTranslation(["dashboard", "common"]);
  const [editingPackVideoId, setEditingPackVideoId] = useState<string | null>(null);
  const [packDraft, setPackDraft] = useState("");
  const [packError, setPackError] = useState<string | null>(null);
  const assetOptions = buildReferenceAssetOptions(projectData);

  const startEditReferencePack = (video: VideoPromptPackItem) => {
    setEditingPackVideoId(video.video_id);
    setPackDraft(JSON.stringify(video.reference_pack?.selected_images ?? [], null, 2));
    setPackError(null);
  };

  const saveReferencePack = async (video: VideoPromptPackItem) => {
    let parsed: unknown;
    try {
      parsed = JSON.parse(packDraft);
      const selectedImages = normalizeReferenceEntries(parsed);
      if (selectedImages.length > MAX_REFERENCE_PACK_IMAGES) {
        throw new Error(t("dashboard:reference_pack_max_reached"));
      }
      await onSaveReferencePack(video.video_id, selectedImages);
      setEditingPackVideoId(null);
      setPackDraft("");
      setPackError(null);
    } catch (error) {
      setPackError(errMsg(error, t("dashboard:reference_pack_invalid_json")));
    }
  };

  const addAssetReference = (option: ReferenceAssetOption) => {
    let selectedImages: VideoReferenceEntry[];
    try {
      selectedImages = normalizeReferenceEntries(JSON.parse(packDraft || "[]"));
    } catch {
      setPackError(t("dashboard:reference_pack_invalid_json"));
      return;
    }

    if (selectedImages.length >= MAX_REFERENCE_PACK_IMAGES) {
      setPackError(t("dashboard:reference_pack_max_reached"));
      return;
    }
    if (selectedImagePaths(selectedImages).has(option.path)) {
      setPackError(t("dashboard:reference_pack_duplicate"));
      return;
    }

    setPackDraft(
      JSON.stringify(
        [
          ...selectedImages,
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
        null,
        2,
      ),
    );
    setPackError(null);
  };

  if (!keyframesReady) return null;
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-900/40 p-3 text-xs text-gray-500">
        {t("dashboard:video_prompts_loading")}
      </div>
    );
  }
  if (!plan) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-gray-700 bg-gray-900/35 p-3">
        <div>
          <div className="text-sm font-medium text-gray-200">{t("dashboard:video_prompts_empty_title")}</div>
          <div className="mt-1 text-xs text-gray-500">{t("dashboard:video_prompts_empty_desc")}</div>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:video_prompts_generating") : t("dashboard:video_prompts_generate")}
        </button>
      </div>
    );
  }

  const videoById = new Map((videoStatus?.videos ?? []).map((video) => [video.video_id, video]));
  const submittableVideos = plan.videos.filter((video) => !video.submit_blockers.length);
  const generatedCount = submittableVideos.filter((video) => videoById.get(video.video_id)?.exists).length;
  const activeCount = submittableVideos.filter((video) => isDraftVideoTaskActive(videoById.get(video.video_id))).length;

  return (
    <section className="rounded-lg border border-gray-800 bg-gray-900/45 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-200">{t("dashboard:video_prompts_title")}</div>
          <div className="mt-0.5 text-[11px] text-gray-500">
            {t("dashboard:video_prompts_meta", {
              ready: plan.ready_video_count,
              total: plan.videos.length,
              seconds: plan.total_duration_seconds,
            })}
          </div>
          <div className="mt-0.5 text-[11px] text-gray-500">
            {videoStatusLoading
              ? t("dashboard:draft_videos_loading")
              : t("dashboard:draft_videos_meta", {
                  generated: generatedCount,
                  total: submittableVideos.length,
                }) + (activeCount > 0 ? ` · ${activeCount} 个生成中` : "")}
          </div>
        </div>
        <div className="flex shrink-0 items-center gap-1">
          <button
            type="button"
            onClick={onGenerateVideos}
            disabled={videoGenerating || !!savingReferencePackId || submittableVideos.length === 0}
            className="flex items-center gap-1.5 rounded bg-indigo-500 px-2 py-1 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {videoGenerating ? t("dashboard:draft_videos_generating") : t("dashboard:draft_videos_generate_all")}
          </button>
          <button
            type="button"
            onClick={onGenerate}
            disabled={generating}
            className="flex items-center gap-1.5 rounded px-2 py-1 text-xs text-indigo-300 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
          >
            <Sparkles className="h-3.5 w-3.5" />
            {generating ? t("dashboard:video_prompts_generating") : t("dashboard:video_prompts_regenerate")}
          </button>
        </div>
      </div>
      <div className="space-y-2">
        {plan.videos.slice(0, 6).map((video) => {
          const ready = !video.submit_blockers.length;
          const draftVideo = videoById.get(video.video_id);
          const active = isDraftVideoTaskActive(draftVideo);
          const failed = draftVideo?.task_status === "failed";
          const videoUrl = draftVideo?.exists
            ? API.getFileUrl(projectName, draftVideo.file_path, draftVideo.fingerprint)
            : null;
          const imageUrl = ready && !videoUrl && video.start_image ? API.getFileUrl(projectName, video.start_image) : null;
          return (
            <div key={video.video_id} className="rounded bg-gray-950/35 p-2 text-xs">
              <div className="flex gap-2">
                {videoUrl ? (
                  <video
                    src={videoUrl}
                    controls
                    className="h-20 w-14 shrink-0 rounded border border-gray-800 object-cover"
                  >
                    <track kind="captions" />
                  </video>
                ) : imageUrl ? (
                  <img
                    src={imageUrl}
                    alt={video.title}
                    className="h-20 w-14 shrink-0 rounded border border-gray-800 object-cover"
                  />
                ) : (
                  <div className="flex h-20 w-14 shrink-0 items-center justify-center rounded border border-dashed border-gray-800 bg-gray-950/60 text-center text-[10px] text-gray-600">
                    {ready ? t("dashboard:draft_videos_missing") : t("dashboard:video_prompts_start_image_missing")}
                  </div>
                )}
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <div className="font-mono text-[10px] text-sky-300">{video.video_id}</div>
                      <div className="mt-0.5 truncate font-medium text-gray-200">{video.title}</div>
                    </div>
                    <div
                      className={`shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] ${
                        draftVideo?.exists
                          ? "bg-emerald-500/15 text-emerald-300"
                          : active
                            ? "bg-sky-500/15 text-sky-300"
                            : failed
                              ? "bg-red-500/15 text-red-300"
                              : ready
                                ? "bg-emerald-500/15 text-emerald-300"
                                : "bg-amber-500/15 text-amber-300"
                      }`}
                    >
                      {draftVideo?.exists
                        ? "已生成"
                        : active
                          ? "生成中"
                          : failed
                            ? "失败"
                            : ready
                              ? t("dashboard:video_prompts_ready")
                              : t("dashboard:video_prompts_blocked")}
                    </div>
                  </div>
                  <div className="mt-1 font-mono text-[10px] text-gray-500">
                    {video.duration_seconds}s · start_image: {video.start_image}
                  </div>
                  <div className="mt-1 line-clamp-2 whitespace-pre-line text-[11px] leading-4 text-gray-500">
                    {video.prompt}
                  </div>
                  <div className="mt-2 rounded border border-gray-800 bg-gray-900/50 p-2">
                    <div className="flex items-center justify-between gap-2">
                      <div className="text-[11px] font-medium text-gray-300">
                        {t("dashboard:reference_pack_title")} ·{" "}
                        {t("dashboard:reference_pack_count", {
                          count: video.reference_pack?.selected_images?.length ?? 0,
                        })}
                      </div>
                      <button
                        type="button"
                        onClick={() => startEditReferencePack(video)}
                        className="rounded px-1.5 py-0.5 text-[11px] text-indigo-300 transition-colors hover:bg-gray-800"
                      >
                        {t("dashboard:reference_pack_edit")}
                      </button>
                    </div>
                    {(video.reference_pack?.selected_images?.length ?? 0) > 0 ? (
                      <div className="mt-2 grid gap-1.5">
                        {video.reference_pack.selected_images.map((entry, index) => {
                          const refUrl = referenceImageUrl(projectName, entry.path);
                          return (
                            <div
                              key={`${entry.role}-${entry.path ?? index}`}
                              className="flex items-center gap-2 rounded bg-gray-950/50 p-1.5"
                            >
                              {refUrl ? (
                                <img
                                  src={refUrl}
                                  alt={entry.role}
                                  className="h-9 w-9 shrink-0 rounded border border-gray-800 object-cover"
                                />
                              ) : (
                                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded border border-dashed border-gray-800 text-[9px] text-gray-600">
                                  ref
                                </div>
                              )}
                              <div className="min-w-0 flex-1">
                                <div className="font-mono text-[10px] text-gray-300">
                                  {entry.role} → {entry.submit_as}
                                </div>
                                <div className="truncate font-mono text-[10px] text-gray-500">
                                  {entry.path || t("dashboard:reference_pack_path_missing")}
                                </div>
                              </div>
                            </div>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="mt-1 text-[11px] text-gray-500">{t("dashboard:reference_pack_empty")}</div>
                    )}
                    {editingPackVideoId === video.video_id && (
                      <div className="mt-2 space-y-2">
                        <div className="rounded border border-gray-800 bg-gray-950/60 p-2">
                          <div className="text-[11px] font-medium text-gray-300">
                            {t("dashboard:reference_pack_asset_picker")}
                          </div>
                          {assetOptions.length ? (
                            <div className="mt-2 flex flex-wrap gap-1">
                              {assetOptions.map((option) => (
                                <button
                                  key={option.key}
                                  type="button"
                                  onClick={() => addAssetReference(option)}
                                  className="rounded bg-gray-800 px-2 py-1 text-[11px] text-gray-300 transition-colors hover:bg-gray-700"
                                >
                                  {option.name} · {t(`dashboard:${option.labelKey}`)}
                                </button>
                              ))}
                            </div>
                          ) : (
                            <div className="mt-1 text-[11px] text-gray-500">
                              {t("dashboard:reference_pack_asset_picker_empty")}
                            </div>
                          )}
                        </div>
                        <textarea
                          aria-label={t("dashboard:reference_pack_json_label")}
                          value={packDraft}
                          onChange={(event) => setPackDraft(event.target.value)}
                          rows={7}
                          className="w-full resize-y rounded border border-gray-800 bg-gray-950 p-2 font-mono text-[11px] leading-4 text-gray-300 outline-none focus-ring focus-visible:border-indigo-500"
                        />
                        {packError && <div className="text-[11px] text-red-300">{packError}</div>}
                        <div className="flex justify-end gap-1">
                          <button
                            type="button"
                            onClick={() => {
                              setEditingPackVideoId(null);
                              setPackError(null);
                            }}
                            className="rounded px-2 py-1 text-[11px] text-gray-400 transition-colors hover:bg-gray-800"
                          >
                            {t("common:cancel")}
                          </button>
                          <button
                            type="button"
                            onClick={voidPromise(() => saveReferencePack(video))}
                            disabled={savingReferencePackId === video.video_id}
                            className="rounded bg-indigo-500 px-2 py-1 text-[11px] font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
                          >
                            {savingReferencePackId === video.video_id
                              ? t("common:saving")
                              : t("common:save")}
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}

const QA_ISSUES = [
  { type: "face_mismatch", key: "draft_video_qa_issue_face" },
  { type: "scene_mismatch", key: "draft_video_qa_issue_scene" },
  { type: "action_mismatch", key: "draft_video_qa_issue_action" },
  { type: "camera_mismatch", key: "draft_video_qa_issue_camera" },
] as const;

function GenerationInputImageRow({
  projectName,
  label,
  path,
}: {
  projectName: string;
  label: string;
  path: string | null | undefined;
}) {
  const { t } = useTranslation(["dashboard"]);
  const imageUrl = referenceImageUrl(projectName, path);
  return (
    <div className="flex items-center gap-2 rounded bg-gray-950/50 p-1.5">
      {imageUrl ? (
        <img
          src={imageUrl}
          alt={label}
          className="h-9 w-9 shrink-0 rounded border border-gray-800 object-cover"
        />
      ) : (
        <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded border border-dashed border-gray-800 text-[9px] text-gray-600">
          ref
        </div>
      )}
      <div className="min-w-0 flex-1">
        <div className="text-[10px] font-medium text-gray-300">{label}</div>
        <div className="truncate font-mono text-[10px] text-gray-500">
          {path || t("dashboard:generation_inputs_none")}
        </div>
      </div>
    </div>
  );
}

function GenerationInputsPanel({
  projectName,
  inputs,
}: {
  projectName: string;
  inputs: VideoGenerationInputs;
}) {
  const { t } = useTranslation(["dashboard"]);
  const refs = Array.isArray(inputs.reference_images) ? inputs.reference_images : [];
  const referenceVideos = Array.isArray(inputs.reference_videos) ? inputs.reference_videos : [];
  const referenceAudios = Array.isArray(inputs.reference_audios) ? inputs.reference_audios : [];
  const displayedDuration = inputs.actual_duration_seconds ?? inputs.duration_seconds;
  const modelLabel = [inputs.provider, inputs.model].filter(Boolean).join(" / ");
  return (
    <div className="mt-2 rounded border border-sky-500/20 bg-sky-500/5 p-2">
      <div className="text-[11px] font-medium text-sky-200">{t("dashboard:generation_inputs_title")}</div>
      <div className="mt-2 grid gap-1.5">
        <GenerationInputImageRow
          projectName={projectName}
          label={t("dashboard:generation_inputs_start_image")}
          path={inputs.start_image}
        />
        {inputs.end_image && (
          <GenerationInputImageRow
            projectName={projectName}
            label={t("dashboard:generation_inputs_end_image")}
            path={inputs.end_image}
          />
        )}
        {refs.map((path, index) => (
          <GenerationInputImageRow
            key={`${path}-${index}`}
            projectName={projectName}
            label={`${t("dashboard:generation_inputs_reference_images")} ${index + 1}`}
            path={path}
          />
        ))}
      </div>
      {(referenceVideos.length > 0 || referenceAudios.length > 0) && (
        <div className="mt-2 space-y-1 font-mono text-[10px] text-gray-500">
          {referenceVideos.length > 0 && <div>reference_videos: {referenceVideos.join(", ")}</div>}
          {referenceAudios.length > 0 && <div>reference_audios: {referenceAudios.join(", ")}</div>}
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-1 text-[10px] text-gray-400">
        {displayedDuration != null && (
          <span className="rounded bg-gray-900 px-1.5 py-0.5">
            {t("dashboard:generation_inputs_duration")}: {displayedDuration}s
          </span>
        )}
        {modelLabel && (
          <span className="rounded bg-gray-900 px-1.5 py-0.5">
            {t("dashboard:generation_inputs_model")}: {modelLabel}
          </span>
        )}
      </div>
    </div>
  );
}

function DraftVideoQaPanel({
  projectName,
  plan,
  loading,
  generating,
  updatingVideoId,
  repairingVideoId,
  videoPromptsReady,
  onGenerate,
  onMark,
  onRepair,
}: {
  projectName: string;
  plan: DraftVideoQaPlan | null;
  loading: boolean;
  generating: boolean;
  updatingVideoId: string | null;
  repairingVideoId: string | null;
  videoPromptsReady: boolean;
  onGenerate: () => void;
  onMark: (videoId: string, status: string, issueType?: string | null) => void;
  onRepair: (videoId: string) => void;
}) {
  const { t } = useTranslation(["dashboard", "common"]);
  if (!videoPromptsReady) return null;
  if (loading) {
    return (
      <div className="rounded-lg border border-gray-800 bg-gray-900/40 p-3 text-xs text-gray-500">
        {t("dashboard:draft_video_qa_loading")}
      </div>
    );
  }
  if (!plan) {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed border-gray-700 bg-gray-900/35 p-3">
        <div>
          <div className="text-sm font-medium text-gray-200">{t("dashboard:draft_video_qa_empty_title")}</div>
          <div className="mt-1 text-xs text-gray-500">{t("dashboard:draft_video_qa_empty_desc")}</div>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded-md bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-400 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:draft_video_qa_generating") : t("dashboard:draft_video_qa_generate")}
        </button>
      </div>
    );
  }

  return (
    <section className="rounded-lg border border-gray-800 bg-gray-900/45 p-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold text-gray-200">{t("dashboard:draft_video_qa_title")}</div>
          <div className="mt-0.5 text-[11px] text-gray-500">
            {t("dashboard:draft_video_qa_meta", {
              approved: plan.approved_count,
              fix: plan.needs_fix_count,
              total: plan.total_count,
            })}
          </div>
        </div>
        <button
          type="button"
          onClick={onGenerate}
          disabled={generating}
          className="flex shrink-0 items-center gap-1.5 rounded px-2 py-1 text-xs text-indigo-300 transition-colors hover:bg-gray-800 disabled:cursor-not-allowed disabled:opacity-60"
        >
          <Sparkles className="h-3.5 w-3.5" />
          {generating ? t("dashboard:draft_video_qa_generating") : t("dashboard:draft_video_qa_regenerate")}
        </button>
      </div>
      <div className="space-y-2">
        {plan.items.slice(0, 6).map((item) => (
          <div key={item.video_id} className="rounded bg-gray-950/35 p-2 text-xs">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0">
                <div className="font-mono text-[10px] text-pink-300">{item.video_id}</div>
                <div className="mt-0.5 truncate font-medium text-gray-200">{item.title}</div>
              </div>
              <div className="shrink-0 rounded bg-gray-800 px-1.5 py-0.5 font-mono text-[10px] text-gray-400">
                {item.status}
              </div>
            </div>
            {item.repair_strategy?.prompt_action && (
              <div className="mt-1 rounded bg-amber-500/10 px-2 py-1 text-[11px] text-amber-200">
                {item.repair_strategy.prompt_action}
              </div>
            )}
            {item.generation_inputs && (
              <GenerationInputsPanel projectName={projectName} inputs={item.generation_inputs} />
            )}
            <div className="mt-2 flex flex-wrap gap-1">
              <button
                type="button"
                disabled={updatingVideoId === item.video_id || item.status === "waiting_generation"}
                onClick={() => onMark(item.video_id, "approved", null)}
                className="rounded bg-emerald-500/15 px-2 py-1 text-[11px] text-emerald-300 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {t("dashboard:draft_video_qa_approve")}
              </button>
              {QA_ISSUES.map((issue) => (
                <button
                  key={issue.type}
                  type="button"
                  disabled={updatingVideoId === item.video_id || item.status === "waiting_generation"}
                  onClick={() => onMark(item.video_id, "needs_fix", issue.type)}
                  className="rounded bg-gray-800 px-2 py-1 text-[11px] text-gray-300 transition-colors hover:bg-gray-700 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {t(`dashboard:${issue.key}`)}
                </button>
              ))}
              {item.status === "needs_fix" && (
                <button
                  type="button"
                  disabled={repairingVideoId === item.video_id}
                  onClick={() => onRepair(item.video_id)}
                  className="rounded bg-indigo-500/20 px-2 py-1 text-[11px] text-indigo-200 transition-colors hover:bg-indigo-500/30 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  {repairingVideoId === item.video_id
                    ? t("dashboard:draft_video_repairing")
                    : t("dashboard:draft_video_repair")}
                </button>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

interface PreprocessingViewProps {
  projectName: string;
  episode: number;
  contentMode: "narration" | "drama" | "reference_video";
  /**
   * 紧凑模式：隐藏"● {statusLabel}"辅助行（当上层已显示同等语义的 page header 时避免重复），
   * 并用更克制的 markdown typography（h1/h2 字号下调、去除 h1 下划线）。
   */
  compact?: boolean;
  /**
   * 可选 render prop：把 edit/save/cancel 控件抬到调用方（比如页面 header 右侧），
   * 组件内部就不再渲染默认 toolbar 行。narration/drama 不传走默认，行为不变。
   */
  renderToolbar?: (ctx: PreprocessingToolbarContext) => ReactNode;
}

export function PreprocessingView({
  projectName,
  episode,
  contentMode,
  compact = false,
  renderToolbar,
}: PreprocessingViewProps) {
  const { t } = useTranslation(["dashboard", "common"]);
  const pushToast = useAppStore((s) => s.pushToast);
  const sourceFilesVersion = useAppStore((s) => s.sourceFilesVersion);
  const currentProjectData = useProjectsStore((s) =>
    s.currentProjectName === projectName ? s.currentProjectData : null,
  );
  const draftRevisionKey = `draft:episode_${episode}_step1`;
  const draftRevision = useAppStore((s) => s.getEntityRevision(draftRevisionKey));
  const [content, setContent] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [editing, setEditing] = useState(false);
  const [editContent, setEditContent] = useState("");
  const [saving, setSaving] = useState(false);
  const [analysis, setAnalysis] = useState<StoryImportAnalysis | null>(null);
  const [analysisLoading, setAnalysisLoading] = useState(true);
  const [analysisGenerating, setAnalysisGenerating] = useState(false);
  const [sourceFiles, setSourceFiles] = useState<SourceFileOption[]>([]);
  const [sourceFilesLoading, setSourceFilesLoading] = useState(true);
  const [selectedSourceFilename, setSelectedSourceFilename] = useState("");
  const [choicePointSaving, setChoicePointSaving] = useState(false);
  const [storyBeatPlan, setStoryBeatPlan] = useState<StoryBeatPlan | null>(null);
  const [storyBeatLoading, setStoryBeatLoading] = useState(true);
  const [storyBeatGenerating, setStoryBeatGenerating] = useState(false);
  const [directorShotPlan, setDirectorShotPlan] = useState<DirectorShotPlan | null>(null);
  const [directorShotLoading, setDirectorShotLoading] = useState(true);
  const [directorShotGenerating, setDirectorShotGenerating] = useState(false);
  const [keyframePromptPlan, setKeyframePromptPlan] = useState<KeyframePromptPlan | null>(null);
  const [keyframePromptLoading, setKeyframePromptLoading] = useState(true);
  const [keyframePromptGenerating, setKeyframePromptGenerating] = useState(false);
  const [keyframeImageStatus, setKeyframeImageStatus] = useState<KeyframeImageStatus | null>(null);
  const [keyframeImageLoading, setKeyframeImageLoading] = useState(true);
  const [keyframeImageGenerating, setKeyframeImageGenerating] = useState(false);
  const [videoPromptPlan, setVideoPromptPlan] = useState<VideoPromptPlan | null>(null);
  const [videoPromptLoading, setVideoPromptLoading] = useState(true);
  const [videoPromptGenerating, setVideoPromptGenerating] = useState(false);
  const [referencePackSavingId, setReferencePackSavingId] = useState<string | null>(null);
  const [draftVideoStatus, setDraftVideoStatus] = useState<DraftVideoStatus | null>(null);
  const [draftVideoLoading, setDraftVideoLoading] = useState(true);
  const [draftVideoGenerating, setDraftVideoGenerating] = useState(false);
  const [draftVideoQaPlan, setDraftVideoQaPlan] = useState<DraftVideoQaPlan | null>(null);
  const [draftVideoQaLoading, setDraftVideoQaLoading] = useState(true);
  const [draftVideoQaGenerating, setDraftVideoQaGenerating] = useState(false);
  const [draftVideoQaUpdatingId, setDraftVideoQaUpdatingId] = useState<string | null>(null);
  const [draftVideoRepairingId, setDraftVideoRepairingId] = useState<string | null>(null);
  const [assetDraftCreating, setAssetDraftCreating] = useState(false);
  const [candidateDrafts, setCandidateDrafts] = useState<CandidateDraftMap>({});
  const statusLabelId = useId();
  const existingNames = existingAssetNameSets(currentProjectData);

  useEffect(() => {
    let cancelled = false;
    API.listFiles(projectName)
      .then((result) => {
        if (cancelled) return;
        const files = (result.files.source ?? []).map((file) => ({ name: file.name, size: file.size }));
        setSourceFiles(files);
        setSelectedSourceFilename((prev) => {
          if (prev && files.some((file) => file.name === prev)) return prev;
          const urlSource = typeof window !== "undefined" ? new URLSearchParams(window.location.search).get("source") : null;
          if (urlSource && files.some((file) => file.name === urlSource)) return urlSource;
          const analysisSource = analysis?.source_filename;
          if (analysisSource && files.some((file) => file.name === analysisSource)) return analysisSource;
          return files[0]?.name ?? "";
        });
      })
      .catch(() => {
        if (!cancelled) setSourceFiles([]);
      })
      .finally(() => {
        if (!cancelled) setSourceFilesLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [analysis?.source_filename, projectName, sourceFilesVersion]);

  useEffect(() => {
    let cancelled = false;
    // 首次加载或切换草稿时展示加载状态并重置编辑态，再触发异步 fetch
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (!content) setLoading(true);
    setEditing(false);

    API.getDraftContent(projectName, episode, 1)
      .then((text) => {
        if (!cancelled) {
          setContent(text);
          setEditContent(text);
        }
      })
      .catch(() => {
        if (!cancelled) setContent(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    setAnalysisLoading(true);
    API.getStoryAnalysis(projectName, episode)
      .then((result) => {
        if (!cancelled) setAnalysis(result);
      })
      .catch(() => {
        if (!cancelled) setAnalysis(null);
      })
      .finally(() => {
        if (!cancelled) setAnalysisLoading(false);
      });

    setStoryBeatLoading(true);
    API.getStoryBeats(projectName, episode)
      .then((result) => {
        if (!cancelled) setStoryBeatPlan(result);
      })
      .catch(() => {
        if (!cancelled) setStoryBeatPlan(null);
      })
      .finally(() => {
        if (!cancelled) setStoryBeatLoading(false);
      });

    setDirectorShotLoading(true);
    API.getDirectorShots(projectName, episode)
      .then((result) => {
        if (!cancelled) setDirectorShotPlan(result);
      })
      .catch(() => {
        if (!cancelled) setDirectorShotPlan(null);
      })
      .finally(() => {
        if (!cancelled) setDirectorShotLoading(false);
      });

    setKeyframePromptLoading(true);
    API.getKeyframePrompts(projectName, episode)
      .then((result) => {
        if (!cancelled) setKeyframePromptPlan(result);
      })
      .catch(() => {
        if (!cancelled) setKeyframePromptPlan(null);
      })
      .finally(() => {
        if (!cancelled) setKeyframePromptLoading(false);
      });

    setKeyframeImageLoading(true);
    API.getKeyframes(projectName, episode)
      .then((result) => {
        if (!cancelled) setKeyframeImageStatus(result);
      })
      .catch(() => {
        if (!cancelled) setKeyframeImageStatus(null);
      })
      .finally(() => {
        if (!cancelled) setKeyframeImageLoading(false);
      });

    setVideoPromptLoading(true);
    API.getVideoPrompts(projectName, episode)
      .then((result) => {
        if (!cancelled) setVideoPromptPlan(result);
      })
      .catch(() => {
        if (!cancelled) setVideoPromptPlan(null);
      })
      .finally(() => {
        if (!cancelled) setVideoPromptLoading(false);
      });

    setDraftVideoLoading(true);
    API.getDraftVideos(projectName, episode)
      .then((result) => {
        if (!cancelled) setDraftVideoStatus(result);
      })
      .catch(() => {
        if (!cancelled) setDraftVideoStatus(null);
      })
      .finally(() => {
        if (!cancelled) setDraftVideoLoading(false);
      });

    setDraftVideoQaLoading(true);
    API.getDraftVideoQa(projectName, episode)
      .then((result) => {
        if (!cancelled) setDraftVideoQaPlan(result);
      })
      .catch(() => {
        if (!cancelled) setDraftVideoQaPlan(null);
      })
      .finally(() => {
        if (!cancelled) setDraftVideoQaLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps -- content 仅用于决定是否显示加载态，加入 deps 会在内容更新后触发重新拉取，导致循环
  }, [projectName, episode, draftRevision]);

  useEffect(() => {
    if (!(draftVideoStatus?.videos ?? []).some(isDraftVideoTaskActive)) return;
    let cancelled = false;
    const refresh = async () => {
      const status = await API.getDraftVideos(projectName, episode).catch(() => null);
      if (!cancelled && status) setDraftVideoStatus(status);
    };
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [draftVideoStatus, episode, projectName]);

  useEffect(() => {
    if (!(keyframeImageStatus?.frames ?? []).some(isKeyframeTaskActive)) return;
    let cancelled = false;
    const refresh = async () => {
      const status = await API.getKeyframes(projectName, episode).catch(() => null);
      if (!cancelled && status) setKeyframeImageStatus(status);
    };
    const timer = window.setInterval(() => {
      void refresh();
    }, 5000);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [episode, keyframeImageStatus, projectName]);

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      await API.saveDraft(projectName, episode, 1, editContent);
      setContent(editContent);
      setEditing(false);
      pushToast(t("dashboard:preprocessing_saved"), "success");
    } catch {
      pushToast(t("dashboard:save_failed"), "error");
    } finally {
      setSaving(false);
    }
  }, [projectName, episode, editContent, pushToast, t]);

  const cancelEdit = useCallback(() => {
    setEditing(false);
    setEditContent(content ?? "");
  }, [content]);

  const handleGenerateAnalysis = useCallback(async () => {
    setAnalysisGenerating(true);
    try {
      const result = await API.generateStoryAnalysis(projectName, episode, {
        sourceFilename: selectedSourceFilename || undefined,
      });
      setAnalysis(result);
      if (result.source_filename) setSelectedSourceFilename(result.source_filename);
      setStoryBeatPlan(null);
      setDirectorShotPlan(null);
      setKeyframePromptPlan(null);
      setKeyframeImageStatus(null);
      setVideoPromptPlan(null);
      setDraftVideoStatus(null);
      setDraftVideoQaPlan(null);
      pushToast(t("dashboard:story_analysis_generated"), "success");
    } catch {
      pushToast(t("dashboard:story_analysis_generate_failed"), "error");
    } finally {
      setAnalysisGenerating(false);
    }
  }, [episode, projectName, pushToast, selectedSourceFilename, t]);

  const handleGenerateStoryBeats = useCallback(async () => {
    setStoryBeatGenerating(true);
    try {
      const result = await API.generateStoryBeats(projectName, episode);
      setStoryBeatPlan(result);
      setDirectorShotPlan(null);
      setKeyframePromptPlan(null);
      setKeyframeImageStatus(null);
      setVideoPromptPlan(null);
      setDraftVideoStatus(null);
      setDraftVideoQaPlan(null);
      pushToast(t("dashboard:story_beats_generated"), "success");
    } catch {
      pushToast(t("dashboard:story_beats_generate_failed"), "error");
    } finally {
      setStoryBeatGenerating(false);
    }
  }, [episode, projectName, pushToast, t]);

  const handleSaveChoicePoints = useCallback(
    async (choicePoints: ChoicePointDraft[]) => {
      if (!analysis || choicePointSaving) return;
      setChoicePointSaving(true);
      try {
        const updated = await API.updateStoryAnalysis(projectName, episode, {
          ...analysis,
          choice_points: choicePoints,
        });
        setAnalysis(updated);
        setStoryBeatPlan(null);
        setDirectorShotPlan(null);
        setKeyframePromptPlan(null);
        setKeyframeImageStatus(null);
        setVideoPromptPlan(null);
        setDraftVideoStatus(null);
        setDraftVideoQaPlan(null);
        pushToast("分支结构已保存，后续步骤需要重新生成。", "success");
      } catch {
        pushToast("分支结构保存失败", "error");
      } finally {
        setChoicePointSaving(false);
      }
    },
    [analysis, choicePointSaving, episode, projectName, pushToast],
  );

  const handleGenerateDirectorShots = useCallback(async () => {
    setDirectorShotGenerating(true);
    try {
      const result = await API.generateDirectorShots(projectName, episode);
      setDirectorShotPlan(result);
      setKeyframePromptPlan(null);
      setKeyframeImageStatus(null);
      setVideoPromptPlan(null);
      setDraftVideoStatus(null);
      setDraftVideoQaPlan(null);
      pushToast(t("dashboard:director_shots_generated"), "success");
    } catch {
      pushToast(t("dashboard:director_shots_generate_failed"), "error");
    } finally {
      setDirectorShotGenerating(false);
    }
  }, [episode, projectName, pushToast, t]);

  const handleGenerateKeyframePrompts = useCallback(async () => {
    setKeyframePromptGenerating(true);
    try {
      const result = await API.generateKeyframePrompts(projectName, episode);
      setKeyframePromptPlan(result);
      const images = await API.getKeyframes(projectName, episode);
      setKeyframeImageStatus(images);
      setVideoPromptPlan(null);
      setDraftVideoStatus(null);
      setDraftVideoQaPlan(null);
      pushToast(t("dashboard:keyframe_prompts_generated"), "success");
    } catch {
      pushToast(t("dashboard:keyframe_prompts_generate_failed"), "error");
    } finally {
      setKeyframePromptGenerating(false);
    }
  }, [episode, projectName, pushToast, t]);

  const handleGenerateKeyframeImages = useCallback(async () => {
    if (!keyframePromptPlan || keyframeImageGenerating) return;
    const prompts = keyframePromptPlan.prompts.filter((prompt) => prompt.role !== "review_frame");
    if (!prompts.length) return;
    setKeyframeImageGenerating(true);
    let submitted = 0;
    let failed = 0;
    try {
      for (const prompt of prompts) {
        try {
          const result = await API.generateKeyframe(projectName, prompt.keyframe_id, {
            prompt: prompt.prompt,
            negative_prompt: prompt.negative_prompt ?? "",
            episode,
            shot_id: prompt.shot_id,
            role: prompt.role,
            reference_images:
              prompt.role === "guide_reference"
                ? []
                : buildKeyframeReferenceImages(
                    currentProjectData,
                    `${prompt.title}\n${prompt.prompt}`,
                  ),
          });
          setKeyframeImageStatus((prev) => {
            const nextFrame: KeyframeImageFrame = {
              keyframe_id: prompt.keyframe_id,
              shot_id: prompt.shot_id,
              role: prompt.role,
              file_path: `keyframes/${prompt.keyframe_id}.png`,
              exists: false,
              fingerprint: null,
              task_id: result.task_id,
              task_status: "queued",
              task_error_message: null,
            };
            if (!prev) return { schema_version: 1, episode, frames: [nextFrame] };
            const found = prev.frames.some((frame) => frame.keyframe_id === prompt.keyframe_id);
            return {
              ...prev,
              frames: found
                ? prev.frames.map((frame) =>
                    frame.keyframe_id === prompt.keyframe_id
                      ? { ...frame, ...nextFrame, exists: frame.exists, fingerprint: frame.fingerprint }
                      : frame,
                  )
                : [...prev.frames, nextFrame],
            };
          });
          submitted += 1;
        } catch {
          failed += 1;
        }
      }
      if (submitted > 0) {
        pushToast(t("dashboard:keyframe_images_submitted", { count: submitted }), "success");
      }
      if (failed > 0) {
        pushToast(t("dashboard:keyframe_images_submit_failed", { count: failed }), "error");
      }
      const images = await API.getKeyframes(projectName, episode);
      setKeyframeImageStatus(images);
      setVideoPromptPlan(null);
      setDraftVideoStatus(null);
      setDraftVideoQaPlan(null);
    } finally {
      setKeyframeImageGenerating(false);
    }
  }, [currentProjectData, episode, keyframeImageGenerating, keyframePromptPlan, projectName, pushToast, t]);

  const handleGenerateVideoPrompts = useCallback(async () => {
    setVideoPromptGenerating(true);
    try {
      const result = await API.generateVideoPrompts(projectName, episode);
      setVideoPromptPlan(result);
      const videos = await API.getDraftVideos(projectName, episode);
      setDraftVideoStatus(videos);
      setDraftVideoQaPlan(null);
      pushToast(t("dashboard:video_prompts_generated"), "success");
    } catch {
      pushToast(t("dashboard:video_prompts_generate_failed"), "error");
    } finally {
      setVideoPromptGenerating(false);
    }
  }, [episode, projectName, pushToast, t]);

  const handleSaveReferencePack = useCallback(
    async (videoId: string, selectedImages: VideoReferenceEntry[]) => {
      if (!videoPromptPlan) return;
      setReferencePackSavingId(videoId);
      const previousPlan = videoPromptPlan;
      const nextPlan: VideoPromptPlan = {
        ...videoPromptPlan,
        videos: videoPromptPlan.videos.map((video) =>
          video.video_id === videoId
            ? {
                ...video,
                reference_pack: {
                  ...(video.reference_pack ?? {}),
                  selected_images: selectedImages,
                },
              }
            : video,
        ),
      };
      setVideoPromptPlan(nextPlan);
      try {
        const saved = await API.updateVideoPrompts(projectName, episode, nextPlan);
        setVideoPromptPlan(saved);
        setDraftVideoQaPlan(null);
        pushToast(t("dashboard:reference_pack_saved"), "success");
      } catch (error) {
        setVideoPromptPlan(previousPlan);
        pushToast(t("dashboard:reference_pack_save_failed"), "error");
        throw error;
      } finally {
        setReferencePackSavingId(null);
      }
    },
    [episode, projectName, pushToast, t, videoPromptPlan],
  );

  const handleGenerateDraftVideos = useCallback(async () => {
    if (!videoPromptPlan || draftVideoGenerating) return;
    const videos = videoPromptPlan.videos.filter((video) => video.submit_blockers.length === 0);
    if (!videos.length) return;
    setDraftVideoGenerating(true);
    let submitted = 0;
    let failed = 0;
    try {
      for (const video of videos) {
        try {
          const result = await API.generateDraftVideo(projectName, video.video_id, {
            prompt: video.prompt,
            episode,
            duration_seconds: video.duration_seconds,
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
          submitted += 1;
        } catch {
          failed += 1;
        }
      }
      if (submitted > 0) {
        pushToast(t("dashboard:draft_videos_submitted", { count: submitted }), "success");
      }
      if (failed > 0) {
        pushToast(t("dashboard:draft_videos_submit_failed", { count: failed }), "error");
      }
      const status = await API.getDraftVideos(projectName, episode);
      setDraftVideoStatus(status);
      setDraftVideoQaPlan(null);
    } finally {
      setDraftVideoGenerating(false);
    }
  }, [draftVideoGenerating, episode, projectName, pushToast, t, videoPromptPlan]);

  const handleGenerateDraftVideoQa = useCallback(async () => {
    setDraftVideoQaGenerating(true);
    try {
      const result = await API.generateDraftVideoQa(projectName, episode);
      setDraftVideoQaPlan(result);
      pushToast(t("dashboard:draft_video_qa_generated"), "success");
    } catch {
      pushToast(t("dashboard:draft_video_qa_generate_failed"), "error");
    } finally {
      setDraftVideoQaGenerating(false);
    }
  }, [episode, projectName, pushToast, t]);

  const handleMarkDraftVideoQa = useCallback(
    async (videoId: string, status: string, issueType?: string | null) => {
      setDraftVideoQaUpdatingId(videoId);
      try {
        const result = await API.updateDraftVideoQa(projectName, episode, videoId, {
          status,
          issue_type: issueType ?? null,
        });
        setDraftVideoQaPlan(result);
        pushToast(t("dashboard:draft_video_qa_updated"), "success");
      } catch {
        pushToast(t("dashboard:draft_video_qa_update_failed"), "error");
      } finally {
        setDraftVideoQaUpdatingId(null);
      }
    },
    [episode, projectName, pushToast, t],
  );

  const handleRepairDraftVideo = useCallback(
    async (videoId: string) => {
      setDraftVideoRepairingId(videoId);
      try {
        await API.repairDraftVideo(projectName, videoId, { episode, seed: null });
        pushToast(t("dashboard:draft_video_repair_submitted"), "success");
        const status = await API.getDraftVideos(projectName, episode);
        setDraftVideoStatus(status);
      } catch {
        pushToast(t("dashboard:draft_video_repair_failed"), "error");
      } finally {
        setDraftVideoRepairingId(null);
      }
    },
    [episode, projectName, pushToast, t],
  );

  const draftDescription = useCallback(
    (item: StoryAnalysisNamedItem) => {
      const description = item.description?.trim();
      if (description) return description;
      return t("dashboard:story_analysis_asset_draft_description", {
        count: item.evidence_count ?? 0,
      });
    },
    [t],
  );

  useEffect(() => {
    if (!analysis) {
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setCandidateDrafts({});
      return;
    }
    const existing = existingAssetNameSets(currentProjectData);
            setCandidateDrafts((prev) => {
      const next: CandidateDraftMap = {};
      for (const candidate of collectAssetCandidates(analysis)) {
        if (isExistingCandidate(existing, candidate)) continue;
        const key = candidateKey(candidate.kind, candidate.item.name);
        next[key] = prev[key] ?? {
          selected: true,
          name: candidate.item.name,
          description: draftDescription(candidate.item),
        };
      }
      return next;
    });
  }, [analysis, currentProjectData, draftDescription]);

  const handleToggleCandidate = useCallback((key: string, checked: boolean) => {
    setCandidateDrafts((prev) => ({
      ...prev,
      [key]: { ...prev[key], selected: checked },
    }));
  }, []);

  const handleChangeCandidateDraft = useCallback(
    (key: string, patch: Partial<Pick<CandidateDraft, "name" | "description">>) => {
      setCandidateDrafts((prev) => ({
        ...prev,
        [key]: { ...prev[key], ...patch },
      }));
    },
    [],
  );

  const handleCreateSelectedAssets = useCallback(async () => {
    if (!analysis || assetDraftCreating) return;
    const candidates = collectAssetCandidates(analysis).filter((candidate) => {
      const draft = candidateDrafts[candidateKey(candidate.kind, candidate.item.name)];
      return !isExistingCandidate(existingNames, candidate) && !!draft?.selected && !!draft.name.trim();
    });
    if (!candidates.length) return;
    setAssetDraftCreating(true);
    let created = 0;
    const failed: Array<{ name: string; message: string }> = [];
    for (const candidate of candidates) {
      const key = candidateKey(candidate.kind, candidate.item.name);
      const draft = candidateDrafts[key];
      const targetName = draft?.name.trim() || candidate.item.name;
      const description = draft?.description.trim() || draftDescription(candidate.item);
      try {
        if (candidate.kind === "character") {
          await API.addCharacter(projectName, targetName, description, "");
        } else if (candidate.kind === "scene") {
          await API.addProjectScene(projectName, targetName, description);
        } else {
          await API.addProjectProp(projectName, targetName, description);
        }
        created += 1;
      } catch (err) {
        failed.push({ name: targetName, message: errMsg(err) });
      }
    }
    try {
      if (created > 0) {
        const refreshed = await API.getProject(projectName);
        useProjectsStore.getState().setCurrentProject(
          projectName,
          refreshed.project,
          refreshed.scripts ?? {},
          refreshed.asset_fingerprints,
        );
        pushToast(t("dashboard:story_analysis_asset_created", { count: created }), "success");
      }
      if (failed.length > 0) {
        pushToast(
          t("dashboard:story_analysis_asset_create_failed", {
            name: failed[0].name,
            message: failed[0].message,
          }),
          "error",
        );
      }
    } finally {
      setAssetDraftCreating(false);
    }
  }, [
    analysis,
    assetDraftCreating,
    candidateDrafts,
    draftDescription,
    existingNames,
    projectName,
    pushToast,
    t,
  ]);

  const statusLabel =
    contentMode === "narration"
      ? t("dashboard:segment_split_complete")
      : contentMode === "drama"
        ? t("dashboard:script_normalized_complete")
        : t("dashboard:reference_units_split_complete_label");

  if (loading) {
    return (
      <div className="flex h-64 items-center justify-center text-gray-500">
        {t("dashboard:loading_preprocessing")}
      </div>
    );
  }

  const hasPreprocessingContent = content !== null;

  // 当调用方接管 toolbar 时，仍把 statusLabel 以 sr-only 形式保留，供 textarea 的 aria-labelledby 引用
  // （保持 a11y 结构稳定）。内置 toolbar 仅在没有 renderToolbar 时渲染。
  const defaultToolbar = (
    <div className="flex items-center justify-between">
      {compact ? (
        <span id={statusLabelId} className="sr-only">{statusLabel}</span>
      ) : (
        <div className="flex items-center gap-2">
          <div className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
          <span id={statusLabelId} className="text-xs text-gray-500">{statusLabel}</span>
        </div>
      )}
      <div className="flex items-center gap-1">
        {editing ? (
          <>
            <button
              type="button"
              onClick={voidPromise(handleSave)}
              disabled={saving}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs text-green-400 transition-colors hover:bg-gray-800 disabled:opacity-50"
            >
              <Save className="h-3.5 w-3.5" />
              {saving ? t("common:saving") : t("common:save")}
            </button>
            <button
              type="button"
              onClick={cancelEdit}
              className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-800"
            >
              <X className="h-3.5 w-3.5" />
              {t("common:cancel")}
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => setEditing(true)}
            className="flex items-center gap-1 rounded px-2 py-1 text-xs text-gray-400 transition-colors hover:bg-gray-800 hover:text-gray-200"
          >
            <Edit3 className="h-3.5 w-3.5" />
            {t("common:edit")}
          </button>
        )}
      </div>
    </div>
  );

  return (
    <div className="flex flex-col gap-3">
      {hasPreprocessingContent ? (
        renderToolbar ? (
          <>
            <span id={statusLabelId} className="sr-only">{statusLabel}</span>
            {renderToolbar({
              editing,
              saving,
              startEdit: () => setEditing(true),
              save: voidPromise(handleSave),
              cancel: cancelEdit,
            })}
          </>
        ) : (
          defaultToolbar
        )
      ) : (
        <div className="rounded-lg border border-gray-800 bg-gray-950/40 px-3 py-2 text-xs text-gray-500">
          {t("dashboard:no_preprocessing_content")}
        </div>
      )}

      <StoryAnalysisPanel
        analysis={analysis}
        loading={analysisLoading}
        generating={analysisGenerating}
        sourceFiles={sourceFiles}
        sourceFilesLoading={sourceFilesLoading}
        selectedSourceFilename={selectedSourceFilename}
        onSelectSourceFilename={setSelectedSourceFilename}
        creatingAssets={assetDraftCreating}
        candidateDrafts={candidateDrafts}
        existingNames={existingNames}
        onGenerate={voidPromise(handleGenerateAnalysis)}
        onToggleCandidate={handleToggleCandidate}
        onChangeCandidateDraft={handleChangeCandidateDraft}
        onCreateSelectedAssets={voidPromise(handleCreateSelectedAssets)}
        savingChoicePoints={choicePointSaving}
        onSaveChoicePoints={handleSaveChoicePoints}
      />
      <StoryBeatPanel
        plan={storyBeatPlan}
        loading={storyBeatLoading}
        generating={storyBeatGenerating}
        analysisReady={!!analysis}
        onGenerate={voidPromise(handleGenerateStoryBeats)}
      />
      <DirectorShotPanel
        plan={directorShotPlan}
        loading={directorShotLoading}
        generating={directorShotGenerating}
        storyBeatsReady={!!storyBeatPlan}
        onGenerate={voidPromise(handleGenerateDirectorShots)}
      />
      <KeyframePromptPanel
        projectName={projectName}
        plan={keyframePromptPlan}
        loading={keyframePromptLoading}
        generating={keyframePromptGenerating}
        imageStatus={keyframeImageStatus}
        imageStatusLoading={keyframeImageLoading}
        imageGenerating={keyframeImageGenerating}
        directorShotsReady={!!directorShotPlan}
        onGenerate={voidPromise(handleGenerateKeyframePrompts)}
        onGenerateImages={voidPromise(handleGenerateKeyframeImages)}
      />
      <VideoPromptPanel
        projectName={projectName}
        projectData={currentProjectData}
        plan={videoPromptPlan}
        loading={videoPromptLoading}
        generating={videoPromptGenerating}
        videoStatus={draftVideoStatus}
        videoStatusLoading={draftVideoLoading}
        videoGenerating={draftVideoGenerating}
        keyframesReady={!!keyframePromptPlan}
        onGenerate={voidPromise(handleGenerateVideoPrompts)}
        onGenerateVideos={voidPromise(handleGenerateDraftVideos)}
        savingReferencePackId={referencePackSavingId}
        onSaveReferencePack={handleSaveReferencePack}
      />
      <DraftVideoQaPanel
        projectName={projectName}
        plan={draftVideoQaPlan}
        loading={draftVideoQaLoading}
        generating={draftVideoQaGenerating}
        updatingVideoId={draftVideoQaUpdatingId}
        repairingVideoId={draftVideoRepairingId}
        videoPromptsReady={!!videoPromptPlan}
        onGenerate={voidPromise(handleGenerateDraftVideoQa)}
        onMark={(videoId, status, issueType) => {
          void handleMarkDraftVideoQa(videoId, status, issueType);
        }}
        onRepair={voidPromise(handleRepairDraftVideo)}
      />

      {hasPreprocessingContent && (
        editing ? (
          <textarea
            aria-labelledby={statusLabelId}
            value={editContent}
            onChange={(e) => setEditContent(e.target.value)}
            className="min-h-[400px] w-full resize-y rounded-lg border border-gray-700 bg-gray-800 p-4 font-mono text-sm leading-relaxed text-gray-200 outline-none focus-ring focus-visible:border-indigo-500"
          />
        ) : (
          <div
            className={`prose-invert max-w-none overflow-x-auto rounded-lg border border-gray-800 bg-gray-900/50 p-4 text-sm ${compact ? "markdown-compact" : ""}`}
          >
            <StreamMarkdown content={content} />
          </div>
        )
      )}
    </div>
  );
}
