"""Draft video QA helpers.

This first QA slice records human review results and suggests deterministic
repair strategies. It does not automatically enqueue repair generation.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class DraftVideoQaItemModel(BaseModel):
    video_id: str
    shot_id: str | None = None
    keyframe_id: str | None = None
    title: str = ""
    status: str = "needs_review"
    issue_type: str | None = None
    note: str = ""
    repair_strategy: dict[str, Any] = Field(default_factory=dict)
    generation_inputs: dict[str, Any] | None = None


class DraftVideoQaPlanModel(BaseModel):
    schema_version: int = 1
    episode: int
    total_count: int = 0
    approved_count: int = 0
    needs_fix_count: int = 0
    items: list[DraftVideoQaItemModel] = Field(default_factory=list)


_REPAIR_STRATEGIES: dict[str, dict[str, Any]] = {
    "face_mismatch": {
        "label": "脸不像",
        "add_reference_roles": ["character_face_closeup", "character_turnaround", "asset_reference"],
        "prompt_action": "强调角色五官、发型、服装和上一版关键帧一致。",
    },
    "scene_mismatch": {
        "label": "场景不对",
        "add_reference_roles": ["scene_reference", "asset_reference"],
        "prompt_action": "强调空间布局、光线方向和场景材质一致。",
    },
    "prop_mismatch": {
        "label": "道具不对",
        "add_reference_roles": ["prop_reference", "asset_reference"],
        "prompt_action": "强调道具外形、位置、大小和交互方式一致。",
    },
    "action_mismatch": {
        "label": "动作不对",
        "add_reference_roles": ["guide_reference"],
        "prompt_action": "收窄动作描述，只保留当前 shot 的一个动作小节。",
    },
    "camera_mismatch": {
        "label": "运镜不对",
        "add_reference_roles": ["guide_reference"],
        "prompt_action": "重写 camera_motion，明确推拉摇移和运动幅度。",
    },
    "lighting_mismatch": {
        "label": "灯光不对",
        "add_reference_roles": ["guide_reference", "scene_reference"],
        "prompt_action": "强调光源方向、亮度层次和暗部不能死黑。",
    },
    "other": {
        "label": "其他问题",
        "add_reference_roles": ["guide_reference"],
        "prompt_action": "根据人工备注调整 prompt 或参考图包。",
    },
}

MAX_REPAIR_SELECTED_IMAGES = 9


def repair_strategy_for_issue(issue_type: str | None) -> dict[str, Any]:
    if not issue_type:
        return {}
    return dict(_REPAIR_STRATEGIES.get(issue_type, _REPAIR_STRATEGIES["other"]))


def _video_status_map(draft_video_status: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("video_id") or ""): item
        for item in (draft_video_status or {}).get("videos", [])
        if str(item.get("video_id") or "")
    }


def _summarize(items: list[dict[str, Any]], episode: int) -> dict[str, Any]:
    payload = {
        "schema_version": 1,
        "episode": episode,
        "total_count": len(items),
        "approved_count": len([item for item in items if item.get("status") == "approved"]),
        "needs_fix_count": len([item for item in items if item.get("status") == "needs_fix"]),
        "items": items,
    }
    return DraftVideoQaPlanModel.model_validate(payload).model_dump()


def build_draft_video_qa_plan(
    *,
    video_prompts: dict[str, Any],
    draft_video_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    episode = int(video_prompts.get("episode") or 1)
    status_by_id = _video_status_map(draft_video_status)
    items: list[dict[str, Any]] = []
    for video in video_prompts.get("videos") or []:
        video_id = str(video.get("video_id") or "")
        if not video_id:
            continue
        video_status = status_by_id.get(video_id, {})
        generation_inputs = video_status.get("generation_inputs")
        items.append(
            {
                "video_id": video_id,
                "shot_id": video.get("shot_id"),
                "keyframe_id": video.get("keyframe_id"),
                "title": str(video.get("title") or video_id),
                "status": "needs_review" if video_status.get("exists") else "waiting_generation",
                "issue_type": None,
                "note": "",
                "repair_strategy": {},
                "generation_inputs": generation_inputs if isinstance(generation_inputs, dict) else None,
            }
        )
    return _summarize(items, episode)


def merge_draft_video_generation_inputs(
    qa_plan: dict[str, Any],
    *,
    draft_video_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Backfill current generation input snapshots into an existing QA plan."""
    episode = int(qa_plan.get("episode") or 1)
    status_by_id = _video_status_map(draft_video_status)
    items: list[dict[str, Any]] = []
    for item in qa_plan.get("items") or []:
        current = dict(item)
        video_id = str(current.get("video_id") or "")
        video_status = status_by_id.get(video_id, {})
        generation_inputs = video_status.get("generation_inputs")
        if isinstance(generation_inputs, dict):
            current["generation_inputs"] = generation_inputs
        items.append(current)
    return _summarize(items, episode)


