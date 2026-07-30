"""Video prompt pack planning helpers.

This slice converts director shots into video-generation packs. It may use
9-grid motion guide images and asset references, but start/end keyframes are
repair controls rather than mandatory first-pass inputs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from lib.resource_paths import resource_relative_path
from lib.text_backends.base import TextGenerationRequest, TextTaskType
from lib.text_generator import TextGenerator
from lib.video_duration import MIN_VIDEO_DURATION_SECONDS, coerce_video_duration
from server.services.text_model_json import parse_model_json_object

logger = logging.getLogger(__name__)

VIDEO_PROMPT_MODEL_TIMEOUT_SECONDS = 25
VIDEO_PROMPT_BATCH_SIZE = 8


class VideoReferenceEntryModel(BaseModel):
    role: str
    path: str | None = None
    submit_as: str
    required: bool = False
    status: str = "missing"


class VideoPromptModel(BaseModel):
    video_id: str
    shot_id: str
    keyframe_id: str
    title: str
    duration_seconds: int
    prompt: str
    start_image: str
    start_image_status: str
    reference_pack: dict[str, Any] = Field(default_factory=dict)
    optional_reference_roles: list[str] = Field(default_factory=list)
    submit_blockers: list[str] = Field(default_factory=list)
    review_checkpoints: list[str] = Field(default_factory=list)


class VideoPromptPlanModel(BaseModel):
    schema_version: int = 1
    episode: int
    source_keyframe_count: int = 0
    ready_video_count: int = 0
    total_duration_seconds: int = 0
    videos: list[VideoPromptModel] = Field(default_factory=list)


def _excerpt(text: Any, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


_SINGLE_ELLIPSIS_RE = re.compile(r"(?<!…)…(?!…)")


def _has_truncation_marker(text: Any) -> bool:
    """Return True when text looks like an excerpt, not intentional dialogue.

    ``_excerpt`` emits a single Chinese ellipsis (``…``). Natural Chinese
    dialogue usually uses ``……``; keep that, but reject single ``…`` and
    English ``...`` because they indicate a half sentence leaking into prompts.
    """

    value = str(text or "")
    return "..." in value or bool(_SINGLE_ELLIPSIS_RE.search(value))


def _prompt_text(text: Any, *, limit: int | None = None) -> str:
    """Clean text for model-facing video prompts without adding ellipses."""

    value = _visual_text(text, allow_metadata_after_strip=True)
    if not value:
        return ""
    # Remove excerpt markers if a model still returned them; do not generate
    # new markers in prompt text.
    value = value.replace("...", "")
    value = _SINGLE_ELLIPSIS_RE.sub("", value)
    value = re.sub(r"\s+", " ", value).strip()
    if limit is None or len(value) <= limit:
        return value

    clipped = value[:limit].rstrip()
    # Prefer a complete phrase/sentence if the field must be shortened.
    for sep in ("。", "；", ";", "，", ","):
        pos = clipped.rfind(sep)
        if pos >= max(12, int(limit * 0.55)):
            clipped = clipped[: pos + 1].rstrip()
            break
    return clipped


_DOCUMENT_META_MARKERS = (
    "最终剧本",
    "加长版",
    "完整剧本",
    "剧本正文",
    "分镜脚本",
)


def _strip_document_metadata(text: Any) -> str:
    """Remove script-document headers while preserving filmable shot details.

    Some user scripts contain a document header such as
    "第 3 集《...》（125秒加长版最终剧本） 分镜1（约0-8s）｜特写至近景｜..."
    inside fields that later become ``start_state``.  Video models need the
    filmable part ("特写至近景｜..."), not the document bookkeeping.
    """

    value = re.sub(r"\s+", " ", str(text or "")).strip()
    if not value:
        return ""
    value = value.replace("```text", "").replace("```", "").strip()
    value = re.sub(r"^【视频生成[^】]*】\s*", "", value)

    # If a whole-episode header precedes a shot marker, keep the shot details
    # after the marker's separator.
    value = re.sub(
        r"^.*?分镜\s*[\d一二三四五六七八九十百]+(?:\s*[（(][^）)]*[）)])?\s*[｜|:：\-—]+\s*",
        "",
        value,
    ).strip()

    # Remove leading episode/script headers that have no pixel value.
    value = re.sub(
        r"^(?:🎬\s*)?[^。！？\n]{0,160}?第\s*[\d一二三四五六七八九十百]+\s*集"
        r"[^。！？\n]{0,220}?(?:最终剧本|完整剧本|剧本正文|加长版)[）)]?\s*",
        "",
        value,
    ).strip()
    value = re.sub(r"^[《「][^》」]{1,80}[》」]\s*", "", value).strip()
    return value.strip(" ｜|—-：:")


def _looks_like_document_metadata(text: Any) -> bool:
    compact = re.sub(r"\s+", "", str(text or "")).strip()
    if not compact:
        return False
    if any(marker in compact for marker in _DOCUMENT_META_MARKERS):
        return True
    return bool(re.search(r"第[\d一二三四五六七八九十百]+集.*分镜[\d一二三四五六七八九十百]+", compact))


def _visual_text(text: Any, *, allow_metadata_after_strip: bool = False) -> str:
    cleaned = _strip_document_metadata(text)
    if not cleaned:
        return ""
    if not allow_metadata_after_strip and _looks_like_document_metadata(cleaned):
        return ""
    return cleaned


def _as_int(value: Any, default: int = MIN_VIDEO_DURATION_SECONDS) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _shot_map(director_shots: dict[str, Any]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for group in director_shots.get("shot_groups") or []:
        for shot in group.get("shots") or []:
            shot_id = str(shot.get("shot_id") or "")
            if shot_id:
                result[shot_id] = shot
    return result


def _frame_map(keyframe_status: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    return {
        str(frame.get("keyframe_id") or ""): frame
        for frame in (keyframe_status or {}).get("frames", [])
        if str(frame.get("keyframe_id") or "")
    }


def _prompt_map(keyframe_prompts: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in (keyframe_prompts or {}).get("prompts") or []:
        shot_id = str(item.get("shot_id") or "")
        role = str(item.get("role") or "")
        if not shot_id:
            continue
        if role == "guide_reference" or shot_id not in result:
            result[shot_id] = item
    return result


def _normalize_reference_match_text(text: Any) -> str:
    return re.sub(r"\s+", "", str(text or "")).replace("红色", "红").lower()


def _character_matches_prompt(name: str, prompt_text: str) -> bool:
    normalized_name = _normalize_reference_match_text(name)
    normalized_text = _normalize_reference_match_text(prompt_text)
    if not normalized_name or not normalized_text:
        return False
    if normalized_name in normalized_text:
        return True
    return normalized_name == "陆泰源" and any(keyword in normalized_text for keyword in ("男主", "主角", "御剑送丹"))


def _scene_matches_prompt(name: str, prompt_text: str) -> bool:
    normalized_name = _normalize_reference_match_text(name)
    normalized_text = _normalize_reference_match_text(prompt_text)
    if not normalized_name or not normalized_text:
        return False
    if normalized_name in normalized_text:
        return True
    return "山道" in normalized_name and any(keyword in normalized_text for keyword in ("山道", "竹林", "竹梢"))


def _prop_matches_prompt(name: str, prompt_text: str) -> bool:
    normalized_name = _normalize_reference_match_text(name)
    normalized_text = _normalize_reference_match_text(prompt_text)
    if not normalized_name or not normalized_text:
        return False
    if normalized_name in normalized_text:
        return True
    if "木牌" in normalized_name:
        return "木牌" in normalized_text
    pairs = [
        ("飞剑", "飞剑"),
        ("储物袋", "储物袋"),
        ("药瓶", "药瓶"),
        ("丹", "丹"),
        ("灵符", "灵符"),
        ("玉简", "玉简"),
    ]
    return any(name_keyword in normalized_name and prompt_keyword in normalized_text for name_keyword, prompt_keyword in pairs)


def _append_reference_entry(
    entries: list[dict[str, Any]],
    seen: set[str],
    *,
    role: str,
    path: Any,
    limit: int,
) -> None:
    value = str(path or "").strip()
    if not value or value in seen or len(entries) >= limit:
        return
    entries.append(
        {
            "role": role,
            "path": value,
            "submit_as": "reference_image",
            "required": False,
            "status": "ready",
        }
    )
    seen.add(value)


def _append_existing_reference_entry(
    entries: list[dict[str, Any]],
    seen: set[str],
    *,
    role: str,
    path: Any,
    project_path_exists: bool,
    submit_as: str = "reference_image",
    required: bool = False,
    limit: int = 9,
) -> None:
    value = str(path or "").strip()
    if not value or value in seen or len(entries) >= limit or not project_path_exists:
        return
    entries.append(
        {
            "role": role,
            "path": value,
            "submit_as": submit_as,
            "required": required,
            "status": "ready",
        }
    )
    seen.add(value)


def _asset_reference_entries(project: dict[str, Any] | None, shot: dict[str, Any], prompt_item: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(project, dict):
        return []
    prompt_item = prompt_item or {}
    prompt_text = "\n".join(
        str(item or "")
        for item in [
            prompt_item.get("title"),
            prompt_item.get("prompt"),
            shot.get("title"),
            shot.get("screen_subject"),
            shot.get("main_subject"),
            shot.get("environment"),
            " ".join(str(name) for name in shot.get("characters") or []),
            " ".join(str(name) for name in shot.get("props") or []),
        ]
    )
    entries: list[dict[str, Any]] = []
    seen: set[str] = set()
    for name, character in (project.get("characters") or {}).items():
        if not isinstance(character, dict) or not _character_matches_prompt(str(name), prompt_text):
            continue
        _append_reference_entry(
            entries,
            seen,
            role="character_face_closeup",
            path=character.get("reference_image"),
            limit=8,
        )
        _append_reference_entry(
            entries,
            seen,
            role="character_turnaround",
            path=character.get("character_sheet"),
            limit=8,
        )
        _append_reference_entry(
            entries,
            seen,
            role="character_combined_sheet",
            path=character.get("character_combined_sheet"),
            limit=8,
        )
    for name, scene in (project.get("scenes") or {}).items():
        if not isinstance(scene, dict) or not _scene_matches_prompt(str(name), prompt_text):
            continue
        _append_reference_entry(entries, seen, role="scene_reference", path=scene.get("scene_sheet"), limit=8)
    for name, prop in (project.get("props") or {}).items():
        if not isinstance(prop, dict) or not _prop_matches_prompt(str(name), prompt_text):
            continue
        _append_reference_entry(entries, seen, role="prop_reference", path=prop.get("prop_sheet"), limit=8)
    return entries


def _is_generic_performance(text: Any) -> bool:
    value = str(text or "")
    generic_markers = ["最后一拍", "新人物", "下一选择", "未完成感", "服务旁白", "B-roll", "画面动作"]
    return sum(1 for marker in generic_markers if marker in value) >= 1


def _performance_for_video(shot: dict[str, Any]) -> str:
    parts = [
        shot.get("facial_performance"),
        shot.get("body_performance"),
        shot.get("performance"),
    ]
    specific = [_prompt_text(part, limit=120) for part in parts if part and not _is_generic_performance(part)]
    return "；".join(specific) if specific else "动作自然，情绪明确，人物姿态服务当前剧情瞬间。"


def _combined_shot_text(*items: dict[str, Any] | None) -> str:
    parts: list[str] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        for key in (
            "title",
            "source_excerpt",
            "screen_subject",
            "main_subject",
            "action",
            "visible_event",
            "start_state",
            "end_state",
            "motion_arc",
            "video_motion",
            "cinematic_language",
            "camera_blocking",
            "movement_design",
            "editing_strategy",
            "transition_plan",
            "micro_performance",
            "environment",
        ):
            parts.append(_visual_text(item.get(key), allow_metadata_after_strip=True))
        parts.extend(str(name) for name in item.get("characters") or [])
        parts.extend(str(name) for name in item.get("props") or [])
    return _normalize_reference_match_text("\n".join(parts))


def _is_sword_flight_context(*items: dict[str, Any] | None) -> bool:
    text = _combined_shot_text(*items)
    return ("御剑" in text or "飞剑" in text) and any(keyword in text for keyword in ("竹梢", "竹林", "山道", "飞行", "掠过"))


def _is_transmission_jade_shot(shot: dict[str, Any], prompt_item: dict[str, Any] | None) -> bool:
    text = _combined_shot_text(shot, prompt_item)
    return "玉简" in text or "传音" in text or ("订单" in text and "丹铺" not in text)


def _flight_continuity_line(
    prompt_item: dict[str, Any] | None,
    shot: dict[str, Any],
    previous_shot: dict[str, Any] | None,
    previous_shots: list[dict[str, Any]] | None = None,
) -> str:
    context = list(previous_shots or [])
    if previous_shot and previous_shot not in context:
        context.append(previous_shot)
    if not context or not _is_transmission_jade_shot(shot, prompt_item) or not any(
        _is_sword_flight_context(item) for item in context
    ):
        return ""
    return (
        "连续性承接：本镜仍在上一镜建立的御剑/飞行途中，角色仍站在飞剑或飞行载具上，"
        "飞剑保持向前运动，不要突然落地或变成地面站立；一手稳住身体或控剑，"
        "另一手抬起传音玉简/信息载体查看，衣摆和周围环境被速度带动。"
    )


def _human_source_text(shot: dict[str, Any], prompt_item: dict[str, Any] | None = None) -> str:
    parts: list[str] = []
    seen: set[str] = set()
    for item in [
        shot.get("source_excerpt"),
        shot.get("visible_event"),
        shot.get("action"),
        shot.get("screen_subject"),
        shot.get("title"),
        (prompt_item or {}).get("title"),
    ]:
        compact = _visual_text(item, allow_metadata_after_strip=True)
        if not compact:
            continue
        if _has_truncation_marker(compact):
            continue
        # The deterministic director fallback often stores "source；画面停在..."
        # in action. Keep only the actual source portion for prompt inference.
        compact = compact.split("；画面停在", 1)[0].strip()
        key = _normalize_reference_match_text(compact)
        if key in seen:
            continue
        parts.append(compact)
        seen.add(key)
    text = " ".join(parts)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _is_generic_motion_text(text: Any) -> bool:
    value = str(text or "")
    if not value.strip():
        return True
    markers = [
        "人物呼吸、衣摆、手指和环境灵光保持细微运动",
        "人物呼吸、衣摆、手指和环境细节保持细微运动",
        "主体保持当前姿态",
        "呈现：",
        "画面停在最有动作张力的一帧",
        "动作从静止预备推进到关键定格",
        "服务旁白节奏",
        "后的半拍，主体仍在画面中心",
    ]
    return any(marker in value for marker in markers)


def _grid_cell_text(cell: dict[str, Any]) -> str:
    if not isinstance(cell, dict):
        return ""
    parts = []
    for key in ("visual", "body"):
        value = _visual_text(cell.get(key), allow_metadata_after_strip=True)
        if not value:
            continue
        if _has_truncation_marker(value):
            continue
        if any(
            marker in value
            for marker in (
                "无人物表演",
                "不画主角脸",
                "不用脸部表情",
                "不补不可见表情",
                "保持主观视角",
                "定格主观参考帧",
            )
        ):
            continue
        parts.append(value.rstrip("。；;，, "))
    return "，".join(parts)


def _grid_motion_summary(prompt_item: dict[str, Any] | None, *, limit: int = 360) -> str:
    cells = (prompt_item or {}).get("grid_cells") or []
    if not isinstance(cells, list) or len(cells) < 3:
        return ""
    selected: list[str] = []
    for cell in cells[:9]:
        if not isinstance(cell, dict):
            continue
        cell_no = cell.get("cell") or len(selected) + 1
        text = _grid_cell_text(cell)
        if text:
            selected.append(f"{cell_no}.{_prompt_text(text, limit=90)}")
    return _prompt_text("动作分解：" + "；".join(selected), limit=limit) if selected else ""


def _grid_start_state(prompt_item: dict[str, Any] | None) -> str:
    cells = (prompt_item or {}).get("grid_cells") or []
    if isinstance(cells, list) and cells:
        return _grid_cell_text(cells[0])
    return ""


def _grid_end_state(prompt_item: dict[str, Any] | None) -> str:
    cells = (prompt_item or {}).get("grid_cells") or []
    if isinstance(cells, list) and cells:
        return _grid_cell_text(cells[-1])
    return ""


def _strip_generic_video_text(text: Any) -> str:
    value = str(text or "")
    for pattern in (
        r"；?画面动作服务旁白信息点[^。；;]*[。；;]?",
        r"；?可用回望、停顿、环境反应或 B-roll 承接解说[。；;]?",
        r"；?情绪由道具速度、雾气和环境压迫感表达[。；;]?",
        r"脸部、眼神、嘴角、肩颈、手指和身体重心都要有连续细微变化[。；;]?",
    ):
        value = re.sub(pattern, "", value)
    value = value.replace("B-roll", "").replace("服务旁白", "")
    return re.sub(r"\s+", " ", value).strip(" ；;。")


def _specific_video_fields(
    *,
    source: str,
    shot: dict[str, Any],
    duration: int,
    continuity_line: str,
) -> dict[str, str]:
    """Derive concrete video actions from source text for deterministic fallback.

    Capability-specific repairs are triggered only by terms present in the
    current shot/context, never by project name.  This keeps the system
    reusable across modern drama, ads, xianxia, and other project types.
    """
    compact = re.sub(r"\s+", "", source)
    fields: dict[str, str] = {}

    if (
        "下品护脉丹" in compact
        or "半炷香" in compact
        or "传音玉简" in compact
        or ("订单" in compact and any(marker in compact for marker in ("玉简", "丹药", "符文", "修仙", "灵光")))
    ):
        fields["start_state"] = (
            "角色仍处在上一镜的连续动作中，手中的传音玉简/信息载体亮起灵光或提示光。"
        )
        fields["motion"] = (
            f"镜头推近信息载体，任务/订单信息以灵光、短字块或界面形式浮出：{_prompt_text(source, limit=120)}；"
            "角色快速扫读信息后表情收紧，抬头看向目标方向。"
        )
        fields["end_state"] = "停在角色一手持信息载体、一边保持原动作连续性的半身近景，紧迫感不断开。"
        fields["performance"] = "眉头压低，眼角绷紧，手指扣紧信息载体边缘，肩颈因赶时间微微僵硬。"
        fields["camera"] = "先推近信息载体上的提示，再轻推到角色紧张表情。"
        fields["lighting"] = "环境主光叠加信息载体的微弱提示光，照亮手指、下颌和胸前衣料。"
        return fields

    if "山魈" in compact and "扑空" in compact and "撞断" in compact:
        fields["start_state"] = "飞剑贴着竹林边缘闪开，第一只小山魈扑击落空。"
        fields["motion"] = (
            "第一只小山魈收不住力道，身体从飞剑后方砸进青竹，连续撞断一排竹竿；"
            "断竹和竹叶向镜头前景飞散，飞剑从碎竹缝隙中擦边掠过。"
        )
        fields["end_state"] = "停在断竹倾倒、小山魈从碎竹里翻滚落地的瞬间，男主已经拉开半个身位。"
        fields["performance"] = "男主没有回头，只用余光确认扑击落空，脚下继续压住飞剑保持速度。"
        fields["camera"] = "侧后方跟拍，山魈撞竹时镜头短促震动，随后追回飞剑。"
        fields["lighting"] = "晨雾柔光中混入断竹飞散的冷绿色碎影。"
        return fields

    if "山魈" in compact and "侧面扑来" in compact:
        fields["start_state"] = "第二只小山魈从侧方竹影里横扑出来，爪尖直扫男主头侧。"
        fields["motion"] = (
            "男主身体突然贴低飞剑侧缘，肩背几乎擦着剑身滑过；"
            "山魈爪子从他头发上方削过，几缕发丝和竹叶被气流卷走，飞剑仍保持向前。"
        )
        fields["end_state"] = "停在爪影掠过脸侧、男主贴剑滑出攻击线的瞬间。"
        fields["performance"] = "男主瞳孔一缩但动作很稳，牙关咬住，单手压住剑身保持平衡。"
        fields["camera"] = "贴近人物侧脸和飞剑的横向跟拍，爪影从前景一闪而过。"
        return fields

    if "山魈" in compact and ("扑" in compact or "砸向飞剑" in compact):
        fields["start_state"] = "男主踩着破旧飞剑掠过竹林山坡，前方雾气被剑风切开。"
        fields["motion"] = (
            "三只小山魈从山坡上方扑落，四肢张开、爪子朝飞剑砸来，尖叫声带动竹叶震颤；"
            "飞剑贴着竹梢侧向闪避，剑尾青光拖出断续尾迹，山石碎屑和竹叶被扑击震飞。"
        )
        fields["end_state"] = "停在飞剑刚避开扑击的半拍，山魈身体擦过画面边缘，危险仍贴在身后。"
        fields["performance"] = "男主膝盖压低、身体前倾稳住重心，眼神迅速判断山魈落点，嘴角绷住不慌乱。"
        fields["camera"] = "快速侧前方跟拍，山魈从上方斜切入画，镜头小幅甩动制造突袭感。"
        fields["lighting"] = "晨雾柔光中带竹林冷绿反光，山魈掠过时投下快速阴影。"
        return fields

    if "飞剑" in compact and ("贴地俯冲" in compact or "钻进竹林" in compact):
        fields["start_state"] = "飞剑原本在竹梢上方高速前进，山魈扑击逼近。"
        fields["motion"] = (
            "男主脚尖一压，破旧飞剑剑尖猛地向下扎，沿山石边缘贴地俯冲进竹林；"
            "剑身几乎擦过石面和竹根，竹叶被气流撕开，山魈从上方扑空。"
        )
        fields["end_state"] = "停在飞剑压低高度钻入竹林阴影的瞬间，石屑和竹叶在身后飞散。"
        fields["performance"] = "男主重心下沉，脚掌压紧剑身，肩膀贴低，表情冷静带一点冒险的狠劲。"
        fields["camera"] = "低角度贴地追拍，跟随飞剑突然下坠再穿入竹林。"
        return fields

    if ("灵符" in compact or "符纸" in compact) and any(marker in compact for marker in ("爆", "藤", "受潮", "术法", "火光")):
        fields["start_state"] = "藤蔓逼近飞剑后方，男主从腰间摸出一张皱巴巴的低阶灵符。"
        fields["motion"] = (
            "他甩出灵符并手掐诀，灵符贴上藤蔓后先潮湿发软、灵光卡顿；"
            "男主脸色一僵，下一瞬符纸迟滞爆开，火光和灵气把藤蔓炸得猛缩回去。"
        )
        fields["end_state"] = "爆炸余光照亮男主僵住又松一口气的脸，藤蔓断须在烟雾中抽回。"
        fields["performance"] = "先是嘴角僵住、眼睛瞪大，随后咬牙补诀；手腕猛压，爆炸后肩膀才松半寸。"
        fields["camera"] = "手部灵符特写接藤蔓爆点，中近景轻微震动表现迟来的爆炸。"
        fields["lighting"] = "竹林冷绿基调中加入灵符爆开的暖黄火光和烟尘散射。"
        return fields

    if "飞剑" in compact and "藤" in compact and ("一跃而起" in compact or "上方飞过" in compact):
        fields["start_state"] = "藤网在飞剑前方收紧，飞剑正对藤蔓缝隙冲去。"
        fields["motion"] = (
            "男主从飞剑上一跃而起，身体在空中舒展成轻松滑翔姿势；"
            "飞剑从藤蔓中间缝隙穿过，男主则从藤网正上方越过，衣摆擦着藤尖掠过。"
        )
        fields["end_state"] = "停在男主越过藤网、飞剑从下方缝隙穿出的上下分层画面。"
        fields["performance"] = "男主表情故作悠闲，身体核心收紧保持平衡，脚尖准备重新落回飞剑。"
        fields["camera"] = "低机位仰拍藤网和男主越过的弧线，再跟回下方飞剑。"
        return fields

    if "飞剑" in compact and ("藤妖" in compact or "藤蔓" in compact or "细藤" in compact):
        fields["start_state"] = "飞剑刚穿入竹林，前方地面和竹根开始异常鼓动。"
        fields["motion"] = (
            "青竹藤妖从地下窜起，粗藤交错形成拦路大网，细藤从后方追来；"
            "男主踩剑寻找缝隙，飞剑从藤网间隙穿过，藤条擦过衣摆和剑尾灵光。"
        )
        fields["end_state"] = "停在飞剑即将穿过藤网缝隙的半拍，前后藤蔓同时收紧。"
        fields["performance"] = "男主眼神快速扫过藤网空隙，手指掐诀预备反制，身体随飞剑压低偏转。"
        fields["camera"] = "前方低机位迎面看藤网升起，再切成跟拍穿缝的速度感。"
        return fields

    if any(keyword in compact for keyword in ("脸色", "咬牙", "倒吸", "惨叫", "笑容", "低头", "嘿嘿")):
        fields["motion"] = (
            f"围绕当前可见动作展开：{_prompt_text(source, limit=120)}；镜头保留人物脸部和上半身，"
            "让眉眼、嘴角、呼吸、肩颈和手指动作清楚表达情绪变化。"
        )
        fields["performance"] = "面部表演必须可见：眉毛压低或扬起，眼神快速变化，嘴角和下颌肌肉跟随台词与情绪收紧。"
        fields["camera"] = "中近景轻推或同速跟拍，保持脸、手和关键道具同时可读。"
        return fields

    if source.strip():
        fields["motion"] = (
            f"按当前画面动作展开：{_prompt_text(source, limit=160)}；"
            "把人物动作、道具运动和环境反应同时表现出来，不只停留在静态姿态。"
        )
        fields["performance"] = _performance_for_video(shot)
    return fields


def _punctuated(text: Any, limit: int = 220) -> str:
    value = _prompt_text(text, limit=limit).rstrip()
    if not value:
        return ""
    return value if value[-1] in "。！？!?" else f"{value}。"


def _director_field(shot: dict[str, Any], key: str, fallback: str = "", limit: int = 180) -> str:
    value = _visual_text(shot.get(key), allow_metadata_after_strip=True)
    if value and not _has_truncation_marker(value):
        return _prompt_text(value, limit=limit)
    return _prompt_text(fallback, limit=limit)


def _cinematic_language_for_video(shot: dict[str, Any], source: str) -> str:
    fallback = (
        f"{_visual_text(shot.get('shot_size'), allow_metadata_after_strip=True) or '中景'}，"
        f"{_visual_text(shot.get('camera_angle'), allow_metadata_after_strip=True) or '平视'}；"
        f"{_visual_text(shot.get('composition'), allow_metadata_after_strip=True) or '主体清楚，前中后景层次明确'}。"
    )
    if "飞剑" in source or "御剑" in source:
        fallback += "用前景高速掠过和主体追焦表现速度，视线从飞行载具引到人物脸部。"
    return _director_field(shot, "cinematic_language", fallback, 220)


def _camera_blocking_for_video(shot: dict[str, Any]) -> str:
    fallback = _visual_text(shot.get("composition"), allow_metadata_after_strip=True) or (
        "人物、道具、环境按前中后三层调度，关键动作和脸部表演不被遮挡。"
    )
    return _director_field(shot, "camera_blocking", fallback, 220)


def _movement_design_for_video(shot: dict[str, Any], camera_movement: str, motion: str) -> str:
    fallback = (
        f"镜头以{camera_movement or '轻微推进'}执行；起点先建立人物、关键道具和环境的相对位置，"
        f"中段跟随主体动作路径推进，焦点从道具/手部转到眼神和脸部；动作重点为：{_prompt_text(motion, limit=100)}；"
        "速度从起步到动作峰值再逐步减慢，结尾停在反应、钩子或下一镜可顺切的位置。"
    )
    return _director_field(shot, "movement_design", fallback, 260)


def _editing_strategy_for_video(shot: dict[str, Any]) -> str:
    fallback = _visual_text(shot.get("edit_note"), allow_metadata_after_strip=True) or (
        "单镜连续呈现为主，不做复杂剪辑；结尾保留半拍停顿，方便下一镜顺切。"
    )
    return _director_field(shot, "editing_strategy", fallback, 220)


def _micro_performance_for_video(shot: dict[str, Any], performance: str) -> str:
    fallback = "；".join(
        item
        for item in [
            _visual_text(shot.get("facial_performance"), allow_metadata_after_strip=True),
            _visual_text(shot.get("body_performance"), allow_metadata_after_strip=True),
            performance,
        ]
        if item
    )
    if not fallback:
        fallback = "眉眼、嘴角、下颌、呼吸、肩颈、手指和身体重心都要有连续细微变化。"
    return _director_field(shot, "micro_performance", fallback, 300)


def _visual_title(shot: dict[str, Any], prompt_item: dict[str, Any] | None, source: str, shot_id: str = "") -> str:
    for candidate in (
        shot.get("title"),
        (prompt_item or {}).get("title"),
        shot.get("screen_subject"),
        shot.get("action"),
        shot.get("visible_event"),
        shot.get("source_excerpt"),
        source,
    ):
        cleaned = _visual_text(candidate)
        if cleaned:
            if _has_truncation_marker(cleaned):
                continue
            return cleaned
    return str(shot_id or shot.get("shot_id") or "video_clip")


def _first_visual_field(*candidates: Any, fallback: str = "") -> str:
    for candidate in candidates:
        cleaned = _visual_text(candidate, allow_metadata_after_strip=True)
        if cleaned:
            return cleaned
    return fallback


def _sanitize_video_prompt_text(prompt: Any) -> str:
    value = str(prompt or "").strip()
    if not value:
        return ""
    sanitized_lines: list[str] = []
    for line in value.splitlines():
        raw = line.strip()
        if not raw:
            sanitized_lines.append(raw)
            continue
        header = re.match(r"^(【视频生成[^】]*】)(.*)$", raw)
        if header:
            # Header is a section marker only. Do not carry display titles into
            # the model-facing prompt; they are often excerpted with "…".
            sanitized_lines.append(header.group(1))
            continue
        label = re.match(
            r"^(起始状态|动作发展|动作节奏|结束状态|镜头语言|镜头调度|运镜设计|剪辑策略|演员表演|细节表演|灯光氛围)[:：]\s*(.*)$",
            raw,
        )
        if label:
            body = _prompt_text(label.group(2))
            sanitized_lines.append(f"{label.group(1)}：{body}" if body else f"{label.group(1)}：")
            continue
        sanitized_lines.append(_prompt_text(raw) or _strip_document_metadata(raw))
    return "\n".join(sanitized_lines).strip()


def _video_prompt(
    prompt_item: dict[str, Any] | None,
    shot: dict[str, Any],
    duration: int,
    *,
    previous_shot: dict[str, Any] | None = None,
    previous_shots: list[dict[str, Any]] | None = None,
) -> str:
    source = _human_source_text(shot, prompt_item)
    title = _visual_title(shot, prompt_item, source, str(shot.get("shot_id") or ""))
    motion = _first_visual_field(
        shot.get("video_motion"),
        shot.get("motion_arc"),
        shot.get("action"),
        shot.get("visible_action"),
        source,
        title,
    )
    start_state = _first_visual_field(shot.get("start_state"), shot.get("screen_subject"), source, motion, title)
    end_state = _first_visual_field(shot.get("end_state"), shot.get("ending_state"), shot.get("action"), source, title)
    grid_motion = _grid_motion_summary(prompt_item)
    grid_start = _grid_start_state(prompt_item)
    grid_end = _grid_end_state(prompt_item)
    continuity_line = _flight_continuity_line(prompt_item, shot, previous_shot, previous_shots)
    specific = _specific_video_fields(
        source=source,
        shot=shot,
        duration=duration,
        continuity_line=continuity_line,
    )
    if continuity_line:
        start_state = (
            "角色仍在上一镜建立的飞行途中，双脚或身体重心保持在飞剑/飞行载具上，"
            "手中的传音玉简/信息载体忽然亮起提示光。"
        )
        motion = (
            "飞行载具保持向前运动，环境从脚下或身后后掠；"
            "角色身体前倾维持平衡，一手稳住身体或控剑，另一手抬起信息载体快速查看，"
            "眉头压低、眼神一惊后看向前方。"
        )
        end_state = "镜头停在角色仍处于飞行连续动作中、手持发光信息载体的半身状态，保留紧迫感。"
    if specific.get("start_state"):
        start_state = specific["start_state"]
    if specific.get("motion") and _is_generic_motion_text(motion):
        motion = specific["motion"]
    elif specific.get("motion") and (
        "订单" in source
        or "山魈" in source
        or "藤" in source
        or "灵符" in source
        or "俯冲" in source
        or "钻进竹林" in source
    ):
        motion = specific["motion"]
    if specific.get("end_state"):
        end_state = specific["end_state"]
    if grid_motion:
        motion = grid_motion
    if grid_start and (_is_generic_motion_text(start_state) or len(start_state) < 12):
        start_state = grid_start
    if grid_end and (_is_generic_motion_text(end_state) or "后的半拍" in end_state or len(end_state) < 12):
        end_state = grid_end
    camera_movement = specific.get("camera") or _visual_text(shot.get("camera_movement"), allow_metadata_after_strip=True)
    performance = _strip_generic_video_text(specific.get("performance") or _performance_for_video(shot))
    if not performance:
        performance = "表演只写当前画面可见反应：眼神、嘴角、手指、肩颈或前景停顿跟随动作变化。"
    lighting = specific.get("lighting") or _visual_text(shot.get("lighting"), allow_metadata_after_strip=True)
    cinematic_language = _cinematic_language_for_video(shot, source)
    camera_blocking = _camera_blocking_for_video(shot)
    movement_design = _movement_design_for_video(shot, camera_movement, motion)
    editing_strategy = _editing_strategy_for_video(shot)
    transition_plan = _director_field(
        shot,
        "transition_plan",
        "承接上一镜的动作、视线或情绪方向，结尾停在方便下一镜顺切的表情、手势或道具状态。",
        180,
    )
    micro_performance = _strip_generic_video_text(_micro_performance_for_video(shot, performance))
    if not micro_performance:
        micro_performance = performance
    timeline = shot.get("action_timeline")
    if isinstance(timeline, list) and timeline:
        timeline_text = "；".join(
            f"{item.get('time')}: {item.get('action')}" if isinstance(item, dict) else str(item)
            for item in timeline[:5]
        )
    else:
        timeline_text = "前70%完成主体动作，后30%保留反应、余韵或悬念停顿"
    lines = ["【视频生成 video_clip】"]
    if continuity_line:
        lines.append(continuity_line)
    lines.extend(
        [
            f"起始状态：{_prompt_text(start_state, limit=180)}",
            f"动作发展：{_prompt_text(motion, limit=420)}",
            f"动作节奏：{_prompt_text(timeline_text, limit=260)}。",
            f"结束状态：{_prompt_text(end_state, limit=180)}",
            f"镜头语言：{_punctuated(cinematic_language)}",
            f"镜头调度：{_punctuated(camera_blocking)}",
            f"运镜设计：{_punctuated(movement_design)}",
            f"剪辑策略：{_punctuated(editing_strategy)} 衔接：{_punctuated(transition_plan)}",
            f"演员表演：{performance}",
            f"细节表演：{micro_performance}",
            f"灯光氛围：{_punctuated(lighting)}",
            f"时长：约 {duration} 秒；动作只完成一个清晰小节，不跨越下一个 shot。",
            "参考素材使用：角色、场景、道具资产用于保持一致性；9宫格动作引导图只用于理解动作和运镜，不要把白底九宫格画进最终视频。",
            "连续性要求：角色位置、脸、服装、场景和道具保持一致，运动自然，不突兀变形，不随机切镜。",
        ]
    )
    return _sanitize_video_prompt_text("\n".join(lines))


def _review_checkpoints() -> list[str]:
    return [
        "视频提示词是否直接描述这一镜怎么演，而不是依赖关键帧兜底。",
        "动作是否只覆盖当前 shot，不提前进入下一个 shot。",
        "reference_pack 是否显示本次会提交的角色、场景、道具和9宫格动作引导图。",
        "时长是否符合系统规则：真实视频生成不得低于 5 秒。",
    ]


def _is_generation_boundary(shot: dict[str, Any]) -> bool:
    if bool(shot.get("is_generation_boundary")):
        return True
    if _as_int(shot.get("duration_seconds"), 0) <= 0:
        return True
    image_roles = shot.get("image_roles") or []
    return "review_frame" in image_roles and "start_image" not in image_roles


def _sanitize_video_item(video: dict[str, Any], fallback_video: dict[str, Any] | None = None) -> dict[str, Any]:
    cleaned = dict(video)
    fallback_video = fallback_video or {}
    title = _visual_text(cleaned.get("title")) or _visual_text(fallback_video.get("title"))
    cleaned["title"] = _excerpt(title or cleaned.get("shot_id") or fallback_video.get("shot_id") or "video_clip", 60)
    prompt = _sanitize_video_prompt_text(cleaned.get("prompt"))
    if not prompt and fallback_video.get("prompt"):
        prompt = _sanitize_video_prompt_text(fallback_video.get("prompt"))
    cleaned["prompt"] = prompt
    return cleaned


def build_video_prompt_plan(
    *,
    keyframe_prompts: dict[str, Any] | None = None,
    director_shots: dict[str, Any],
    keyframe_status: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
    project_dir: Any | None = None,
) -> dict[str, Any]:
    episode = _as_int((keyframe_prompts or {}).get("episode") or director_shots.get("episode"), 1)
    shots = _shot_map(director_shots)
    frames = _frame_map(keyframe_status)
    prompts_by_shot = _prompt_map(keyframe_prompts)
    videos: list[dict[str, Any]] = []

    ordered_shots = list(shots.items())
    for index, (shot_id, shot) in enumerate(ordered_shots):
        if _is_generation_boundary(shot):
            continue
        duration = coerce_video_duration(shot.get("duration_seconds"))
        item = prompts_by_shot.get(shot_id) or {}
        keyframe_id = str(item.get("keyframe_id") or f"KF-{shot_id}-guide")
        guide_frame = frames.get(keyframe_id, {})
        guide_image = str(guide_frame.get("file_path") or resource_relative_path("keyframe", keyframe_id))
        guide_ready = bool(guide_frame.get("exists"))
        asset_references = _asset_reference_entries(project, shot, item)
        selected_images: list[dict[str, Any]] = []
        seen_paths: set[str] = set()
        guide_exists_on_disk = guide_ready
        if project_dir is not None and guide_image:
            try:
                guide_exists_on_disk = bool((project_dir / guide_image).exists())
            except TypeError:
                guide_exists_on_disk = guide_ready
        _append_existing_reference_entry(
            selected_images,
            seen_paths,
            role="motion_guide_grid",
            path=guide_image,
            project_path_exists=guide_exists_on_disk,
            submit_as="reference_image",
            required=False,
            limit=9,
        )
        for entry in asset_references:
            _append_existing_reference_entry(
                selected_images,
                seen_paths,
                role=str(entry.get("role") or "asset_reference"),
                path=entry.get("path"),
                project_path_exists=str(entry.get("status") or "") == "ready",
                submit_as=str(entry.get("submit_as") or "reference_image"),
                required=bool(entry.get("required")),
                limit=9,
            )

        videos.append(
            _sanitize_video_item(
                {
                "video_id": f"VID-{shot_id}",
                "shot_id": shot_id,
                "keyframe_id": keyframe_id,
                "title": _visual_title(shot, item, _human_source_text(shot, item), shot_id),
                "duration_seconds": duration,
                "prompt": _video_prompt(
                    item,
                    shot,
                    duration,
                    previous_shot=ordered_shots[index - 1][1] if index > 0 else None,
                    previous_shots=[
                        ordered_shots[prev_index][1]
                        for prev_index in range(max(0, index - 2), index)
                    ],
                ),
                "start_image": "",
                "start_image_status": "not_required",
                "reference_pack": {
                    "policy": "首轮视频不强制 start_image；提交匹配到的角色、场景、道具资产作为一致性参考，若9宫格动作引导图已生成，则作为动作/运镜辅助参考。用户可在生成前删除不想提交的参考图。",
                    "selected_images": selected_images,
                },
                "optional_reference_roles": ["motion_guide_grid", "asset_reference", "repair_start_image", "repair_end_image"],
                "submit_blockers": [],
                "review_checkpoints": _review_checkpoints(),
                }
            )
        )

    payload = {
        "schema_version": 1,
        "episode": episode,
        "source_keyframe_count": len([p for p in (keyframe_prompts or {}).get("prompts") or [] if p.get("role") != "review_frame"]),
        "ready_video_count": len([video for video in videos if not video["submit_blockers"]]),
        "total_duration_seconds": sum(video["duration_seconds"] for video in videos),
        "videos": videos,
    }
    return VideoPromptPlanModel.model_validate(payload).model_dump()


def _director_shot_batches(director_shots: dict[str, Any], *, batch_size: int = VIDEO_PROMPT_BATCH_SIZE) -> list[dict[str, Any]]:
    content = {key: value for key, value in director_shots.items() if key != "shot_groups"}
    flattened: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for group in director_shots.get("shot_groups") or []:
        if not isinstance(group, dict):
            continue
        group_meta = {key: value for key, value in group.items() if key != "shots"}
        for shot in group.get("shots") or []:
            if isinstance(shot, dict):
                flattened.append((group_meta, shot))

    batches: list[dict[str, Any]] = []
    for start in range(0, len(flattened), max(1, batch_size)):
        grouped: list[dict[str, Any]] = []
        group_by_id: dict[str, dict[str, Any]] = {}
        for group_meta, shot in flattened[start : start + batch_size]:
            group_id = str(group_meta.get("group_id") or f"SG{len(grouped) + 1:02d}")
            group = group_by_id.get(group_id)
            if group is None:
                group = dict(group_meta)
                group["shots"] = []
                group_by_id[group_id] = group
                grouped.append(group)
            group["shots"].append(shot)
        batch = dict(content)
        batch["shot_groups"] = grouped
        batches.append(batch)
    return batches


def _shot_ids_in_director_plan(director_shots: dict[str, Any]) -> set[str]:
    return {
        str(shot.get("shot_id") or "")
        for group in director_shots.get("shot_groups") or []
        if isinstance(group, dict)
        for shot in group.get("shots") or []
        if isinstance(shot, dict) and str(shot.get("shot_id") or "")
    }


def _filter_keyframe_prompts(keyframe_prompts: dict[str, Any], shot_ids: set[str]) -> dict[str, Any]:
    filtered = dict(keyframe_prompts or {})
    filtered["prompts"] = [
        item
        for item in (keyframe_prompts or {}).get("prompts") or []
        if str(item.get("shot_id") or "") in shot_ids
    ]
    return filtered


def _filter_keyframe_status(keyframe_status: dict[str, Any] | None, shot_ids: set[str]) -> dict[str, Any] | None:
    if not isinstance(keyframe_status, dict):
        return keyframe_status
    filtered = dict(keyframe_status)
    filtered["frames"] = [
        frame
        for frame in keyframe_status.get("frames") or []
        if str(frame.get("shot_id") or "") in shot_ids
        or str(frame.get("keyframe_id") or "").replace("KF-", "").split("-", 1)[0] in shot_ids
    ]
    return filtered


def _video_system_prompt() -> str:
    return """你是视频动态提示词模型。你的任务是把导演分镜转换成可提交给视频模型的动态描述。

