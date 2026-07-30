"""Director-shot planning helpers.

This slice turns a reviewed story-beat plan into a deterministic director
shot plan. It deliberately stays lightweight: one group per beat, short shots
per micro-beat, and explicit image-role hints for later keyframe/video steps.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import Any

from pydantic import BaseModel, Field

from lib.text_backends.base import TextGenerationRequest, TextTaskType
from lib.text_generator import TextGenerator
from lib.video_duration import MIN_VIDEO_DURATION_SECONDS, coerce_video_duration
from server.services.project_type_templates import (
    CONTENT_FORMAT_AD,
    CONTENT_FORMAT_INTERACTIVE,
    CONTENT_FORMAT_NARRATED,
    DEFAULT_CONTENT_FORMAT,
    is_interactive_boundary,
    template_summary,
)
from server.services.story_beats import normalize_story_beat_plan_for_director
from server.services.text_model_json import parse_model_json_object

logger = logging.getLogger(__name__)

DIRECTOR_SHOT_MODEL_TIMEOUT_SECONDS = 25
DIRECTOR_SHOT_MODEL_FAILURE_BREAKER = 1
MAX_SINGLE_SHOT_DURATION_SECONDS = 15


class DirectorShotModel(BaseModel):
    shot_id: str
    source_micro_id: str
    title: str
    source_excerpt: str = ""
    duration_seconds: int
    shot_size: str
    camera_angle: str
    camera_movement: str
    screen_subject: str
    action: str
    visible_event: str = ""
    main_subject: str = ""
    environment: str = ""
    characters: list[str] = Field(default_factory=list)
    props: list[str] = Field(default_factory=list)
    emotional_subtext: str = ""
    facial_performance: str = ""
    body_performance: str = ""
    prop_interaction: str = ""
    environment_reaction: str = ""
    composition: str = ""
    cinematic_language: str = ""
    camera_blocking: str = ""
    movement_design: str = ""
    editing_strategy: str = ""
    transition_plan: str = ""
    micro_performance: str = ""
    start_state: str = ""
    end_state: str = ""
    motion_arc: str = ""
    keyframe_start: str = ""
    video_motion: str = ""
    viewer_effect: str = ""
    color_palette: str = ""
    performance: str
    lighting: str
    edit_note: str
    image_roles: list[str] = Field(default_factory=list)
    reference_strategy: str = ""
    interaction_role: str = ""
    choice_point_id: str = ""
    choice_options: list[str] = Field(default_factory=list)
    is_generation_boundary: bool = False


class DirectorChoiceOptionModel(BaseModel):
    option_id: str
    label: str
    branch_key: str
    next_hint: str = ""


class DirectorChoicePointModel(BaseModel):
    choice_id: str
    source_node_id: str = ""
    line: int = 0
    prompt: str
    options: list[DirectorChoiceOptionModel] = Field(default_factory=list)
    handoff: str = "to_branch"


class DirectorShotGroupModel(BaseModel):
    group_id: str
    source_beat_id: str
    title: str
    purpose: str = ""
    duration_seconds: int = 0
    shots: list[DirectorShotModel] = Field(default_factory=list)


class DirectorShotPlanModel(BaseModel):
    schema_version: int = 1
    episode: int
    content_format: str = DEFAULT_CONTENT_FORMAT
    template_name: str = "剧情视频"
    template_focus: str = "情绪推进、镜头节奏、人物关系"
    format_profile: dict[str, Any] = Field(default_factory=dict)
    source_story_beat_count: int = 0
    total_duration_seconds: int = 0
    choice_points: list[DirectorChoicePointModel] = Field(default_factory=list)
    shot_groups: list[DirectorShotGroupModel] = Field(default_factory=list)


def _excerpt(text: Any, limit: int = 80) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _full_source_excerpt(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _as_int(value: Any, default: int = MIN_VIDEO_DURATION_SECONDS) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _split_duration(seconds: int) -> list[int]:
    """Split only when one visual action exceeds the video model's safe span."""
    if seconds <= 0:
        return []
    seconds = coerce_video_duration(seconds)
    if seconds <= MAX_SINGLE_SHOT_DURATION_SECONDS:
        return [seconds]
    parts = max(1, math.ceil(seconds / MAX_SINGLE_SHOT_DURATION_SECONDS))
    while parts > 1 and seconds // parts < MIN_VIDEO_DURATION_SECONDS:
        parts -= 1
    base = seconds // parts
    remainder = seconds % parts
    return [base + (1 if index < remainder else 0) for index in range(parts)]


def _shot_profile(dramatic_value: str, shot_index: int, content_format: str) -> tuple[str, str, str]:
    value = dramatic_value.lower()
    if content_format == CONTENT_FORMAT_AD:
        if any(keyword in value for keyword in ("attention_hook", "pain", "desire")):
            return "强钩子特写", "平视", "快速推近，前 3 秒抓注意力"
        if any(keyword in value for keyword in ("cta", "proof", "demo", "benefit")):
            return "结果展示镜头", "平视", "干脆推近或顺滑转场"
    if content_format == CONTENT_FORMAT_NARRATED:
        return "说明性中景/插入镜头", "平视", "慢横移或定机位，服务旁白节奏"
    if content_format == CONTENT_FORMAT_INTERACTIVE and any(
        keyword in value for keyword in ("choice", "gameplay", "return_to_story")
    ):
        return "第一人称近景", "主观机位", "轻微手持推进，保留玩家代入"
    if content_format == CONTENT_FORMAT_INTERACTIVE and any(keyword in value for keyword in ("hook", "cliffhanger")):
        return "悬念特写", "主观反应机位", "缓慢推近，停在可点击钩子前"
    if any(keyword in value for keyword in ("reveal", "turn", "climax", "反转", "揭示", "高潮")):
        return "特写", "平视", "缓慢推进"
    if any(keyword in value for keyword in ("conflict", "danger", "tension", "危机", "冲突", "紧张")):
        return "近景", "微低机位", "轻微手持推进"
    if "setup" in value or "铺垫" in value or shot_index == 0:
        return "中远景", "平视", "缓慢推进"
    if shot_index % 4 == 3:
        return "插入镜头", "俯视", "小幅摇移"
    return "中景", "平视", "定机位或微移"


def _lighting_for(text: str) -> str:
    if any(keyword in text for keyword in ("夜", "雨", "暗", "巷")):
        return "低照度柔和漫射光，保留雨后反光与暗部层次。"
    if any(keyword in text for keyword in ("火", "烟", "灯", "烛")):
        return "暖色局部光源，火光或烟头亮点作为视觉重心。"
    return "自然柔和主光，低对比度，避免硬阴影。"


def _infer_environment(text: str) -> str:
    if any(keyword in text for keyword in ("房间", "书桌", "咖啡", "计划书", "晨袍", "手机")):
        return "现代居家室内空间，书桌、窗光、生活物件和人物动线清楚，整体干净高级。"
    if any(keyword in text for keyword in ("夜市", "奶茶", "相馆", "机车")):
        return "现代都市生活场景，招牌、灯光、道路或店内陈设清楚，空间层次适合人物表演。"
    if any(keyword in text for keyword in ("青岚宗", "山道", "竹林", "晨雾")):
        return "青岚宗外门山道，晨雾贴着石阶和竹林流动，远处宗门轮廓被雾气压暗。"
    if any(keyword in text for keyword in ("丹铺", "药柜", "柜台", "丹药")):
        return "霞丹鑫外卖丹铺内，木质药柜层层排开，丹瓶和符纸在暖光里反出细碎灵光。"
    if any(keyword in text for keyword in ("校场", "飞剑课", "弟子")):
        return "训练场或开阔校场，地面空间清楚，背景人物和标识只作环境层次。"
    if any(keyword in text for keyword in ("雨", "巷", "夜市", "街灯", "街道")):
        return "雨后窄巷，地面积水反射零散灯光，背景被潮湿雾气柔化。"
    return "当前剧情场景，空间关系清楚，前景、中景、背景有层次。"


def _infer_characters(text: str) -> list[str]:
    names = ["男主", "女主", "小山魈", "师姐", "丹修", "外门弟子"]
    found = [name for name in names if name in text]
    for match in re.finditer(r"([王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐苏陆][一-龥]{1,2})", text):
        name = match.group(1)
        if name not in found:
            found.append(name)
    return found


def _infer_props(text: str) -> list[str]:
    candidates = [
        "破旧飞剑",
        "飞剑",
        "储物袋",
        "红色十字标志",
        "传音玉简",
        "玉质药瓶",
        "下品护脉丹",
        "低阶灵符",
        "飞剑课木牌",
        "商业计划书",
        "咖啡",
        "奶茶",
        "手机",
        "重型机车",
        "易拉罐",
        "雪克壶",
        "居家晨袍",
        "纯白衬衫",
    ]
    props: list[str] = []
    for item in candidates:
        if item in text and item not in props:
            props.append(item)
    return props


