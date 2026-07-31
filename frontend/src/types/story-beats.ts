export interface StoryMicroBeat {
  micro_id: string;
  title: string;
  dramatic_value?: string;
  source_excerpt?: string;
  estimated_seconds: number;
  interaction_role?: string;
  choice_point_id?: string;
  choice_options?: string[];
  handoff?: string;
}

export interface StoryBeat {
  beat_id: string;
  title: string;
  story_function?: string;
  summary?: string;
  source_excerpt?: string;
  estimated_seconds: number;
  interaction_role?: string;
  choice_point_id?: string;
  choice_options?: string[];
  handoff?: string;
  micro_beats: StoryMicroBeat[];
}

export interface StoryBeatChoiceOption {
  option_id: string;
  label: string;
  branch_key: string;
  next_hint?: string;
}

export interface StoryBeatChoicePoint {
  choice_id: string;
  source_node_id?: string;
  line?: number;
  prompt: string;
  options: StoryBeatChoiceOption[];
  handoff?: string;
}

export interface StoryBeatPlan {
  schema_version: number;
  episode: number;
  content_format?: string;
  template_name?: string;
  template_focus?: string;
  format_profile?: Record<string, unknown>;
  source_filename?: string | null;
  source_summary?: string;
  total_estimated_seconds: number;
  choice_points?: StoryBeatChoicePoint[];
  beats: StoryBeat[];
}
