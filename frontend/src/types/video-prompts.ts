import type { VideoGenerationInputs } from "./script";

export interface VideoReferenceEntry {
  role: string;
  path?: string | null;
  url?: string | null;
  submit_as: string;
  required: boolean;
  status: string;
  asset_type?: "character" | "scene" | "prop" | string;
  asset_name?: string;
  source?: string;
}

export interface VideoPromptPack {
  policy?: string;
  selected_images: VideoReferenceEntry[];
  selected_videos?: VideoReferenceEntry[];
  selected_audios?: VideoReferenceEntry[];
}

export interface VideoPromptPackItem {
  video_id: string;
  shot_id: string;
  keyframe_id: string;
  title: string;
  duration_seconds: number;
  prompt: string;
  start_image: string;
  start_image_status: "ready" | "missing" | string;
  reference_pack: VideoPromptPack;
  optional_reference_roles: string[];
  submit_blockers: string[];
  review_checkpoints: string[];
}

export interface VideoPromptPlan {
  schema_version: number;
  episode: number;
  source_keyframe_count: number;
  ready_video_count: number;
  total_duration_seconds: number;
  videos: VideoPromptPackItem[];
}

export interface DraftVideoFrame {
  video_id: string;
  shot_id?: string | null;
  keyframe_id?: string | null;
  file_path: string;
  exists: boolean;
  fingerprint?: number | null;
  generation_inputs?: VideoGenerationInputs | null;
  task_id?: string | null;
  task_status?: "queued" | "running" | "cancelling" | "succeeded" | "failed" | "cancelled" | string | null;
  task_provider_id?: string | null;
  task_provider_job_id?: string | null;
  task_error_message?: string | null;
  task_queued_at?: string | null;
  task_started_at?: string | null;
  task_finished_at?: string | null;
  task_updated_at?: string | null;
}

export interface DraftVideoStatus {
  schema_version: number;
  episode: number;
  videos: DraftVideoFrame[];
}