必须遵守：
1. 输出严格 JSON，符合 schema，不要 Markdown。
2. 每个视频片段只描述当前 shot 的动作，不跨入下一镜；真实生成时长不得低于 5 秒。
3. prompt 必须描述这一镜怎么演：起始状态、动作分解、表情变化、身体动作、道具运动、环境反馈、镜头运动、结束状态。
4. prompt 必须包含导演级镜头设计：镜头语言、镜头调度、运镜设计、剪辑策略、细节表演；不要只写“推近/跟拍/轻微手持”。
5. 运镜设计要写清楚镜头从哪里到哪里、主体从哪里到哪里、焦点如何转移、速度如何变化、最后停在哪里。
6. 细节表演要写眉眼、嘴角、下颌、呼吸、肩颈、手指和身体重心的连续微变化。
7. 蒙太奇、希区柯克变焦、甩镜、match cut、前景遮挡转场只在剧情需要时使用；不用时明确单镜连续呈现或动作顺切。
8. 如果导演分镜已有具体蒙太奇类型，必须继承它；禁止改成泛化的“使用蒙太奇”。如果需要自行判断，按以下类型选择：时间压缩=赶路/修炼/炼丹/调查/反复过程；平行=两地同时；交叉=两线逼近危机/救援/碰撞；省略=跳过显而易见过程；心理/回忆=记忆/恐惧/幻想/内心压力；隐喻/象征/预兆=命运物象/暗线/未来危险/能力觉醒；对比=身份/处境/情绪反差；加速节奏=追逐/倒计时/战斗升级；减速=失落/余韵/安静顿悟；冲击=攻击、雷光、刀光、眼睛特写等短促冲击。
9. 如果导演分镜已有风格化运镜，如诺兰式、斯皮尔伯格式、库布里克式、希区柯克式、王家卫式、是枝裕和式、黑泽明式、张艺谋式、李安式、芬奇式、宫崎骏式，必须继承其可执行镜头行为；禁止只保留导演名字，必须写清楚实际运镜路径、焦点转移、速度变化和结尾画面。
10. 关键动作放在前70%，最后30%用于反应、余韵、停顿或钩子。
11. 首轮视频不强制 start_image；角色、场景、道具资产用于一致性，9宫格动作引导图用于动作和运镜理解。
12. 不要把9宫格白底草稿画进最终视频；它只是动作参考。reference_pack 不超过9张，且必须保留 fallback 中的 selected_images。
13. 禁止把剧本文档元信息写进 prompt，例如：剧集标题、项目标题、125秒加长版、最终剧本、分镜1、约0-8s、Markdown 标题。起始状态必须是第一帧可见画面，不是文档标题。
14. 如果原文混有“分镜N｜景别｜画面内容”，只保留景别、画面、人物动作、环境、光影、运镜等可拍内容。
"""


async def build_video_prompt_plan_with_text_model(
    *,
    keyframe_prompts: dict[str, Any],
    director_shots: dict[str, Any],
    keyframe_status: dict[str, Any] | None = None,
    project: dict[str, Any] | None = None,
    project_dir: Any | None = None,
    project_name: str,
) -> dict[str, Any]:
    """Build video prompts with the configured text model, falling back to deterministic output."""
    fallback = build_video_prompt_plan(
        keyframe_prompts=keyframe_prompts,
        director_shots=director_shots,
        keyframe_status=keyframe_status,
        project=project,
        project_dir=project_dir,
    )
    try:
        generator = await TextGenerator.create(TextTaskType.VIDEO_PROMPTS, project_name=project_name)
    except Exception as exc:
        logger.warning("视频提示词文本模型初始化失败，回退到规则模板: %s", exc)
        return fallback

    fallback_by_id = {str(video.get("video_id") or ""): video for video in fallback.get("videos") or []}
    videos_by_id: dict[str, dict[str, Any]] = {}

    for batch_index, batch_director_shots in enumerate(_director_shot_batches(director_shots), start=1):
        shot_ids = _shot_ids_in_director_plan(batch_director_shots)
        batch_keyframes = _filter_keyframe_prompts(keyframe_prompts, shot_ids)
        batch_status = _filter_keyframe_status(keyframe_status, shot_ids)
        batch_fallback = build_video_prompt_plan(
            keyframe_prompts=batch_keyframes,
            director_shots=batch_director_shots,
            keyframe_status=batch_status,
            project=project,
            project_dir=project_dir,
        )
        try:
            result = await asyncio.wait_for(
                generator.generate(
                    TextGenerationRequest(
                        system_prompt=_video_system_prompt(),
                        prompt=json.dumps(
                            {
                                "keyframe_prompts": batch_keyframes,
                                "director_shots": batch_director_shots,
                                "keyframe_status": batch_status,
                                "fallback_videos": batch_fallback.get("videos") or [],
                                "reference_pack_policy": "首轮视频不强制 start_image；保留 fallback_videos 中已选中的9宫格动作引导图和角色/场景/道具资产参考；不要删除 fallback 中的 selected_images。",
                                "requirements": (
                                    "只生成这一小批 shot 对应的 videos；必须逐条扩写画面、动作、表演、镜头运动，"
                                    "必须写镜头语言、镜头调度、运镜设计、剪辑策略、细节表演；"
                                    "不要写泛化模板，不要生成整集；不要把剧集标题、最终剧本、分镜编号、时长备注等文档元信息写进 prompt。"
                                ),
                            },
                            ensure_ascii=False,
                        ),
                        max_output_tokens=6000,
                    ),
                    project_name=project_name,
                ),
                timeout=VIDEO_PROMPT_MODEL_TIMEOUT_SECONDS,
            )
            raw = parse_model_json_object(result.text)
            batch_plan = VideoPromptPlanModel.model_validate(raw).model_dump()
            if not batch_plan.get("videos"):
                raise ValueError("video prompt model returned empty videos")
            batch_videos = batch_plan.get("videos") or []
        except Exception as exc:
            logger.warning("视频提示词第 %d 批生成失败，使用该批规则模板: %s", batch_index, exc)
            batch_videos = batch_fallback.get("videos") or []

        for video in batch_videos:
            video_id = str(video.get("video_id") or "")
            fallback_video = fallback_by_id.get(video_id)
            if fallback_video:
                video["reference_pack"] = fallback_video.get("reference_pack") or video.get("reference_pack") or {}
                video["optional_reference_roles"] = fallback_video.get("optional_reference_roles") or video.get(
                    "optional_reference_roles"
                )
                video["submit_blockers"] = fallback_video.get("submit_blockers") or video.get("submit_blockers") or []
            video = _sanitize_video_item(video, fallback_video)
            if video_id:
                videos_by_id[video_id] = video

    ordered_videos = [
        videos_by_id.get(str(video.get("video_id") or ""), video)
        for video in fallback.get("videos") or []
    ]
    plan = {
        "schema_version": 1,
        "episode": fallback["episode"],
        "source_keyframe_count": fallback["source_keyframe_count"],
        "ready_video_count": len([video for video in ordered_videos if not video.get("submit_blockers")]),
        "total_duration_seconds": sum(int(video.get("duration_seconds") or 0) for video in ordered_videos),
        "videos": ordered_videos,
    }
    return VideoPromptPlanModel.model_validate(plan).model_dump()
