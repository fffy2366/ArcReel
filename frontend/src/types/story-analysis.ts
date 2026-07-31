export interface StoryAnalysisNamedItem {
  name: string;
  evidence_count?: number;
  source?: "project" | "text" | string;
  description?: string;
}

export interface StoryAnalysisBeat {
  beat_id: string;
  title: string;
  story_function?: string;
  source_excerpt?: string;
}

export interface StoryAnalysisHardPoint {
  type: string;
  label: string;
  reason?: string;
}

export interface StoryAnalysisGameplayMarker {
  line: number;
  kind: "gameplay_entry" | "return_to_story" | string;
  text: string;
}

export interface StoryAnalysisInteractiveNode {
  node_id: string;
  line?: number;
  kind: "gameplay_entry" | "return_to_story" | "choice_point" | "hook" | string;
  text: string;
  options?: string[];
  handoff?: string;
}

export interface StoryAnalysisChoiceOption {
  option_id: string;
  label: string;
  branch_key: string;
  next_hint?: string;
}

export interface StoryAnalysisChoicePoint {
  choice_id: string;
  source_node_id?: string;
  line?: number;
  prompt: string;
  options: StoryAnalysisChoiceOption[];
  handoff?: string;
}

export interface StoryImportAnalysis {
  schema_version: number;
  episode: number;
  source_filename?: string | null;
  content_format?: string;
  template_name?: string;
  template_focus?: string;
  format_profile?: Record<string, unknown>;
  summary?: string;
  story_beats: StoryAnalysisBeat[];
  characters: StoryAnalysisNamedItem[];
  scenes: StoryAnalysisNamedItem[];
  props: StoryAnalysisNamedItem[];
  hard_points: StoryAnalysisHardPoint[];
  gameplay_markers: StoryAnalysisGameplayMarker[];
  interactive_nodes?: StoryAnalysisInteractiveNode[];
  choice_points?: StoryAnalysisChoicePoint[];
}
