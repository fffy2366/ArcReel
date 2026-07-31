"""
生成 API 路由

处理分镜图、视频、角色图、线索图的生成请求。
所有生成请求入队到 GenerationQueue，由 GenerationWorker 异步执行。

错误处理：路由函数体只保留 happy path。领域异常（``lib.api_errors``）与 lib 层异常
（``FileNotFoundError`` / ``ScriptEditError`` / ``TaskSpecValidationError`` / 未预期异常）
由 app 级 exception handler 统一映射为 HTTP 响应并脱敏（见 ``server/error_handlers.py``）。
"""

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import APIRouter
from pydantic import BaseModel

from lib.api_errors import BadRequestError, NotFoundError
from lib.asset_types import ASSET_SPECS
from lib.config.resolver import ConfigResolver
from lib.generation_queue import get_generation_queue
from lib.generation_queue_client import TaskSpec
from lib.i18n import Translator
from lib.path_safety import safe_exists
from lib.project_manager import get_project_manager
from lib.resource_paths import resource_relative_path
from lib.script_models import get_generated_assets
from lib.storyboard_sequence import (
    find_storyboard_item,
    get_storyboard_items,
    resolve_storyboard_image_ref,
)
from server.auth import CurrentUser
from server.services.draft_video_qa import build_draft_video_repair_payload
from server.services.image_edit_tasks import EDITABLE_RESOURCE_TYPES, resolve_current_image_rel

router = APIRouter()

# ==================== 请求模型 ====================


class GenerateStoryboardRequest(BaseModel):
    prompt: str | dict
    script_file: str


class GenerateVideoRequest(BaseModel):
    prompt: str | dict
    script_file: str
    duration_seconds: int | None = None  # 改为 None，由服务层解析
    seed: int | None = None


class GenerateTtsRequest(BaseModel):
    script_file: str


class GenerateCharacterRequest(BaseModel):
    prompt: str


class GenerateSceneRequest(BaseModel):
    prompt: str


class GeneratePropRequest(BaseModel):
    prompt: str


class GenerateProductRequest(BaseModel):
    prompt: str


class EditImageRequest(BaseModel):
    resource_type: str
    resource_id: str
    instruction: str
    script_file: str | None = None


class GenerateKeyframeRequest(BaseModel):
    prompt: str
    negative_prompt: str | None = None
    episode: int
    shot_id: str | None = None
    role: str = "start_image"
    reference_images: list[str] | None = None


class GenerateDraftVideoRequest(BaseModel):
    prompt: str
    episode: int
    duration_seconds: int | None = None
    start_image: str | None = None
    reference_pack: dict | None = None
    reference_images: list[str] | None = None
    reference_videos: list[str] | None = None
    reference_audios: list[str] | None = None
    seed: int | None = None


class RepairDraftVideoRequest(BaseModel):
    episode: int
    seed: int | None = None


def _drafts_path(project_path: Path, episode: int, filename: str) -> Path:
    return project_path / "drafts" / f"episode_{episode}" / filename


def _find_keyframe_prompt(project_path: Path, episode: int, keyframe_id: str, _t: Translator) -> dict:
    path = _drafts_path(project_path, episode, "keyframe_prompts.json")
    if not path.exists():
        raise NotFoundError("draft_file_not_found")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload.get("prompts") or []:
        if str(item.get("keyframe_id") or "") == keyframe_id:
            return item
    raise NotFoundError("keyframe_not_found", keyframe_id=keyframe_id)


def _find_video_prompt(project_path: Path, episode: int, video_id: str) -> dict:
    path = _drafts_path(project_path, episode, "video_prompts.json")
    if not path.exists():
        raise NotFoundError("draft_file_not_found")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload.get("videos") or []:
        if str(item.get("video_id") or "") == video_id:
            return item
    raise NotFoundError("draft_video_not_found", video_id=video_id)


def _find_director_shot(project_path: Path, episode: int, shot_id: str) -> dict | None:
    if not shot_id:
        return None
    path = _drafts_path(project_path, episode, "director_shots.json")
    if not path.exists():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    for group in payload.get("shot_groups") or []:
        for shot in group.get("shots") or []:
            if str(shot.get("shot_id") or "") == shot_id:
                return shot
    return None