def _text_for_micro(micro: dict[str, Any]) -> str:
    return _full_source_excerpt(micro.get("source_excerpt") or micro.get("title") or "")


def _beat_context_text(beat: dict[str, Any]) -> str:
    return _excerpt(beat.get("summary") or beat.get("source_excerpt") or beat.get("title") or "", 360)


def _project_prefers_first_person(story_beats: dict[str, Any]) -> bool:
    text = " ".join(
        str(value or "")
        for key, value in story_beats.items()
        if key != "beats" and not isinstance(value, (dict, list))
    )
    for beat in story_beats.get("beats") or []:
        if not isinstance(beat, dict):
            continue
        text += " " + " ".join(str(beat.get(key) or "") for key in ("title", "summary", "source_excerpt"))
        for micro in beat.get("micro_beats") or []:
            if isinstance(micro, dict):
                text += " " + " ".join(
                    str(micro.get(key) or "")
                    for key in ("title", "source_excerpt", "director_context")
                )
    return "第一人称视角" in text or "男主第一人称" in text or "主观视角" in text


def _should_apply_first_person_pov(text: str, *, project_first_person: bool) -> bool:
    if not project_first_person and not any(marker in text for marker in ("第一人称", "男主第一人称", "主观视角", "POV")):
        return False
    if any(marker in text for marker in ("无人", "空镜", "纯场景", "外景空镜")):
        return False
    return True


def _apply_first_person_pov_fields(shot: dict[str, Any], *, source_text: str, context: str) -> None:
    shot["camera_angle"] = "男主第一人称主观视角"
    shot["shot_size"] = "第一人称主观近景/插入镜头"
    shot["camera_movement"] = "男主视线带动的轻微手持运动，镜头从可见前景手部/衣袖/桌面物件移动到关键对象"
    shot["composition"] = (
        "男主第一人称 POV 构图：镜头不能离体变成第三人称；必要时只露男主前景手、衣袖、胸前或镜头边缘，"
        "用对面人物、桌面道具、窗光和前景遮挡建立空间关系。"
    )
    shot["camera_blocking"] = (
        "主观视线调度：画面从男主眼前可见物开始，跟随视线或身体反应移动；"
        "不得切到看见男主全身的客观反打，除非只是前景手臂/衣袖。"
    )
    shot["movement_design"] = (
        "第一人称运镜：起点是男主眼前视野，前景可见手、衣袖、桌沿或镜头边缘；"
        "中段随视线微推、轻摇或被动作冲击短促一抖；焦点从前景反应转到关键人物/道具；"
        "结尾停在男主仍能看到的主观构图里。"
    )
    shot["edit_note"] = f"{shot.get('edit_note') or ''} 全剧第一人称 POV：本镜按男主主观视角生成，不拍男主第三人称全身。".strip()
    current = str(source_text or "")
    if "窗户渐显" in current or "旭日" in current:
        shot["screen_subject"] = "男主第一人称视角从清晨窗户和旭日晨光开始，窗光进入眼前视野。"
        shot["action"] = "男主第一人称视角看见窗户渐显和旭日东升，晨光穿过玻璃进入画面；镜头像刚睁眼或从回忆中醒来一样轻微呼吸晃动。"
        shot["visible_event"] = "第一人称看见窗户渐显、旭日东升和晨光入室。"
        shot["start_state"] = "黑场或昏暗视野渐亮，男主第一人称眼前出现清晨窗户轮廓。"
        shot["end_state"] = "停在男主第一人称看见旭日晨光穿过窗户的主观画面，准备下移到书桌。"
        shot["keyframe_start"] = "男主第一人称 POV：清晨窗户在眼前渐显，旭日从窗外升起，晨光穿过玻璃洒入室内；画面不能出现男主第三人称身体。"
        shot["video_motion"] = "第一人称视野从暗到亮，轻微呼吸晃动；焦点从窗户轮廓转到窗外旭日和洒入室内的晨光，结尾准备向书桌方向下移。"
    if "奶茶" in current and "男主" in current and any(marker in current for marker in ("喷洒", "喷", "一身一脸")):
        shot.update(
            {
                "screen_subject": "男主第一人称视角下，林予曦在对面操作台摇雪克壶失手，奶茶朝镜头和男主前景衣袖喷来。",
                "action": "林予曦在对面摇雪克壶，杯盖松脱，奶茶从她手中的雪克壶喷向男主第一人称镜头，溅到镜头边缘、前景衣袖和可见手臂；不是林予曦被泼。",
                "visible_event": "第一人称看见奶茶从林予曦手中的雪克壶喷向自己，打湿男主镜头边缘、衣袖和手臂。",
                "main_subject": "第一人称被奶茶喷到的瞬间：林予曦在对面，飞溅奶茶朝男主镜头袭来。",
                "prop_interaction": "雪克壶由林予曦握在画面对面，奶茶喷射方向必须从林予曦/雪克壶指向镜头和男主前景衣袖；禁止画成她泼到自己身上。",
                "environment_reaction": "奶茶液滴打到镜头边缘和男主前景衣袖，画面短促一抖，操作台杯具轻晃。",
                "start_state": "男主第一人称站在奶茶店操作台前，对面的林予曦拿起雪克壶准备摇。",
                "end_state": "停在奶茶溅满镜头边缘和男主前景衣袖的主观画面，林予曦在对面笑到后仰。",
                "motion_arc": "第一人称从雪克壶特写看起，林予曦摇壶失手，杯盖松开，奶茶沿画面纵深朝镜头喷来，冲击时镜头一抖，最后液滴挂在镜头边缘。",
                "keyframe_start": "男主第一人称 POV：奶茶店操作台对面，林予曦手持雪克壶失手，奶茶正从雪克壶喷向镜头和男主前景衣袖；画面边缘可见男主被溅到的衣袖/手臂，林予曦本人在对面，不是被泼的一方。",
                "video_motion": "第一人称主观运动：镜头先盯住林予曦手中的雪克壶，杯盖松脱后奶茶液体朝镜头飞来，液滴撞到镜头边缘和男主前景衣袖；镜头被冲击短促一抖，随后看见林予曦在对面后仰大笑。",
                "camera_movement": "男主第一人称手持视角，先盯雪克壶，再被飞溅奶茶冲击产生短促抖动",
            }
        )


def _is_flying_sword_lead_in(current_text: str, next_text: str, beat_context: str) -> bool:
    combined_next = f"{next_text} {beat_context}"
    return (
        "飞剑" in current_text
        and any(keyword in current_text for keyword in ("低空", "呼啸", "掠过", "剑身"))
        and "男主" in combined_next
        and any(keyword in combined_next for keyword in ("踩在剑上", "剑上", "御剑"))
    )


def _is_flying_sword_rider_reveal(previous_text: str, current_text: str, beat_context: str) -> bool:
    combined_current = f"{current_text} {beat_context}"
    return (
        "飞剑" in previous_text
        and "男主" in combined_current
        and any(keyword in combined_current for keyword in ("踩在剑上", "剑上", "储物袋", "红色十字"))
    )


