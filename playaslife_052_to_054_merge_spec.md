# PlayAsLife v0.5.2 → v0.5.4 功能合并至 ArcReel 项目方案

## 一、合并概述

**源分支**: `playaslife-xizhu` @ `6e4e95d` (v0.5.2) → `62e673c` (v0.5.4)  
**目标仓库**: `/Users/frank/workspace/jiezi/ArcReel`  
**目标分支**: `merge-playaslife-0.5.2-0.5.4`  

合并范围涉及 **68 个文件**，新增约 **5,293 行代码**，修改约 **397 行**。主要功能是构建完整的小说→视频生产流水线，包含故事分析、节拍规划、导演分镜、关键帧规划、视频提示词、草稿 QA 审核等核心能力。

---

## 二、合并模块清单与优先级

### 🔴 P0 - 核心基础设施（必须合并）

| # | PlayAsLife 路径 | ArcReel 目标路径 | 合并说明 | 风险等级 |
|---|----------------|------------------|---------|---------|
| 1.1 | `lib/video_duration.py` | `lib/video_duration.py` | 纯工具函数库，无依赖外部状态，直接复制 | ⭐低 |
| 1.2 | `server/services/director_script_export.py` | `server/services/director_script_export.py` | 核心桥接服务，依赖 lib/script_models，需确认 ArcReel 是否有相同模型 | ⭐⭐中 |

### 🟠 P1 - 流水线核心服务（重要但需适配）

| # | PlayAsLife 路径 | ArcReel 目标路径 | 合并说明 | 风险等级 |
|---|----------------|------------------|---------|---------|
| 2.1 | `server/services/story_analysis.py` | `server/services/story_analysis.py` | 小说导入分析，依赖文本后端，需检查 ArcReel 的 story analysis 实现差异 | ⭐⭐中 |
| 2.2 | `server/services/story_beats.py` | `server/services/story_beats.py` | 故事节拍规划，基于 story_analysis 输出，逻辑独立性强 | ⭐⭐中 |
| 2.3 | `server/services/shot_director.py` | `server/services/shot_director.py` | 导演分镜规划，依赖 story_beats 和 project_type_templates，需处理类型引用 | ⭐⭐⭐高 |
| 2.4 | `server/services/keyframe_prompts.py` | `server/services/keyframe_prompts.py` | 关键帧提示词规划，较复杂，依赖多个中间产物 | ⭐⭐⭐高 |
| 2.5 | `server/services/video_prompts.py` | `server/services/video_prompts.py` | 视频提示词打包，依赖 keyframe_prompts 和 director_shots，需注意视频长度约束 | ⭐⭐中 |
| 2.6 | `server/services/generation_tasks.py` | `server/services/generation_tasks.py` | 任务编排核心，涉及 enqueue 逻辑，ArcReel 已有 generation_tasks，需增量合并而非覆盖 | ⭐⭐⭐高 |

### 🟡 P2 - 用户界面与交互（可选/根据需求决定）

| # | PlayAsLife 路径 | ArcReel 目标路径 | 合并说明 | 风险等级 |
|---|----------------|------------------|---------|---------|
| 3.1 | `frontend/src/components/canvas/timeline/PreprocessingView.tsx` | 按 ArcReel 时间线组件结构调整 | 时间线预处理视图，ArcReel 可能有自己的时间线实现，需谨慎适配 | ⭐⭐⭐高 |
| 3.2 | `frontend/src/components/canvas/timeline/ShotDetail.tsx` | 同上 | 镜头详情展示，依赖 TypeScript 类型定义 | ⭐⭐⭐高 |
| 3.3 | `frontend/src/types/keyframe-prompts.ts` | `frontend/src/types/keyframe-prompts.ts` | 类型定义，需与后端 API 保持一致 | ⭐低 |
| 3.4 | `frontend/src/utils/generation-mode.ts` | 按 ArcReel 的模式选择器结构调整 | 生成模式工具类，ArcReel 可能有类似实现 | ⭐⭐中 |

### 🟢 P3 - 辅助功能与扩展（按需合并）

