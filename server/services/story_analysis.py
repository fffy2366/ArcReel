"""Stage-1 story import analysis helpers.

This is a deterministic first-pass analyzer. It creates the product data
contract for "导入小说 / 剧本" before we wire in an LLM/skill runner.
"""

from __future__ import annotations

import json
import logging
import re
from collections import Counter
from collections.abc import Awaitable, Callable
from typing import Any

from pydantic import BaseModel, Field

from lib.text_backends.base import TextGenerationRequest, TextTaskType
from lib.text_generator import TextGenerator
from server.services.project_type_templates import (
    CONTENT_FORMAT_INTERACTIVE,
    DEFAULT_CONTENT_FORMAT,
    beat_function_for_index,
    choice_points_from_interactive_nodes,
    detect_content_format,
    detect_interactive_nodes,
    extract_choice_options,
    interactive_handoff_for_kind,
    interactive_kind_for_text,
    template_summary,
)

logger = logging.getLogger(__name__)


_COMMON_PROP_NAMES = [
    "商业计划书",
    "计划书",
    "咖啡",
    "热咖啡",
    "奶茶",
    "雪克壶",
    "易拉罐",
    "啤酒易拉罐",
    "重型机车",
    "机车",
    "晨袍",
    "居家晨袍",
    "男士oversize纯白衬衫",
    "纯白衬衫",
    "香烟",
    "烟",
    "灵符",
    "飞剑",
    "丹药",
    "丹炉",
    "玉佩",
    "手机",
    "订单",
    "伞",
    "剑",
]

_SCENE_KEYWORDS = {
    "小巷": ["小巷", "巷"],
    "小吃街": ["小吃街"],
    "桃花源": ["桃花源"],
    "医馆": ["医馆"],
    "山道": ["山道", "山路"],
    "洞府": ["洞府"],
    "龙宫": ["龙宫"],
    "雨夜街道": ["雨夜", "雨后", "街道"],
    "居家房间": ["房间", "居家", "晨袍", "窗户", "书桌"],
    "清晨书桌": ["清晨", "书桌", "桌面", "商业计划书"],
    "夜市": ["夜市"],
    "相馆": ["相馆"],
    "奶茶店": ["奶茶"],
    "机车道路": ["机车", "狂飙"],
}


class StoryAnalysisNamedItem(BaseModel):
    name: str
    evidence_count: int = 1
    source: str = "llm"
    description: str = ""


class StoryAnalysisBeat(BaseModel):
    beat_id: str
    title: str
    story_function: str = ""
    source_excerpt: str = ""


class StoryAnalysisHardPoint(BaseModel):
    type: str
    label: str
    reason: str = ""


class StoryAnalysisGameplayMarker(BaseModel):
    line: int = 0
    kind: str
    text: str


class StoryAnalysisInteractiveNode(BaseModel):
    node_id: str
    line: int = 0
    kind: str
    text: str
    options: list[str] = Field(default_factory=list)
    handoff: str = ""


class StoryAnalysisChoiceOption(BaseModel):
    option_id: str
    label: str
    branch_key: str
    next_hint: str = ""


class StoryAnalysisChoicePoint(BaseModel):
    choice_id: str
    source_node_id: str = ""
    line: int = 0
    prompt: str
    options: list[StoryAnalysisChoiceOption] = Field(default_factory=list)
    handoff: str = "to_branch"


class StoryImportAnalysisModel(BaseModel):
    schema_version: int = 1
    episode: int
    source_filename: str | None = None
    content_format: str = DEFAULT_CONTENT_FORMAT
    template_name: str = "剧情视频"
    template_focus: str = "情绪推进、镜头节奏、人物关系"
    format_profile: dict[str, Any] = Field(default_factory=dict)
    summary: str = ""
    story_beats: list[StoryAnalysisBeat] = Field(default_factory=list)
    characters: list[StoryAnalysisNamedItem] = Field(default_factory=list)
    scenes: list[StoryAnalysisNamedItem] = Field(default_factory=list)
    props: list[StoryAnalysisNamedItem] = Field(default_factory=list)
    hard_points: list[StoryAnalysisHardPoint] = Field(default_factory=list)
    gameplay_markers: list[StoryAnalysisGameplayMarker] = Field(default_factory=list)
    interactive_nodes: list[StoryAnalysisInteractiveNode] = Field(default_factory=list)
    choice_points: list[StoryAnalysisChoicePoint] = Field(default_factory=list)