def _apply_flying_sword_lead_in_fields(shot: dict[str, Any], *, source_text: str, next_text: str) -> None:
    shot.update(
        {
            "shot_size": "空中树冠层跟拍全景",
            "camera_angle": "略低机位斜仰拍，镜头位于竹冠侧下方但画面必须看见脚下大片竹梢",
            "camera_movement": "起始帧先锁定完整人物踩剑飞在竹冠上方，视频再用侧前方高速跟拍，随后从剑尖沿剑身轻微上摇到男主身体和脸部，配合追焦和镜头震动制造速度感",
            "screen_subject": "男主陆泰源完整踩在破旧飞剑上，从青岚宗外门竹冠上方掠过；脚下不是石阶地面，而是一整片被压弯的竹梢和雾海。",
            "action": "破旧青铁飞剑在竹梢上方约一到两人高处高速掠过，男主完整站在剑上赶路；画面必须远离地面石阶，不要贴地飞行。",
            "visible_event": (
                f"{source_text} 下一拍信息确认：{next_text}；因此本镜起始帧必须完整呈现男主踩在飞剑上的关系，再把局部揭示交给视频运镜。"
            ),
            "main_subject": "男主陆泰源御剑飞行的完整起始画面，破旧飞剑是前景焦点，人物全身和飞剑关系清楚。",
            "characters": ["男主"],
            "props": ["破旧飞剑", "飞剑", "储物袋", "红色十字标志"],
            "facial_performance": "男主脸部可见但不抢戏，眉头微压、眼神盯向前方山道，嘴唇收紧，表现赶路的专注和紧张。",
            "body_performance": "男主全身可见，双脚都踩在狭窄剑身上，两条腿同时可见，膝盖微弯抵消飞剑颠簸，身体重心前压，一只手下意识护住腰间储物袋；禁止只露一条腿。",
            "prop_interaction": "破旧飞剑承载男主飞行，剑尖固定指向画面右上方/前进方向，剑柄和灵石驱动盒固定在画面左下方/后方；剑身缺口、青铁斑驳和腰间红色十字储物袋要形成可辨认的视觉线索。",
            "composition": "侧前方略低机位斜仰拍，前景竹叶被速度拉成轻微动感虚化，中景完整破旧飞剑和男主全身清晰，飞剑剑尖明确指向画面右上方，剑柄和灵石驱动盒在画面左下方，脚下是一整片竹冠和雾海，远处山道只作为背景小面积出现。",
            "start_state": "晨雾缠在竹林树冠上缘，破旧飞剑悬在竹梢上方破雾切入，脚下竹梢被风压向下弯。",
            "end_state": "镜头高速贴近到男主腰侧储物袋和紧张脸部，仍保持人物、飞剑和竹冠上方环境连续，不落到地面。",
            "motion_arc": "起始帧先给完整人物踩剑飞在竹冠上方的空间关系，视频中镜头再从右上方剑尖和破旧剑身追焦推近，上摇经过双脚、腿部、储物袋到男主脸部。",
            "keyframe_start": "完整起始帧：侧前方略低机位斜仰拍，男主陆泰源全身完整踩在破旧青铁飞剑上，飞在青岚宗外门竹林树冠上方/竹梢上方，脚下可见大片竹梢和雾海而不是地面石阶；飞剑完整可见，剑尖明确朝向飞行方向，并固定指向画面右上方/前进方向，剑柄和灵石驱动盒固定在画面左下方/后方；男主双脚、两条腿、腰间红十字储物袋、上半身和脸部都在画面内，衣袍、发带和袋绳被疾风向后拉起；竹叶被风压弯，雾气被切开，画面有高速飞行的方向线和背景动感虚化。禁止贴地飞行，禁止剑尖反向，禁止只有脚或单腿。",
            "video_motion": "基于完整起始帧运动：镜头与飞剑同向高速侧前方跟拍，保持飞剑悬在竹冠上方；画面右上方剑尖切开晨雾，左下方剑柄和灵石驱动盒拖出断续青光尾迹；竹叶向下压弯并快速后掠，背景竹林横向动感虚化，雾气被剑气切成 V 形尾流；镜头轻微震动和追焦，从剑尖推到剑身缺口，再上摇经过男主双脚、两条腿、袍角、腰间储物袋，最后停到半身和紧张脸部。不要变成静图平移，不要落到地面。",
        }
    )


def _apply_flying_sword_rider_reveal_fields(shot: dict[str, Any], *, source_text: str, previous_text: str) -> None:
    shot.update(
        {
            "shot_size": "中近景揭示",
            "camera_angle": "微低机位转俯视",
            "camera_movement": "从男主脚边顺着腿部和腰间储物袋上摇到半身，再轻微抬高交代山道方向",
            "screen_subject": "男主踩在破旧飞剑上赶路，腰间灰扑扑储物袋和红色十字标志成为身份钩子。",
            "action": "承接上一镜的飞剑低空掠过，镜头继续揭示男主站在剑上，储物袋随着速度晃动，红色十字短暂撞入视觉中心。",
            "visible_event": f"{previous_text} 之后揭示：{source_text}",
            "main_subject": "御剑送丹的男主，破旧飞剑、储物袋、红色十字共同说明他的外卖员身份。",
            "characters": ["男主"],
            "props": ["破旧飞剑", "飞剑", "储物袋", "红色十字标志"],
            "facial_performance": "眉头压低，眼神盯着前方山道，嘴唇微抿，脸颊被疾风压出紧张赶路感。",
            "body_performance": "身体前倾保持平衡，一只手压住腰间储物袋，另一只手微张控剑，衣摆和袋绳被风向后扯。",
            "prop_interaction": "储物袋不是装饰，它随着御剑速度撞在腰侧，红色十字标志要清楚露出一瞬。",
            "composition": "人物腰侧和储物袋先占据画面中心，随后上摇到半身和脸，最后用轻俯视保留青岚宗山道、竹林和远处宗门轮廓。",
            "start_state": "镜头停在男主脚踩飞剑和腰侧储物袋的局部，承接上一镜的低机位速度。",
            "end_state": "镜头揭示男主半身与前方山道，观众确认这不是普通飞剑，而是男主正在执行送丹任务。",
            "motion_arc": "由脚和飞剑的局部细节上摇到腰间红色十字储物袋，再到男主紧张的半身状态，最后稍微抬高带出环境。",
            "keyframe_start": "男主双脚踩在破旧飞剑上，两条腿都清楚可见，腰间灰扑扑储物袋带红色十字标志，被风吹得轻微晃动；飞剑剑尖朝向飞行方向，剑柄和灵石驱动盒在后方，镜头从微低机位拍到腿部和腰侧，准备继续上摇揭示半身与脸。",
            "video_motion": "镜头从飞剑和双脚边继续上摇，掠过男主两条小腿、腰间储物袋和红色十字标志，再推到半身与紧张脸部；最后轻微抬高，露出晨雾山道和竹林方向，不要提前进入下一剧情事件。",
        }
    )


def _facial_performance_for(text: str) -> str:
    if not _infer_characters(text):
        return "无人物面部特写；情绪由道具速度、雾气和环境压迫感表达。"
    if any(keyword in text for keyword in ("急", "险", "撞", "崩", "追", "吼", "怒", "怕")):
        return "眉头压低，眼睛睁大并紧盯前方，鼻翼轻张，嘴角绷紧，脸颊肌肉被疾风压出紧张感。"
    if any(keyword in text for keyword in ("笑", "得意", "挑衅")):
        return "眉尾微挑，眼神带一点得意，嘴角轻轻上扬，表情克制但有挑衅感。"
    return "眉眼专注，嘴唇微抿，呼吸收住，脸部肌肉保持紧绷但不过度夸张。"


def _body_performance_for(text: str, fallback: str) -> str:
    if any(keyword in text for keyword in ("飞剑", "剑上", "剑身")) and any(
        keyword in text for keyword in ("踩", "掠", "低空", "呼啸")
    ):
        return "身体重心前压，膝盖微弯抵消飞剑颠簸，一只手护住腰间储物袋，衣摆被速度拉向后方。"
    if "递" in text or "接" in text:
        return "肩膀微微前送，手臂伸出但手指保持犹豫，动作停在即将交接的一瞬。"
    return fallback


def _composition_for(shot_size: str, camera_angle: str, text: str) -> str:
    if "飞剑" in text:
        return f"{shot_size}，{camera_angle}，低机位贴近飞剑飞行路径，前景竹叶虚化，中景飞剑清晰，远景山道被雾气压浅。"
    if "储物袋" in text or "红色十字" in text:
        return f"{shot_size}，{camera_angle}，人物腰侧和储物袋占据视觉中心，红色十字作为最醒目的色彩锚点。"
    return f"{shot_size}，{camera_angle}，主体放在画面视觉中心，前景压出空间感，背景保留剧情环境信息。"


def _motion_arc_for(camera_movement: str, text: str, duration: int) -> str:
    if "飞剑" in text:
        return f"飞剑从雾中切入画面，擦过前景竹叶后向镜头侧前方掠出；{camera_movement}，动作只覆盖当前 {duration} 秒。"
    return f"动作从静止预备推进到关键定格，最后一拍停在情绪或事件最清楚的位置；{camera_movement}，只覆盖当前 {duration} 秒。"