def _find_draft_video_qa_item(project_path: Path, episode: int, video_id: str) -> dict:
    path = _drafts_path(project_path, episode, "draft_video_qa.json")
    if not path.exists():
        raise NotFoundError("draft_file_not_found")
    payload = json.loads(path.read_text(encoding="utf-8"))
    for item in payload.get("items") or []:
        if str(item.get("video_id") or "") == video_id:
            return item
    raise NotFoundError("draft_video_not_found", video_id=video_id)


def _resolve_project_file_path(project_path: Path, rel_path: str, *, field_name: str) -> Path:
    raw = str(rel_path or "").strip()
    if not raw:
        raise BadRequestError("draft_video_blocked", video_id=field_name, reason=f"{field_name} is empty")
    resolved = (project_path / raw).resolve()
    try:
        resolved.relative_to(project_path.resolve())
    except ValueError:
        raise BadRequestError("draft_video_blocked", video_id=field_name, reason=f"{field_name} must be inside project")
    return resolved


def _with_existing_motion_guide_reference(project_path: Path, reference_pack: Any, keyframe_id: str) -> dict[str, Any]:
    pack = dict(reference_pack) if isinstance(reference_pack, dict) else {}
    selected_images = list(pack.get("selected_images")) if isinstance(pack.get("selected_images"), list) else []
    guide_path = resource_relative_path("keyframe", keyframe_id)
    if guide_path and (project_path / guide_path).exists():
        seen_paths = {
            str(entry.get("path") or "")
            for entry in selected_images
            if isinstance(entry, dict) and str(entry.get("path") or "")
        }
        if guide_path not in seen_paths:
            selected_images.insert(
                0,
                {
                    "role": "motion_guide_grid",
                    "path": guide_path,
                    "submit_as": "reference_image",
                    "required": False,
                    "status": "ready",
                },
            )
    pack["selected_images"] = selected_images[:9]
    return pack


# ==================== 分镜图生成 ====================


