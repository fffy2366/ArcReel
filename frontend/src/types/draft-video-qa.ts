import type { VideoGenerationInputs } from "./script";

export type DraftVideoQaStatus = "waiting_generation" | "needs_review" | "approved" | "needs_fix" | string;

export interface DraftVideoRepairStrategy {
  label?: string;
  add_reference_roles?: string[];
  prompt_action?: string;
}

export interface DraftVideoQaItem {
  video_id: string;
  shot_id?: string | null;
  keyframe_id?: string | null;
  title: string;
  status: DraftVideoQaStatus;
  issue_type?: string | null;
  note: string;
  repair_strategy: DraftVideoRepairStrategy;
  generation_inputs?: VideoGenerationInputs | null;
}

export interface DraftVideoQaPlan {
  schema_version: number;
  episode: number;
  total_count: number;
  approved_count: number;
  needs_fix_count: number;
  items: DraftVideoQaItem[];
}