def _director_camera_style_for(text: str) -> str:
    if any(keyword in text for keyword in ("命运", "天命", "时间", "审判", "系统", "秩序", "迷宫", "巨大结构", "宏大")):
        return "诺兰式冷峻空间压迫：用轴线推进、对称纵深、低位稳定推轨和人物/巨大结构的尺度反差表现命运或系统压力。"
    if any(keyword in text for keyword in ("第一次看见", "奇观", "震撼", "巨兽", "巨物", "天门", "仙门", "奇迹", "不可思议")):
        return "斯皮尔伯格式奇观揭示：先拍人物眼神和呼吸反应，再沿视线推近、仰拍或过肩揭示巨大主体，让观众跟着角色一起发现。"
    if any(keyword in text for keyword in ("对称", "走廊", "仪式", "机构", "宫殿", "压迫", "规训")):
        return "库布里克式对称压迫：中央透视、缓慢推轨、刚性站位和冷静构图，让空间本身形成心理压力。"
    if any(keyword in text for keyword in ("悬念", "窥视", "偷看", "暗处", "危险但不知道", "门缝", "背后")):
        return "希区柯克式悬念视角：用主观视线、前景遮挡、物件插入和焦点错位制造信息差；只有心理坠落时才允许希区柯克变焦。"
    if any(keyword in text for keyword in ("雨夜", "霓虹", "巷", "香烟", "擦肩", "暧昧", "孤独", "酒吧")):
        return "王家卫式都市亲密：慢速横移、前景虚化、反光表面和近距离身体调度，让情绪停在未说出口的位置。"
    if any(keyword in text for keyword in ("早餐", "家里", "房间", "书桌", "咖啡", "照顾", "日常", "安静")):
        return "是枝裕和式生活观察：静态或极慢低机位观察，让人物自然进出画面，用手部动作和生活物件承接情绪。"
    if any(keyword in text for keyword in ("风", "雨", "尘", "群像", "决斗", "战场", "竹林", "山林")):
        return "黑泽明式天气动作调度：让风、雨、尘或竹叶参与动作方向，横向运动清楚，群体或对抗关系一眼可读。"
    if any(keyword in text for keyword in ("红", "金", "白", "旗", "阵列", "典礼", "祭祀", "仪仗")):
        return "张艺谋式仪式色块：用正面构图、群体几何和大色块形成视觉秩序，颜色承担情绪和权力含义。"
    if any(keyword in text for keyword in ("告白", "隐忍", "羞愧", "道德", "选择", "克制", "距离")):
        return "李安式克制情绪：用缓慢推拉、身体距离、手和眼神细节表现未说出口的情感与道德压力。"
    if any(keyword in text for keyword in ("调查", "监控", "公司", "会议室", "计划", "计算", "隐藏", "文件")):
        return "芬奇式精密控制：锁定构图、机械式推拉、暗部层次和干净空间线条，表现冷静计算和信息控制。"
    if any(keyword in text for keyword in ("飞行", "天空", "云", "风吹", "森林", "精灵", "生物", "翅膀")):
        return "宫崎骏式飞行与环境呼吸：漂浮跟拍、风带动衣发和云雾，环境像有生命一样回应人物运动。"
    return ""


def _movement_grammar_for(text: str) -> str:
    if any(keyword in text for keyword in ("玉简", "手机", "信", "戒指", "钥匙", "法宝", "丹药", "药瓶", "文件", "计划书")):
        return "道具揭示语法：从道具特写开始，经过手指/指节/材质细节，焦点再转到人物眼神或脸部反应。"
    if any(keyword in text for keyword in ("登场", "出现", "走来", "转身", "露面", "揭示身份")):
        return "人物登场语法：先给背影或侧影，再露出局部五官，最后停到完整正脸或半身身份揭示。"
    if any(keyword in text for keyword in ("逼近", "袭来", "背后", "靠近", "危险", "威胁")):
        return "危险逼近语法：前景先压出威胁，焦点转到人物反应，再沿逃离/撞击路径完成动作。"
    if any(keyword in text for keyword in ("追逐", "飞剑", "飞行", "奔跑", "骑车", "掠过", "赶路")):
        return "追逐/飞行语法：低机位侧前方跟拍，背景形成方向拖影，冲击点可控轻震，结尾停在人物反应。"
    if any(keyword in text for keyword in ("愤怒", "崩溃", "犹豫", "心动", "紧张", "害怕", "震惊", "沉默")):
        return "情绪变化语法：静止或慢推开始，焦点从手、嘴角或下颌转到眼睛，最后以一次呼吸停顿收束。"
    if any(keyword in text for keyword in ("广场", "大殿", "城市", "山门", "校场", "全景", "空间", "环境")):
        return "空间揭示语法：先用高位/远景建立方向，再下降或推到主体，最后锁定人物在空间里的位置。"
    if any(keyword in text for keyword in ("悬念", "窥视", "门缝", "窗后", "暗处", "遮挡")):
        return "悬念窥视语法：前景遮挡或主观视角先行，rack focus 到隐藏信息，揭示前保留半拍。"
    return "基础连续调度语法：先建立人物、道具、环境位置，中段跟随动作路径，结尾停在下一镜可顺接的状态。"


def _cinematic_language_for(shot_size: str, camera_angle: str, text: str) -> str:
    style = _director_camera_style_for(text)
    if "飞剑" in text or "御剑" in text:
        base = f"{shot_size}结合{camera_angle}制造速度和高度感，用前景竹叶、背景横向拖影和主体追焦引导视线从飞剑移动到人物。"
        return f"{style}{base}" if style else base
    if any(keyword in text for keyword in ("惊", "愣", "僵", "发现", "意识到", "反应")):
        base = f"{shot_size}突出人物认知变化，先压住环境信息，再用轻微推近和焦点转移把注意力落到眼神、嘴角和手部。"
        return f"{style}{base}" if style else base
    base = f"{shot_size}服务当前情绪与叙事信息，先交代主体关系，再用{camera_angle}和画面层次把视线引到关键动作。"
    return f"{style}{base}" if style else base


def _camera_blocking_for(text: str) -> str:
    if "飞剑" in text or "御剑" in text:
        return "主体沿画面纵深或斜线运动，飞剑/载具保持在人物脚下中轴，前景环境快速掠过，中景人物稳定可读。"
    return "主体、道具和环境按前中后三层调度，人物动作不遮挡关键道具，镜头始终保留可读的脸部或手部信息。"


def _movement_design_for(camera_movement: str, text: str) -> str:
    movement_grammar = _movement_grammar_for(text)
    if any(keyword in text for keyword in ("突", "扑", "撞", "爆", "追", "冲")):
        return (
            f"{movement_grammar}运镜以{camera_movement}为基础，起点先压住主体和危险来源的相对位置，"
            "随后跟随攻击/冲撞方向快速推进；冲击点允许短促震动或甩动，焦点从危险物转到人物脸和手，"
            "后半段明显减速，停在人物刚完成反应但危险仍未解除的状态。"
        )
    return (
        f"{movement_grammar}运镜以{camera_movement}为基础，起点先建立人物、道具、环境的空间关系，"
        "中段随人物动作路径微推或轻摇，焦点从关键道具/手部转到眼神和脸部，"
        "速度从慢到稳，结尾停在最能承接下一镜的表情、手势或道具位置。"
    )


def _editing_strategy_for(text: str) -> str:
    if any(keyword in text for keyword in ("倒计时", "剩余", "最后", "追逐", "追来", "赶时间", "半炷香", "限时")):
        return "加速节奏蒙太奇：用逐渐变短的动作插入和同向运动切点强化倒计时/追逐压力，但本 clip 只完成当前动作小节，结尾保留反应停顿。"
    has_parallel_space = any(keyword in text for keyword in ("与此同时", "另一边", "另一头", "两边", "两地")) or (
        "同时" in text and any(keyword in text for keyword in ("两处", "两地", "两边", "一边", "另一"))
    )
    if has_parallel_space:
        if any(keyword in text for keyword in ("逼近", "赶到", "相遇", "撞上", "救", "危机", "危险", "袭来")):
            return "交叉蒙太奇：两条同时发生的行动线相互逼近，用方向一致的切点制造救援/危机临近感，结尾停在碰撞前一拍。"
        return "平行蒙太奇：两处同时发生的信息交替呈现，保持各自空间清楚，不制造误会成同一地点。"
    if any(keyword in text for keyword in ("转眼", "片刻后", "不知过了多久", "跳过", "省略", "过程不表", "已是", "终于")):
        return "省略蒙太奇：跳过观众能自行补全的中间过程，只保留动作起点、结果和一个最有信息量的过渡插入。"
    if any(keyword in text for keyword in ("赶路", "修炼", "炼丹", "寻找", "搜索", "调查", "反复", "一连", "整夜", "数日")):
        return "时间压缩蒙太奇：用少量过程插入压缩长时间动作，保留最关键的起因、动作峰值和结果，不跨入下一剧情事件。"
    if any(keyword in text for keyword in ("回忆", "想起", "记起", "脑海", "幻觉", "噩梦", "梦见", "内心", "心里")):
        return "心理/回忆蒙太奇：用短促记忆碎片或主观画面表现内心压力，必须回到当前人物表情收束，不把回忆当成真实跳场。"
    if any(keyword in text for keyword in ("预感", "预兆", "伏笔", "命运", "天命", "碎片", "裂隙", "暗线", "血红眼睛", "窥视")):
        return "象征/预兆蒙太奇：用发光物、裂纹、眼睛、风声或环境异动短暂暗示后续危险，保持隐蔽，不抢走当前主动作。"
    if any(keyword in text for keyword in ("反差", "一边", "却", "而他", "而她", "穷", "富", "仙界", "凡间", "落魄", "豪门")):
        return "对比蒙太奇：把身份、处境或情绪相反的画面对切，突出反差意义；每个插入只保留一个清楚视觉点。"
    if any(keyword in text for keyword in ("悲", "失落", "沉默", "羞愧", "心碎", "怔住", "余韵", "愣住")):
        return "减速蒙太奇：延长呼吸、眼神和环境余波，用更慢切点保留情绪下沉，不急着进入下一事件。"
    if any(keyword in text for keyword in ("雷光", "刀光", "剑光", "瞳孔", "炸裂", "轰鸣", "碎裂", "冲击", "眼睛特写")):
        return "冲击蒙太奇：用雷光/刃光/瞳孔/碎裂等极短高冲击插入强化瞬间打击，随后立刻回到当前主动作，不扩写成多事件。"
    if any(keyword in text for keyword in ("突然", "扑", "爆", "撞", "袭")):
        return "单镜为主，冲击点可用短促节奏停顿，不硬切到无关角度；如需衔接下一镜，用动作方向顺切。"
    return "单镜连续呈现为主，不做复杂剪辑；结尾保留半拍停顿，方便与下一镜顺切或情绪承接。"


