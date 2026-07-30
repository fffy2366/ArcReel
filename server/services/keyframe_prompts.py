"""Keyframe prompt planning helpers.

This deterministic slice converts director shots into reviewable keyframe
prompts. It does not enqueue image generation; it only prepares the prompt
contract for the next step.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from lib.text_backends.base import TextGenerationRequest, TextTaskType
from lib.text_generator import TextGenerator
from server.services.text_model_json import parse_model_json_object

logger = logging.getLogger(__name__)

KEYFRAME_PROMPT_MODEL_TIMEOUT_SECONDS = 25
KEYFRAME_PROMPT_MODEL_FAILURE_BREAKER = 1


class KeyframePromptModel(BaseModel):
    keyframe_id: str
    shot_id: str
    role: str
    title: str
    image_role_explanation: str
    prompt: str
    negative_prompt: str = ""
    style_policy: str = ""
    reference_policy: str = ""
    grid_cells: list[dict[str, Any]] = Field(default_factory=list)
    optional_reference_roles: list[str] = Field(default_factory=list)
    review_checkpoints: list[str] = Field(default_factory=list)


class KeyframePromptPlanModel(BaseModel):
    schema_version: int = 1
    episode: int
    source_shot_count: int = 0
    total_duration_seconds: int = 0
    prompts: list[KeyframePromptModel] = Field(default_factory=list)


def _excerpt(text: Any, limit: int = 160) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _clean_text(text: Any) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    compact = re.sub(r"^呈现[:：]\s*", "", compact)
    compact = compact.replace("```text", "").replace("```", "").strip()
    return compact.strip("“”\"'")


def _clean_for_prompt(text: Any, limit: int = 180) -> str:
    compact = _clean_text(text).replace("……", "").replace("...", "").replace("…", "")
    compact = re.sub(r"^\d+-\d+\s*", "", compact)
    compact = re.sub(r"\s+", " ", compact).strip()
    return compact if len(compact) <= limit else compact[:limit].rstrip("，,。；; ")


def _has_truncation(text: Any) -> bool:
    value = str(text or "")
    return "…" in value or "..." in value


def _finish_sentence(text: str) -> str:
    text = text.rstrip("。；;,.， ")
    return f"{text}。" if text else ""


def _is_generic_performance(text: str) -> bool:
    generic_markers = [
        "最后一拍",
        "新人物",
        "下一选择",
        "未完成感",
        "服务旁白",
        "B-roll",
        "情绪由道具速度",
        "情绪由",
        "画面动作",
    ]
    return sum(1 for marker in generic_markers if marker in text) >= 1


def _has_human_performance_target(shot: dict[str, Any]) -> bool:
    text = _shot_text_blob(shot)
    human_markers = [
        "男主",
        "女主",
        "人物",
        "角色",
        "他",
        "她",
        "脸",
        "眼",
        "嘴",
        "手",
        "身体",
        "肩",
        "林",
        "苏",
    ]
    no_human_markers = ["无人物入镜", "无人", "空场景", "纯场景", "环境空镜"]
    if any(marker in text for marker in no_human_markers):
        return False
    return any(marker in text for marker in human_markers)


def _visibility_mode(shot: dict[str, Any]) -> str:
    """Return how much actor performance is actually visible in this shot."""
    text = _shot_text_blob(shot)
    if any(
        marker in text
        for marker in [
            "第一人称",
            "主观视角",
            "POV",
            "无人物面部特写",
            "道具特写",
            "插入镜头",
            "手部特写",
            "只拍手",
            "看不到脸",
        ]
    ):
        return "limited_actor"
    if any(marker in text for marker in ["无人物入镜", "无人", "空场景", "纯场景", "环境空镜"]):
        return "no_human"
    return "visible_actor" if _has_human_performance_target(shot) else "no_human"


def _camera_text(shot: dict[str, Any]) -> str:
    shot_size = _clean_for_prompt(shot.get("shot_size") or "", 40)
    camera_angle = _clean_for_prompt(shot.get("camera_angle") or "", 40)
    generic = {"悬念特写", "主观反应机位", "镜头组", ""}
    if shot_size in generic or camera_angle in generic:
        return "电影感中景或近景，平视略低机位，主体清楚，环境保留足够信息"
    return f"{shot_size or '电影感中景'}，{camera_angle or '平视机位'}"


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _style_policy() -> str:
    return (
        "动作引导图默认使用素描铅笔画/动画分镜草稿风格，优先表达动作、机位和节奏；"
        "它用于提交给视频模型辅助理解这一镜怎么演，不作为最终画面。"
    )


def _reference_policy() -> str:
    return (
        "首轮生成9宫格动作引导图；视频生成时主要提交角色、场景、道具资产，动作引导图作为辅助参考。"
        "关键帧 start/end 只在视频质检失败后作为修复手段生成。"
    )


def _review_checkpoints() -> list[str]:
    return [
        "9宫格是否清楚表达这一镜的动作起承转合。",
        "每格是否只表达一个小动作或镜头状态。",
        "角色、道具、场景关系是否足够让视频模型理解怎么演。",
        "是否保持草稿示意性质，而不是追求最终精修画面。",
    ]


def _shot_text_blob(shot: dict[str, Any]) -> str:
    return " ".join(str(value or "") for value in shot.values())


def _shot_visual_text_blob(shot: dict[str, Any]) -> str:
    visual_keys = [
        "source_excerpt",
        "screen_subject",
        "action",
        "visible_event",
        "main_subject",
        "environment",
        "characters",
        "props",
        "start_state",
        "end_state",
        "motion_arc",
        "keyframe_start",
        "video_motion",
    ]
    return " ".join(str(shot.get(key) or "") for key in visual_keys)


def _current_source_text(shot: dict[str, Any]) -> str:
    return _clean_text(shot.get("source_excerpt") or shot.get("visible_event") or shot.get("action") or "")


def _current_visual_text(shot: dict[str, Any]) -> str:
    keys = ("source_excerpt", "screen_subject", "action", "visible_event", "main_subject", "keyframe_start", "video_motion")
    return " ".join(_clean_text(shot.get(key)) for key in keys if _clean_text(shot.get(key)))


def _is_plan_paper_scene(shot: dict[str, Any]) -> bool:
    text = _current_visual_text(shot)
    return any(marker in text for marker in ("商业计划书", "计划书", "纸页", "纸质", "满篇", "写满", "名字", "予曦地产"))


def _is_window_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return "窗户渐显" in current or "旭日" in current or "晨曦穿透玻璃" in current


def _is_milk_splash_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return "奶茶" in current and any(marker in current for marker in ("喷洒", "喷", "一身一脸"))


def _is_milk_laugh_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    visual = _shot_visual_text_blob(shot)
    return (
        "笑" in current
        and any(marker in visual for marker in ("奶茶", "雪克壶", "奶茶店"))
        and not _is_milk_splash_scene(shot)
    )


def _is_milk_wipe_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return any(marker in current for marker in ("跪倒", "毛巾", "擦拭裤子", "擦拭裤子和衣服"))


def _is_oversized_shirt_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return any(marker in current for marker in ("衬衫", "男士纯白衬衫", "oversize", "贴身衣物", "大长腿"))


def _is_fatigue_room_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return any(marker in current for marker in ("通宵", "疲惫", "哈欠"))


def _is_coffee_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return "咖啡" in current or "咖啡杯" in current


def _is_phone_notification_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return "手机" in current and any(marker in current for marker in ("弹窗", "震动", "刷屏", "通知"))


def _is_kiss_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return "吻" in current or ("凑过来" in current and "镜头" in current)


def _is_motorcycle_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    visual = _shot_visual_text_blob(shot)
    return (
        "机车" in current
        or "漂移" in current
        or "后座" in current
        or (any(marker in current for marker in ("乱抓", "搂住", "肘击", "飞出去")) and "机车" in visual)
    )


def _is_drinking_scene(shot: dict[str, Any]) -> bool:
    current = _current_source_text(shot)
    return "啤酒" in current or "易拉罐" in current or "酒桌" in current or "酒渍" in current or "吊带衣" in current


def _is_sword_flight_shot(shot: dict[str, Any]) -> bool:
    text = _shot_text_blob(shot)
    return "飞剑" in text or "御剑" in text


def _sword_flight_prompt_block() -> str:
    return (
        "御剑构图：飞剑沿画面左下到右上飞行，剑尖在右上，剑柄和灵石驱动盒在左下后方。"
        "飞剑是窄身青铁叶片，长度约人物身高 1.4–1.6 倍，宽度只够双脚前后错步站立；"
        "男主双脚踩实剑身中轴线，两条腿完整可见，膝盖微弯，身体重心稳定前压。"
    )


def _sword_flight_environment_block(environment: str) -> str:
    return (
        "场景环境：飞剑位于当前场景的高处或开阔飞行路径中，脚下/身后环境快速后掠；"
        f"{environment or '背景按当前项目场景呈现'}只作为远景或中景空间参照；"
        "竹叶被气流压弯，雾气有 3D 体积层次，画面不能贴地。"
    )


def _sword_safe_action_text(text: str) -> str:
    text = text.replace("竹梢上方低空", "竹梢上方一到两人高处")
    text = text.replace("低空掠过", "贴着竹冠上方掠过")
    text = text.replace("低空飞行", "竹冠上方飞行")
    text = text.replace("，不要贴地飞行，不要裁成只有脚或单腿。", "。")
    text = text.replace("；关键帧不要裁成局部脚部，不要贴着地面飞行。", "。")
    text = text.replace("；禁止只露一条腿", "")
    return text


def _sword_flight_review_checkpoints() -> list[str]:
    return [
        "飞剑比例是否合理：不是巨剑/平台/冲浪板，长度约人物身高 1.4–1.6 倍，剑身细长。",
        "男主是否双脚真实踩在剑身中轴线，脚底贴合剑面，两条腿完整，重心稳定。",
        "剑尖是否朝画面右上/前进方向，剑柄与灵石驱动盒是否在左下后方。",
    ]


def _micro_excerpt_map(story_beats: dict[str, Any] | None) -> dict[str, str]:
    mapping: dict[str, str] = {}
    if not isinstance(story_beats, dict):
        return mapping
    ordered: list[tuple[str, str]] = []
    for beat in story_beats.get("beats") or []:
        for micro in beat.get("micro_beats") or []:
            micro_id = str(micro.get("micro_id") or "").strip()
            source = _clean_text(micro.get("source_excerpt") or micro.get("title"))
            if micro_id and source:
                ordered.append((micro_id, source))
    for index, (micro_id, source) in enumerate(ordered):
        if len(_clean_for_prompt(source, 40)) >= 6:
            mapping[micro_id] = source
            continue
        context = [
            ordered[index - 1][1] if index > 0 else "",
            source,
            ordered[index + 1][1] if index + 1 < len(ordered) else "",
        ]
        mapping[micro_id] = " ".join(_clean_text(item) for item in context if _clean_text(item))
    return mapping


def _best_source_text(shot: dict[str, Any], source_by_micro_id: dict[str, str]) -> str:
    micro_id = str(shot.get("source_micro_id") or "").strip()
    candidates = [
        shot.get("keyframe_start"),
        shot.get("visible_event"),
        shot.get("source_excerpt"),
        source_by_micro_id.get(micro_id),
        shot.get("action"),
        shot.get("screen_subject"),
        shot.get("title"),
    ]
    cleaned = [_clean_for_prompt(candidate, 220) for candidate in candidates if _clean_text(candidate)]
    for item in cleaned:
        if item and "…" not in item and len(item) >= 4:
            return item
    return cleaned[0] if cleaned else "当前剧情关键瞬间"


def _performance_text(shot: dict[str, Any]) -> str:
    mode = _visibility_mode(shot)
    performance_parts = [
        _clean_for_prompt(shot.get("facial_performance"), 100),
        _clean_for_prompt(shot.get("body_performance"), 100),
        _clean_for_prompt(shot.get("performance"), 120),
    ]
    specific_parts = [part for part in performance_parts if part and not _is_generic_performance(part)]
    if mode == "limited_actor":
        return "不强制脸部表演；用可见手部动作、道具位置变化、镜头停顿、呼吸造成的轻微晃动或环境反应表达情绪。"
    if mode == "no_human":
        return "无人物表演；通过主体道具的位置变化、光影方向、环境细节和运动线表达节奏。"
    if specific_parts:
        text = "；".join(specific_parts)
        if mode == "visible_actor":
            visible_markers = ["眼", "眉", "嘴", "呼吸", "手指", "肩", "重心"]
            if sum(1 for marker in visible_markers if marker in text) < 2:
                text = f"{text}；眼神先靠近目标再短暂停住，嘴角轻微变化，呼吸放慢，手指和肩颈跟着情绪产生细微动作。"
        return text
    if mode == "visible_actor":
        return "眼神先寻找目标再短暂停住，眉心轻压，嘴唇微张后收住，肩颈随呼吸产生细微起伏，手指和身体重心跟随动作连续变化。"
    return "无人物表演；通过主体道具的位置变化、光影方向、环境细节和运动线表达节奏。"


def _event_clauses(*texts: str) -> list[str]:
    clauses: list[str] = []
    seen: set[str] = set()
    for text in texts:
        cleaned = _clean_text(text)
        if not cleaned:
            continue
        cleaned = cleaned.replace("就在", "")
        cleaned = re.sub(r"(.{4,80}?)时[，,]", r"\1，", cleaned)
        for part in re.split(r"[。；;，,：:\n]", cleaned):
            part = _clean_for_prompt(part, 42)
            part = re.sub(r"^(呈现|画面|镜头|主体|动作|旁白)\s*", "", part).strip()
            if len(part) < 4:
                continue
            if part in seen:
                continue
            seen.add(part)
            clauses.append(part)
    return clauses


def _event_part(clauses: list[str], index: int, fallback: str) -> str:
    if 0 <= index < len(clauses):
        return clauses[index]
    return _clean_for_prompt(fallback, 42)


def _allowed_scene_texts(shot: dict[str, Any]) -> list[str]:
    """Text that is part of the pictured world, not script narration.

    Keep this deliberately conservative. Anything not whitelisted must be
    represented as marks, blocks, symbols, or blur, never readable text.
    """
    text = _current_visual_text(shot)
    allowed: list[str] = []
    if "照相馆" in text or "相馆" in text:
        allowed.append("XX照相馆")
    if "系统绑定成功" in text:
        allowed.append("系统绑定成功")
    if "S级订单" in text or "S 级订单" in text:
        allowed.append("S级订单")
    if _is_plan_paper_scene(shot) and "内心" not in text and "吐槽" not in text:
        allowed.append("商业计划书")
    deduped: list[str] = []
    for item in allowed:
        if item not in deduped:
            deduped.append(item)
    return deduped


def _text_rule_line(allowed_texts: list[str]) -> str:
    if allowed_texts:
        allowed = "、".join(f"“{item}”" for item in allowed_texts)
        return (
            f"画面文字规则：只允许出现这些画内文字：{allowed}；"
            "除此之外禁止任何可读汉字、英文、数字、台词、旁白、字幕、分镜标题。"
            "纸张、书页、屏幕、海报、照片墙如需文字感，只画不可读短横线、灰线、抽象符号块或发光图形。"
        )
    return (
        "画面文字规则：禁止任何可读汉字、英文、数字、台词、旁白、字幕、分镜标题；"
        "纸张、书页、屏幕、海报、照片墙如需文字感，只画不可读短横线、灰线、抽象符号块或发光图形。"
    )


def _visual_anchor(shot: dict[str, Any]) -> str:
    text = _current_visual_text(shot)
    if "金光" in text or "系统" in text or "界面" in text:
        return "桌面纸页上方浮现无字金色系统界面轮廓，纸面只有不可读短横线"
    if "照相馆" in text or "相馆" in text:
        return "照相馆门口与店内照片墙，招牌仅写XX照相馆，照片内容模糊不可读"
    if "奶茶" in text or "雪克壶" in text:
        return "奶茶店操作台、雪克壶、飞溅奶茶和人物手忙脚乱的动作"
    if _is_plan_paper_scene(shot):
        return "桌面商业计划书与手指，纸面布满不可读短横线和模糊灰线"
    return _clean_for_prompt(shot.get("screen_subject") or shot.get("visible_event") or shot.get("action") or "当前镜头主体", 80)


def _visual_sequence_for_shot(shot: dict[str, Any], environment: str) -> list[str]:
    text = _current_visual_text(shot)
    if _is_window_scene(shot):
        return [
            "男主第一人称视野从微暗晨光中慢慢亮起，窗户轮廓刚显现",
            "窗外地平线露出旭日边缘，玻璃上有柔和晨光反射",
            "金色晨曦穿透玻璃，空气里浮尘被照亮",
            "镜头从窗户缓慢向下移动，窗框退到画面上方",
            "书桌边缘和凌乱纸页进入画面下方，仍保持主观视角",
            "纸页被晨光扫过，房间通宵后的疲惫感显现",
            "前景轻微晃动像男主疲惫呼吸或打哈欠",
            "镜头继续稳定下移，桌面计划书成为下一镜焦点",
            "停在窗光、桌面边缘和计划书同框的第一人称近景",
        ]
    if "金光" in text or "系统" in text or "界面" in text:
        system_text = "系统界面中央浮现系统绑定成功五个金色字" if "系统绑定成功" in text else "界面内部只有抽象符号块和光点，不出现其他文字"
        return [
            "第一人称低头看桌面纸页，纸面只有不可读短横线",
            "手指停在纸页边缘，画面短暂停顿",
            "纸页上方空气出现一点金色微光",
            "金光扩散成半透明矩形系统界面轮廓",
            system_text,
            "金光照亮手指和纸页边缘，前景轻微晃动",
            "手指轻微后缩，纸角被气流带起",
            "金色界面稳定悬浮，背景虚化",
            "停在手指、纸页、无字发光界面同框的主观近景",
        ]
    if _is_phone_notification_scene(shot):
        return [
            "男主第一人称低头看向书桌，手机躺在计划书旁开始震动",
            "手机屏幕亮起，弹窗以抽象无字信息块连续冒出",
            "手机因震动在桌面轻轻位移，旁边纸页边角被震动带起",
            "镜头推近手机屏幕，多个通知卡片快速堆叠但不可读",
            "金色系统光和手机冷光同时照亮男主前景手指",
            "弹窗刷屏速度加快，桌面小物件跟着细微颤动",
            "男主前景手指停在手机旁，像被突如其来的消息震住",
            "手机屏幕继续闪烁，通知信息变成密集图形块",
            "停在手机、计划书边缘、男主前景手指同框的第一人称近景",
        ]
    if _is_coffee_scene(shot):
        return [
            "男主第一人称视角看向凌乱书桌和计划书边缘",
            "一只白皙纤细的手从镜头侧面伸入，手里端着热咖啡",
            "咖啡杯靠近桌面，杯口热气上升，晨光照到杯沿",
            "手指轻轻松开杯柄，咖啡杯落在纸旁没有碰乱纸页",
            "杯底接触桌面，咖啡液面轻微晃动",
            "镜头随男主视线从咖啡杯抬向手腕和袖口",
            "林予曦的身影从侧后方靠近，仍保持第一人称视角",
            "咖啡热气和窗光叠在一起，桌面疲惫感被温柔打断",
            "停在咖啡杯、纤细手指、计划书边缘同框的主观近景",
        ]
    if _is_fatigue_room_scene(shot):
        return [
            "男主第一人称视角停在清晨房间，窗光铺在凌乱书桌边缘",
            "桌面纸页、笔和生活小物有通宵后的凌乱感",
            "前景轻微上下晃动，像男主疲惫呼吸",
            "镜头短暂停住，空气中浮尘和晨光缓慢漂移",
            "前景手指或衣袖无力地搭在桌边，表现困倦",
            "哈欠造成画面轻微模糊和短促晃动",
            "镜头重新稳定，房间安静、纸张边缘微动",
            "疲惫感停在空间和前景细节上，不新增人物",
            "停在第一人称疲惫视野：窗光、桌面边缘、前景手部同框",
        ]
    if "照相馆" in text or "相馆" in text:
        return [
            "第一人称站在照相馆门口，手伸向门把手，招牌写XX照相馆",
            "门被推开一条缝，室内相框墙和柔光从门缝露出",
            "快速混剪到相馆内，几张照片挂在墙上，照片内容模糊不可读",
            "画面切到奶茶店操作台，女主手忙脚乱摇雪克壶",
            "奶茶飞溅到前景衣袖，镜头轻微一抖",
            "女主在画外笑弯腰，只露侧影和摆动的手臂",
            "闪回到桌面商业计划书，纸页只有不可读短横线",
            "男主手指按住纸页，纸角轻轻回弹，窗光滑过纸面",
            "停在手指、纸页、窗光同框的第一人称近景",
        ]
    if "奶茶" in text or "雪克壶" in text or _is_milk_laugh_scene(shot) or _is_milk_wipe_scene(shot):
        if _is_milk_splash_scene(shot):
            return [
                "男主第一人称视角看向奶茶店操作台，对面的林予曦拿起雪克壶",
                "前景露出男主衣袖和手臂边缘，林予曦手指扣住雪克壶杯身",
                "林予曦开始摇雪克壶，杯口角度偏向镜头，奶茶液面剧烈晃动",
                "杯盖松动，第一道奶茶从雪克壶缝隙朝镜头喷出",
                "奶茶液体沿画面纵深飞向男主视角，液滴接近镜头边缘",
                "奶茶打到镜头边缘、男主前景衣袖和可见手臂，画面短促一抖",
                "林予曦在对面愣住后身体后仰笑出声，手里还攥着雪克壶",
                "镜头边缘挂着奶茶液滴，男主前景衣袖被打湿，操作台杯具轻晃",
                "停在第一人称主观近景：湿掉的镜头边缘、男主衣袖、对面笑弯腰的林予曦同框",
            ]
        if _is_milk_wipe_scene(shot):
            return [
                "男主第一人称视角低头看见林予曦跪在身前，手里拿着毛巾",
                "毛巾贴近男主前景裤腿和衣摆，奶茶污渍清楚可见",
                "林予曦俯身认真擦拭，动作小心又急促，头发垂到侧脸边",
                "她抬眼确认男主反应，手上的毛巾没有停",
                "镜头微微后缩，交代她跪在身前和男主前景衣物的位置关系",
                "她换一块衣料继续擦，袖口和毛巾形成连续运动线",
                "林予曦表情从认真转成无辜讨好，动作放慢",
                "男主主观视角停顿半拍，前景衣物仍有湿痕",
                "停在第一人称近景：毛巾、男主前景裤腿、林予曦俯身擦拭同框",
            ]
        if _is_milk_laugh_scene(shot):
            return [
                "男主第一人称视角看向奶茶店操作台，对面林予曦刚从失手中反应过来",
                "林予曦嘴角先憋住笑，手里还攥着雪克壶",
                "她突然笑出声，肩膀开始抖动，身体向后仰",
                "镜头边缘仍有少量奶茶液滴，操作台杯具微微晃动",
                "林予曦笑得前仰后合，一只手扶住操作台边缘",
                "男主主观镜头停住半拍，像被她的反应噎住",
                "她弯腰继续笑，雪克壶垂在手边，奶茶滴落到台面",
                "笑声后的余韵里，她抬眼看向镜头，表情无辜又调皮",
                "停在第一人称中近景：林予曦笑弯腰、雪克壶、凌乱操作台同框",
            ]
        return [
            "奶茶店操作台建立，杯具、封口机和雪克壶排列清楚",
            "林予曦站在操作台前拿起雪克壶，手指扣住杯身边缘",
            "雪克壶第一次上扬，杯口角度略偏，奶茶液面晃动",
            "她用力摇晃雪克壶，肩膀和手腕形成连续运动线",
            "杯盖松动，奶茶从缝隙喷向前景衣袖",
            "镜头轻微一抖，飞溅奶茶在前景形成弧线",
            "林予曦身体后仰笑出声，手里还攥着雪克壶",
            "操作台上杯具轻晃，奶茶滴落，动作后的余波还在",
            "停在她笑弯腰、雪克壶和凌乱操作台同框的中近景",
        ]
    if _is_oversized_shirt_scene(shot):
        return [
            "男主第一人称视角进入温馨居家房间，前景门框或桌角轻微遮挡",
            "林予曦穿着宽大的男士纯白衬衫站在房间中，衣摆宽松垂落",
            "镜头从衬衫衣摆和修长双腿上移到她的半身轮廓",
            "她抬起手，用两根手指嫌弃地拎着男主贴身衣物",
            "她把贴身衣物举远一点，另一只手夸张捂住鼻子",
            "男主第一人称前景轻微后缩，像被她的嫌弃动作噎住",
            "林予曦侧身晃了晃手里的衣物，宽大白衬衫跟着轻轻摆动",
            "居家柔光落在白衬衫和她嫌弃又娇嗔的表情上",
            "停在第一人称中近景：林予曦、宽大男士白衬衫、手里拎着的贴身衣物同框",
        ]
    if _is_kiss_scene(shot):
        return [
            "男主第一人称视角停在书桌前，画面边缘仍有系统金光余亮",
            "林予曦带着轻笑从画面侧前方靠近镜头",
            "她的脸部逐渐占据画面中心，背景书桌和手机虚化",
            "她抬眼看向镜头，表情温柔调皮，距离继续缩短",
            "镜头因男主愣住而短暂停顿，前景光斑轻微晃动",
            "林予曦贴近镜头，在主观视角前留下一个吻",
            "画面边缘被柔和遮挡，光线变暖，动作放慢半拍",
            "她轻轻退开一点，笑意和呼吸余韵留在镜头前",
            "停在第一人称近景：林予曦靠近后的温柔表情、虚化书桌和暖光同框",
        ]
    if _is_drinking_scene(shot):
        return [
            "男主第一人称视角看向家中小酒桌，桌上有易拉罐和杯子",
            "林予曦穿着舒适居家吊带衣坐在桌旁，动作放松",
            "她一只脚踩上凳子，身体重心变得豪迈外放",
            "她抬起易拉罐仰头喝酒，手臂和肩线形成清楚动作线",
            "易拉罐压到桌面，桌上小物被震得轻轻跳动",
            "她抹去嘴角酒渍，眼神从迷离转向镜头",
            "她带着霸气玩笑感伸手指向男主第一人称镜头",
            "酒桌灯光和罐身反光保留动作后的余韵",
            "停在林予曦、易拉罐、小酒桌同框的第一人称中近景",
        ]
    if _is_motorcycle_scene(shot):
        current = _current_source_text(shot)
        if "乱抓" in current or "搂住" in current:
            return [
                "男主第一人称视角在重型机车后座被惯性甩向前方",
                "前方林予曦的背影和机车把手剧烈晃动，街灯拉成长线",
                "男主前景双手本能向前伸出，手指张开寻找支撑点",
                "车身继续倾斜漂移，男主手臂越过座位向林予曦靠近",
                "男主双手抓住林予曦上半身附近，动作带着慌乱和求稳",
                "林予曦肩背突然僵住，身体线条明显一顿",
                "机车仍高速前进，风把发丝和衣摆向后拉",
                "男主前景手臂紧绷，镜头因尴尬和惯性停顿半拍",
                "停在第一人称后座近景：男主前景双手、林予曦背影、飞驰街道同框",
            ]
        if "肘击" in current or "身体一僵" in current:
            return [
                "男主第一人称后座视角中，林予曦肩背突然一僵",
                "她一只手稳住机车，另一侧手臂开始向后收紧",
                "镜头靠近她肩线和手臂，能看出她准备反击",
                "林予曦顺势向后做出一记短促肘击，动作干脆",
                "男主主观镜头被肘击吓得短促后缩，前景手臂松动",
                "林予曦没有减速，身体重新压回机车前方路线",
                "街灯和道路继续高速后掠，机车保持危险速度",
                "男主前景手停在半空，尴尬和惊吓都压在停顿里",
                "停在第一人称后座画面：林予曦背影、收回的手臂、飞驰街道同框",
            ]
        if "急加速" in current or "漂移" in current or "飞出去" in current:
            return [
                "男主第一人称坐在重型机车后座，前方是林予曦背影和深夜街灯",
                "机车猛地急加速，路灯和道路标线向后拉成长线",
                "车身开始漂移倾斜，男主前景手臂本能向前伸出",
                "镜头因惯性短促晃动，林予曦发丝和衣摆被风向后拉",
                "男主身体被甩向一侧，几乎要从后座滑出去",
                "前景手指乱抓，试图找到能稳住身体的位置",
                "机车压低角度冲过街口，背景灯光形成弧线",
                "男主视野重新对准林予曦背影，危险还没结束",
                "停在第一人称后座画面：倾斜机车、飞驰街道、男主前景手臂同框",
            ]
        return [
            "男主第一人称视角坐在重型机车后座，前方是林予曦的背影和街头灯光",
            "机车在深夜街头加速，路灯和道路标线向后拉成长线",
            "车身开始漂移倾斜，男主前景手臂本能向前伸出",
            "镜头因急加速短促晃动，林予曦发丝和衣摆被风向后拉",
            "男主双手抓向前方，身体重心被甩向一侧",
            "林予曦身体一僵，肩线突然收紧",
            "她反手或肘部做出警告动作，仍控制机车不减速",
            "机车重新压回路线，街灯继续高速后掠",
            "停在后座第一人称视角：林予曦背影、机车把手、飞驰街道同框",
        ]
    if _is_plan_paper_scene(shot):
        return [
            "第一人称看向桌面计划书，纸页铺满画面下半部",
            "纸面只有密集不可读短横线，不出现真实汉字",
            "手指从纸页边缘慢慢滑入画面",
            "镜头向下轻推，纸页纹理和灰线变清楚",
            "手指停在一片密集灰线旁，纸角轻微翘起",
            "窗光从纸面滑过，灰线短暂变亮",
            "前景手指轻轻压住纸角，纸页停止晃动",
            "背景虚化，只保留纸面、手指和窗光层次",
            "停在手指压住计划书的主观近景，纸面仍不可读",
        ]
    anchor = _visual_anchor(shot)
    return [
        f"建立{environment or '当前场景'}，主体进入画面",
        f"镜头靠近{anchor}",
        "主体发生第一个可见变化，动作从静止开始",
        "动作继续推进，前景和背景保持连续",
        "焦点收窄到关键道具或手部细节",
        "镜头轻推或轻摇，强化运动方向",
        "动作停在最有张力的一帧",
        "光影和前景保留细微余动",
        "停在可顺接下一镜的稳定构图",
    ]


def _grid_cell(
    cell: int,
    phase: str,
    visual: str,
    acting: str,
    body: str,
    camera: str,
    purpose: str,
) -> dict[str, Any]:
    return {
        "cell": cell,
        "phase": phase,
        "visual": _finish_sentence(_clean_for_prompt(visual, 90)),
        "acting": _finish_sentence(_clean_for_prompt(acting, 70)),
        "body": _finish_sentence(_clean_for_prompt(body, 70)),
        "camera": _finish_sentence(_clean_for_prompt(camera, 70)),
        "purpose": _finish_sentence(_clean_for_prompt(purpose, 50)),
    }


def _grid_cells_for_shot(
    shot: dict[str, Any],
    *,
    source_text: str,
    subject: str,
    action: str,
    camera: str,
    camera_movement: str,
    performance: str,
    environment: str,
) -> list[dict[str, Any]]:
    is_sword_flight = _is_sword_flight_shot(shot)
    has_human = _has_human_performance_target(shot)
    title = _clean_for_prompt(shot.get("title") or source_text, 120)
    environment_text = environment or "当前剧情场景，空间关系清楚，前景、中景、背景有层次"
    subject_text = subject or source_text or title
    action_text = action or source_text or title
    camera_text = camera or _camera_text(shot)
    movement_text = camera_movement or "轻微推进"
    clauses = _event_clauses(action_text, source_text, subject_text)
    setup_part = _event_part(clauses, 0, subject_text)
    trigger_part = _event_part(clauses, 1, action_text)
    develop_part = _event_part(clauses, 2, action_text)
    detail_part = _event_part(clauses, 3, subject_text)

    if is_sword_flight:
        return [
            _grid_cell(1, "建立空间", "竹冠和晨雾从画面下方掠过，飞剑从左下进入画面，剑尖朝右上前进方向", "男主先不做夸张表情，注意力压在前方路线", "双脚前后错步踩在剑身中轴线，膝盖微弯，重心前压", "三分之二侧前方跟拍，略低于人物胸口，完整人剑入画", "先证明人和剑在高处飞行，不贴地"),
            _grid_cell(2, "动作准备", "镜头靠近剑身，窄青铁剑面、剑柄和灵石驱动盒位置清楚", "眼神快速扫向飞行方向，眉心收紧", "脚底贴合剑面，脚踝微调保持平衡", "同速跟拍，画面加少量运动线", "交代飞剑比例和踩踏接触点"),
            _grid_cell(3, "速度启动", "竹叶被气流压弯，雾带向后拉成长线", "嘴唇抿紧，呼吸收住", "身体略向前倾，衣摆和发梢向后扬起", "镜头轻微推近到人物半身和脚下剑面", "建立速度感"),
            _grid_cell(4, "动作发展", action_text, performance, "双腿完整可见，膝盖用小幅度缓冲飞行颠簸", movement_text, "让视频模型理解主体运动路径"),
            _grid_cell(5, "身体调度", "飞剑穿过竹梢上方一到两人高度，背景高速后掠", "眼神从脚下余光抬到远处目标", "一只手稳住身体，另一只手根据剧情持物或前伸", "焦点从飞剑转到上半身", "把道具、身体、表情连成一个动作"),
            _grid_cell(6, "情绪推进", "脸部进入更清楚的中近景，身后竹林仍在流动", performance, "肩颈紧绷但不僵硬，重心继续压向前方", "轻推到脸部与胸前动作", "让焦急或紧迫感落在人脸上"),
            _grid_cell(7, "落点前奏", "前方空间打开，飞剑保持剑尖朝前，人物站位不偏离剑身", "眼睛锁定前方，表情进入决断", "脚尖微微调整方向，身体准备承接下一镜", "镜头稳定半拍", "准备剪辑衔接"),
            _grid_cell(8, "反应停顿", "衣摆和雾线还在动，人物动作短暂停住", "眉眼保持紧迫，嘴角收紧", "手指扣紧道具或握拳，脚底仍贴住剑面", "保持中景，不随机切镜", "保留余韵"),
            _grid_cell(9, "结尾状态", "完整人剑停在可读构图里，竹冠在下方，飞行方向明确", "视线朝下一镜方向", "两条腿完整、站稳、重心清楚", "定格在能直接进入视频生成的起始姿态", "给视频模型稳定起始参考"),
        ]

    visual_sequence = _visual_sequence_for_shot(shot, environment_text)
    if _visibility_mode(shot) == "limited_actor":
        return [
            _grid_cell(1, "主观建立", visual_sequence[0], "不画主角脸", "前景轻微呼吸晃动", camera_text, "建立视角"),
            _grid_cell(2, "停顿", visual_sequence[1], "犹豫半拍", "手指或前景停住", movement_text, "给触发前留白"),
            _grid_cell(3, "触发", visual_sequence[2], "焦点被拉走", "光影或道具边缘微动", "焦点转向异常处", "进入事件"),
            _grid_cell(4, "扩散", visual_sequence[3], "不用脸部表情", "纸页、衣袖或前景被照亮", "中近景保持主体清楚", "强化变化"),
            _grid_cell(5, "细节", visual_sequence[4], "用镜头微停表达震惊", "手指轻颤或道具轻晃", "焦点收窄", "锁住信息点"),
            _grid_cell(6, "靠近", visual_sequence[5], "保持主观视角", "前景遮挡发生小变化", "轻推或轻摇", "读清动作方向"),
            _grid_cell(7, "落点", visual_sequence[6], "情绪靠停顿表达", "可见动作收住", "稳定半拍", "形成可用姿态"),
            _grid_cell(8, "余韵", visual_sequence[7], "不补不可见表情", "手指余力或道具惯性未完全消失", "固定或极慢推", "保留情绪"),
            _grid_cell(9, "衔接", visual_sequence[8], "焦点指向下一镜", "画面关系稳定", "定格主观参考帧", "收束镜头"),
        ]

    if has_human:
        visual_sequence = _visual_sequence_for_shot(shot, environment_text)
        return [
            _grid_cell(1, "建立空间", visual_sequence[0], "表情保持在情绪爆发前一拍，眼神先寻找关键对象", "身体站位稳定，肩颈放松但有预备张力", camera_text, "交代人物、道具和空间关系"),
            _grid_cell(2, "动作准备", visual_sequence[1], "眉心轻压，视线短暂停在目标上", "手臂开始抬起或身体微微前倾，手指有准备动作", movement_text, "让动作有清楚起点"),
            _grid_cell(3, "触发瞬间", visual_sequence[2] if visual_sequence[2] else trigger_part, "眼神出现第一次变化，嘴唇微张或轻抿", "手指、手腕、肩膀带动主体动作开始", "镜头跟随手部或身体运动，不突然切景", "进入主体动作"),
            _grid_cell(4, "动作推进", visual_sequence[3] if visual_sequence[3] else develop_part, performance, "身体重心从后脚转到前脚，肩膀和手臂形成连续运动线", "中近景保持人物与关键道具同框", "表达动作发展"),
            _grid_cell(5, "情绪细化", visual_sequence[4], performance, "手指停顿、握紧、松开或微颤，配合当前情绪", "焦点从道具/动作转到眼神和嘴角", "把内心变化落到可见表演"),
            _grid_cell(6, "关系变化", visual_sequence[5], "眼神从目标移向下一处反应点", "身体角度调整，胸口或肩线转向新的行动方向", "轻推或轻摇，保持空间连续", "让观众读懂人物选择"),
            _grid_cell(7, "动作落点", visual_sequence[6] if visual_sequence[6] else f"{detail_part}完成到最有张力的一帧", "表情到达峰值但不过度夸张", "身体停在可识别姿态，手部位置清楚", "镜头稳定半拍", "形成视频可用关键姿态"),
            _grid_cell(8, "余韵反应", "动作后的半拍，环境和衣摆仍有细微运动", "眼神保留反应，呼吸略有变化", "肩膀回落或继续紧绷，手指保持上一动作的后劲", "固定或极慢推进", "保留情绪余味"),
            _grid_cell(9, "结尾衔接", "人物停在下一镜可顺接的位置，关键道具不被遮挡", "视线或身体方向指向下一镜", "重心稳定，姿态不要随机改变", "定格在清晰中近景或中景", "给视频生成明确结束状态"),
        ]

    return [
        _grid_cell(1, "建立空间", environment_text, "无人物表演", "用前景、中景、背景层次建立空间", camera_text, "交代场景位置"),
        _grid_cell(2, "主体出现", f"关键道具或环境主体进入视觉中心：{subject_text}", "无人物表演", "道具轮廓、材质和位置清楚", movement_text, "让画面有主体"),
        _grid_cell(3, "光影启动", f"光线或环境细节开始变化：{action_text}", "无人物表演", "用光斑、阴影、蒸汽、纸张或物件细微位移表达动作", "镜头轻微推进或横移", "制造动态起点"),
        _grid_cell(4, "信息推进", action_text, "无人物表演", "主体道具与周围物件形成清楚因果关系", "中景/插入镜头保持可读", "呈现主要信息"),
        _grid_cell(5, "重点强调", f"画面焦点落在最重要细节：{subject_text}", "无人物表演", "材质、边缘、光泽或文字性信息只作为图形提示，不画真实可读文字", "焦点轻移到细节", "强调关键信息"),
        _grid_cell(6, "节奏变化", f"环境运动继续：{action_text}", "无人物表演", "背景保持简洁，不增加无关人物", "轻微摇移或推近", "避免静图感"),
        _grid_cell(7, "落点前奏", "主体道具停在最有叙事张力的位置", "无人物表演", "周围物件辅助指向主体", "镜头速度放慢", "准备落点"),
        _grid_cell(8, "余韵停顿", "光影、雾气、纸张或小物件保持细微运动", "无人物表演", "空间层次保持稳定", "固定半拍", "保留观看时间"),
        _grid_cell(9, "结尾衔接", "画面停在下一镜可顺接的构图，主体仍清楚", "无人物表演", "不出现多余人物、手、脸或人形剪影", "定格为清晰参考帧", "给视频模型稳定收束"),
    ]


def _normalize_grid_cells(raw_cells: Any) -> list[dict[str, Any]]:
    if not isinstance(raw_cells, list):
        return []
    cells: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_cells[:9], start=1):
        if not isinstance(raw, dict):
            continue
        cell_no = _as_int(raw.get("cell") or raw.get("index"), index)
        cell_no = min(9, max(1, cell_no))
        cells.append(
            {
                "cell": cell_no,
                "phase": _clean_for_prompt(raw.get("phase") or raw.get("阶段") or "", 40),
                "visual": _finish_sentence(_clean_for_prompt(raw.get("visual") or raw.get("画面") or "", 180)),
                "acting": _finish_sentence(_clean_for_prompt(raw.get("acting") or raw.get("表演") or "", 180)),
                "body": _finish_sentence(_clean_for_prompt(raw.get("body") or raw.get("身体") or "", 180)),
                "camera": _finish_sentence(_clean_for_prompt(raw.get("camera") or raw.get("镜头") or "", 180)),
                "purpose": _finish_sentence(_clean_for_prompt(raw.get("purpose") or raw.get("目的") or "", 140)),
            }
        )
    return sorted(cells, key=lambda item: _as_int(item.get("cell"), 0))


def _compose_grid_prompt(
    *,
    shot_id: Any,
    environment: str,
    lighting: str,
    grid_cells: list[dict[str, Any]],
    allowed_texts: list[str] | None = None,
    sword_block: str = "",
) -> str:
    lines = [
        "输出一张黑白素描风格的3x3九宫格运镜示意图，表现这一镜的连续动态画面。画面是动作草稿，不是精修插画。",
        "画风：黑白素描铅笔画、动画分镜草稿、白底九宫格、少量灰阶阴影；每一格独立清楚，格与格之间动作连续。",
        _text_rule_line(allowed_texts or []),
    ]
    if sword_block:
        lines.append(sword_block)
    lines.extend(
        [
            f"场景环境：{environment or '当前剧情场景，空间关系清楚，前景、中景、背景有层次。'}",
            "九格连续画面：",
        ]
    )
    for cell in grid_cells:
        lines.append(_grid_cell_prompt_line(cell))
    lines.extend(
        [
            f"空间与光影：只用必要线稿交代空间高度、前后层次和光源方向；参考氛围：{lighting.rstrip('。；; ') or '自然柔和主光，低对比度，避免硬阴影'}。",
            "排除项：不要把剧本旁白、内心独白、分镜标题、用途说明画成文字；不要精修彩色插画、不要真人照片、不要油画厚涂、不要复杂背景压过动作、不要文字水印、不要对白气泡。",
        ]
    )
    return "\n".join(line for line in lines if line)


def _grid_cell_prompt_line(cell: dict[str, Any]) -> str:
    parts = [_strip_sentence_punctuation(_clean_for_prompt(cell.get("visual"), 86))]
    for key, limit in (("acting", 42), ("body", 42), ("camera", 36)):
        detail = _clean_for_prompt(cell.get(key), 120)
        if not detail:
            continue
        detail = _strip_sentence_punctuation(re.split(r"[。；;]", detail)[0])
        detail = _short_detail(detail, limit)
        if any(
            marker in detail
            for marker in (
                "无人物表演",
                "不画主角脸",
                "不补不可见表情",
                "不用脸部表情",
                "保持主观视角",
            )
        ):
            continue
        if detail in parts[0]:
            continue
        parts.append(detail)
    return f"{cell.get('cell')} {'，'.join(parts)}"


def _strip_sentence_punctuation(text: str) -> str:
    return str(text or "").strip().rstrip("。；;，, ")


def _short_detail(text: str, limit: int) -> str:
    detail = _clean_for_prompt(text, 120)
    if len(detail) <= limit:
        return detail
    chunks = [chunk.strip("，, ") for chunk in re.split(r"[，,]", detail) if chunk.strip("，, ")]
    if not chunks:
        return _clean_for_prompt(detail, limit)
    selected: list[str] = []
    for chunk in chunks:
        candidate = "，".join(selected + [chunk])
        if len(candidate) > limit:
            break
        selected.append(chunk)
    if selected:
        return "，".join(selected)
    return chunks[0] if len(chunks[0]) <= limit + 8 else _clean_for_prompt(chunks[0], limit)


def _strip_prompt_pollution(prompt: str) -> str:
    banned_prefixes = (
        "【9宫格动作引导图",
        "用途：",
        "镜头核心：",
        "主体与道具：",
    )
    clean_lines: list[str] = []
    for line in str(prompt or "").splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        if any(stripped.startswith(prefix) for prefix in banned_prefixes):
            continue
        clean_lines.append(stripped)
    return "\n".join(clean_lines).strip()


def _append_grid_cells_to_prompt(prompt: str, grid_cells: list[dict[str, Any]]) -> str:
    prompt = _strip_prompt_pollution(prompt)
    if not grid_cells:
        return prompt
    head, tail = prompt, ""
    for marker in ("九格连续画面：", "九格动作草稿（短句，不重复原文）：", "九格逐格导演动作表"):
        if marker in head:
            head = prompt.split(marker, 1)[0].rstrip()
            after_marker = prompt.split(marker, 1)[1]
            for tail_marker in ("空间与光影：", "排除项："):
                if tail_marker in after_marker:
                    tail = tail_marker + after_marker.split(tail_marker, 1)[1].strip()
                    break
            break
    lines = [head.rstrip(), "", "九格连续画面："]
    for cell in grid_cells:
        lines.append(_grid_cell_prompt_line(cell))
    if tail:
        lines.extend(["", tail])
    return "\n".join(lines).strip()


def _normal_prompt_payload(shot: dict[str, Any], source_by_micro_id: dict[str, str]) -> dict[str, Any]:
    source_text = _best_source_text(shot, source_by_micro_id)
    raw_subject = _clean_for_prompt(shot.get("screen_subject"), 80)
    raw_action = _clean_for_prompt(shot.get("action"), 80)
    subject_source = shot.get("main_subject") or (
        source_text if _has_truncation(shot.get("screen_subject")) or len(raw_subject) < 6 else raw_subject
    )
    action_source = source_text if _has_truncation(shot.get("action")) or len(raw_action) < 6 else raw_action
    subject = _clean_for_prompt(subject_source or source_text, 150)
    action = _clean_for_prompt(action_source or source_text, 180)
    camera = _camera_text(shot)
    camera_movement = _clean_for_prompt(shot.get("camera_movement") or "轻微推进", 70)
    lighting = _clean_for_prompt(shot.get("lighting") or "柔和电影级布光，主体清晰可见", 100)
    performance = _performance_text(shot)
    environment = _clean_for_prompt(shot.get("environment"), 100)
    composition = _clean_for_prompt(shot.get("composition"), 140)
    if composition:
        camera = f"{camera}；{composition}"
    is_sword_flight = _is_sword_flight_shot(shot)
    if is_sword_flight:
        source_text = _sword_safe_action_text(source_text)
        action = _sword_safe_action_text(action)
        performance = _sword_safe_action_text(performance)
        camera = (
            "三分之二侧前方跟拍视角，镜头与飞剑同高、略低于人物胸口；"
            "完整人剑入画，人物和飞剑占画面中景，竹冠在下方形成高度感"
        )
        camera_movement = "视频中再做轻微跟拍推进，图片本身只生成稳定完整起始帧"
    sword_block = _sword_flight_prompt_block() if is_sword_flight else ""
    environment_text = (
        _sword_flight_environment_block(environment).replace("场景环境：", "", 1)
        if is_sword_flight
        else environment
        if environment
        else "依据画面内容呈现清晰、可读、与项目风格一致的空间。"
    )
    grid_cells = _grid_cells_for_shot(
        shot,
        source_text=source_text,
        subject=subject,
        action=action,
        camera=camera,
        camera_movement=camera_movement,
        performance=performance,
        environment=environment_text,
    )
    prompt = _compose_grid_prompt(
        shot_id=shot.get("shot_id"),
        environment=environment_text,
        lighting=lighting,
        grid_cells=grid_cells,
        allowed_texts=_allowed_scene_texts(shot),
        sword_block=sword_block,
    )
    return {
        "prompt": prompt,
        "grid_cells": grid_cells,
        "source_text": source_text,
        "subject": subject,
        "environment": environment_text,
        "lighting": lighting,
        "sword_block": sword_block,
    }


def _normal_prompt(shot: dict[str, Any], source_by_micro_id: dict[str, str]) -> str:
    return str(_normal_prompt_payload(shot, source_by_micro_id).get("prompt") or "")


def _boundary_prompt(shot: dict[str, Any]) -> str:
    return "\n".join(
        [
            f"【审核帧 review_frame】{_excerpt(shot.get('title'), 60)}",
            f"用途：{_excerpt(shot.get('action'), 140)}",
            "这不是视频起始帧，只用于确认玩法入口、剧情回归或段落切点是否放在正确位置。",
        ]
    )


def _negative_prompt(shot: dict[str, Any] | None = None) -> str:
    text = _shot_text_blob(shot or {})
    base = (
        "真人摄影、彩色精修大图、油画厚涂、海报构图、复杂背景、文字水印/logo/UI、对白气泡、"
        "多余人物、动作顺序混乱、肢体关系看不清"
    )
    if "飞剑" in text or "御剑" in text:
        return f"{base}、飞剑方向反了、贴地飞行。"
    return f"{base}。"


def _is_generation_boundary(shot: dict[str, Any], *, duration: int) -> bool:
    if bool(shot.get("is_generation_boundary")):
        return True
    return (
        duration <= 0
        or "review_frame" in (shot.get("image_roles") or [])
        and "start_image" not in (shot.get("image_roles") or [])
    )


def build_keyframe_prompt_plan_from_director_shots(
    director_shots: dict[str, Any], story_beats: dict[str, Any] | None = None
) -> dict[str, Any]:
    """Build keyframe prompt plan from ``director_shots.json`` data."""
    episode = _as_int(director_shots.get("episode"), 1)
    prompts: list[dict[str, Any]] = []
    source_shot_count = 0
    source_by_micro_id = _micro_excerpt_map(story_beats)

    for group in director_shots.get("shot_groups") or []:
        for shot in group.get("shots") or []:
            source_shot_count += 1
            shot_id = str(shot.get("shot_id") or f"E{episode}S{source_shot_count:02d}")
            duration = _as_int(shot.get("duration_seconds"), 0)
            is_boundary = _is_generation_boundary(shot, duration=duration)
            role = "review_frame" if is_boundary else "guide_reference"
            normal_payload = {} if is_boundary else _normal_prompt_payload(shot, source_by_micro_id)
            prompts.append(
                {
                    "keyframe_id": f"KF-{shot_id}-{'review' if is_boundary else 'guide'}",
                    "shot_id": shot_id,
                    "role": role,
                    "title": _excerpt(shot.get("title") or shot_id, 60),
                    "image_role_explanation": "9宫格动作引导图，用来告诉视频模型这一镜怎么演，不是最终关键帧。"
                    if role == "guide_reference"
                    else "审核帧，只用于确认结构切点，不提交视频生成。",
                    "prompt": _boundary_prompt(shot) if is_boundary else normal_payload.get("prompt", ""),
                    "negative_prompt": "" if is_boundary else _negative_prompt(shot),
                    "style_policy": _style_policy(),
                    "reference_policy": "不提交视频生成。" if is_boundary else _reference_policy(),
                    "grid_cells": [] if is_boundary else normal_payload.get("grid_cells", []),
                    "optional_reference_roles": [] if is_boundary else ["guide_reference", "asset_reference"],
                    "review_checkpoints": ["切点位置是否正确。"]
                    if is_boundary
                    else _review_checkpoints()
                    + (_sword_flight_review_checkpoints() if _is_sword_flight_shot(shot) else []),
                }
            )

    payload = {
        "schema_version": 1,
        "episode": episode,
        "source_shot_count": source_shot_count,
        "total_duration_seconds": sum(
            _as_int(shot.get("duration_seconds"), 0)
            for group in director_shots.get("shot_groups") or []
            for shot in group.get("shots") or []
        ),
        "prompts": prompts,
    }
    return KeyframePromptPlanModel.model_validate(payload).model_dump()


def _keyframe_system_prompt() -> str:
    return """你是动作引导图提示词模型。你的任务是把导演分镜转换成可提交给图片生成模型的9宫格动作草稿图提示词。