| # | PlayAsLife 路径 | ArcReel 目标路径 | 合并说明 | 风险等级 |
|---|----------------|------------------|---------|---------|
| 4.1 | `server/services/draft_video_qa.py` | `server/services/draft_video_qa.py` | QA 审核系统，非核心流水线必需，可放后续迭代 | ⭐⭐中 |
| 4.2 | `frontend/pages/UiImageWorkbenchPage.tsx` | 根据 ArcReel 页面结构适配 | UI 出图工作台，属于独立小特性 | ⭐⭐⭐高 |
| 4.3 | `lib/config/registry.py` - Manxue provider | ArcReel 的 provider config | 新增视频供应商，是否纳入视 ArcReel 的供应商支持范围而定 | ⭐低 |
| 4.4 | `lib/custom_provider/endpoints.py` - Manxue 相关 | ArcReel 的 custom_provider 配置 | 自定义供应商 endpoint 增强，影响较小 | ⭐低 |
| 4.5 | `lib/prompt_builders.py` - 少量调整 | ArcReel 的 prompt_builders | Prompt 构建工具的微调，需合并而非覆盖 | ⭐⭐中 |

---

## 三、关键数据模型一致性检查

在合并前，需要确认 ArcReel 中以下数据类型是否与 PlayAsLife 兼容：

1. **`lib/script_models.py` 中的 `NarrationEpisodeScript`**（director_script_export 依赖）
   - 查看 ArcReel 是否有等效的剧本模型定义
   
2. **`lib/text_backends/base.py` 中的 `TextTaskType`**（story_analysis、story_beats 等依赖的新任务类型）
   - 需要确认 ArcReel 的 enum 是否已包含：`STORY_BEATS`, `DIRECTOR_SHOTS`, `KEYFRAME_PROMPTS`, `VIDEO_PROMPTS`

3. **前端 TypeScript 接口**
   - `StoryImportAnalysis`
   - `DirectorShotPlan` 
   - `KeyframePromptModel`
   - `VideoPromptPlan`

---

## 四、分阶段实施计划

### 第一阶段：基础设施准备（1-2 天）

```bash
# 创建合并分支
cd /Users/frank/workspace/jiezi/ArcReel
git checkout -b merge-playaslife-0.52-0.54

# 添加 PlayAsLife 作为远程仓库以便拉取特定版本的文件
git remote add playa https://github.com/sapiens-ai/playaslife-xizhu.git  # 或本地 path
git fetch playa 6e4e95d:playaslife-v0.5.2 62e673c:playaslife-v0.5.4
```

### 第二阶段：P0 核心模块合并（2-3 天）

1. **合并 `video_duration.py`**
   - 直接复制到 `lib/video_duration.py`
   - 验证：跑所有时长相关的单元测试

2. **合并 `director_script_export.py`**
   - 先确认 ArcReel 的 `lib/script_models.py` 是否有兼容的 `NarrationEpisodeScript`
   - 如不兼容，需要调整导入路径或创建适配层
   - 复制到 `server/services/director_script_export.py`
   - 验证：导出生成逻辑是否能正确读取分镜草稿并产出剧集剧本

### 第三阶段：P1 流水线服务逐个合并（5-7 天）

按以下顺序合并，因为存在依赖关系：
```
story_analysis → story_beats → shot_director → keyframe_prompts → video_prompts
```

每个服务的合并步骤：
1. **对比文件**：用 `diff` 或可视化工具对比 PlayAsLife 版本和 ArcReel 当前版本
2. **识别冲突**：找出修改交集部分
3. **策略选择**：
   - 如果 ArcReel 有同名但不同实现 → 将 PlayAsLife 的逻辑函数提取出来，以混合（mix-in）方式调用
   - 如果 ArcReel 没有该文件 → 直接复制 + 调整导入引用
   - 如果 ArcReel 有部分实现 → 增量合并（patch 新增的代码块）
4. **测试验证**：每个服务合并后立即运行相关测试

### 第四阶段：P2 前端组件适配（3-5 天）

这部分最耗时，因为：
- ArcReel 的前端路由、组件结构与 PlayAsLife 不同
- 需要根据 ArcReel 的设计模式重写 UI 逻辑
- 不是简单的文件复制，而是功能移植

建议：
1. 先合并前端类型定义（`keyframe-prompts.ts` 等）
2. 再考虑逐步实现 UI 组件，而非一次性全量替换

### 第五阶段：P3 扩展功能（按需）

根据 ArcReel 的实际需求决定是否合并 Draft Video QA、Manxue Provider 等特性。

---

## 五、可能的冲突及解决方案

### 冲突 1：`lib/prompt_builders.py` 差异

