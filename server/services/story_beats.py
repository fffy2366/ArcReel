"""Stage-2 story-beat planning helpers.

This first product slice turns the existing story import analysis into a
reviewable beat plan. It is intentionally deterministic; LLM/skill-backed
expansion can be added after the UI contract is proven.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import BaseModel, Field

from lib.text_backends.base import TextGenerationRequest, TextTaskType
from lib.text_generator import TextGenerator
from lib.video_duration import coerce_video_duration
from server.services.project_type_templates import (
    CONTENT_FORMAT_AD,
    CONTENT_FORMAT_INTERACTIVE,
    CONTENT_FORMAT_NARRATED,
    DEFAULT_CONTENT_FORMAT,
    beat_function_for_index,
    choice_points_from_interactive_nodes,
    extract_choice_options,
    interactive_handoff_for_kind,
    interactive_kind_for_text,
    is_interactive_boundary,
    template_summary,
)
from server.services.text_model_json import parse_model_json_object

logger = logging.getLogger(__name__)


class StoryMicroBeatModel(BaseModel):
    micro_id: str
    title: str
    dramatic_value: str = ""
    source_excerpt: str = ""
    estimated_seconds: int = 4
    interaction_role: str = ""
    choice_point_id: str = ""
    choice_options: list[str] = Field(default_factory=list)
    handoff: str = ""
    director_context: str = ""


class StoryBeatModel(BaseModel):
    beat_id: str
    title: str
    story_function: str = ""
    summary: str = ""
    source_excerpt: str = ""
    estimated_seconds: int = 0
    interaction_role: str = ""
    choice_point_id: str = ""
    choice_options: list[str] = Field(default_factory=list)
    handoff: str = ""
    micro_beats: list[StoryMicroBeatModel] = Field(default_factory=list)


class StoryBeatChoiceOptionModel(BaseModel):
    option_id: str
    label: str
    branch_key: str
    next_hint: str = ""


class StoryBeatChoicePointModel(BaseModel):
    choice_id: str
    source_node_id: str = ""
    line: int = 0
    prompt: str
    options: list[StoryBeatChoiceOptionModel] = Field(default_factory=list)
    handoff: str = "to_branch"


class StoryBeatPlanModel(BaseModel):
    schema_version: int = 1
    episode: int
    content_format: str = DEFAULT_CONTENT_FORMAT
    template_name: str = "剧情视频"
    template_focus: str = "情绪推进、镜头节奏、人物关系"
    format_profile: dict[str, Any] = Field(default_factory=dict)
    source_filename: str | None = None
    source_summary: str = ""
    total_estimated_seconds: int = 0
    choice_points: list[StoryBeatChoicePointModel] = Field(default_factory=list)
    beats: list[StoryBeatModel] = Field(default_factory=list)


def _excerpt(text: str, limit: int = 80) -> str:
    compact = re.sub(r"\s+", " ", str(text or "")).strip()
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _full_source_excerpt(text: Any) -> str:
    return re.sub(r"\s+", " ", str(text or "")).strip()


_PUNCTUATION_FRAGMENT_RE = re.compile(r"^[`'\"“”‘’…,.，。！？!?；;:：、\s]+$")


def _clean_source_for_sentences(text: str) -> str:
    """Remove authoring markup that should never become a video beat.

    Source text can contain Markdown fences around order/UI blocks. The fence
    itself is not story content; if we keep it, downstream director shots become
    unusable fragments such as "```text" or "”".
    """
    value = str(text or "")
    value = re.sub(r"(?m)^\s*```[A-Za-z0-9_-]*\s*$", "", value)
    value = value.replace("```text", "").replace("```", "")
    return value.strip()


def _is_punctuation_fragment(text: str) -> bool:
    return bool(_PUNCTUATION_FRAGMENT_RE.fullmatch(str(text or "").strip()))


def _sentences(text: str) -> list[str]:
    cleaned = _clean_source_for_sentences(str(text or ""))
    raw_chunks = [chunk.strip() for chunk in re.split(r"(?<=[。！？!?；;])", cleaned) if chunk.strip()]
    merged: list[str] = []
    pending = ""

    for raw in raw_chunks:
        chunk = raw.strip()
        if not chunk:
            continue
        if not pending:
            chunk = chunk.lstrip("，,、；;。！？!? ")
        if _is_punctuation_fragment(chunk):
            if pending and "”" in chunk:
                pending = f"{pending}{chunk}"
            continue

        if pending:
            pending = f"{pending}{chunk}"
        else:
            pending = chunk

        # Keep quoted dialogue together. A video shot should receive the full
        # spoken beat, not "你到底到哪了？" / "飞剑课马上点名..." / "”" as
        # three unrelated shots.
        if pending.count("“") > pending.count("”"):
            continue

        normalized = pending.strip()
        pending = ""
        if normalized and not _is_punctuation_fragment(normalized):
            merged.append(normalized)

    if pending.strip() and not _is_punctuation_fragment(pending):
        merged.append(pending.strip())

    return merged or ([cleaned] if cleaned else [])


def _director_instruction_payload(text: str) -> str:
    value = _visual_text_without_director_prefix(str(text or ""))
    value = re.sub(r"分镜\s*\d+(?:[（(][^）)]*[）)])?", "", value)
    value = re.sub(r"\b\d+\s*[-~—至到]\s*\d+\s*s\b", "", value, flags=re.IGNORECASE)
    value = re.sub(r"(特写|近景|中景|远景|全景|大全景|插入镜头|说明性镜头|主观机位|平视|俯视|仰视|至|到)", "", value)
    value = re.sub(r"(男主)?第一人称视角|主观视角|POV|混剪回忆|回忆混剪", "", value, flags=re.IGNORECASE)
    value = re.sub(r"[\s|｜+＋/、，,。；;:：\-—（）()【】\[\]]+", "", value)
    return value.strip()


def _visual_text_without_director_prefix(text: str) -> str:
    value = _clean_source_for_sentences(str(text or "")).strip()
    if not value:
        return ""
    if value.startswith(("旁白", "男主内心", "【男主内心")):
        for pattern in (
            r"回归现实\s*[:：]",
            r"就在",
            r"桌上",
            r"只见",
            r"镜头",
            r"画面",
            r"窗外",
        ):
            match = re.search(pattern, value)
            if match and match.start() > 0:
                return _strip_visual_director_markers(value[match.start() :])
        return ""
    visual_patterns = [
        r"回忆画面\s*\d+\s*[:：]?",
        r"回归现实\s*[:：]",
        r"【男主内心(?:独白|吐槽)】",
        r"男主内心(?:独白|吐槽)\s*[:：]",
        r"窗户渐显",
        r"旭日东升",
        r"镜头骤然",
        r"男主顺着",
        r"就在",
        r"窗外",
        r"桌上",
        r"只见",
    ]
    if value.startswith(("旁白", "男主内心", "【男主内心")):
        for pattern in visual_patterns:
            match = re.search(pattern, value)
            if match:
                return _strip_visual_director_markers(value[match.start() :])
    if any(marker in value for marker in ("分镜", "第一人称视角", "主观视角", "POV")):
        for pattern in visual_patterns:
            match = re.search(pattern, value)
            if match and match.start() > 0:
                prefix = value[: match.start()]
                if any(marker in prefix for marker in ("分镜", "第一人称视角", "主观视角", "POV", "特写", "近景", "中景")):
                    return _strip_visual_director_markers(value[match.start() :])
    return _strip_visual_director_markers(value)


def _strip_visual_director_markers(text: str) -> str:
    value = str(text or "").strip(" ，,。；;")
    value = re.sub(r"(?:男主)?第一人称视角", "", value)
    value = re.sub(r"主观视角|POV", "", value, flags=re.IGNORECASE)
    value = re.sub(r"\s*[+＋｜|、]\s*$", "", value)
    value = re.sub(r"\s+", " ", value)
    return value.strip(" ，,。；;")


def _director_context_from_text(text: str) -> str:
    value = _clean_source_for_sentences(str(text or "")).strip()
    visual = _visual_text_without_director_prefix(value)
    context = ""
    if visual and value != visual and value.endswith(visual):
        context = value[: len(value) - len(visual)].strip(" ，,。；;")
    if not context and _is_director_instruction_fragment(value):
        context = value
    return _excerpt(context, 120) if context else ""


def _strip_narration_prefix(text: str) -> str:
    value = _clean_source_for_sentences(str(text or "")).strip()
    value = _visual_text_without_director_prefix(value)
    value = re.sub(r"^旁白\s*[:：]\s*", "", value)
    value = re.sub(r"^男主内心(?:独白|吐槽)\s*[:：]\s*", "", value)
    value = re.sub(r"^【男主内心(?:独白|吐槽)】\s*", "", value)
    value = re.sub(r"^不是[……\.\.\.]\s*", "", value)
    return value.strip()


def _is_sound_effect_fragment(text: str) -> bool:
    value = _clean_source_for_sentences(str(text or "")).strip()
    if not value:
        return False
    if value.startswith(("【音效】", "音效：", "音效:", "【音效")):
        return True
    if value.startswith("伴随着") and any(marker in value for marker in ("声", "音", "BGM", "音乐")):
        return True
    return False


def _dialogue_context_from_text(text: str) -> str:
    value = _clean_source_for_sentences(str(text or "")).strip()
    snippets = re.findall(r"(?:【[^】]{1,12}】\s*)?[\w\u4e00-\u9fff]{0,8}[：:]?\s*“[^”]{1,160}”", value)
    return " ".join(snippet.strip() for snippet in snippets)


def _remove_dialogue_text(text: str) -> str:
    value = _clean_source_for_sentences(str(text or "")).strip()
    value = re.sub(r"【[^】]{1,12}】\s*“[^”]{1,200}”", "", value)
    value = re.sub(r"[：:]\s*“[^”]{1,200}”", "", value)
    value = re.sub(r"[，,。；;：:]?\s*(语气[^：:。；;]*|温柔调侃道|娇嗔道|说道|说完|冲镜头一指)", "", value)
    value = re.sub(r"\s+", " ", value).strip(" ，,。；;")
    return value


def _is_dialogue_only_fragment(text: str) -> bool:
    value = _clean_source_for_sentences(str(text or "")).strip()
    if "“" not in value or "”" not in value:
        return False
    visual = _remove_dialogue_text(value)
    return not _has_concrete_visual_event(visual)


def _is_narration_only_fragment(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    visible_raw = _visual_text_without_director_prefix(raw)
    starts_as_narration = (
        raw.startswith("旁白")
        or raw.startswith("男主内心")
        or raw.startswith("【男主内心")
        or visible_raw.startswith("旁白")
        or visible_raw.startswith("男主内心")
        or visible_raw.startswith("【男主内心")
        or bool(re.match(r"^(不是|靠)[……\.\.\.]", visible_raw))
    )
    if not starts_as_narration:
        return False
    visual = _visual_text_without_director_prefix(raw)
    if visual and visual != raw and _has_concrete_visual_event(visual):
        return False
    if starts_as_narration:
        return True
    stripped = _strip_narration_prefix(raw)
    if "“" in stripped or "”" in stripped:
        # Narration + dialogue + sound-effect lines are usually performance
        # notes for the current/previous visual action, not a standalone shot.
        return True
    visual_markers = (
        "镜头",
        "画面",
        "桌",
        "窗",
        "手",
        "眼",
        "脸",
        "走",
        "伸",
        "拿",
        "递",
        "摇",
        "喷",
        "骑",
        "踩",
        "金光",
        "系统",
        "计划书",
        "奶茶",
        "机车",
        "衬衫",
        "酒桌",
    )
    return not any(marker in stripped for marker in visual_markers)


def _has_concrete_visual_event(text: str) -> bool:
    value = _strip_narration_prefix(text)
    if not value or _is_punctuation_fragment(value):
        return False
    concrete_markers = (
        "回忆画面",
        "回归现实",
        "窗户",
        "旭日",
        "晨光",
        "镜头",
        "画面",
        "桌",
        "窗",
        "手",
        "眼",
        "脸",
        "传音",
        "玉简",
        "天命",
        "碎片",
        "裂纹",
        "暗处",
        "窥视",
        "低头",
        "放下",
        "走",
        "伸",
        "拿",
        "递",
        "摇",
        "喷",
        "骑",
        "踩",
        "跪",
        "笑",
        "金光",
        "浮现",
        "界面",
        "计划书",
        "奶茶",
        "机车",
        "衬衫",
        "酒桌",
        "咖啡",
        "杯",
        "林予曦：",
    )
    return any(marker in value for marker in concrete_markers)


def _is_abstract_narration_fragment(text: str) -> bool:
    value = _strip_narration_prefix(text)
    if not value or _is_punctuation_fragment(value):
        return True
    raw = str(text or "").strip()
    has_narration_marker = raw.startswith("旁白") or raw.startswith("男主内心") or raw.startswith("【男主内心")
    abstract_starts = (
        "靠着",
        "不过",
        "讲道理",
        "说实话",
        "这写的是什么",
        "这分明是",
        "不是",
        "靠",
    )
    if value.startswith(abstract_starts):
        return not any(marker in value for marker in ("镜头", "画面", "桌", "手", "低头", "金光", "浮现", "界面"))
    return has_narration_marker and not _has_concrete_visual_event(value)


def _is_director_instruction_fragment(text: str) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    has_instruction_marker = any(marker in raw for marker in ("分镜", "第一人称视角", "主观视角", "POV", "混剪回忆", "回忆混剪"))
    return has_instruction_marker and len(_director_instruction_payload(raw)) < 2


def _prepend_instruction_context(text: Any, context: str, *, limit: int) -> str:
    source = str(text or "").strip()
    ctx = re.sub(r"\s+", " ", str(context or "")).strip()
    if not ctx:
        return _excerpt(source, limit)
    if source.startswith(ctx):
        return _excerpt(source, limit)
    return _excerpt(f"{ctx} {source}".strip(), limit)


def _attach_director_context(micro: dict[str, Any], context: str) -> dict[str, Any]:
    next_micro = dict(micro)
    existing = str(next_micro.get("director_context") or "").strip()
    ctx = " ".join(item for item in [existing, str(context or "").strip()] if item).strip()
    if ctx:
        next_micro["director_context"] = _excerpt(ctx, 160)
    return next_micro


def _fold_instruction_micro_beats(micro_beats: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], str]:
    folded: list[dict[str, Any]] = []
    pending_instructions: list[str] = []
    for micro in micro_beats:
        if not isinstance(micro, dict):
            continue
        source = str(micro.get("source_excerpt") or micro.get("title") or "").strip()
        if _is_sound_effect_fragment(source) or _is_dialogue_only_fragment(source):
            if folded:
                folded[-1] = _attach_director_context(folded[-1], source)
            else:
                pending_instructions.append(source)
            continue
        if (
            _is_director_instruction_fragment(source)
            or _is_narration_only_fragment(source)
            or _is_abstract_narration_fragment(source)
        ):
            pending_instructions.append(source)
            continue
        next_micro = dict(micro)
        source_without_dialogue = (
            source
            if "“" in source and "”" in source and any(marker in source for marker in ("传音", "声音", "画外音"))
            else _remove_dialogue_text(source)
            if "“" in source and "”" in source
            else source
        )
        visual_source = _visual_text_without_director_prefix(source_without_dialogue)
        dialogue_context = _dialogue_context_from_text(source)
        director_context = " ".join(
            item for item in [_director_context_from_text(source), dialogue_context] if item
        ).strip()
        if visual_source and visual_source != source:
            next_micro["source_excerpt"] = _full_source_excerpt(visual_source)
            next_micro["title"] = _excerpt(visual_source, 32)
            next_micro = _attach_director_context(next_micro, director_context)
        if pending_instructions:
            context = " ".join(pending_instructions)
            next_micro = _attach_director_context(next_micro, context)
            pending_instructions.clear()
        folded.append(next_micro)
    return folded, " ".join(pending_instructions).strip()


def normalize_story_beat_plan_for_director(plan: dict[str, Any]) -> dict[str, Any]:
    """Fold pure camera/viewpoint instruction beats into the next visual beat.

    Some scripts contain authoring lines like "分镜2｜第一人称视角＋混剪回忆"
    followed by the actual picture line. Those lines are not shots and should
    not receive their own 9-grid or video task; they are context for the next
    visual beat.
    """
    normalized = dict(plan or {})
    beats: list[dict[str, Any]] = []
    pending_context: list[str] = []
    for raw_beat in normalized.get("beats") or []:
        if not isinstance(raw_beat, dict):
            continue
        beat = dict(raw_beat)
        micro_beats, trailing_context = _fold_instruction_micro_beats(
            [micro for micro in beat.get("micro_beats") or [] if isinstance(micro, dict)]
        )
        beat_context = str(beat.get("source_excerpt") or beat.get("summary") or beat.get("title") or "").strip()
        is_narration_context = bool(trailing_context) and _is_narration_only_fragment(trailing_context)
        is_instruction_only_beat = not micro_beats and (
            bool(trailing_context) or _is_director_instruction_fragment(beat_context) or _is_narration_only_fragment(beat_context)
        )
        if is_instruction_only_beat:
            context = trailing_context or beat_context
            if is_narration_context and beats and beats[-1].get("micro_beats"):
                previous_beat = dict(beats[-1])
                previous_micros = [dict(item) for item in previous_beat.get("micro_beats") or []]
                previous_micros[-1] = _attach_director_context(previous_micros[-1], context)
                previous_beat["micro_beats"] = previous_micros
                beats[-1] = previous_beat
            else:
                pending_context.append(context)
            continue
        if pending_context and micro_beats:
            context = " ".join(pending_context)
            first_micro = _attach_director_context(dict(micro_beats[0]), context)
            micro_beats[0] = first_micro
            pending_context.clear()
        beat["micro_beats"] = micro_beats
        beat["estimated_seconds"] = sum(int(item.get("estimated_seconds") or 0) for item in micro_beats)
        beats.append(beat)
    normalized["beats"] = beats
    normalized["total_estimated_seconds"] = sum(int(beat.get("estimated_seconds") or 0) for beat in beats)
    return normalized


def _duration_for_micro(content_format: str, text: str) -> int:
    if content_format == CONTENT_FORMAT_AD:
        return 3
    if content_format == CONTENT_FORMAT_NARRATED:
        return coerce_video_duration(min(6, round(len(text) / 5)))
    return 5


def _dramatic_value_for_micro(content_format: str, index: int, total: int, text: str) -> str:
    if "进入游戏" in text or "进入玩法" in text:
        return "gameplay_entry"
    if "回归剧情" in text:
        return "return_to_story"
    if content_format == CONTENT_FORMAT_INTERACTIVE and any(marker in text for marker in ("选择", "怎么办", "是否")):
        return "choice_setup"
    return beat_function_for_index(content_format, index, total)


def _interactive_fields_for_text(content_format: str, text: str, *, fallback_kind: str = "") -> dict[str, Any]:
    kind = fallback_kind or (interactive_kind_for_text(text) if content_format == CONTENT_FORMAT_INTERACTIVE else "")
    if not kind:
        return {"interaction_role": "", "choice_options": [], "handoff": ""}
    return {
        "interaction_role": kind,
        "choice_options": extract_choice_options(text),
        "handoff": interactive_handoff_for_kind(kind),
    }


def _primary_interactive_fields(micro_beats: list[dict[str, Any]]) -> dict[str, Any]:
    for micro in micro_beats:
        role = str(micro.get("interaction_role") or "")
        if role:
            return {
                "interaction_role": role,
                "choice_point_id": str(micro.get("choice_point_id") or ""),
                "choice_options": list(micro.get("choice_options") or []),
                "handoff": str(micro.get("handoff") or ""),
            }
    return {"interaction_role": "", "choice_point_id": "", "choice_options": [], "handoff": ""}


def _micro_beats_for_source(beat_id: str, source: str, *, content_format: str) -> list[dict[str, Any]]:
    sentences = _sentences(source)
    if not sentences:
        return []
    result: list[dict[str, Any]] = []
    for index, sentence in enumerate(sentences, start=1):
        dramatic_value = _dramatic_value_for_micro(content_format, index, len(sentences), sentence)
        interactive_fields = _interactive_fields_for_text(content_format, sentence)
        estimated_seconds = (
            0
            if is_interactive_boundary(interactive_fields["interaction_role"])
            else _duration_for_micro(
                content_format,
                sentence,
            )
        )
        result.append(
            {
                "micro_id": f"{beat_id}.{index}",
                "title": _excerpt(sentence, 32),
                "dramatic_value": dramatic_value,
                "source_excerpt": _full_source_excerpt(sentence),
                "estimated_seconds": estimated_seconds,
                **interactive_fields,
            }
        )
    return result


def _interactive_nodes_from_analysis(analysis: dict[str, Any]) -> list[dict[str, Any]]:
    raw_nodes = analysis.get("interactive_nodes") or analysis.get("gameplay_markers") or []
    nodes: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_nodes, start=1):
        text = str(raw.get("text") or raw.get("title") or "").strip()
        kind = str(raw.get("kind") or interactive_kind_for_text(text) or "").strip()
        if not text or not kind:
            continue
        nodes.append(
            {
                "node_id": str(raw.get("node_id") or f"I{index:02d}"),
                "line": int(raw.get("line") or 0),
                "kind": kind,
                "text": text,
                "options": list(raw.get("options") or extract_choice_options(text)),
                "handoff": str(raw.get("handoff") or interactive_handoff_for_kind(kind)),
            }
        )
    return nodes


def _choice_points_from_analysis(analysis: dict[str, Any], nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    raw_points = analysis.get("choice_points")
    if isinstance(raw_points, list) and raw_points:
        return raw_points
    return choice_points_from_interactive_nodes(nodes)


def _interactive_node_summary(kind: str) -> str:
    if kind == "gameplay_entry":
        return "玩法入口边界，用于从剧情镜头切入可交互玩法。"
    if kind == "return_to_story":
        return "回归剧情边界，用于从玩法结果切回剧情镜头。"
    if kind == "choice_point":
        return "选择点边界，玩家在这里分支，剧情视频不默认继续合并生成。"
    if kind == "hook":
        return "剧游钩子镜头，用于把玩家带向下一选择或新事件。"
    return "剧游交互节点。"


def _beat_for_interactive_node(beat_id: str, node: dict[str, Any], *, choice_point_id: str = "") -> dict[str, Any]:
    kind = str(node.get("kind") or "")
    text = str(node.get("text") or kind)
    options = list(node.get("options") or [])
    handoff = str(node.get("handoff") or interactive_handoff_for_kind(kind))
    is_boundary = is_interactive_boundary(kind)
    duration = 0 if is_boundary else 4
    dramatic_value = "boundary_marker" if is_boundary else "branch_cliffhanger"
    return {
        "beat_id": beat_id,
        "title": _excerpt(text, 42),
        "story_function": kind,
        "summary": _interactive_node_summary(kind),
        "source_excerpt": _full_source_excerpt(text),
        "estimated_seconds": duration,
        "interaction_role": kind,
        "choice_point_id": choice_point_id,
        "choice_options": options,
        "handoff": handoff,
        "micro_beats": [
            {
                "micro_id": f"{beat_id}.1",
                "title": _excerpt(text, 32),
                "dramatic_value": dramatic_value,
                "source_excerpt": _full_source_excerpt(text),
                "estimated_seconds": duration,
                "interaction_role": kind,
                "choice_point_id": choice_point_id,
                "choice_options": options,
                "handoff": handoff,
            }
        ],
    }


def build_story_beat_plan_from_analysis(analysis: dict[str, Any]) -> dict[str, Any]:
    """Build a reviewable story-beat plan from ``story_analysis.json`` data."""
    raw_beats = analysis.get("story_beats") or []
    content_format = str(analysis.get("content_format") or DEFAULT_CONTENT_FORMAT)
    template = template_summary(content_format)
    content_format = template["content_format"]
    interactive_nodes = _interactive_nodes_from_analysis(analysis)
    choice_points = _choice_points_from_analysis(analysis, interactive_nodes)
    choice_id_by_node_id = {
        str(choice.get("source_node_id") or ""): str(choice.get("choice_id") or "")
        for choice in choice_points
        if choice.get("source_node_id")
    }
    beats: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_beats, start=1):
        beat_id = str(raw.get("beat_id") or f"B{index:02d}")
        source_excerpt = str(raw.get("source_excerpt") or raw.get("title") or "")
        micro_beats = _micro_beats_for_source(beat_id, source_excerpt, content_format=content_format)
        estimated = sum(int(item.get("estimated_seconds") or 0) for item in micro_beats)
        interactive_fields = _primary_interactive_fields(micro_beats)
        beats.append(
            {
                "beat_id": beat_id,
                "title": _excerpt(raw.get("title") or source_excerpt or f"剧情节拍 {index}", 42),
                "story_function": str(
                    raw.get("story_function") or beat_function_for_index(content_format, index, len(raw_beats))
                ),
                "summary": _excerpt(source_excerpt, 120),
                "source_excerpt": _full_source_excerpt(source_excerpt),
                "estimated_seconds": estimated,
                **interactive_fields,
                "micro_beats": micro_beats,
            }
        )

    existing_interactive_keys = {
        (str(beat.get("interaction_role") or ""), str(beat.get("source_excerpt") or "").strip()) for beat in beats
    }
    missing_interactive_nodes = [
        node
        for node in interactive_nodes
        if (str(node.get("kind") or ""), str(node.get("text") or "").strip()) not in existing_interactive_keys
    ]
    marker_start = len(beats) + 1
    for offset, node in enumerate(missing_interactive_nodes, start=0):
        choice_point_id = choice_id_by_node_id.get(str(node.get("node_id") or ""), "")
        beats.append(_beat_for_interactive_node(f"B{marker_start + offset:02d}", node, choice_point_id=choice_point_id))

    payload = normalize_story_beat_plan_for_director(
        {
        "schema_version": 1,
        "episode": int(analysis.get("episode") or 1),
        "content_format": content_format,
        "template_name": template["label"],
        "template_focus": template["focus"],
        "format_profile": template,
        "source_filename": analysis.get("source_filename"),
        "source_summary": str(analysis.get("summary") or ""),
        "total_estimated_seconds": sum(int(item.get("estimated_seconds") or 0) for item in beats),
        "choice_points": choice_points,
        "beats": beats,
        }
    )
    return StoryBeatPlanModel.model_validate(payload).model_dump()


def _story_beat_system_prompt() -> str:
    return """你是剧情节拍拆分模型。你的任务是把小说/剧本分析结果拆成适合影片生成的剧情节拍和微节拍。

