# Golden Sample: `1-1.md` Shot Director Breakdown

Source beat sample: `agent_runtime_profile/.claude/skills/story-beat/references/golden-1-1-detailed.md`

Purpose: calibrate converting detailed story beats into shot groups and generation-ready shots. This sample is intentionally practical: it merges compatible 2-second micro beats while preserving danger, comedy timing, gameplay boundaries, and keyframe roles.

## Metadata

```json
{
  "source_id": "1-1",
  "content_format": "interactive_drama_game",
  "subtype": "mission_gameplay_comedy",
  "target_runtime_sec": 126,
  "story_micro_beat_count": 47,
  "shot_count": 37,
  "hard_boundaries": ["进入游戏：摆筋脉", "回归剧情："]
}
```

## Shot Groups Overview

| Group | Source | Purpose | Duration | Shots |
|---|---|---|---:|---:|
| SG01 | G01 | 建立修真外卖任务、倒计时和差评压力。 | 12s | 4 |
| SG02 | G02 | 山魈三连袭击，表现配送路途凶险。 | 14s | 4 |
| SG03 | G03 | 藤妖封路、受潮灵符和延迟爆炸笑点。 | 13s | 4 |
| SG04 | G04 | 双线倒计时：男主得意，林小满濒临失控。 | 9s | 3 |
| SG05 | G05 | “零失误”立 flag 后飞剑故障坠落。 | 12s | 4 |
| SG06 | G06 | 双线尖叫与校场逼近。 | 10s | 3 |
| SG07 | G07 | 校场失控入场连环笑点。 | 16s | 5 |
| SG08 | G08 | 极限送达和五星好评。 | 8s | 2 |
| SG09 | G09 | 药力走偏，进入玩法，分镜结尾。 | 11s | 3 |
| SG10 | G10 | 回归剧情，调息羞恼、能力泄露、身份追问。 | 17s | 4 |
| SG11 | G11 | 血红眼睛暗线钩子。 | 4s | 1 |

## Detailed Shots

### SG01 配送任务建立

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S01 | B01.1+B01.2 | `establishing` | 晨雾竹林里，破旧飞剑低空掠过，男主腰间红十字储物袋露出。 | 4s | `start_only` 起始帧：飞剑贴竹林掠过 |
| E1S02 | B01.3 | `mission_info` | 男主捏传音玉简，林小满急催飞剑课马上点名。 | 3s | `start_and_guide` 起始帧：男主持玉简；引导参考图：玉简传出急声 |
| E1S03 | B01.4 | `insert` | S级订单信息浮现：收货人、丹药、半炷香、迟到差评。 | 3s | `review_only` 审核帧：订单界面/信息浮现 |
| E1S04 | B01.5 | `comedy_pause` | 男主听到差评，倒吸气，慌张念叨执照要没了。 | 2s | `start_and_guide` 起始帧：男主震住；引导参考图：慌张表情落点 |

### SG02 山魈三连袭击

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S05 | B02.1 | `action_motion` | 三只小山魈从山坡扑下，砸向低空飞剑。 | 3s | `start_and_guide` 起始帧：山坡异动；引导参考图：山魈扑近 |
| E1S06 | B02.2 | `evasive_action` | 男主压低飞剑贴地俯冲，第一只山魈扑空撞断青竹。 | 4s | `start_and_guide` 起始帧：飞剑贴地；引导参考图：青竹被撞断 |
| E1S07 | B02.3 | `near_miss` | 第二只山魈从侧面扑来，爪子擦着男主头发削过。 | 3s | `start_and_guide` 起始帧：山魈侧扑；引导参考图：爪子贴发擦过 |
| E1S08 | B02.4 | `evasive_action` | 第三只山魈砸下山石，男主借飞剑尾摆钻出，石块身后炸碎。 | 4s | `start_and_guide` 起始帧：山石压下；引导参考图：碎石在身后炸开 |

