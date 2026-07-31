"""Project-type templates for novel/script-to-video preprocessing."""

from __future__ import annotations

import re
from typing import Any

CONTENT_FORMAT_INTERACTIVE = "interactive_drama_game"
CONTENT_FORMAT_AD = "ad"
CONTENT_FORMAT_NARRATIVE = "narrative_video"
CONTENT_FORMAT_NARRATED = "narrated_drama"

DEFAULT_CONTENT_FORMAT = CONTENT_FORMAT_NARRATIVE

PROJECT_TYPE_TEMPLATES: dict[str, dict[str, Any]] = {
    CONTENT_FORMAT_INTERACTIVE: {
        "label": "剧游",
        "focus": "玩法入口、回归剧情、选择点、钩子",
        "beat_functions": [
            "opening_hook",
            "arrival",
            "first_encounter",
            "relationship_shift",
            "choice_setup",
            "gameplay_entry",
            "return_to_story",
            "branch_cliffhanger",
        ],
    },
    CONTENT_FORMAT_AD: {
        "label": "广告",
        "focus": "前 3 秒钩子、痛点、反转、强转化",
        "beat_functions": [
            "attention_hook",
            "pain_or_desire",
            "solution_reveal",
            "reversal",
            "proof_demo",
            "cta",
        ],
    },
    CONTENT_FORMAT_NARRATIVE: {
        "label": "剧情视频",
        "focus": "情绪推进、镜头节奏、人物关系",
        "beat_functions": [
            "opening_hook",
            "setup",
            "inciting_incident",
            "conflict",
            "escalation",
            "reveal",
            "climax",
            "cliffhanger",
        ],
    },
    CONTENT_FORMAT_NARRATED: {
        "label": "解说剧",
        "focus": "旁白信息密度、画面承接、转场节奏",
        "beat_functions": [
            "context_intro",
            "character_intro",
            "cause_effect",
            "contrast",
            "suspense_question",
            "emotional_punch",
            "transition",
        ],
    },
}

_CHOICE_OPTION_RE = re.compile(
    r"(?:选项|选择)?\s*([A-Da-d一二三四1234])\s*[、.．：:]\s*"
    r"([^。！？；;\n]+?)(?=\s*(?:[A-Da-d一二三四1234]\s*[、.．：:]|$|[。！？；;\n]))"
)
_INTERACTIVE_BOUNDARY_KINDS = {"gameplay_entry", "return_to_story", "choice_point"}
_CHOICE_OPTION_IDS = ["A", "B", "C", "D"]


def template_for_format(content_format: str | None) -> dict[str, Any]:
    key = str(content_format or "").strip() or DEFAULT_CONTENT_FORMAT
    return PROJECT_TYPE_TEMPLATES.get(key, PROJECT_TYPE_TEMPLATES[DEFAULT_CONTENT_FORMAT])


def template_summary(content_format: str | None) -> dict[str, Any]:
    key = str(content_format or "").strip() or DEFAULT_CONTENT_FORMAT
    if key not in PROJECT_TYPE_TEMPLATES:
        key = DEFAULT_CONTENT_FORMAT
    template = PROJECT_TYPE_TEMPLATES[key]
    return {
        "content_format": key,
        "label": template["label"],
        "focus": template["focus"],
        "beat_functions": list(template["beat_functions"]),
    }


def detect_content_format(text: str, *, project: dict[str, Any] | None = None) -> str:
    """Detect the preprocessing template from explicit project settings first."""
    raw = str(text or "")
    project = project or {}
    project_type = str(project.get("project_type") or project.get("content_format") or "").strip()
    if project_type in PROJECT_TYPE_TEMPLATES:
        return project_type

    if any(marker in raw for marker in ("进入游戏", "进入玩法", "回归剧情", "选择：", "玩家", "玩法入口")):
        return CONTENT_FORMAT_INTERACTIVE
    if any(marker in raw for marker in ("广告", "下载", "转化", "CTA", "痛点", "前三秒", "前3秒", "视觉锤")):
        return CONTENT_FORMAT_AD
    if any(marker in raw for marker in ("旁白", "解说", "VO：", "voiceover", "字幕：")):
        return CONTENT_FORMAT_NARRATED
    return DEFAULT_CONTENT_FORMAT


def extract_choice_options(text: str) -> list[str]:
    options: list[str] = []
    for match in _CHOICE_OPTION_RE.finditer(str(text or "")):
        value = match.group(2).strip()
        if value and value not in options:
            options.append(value)
    return options


def interactive_kind_for_text(text: str) -> str:
    raw = str(text or "")
    if "进入游戏" in raw or "进入玩法" in raw or "玩法入口" in raw:
        return "gameplay_entry"
    if "回归剧情" in raw:
        return "return_to_story"
    if extract_choice_options(raw) or any(
        marker in raw for marker in ("选择：", "选择:", "玩家选择", "是否", "怎么办")
    ):
        return "choice_point"
    if any(marker in raw for marker in ("结尾钩子", "新人物", "新事件", "悬念", "钩子")):
        return "hook"
    return ""


def is_interactive_boundary(kind: str | None) -> bool:
    return str(kind or "") in _INTERACTIVE_BOUNDARY_KINDS


def interactive_handoff_for_kind(kind: str | None) -> str:
    if kind == "gameplay_entry":
        return "to_gameplay"
    if kind == "return_to_story":
        return "to_story"
    if kind == "choice_point":
        return "to_branch"
    if kind == "hook":
        return "to_next_event"
    return ""


def detect_interactive_nodes(lines: list[str]) -> list[dict[str, Any]]:
    nodes: list[dict[str, Any]] = []
    for line_index, line in enumerate(lines, start=1):
        text = str(line or "").strip()
        if not text:
            continue
        kind = interactive_kind_for_text(text)
        if not kind:
            continue
        nodes.append(
            {
                "node_id": f"I{len(nodes) + 1:02d}",
                "line": line_index,
                "kind": kind,
                "text": text,
                "options": extract_choice_options(text),
                "handoff": interactive_handoff_for_kind(kind),
            }
        )
    return nodes


def choice_points_from_interactive_nodes(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    choice_points: list[dict[str, Any]] = []
    for node in nodes:
        if node.get("kind") != "choice_point":
            continue
        choice_id = f"C{len(choice_points) + 1:02d}"
        options = []
        for index, label in enumerate(list(node.get("options") or [])[: len(_CHOICE_OPTION_IDS)]):
            option_id = _CHOICE_OPTION_IDS[index]
            options.append(
                {
                    "option_id": f"{choice_id}-{option_id}",
                    "label": str(label),
                    "branch_key": f"branch_{option_id.lower()}",
                    "next_hint": "",
                }
            )
        choice_points.append(
            {
                "choice_id": choice_id,
                "source_node_id": str(node.get("node_id") or ""),
                "line": int(node.get("line") or 0),
                "prompt": str(node.get("text") or ""),
                "options": options,
                "handoff": "to_branch",
            }
        )
    return choice_points


def beat_function_for_index(content_format: str | None, index: int, total: int) -> str:
    functions = template_for_format(content_format)["beat_functions"]
    if not functions:
        return "development"
    if content_format == CONTENT_FORMAT_AD:
        if index <= len(functions):
            return functions[index - 1]
        return functions[-1]
    if index == 1:
        return functions[0]
    if total > 1 and index == total:
        return functions[-1]
    middle = functions[1:-1] or functions
    return middle[(index - 2) % len(middle)]