class StoryAssetInventoryModel(BaseModel):
    characters: list[StoryAnalysisNamedItem] = Field(default_factory=list)
    scenes: list[StoryAnalysisNamedItem] = Field(default_factory=list)
    props: list[StoryAnalysisNamedItem] = Field(default_factory=list)


def _paragraphs(text: str) -> list[str]:
    chunks = [p.strip() for p in re.split(r"\n\s*\n|(?<=。)\s*\n", text) if p.strip()]
    if chunks:
        return chunks
    stripped = text.strip()
    return [stripped] if stripped else []


def _excerpt(text: str, limit: int = 90) -> str:
    compact = re.sub(r"\s+", " ", text).strip()
    return compact if len(compact) <= limit else compact[: limit - 1] + "…"


def _full_source_excerpt(text: str) -> str:
    """Keep source evidence intact for downstream directing."""
    return re.sub(r"\s+", " ", str(text or "")).strip()


def _extract_registered_assets(text: str, bucket: dict[str, Any]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for name in sorted(bucket):
        count = text.count(name)
        if count:
            data = bucket.get(name) or {}
            result.append(
                {
                    "name": name,
                    "evidence_count": count,
                    "source": "project",
                    "description": str(data.get("description") or ""),
                }
            )
    return result


_COMMON_SURNAME_CHARS = "王李张刘陈杨赵黄周吴徐孙胡朱高林何郭马罗梁宋郑谢韩唐冯于董萧程曹袁邓许傅沈曾彭吕苏卢蒋蔡贾丁魏薛叶阎余潘杜戴夏钟汪田任姜范方石姚谭廖邹熊金陆郝孔白崔康毛邱秦江史顾侯邵孟龙万段雷钱汤尹黎易常武乔贺赖龚文庞樊兰殷施陶洪翟安颜倪严牛温芦季俞章鲁葛伍韦申尤毕聂丛焦向柳邢路岳齐沿梅莫庄辛管祝左涂谷祁时舒耿牟卜路詹关苗凌费纪靳盛童欧甄项曲成游阳裴席卫查屈鲍位覃霍翁隋植甘景薄单包司柏宁柯阮桂闵欧阳上官司马诸葛东方夏侯皇甫尉迟公孙"
_COMMON_SURNAME_CHARS = _COMMON_SURNAME_CHARS.replace("欧阳上官司马诸葛东方夏侯皇甫尉迟公孙", "")
_NON_CHARACTER_NAMES = {"自己", "面前", "身后", "这里", "那里", "时间", "镜头", "画面", "剧情", "旁白", "音效"}


def _add_character_candidate(candidates: Counter[str], name: str, count: int = 1) -> None:
    cleaned = str(name or "").strip()
    if cleaned and cleaned not in _NON_CHARACTER_NAMES:
        candidates[cleaned] = max(candidates[cleaned], count)


def _extract_character_candidates(text: str) -> list[dict[str, Any]]:
    candidates: Counter[str] = Counter()
    patterns = [
        r"(?:精神妹|师姐|仙子|狐妖|龙女|魔女)([一-龥]{2,4})(?:说|问|喊|道|看着|微微|凑近|递上)",
        rf"([{re.escape(_COMMON_SURNAME_CHARS)}][一-龥]{{1,2}})(?:说|问|喊|道|看着|微微|凑近|递上)",
        rf"([{re.escape(_COMMON_SURNAME_CHARS)}][一-龥]{{1,2}})(?:穿着|端着|轻笑|俯身|贴近|凑过来|的名字|名字)",
        r"@([一-龥A-Za-z0-9_]{2,12})",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text):
            name = match.group(1).strip()
            _add_character_candidate(candidates, name, max(1, text.count(name)))
    return [{"name": name, "evidence_count": count, "source": "text"} for name, count in candidates.most_common(8)]


def _extract_scene_candidates(text: str) -> list[dict[str, Any]]:
    scenes: list[dict[str, Any]] = []
    for name, keywords in _SCENE_KEYWORDS.items():
        count = sum(text.count(keyword) for keyword in keywords)
        if count:
            scenes.append({"name": name, "evidence_count": count, "source": "text"})
    return scenes


def _extract_prop_candidates(text: str) -> list[dict[str, Any]]:
    props = []
    for name in _COMMON_PROP_NAMES:
        count = text.count(name)
        if count:
            canonical = name
            if name == "计划书" and "商业计划书" in text:
                canonical = "商业计划书"
            elif name in {"热咖啡"}:
                canonical = "咖啡"
            elif name == "机车" and "重型机车" in text:
                canonical = "重型机车"
            elif name == "晨袍" and "居家晨袍" in text:
                canonical = "居家晨袍"
            elif name == "易拉罐" and "啤酒易拉罐" in text:
                canonical = "啤酒易拉罐"
            props.append({"name": canonical, "evidence_count": count, "source": "text"})
    return _dedupe_by_name(props)


def _dedupe_by_name(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for item in items:
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        existing = result.get(name)
        if existing is None or int(item.get("evidence_count") or 0) > int(existing.get("evidence_count") or 0):
            if existing and not item.get("description") and existing.get("description"):
                item = {**item, "description": existing.get("description")}
            result[name] = item
        elif existing is not None and item.get("description") and not existing.get("description"):
            existing["description"] = item.get("description")
    return list(result.values())


_PLACEHOLDER_DESCRIPTION_MARKERS = (
    "待补充设定",
    "Details pending",
    "Imported placeholder",
    "原文依据",
    "source_excerpt",
)


def _is_placeholder_description(description: Any) -> bool:
    value = str(description or "").strip()
    return not value or any(marker in value for marker in _PLACEHOLDER_DESCRIPTION_MARKERS)


def _project_style_prompt(project: dict[str, Any] | None) -> str:
    project = project or {}
    return str(project.get("style_description") or project.get("style") or "").strip()


def _sentences(text: str) -> list[str]:
    return [chunk.strip() for chunk in re.split(r"(?<=[。！？!?])\s*|\n+", text) if chunk.strip()]


def _evidence_snippets(text: str, name: str, *, limit: int = 3) -> list[str]:
    snippets = [sentence for sentence in _sentences(text) if name and name in sentence]
    if not snippets and name in _SCENE_KEYWORDS:
        keywords = _SCENE_KEYWORDS[name]
        snippets = [sentence for sentence in _sentences(text) if any(keyword in sentence for keyword in keywords)]
    return [_excerpt(snippet, 80) for snippet in snippets[:limit]]


def _asset_base_prompt(project: dict[str, Any] | None) -> str:
    style = _project_style_prompt(project)
    return f"统一视觉风格：{style}" if style else "统一视觉风格：遵守项目已选画风，保持全片视觉一致。"


def _infer_character_gender(name: str, snippets: list[str]) -> str:
    joined = " ".join(snippets)
    if any(marker in joined for marker in ("她", "女主", "女朋友", "晨袍", "裙", "吻")):
        return "女性角色"
    if any(marker in joined for marker in ("他", "男主", "男朋友", "衬衫")):
        return "男性角色"
    if name.endswith(("曦", "瑶", "烟", "儿", "雪", "月", "婷", "娜", "妍", "琪")):
        return "女性角色"
    return "角色"


def _build_character_asset_description(
    name: str,
    *,
    source_text: str,
    project: dict[str, Any] | None,
) -> str:
    snippets = _evidence_snippets(source_text, name)
    gender = _infer_character_gender(name, snippets)
    return "\n".join(
        [
            "【角色资产提示词】",
            _asset_base_prompt(project),
            f"角色名称：{name}。",
            f"基础人设：{gender}，韩剧偶像剧镜头下的高级商业影像质感，干净、精致、具有可连续出演短剧的明星感。",
            "外貌气质：五官清晰立体，皮肤通透自然，眼神有情绪层次，发型服帖有造型感，整体不能像路人抓拍。",
            "服装造型：根据角色定位选择现代偶像剧造型，衣料质感清楚，颜色低饱和、干净高级，避免夸张廉价网红风。",
            "表演方向：面部表情细腻，眼神、嘴角、肩颈和手部动作都要能支撑近景表演，适合后续视频模型保持同一角色。",
            "角色设定图要求：白色或浅灰干净背景，清晰正面形象，可用于生成面部特写、三视图和合并人设卡；不要文字水印，不要多人同框。",
        ]
    )


def _build_scene_asset_description(
    name: str,
    *,
    source_text: str,
    project: dict[str, Any] | None,
) -> str:
    return "\n".join(
        [
            "【场景资产提示词】",
            _asset_base_prompt(project),
            f"场景名称：{name}。",
            "核心空间：现代韩剧偶像剧质感的真实可拍无人空场景，空间关系清楚，方便后续分镜反复调用。",
            "布景要求：陈设干净高级，保留生活细节和商业影像质感；主体动线明确，前景、中景、背景有层次。",
            "光线色调：柔和漫射光，皮肤友好，低对比但细节清晰，色彩低饱和，营造浪漫、精致、微电影感。",
            "镜头适配：既能拍远景交代环境，也能拍空镜中近景和道具特写；避免杂乱、廉价、过暗或过度舞台化。",
            "场景设定图要求：横版环境参考图，展示完整空间、主要家具/招牌/道路/灯光方向；必须是无人空场，不出现人物、路人、手、脸、身体、剪影或人形模特；不要文字水印。",
        ]
    )


def _build_prop_asset_description(
    name: str,
    *,
    source_text: str,
    project: dict[str, Any] | None,
) -> str:
    return "\n".join(
        [
            "【道具资产提示词】",
            _asset_base_prompt(project),
            f"道具名称：{name}。",
            "道具定位：现代韩剧偶像剧短剧中的关键可识别道具，造型真实、精致、能在近景里看清材质和细节。",
            "外观细节：比例准确，边缘清楚，材质有高级商业摄影质感；如果是纸张/手机/饮品/机车等，要体现对应结构和使用痕迹。",
            "使用关系：道具需要方便角色拿取、递交、翻看、摆放或特写展示，和人物动作保持尺寸一致。",
            "道具设定图要求：白底或浅灰背景单体图，主体居中，清晰展示正面与关键细节，不要文字水印，不要被手遮挡。",
        ]
    )


def enrich_story_asset_descriptions(
    analysis: dict[str, Any],
    *,
    source_text: str,
    project: dict[str, Any] | None = None,
) -> dict[str, Any]:
    enriched = dict(analysis)
    builders = {
        "characters": _build_character_asset_description,
        "scenes": _build_scene_asset_description,
        "props": _build_prop_asset_description,
    }
    for bucket, builder in builders.items():
        items: list[dict[str, Any]] = []
        for raw in enriched.get(bucket) or []:
            item = dict(raw)
            name = str(item.get("name") or "").strip()
            if name and _is_placeholder_description(item.get("description")):
                item["description"] = builder(name, source_text=source_text, project=project)
            items.append(item)
        enriched[bucket] = items
    return enriched


def _canonicalize_agent_characters(
    items: list[StoryAnalysisNamedItem],
    project: dict[str, Any],
) -> list[dict[str, Any]]:
    registered = project.get("characters") or {}
    protagonist_candidates = [
        name
        for name, data in registered.items()
        if any(
            marker in str((data or {}).get("description") or "") for marker in ("男主", "主角", "店长", "外卖丹铺老板")
        )
    ]
    normalized: list[dict[str, Any]] = []
    creature_suffixes = ("魈", "妖", "兽", "狼", "狐", "龙", "鬼", "魔", "灵", "精")

    for item in items:
        raw_name = item.name.strip()
        name = re.sub(r"[（(][^）)]*[）)]\s*$", "", raw_name).strip()
        if not name:
            continue
        if name in registered:
            normalized.append(
                {
                    "name": name,
                    "evidence_count": item.evidence_count,
                    "source": "project",
                    "description": item.description,
                }
            )
            continue
        if any(marker in raw_name for marker in ("男主", "主角")) and len(protagonist_candidates) == 1:
            normalized.append(
                {
                    "name": protagonist_candidates[0],
                    "evidence_count": item.evidence_count,
                    "source": "project",
                    "description": item.description,
                }
            )
            continue
        if name.endswith(creature_suffixes):
            normalized.append(
                {
                    "name": name,
                    "evidence_count": item.evidence_count,
                    "source": item.source,
                    "description": item.description,
                }
            )

    return _dedupe_by_name(normalized)


def _detect_hard_points(text: str, markers: list[dict[str, Any]]) -> list[dict[str, str]]:
    points: list[dict[str, str]] = []
    if any(word in text for word in ("第一人称", "鼻尖", "呼吸", "贴得极近")):
        points.append(
            {
                "type": "performance_continuity",
                "label": "第一人称近距离表演",
                "reason": "脸部距离、呼吸、眼神和身体微动作需要稳定控制。",
            }
        )
    if any(word in text for word in ("雨后", "雨夜", "夜里", "偏暗", "小巷")):
        points.append(
            {
                "type": "lighting",
                "label": "低照度雨夜/小巷",
                "reason": "需要避免画面过暗，同时保留雨后潮湿质感。",
            }
        )
    if any(word in text for word in ("火焰", "灵符", "飞剑", "爆炸", "血红眼睛")):
        points.append(
            {
                "type": "effect_continuity",
                "label": "特效/道具动作连续性",
                "reason": "特效大小、方向和道具位置容易在视频中漂移。",
            }
        )
    if markers:
        points.append(
            {
                "type": "gameplay_boundary",
                "label": "玩法入口与回归剧情边界",
                "reason": "玩法入口通常只做审核帧，不应默认提交剧情视频模型。",
            }
        )
    return points


def analyze_story_import(
    text: str,
    *,
    project: dict[str, Any] | None = None,
    episode: int = 1,
    source_filename: str | None = None,
) -> dict[str, Any]:
    paragraphs = _paragraphs(text)
    lines = text.splitlines()
    project = project or {}
    content_format = detect_content_format(text, project=project)
    interactive_nodes = detect_interactive_nodes(lines) if content_format == CONTENT_FORMAT_INTERACTIVE else []
    markers = [
        {"line": node["line"], "kind": node["kind"], "text": node["text"]}
        for node in interactive_nodes
        if node["kind"] in {"gameplay_entry", "return_to_story"}
    ]
    template = template_summary(content_format)

    beats = []
    visible_paragraphs = paragraphs
    for index, paragraph in enumerate(visible_paragraphs, start=1):
        beats.append(
            {
                "beat_id": f"B{index:02d}",
                "title": _excerpt(paragraph, 28),
                "story_function": beat_function_for_index(content_format, index, len(visible_paragraphs)),
                "source_excerpt": _full_source_excerpt(paragraph),
            }
        )

    characters = _dedupe_by_name(
        [
            *_extract_registered_assets(text, project.get("characters") or {}),
            *_extract_character_candidates(text),
        ]
    )
    scenes = _dedupe_by_name(
        [
            *_extract_registered_assets(text, project.get("scenes") or {}),
            *_extract_scene_candidates(text),
        ]
    )
    props = _dedupe_by_name(
        [
            *_extract_registered_assets(text, project.get("props") or {}),
            *_extract_prop_candidates(text),
        ]
    )

    analysis = {
        "schema_version": 1,
        "episode": episode,
        "source_filename": source_filename,
        "content_format": content_format,
        "template_name": template["label"],
        "template_focus": template["focus"],
        "format_profile": template,
        "summary": _excerpt(" ".join(paragraphs[:2]), 160),
        "story_beats": beats,
        "characters": characters,
        "scenes": scenes,
        "props": props,
        "hard_points": _detect_hard_points(text, markers),
        "gameplay_markers": markers,
        "interactive_nodes": interactive_nodes,
        "choice_points": choice_points_from_interactive_nodes(interactive_nodes),
    }
    return StoryImportAnalysisModel.model_validate(
        enrich_story_asset_descriptions(analysis, source_text=text, project=project)
    ).model_dump()


def build_story_analysis_prompt(
    text: str,
    *,
    project: dict[str, Any] | None = None,
    episode: int = 1,
    source_filename: str | None = None,
) -> str:
    project = project or {}
    characters = ", ".join(sorted((project.get("characters") or {}).keys())) or "无"
    scenes = ", ".join(sorted((project.get("scenes") or {}).keys())) or "无"
    props = ", ".join(sorted((project.get("props") or {}).keys())) or "无"
    source_text = text.strip()
    if len(source_text) > 24000:
        source_text = source_text[:24000] + "\n……（原文过长，此处截断；请优先分析已提供部分）"

    return f"""你是 PlayAsLife 的 story-beat 分析器，负责第 1 步“导入小说 / 剧本”。

本次仅做分析：不要调用工具，不写入或修改任何项目文件。
本次粒度固定为 normal：只做导入盘点和粗节拍，不执行 detailed 微节拍拆分；详细节拍由下一阶段单独生成。

请把原文拆成结构化分析结果，供后续视觉资产库、导演分镜、关键帧和视频生成使用。

必须只输出 JSON 对象，不要 Markdown，不要解释。字段要求：
- story_beats：剧情粗节拍，建议 8-15 个。每个 beat 是叙事变化点，不是镜头。
- characters：角色候选。
- scenes：场景候选。
- props：道具/关键物件候选。
- characters/scenes/props 每项尽量写 description：这是后续生成资产图的视觉提示词，只能写外观、空间、材质、用途、风格和设定图要求；其中 scenes 的 description 必须明确写“无人空场景/不出现人物、路人、手、脸、身体、剪影或人形模特”；禁止写“原文依据/source_excerpt/第几段/剧情里说”等文本证据，禁止把原文句子塞进 description。
- hard_points：难拍点，例如第一人称近距离表演、低照度雨夜、特效连续性、玩法边界。
- gameplay_markers：明确的“进入游戏”“回归剧情”等边界。
- interactive_nodes：剧游专属交互节点，kind 只能从 gameplay_entry / return_to_story / choice_point / hook 中选择；选择点要写 options；handoff 写 to_gameplay / to_story / to_branch / to_next_event。
- choice_points：从 choice_point 节点抽出的分支结构，包含 choice_id、source_node_id、prompt、options；每个 option 包含 option_id、label、branch_key、next_hint。
- content_format：必须四选一：interactive_drama_game（剧游）、ad（广告）、narrative_video（剧情视频）、narrated_drama（解说剧）。
- template_name / template_focus / format_profile：按 content_format 写入项目类型模板信息。

规则：
1. 不写摄影机、镜头、灯光、关键帧或视频提示词。
2. 保留“进入游戏/回归剧情”边界，不要把玩法入口默认当剧情视频生成。
3. 如果文本包含细腻动作、暧昧距离、危险路途、喜剧停顿、能力泄露、钩子，拆得更细。
4. 不要发明原文没有的人物和剧情。
5. source_excerpt 要能追溯原文。
6. 类型模板口径：
   - 剧游：玩法入口、回归剧情、选择点、钩子。
   - 广告：前 3 秒钩子、痛点、反转、强转化。
   - 剧情视频：情绪推进、镜头节奏、人物关系。
   - 解说剧：旁白信息密度、画面承接、转场节奏。
7. characters 只能收录真正的人物或需要独立视觉资产的妖兽/怪物；禁止把动词、形容词或句子碎片当人名。
8. 原文使用“男主/女主/师姐”等称谓时，结合项目已登记角色和剧情证据映射为正确角色名；无法确定时才保留称谓并说明。
9. 山魈、藤妖等实际出场并需要保持造型连续的生物，应作为角色候选，不得漏掉。
10. description 必须服务生图，不要写“待补充设定”；如果信息不足，也要按项目风格补足可生成的视觉设定。

项目已登记角色：{characters}
项目已登记场景：{scenes}
项目已登记道具：{props}

episode: {episode}
source_filename: {source_filename or ""}

<source_text>
{source_text}
</source_text>
"""


async def analyze_story_import_agent(
    text: str,
    *,
    agent_runner: Callable[[str, dict[str, Any]], Awaitable[dict[str, Any]]],
    project: dict[str, Any] | None = None,
    episode: int = 1,
    source_filename: str | None = None,
) -> dict[str, Any]:
    """通过当前智能体提炼语义资产，再与可确定计算的导入元数据合并。"""
    project = project or {}
    registered_characters = ", ".join(sorted((project.get("characters") or {}).keys())) or "无"
    registered_scenes = ", ".join(sorted((project.get("scenes") or {}).keys())) or "无"
    registered_props = ", ".join(sorted((project.get("props") or {}).keys())) or "无"
    registered_character_details = "\n".join(
        f"- {name}: {_excerpt(str((data or {}).get('description') or ''), 140)}"
        for name, data in sorted((project.get("characters") or {}).items())
    )
    source_text = text.strip()
    if len(source_text) > 24000:
        source_text = source_text[:24000] + "\n……（原文过长，已截断）"

    prompt = f"""你是 PlayAsLife 的视觉资产提炼智能体。只分析本集实际出场、需要保持视觉连续的角色、场景和道具。

只输出 JSON，严格匹配 response schema；不写剧情节拍、镜头、提示词或解释。

提炼规则：
1. characters 收录真正的人物，以及需要单独设计造型的妖兽/怪物。
2. 禁止把动词、形容词、地名碎片或句子片段当成角色，例如“刚看清”“把头上的”“排晾晒的”。
3. 原文使用“男主/女主/师姐”时，必须结合已登记角色和剧情证据映射为正确姓名。
4. 山魈、藤妖等出场生物要作为角色候选，不要当成道具。
5. 项目已登记资产只有在本集出现或被明确引用时才返回。
6. source 填 project 或 agent；evidence_count 按原文显式出现次数估算，最少为 1。
7. description 如果填写，只能是纯视觉资产提示词：外观、服装/空间/材质、用途、风格和设定图要求。场景 description 必须明确写无人空场景，禁止出现人物、路人、手、脸、身体、剪影或人形模特。禁止写原文依据、source_excerpt、剧情句子、旁白、段落编号；文本证据只允许通过 evidence_count/source 表达，不能进入 description。

项目已登记角色：{registered_characters}
已登记角色视觉/身份摘要（用于把“男主/店长/师姐”映射回正式名）：
{registered_character_details or "无"}
项目已登记场景：{registered_scenes}
项目已登记道具：{registered_props}

<source_text>
{source_text}
</source_text>
"""
    payload = await agent_runner(prompt, StoryAssetInventoryModel.model_json_schema())
    if not isinstance(payload, dict):
        raise ValueError("story asset inventory agent response must be a JSON object")
    inventory = StoryAssetInventoryModel.model_validate(payload)
    analysis = analyze_story_import(
        text,
        project=project,
        episode=episode,
        source_filename=source_filename,
    )
    analysis["characters"] = _canonicalize_agent_characters(inventory.characters, project)
    analysis["scenes"] = [item.model_dump() for item in inventory.scenes]
    analysis["props"] = [item.model_dump() for item in inventory.props]
    return StoryImportAnalysisModel.model_validate(
        enrich_story_asset_descriptions(analysis, source_text=text, project=project)
    ).model_dump()


def _apply_template_defaults(
    payload: dict[str, Any],
    *,
    source_text: str,
    project: dict[str, Any] | None,
) -> None:
    raw_format = str(payload.get("content_format") or "").strip()
    if not raw_format:
        raw_format = detect_content_format(source_text, project=project)
    template = template_summary(raw_format)
    payload["content_format"] = template["content_format"]
    payload["template_name"] = payload.get("template_name") or template["label"]
    payload["template_focus"] = payload.get("template_focus") or template["focus"]
    if not isinstance(payload.get("format_profile"), dict):
        payload["format_profile"] = template
    _apply_interactive_defaults(payload, source_text=source_text)


def _normalise_interactive_nodes(raw_nodes: Any, *, source_text: str) -> list[dict[str, Any]]:
    if not isinstance(raw_nodes, list) or not raw_nodes:
        return detect_interactive_nodes(source_text.splitlines())
    nodes: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_nodes, start=1):
        item = raw if isinstance(raw, dict) else {}
        text = str(item.get("text") or item.get("title") or "").strip()
        kind = str(item.get("kind") or interactive_kind_for_text(text) or "").strip()
        if not text or not kind:
            continue
        nodes.append(
            {
                "node_id": str(item.get("node_id") or f"I{index:02d}"),
                "line": int(item.get("line") or 0),
                "kind": kind,
                "text": text,
                "options": list(item.get("options") or extract_choice_options(text)),
                "handoff": str(item.get("handoff") or interactive_handoff_for_kind(kind)),
            }
        )
    return nodes


def _normalise_choice_points(raw_points: Any, *, nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(raw_points, list) or not raw_points:
        return choice_points_from_interactive_nodes(nodes)
    choice_points: list[dict[str, Any]] = []
    for index, raw in enumerate(raw_points, start=1):
        item = raw if isinstance(raw, dict) else {}
        prompt = str(item.get("prompt") or item.get("text") or "").strip()
        if not prompt:
            continue
        choice_id = str(item.get("choice_id") or f"C{index:02d}")
        raw_options = item.get("options") if isinstance(item.get("options"), list) else extract_choice_options(prompt)
        options: list[dict[str, str]] = []
        for option_index, raw_option in enumerate(raw_options[:4], start=1):
            if isinstance(raw_option, dict):
                label = str(raw_option.get("label") or "").strip()
                option_id = str(raw_option.get("option_id") or f"{choice_id}-{chr(64 + option_index)}")
                branch_key = str(raw_option.get("branch_key") or f"branch_{chr(96 + option_index)}")
                next_hint = str(raw_option.get("next_hint") or "")
            else:
                label = str(raw_option).strip()
                option_id = f"{choice_id}-{chr(64 + option_index)}"
                branch_key = f"branch_{chr(96 + option_index)}"
                next_hint = ""
            if label:
                options.append(
                    {
                        "option_id": option_id,
                        "label": label,
                        "branch_key": branch_key,
                        "next_hint": next_hint,
                    }
                )
        choice_points.append(
            {
                "choice_id": choice_id,
                "source_node_id": str(item.get("source_node_id") or ""),
                "line": int(item.get("line") or 0),
                "prompt": prompt,
                "options": options,
                "handoff": str(item.get("handoff") or "to_branch"),
            }
        )
    return choice_points


def _apply_interactive_defaults(payload: dict[str, Any], *, source_text: str) -> None:
    if payload.get("content_format") != CONTENT_FORMAT_INTERACTIVE:
        payload["interactive_nodes"] = []
        payload["choice_points"] = []
        return
    nodes = _normalise_interactive_nodes(payload.get("interactive_nodes"), source_text=source_text)
    payload["interactive_nodes"] = nodes
    payload["choice_points"] = _normalise_choice_points(payload.get("choice_points"), nodes=nodes)
    if not payload.get("gameplay_markers"):
        payload["gameplay_markers"] = [
            {"line": node["line"], "kind": node["kind"], "text": node["text"]}
            for node in nodes
            if node["kind"] in {"gameplay_entry", "return_to_story"}
        ]


def _parse_llm_analysis_text(
    text: str,
    *,
    episode: int,
    source_filename: str | None,
    source_text: str,
    project: dict[str, Any] | None,
) -> dict[str, Any]:
    raw = text.strip()
    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        start = raw.find("{")
        end = raw.rfind("}")
        if start < 0 or end <= start:
            raise
        payload = json.loads(raw[start : end + 1])
    if not isinstance(payload, dict):
        raise ValueError("story analysis LLM response must be a JSON object")
    payload.setdefault("schema_version", 1)
    payload["episode"] = episode
    payload.setdefault("source_filename", source_filename)
    _apply_template_defaults(payload, source_text=source_text, project=project)
    deterministic = analyze_story_import(
        source_text,
        project=project,
        episode=episode,
        source_filename=source_filename,
    )
    payload["characters"] = _dedupe_by_name(
        [
            *(payload.get("characters") or []),
            *(deterministic.get("characters") or []),
        ]
    )
    payload["scenes"] = _dedupe_by_name(
        [
            *(payload.get("scenes") or []),
            *(deterministic.get("scenes") or []),
        ]
    )
    payload["props"] = _dedupe_by_name(
        [
            *(payload.get("props") or []),
            *(deterministic.get("props") or []),
        ]
    )
    payload = enrich_story_asset_descriptions(payload, source_text=source_text, project=project)
    return StoryImportAnalysisModel.model_validate(payload).model_dump()


async def analyze_story_import_llm(
    text: str,
    *,
    project: dict[str, Any] | None = None,
    episode: int = 1,
    source_filename: str | None = None,
    project_name: str | None = None,
) -> dict[str, Any]:
    prompt = build_story_analysis_prompt(
        text,
        project=project,
        episode=episode,
        source_filename=source_filename,
    )
    generator = await TextGenerator.create(TextTaskType.SCRIPT, project_name)
    result = await generator.generate(
        TextGenerationRequest(
            prompt=prompt,
            response_schema=None,
            max_output_tokens=12000,
        ),
        project_name=project_name,
    )
    return _parse_llm_analysis_text(
        result.text,
        episode=episode,
        source_filename=source_filename,
        source_text=text,
        project=project,
    )


async def analyze_story_import_auto(
    text: str,
    *,
    project: dict[str, Any] | None = None,
    episode: int = 1,
    source_filename: str | None = None,
    project_name: str | None = None,
    engine: str = "auto",
) -> dict[str, Any]:
    if engine not in {"auto", "llm", "deterministic"}:
        raise ValueError("engine must be auto/llm/deterministic")

    if engine in {"auto", "llm"}:
        try:
            return await analyze_story_import_llm(
                text,
                project=project,
                episode=episode,
                source_filename=source_filename,
                project_name=project_name,
            )
        except Exception:
            if engine == "llm":
                raise
            logger.warning("story analysis LLM failed; falling back to deterministic analyzer", exc_info=True)

    return analyze_story_import(
        text,
        project=project,
        episode=episode,
        source_filename=source_filename,
    )
