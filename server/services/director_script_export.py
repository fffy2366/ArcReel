"""Export director-storyboard drafts into the canonical episode script.

The director-storyboard pipeline stores its intermediate products under
``drafts/episode_N``.  The legacy timeline UI, however, only unlocks when the
episode points to a real ``scripts/episode_N.json`` file.  This module is the
bridge between those two worlds.
"""

from __future__ import annotations

import re
from typing import Any

from lib.script_models import NarrationEpisodeScript
from lib.video_duration import coerce_video_duration


def _compact(text: Any, limit: int = 500) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if limit <= 0 or len(value) <= limit:
        return value
    return value[: limit - 1] + "…"


def _shot_map(director_shots: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for group in (director_shots or {}).get("shot_groups") or []:
        if not isinstance(group, dict):
            continue
        for shot in group.get("shots") or []:
            if not isinstance(shot, dict):
                continue
            shot_id = str(shot.get("shot_id") or "").strip()
            if shot_id:
                result[shot_id] = shot
    return result


def _keyframe_prompt_map(keyframe_prompts: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in (keyframe_prompts or {}).get("prompts") or []:
        if not isinstance(item, dict):
            continue
        shot_id = str(item.get("shot_id") or "").strip()
        if not shot_id:
            continue
        # Prefer the editable guide prompt.  If it does not exist, keep the
        # first prompt for that shot as a reasonable visual description.
        if str(item.get("role") or "") == "guide_reference" or shot_id not in result:
            result[shot_id] = item
    return result


def _as_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item or "").strip()]


def _camera_motion(raw: Any) -> str:
    text = str(raw or "").lower()
    if any(token in text for token in ("track", "跟", "随", "横移", "推进", "推近", "dolly")):
        return "Tracking Shot"
    if any(token in text for token in ("zoom in", "推", "拉近", "变焦", "放大")):
        return "Zoom In"
    if any(token in text for token in ("zoom out", "拉远", "后退")):
        return "Zoom Out"
    if any(token in text for token in ("tilt up", "上摇", "仰")):
        return "Tilt Up"
    if any(token in text for token in ("tilt down", "下摇", "俯")):
        return "Tilt Down"
    if any(token in text for token in ("pan left", "左摇")):
        return "Pan Left"
    if any(token in text for token in ("pan right", "右摇")):
        return "Pan Right"
    return "Static"


def _shot_type(raw: Any) -> str:
    text = str(raw or "").lower()
    if any(token in text for token in ("极特写", "extreme close")):
        return "Extreme Close-up"
    if any(token in text for token in ("特写", "close")):
        return "Close-up"
    if any(token in text for token in ("近景", "medium close")):
        return "Medium Close-up"
    if any(token in text for token in ("中近",)):
        return "Medium Close-up"
    if any(token in text for token in ("中景", "medium")):
        return "Medium Shot"
    if any(token in text for token in ("全景", "远景", "long")):
        return "Long Shot"
    return "Medium Shot"


def _episode_title(project: dict[str, Any] | None, episode: int) -> str:
    for item in (project or {}).get("episodes") or []:
        if isinstance(item, dict) and item.get("episode") == episode:
            title = str(item.get("title") or "").strip()
            if title:
                return title
    return f"第 {episode} 集"


def _source_filename(story_analysis: dict[str, Any] | None, story_beats: dict[str, Any] | None) -> str:
    return str((story_analysis or {}).get("source_filename") or (story_beats or {}).get("source_filename") or "")