@router.post("/projects/{project_name}/generate/storyboard/{segment_id}")
async def generate_storyboard(
    project_name: str,
    segment_id: str,
    req: GenerateStoryboardRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """
    提交分镜图生成任务到队列，立即返回 task_id。

    生成由 GenerationWorker 异步执行，状态通过 SSE 推送。
    """

    def _sync():
        get_project_manager().load_project(project_name)
        script = get_project_manager().load_script(project_name, req.script_file)
        items, id_field, _, _, _ = get_storyboard_items(script)
        resolved = find_storyboard_item(items, id_field, segment_id)
        if resolved is None:
            raise NotFoundError("segment_not_found", id=segment_id)

    await asyncio.to_thread(_sync)

    # 结构校验 + 构造经单一守卫点（与 SDK 入队同源，规则不分叉）；
    # 校验失败抛 TaskSpecValidationError，由 app 级 handler 映射为 400
    spec = TaskSpec.from_request(
        task_type="storyboard",
        media_type="image",
        resource_id=segment_id,
        prompt=req.prompt,
        script_file=req.script_file,
    )

    # 入队
    queue = get_generation_queue()
    result = await queue.enqueue_task(
        project_name=project_name,
        task_type=spec.task_type,
        media_type=spec.media_type,
        resource_id=spec.resource_id,
        script_file=spec.script_file,
        payload=spec.payload,
        source="webui",
        user_id=_user.id,
    )

    return {
        "success": True,
        "task_id": result["task_id"],
        "deduped": result.get("deduped", False),
        "message": _t("storyboard_task_submitted", segment_id=segment_id),
    }


# ==================== 视频生成 ====================


@router.post("/projects/{project_name}/generate/video/{segment_id}")
async def generate_video(
    project_name: str,
    segment_id: str,
    req: GenerateVideoRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """
    提交视频生成任务到队列，立即返回 task_id。

    需要先有分镜图作为起始帧。生成由 GenerationWorker 异步执行。
    """

    def _sync():
        pm_local = get_project_manager()
        pm_local.load_project(project_name)
        project_path = pm_local.get_project_path(project_name)

        # 与 worker 一致：优先读取 generated_assets.storyboard_image，回退默认路径。
        # 旧宫格项目 storyboard_image 指向 scene_{id}_first.png，仍可正常解析。
        # 脚本缺失（FileNotFoundError）/ 脏脚本（分镜数组键损坏，ScriptEditError）均
        # fail-fast：不能 silently 降级走 default 路径——default 文件恰好存在时会让请求
        # 「先返回提交成功、worker 解析脚本时再确定失败」，撕裂用户预期。两者均由 app 级
        # handler 统一映射为脱敏响应（404 / 400）。
        script = pm_local.load_script(project_name, req.script_file)
        items, id_field, _, _, _ = get_storyboard_items(script)
        resolved = find_storyboard_item(items, id_field, segment_id)
        if resolved is None:
            raise NotFoundError("segment_not_found", id=segment_id)
        storyboard_rel = get_generated_assets(resolved[0]).get("storyboard_image")

        # 字段值来自磁盘剧本 JSON，不可信任：非字符串脏数据会让下面的路径拼接抛未处理
        # TypeError 变成通用 500；越界 / 绝对路径引用会把项目外任意文件当分镜图使用。
        # 校验口径与 execute_video_task / SDK 工具入队预检共用同一份（resolve_storyboard_image_ref）。
        try:
            storyboard_file = resolve_storyboard_image_ref(project_path, storyboard_rel)
        except ValueError:
            raise BadRequestError("invalid_storyboard_image_path", segment_id=segment_id) from None
        if storyboard_file is None:
            storyboard_file = project_path / "storyboards" / f"scene_{segment_id}.png"
        if not storyboard_file.is_file():
            raise BadRequestError("generate_storyboard_first", segment_id=segment_id)

    await asyncio.to_thread(_sync)

    # 结构校验 + 构造经单一守卫点（与 SDK 入队同源，规则不分叉）。
    # duration 是能力维度，留待执行层在 provider 解析后校验（见 ADR-0001）。
    spec = TaskSpec.from_request(
        task_type="video",
        media_type="video",
        resource_id=segment_id,
        prompt=req.prompt,
        script_file=req.script_file,
        extra_payload={"duration_seconds": req.duration_seconds, "seed": req.seed},
    )

    # 入队（provider 由服务层根据配置自动解析，调用方无需传递）
    queue = get_generation_queue()
    result = await queue.enqueue_task(
        project_name=project_name,
        task_type=spec.task_type,
        media_type=spec.media_type,
        resource_id=spec.resource_id,
        script_file=spec.script_file,
        payload=spec.payload,
        source="webui",
        user_id=_user.id,
    )

    return {
        "success": True,
        "task_id": result["task_id"],
        "deduped": result.get("deduped", False),
        "message": _t("video_task_submitted", segment_id=segment_id),
    }


@router.post("/projects/{project_name}/generate/keyframe/{keyframe_id}")
async def generate_keyframe(
    project_name: str,
    keyframe_id: str,
    req: GenerateKeyframeRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """提交导演分镜关键帧生成任务到队列。"""

    def _sync():
        project = get_project_manager().load_project(project_name)
        project_path = get_project_manager().get_project_path(project_name)
        item = _find_keyframe_prompt(project_path, req.episode, keyframe_id, _t)
        if str(item.get("role") or "") == "review_frame":
            raise BadRequestError("keyframe_review_frame_not_generatable", keyframe_id=keyframe_id)
        return project, item

    project, prompt_item = await asyncio.to_thread(_sync)
    prompt = req.prompt.strip() or str(prompt_item.get("prompt") or "").strip()
    if not prompt:
        raise BadRequestError("prompt_text_empty")

    spec = TaskSpec.from_request(
        task_type="keyframe",
        media_type="image",
        resource_id=keyframe_id,
        prompt=prompt,
        extra_payload={
            "negative_prompt": req.negative_prompt or prompt_item.get("negative_prompt") or "",
            "episode": req.episode,
            "shot_id": req.shot_id or prompt_item.get("shot_id"),
            "role": req.role or prompt_item.get("role") or "start_image",
            "reference_images": req.reference_images,
        },
    )
    queue = get_generation_queue()
    result = await queue.enqueue_task(
        project_name=project_name,
        task_type=spec.task_type,
        media_type=spec.media_type,
        resource_id=spec.resource_id,
        payload=spec.payload,
        source="webui",
        user_id=_user.id,
    )
    return {
        "success": True,
        "task_id": result["task_id"],
        "deduped": result.get("deduped", False),
        "message": _t("keyframe_task_submitted", keyframe_id=keyframe_id),
    }


@router.post("/projects/{project_name}/generate/draft-video/{video_id}")
async def generate_draft_video(
    project_name: str,
    video_id: str,
    req: GenerateDraftVideoRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """提交导演分镜草稿视频生成任务到队列。"""

    def _sync():
        get_project_manager().load_project(project_name)
        project_path = get_project_manager().get_project_path(project_name)
        item = _find_video_prompt(project_path, req.episode, video_id)
        blockers = [str(blocker) for blocker in item.get("submit_blockers") or [] if str(blocker)]
        if blockers:
            raise BadRequestError("draft_video_blocked", video_id=video_id, reason=", ".join(blockers))
        start_image = req.start_image or item.get("start_image")
        if start_image:
            start_image_path = _resolve_project_file_path(project_path, start_image, field_name="start_image")
            if not start_image_path.exists():
                raise BadRequestError("draft_video_blocked", video_id=video_id, reason="start_image_missing")
        reference_pack = (
            req.reference_pack
            if req.reference_pack is not None
            else _with_existing_motion_guide_reference(project_path, item.get("reference_pack"), str(item.get("keyframe_id") or ""))
        )
        return item, start_image, reference_pack

    prompt_item, start_image, reference_pack = await asyncio.to_thread(_sync)
    prompt = req.prompt.strip()
    if not prompt:
        raise BadRequestError("prompt_text_empty")

    spec = TaskSpec.from_request(
        task_type="draft_video",
        media_type="video",
        resource_id=video_id,
        prompt=prompt,
        extra_payload={
            "episode": req.episode,
            "duration_seconds": req.duration_seconds or prompt_item.get("duration_seconds"),
            "start_image": start_image,
            "reference_pack": reference_pack,
            "reference_images": req.reference_images,
            "reference_videos": req.reference_videos,
            "reference_audios": req.reference_audios,
            "seed": req.seed,
        },
    )
    queue = get_generation_queue()
    result = await queue.enqueue_task(
        project_name=project_name,
        task_type=spec.task_type,
        media_type=spec.media_type,
        resource_id=spec.resource_id,
        payload=spec.payload,
        source="webui",
        user_id=_user.id,
    )
    return {
        "success": True,
        "task_id": result["task_id"],
        "deduped": result.get("deduped", False),
        "message": _t("draft_video_task_submitted", video_id=video_id),
    }


@router.post("/projects/{project_name}/generate/draft-video/{video_id}/repair")
async def repair_draft_video(
    project_name: str,
    video_id: str,
    req: RepairDraftVideoRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """根据 QA 结果提交草稿视频修复任务。"""

    def _sync():
        project = get_project_manager().load_project(project_name)
        project_path = get_project_manager().get_project_path(project_name)
        video_prompt = _find_video_prompt(project_path, req.episode, video_id)
        qa_item = _find_draft_video_qa_item(project_path, req.episode, video_id)
        if str(qa_item.get("status") or "") != "needs_fix":
            raise BadRequestError("draft_video_repair_not_needed", video_id=video_id)
        shot = _find_director_shot(project_path, req.episode, str(video_prompt.get("shot_id") or ""))
        return build_draft_video_repair_payload(
            video_prompt,
            qa_item,
            project=project,
            project_path=project_path,
            shot=shot,
        )

    repair_payload = await asyncio.to_thread(_sync)
    repair_payload["seed"] = req.seed
    queue = get_generation_queue()
    result = await queue.enqueue_task(
        project_name=project_name,
        task_type="draft_video",
        media_type="video",
        resource_id=video_id,
        payload=repair_payload,
        source="webui",
        user_id=_user.id,
    )
    return {
        "success": True,
        "task_id": result["task_id"],
        "deduped": result.get("deduped", False),
        "message": _t("draft_video_repair_task_submitted", video_id=video_id),
    }


# ==================== 旁白配音（TTS）生成 ====================


async def _require_audio_provider_configured(project: dict) -> str:
    """未配置任何 audio 供应商时直接 400，让用户在生成入口就看到清晰提示。

    解析失败（无全局默认且 auto-resolve 找不到 ready 的 audio 供应商）即视为未配置；
    解析成功但凭证失效等运行期错误与图片/视频一致，留给 worker 在任务面板暴露。
    返回解析出的 provider_id，入队时直接复用，避免每段重复解析。
    """
    from lib.db import async_session_factory

    try:
        resolved = await ConfigResolver(async_session_factory).resolve_audio_backend(project, None)
    except ValueError:
        raise BadRequestError("audio_provider_not_configured")
    return resolved.provider_id


def _narration_text(segment: dict) -> str:
    text = segment.get("novel_text")
    return text.strip() if isinstance(text, str) else ""


async def _enqueue_tts_segment(
    *,
    project_name: str,
    segment_id: str,
    script_file: str,
    user_id: str,
    provider_id: str | None,
) -> dict:
    spec = TaskSpec.from_request(
        task_type="tts",
        media_type="audio",
        resource_id=segment_id,
        script_file=script_file,
    )

    queue = get_generation_queue()
    return await queue.enqueue_task(
        project_name=project_name,
        task_type=spec.task_type,
        media_type=spec.media_type,
        resource_id=spec.resource_id,
        script_file=spec.script_file,
        payload=spec.payload,
        source="webui",
        user_id=user_id,
        provider_id=provider_id,
    )


@router.post("/projects/{project_name}/generate/tts/{segment_id}")
async def generate_tts(
    project_name: str,
    segment_id: str,
    req: GenerateTtsRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """提交单段旁白配音任务到队列，立即返回 task_id。

    文本由执行层从剧本 segment 的 novel_text 读取；已有旁白的段允许重生成。
    """

    def _sync() -> tuple[dict, dict]:
        pm_local = get_project_manager()
        _project = pm_local.load_project(project_name)
        script = pm_local.load_script(project_name, req.script_file)
        items, id_field, _, _, _ = get_storyboard_items(script)
        resolved = find_storyboard_item(items, id_field, segment_id)
        if resolved is None:
            raise NotFoundError("segment_not_found", id=segment_id)
        return _project, resolved[0]

    project, segment = await asyncio.to_thread(_sync)

    if not _narration_text(segment):
        raise BadRequestError("tts_novel_text_missing", segment_id=segment_id)

    provider_id = await _require_audio_provider_configured(project)

    result = await _enqueue_tts_segment(
        project_name=project_name,
        segment_id=segment_id,
        script_file=req.script_file,
        user_id=_user.id,
        provider_id=provider_id,
    )

    return {
        "success": True,
        "task_id": result["task_id"],
        "deduped": result.get("deduped", False),
        "message": _t("tts_task_submitted", segment_id=segment_id),
    }


@router.post("/projects/{project_name}/generate/tts")
async def generate_tts_batch(
    project_name: str,
    req: GenerateTtsRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """批量提交旁白配音任务：只入队缺少 narration_audio 且有小说原文的段（断点补缺）。"""

    def _sync() -> tuple[dict, list[str]]:
        pm_local = get_project_manager()
        _project = pm_local.load_project(project_name)
        script = pm_local.load_script(project_name, req.script_file)
        items, id_field, _, _, _ = get_storyboard_items(script)
        missing: list[str] = []
        for item in items:
            if not _narration_text(item):
                continue
            if get_generated_assets(item).get("narration_audio"):
                continue
            seg_id = item.get(id_field)
            if seg_id:
                missing.append(str(seg_id))
        return _project, missing

    project, missing_ids = await asyncio.to_thread(_sync)

    if not missing_ids:
        return {"success": True, "task_ids": [], "deduped": False, "message": _t("tts_batch_none_missing")}

    provider_id = await _require_audio_provider_configured(project)

    task_ids: list[str] = []
    deduped_flags: list[bool] = []
    for seg_id in missing_ids:
        result = await _enqueue_tts_segment(
            project_name=project_name,
            segment_id=seg_id,
            script_file=req.script_file,
            user_id=_user.id,
            provider_id=provider_id,
        )
        task_ids.append(result["task_id"])
        deduped_flags.append(bool(result.get("deduped", False)))

    message = _t("tts_batch_submitted", count=len(task_ids)) if task_ids else _t("tts_batch_none_missing")
    # 批量语义：全部入队都命中既有任务（本次一个新任务都没建）才算 deduped
    return {
        "success": True,
        "task_ids": task_ids,
        "deduped": bool(task_ids) and all(deduped_flags),
        "message": message,
    }


# ==================== 资产设计图生成（character / scene / prop / product 共用） ====================


# i18n key 命名差异：scene 用历史前缀 "project_scene_*"
_ASSET_GENERATE_I18N: dict[str, dict[str, str]] = {
    "character": {"not_found": "character_not_found", "submitted": "character_task_submitted"},
    "scene": {"not_found": "project_scene_not_found", "submitted": "scene_task_submitted"},
    "prop": {"not_found": "prop_not_found", "submitted": "prop_task_submitted"},
    "product": {"not_found": "product_not_found", "submitted": "product_task_submitted"},
}


async def _enqueue_asset_generation(
    *,
    asset_type: str,
    project_name: str,
    resource_name: str,
    prompt: str,
    user_id: str,
    _t: Translator,
) -> dict:
    """项目级资产（character / scene / prop / product）设计图生成共用入队逻辑。"""
    spec = ASSET_SPECS[asset_type]
    keys = _ASSET_GENERATE_I18N[asset_type]

    def _sync():
        project = get_project_manager().load_project(project_name)
        # load_project 读时不校验 bucket 结构：project.json 存在显式 null 时
        # get(key, {}) 仍返回 None，`not in None` 会抛 TypeError → 500，故用 `or {}` 兜底
        if resource_name not in (project.get(spec.bucket_key) or {}):
            raise NotFoundError(keys["not_found"], name=resource_name)

    await asyncio.to_thread(_sync)

    task_spec = TaskSpec.from_request(
        task_type=asset_type,
        media_type="image",
        resource_id=resource_name,
        prompt=prompt,
    )

    queue = get_generation_queue()
    result = await queue.enqueue_task(
        project_name=project_name,
        task_type=task_spec.task_type,
        media_type=task_spec.media_type,
        resource_id=task_spec.resource_id,
        payload=task_spec.payload,
        source="webui",
        user_id=user_id,
    )

    return {
        "success": True,
        "task_id": result["task_id"],
        "deduped": result.get("deduped", False),
        "message": _t(keys["submitted"], name=resource_name),
    }


@router.post("/projects/{project_name}/generate/character/{char_name}")
async def generate_character(
    project_name: str,
    char_name: str,
    req: GenerateCharacterRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """提交角色设计图生成任务到队列，立即返回 task_id。"""
    return await _enqueue_asset_generation(
        asset_type="character",
        project_name=project_name,
        resource_name=char_name,
        prompt=req.prompt,
        user_id=_user.id,
        _t=_t,
    )


@router.post("/projects/{project_name}/generate/scene/{scene_name}")
async def generate_scene(
    project_name: str,
    scene_name: str,
    req: GenerateSceneRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """提交场景设计图生成任务到队列，立即返回 task_id。"""
    return await _enqueue_asset_generation(
        asset_type="scene",
        project_name=project_name,
        resource_name=scene_name,
        prompt=req.prompt,
        user_id=_user.id,
        _t=_t,
    )


@router.post("/projects/{project_name}/generate/prop/{prop_name}")
async def generate_prop(
    project_name: str,
    prop_name: str,
    req: GeneratePropRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """提交道具设计图生成任务到队列，立即返回 task_id。"""
    return await _enqueue_asset_generation(
        asset_type="prop",
        project_name=project_name,
        resource_name=prop_name,
        prompt=req.prompt,
        user_id=_user.id,
        _t=_t,
    )


@router.post("/projects/{project_name}/generate/product/{product_name}")
async def generate_product(
    project_name: str,
    product_name: str,
    req: GenerateProductRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """提交产品标准参考图（product sheet）生成任务到队列，立即返回 task_id。"""
    return await _enqueue_asset_generation(
        asset_type="product",
        project_name=project_name,
        resource_name=product_name,
        prompt=req.prompt,
        user_id=_user.id,
        _t=_t,
    )


# ==================== 图片指令式编辑（image edit） ====================


async def _require_i2i_image_provider_configured(project: dict) -> str:
    """项目 i2i 槽解析不出可用供应商时直接 400，不创建任务。

    图片编辑必然 i2i 且入队即知（唯一例外，见 ``docs/adr/0001`` 与 CONTEXT.md「图片编辑」），
    故解析前置到入队；执行层 ``generate_image_async`` 的 capability gating 保留兜底。
    返回解析出的 provider_id，入队时直接复用（限流池路由按 i2i 槽精确记账）。
    """
    from lib.db import async_session_factory

    try:
        resolved = await ConfigResolver(async_session_factory).resolve_image_backend(project, None, capability="i2i")
    except ValueError:
        raise BadRequestError("image_edit_i2i_unavailable")
    return resolved.provider_id


@router.post("/projects/{project_name}/edit/image")
async def edit_image(
    project_name: str,
    req: EditImageRequest,
    _user: CurrentUser,
    _t: Translator,
):
    """提交图片指令式编辑任务到队列，立即返回 task_id。

    以当前图为唯一参考图、编辑指令为唯一 prompt 走 i2i；新图覆盖 current、旧图自动进
    版本历史，原 image_prompt 不回写（编辑语义见 ``docs/adr/0050``）。
    """
    if req.resource_type not in EDITABLE_RESOURCE_TYPES:
        raise BadRequestError("image_edit_resource_type_invalid", resource_type=req.resource_type)
    instruction = req.instruction.strip()
    if not instruction:
        raise BadRequestError("image_edit_instruction_required")
    is_storyboard = req.resource_type == "storyboard"
    script_file = req.script_file.strip() if req.script_file else None
    if is_storyboard and not script_file:
        raise BadRequestError("image_edit_script_file_required")

    def _sync() -> dict:
        pm_local = get_project_manager()
        project = pm_local.load_project(project_name)
        project_path = pm_local.get_project_path(project_name)
        script = pm_local.load_script(project_name, str(script_file)) if is_storyboard else None
        try:
            current_rel = resolve_current_image_rel(project, req.resource_type, req.resource_id, script)
        except KeyError:
            if is_storyboard:
                raise NotFoundError("segment_not_found", id=req.resource_id)
            raise NotFoundError(_ASSET_GENERATE_I18N[req.resource_type]["not_found"], name=req.resource_id)
        if not (current_rel and safe_exists(project_path, current_rel)):
            raise BadRequestError("image_edit_no_current_image", id=req.resource_id)
        return project

    project = await asyncio.to_thread(_sync)

    provider_id = await _require_i2i_image_provider_configured(project)

    # 结构校验 + 构造经单一守卫点（与 SDK 入队同源，规则不分叉）
    spec = TaskSpec.from_request(
        task_type="image_edit",
        media_type="image",
        resource_id=req.resource_id,
        prompt=instruction,
        script_file=script_file if is_storyboard else None,
        extra_payload={"resource_type": req.resource_type},
    )

    queue = get_generation_queue()
    result = await queue.enqueue_task(
        project_name=project_name,
        task_type=spec.task_type,
        media_type=spec.media_type,
        resource_id=spec.resource_id,
        script_file=spec.script_file,
        # image_edit 跨四类资产 + storyboard 共用同一 task_type，resource_id 命名空间
        # 不互斥（角色和道具可能同名）；纳入去重键避免跨类型误判为重复任务。
        resource_type=req.resource_type,
        payload=spec.payload,
        source="webui",
        user_id=_user.id,
        provider_id=provider_id,
    )

    return {
        "success": True,
        "task_id": result["task_id"],
        "deduped": result.get("deduped", False),
        "message": _t("image_edit_task_submitted", id=req.resource_id),
    }
