export interface DirectorShot {
  shot_id: string;
  source_micro_id: string;
  title: string;
  duration_seconds: number;
  shot_size: string;
  camera_angle: string;
  camera_movement: string;
  screen_subject: string;
  action: string;
  performance: string;
  lighting: string;
  edit_note: string;
  image_roles: string[];
  reference_strategy?: string;
  interaction_role?: string;
  choice_point_id?: string;
  choice_options?: string[];
  is_generation_boundary?: boolean;
}

export interface DirectorChoiceOption {
  option_id: string;
  label: string;
  branch_key: string;
  next_hint?: string;
}

export interface DirectorChoicePoint {
  choice_id: string;
  source_node_id?: string;
  line?: number;
  prompt: string;
  options: DirectorChoiceOption[];
  handoff?: string;
}

export interface DirectorShotGroup {
  group_id: string;
  source_beat_id: string;
  title: string;
  purpose?: string;
  duration_seconds: number;
  shots: DirectorShot[];
}

export interface DirectorShotPlan {
  schema_version: number;
  episode: number;
  content_format?: string;
  template_name?: string;
  template_focus?: string;
  format_profile?: Record<string, unknown>;
  source_story_beat_count: number;
  total_duration_seconds: number;
  choice_points?: DirectorChoicePoint[];
  shot_groups: DirectorShotGroup[];
}