必须遵守：
1. 输出严格 JSON，符合 schema，不要 Markdown。
2. 只为可生成视频的 shot 写 guide_reference 九宫格动作引导图；review_frame 只用于结构审核。
3. 每个 guide_reference 必须先写 grid_cells，严格 9 个格子，cell=1..9，不得省略，不得只写“第1-3格/第4-6格/第7-9格”。
4. 每个 grid_cell 必须包含 phase、visual、acting、body、camera、purpose 六项，但 acting/body 的含义是“画面可见的反应/运动”，不是强制演员露脸或露全身：
   - visual：这一格具体画什么，人物/道具/空间位置要清楚。
   - acting：只写画面中真的看得到的表演/反应；能看见脸时才写眉、眼、嘴、呼吸、停顿；第一人称/道具特写/无脸镜头不得硬写脸部表情，要写焦点停顿、手部反应、道具反应或环境反应。
   - body：只写画面中真的看得到的运动；能看见身体时写手指、手臂、肩颈、重心、脚步；看不到人物时写道具、光影、环境、前景晃动或运动线。
   - camera：景别、机位、焦点、推拉摇移或定机位。
   - purpose：这一格在动作起承转合里的叙事目的。
5. prompt 必须把 9 个 grid_cells 合成为图片生成提示词，标题为“九格连续画面：”，不是剧情摘要。每格只写一行画面短句，不要把 acting/body/camera/purpose 四个字段全量铺开。
6. 如果原分镜只有旁白、台词、内心独白或概念，你必须把它转成可见画面、道具、光影、演员反应或镜头运动，不能原样复制“旁白：……”当画面主体。
7. 如果 director shot 内的表演字段是套话，例如“服务旁白”“B-roll 承接”，必须改写为具体可见动作。
8. 画风固定为黑白素描铅笔画、动画分镜草稿、白底九宫格、少量灰阶阴影；不要精修彩色最终画面。
9. 每格要有明确动作状态：1-2 建立空间和动作准备，3-6 动作发展和情绪变化，7-9 落点/反应/悬念。
10. 人物情绪只在“画面可见”时拆成眉眼、嘴角、肩膀、手臂、手指、身体重心和运动线；第一人称、空镜、道具特写必须改用可见手部/道具/光影/镜头节奏表达。
11. prompt 禁止包含“用途：”“镜头核心：”“主体与道具：”“【9宫格动作引导图...】”这类给人看的说明；直接输出给生图模型看的画面描述。
12. 画面文字必须保守：只有画内真实需要的招牌、系统UI、订单、封面字才可出现；旁白、台词、内心独白、分镜标题不得画成文字。纸张、书页、屏幕、海报如无明确画内文字需求，只能画不可读短横线、灰线、抽象符号块或发光图形。
13. 每条 negative_prompt 必须避免真人照片、彩色精修、油画厚涂、复杂背景、文字水印、动作顺序混乱。
14. 如果镜头包含御剑/飞剑，必须在九宫格里标清飞剑方向、人物双脚接触点、身体重心、剑尖方向和剑柄位置。