必须遵守：
1. 输出严格 JSON，符合 schema，不要 Markdown。
2. 保留原文 source_excerpt，不要只写摘要。
3. 微节拍要足够细，每个真实生成的 micro_beat 通常对应不少于 5 秒的可视画面。
4. 玩法入口、回归剧情、选择点必须作为边界节点保留，duration 可为 0。
5. 不要跳过配送路途、危险感、停顿、细腻表演等短画面。
6. estimated_seconds 要服务视频模型可控性，长动作拆短。
"""


async def build_story_beat_plan_from_analysis_with_text_model(
    analysis: dict[str, Any],
    *,
    project_name: str,
) -> dict[str, Any]:
    """Build story beats with the configured text model, falling back to deterministic output."""
    fallback = build_story_beat_plan_from_analysis(analysis)
    try:
        generator = await TextGenerator.create(TextTaskType.STORY_BEATS, project_name=project_name)
        result = await generator.generate(
            TextGenerationRequest(
                system_prompt=_story_beat_system_prompt(),
                prompt=json.dumps(
                    {
                        "story_analysis": analysis,
                        "requirements": "生成完整 story_beats.json，不能遗漏原文段落和交互边界。",
                    },
                    ensure_ascii=False,
                ),
                max_output_tokens=24000,
            ),
            project_name=project_name,
        )
        raw = parse_model_json_object(result.text)
        plan = StoryBeatPlanModel.model_validate(raw).model_dump()
        if not plan.get("beats"):
            raise ValueError("story beat model returned empty beats")
        plan["episode"] = fallback["episode"]
        plan["content_format"] = plan.get("content_format") or fallback["content_format"]
        plan["template_name"] = plan.get("template_name") or fallback["template_name"]
        plan["template_focus"] = plan.get("template_focus") or fallback["template_focus"]
        plan["format_profile"] = plan.get("format_profile") or fallback["format_profile"]
        plan["source_filename"] = fallback["source_filename"]
        plan["source_summary"] = plan.get("source_summary") or fallback["source_summary"]
        plan["choice_points"] = plan.get("choice_points") or fallback["choice_points"]
        plan = normalize_story_beat_plan_for_director(plan)
        return StoryBeatPlanModel.model_validate(plan).model_dump()
    except Exception as exc:
        logger.warning("剧情节拍文本模型生成失败，回退到规则模板: %s", exc)
        return fallback