def update_draft_video_qa_item(
    qa_plan: dict[str, Any],
    *,
    video_id: str,
    status: str,
    issue_type: str | None = None,
    note: str = "",
) -> dict[str, Any]:
    episode = int(qa_plan.get("episode") or 1)
    items = [dict(item) for item in qa_plan.get("items") or []]
    for item in items:
        if str(item.get("video_id") or "") != video_id:
            continue
        item["status"] = status
        item["note"] = note
        if status == "needs_fix":
            item["issue_type"] = issue_type or "other"
            item["repair_strategy"] = repair_strategy_for_issue(item["issue_type"])
        elif status == "approved":
            item["issue_type"] = None
            item["repair_strategy"] = {}
        else:
            item["issue_type"] = issue_type
            item["repair_strategy"] = repair_strategy_for_issue(issue_type)
        return _summarize(items, episode)
    raise KeyError(video_id)


def _text_for_asset_matching(
    video_prompt: dict[str, Any],
    qa_item: dict[str, Any],
    shot: dict[str, Any] | None,
) -> str:
    parts: list[str] = []
    for source in (video_prompt, qa_item, shot or {}):
        for key in (
            "video_id",
            "shot_id",
            "keyframe_id",
            "title",
            "prompt",
            "note",
            "screen_subject",
            "action",
            "performance",
            "lighting",
            "edit_note",
        ):
            value = source.get(key)
            if value:
                parts.append(str(value))
    return "\n".join(parts)


def _asset_name_aliases(name: str) -> set[str]:
    cleaned = str(name or "").strip()
    aliases = {cleaned} if cleaned else set()
    for sep in ("·", "/", "／", "|", "｜", "-", "—", "_", "（", "(", "：", ":"):
        if sep in cleaned:
            aliases.add(cleaned.split(sep, 1)[0].strip())
    return {alias for alias in aliases if len(alias) >= 2}


def _asset_name_matches_text(name: str, text: str) -> bool:
    return any(alias and alias in text for alias in _asset_name_aliases(name))


def _project_relative_existing_file(project_path: Path, raw_path: Any) -> str | None:
    raw_text = str(raw_path or "").strip()
    if not raw_text:
        return None

    candidate = Path(raw_text)
    raw_is_absolute = candidate.is_absolute()
    raw_parts = candidate.parts
    is_global_asset_ref = bool(raw_parts and raw_parts[0] == "_global_assets")
    if not raw_is_absolute:
        candidate = project_path.parent / candidate if is_global_asset_ref else project_path / candidate

    project_root = project_path.resolve()
    try:
        resolved = candidate.resolve()
    except OSError:
        return None

    try:
        rel_path = resolved.relative_to(project_root)
    except ValueError:
        if not raw_is_absolute and not is_global_asset_ref:
            return None
        try:
            global_rel = resolved.relative_to((project_path.parent / "_global_assets").resolve())
            rel_path = Path("_global_assets") / global_rel
        except ValueError:
            return None

    if not resolved.is_file():
        return None
    return rel_path.as_posix()