def _transition_plan_for(text: str) -> str:
    if "飞剑" in text or "御剑" in text:
        return "承接上一镜的运动方向，结尾保持同向速度或视线方向，下一镜可用动作顺切继续。"
    return "从上一镜的情绪或视线方向自然承接，结尾停在可顺切的表情、手势或道具状态。"


def _micro_performance_for(facial: str, body: str, text: str) -> str:
    base = "脸部、眼神、嘴角、肩颈、手指和身体重心都要有连续细微变化。"
    if facial or body:
        return f"{base}面部：{_excerpt(facial, 90)}；身体：{_excerpt(body, 110)}"
    if any(keyword in text for keyword in ("急", "紧", "怕", "惊", "怒")):
        return f"{base}眉头逐渐压低，眼神从搜索到锁定，嘴唇收紧，手指扣紧道具或衣料，肩颈微僵。"
    return f"{base}动作不僵硬，呼吸、眨眼、手腕和衣摆随情绪自然变化。"


def _video_motion_for(camera_movement: str, text: str) -> str:
    if "飞剑" in text:
        return f"竹叶被飞剑风压向两侧压弯，露珠飞散，剑尾青光断续拖出短尾迹，雾气被切开后缓慢合拢；镜头{camera_movement}。"
    return f"人物呼吸、衣摆、手指和环境细节保持细微运动，镜头{camera_movement}，动作不要跳到下一剧情。"


def _performance_for(dramatic_value: str, shot_size: str, content_format: str) -> str:
    value = dramatic_value.lower()
    if content_format == CONTENT_FORMAT_AD:
        return "表演服务转化：情绪反应要直接、明确，避免文学化铺垫拖慢前三秒。"
    if content_format == CONTENT_FORMAT_NARRATED:
        return "画面动作服务旁白信息点，可用回望、停顿、环境反应或 B-roll 承接解说。"
    if content_format == CONTENT_FORMAT_INTERACTIVE and any(keyword in value for keyword in ("choice", "gameplay")):
        return "保留玩家视角的反应空间，动作结束处要能自然接选择、玩法入口或回归剧情。"
    if content_format == CONTENT_FORMAT_INTERACTIVE and any(keyword in value for keyword in ("hook", "cliffhanger")):
        return "表演要在最后一拍留下未完成感，让新人物、新事件或下一选择自然冒出来。"
    if any(keyword in value for keyword in ("conflict", "danger", "tension", "危机", "冲突", "紧张")):
        return "呼吸、眼神和停顿要有压力感，动作不要过快。"
    if shot_size in {"特写", "近景"}:
        return "用克制微表情推动情绪，重点捕捉眼神、呼吸和手部细节。"
    return "表演收敛自然，动作路径清晰，给观众留出理解空间。"


def _normal_image_roles(duration_seconds: int) -> list[str]:
    roles = ["start_image", "review_frame"]
    if duration_seconds >= MIN_VIDEO_DURATION_SECONDS:
        roles.insert(1, "guide_reference")
    return roles


def _normal_reference_strategy() -> str:
    return "默认先用 start_image 生成；guide_reference / asset_reference 仅在脸、场景、道具或风格需要强化时追加。"


def _edit_note_for(content_format: str) -> str:
    if content_format == CONTENT_FORMAT_AD:
        return "广告节奏顺切，前三秒必须有钩子，每个镜头都服务痛点、反转或转化。"
    if content_format == CONTENT_FORMAT_NARRATED:
        return "剪辑跟随旁白信息点，画面可用插入/B-roll 承接，不强求连续动作。"
    if content_format == CONTENT_FORMAT_INTERACTIVE:
        return "同一剧情动作内顺切，保留选择点、玩法入口或回归剧情的边界。"
    return "同一剧情动作内顺切，保持角色空间关系连续。"


def _boundary_shot(episode: int, shot_number: int, micro: dict[str, Any], title: str) -> dict[str, Any]:
    interaction_role = str(micro.get("interaction_role") or micro.get("dramatic_value") or "")
    return {
        "shot_id": f"E{episode}S{shot_number:02d}",
        "source_micro_id": str(micro.get("micro_id") or ""),
        "title": title,
        "source_excerpt": _excerpt(micro.get("source_excerpt") or title, 160),
        "duration_seconds": 0,
        "shot_size": "边界标记",
        "camera_angle": "不适用",
        "camera_movement": "剧情切点",
        "screen_subject": title,
        "action": "作为玩法入口或回归剧情边界，不直接生成视频；后续从这里另起镜头。",
        "performance": "无需演员表演；用于标记交互段落与剧情段落的分界。",
        "lighting": "沿用前后镜头氛围。",
        "edit_note": "这里是分镜结尾点，可接玩法画面、回归剧情或新事件。",
        "image_roles": ["review_frame"],
        "reference_strategy": "仅用于审核结构，不提交视频生成。",
        "interaction_role": interaction_role,
        "choice_point_id": str(micro.get("choice_point_id") or ""),
        "choice_options": list(micro.get("choice_options") or []),
        "is_generation_boundary": True,
    }


