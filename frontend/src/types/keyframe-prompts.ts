export interface KeyframeGridCell {
  cell: number;
  phase?: string;
  visual?: string;
  acting?: string;
  body?: string;
  camera?: string;
  purpose?: string;
}

export interface KeyframePrompt {
  keyframe_id: string;
  shot_id: string;
  role: "start_image" | "review_frame" | string;
  title: string;
  image_role_explanation: string;
  prompt: string;
  negative_prompt?: string;
  style_policy?: string;
  reference_policy?: string;
  grid_cells?: KeyframeGridCell[];
  optional_reference_roles: string[];
  review_checkpoints: string[];
}

export interface KeyframePromptPlan {
  schema_version: number;
  episode: number;
  source_shot_count: number;
  total_duration_seconds: number;
  prompts: KeyframePrompt[];
}

export interface KeyframeImageFrame {
  keyframe_id: string;
  shot_id?: string | null;
  role: string;
  file_path?: string | null;
  exists: boolean;
  fingerprint?: number | null;
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

export interface KeyframeImageStatus {
  schema_version: number;
  episode: number;
  frames: KeyframeImageFrame[];
}