def _selected_image_path(entry: Any) -> str | None:
    if isinstance(entry, str):
        return entry
    if not isinstance(entry, dict):
        return None
    for key in ("path", "file_path", "relative_path", "image_path", "asset_path"):
        value = entry.get(key)
        if value:
            return str(value)
    return None


def _append_selected_image(
    selected_images: list[Any],
    seen_paths: set[str],
    *,
    role: str,
    path: str | None,
    submit_as: str,
    max_selected_images: int,
    asset_type: str | None = None,
    asset_name: str | None = None,
) -> bool:
    if not path or len(selected_images) >= max_selected_images or path in seen_paths:
        return False

    entry: dict[str, Any] = {
        "role": role,
        "path": path,
        "submit_as": submit_as,
        "required": False,
        "status": "ready",
    }
    if asset_type:
        entry["asset_type"] = asset_type
    if asset_name:
        entry["asset_name"] = asset_name
    if asset_type or asset_name:
        entry["source"] = "repair_auto_asset_match"

    selected_images.append(entry)
    seen_paths.add(path)
    return True


def _add_matching_assets(
    *,
    selected_images: list[Any],
    seen_paths: set[str],
    project: dict[str, Any],
    project_path: Path,
    match_text: str,
    bucket_key: str,
    sheet_field: str,
    role: str,
    max_selected_images: int,
) -> list[dict[str, str]]:
    added: list[dict[str, str]] = []
    bucket = project.get(bucket_key) or {}
    if not isinstance(bucket, dict):
        return added

    for name, data in bucket.items():
        if len(selected_images) >= max_selected_images:
            break
        if not isinstance(data, dict) or not _asset_name_matches_text(str(name), match_text):
            continue

        rel_path = _project_relative_existing_file(project_path, data.get(sheet_field))
        if not rel_path:
            continue

        if _append_selected_image(
            selected_images,
            seen_paths,
            role=role,
            path=rel_path,
            submit_as="reference_image",
            max_selected_images=max_selected_images,
            asset_type=bucket_key.rstrip("s"),
            asset_name=str(name),
        ):
            added.append(
                {"asset_type": bucket_key.rstrip("s"), "asset_name": str(name), "role": role, "path": rel_path}
            )

    return added


def _add_matching_character_assets(
    *,
    selected_images: list[Any],
    seen_paths: set[str],
    project: dict[str, Any],
    project_path: Path,
    match_text: str,
    max_selected_images: int,
) -> list[dict[str, str]]:
    added: list[dict[str, str]] = []
    characters = project.get("characters") or {}
    if not isinstance(characters, dict):
        return added

    for name, data in characters.items():
        if len(selected_images) >= max_selected_images:
            break
        if not isinstance(data, dict) or not _asset_name_matches_text(str(name), match_text):
            continue

        for field, role in (
            ("reference_image", "character_face_closeup"),
            ("character_sheet", "character_turnaround"),
            ("character_combined_sheet", "character_combined_sheet"),
        ):
            if len(selected_images) >= max_selected_images:
                break
            rel_path = _project_relative_existing_file(project_path, data.get(field))
            if not rel_path:
                continue
            if _append_selected_image(
                selected_images,
                seen_paths,
                role=role,
                path=rel_path,
                submit_as="reference_image",
                max_selected_images=max_selected_images,
                asset_type="character",
                asset_name=str(name),
            ):
                added.append({"asset_type": "character", "asset_name": str(name), "role": role, "path": rel_path})

    return added