**PlayAsLife v0.5.4 对 prompt_builders.py 做了 112 行的修改和新增。**

**解决方案**：采用"合并而非覆盖"策略。先获取 PlayAsLife 的完整版本，然后手动保留 ArcReel 的特殊扩展逻辑，将 PlayAsLife 的通用函数加入其中。

### 冲突 2：`server/services/generation_tasks.py` 高度定制化

**ArcReel 很可能有自己的 generation_tasks 实现，不能简单替换。**

**解决方案**：从 PlayAsLife 的 `generation_tasks.py` 中提取出新的函数（如 `_draft_video_generate_audio`, `_reference_pack_image_priority` 等），然后作为扩展方法注入到 ArcReel 的现有类中。使用继承或组合模式。

### 冲突 3：前端类型定义不一致

**ArcReel 和 PlayAsLife 可能有不同类型的 StoryAnalysis 等接口。**

**解决方案**：在 ArcReel 的类型文件中增加类型别名或适配器层，例如：
```typescript
// frontend/src/types/playaslife-compat.ts
export type PlayAsLifeStoryAnalysis = Omit<YourArcReelStoryAnalysis, 'extraField'>;
```

### 冲突 4：Service 依赖的上下文对象不同

**PlayAsLife 的服务函数直接访问 project/episode 对象，而 ArcReel 可能通过不同的服务层包装。**

**解决方案**：在 ArcReel 的服务层调用 PlayAsLife 的服务时，做一层适配转换。例如：
```python
# ArcReel 的 wrapper
class StoryAnalysisService(PlayAsLifeStoryAnalysis):
    def get_project_context(self, project_name: str) -> dict:
        # 调用 ArcReel 的项目管理器获取项目上下文
        return self.arc_reel_project_manager.get(project_name)
```

---

## 六、质量保障措施

1. **自动化测试**：每个功能模块合并后，运行相关测试用例，确保功能不变
2. **代码审查**：每次合并 PR（即使本地提交）都要进行同行审查
3. **功能验收测试**：合并完成后，走一次完整的故事→视频全流程，确保各阶段衔接正常
4. **性能基准**：记录合并前的关键操作耗时，对比合并后的性能变化（特别是关键帧规划和视频提示词生成）
5. **灰度发布**：先在测试项目中启用新流水线，确认稳定后再推广到生产环境

---

## 七、分支策略建议

推荐使用 feature branch + PR review 的工作流：

```
main (prod) ←───┐
                │
merge-branch    │
├── feat/video-duration       (P0, 最早合并)
├── feat/director-script-export (P0)
├── feat/story-analysis       (P1)
├── feat/story-beats          (P1)
├── feat/shot-director        (P1)
├── feat/keyframe-prompts     (P1)
├── feat/video-prompts        (P1)
└── feat/generation-tasks-ext (P1, 增量扩展)

每个 feature branch 完成后再以 PR 形式 merge 到 merge-branch，最后再 merge 到 main
```

## 八、时间预估

| 阶段 | 预计工时 | 备注 |
|------|---------|------|
| P0 基础设施 | 1-2 天 | 相对简单，主要是文件复制 |
| P1 流水线服务 | 5-7 天 | 需要仔细适配 ArcReel 架构 |
| P2 前端组件 | 3-5 天 | 工作量最大，需根据 ArcReel UI 重构 |
| P3 扩展功能 | 按需 | 可选 |
| 测试与验收 | 2-3 天 | 端到端流程验证 |
| **总计** | **12-20 天** | 取决于 ArcReel 原始架构相似度 |

> **注意**：以上时间是初步估算，实际开发中可能需要根据具体实现细节调整。建议在开始合并前先做一个小型 PoC（例如先合并 `video_duration.py`），验证可行后再继续。

---

## 九、后续工作（合并完成后）

1. **文档更新**：ArcReel 的项目 README 和开发者文档需要更新，反映新的流水线功能
2. **Skill 文档同步**：PlayAsLife 的 `.claude/skills/` 系列技能文档也需要考虑是否合并到 ArcReel 的 agent_runtime_profile 中
3. **前端国际化**：新增的英文/中文翻译词条需要同步到 ArcReel 的 i18n 文件
4. **迁移脚本**：为旧项目提供从原生工作流到新流水线的迁移指南

---

*最后更新时间：$(date)*
*负责人：待指定*