### SG03 藤妖封路与受潮灵符

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S09 | B03.1+B03.2 | `evasive_action` | 藤妖从地下窜起织成大网，男主跃起，飞剑从藤缝穿过。 | 5s | `start_and_guide` 起始帧：藤网封路；引导参考图：男主从藤网上方滑过 |
| E1S10 | B03.3 | `action_motion` | 十几根细藤从后方追来，距离迅速缩短。 | 2s | `start_only` 起始帧：藤蔓追近 |
| E1S11 | B03.4 | `comedy_pause` | 男主甩出皱巴巴灵符大喊“爆”，灵符贴住藤蔓却没反应。 | 3s | `start_and_guide` 起始帧：甩符；引导参考图：灵符没反应、男主僵住 |
| E1S12 | B03.5 | `near_miss` | 藤蔓快缠住男主时，灵符延迟爆炸，把藤蔓炸得缩回。 | 3s | `start_and_guide` 起始帧：藤蔓逼近；引导参考图：延迟爆炸 |

### SG04 双线倒计时

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S13 | B04.1+B04.3 | `transition` | 男主从树梢掠过，山魈扑空；他回头得意整理头发。 | 3s | `start_and_guide` 起始帧：掠过树梢；引导参考图：得意整理头发 |
| E1S14 | B04.2 | `reaction` | 林小满在飞剑课校场，灵脉乱冲，疼得猛吸气。 | 3s | `start_and_guide` 起始帧：林小满强撑；引导参考图：疼痛反应 |
| E1S15 | B04.4 | `reaction` | 林小满按胸口脸色发白，咬牙反复念“还不到”。 | 3s | `start_and_guide` 起始帧：手按胸口；引导参考图：咬牙强忍 |

### SG05 飞剑故障反转

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S16 | B05.1+B05.2 | `comedy_pause` | 男主比胜利手势吹“零失误”，飞剑脚下突然咔哒一声，他低头。 | 4s | `start_and_guide` 起始帧：胜利手势；引导参考图：听见咔哒低头 |
| E1S17 | B05.3 | `reveal` | 飞剑连续咔哒，剑身一顿一顿往下掉，男主笑容僵住。 | 3s | `start_and_guide` 起始帧：飞剑不稳；引导参考图：笑容僵住 |
| E1S18 | B05.4 | `comedy_pause` | 飞剑尾部喷黑烟，男主掐诀哄老伙计撑住。 | 3s | `start_and_guide` 起始帧：喷黑烟；引导参考图：男主哄飞剑 |
| E1S19 | B05.5 | `action_motion` | 飞剑黑烟更浓，猛地向下一沉，男主惨叫。 | 2s | `start_and_guide` 起始帧：黑烟加重；引导参考图：下沉惨叫 |

### SG06 双线尖叫与校场逼近

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S20 | B06.1 | `reaction` | 林小满青白灵光从手腕窜到脖颈，疼得大叫。 | 3s | `start_and_guide` 起始帧：灵光窜起；引导参考图：林小满大叫 |
| E1S21 | B06.2+B06.3 | `comedy_action` | 男主抱紧储物袋随飞剑下坠，与林小满尖叫交替加速。 | 4s | `start_and_guide` 起始帧：男主下坠；引导参考图：交替尖叫节奏 |
| E1S22 | B06.4 | `arrival` | 树林尽头校场出现，外门弟子列队，林小满强撑站直。 | 3s | `start_only` 起始帧：校场出现在前方 |

### SG07 校场失控入场

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S23 | B07.1 | `arrival` | 林小满盯山路说迟到给一星，男主远处冲出树林喊让开。 | 3s | `start_and_guide` 起始帧：林小满怒等；引导参考图：男主冲出树林 |
| E1S24 | B07.2 | `comedy_action` | 飞剑失速滑进校场，贴墙擦过，削掉一排晾晒道袍。 | 3s | `start_and_guide` 起始帧：失速入场；引导参考图：道袍被削飞 |
| E1S25 | B07.3 | `comedy_gag` | 道袍蒙住男主头，他瞎飞撞飞半块飞剑课木牌，众人“哦”。 | 3s | `start_and_guide` 起始帧：道袍蒙头；引导参考图：木牌被撞飞 |
| E1S26 | B07.4 | `comedy_action` | 男主扯掉道袍刚看清路，飞剑直扎进老槐树树杈并颤动。 | 3s | `start_and_guide` 起始帧：看见大树；引导参考图：飞剑扎树 |
| E1S27 | B07.5+B07.6 | `comedy_pause` | 男主被甩飞，脸先着地滑到林小满脚边；全场安静。 | 4s | `start_and_guide` 起始帧：男主飞出；引导参考图：脸扎地停在脚边 |