def _augment_repair_reference_pack(
    reference_pack: dict[str, Any],
    *,
    video_prompt: dict[str, Any],
    qa_item: dict[str, Any],
    project: dict[str, Any] | None,
    project_path: Path | None,
    shot: dict[str, Any] | None,
    max_selected_images: int,
) -> dict[str, Any]:
    raw_selected = reference_pack.get("selected_images")
    selected_images = list(raw_selected) if isinstance(raw_selected, list) else []
    seen_paths = {path for entry in selected_images if (path := _selected_image_path(entry))}

    start_image = str(video_prompt.get("start_image") or "").strip()
    if start_image and start_image not in seen_paths:
        selected_images.insert(
            0,
            {
                "role": "start_image",
                "path": start_image,
                "submit_as": "start_image",
                "required": True,
                "status": str(video_prompt.get("start_image_status") or "ready"),
            },
        )
        seen_paths.add(start_image)

    added: list[dict[str, str]] = []
    if project and project_path:
        match_text = _text_for_asset_matching(video_prompt, qa_item, shot)
        issue_type = str(qa_item.get("issue_type") or "")
        if issue_type == "face_mismatch":
            added.extend(
                _add_matching_character_assets(
                    selected_images=selected_images,
                    seen_paths=seen_paths,
                    project=project,
                    project_path=project_path,
                    match_text=match_text,
                    max_selected_images=max_selected_images,
                )
            )
        elif issue_type in {"scene_mismatch", "lighting_mismatch"}:
            added.extend(
                _add_matching_assets(
                    selected_images=selected_images,
                    seen_paths=seen_paths,
                    project=project,
                    project_path=project_path,
                    match_text=match_text,
                    bucket_key="scenes",
                    sheet_field="scene_sheet",
                    role="scene_reference",
                    max_selected_images=max_selected_images,
                )
            )
        elif issue_type == "prop_mismatch":
            added.extend(
                _add_matching_assets(
                    selected_images=selected_images,
                    seen_paths=seen_paths,
                    project=project,
                    project_path=project_path,
                    match_text=match_text,
                    bucket_key="props",
                    sheet_field="prop_sheet",
                    role="prop_reference",
                    max_selected_images=max_selected_images,
                )
            )

    reference_pack["selected_images"] = selected_images[:max_selected_images]
    reference_pack["repair_asset_selection"] = {
        "mode": "auto_project_asset_match",
        "status": "selected" if added else "no_matching_project_asset",
        "max_selected_images": max_selected_images,
        "added": added,
    }
    return reference_pack


def build_draft_video_repair_payload(
    video_prompt: dict[str, Any],
    qa_item: dict[str, Any],
    *,
    project: dict[str, Any] | None = None,
    project_path: Path | None = None,
    shot: dict[str, Any] | None = None,
    max_selected_images: int = MAX_REPAIR_SELECTED_IMAGES,
) -> dict[str, Any]:
    strategy = qa_item.get("repair_strategy") or repair_strategy_for_issue(qa_item.get("issue_type"))
    original_prompt = str(video_prompt.get("prompt") or "").strip()
    repair_lines = [
        "",
        "【修复指令 repair】",
        f"已标记问题：{strategy.get('label') or qa_item.get('issue_type') or '需修复'}。",
        f"修复动作：{strategy.get('prompt_action') or '根据人工质检意见收窄提示词。'}",
    ]
    roles = strategy.get("add_reference_roles") or []
    if roles:
        repair_lines.append(f"参考图策略：后续如需增强一致性，优先追加 {' / '.join(roles)}。")

    reference_pack = dict(video_prompt.get("reference_pack") or {})
    reference_pack["repair_strategy"] = strategy
    reference_pack["repair_source"] = {
        "video_id": qa_item.get("video_id"),
        "issue_type": qa_item.get("issue_type"),
        "note": qa_item.get("note") or "",
    }
    reference_pack = _augment_repair_reference_pack(
        reference_pack,
        video_prompt=video_prompt,
        qa_item=qa_item,
        project=project,
        project_path=project_path,
        shot=shot,
        max_selected_images=max_selected_images,
    )

    return {
        "prompt": original_prompt + "\n".join(repair_lines),
        "duration_seconds": video_prompt.get("duration_seconds"),
        "start_image": video_prompt.get("start_image"),
        "reference_pack": reference_pack,
    }