def build_director_shot_plan_from_story_beats(story_beats: dict[str, Any]) -> dict[str, Any]:
    """Build a director-shot plan from ``story_beats.json`` data."""
    story_beats = normalize_story_beat_plan_for_director(story_beats)
    episode = _as_int(story_beats.get("episode"), 1)
    content_format = str(story_beats.get("content_format") or DEFAULT_CONTENT_FORMAT)
    template = template_summary(content_format)
    content_format = template["content_format"]
    project_first_person = _project_prefers_first_person(story_beats)
    groups: list[dict[str, Any]] = []
    shot_number = 1

    for beat_index, beat in enumerate(story_beats.get("beats") or [], start=1):
        beat_id = str(beat.get("beat_id") or f"B{beat_index:02d}")
        group_shots: list[dict[str, Any]] = []
        micro_beats = [micro for micro in beat.get("micro_beats") or [] if isinstance(micro, dict)]
        beat_context = _beat_context_text(beat)
        for micro_index, micro in enumerate(micro_beats, start=1):
            previous_text = _text_for_micro(micro_beats[micro_index - 2]) if micro_index > 1 else ""
            next_text = _text_for_micro(micro_beats[micro_index]) if micro_index < len(micro_beats) else ""
            dramatic_value = str(micro.get("dramatic_value") or "")
            interaction_role = str(micro.get("interaction_role") or "")
            choice_point_id = str(micro.get("choice_point_id") or beat.get("choice_point_id") or "")
            title = _excerpt(micro.get("title") or beat.get("title") or f"镜头 {shot_number}", 42)
            raw_duration = _as_int(micro.get("estimated_seconds"), MIN_VIDEO_DURATION_SECONDS)

            if dramatic_value == "boundary_marker" or is_interactive_boundary(interaction_role) or raw_duration <= 0:
                group_shots.append(_boundary_shot(episode, shot_number, micro, title))
                shot_number += 1
                continue

            durations = _split_duration(raw_duration)
            for duration in durations:
                shot_size, camera_angle, camera_movement = _shot_profile(
                    dramatic_value,
                    micro_index - 1,
                    content_format,
                )
                source_text = _full_source_excerpt(micro.get("source_excerpt") or title)
                director_context = _excerpt(micro.get("director_context") or "", 160)
                context_for_inference = " ".join(
                    item for item in [previous_text, source_text, next_text, beat_context, director_context] if item
                )
                part_title = title
                performance = _performance_for(dramatic_value, shot_size, content_format)
                lighting = _lighting_for(context_for_inference)
                environment = _infer_environment(context_for_inference)
                characters = _infer_characters(context_for_inference)
                props = _infer_props(context_for_inference)
                facial_performance = _facial_performance_for(context_for_inference)
                body_performance = _body_performance_for(context_for_inference, performance)
                composition = _composition_for(shot_size, camera_angle, context_for_inference)
                cinematic_language = _cinematic_language_for(shot_size, camera_angle, context_for_inference)
                camera_blocking = _camera_blocking_for(context_for_inference)
                movement_design = _movement_design_for(camera_movement, context_for_inference)
                editing_strategy = _editing_strategy_for(context_for_inference)
                transition_plan = _transition_plan_for(context_for_inference)
                micro_performance = _micro_performance_for(facial_performance, body_performance, context_for_inference)
                motion_arc = _motion_arc_for(camera_movement, context_for_inference, duration)
                video_motion = _video_motion_for(camera_movement, context_for_inference)
                shot = {
                        "shot_id": f"E{episode}S{shot_number:02d}",
                        "source_micro_id": str(micro.get("micro_id") or f"{beat_id}.{micro_index}"),
                        "title": part_title,
                        "source_excerpt": source_text,
                        "duration_seconds": duration,
                        "shot_size": shot_size,
                        "camera_angle": camera_angle,
                        "camera_movement": camera_movement,
                        "screen_subject": title,
                        "action": f"{source_text}；画面停在最有动作张力的一帧，清楚交代主体、道具和空间关系。",
                        "visible_event": source_text,
                        "main_subject": title,
                        "environment": environment,
                        "characters": characters,
                        "props": props,
                        "emotional_subtext": _excerpt(micro.get("dramatic_value") or beat.get("story_function"), 80),
                        "facial_performance": facial_performance,
                        "body_performance": body_performance,
                        "prop_interaction": "道具必须清楚参与动作，不作为背景摆件；关键外形、材质、标识或文字信息要可辨认。"
                        if props
                        else "",
                        "environment_reaction": "光线、衣摆、空气、桌面物件或背景元素随动作产生细微反应，增强空间真实感。",
                        "composition": composition,
                        "cinematic_language": cinematic_language,
                        "camera_blocking": camera_blocking,
                        "movement_design": movement_design,
                        "editing_strategy": editing_strategy,
                        "transition_plan": transition_plan,
                        "micro_performance": micro_performance,
                        "start_state": source_text,
                        "end_state": f"{source_text}后的半拍，主体仍在画面中心，动作没有进入下一剧情。",
                        "motion_arc": motion_arc,
                        "keyframe_start": source_text,
                        "video_motion": video_motion,
                        "viewer_effect": _excerpt(beat.get("story_function") or beat.get("summary") or "", 100),
                        "color_palette": "青灰晨雾、竹叶冷绿、法器暗金或青铁色，红色十字作为局部高饱和视觉锚点。"
                        if "红色十字" in source_text
                        else "遵守项目画风，低饱和电影级色调，主体清楚，背景不过度抢戏。",
                        "performance": performance,
                        "lighting": lighting,
                        "edit_note": _edit_note_for(content_format)
                        + (f" 导演上下文：{director_context}。" if director_context else ""),
                        "image_roles": _normal_image_roles(duration),
                        "reference_strategy": _normal_reference_strategy(),
                        "interaction_role": interaction_role,
                        "choice_point_id": choice_point_id,
                        "choice_options": list(micro.get("choice_options") or []),
                        "is_generation_boundary": False,
                    }
                if _is_flying_sword_lead_in(source_text, next_text, beat_context):
                    _apply_flying_sword_lead_in_fields(shot, source_text=source_text, next_text=next_text)
                elif _is_flying_sword_rider_reveal(previous_text, source_text, beat_context):
                    _apply_flying_sword_rider_reveal_fields(
                        shot, source_text=source_text, previous_text=previous_text
                    )
                elif _should_apply_first_person_pov(context_for_inference, project_first_person=project_first_person):
                    _apply_first_person_pov_fields(shot, source_text=source_text, context=context_for_inference)
                group_shots.append(shot)
                shot_number += 1

        group_duration = sum(int(shot.get("duration_seconds") or 0) for shot in group_shots)
        groups.append(
            {
                "group_id": f"SG{beat_index:02d}",
                "source_beat_id": beat_id,
                "title": _excerpt(beat.get("title") or f"镜头组 {beat_index}", 42),
                "purpose": _excerpt(beat.get("story_function") or beat.get("summary") or "推进剧情节拍", 80),
                "duration_seconds": group_duration,
                "shots": group_shots,
            }
        )

    payload = {
        "schema_version": 1,
        "episode": episode,
        "content_format": content_format,
        "template_name": template["label"],
        "template_focus": template["focus"],
        "format_profile": template,
        "source_story_beat_count": len(story_beats.get("beats") or []),
        "total_duration_seconds": sum(int(group.get("duration_seconds") or 0) for group in groups),
        "choice_points": list(story_beats.get("choice_points") or []),
        "shot_groups": groups,
    }
    return DirectorShotPlanModel.model_validate(payload).model_dump()


def _director_system_prompt() -> str:
    return """你是影视动画导演分镜模型。你的任务不是摘要小说，而是把剧情节拍扩写成可生成图片和视频的导演镜头设计。

必须遵守：
1. 输出严格 JSON，符合给定 schema，不要 Markdown。
2. 保留每个 shot 的 source_micro_id 和 source_excerpt，不能丢剧情依据。
3. 每个普通 shot 不得低于 5 秒；复杂动作可拆成多个 shot，但每个 shot 仍必须 >=5 秒。
4. 不能孤立理解单个 micro_beat；必须结合同一 beat 的 summary/source_excerpt 和相邻 micro_beat 推断真实画面主体。
5. 如果当前 micro_beat 只写道具或环境，但下一拍说明人物正在使用它，要把当前镜头设计成“道具引出人物”的视觉揭示，不要拍成空道具。
6. 把抽象情绪扩写成可见表演：眉毛、眼睛、鼻子、嘴、脸部肌肉、肩膀、手臂、手指、身体重心；每项写具体画面，不要空泛。
7. 必须像称职导演一样写镜头语言：cinematic_language、camera_blocking、movement_design、editing_strategy、transition_plan、micro_performance 都要具体。
8. movement_design 要写动作从哪里到哪里、镜头从哪里到哪里、焦点如何转移、速度如何变化；不能只写“推近/跟拍/摇镜”。
9. editing_strategy 要判断是否单镜到底、动作顺切、前景遮挡转场、match cut、whip pan、反应停顿或某一种具体蒙太奇；只有剧情需要时才用蒙太奇或希区柯克变焦，不要乱塞。
10. 蒙太奇必须选择具体类型并说明理由：时间压缩蒙太奇=赶路/修炼/炼丹/调查/反复过程；平行蒙太奇=两地同时发生；交叉蒙太奇=两条同时行动线逼近救援/危机/碰撞；省略蒙太奇=跳过显而易见过程只保留结果；心理/回忆蒙太奇=记忆、恐惧、幻想、内心压力；隐喻/象征蒙太奇=命运、主题、物象、天气、光、裂纹；对比蒙太奇=身份/处境/情绪反差；预兆蒙太奇=未来危险、暗线、窥视、能力觉醒；加速节奏蒙太奇=追逐/倒计时/战斗升级；减速蒙太奇=失落/心碎/余韵/安静顿悟；冲击蒙太奇=攻击、雷光、刀光、眼睛特写等短促冲击。
11. 禁止只写“使用蒙太奇/轻量蒙太奇”。普通对话和单一普通动作不用蒙太奇，写单镜连续、动作顺切或反应 hold。
12. 希区柯克变焦/dolly zoom 只用于突然心理坠落、空间眩晕、身份崩塌或不可能真相，不可装饰性使用。
13. 必须理解导演风格化运镜，但不能只写导演名字：诺兰式=冷峻轴线/空间压迫/尺度反差；斯皮尔伯格式=先人物反应再奇观揭示；库布里克式=中央透视/对称压迫；希区柯克式=主观视角/信息差/悬念遮挡；王家卫式=雨夜霓虹/慢横移/前景虚化/暧昧距离；是枝裕和式=生活流静观/自然调度；黑泽明式=天气参与动作/横向调度；张艺谋式=仪式色块/群体几何；李安式=克制推拉/身体距离；芬奇式=机械推拉/锁定构图/暗部层次；宫崎骏式=飞行漂浮/风和环境呼吸。
14. 如果使用上述风格，cinematic_language 必须写“为什么选”，movement_design 必须写成可执行运镜路径：起点、终点、主体路径、焦点转移、速度变化、结尾停点；禁止只写“诺兰运镜/斯皮尔伯格运镜”。
15. 基础运镜语法要按剧情选择：道具揭示=道具特写→手指→眼神；人物登场=背影/侧影→局部脸→完整揭示；危险逼近=前景威胁→人物反应→逃离/撞击路径；追逐/飞行=低机位侧前方跟拍→背景拖影→可控轻震→反应停顿；情绪变化=静止/慢推→手/嘴角/下颌到眼睛→呼吸停顿；空间揭示=高位/远景→下降/推到主体→锁定方位；悬念窥视=遮挡/主观视角→rack focus→揭示前停半拍。
16. micro_performance 要写眉眼、嘴角、下颌、呼吸、肩颈、手指、身体重心的连续细微变化。
17. 把动作扩写成 start_state、end_state、motion_arc、video_motion；每项 20-80 字。
18. 把画面扩写成 visible_event、main_subject、environment、composition、lighting、color_palette；每项 20-100 字。
19. 保持项目已选画风和当前文本类型，不要跨项目套用专有世界观、人物名、道具名或色调模板；避免空泛镜头词。
20. 玩法入口、选择点、回归剧情等边界节点保留为 review_frame，不生成视频。
21. 只输出本批 story_beats 对应内容，严禁补全整集，严禁解释。
"""