输出格式：
{
  "prompts": [
    {
      "keyframe_id": "沿用输入",
      "shot_id": "沿用输入",
      "role": "guide_reference",
      "title": "短标题",
      "image_role_explanation": "9宫格动作引导图，用来告诉视频模型这一镜怎么演，不是最终关键帧。",
      "grid_cells": [
        {"cell": 1, "phase": "建立空间", "visual": "...", "acting": "...", "body": "...", "camera": "...", "purpose": "..."}
      ],
      "prompt": "包含九格连续画面的完整生图提示词，短句，不重复原文，不包含用途/镜头核心/主体与道具等说明行",
      "negative_prompt": "...",
      "style_policy": "...",
      "reference_policy": "...",
      "optional_reference_roles": ["guide_reference", "asset_reference"],
      "review_checkpoints": [...]
    }
  ]
}
"""


def _keyframe_user_prompt(
    director_shots: dict[str, Any],
    story_beats: dict[str, Any] | None,
    *,
    requirements: str,
) -> str:
    return json.dumps(
        {
            "director_shots": director_shots,
            "story_beats": story_beats,
            "requirements": requirements,
        },
        ensure_ascii=False,
    )


def _director_shot_batches(director_shots: dict[str, Any], *, batch_size: int = 8) -> list[dict[str, Any]]:
    """Flatten director shots into small prompt-generation batches."""
    episode = _as_int(director_shots.get("episode"), 1)
    content = {key: value for key, value in director_shots.items() if key != "shot_groups"}
    flat: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for group in director_shots.get("shot_groups") or []:
        if not isinstance(group, dict):
            continue
        group_meta = {key: value for key, value in group.items() if key != "shots"}
        for shot in group.get("shots") or []:
            if isinstance(shot, dict):
                flat.append((group_meta, shot))

    batches: list[dict[str, Any]] = []
    for start in range(0, len(flat), max(1, batch_size)):
        shot_groups: list[dict[str, Any]] = []
        for item_index, (group_meta, shot) in enumerate(flat[start : start + batch_size], start=1):
            shot_groups.append(
                {
                    **group_meta,
                    "group_id": str(group_meta.get("group_id") or f"BATCH{start + item_index:02d}"),
                    "duration_seconds": _as_int(shot.get("duration_seconds"), 0),
                    "shots": [shot],
                }
            )
        batch = dict(content)
        batch["episode"] = episode
        batch["source_shot_count"] = len(shot_groups)
        batch["shot_groups"] = shot_groups
        batches.append(batch)
    return batches


def _normalize_keyframe_prompt(raw: dict[str, Any], fallback_prompt: dict[str, Any]) -> dict[str, Any]:
    prompt = dict(fallback_prompt)
    prompt.update({key: value for key, value in raw.items() if value is not None})
    prompt["keyframe_id"] = str(prompt.get("keyframe_id") or fallback_prompt.get("keyframe_id") or "")
    prompt["shot_id"] = str(prompt.get("shot_id") or fallback_prompt.get("shot_id") or "")
    prompt["role"] = str(prompt.get("role") or fallback_prompt.get("role") or "guide_reference")
    prompt["title"] = _excerpt(prompt.get("title") or fallback_prompt.get("title"), 80)
    prompt["image_role_explanation"] = _clean_text(
        prompt.get("image_role_explanation") or fallback_prompt.get("image_role_explanation")
    )
    raw_grid_cells = _normalize_grid_cells(raw.get("grid_cells") or raw.get("cells"))
    fallback_grid_cells = _normalize_grid_cells(fallback_prompt.get("grid_cells"))
    prompt["grid_cells"] = raw_grid_cells if len(raw_grid_cells) == 9 else fallback_grid_cells
    prompt["prompt"] = _clean_text(prompt.get("prompt") or fallback_prompt.get("prompt"))
    if prompt["role"] == "guide_reference" and prompt["grid_cells"]:
        prompt["prompt"] = _append_grid_cells_to_prompt(prompt["prompt"], prompt["grid_cells"])
    prompt["negative_prompt"] = _clean_text(prompt.get("negative_prompt") or fallback_prompt.get("negative_prompt"))
    fallback_text = str(fallback_prompt.get("prompt") or "")
    if "御剑构图硬约束" in fallback_text and "御剑构图硬约束" not in prompt["prompt"]:
        prompt["prompt"] = f"{prompt['prompt']}\n{_sword_flight_prompt_block()}"
    for required_negative in (
        "油画",
        "厚涂",
        "概念设定稿",
        "粗糙背景",
        "巨型飞剑",
        "脚悬空",
        "站姿不稳",
    ):
        if required_negative not in prompt["negative_prompt"]:
            prompt["negative_prompt"] = f"{prompt['negative_prompt']}、{required_negative}".strip("、")
    prompt["style_policy"] = _clean_text(prompt.get("style_policy") or fallback_prompt.get("style_policy"))
    prompt["reference_policy"] = _clean_text(prompt.get("reference_policy") or fallback_prompt.get("reference_policy"))
    prompt["optional_reference_roles"] = list(
        prompt.get("optional_reference_roles") or fallback_prompt.get("optional_reference_roles") or []
    )
    prompt["review_checkpoints"] = list(prompt.get("review_checkpoints") or fallback_prompt.get("review_checkpoints") or [])
    return prompt


def _normalize_keyframe_plan(raw: dict[str, Any], fallback: dict[str, Any]) -> dict[str, Any]:
    fallback_by_shot = {str(item.get("shot_id") or ""): item for item in fallback.get("prompts") or []}
    fallback_by_id = {str(item.get("keyframe_id") or ""): item for item in fallback.get("prompts") or []}
    prompts: list[dict[str, Any]] = []
    for item in raw.get("prompts") or []:
        if not isinstance(item, dict):
            continue
        fallback_prompt = fallback_by_shot.get(str(item.get("shot_id") or "")) or fallback_by_id.get(
            str(item.get("keyframe_id") or "")
        )
        if fallback_prompt:
            prompts.append(_normalize_keyframe_prompt(item, fallback_prompt))
    if not prompts and isinstance(raw.get("keyframes"), list):
        for index, item in enumerate(raw["keyframes"]):
            if isinstance(item, dict) and index < len(fallback.get("prompts") or []):
                prompts.append(_normalize_keyframe_prompt(item, fallback["prompts"][index]))
    return {
        "schema_version": fallback["schema_version"],
        "episode": fallback["episode"],
        "source_shot_count": fallback["source_shot_count"],
        "total_duration_seconds": fallback["total_duration_seconds"],
        "prompts": prompts,
    }


async def build_keyframe_prompt_plan_from_director_shots_with_text_model(
    director_shots: dict[str, Any],
    story_beats: dict[str, Any] | None = None,
    *,
    project_name: str,
) -> dict[str, Any]:
    """Build keyframe prompts with the configured text model, falling back per batch."""
    fallback = build_keyframe_prompt_plan_from_director_shots(director_shots, story_beats)
    try:
        generator = await TextGenerator.create(TextTaskType.KEYFRAME_PROMPTS, project_name=project_name)
    except Exception as exc:
        logger.warning("关键帧提示词文本模型初始化失败，回退到规则模板: %s", exc)
        return fallback

    fallback_by_shot = {str(item.get("shot_id") or ""): item for item in fallback.get("prompts") or []}
    merged_prompts: list[dict[str, Any]] = []
    consecutive_failures = 0
    for batch_index, batch in enumerate(_director_shot_batches(director_shots, batch_size=8), start=1):
        batch_fallback = build_keyframe_prompt_plan_from_director_shots(batch, story_beats)
        if consecutive_failures >= KEYFRAME_PROMPT_MODEL_FAILURE_BREAKER:
            for item in batch_fallback.get("prompts") or []:
                original = fallback_by_shot.get(str(item.get("shot_id") or ""))
                merged_prompts.append(original or item)
            continue
        try:
            result = await asyncio.wait_for(
                generator.generate(
                    TextGenerationRequest(
                        system_prompt=_keyframe_system_prompt(),
                        prompt=_keyframe_user_prompt(
                            batch,
                            story_beats,
                            requirements="为这批 director_shots 生成 keyframe_prompts.json，只输出本批 prompts，不要漏 shot。",
                        ),
                        max_output_tokens=8000,
                    ),
                    project_name=project_name,
                ),
                timeout=KEYFRAME_PROMPT_MODEL_TIMEOUT_SECONDS,
            )
            batch_plan = _normalize_keyframe_plan(parse_model_json_object(result.text), batch_fallback)
            if not batch_plan.get("prompts"):
                raise ValueError("keyframe prompt model returned empty prompts")
            merged_prompts.extend(batch_plan.get("prompts") or [])
            consecutive_failures = 0
        except Exception as exc:
            logger.warning("关键帧提示词第 %s 批文本模型生成失败，回退该批规则模板: %s", batch_index, exc)
            consecutive_failures += 1
            for item in batch_fallback.get("prompts") or []:
                original = fallback_by_shot.get(str(item.get("shot_id") or ""))
                merged_prompts.append(original or item)

    if not merged_prompts:
        return fallback

    seen: set[str] = set()
    ordered_prompts: list[dict[str, Any]] = []
    for fallback_prompt in fallback.get("prompts") or []:
        shot_id = str(fallback_prompt.get("shot_id") or "")
        match = next((item for item in merged_prompts if str(item.get("shot_id") or "") == shot_id), None)
        selected = match or fallback_prompt
        key = str(selected.get("keyframe_id") or shot_id)
        if key in seen:
            continue
        seen.add(key)
        ordered_prompts.append(selected)

    payload = {
        "schema_version": fallback["schema_version"],
        "episode": fallback["episode"],
        "source_shot_count": fallback["source_shot_count"],
        "total_duration_seconds": fallback["total_duration_seconds"],
        "prompts": ordered_prompts,
    }
    return KeyframePromptPlanModel.model_validate(payload).model_dump()