### SG08 极限送达

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S28 | B08.1+B08.2 | `service_success` | 男主趴地摸出药瓶递给林小满，林小满惊愕问你这么拼吗。 | 5s | `start_and_guide` 起始帧：趴地摸药；引导参考图：药瓶递到林小满面前 |
| E1S29 | B08.3 | `comedy_pause` | 男主脸贴地闷声讨五星好评。 | 3s | `start_and_guide` 起始帧：男主趴地；引导参考图：求好评冷笑点 |

### SG09 药力走偏与进入游戏

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S30 | B09.1+B09.2 | `reveal` | 林小满服下护脉丹后气息猛震，青白药力乱窜，身上冒青烟，膝盖一软。 | 5s | `start_and_guide` 起始帧：服丹；引导参考图：药力乱窜冒青烟 |
| E1S31 | B09.3+B09.4 | `relationship_shift` | 男主抬头，灰脸却眼神认真，提醒别动；林小满问怎么办，男主蹦起说我来助你。 | 5s | `start_and_guide` 起始帧：男主抬头认真；引导参考图：男主起身准备出手 |
| E1S32 | B09.5 | `gameplay_entry` | 进入游戏：摆筋脉。 | 1s | `review_only` 审核帧/转场：玩法入口；此 shot group 结束 |

### SG10 回归剧情

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S33 | B10.0+B10.1+B10.2 | `return_to_story` | 回归剧情后，林小满被迫摆出别扭调息姿势，围观弟子转头，她脸红喊不许看，男主让她忍一下。 | 5s | `start_and_guide` 起始帧：回归剧情调息姿势；引导参考图：林小满羞恼喊不许看 |
| E1S34 | B10.3 | `comedy_pause` | 林小满嘴硬催促，男主不好意思说“好了好了～给我通！” | 3s | `start_and_guide` 起始帧：林小满嘴硬偏头；引导参考图：男主尴尬出手 |
| E1S35 | B10.4+B10.6 | `ability_leak` | 男主指尖淡金火焰牵住药力，拨开堵塞灵脉；掌心火焰纹路一闪即逝。 | 5s | `start_and_guide` 起始帧：淡金火焰出现；引导参考图：掌心纹路亮起又消失 |
| E1S36 | B10.5+B10.7 | `reveal` | 林小满追问身份，男主硬说自己是霞丹鑫店长并讨好评，乌鸦飞过。 | 4s | `start_and_guide` 起始帧：林小满质问；引导参考图：男主挠头糊弄 |

### SG11 暗线钩子

| Shot | Source beats | Type | Visible action | Duration | Keyframe strategy |
|---|---|---|---|---:|---|
| E1S37 | B11.1 | `cliffhanger` | 林小满震惊羞恼、男主强装镇定；画面边缘青白灯火里血红眼睛一闪，钻入地缝。 | 4s | `end_hook` 结束帧：血红眼睛钻入地缝；资产参考图可选 |

## Evaluation Rubric

Candidate output should:

1. Keep shot count around 30-40 for this detailed 105-120s sample.
2. Preserve independent danger beats for 山魈侧扑、山石砸下、藤妖封路、藤蔓追近.
3. Preserve independent comedy beats for 灵符没反应、零失误立 flag、飞剑咔哒、校场连撞、五星好评.
4. End SG09 at `进入游戏：摆筋脉`.
5. Start SG10 at `回归剧情：`.
6. Label 起始帧、引导参考图、结束帧、资产参考图 explicitly; never collapse all as “参考图”.
7. Keep each shot to one primary action.
8. Keep most shots 3-5 seconds; use 7-8 seconds only with justification.
9. Avoid final camera/lens/lighting/prompt wording.
10. Leave enough keyframe guidance for downstream keyframe/video prompt skills.