def _director_user_prompt(story_beats: dict[str, Any]) -> str:
    return "\n".join(
        [
            "请根据下面这一小批 story_beats.json 生成导演分镜 director_shots.json。",
            "导演分镜要服务后续关键帧和视频生成，必须把小说文本扩写成可见画面、演员表演和镜头运动。",
            "不要只写“呈现：原文”。不要使用大量重复的泛化镜头词。",
            "重要：生成每个 shot 时，必须阅读当前 micro_beat 的前一拍、后一拍和所属 beat summary；允许重组小说信息为更清楚的电影揭示顺序。",
            "例：当前只写飞剑掠过、下一拍写男主踩在剑上，则当前镜头应是低机位跟拍飞剑并局部露出男主脚/腿/袍角，而不是只有一柄空飞剑。",
            "顶层必须包含 shot_groups 数组；每个 group 必须包含 shots 数组。",
            "不要把 shots 放在顶层。如果你想先写平铺镜头，也必须包进 shot_groups[0].shots。",
            "输出字段合同：每个 shot 必须包含 shot_id/source_micro_id/title/source_excerpt/duration_seconds/shot_size/camera_angle/camera_movement/screen_subject/action/visible_event/main_subject/environment/characters/props/emotional_subtext/facial_performance/body_performance/prop_interaction/environment_reaction/composition/cinematic_language/camera_blocking/movement_design/editing_strategy/transition_plan/micro_performance/start_state/end_state/motion_arc/keyframe_start/video_motion/viewer_effect/color_palette/performance/lighting/edit_note/image_roles/reference_strategy/interaction_role/choice_point_id/choice_options/is_generation_boundary。",
            "每个 micro_beat 通常生成 1 个 shot；不要为了凑时长拆出 1/2、2/2 这种重复镜头。只有同一动作明显超过 15 秒才拆多个 shot，拆分后每个 shot 的 duration_seconds 都必须 >=5，且每条必须有不同的动作阶段。每个字段短而具体，禁止长篇解释。",
            "",
            json.dumps(story_beats, ensure_ascii=False),
        ]
    )


def _story_beat_batches(story_beats: dict[str, Any], *, batch_size: int = 1) -> list[dict[str, Any]]:
    """Split story beats into small model-friendly payloads."""
    beats = [beat for beat in story_beats.get("beats") or [] if isinstance(beat, dict)]
    batches: list[dict[str, Any]] = []
    for start in range(0, len(beats), max(1, batch_size)):
        batch_beats = beats[start : start + batch_size]
        batch = dict(story_beats)
        batch["beats"] = batch_beats
        batch["source_story_beat_count"] = len(batch_beats)
        batches.append(batch)
    return batches


def _stringify_model_field(value: Any, limit: int = 260) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return _excerpt(value, limit)
    if isinstance(value, list):
        return _excerpt("，".join(_stringify_model_field(item, limit) for item in value if item), limit)
    if isinstance(value, dict):
        if value.get("description"):
            return _excerpt(value["description"], limit)
        parts = []
        for key, item in value.items():
            rendered = _stringify_model_field(item, limit)
            if rendered:
                parts.append(f"{key}：{rendered}")
        return _excerpt("；".join(parts), limit)
    return _excerpt(str(value), limit)


def _normalize_model_shot(raw: dict[str, Any], fallback_shot: dict[str, Any] | None, episode: int, index: int) -> dict[str, Any]:
    fallback_shot = fallback_shot or {}
    is_boundary = bool(raw.get("is_generation_boundary") or fallback_shot.get("is_generation_boundary") or False)
    raw_duration = _as_int(
        raw.get("duration_seconds"),
        _as_int(
            fallback_shot.get("duration_seconds"),
            0 if is_boundary else MIN_VIDEO_DURATION_SECONDS,
        ),
    )
    duration_seconds = 0 if is_boundary or raw_duration <= 0 else coerce_video_duration(raw_duration)
    main_subject = raw.get("main_subject")
    environment = raw.get("environment")
    composition = raw.get("composition")
    video_motion = raw.get("video_motion")
    facial = raw.get("facial_performance") or (
        (main_subject or {}).get("facial_performance") if isinstance(main_subject, dict) else ""
    )
    body = raw.get("body_performance") or (
        (main_subject or {}).get("body_performance") if isinstance(main_subject, dict) else ""
    )
    camera_angle = raw.get("camera_angle") or (
        (composition or {}).get("camera_angle") if isinstance(composition, dict) else ""
    )
    camera_movement = raw.get("camera_movement") or (
        (video_motion or {}).get("camera_motion") if isinstance(video_motion, dict) else ""
    )
    shot_size = raw.get("shot_size") or (
        (composition or {}).get("framing") if isinstance(composition, dict) else ""
    )
    return {
        "shot_id": fallback_shot.get("shot_id") or raw.get("shot_id") or f"E{episode}S{index:02d}",
        "source_micro_id": raw.get("source_micro_id") or fallback_shot.get("source_micro_id") or "",
        "title": _excerpt(raw.get("title") or raw.get("visible_event") or fallback_shot.get("title") or f"镜头 {index}", 80),
        "source_excerpt": _excerpt(raw.get("source_excerpt") or fallback_shot.get("source_excerpt") or "", 220),
        "duration_seconds": duration_seconds,
        "shot_size": _stringify_model_field(shot_size or fallback_shot.get("shot_size") or "中景", 80),
        "camera_angle": _stringify_model_field(camera_angle or fallback_shot.get("camera_angle") or "平视", 80),
        "camera_movement": _stringify_model_field(camera_movement or fallback_shot.get("camera_movement") or "轻微推进", 120),
        "screen_subject": _stringify_model_field(raw.get("screen_subject") or raw.get("visible_event") or main_subject or fallback_shot.get("screen_subject"), 220),
        "action": _stringify_model_field(raw.get("action") or raw.get("visible_event") or fallback_shot.get("action"), 260),
        "visible_event": _stringify_model_field(raw.get("visible_event") or fallback_shot.get("visible_event"), 300),
        "main_subject": _stringify_model_field(main_subject or fallback_shot.get("main_subject"), 220),
        "environment": _stringify_model_field(environment or fallback_shot.get("environment"), 220),
        "characters": list(raw.get("characters") or fallback_shot.get("characters") or []),
        "props": list(raw.get("props") or fallback_shot.get("props") or []),
        "emotional_subtext": _stringify_model_field(raw.get("emotional_subtext") or raw.get("dramatic_function") or fallback_shot.get("emotional_subtext"), 160),
        "facial_performance": _stringify_model_field(facial, 220),
        "body_performance": _stringify_model_field(body, 260),
        "prop_interaction": _stringify_model_field(raw.get("prop_interaction") or fallback_shot.get("prop_interaction"), 180),
        "environment_reaction": _stringify_model_field(raw.get("environment_reaction") or raw.get("effects_motion") or fallback_shot.get("environment_reaction"), 220),
        "composition": _stringify_model_field(composition or fallback_shot.get("composition"), 260),
        "cinematic_language": _stringify_model_field(raw.get("cinematic_language") or fallback_shot.get("cinematic_language"), 260),
        "camera_blocking": _stringify_model_field(raw.get("camera_blocking") or fallback_shot.get("camera_blocking"), 240),
        "movement_design": _stringify_model_field(raw.get("movement_design") or fallback_shot.get("movement_design"), 260),
        "editing_strategy": _stringify_model_field(raw.get("editing_strategy") or fallback_shot.get("editing_strategy"), 220),
        "transition_plan": _stringify_model_field(raw.get("transition_plan") or fallback_shot.get("transition_plan"), 180),
        "micro_performance": _stringify_model_field(raw.get("micro_performance") or fallback_shot.get("micro_performance"), 300),
        "start_state": _stringify_model_field(raw.get("start_state") or fallback_shot.get("start_state"), 220),
        "end_state": _stringify_model_field(raw.get("end_state") or fallback_shot.get("end_state"), 220),
        "motion_arc": _stringify_model_field(raw.get("motion_arc") or fallback_shot.get("motion_arc"), 260),
        "keyframe_start": _stringify_model_field(raw.get("keyframe_start") or raw.get("start_state") or raw.get("visible_event") or fallback_shot.get("keyframe_start"), 260),
        "video_motion": _stringify_model_field(video_motion or raw.get("motion_arc") or fallback_shot.get("video_motion"), 300),
        "viewer_effect": _stringify_model_field(raw.get("viewer_effect") or raw.get("dramatic_function") or fallback_shot.get("viewer_effect"), 160),
        "color_palette": _stringify_model_field(raw.get("color_palette") or fallback_shot.get("color_palette"), 120),
        "performance": _stringify_model_field(raw.get("performance") or facial or body or fallback_shot.get("performance"), 260),
        "lighting": _stringify_model_field(raw.get("lighting") or fallback_shot.get("lighting") or "柔和电影级布光。", 180),
        "edit_note": _stringify_model_field(raw.get("edit_note") or fallback_shot.get("edit_note") or "同一剧情动作内顺切。", 160),
        "image_roles": list(raw.get("image_roles") or fallback_shot.get("image_roles") or ["start_image", "guide_reference", "review_frame"]),
        "reference_strategy": _stringify_model_field(raw.get("reference_strategy") or fallback_shot.get("reference_strategy") or _normal_reference_strategy(), 180),
        "interaction_role": _stringify_model_field(raw.get("interaction_role") or fallback_shot.get("interaction_role"), 80),
        "choice_point_id": _stringify_model_field(raw.get("choice_point_id") or fallback_shot.get("choice_point_id"), 80),
        "choice_options": list(raw.get("choice_options") or fallback_shot.get("choice_options") or []),
        "is_generation_boundary": is_boundary,
    }