def build_director_storyboard_episode_script(
    *,
    project: dict[str, Any] | None,
    episode: int,
    video_prompts: dict[str, Any],
    director_shots: dict[str, Any] | None = None,
    keyframe_prompts: dict[str, Any] | None = None,
    story_analysis: dict[str, Any] | None = None,
    story_beats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build a canonical narration episode script from director draft files."""

    shots_by_id = _shot_map(director_shots)
    keyframes_by_shot = _keyframe_prompt_map(keyframe_prompts)
    videos = [item for item in video_prompts.get("videos") or [] if isinstance(item, dict)]

    segments: list[dict[str, Any]] = []
    for index, video in enumerate(videos, start=1):
        shot_id = str(video.get("shot_id") or "").strip() or f"E{episode}S{index:02d}"
        shot = shots_by_id.get(shot_id, {})
        keyframe = keyframes_by_shot.get(shot_id, {})
        duration = int(video.get("duration_seconds") or shot.get("duration_seconds") or 5)
        duration = min(60, coerce_video_duration(duration))

        source_excerpt = _compact(
            shot.get("source_excerpt")
            or shot.get("visible_event")
            or shot.get("screen_subject")
            or video.get("title")
            or shot_id,
            1200,
        )
        image_scene = "\n".join(
            part
            for part in [
                _compact(keyframe.get("prompt"), 1200),
                _compact(shot.get("screen_subject") or shot.get("main_subject"), 500),
                _compact(shot.get("action"), 500),
                _compact(shot.get("environment"), 500),
            ]
            if part
        )
        if not image_scene:
            image_scene = _compact(video.get("title") or source_excerpt, 800)

        lighting = _compact(shot.get("lighting") or "按导演分镜保持当前场景自然光线与情绪氛围。", 300)
        ambiance = _compact(
            shot.get("emotional_subtext")
            or shot.get("viewer_effect")
            or shot.get("environment")
            or "延续当前剧情节奏。",
            300,
        )

        segments.append(
            {
                "segment_id": shot_id,
                "duration_seconds": duration,
                "segment_break": bool(shot.get("segment_break") or shot.get("is_generation_boundary")),
                "novel_text": source_excerpt,
                "characters_in_segment": _as_list(shot.get("characters")),
                "scenes": _as_list(shot.get("scenes")),
                "props": _as_list(shot.get("props")),
                "image_prompt": {
                    "scene": image_scene,
                    "composition": {
                        "shot_type": _shot_type(shot.get("shot_size") or shot.get("composition")),
                        "lighting": lighting,
                        "ambiance": ambiance,
                    },
                },
                "video_prompt": {
                    "action": str(video.get("prompt") or shot.get("video_motion") or shot.get("motion_arc") or ""),
                    "camera_motion": _camera_motion(shot.get("camera_movement")),
                    "ambiance_audio": "仅保留画面内真实环境声、动作声和必要对白声，不添加背景音乐。",
                    "dialogue": [],
                },
                "transition_to_next": "cut",
                "note": f"由导演分镜预处理导出；video_id={video.get('video_id') or ''}; keyframe_id={video.get('keyframe_id') or ''}",
                "generated_assets": {
                    "storyboard_image": None,
                    "storyboard_last_image": None,
                    "grid_id": None,
                    "grid_cell_index": None,
                    "video_clip": None,
                    "video_thumbnail": None,
                    "video_uri": None,
                    "status": "pending",
                },
            }
        )

    summary = _compact(
        (story_analysis or {}).get("summary")
        or (story_beats or {}).get("summary")
        or (director_shots or {}).get("summary")
        or f"第 {episode} 集导演分镜导出脚本，共 {len(segments)} 镜。",
        1000,
    )
    script = {
        "episode": episode,
        "title": _episode_title(project, episode),
        "content_mode": "narration",
        "generation_mode": "director_storyboard",
        "duration_seconds": sum(item["duration_seconds"] for item in segments),
        "summary": summary,
        "novel": {
            "title": str((project or {}).get("title") or ""),
            "chapter": _source_filename(story_analysis, story_beats) or f"episode_{episode}",
        },
        "segments": segments,
    }
    validated = NarrationEpisodeScript.model_validate(script).model_dump()
    # `episode` is intentionally hidden from the LLM-facing schema, so Pydantic
    # drops it during validation.  The project manager still needs it as the
    # authoritative key for syncing project.json.
    validated["episode"] = episode
    validated["generation_mode"] = "director_storyboard"
    validated["duration_seconds"] = sum(item["duration_seconds"] for item in segments)
    return validated