def _normalize_model_director_plan(raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    episode = int(fallback.get("episode") or 1)
    if not raw.get("shot_groups") and isinstance(raw.get("shots"), list):
        fallback_groups = fallback.get("shot_groups") or []
        fallback_shots = fallback_groups[0].get("shots", []) if fallback_groups else []
        raw_shots = [
            _normalize_model_shot(shot, fallback_shots[index] if index < len(fallback_shots) else None, episode, index + 1)
            for index, shot in enumerate(raw["shots"])
            if isinstance(shot, dict)
        ]
        raw["shot_groups"] = [
            {
                "group_id": fallback_groups[0].get("group_id", "SG01") if fallback_groups else "SG01",
                "source_beat_id": fallback_groups[0].get("source_beat_id", "B01") if fallback_groups else "B01",
                "title": raw.get("title") or (fallback_groups[0].get("title") if fallback_groups else "导演分镜"),
                "purpose": raw.get("template_focus") or (fallback_groups[0].get("purpose") if fallback_groups else "推进剧情"),
                "duration_seconds": sum(int(shot.get("duration_seconds") or 0) for shot in raw_shots),
                "shots": raw_shots,
            }
        ]
    else:
        fallback_groups = fallback.get("shot_groups") or []
        fallback_shots_by_id = {
            str(shot.get("source_micro_id") or shot.get("shot_id") or ""): shot
            for group in fallback_groups
            for shot in group.get("shots") or []
        }
        for group_index, group in enumerate(raw.get("shot_groups") or []):
            if not isinstance(group, dict):
                continue
            fallback_group = fallback_groups[group_index] if group_index < len(fallback_groups) else {}
            group["group_id"] = group.get("group_id") or fallback_group.get("group_id") or f"SG{group_index + 1:02d}"
            group["source_beat_id"] = group.get("source_beat_id") or fallback_group.get("source_beat_id") or ""
            group["title"] = group.get("title") or group.get("group_title") or fallback_group.get("title") or "导演分镜"
            group["purpose"] = group.get("purpose") or fallback_group.get("purpose") or "推进剧情"
            normalized = []
            for index, shot in enumerate(group.get("shots") or [], start=1):
                if isinstance(shot, dict):
                    key = str(shot.get("source_micro_id") or shot.get("shot_id") or "")
                    normalized.append(_normalize_model_shot(shot, fallback_shots_by_id.get(key), episode, index))
            group["shots"] = normalized
            group["duration_seconds"] = sum(int(shot.get("duration_seconds") or 0) for shot in normalized)
    return raw


def _renumber_director_plan(plan: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    """Renumber merged model output into stable global SG/S ids."""
    episode = int(fallback.get("episode") or plan.get("episode") or 1)
    shot_number = 1
    groups: list[dict[str, Any]] = []
    for group_index, group in enumerate(plan.get("shot_groups") or [], start=1):
        if not isinstance(group, dict):
            continue
        next_group = dict(group)
        next_group["group_id"] = f"SG{group_index:02d}"
        shots: list[dict[str, Any]] = []
        for shot in next_group.get("shots") or []:
            if not isinstance(shot, dict):
                continue
            next_shot = dict(shot)
            next_shot["shot_id"] = f"E{episode}S{shot_number:02d}"
            shots.append(next_shot)
            shot_number += 1
        next_group["shots"] = shots
        next_group["duration_seconds"] = sum(int(shot.get("duration_seconds") or 0) for shot in shots)
        groups.append(next_group)
    plan["shot_groups"] = groups
    plan["schema_version"] = fallback["schema_version"]
    plan["episode"] = fallback["episode"]
    plan["content_format"] = plan.get("content_format") or fallback["content_format"]
    plan["template_name"] = plan.get("template_name") or fallback["template_name"]
    plan["template_focus"] = plan.get("template_focus") or fallback["template_focus"]
    plan["format_profile"] = plan.get("format_profile") or fallback["format_profile"]
    plan["source_story_beat_count"] = fallback["source_story_beat_count"]
    plan["choice_points"] = fallback["choice_points"]
    plan["total_duration_seconds"] = sum(int(group.get("duration_seconds") or 0) for group in groups)
    return plan


async def build_director_shot_plan_from_story_beats_with_text_model(
    story_beats: dict[str, Any],
    *,
    project_name: str,
) -> dict[str, Any]:
    """Build director shots with the configured text model, falling back per beat.

    Full episodes can exceed model/proxy limits and silently degrade into the
    deterministic template. Generate small beat batches, then merge + renumber.
    """
    story_beats = normalize_story_beat_plan_for_director(story_beats)
    fallback = build_director_shot_plan_from_story_beats(story_beats)
    try:
        generator = await TextGenerator.create(TextTaskType.DIRECTOR_SHOTS, project_name=project_name)
    except Exception as exc:
        logger.warning("导演分镜文本模型初始化失败，回退到规则模板: %s", exc)
        return fallback

    merged_groups: list[dict[str, Any]] = []
    fallback_groups = fallback.get("shot_groups") or []
    consecutive_failures = 0
    for batch_index, batch in enumerate(_story_beat_batches(story_beats, batch_size=1), start=1):
        batch_fallback = build_director_shot_plan_from_story_beats(batch)
        if consecutive_failures >= DIRECTOR_SHOT_MODEL_FAILURE_BREAKER:
            fallback_group = fallback_groups[batch_index - 1] if batch_index - 1 < len(fallback_groups) else None
            if fallback_group:
                merged_groups.append(fallback_group)
            else:
                merged_groups.extend(batch_fallback.get("shot_groups") or [])
            continue
        try:
            result = await asyncio.wait_for(
                generator.generate(
                    TextGenerationRequest(
                        system_prompt=_director_system_prompt(),
                        prompt=_director_user_prompt(batch),
                        max_output_tokens=3000,
                    ),
                    project_name=project_name,
                ),
                timeout=DIRECTOR_SHOT_MODEL_TIMEOUT_SECONDS,
            )
            raw = _normalize_model_director_plan(parse_model_json_object(result.text), batch_fallback)
            batch_plan = DirectorShotPlanModel.model_validate(raw).model_dump()
            if not batch_plan.get("shot_groups"):
                raise ValueError("director_shots model returned empty shot_groups")
            merged_groups.extend(batch_plan.get("shot_groups") or [])
            consecutive_failures = 0
        except Exception as exc:
            logger.warning("导演分镜第 %s 批文本模型生成失败，回退该批规则模板: %s", batch_index, exc)
            consecutive_failures += 1
            fallback_group = fallback_groups[batch_index - 1] if batch_index - 1 < len(fallback_groups) else None
            if fallback_group:
                merged_groups.append(fallback_group)
            else:
                merged_groups.extend(batch_fallback.get("shot_groups") or [])

    if not merged_groups:
        return fallback

    plan = dict(fallback)
    plan["shot_groups"] = merged_groups
    return DirectorShotPlanModel.model_validate(_renumber_director_plan(plan, fallback)).model_dump()
