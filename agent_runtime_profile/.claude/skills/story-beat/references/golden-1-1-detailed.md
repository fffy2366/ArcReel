# Golden Sample: `1-1.md` Detailed Story Beat Breakdown

Source: `/Users/diamond/Desktop/剧游设计/修真外卖正文/第01章/1-1.md`

Purpose: calibrate `story-beat` detailed mode for mission/gameplay/comedy interactive drama. This is a golden sample, not a final storyboard. It preserves parent/micro beat structure, visible action, state change, duration guidance, gameplay-entry boundary, and evaluation criteria.

## Metadata

```json
{
  "content_format": "interactive_drama_game",
  "subtype": "mission_gameplay_comedy",
  "source_id": "1-1",
  "granularity": "detailed",
  "player_role": "男主",
  "heroine_focus": "林小满",
  "mission_context": "S级订单：半炷香内送达下品护脉丹，迟到会被差评",
  "estimated_total_duration_sec": "115-130",
  "micro_beat_count": 47,
  "estimated_shot_or_clip_count": "32-38 after shot-director merges compatible 2s micro beats",
  "assumptions": [
    "此样例用于 detailed 微拆，因此会比普通剧情 Beat 更细。",
    "“进入游戏：摆筋脉”是玩法入口和分镜结尾，不在 story-beat 阶段设计玩法机制。",
    "按原文标记执行：“进入游戏：摆筋脉”后立即出现“回归剧情：”，因此后续调息姿势、淡金火焰、身份追问和暗线钩子都作为回归剧情继续拆分。"
  ]
}
```

## Parent Beat Overview

| Parent | Function | Summary | Duration |
|---|---|---|---:|
| G01 | `delivery_mission` | 开场建立破旧飞剑、S级订单、半炷香倒计时和差评压力。 | 10-12s |
| G02 | `route_danger` | 三只山魈连续袭击，男主用飞剑低空闪避。 | 10-12s |
| G03 | `route_danger` / `comedy_gag` | 藤妖封路，男主用受潮灵符险险脱身。 | 11-13s |
| G04 | `escalation` | 男主暂时得意，林小满校场濒临经脉失控，双线倒计时加压。 | 9-11s |
| G05 | `reversal` / `comedy_gag` | 男主刚吹零失误，飞剑故障冒烟下坠。 | 10-12s |
| G06 | `escalation` | 男主坠落和林小满经脉暴冲交替尖叫，校场进入视野。 | 10-12s |
| G07 | `comedy_action` | 飞剑失控滑入校场，连环撞击后男主摔到林小满脚边。 | 14-17s |
| G08 | `service_success` | 男主趴地极限送达，林小满震惊，他仍讨五星好评。 | 7-9s |
| G09 | `gameplay_entry` | 护脉丹药力走偏，男主准备出手，分镜以“进入游戏：摆筋脉”结束。 | 10-12s |
| G10 | `ability_leak` / `comedy_gag` | 按“回归剧情”标记继续拆：林小满被迫调息、淡金火焰牵引药力、身份异常暴露，男主用店长身份糊弄。 | 14-17s |
| G11 | `branch_cliffhanger` | 青白灯火里的血红眼睛钻入地缝，留下暗线钩子。 | 3-5s |

## Detailed Micro Beats

### G01 配送任务建立

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B01.1 | `opening_hook` | 晨雾未散，破旧飞剑贴着竹林低空呼啸掠过，剑身像快散架的青铁叶。 | 以“穷酸但高速”的修真外卖视觉建立开场吸引力。 | 3s |
| B01.2 | `delivery_mission` | 男主踩剑赶路，腰间灰扑扑储物袋露出红色十字送丹标志。 | 男主身份从普通修士明确为修真外卖员。 | 2s |
| B01.3 | `delivery_mission` | 传音玉简里林小满急声催单，飞剑课马上点名。 | 任务从赶路变成即时催单压力。 | 3s |
| B01.4 | `delivery_mission` | S级订单信息浮现：林小满、下品护脉丹、半炷香、迟到差评。 | 明确倒计时、收货人、物品和失败惩罚。 | 3s |
| B01.5 | `comedy_gag` | 男主倒吸气，惶恐念叨再有差评就要吊销执照。 | 危机从任务失败变成男主职业生存危机，喜剧口吻成立。 | 2s |

### G02 山魈三连袭击

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B02.1 | `threat_arrival` | 三只小山魈从山坡扑下，尖叫着砸向飞剑。 | 配送路线突变为妖兽伏击。 | 2s |
| B02.2 | `evasive_maneuver` | 男主脚尖一压，飞剑贴地俯冲钻进竹林，第一只山魈撞断青竹。 | 第一次险避，表现飞剑低空配送的危险感。 | 3s |
| B02.3 | `near_miss` | 第二只山魈从侧面扑来，男主侧身躲开，爪子擦着头发削过。 | 近身擦过，危险从宏观追击变成身体级威胁。 | 3s |
| B02.4 | `evasive_maneuver` | 第三只山魈砸下山石，男主借飞剑尾部一摆钻出，石块在身后炸碎。 | 障碍升级为重击，男主靠熟练配送身法脱险。 | 3s |

### G03 藤妖封路与受潮灵符

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B03.1 | `route_danger` | 青竹藤妖从地下窜起，在前方织成大网。 | 路线被封死，危机从追击变成拦截。 | 3s |
| B03.2 | `evasive_maneuver` | 男主在飞剑上一跃，飞剑从藤缝穿过，男主身体从藤网上方滑过。 | 闪避动作形成奇观和轻喜剧身段。 | 3s |
| B03.3 | `route_danger` | 十几根细藤从后方追来，距离快速缩短。 | 逃过前网后，追击压力重新压上来。 | 2s |
| B03.4 | `comedy_gag` | 男主甩出皱巴巴低阶灵符，大喝“爆”，灵符贴上藤蔓却没反应。 | 道具失灵制造喜剧停顿，同时把危险悬住。 | 3s |
| B03.5 | `near_miss` | 藤蔓即将缠住男主时，灵符延迟爆炸，把藤蔓炸得缩回。 | 失败道具反转成险险脱身，危险与笑点同时释放。 | 3s |

### G04 双线倒计时与反差得意

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B04.1 | `transition` | 快速蒙太奇：男主从树梢上方掠过，山魈在下方扑空尖叫。 | 男主暂时甩开追兵。 | 2s |
| B04.2 | `escalation` | 林小满站在飞剑课校场，体内灵脉乱冲，疼得猛吸气。 | 收货人危机第一次被具体可视化。 | 3s |
| B04.3 | `comedy_gag` | 男主回头见妖兽甩远，松口气，得意整理被风吹歪的头发。 | 男主误以为危机解除，为下一次反转立 flag。 | 2s |
| B04.4 | `escalation` | 林小满手按胸口、脸色发白，咬牙反复念“还不到”。 | 倒计时由订单界面转为林小满身体危机。 | 3s |

### G05 飞剑故障反转

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B05.1 | `comedy_gag` | 男主对身后山魈比胜利手势，吹“专业配送，零失误”。 | 自信爆棚，喜剧 flag 明确。 | 2s |
| B05.2 | `reversal` | 飞剑脚下忽然咔哒一声，男主低头。 | 危机源从外部妖兽转为交通工具故障。 | 2s |
| B05.3 | `route_danger` | 飞剑咔哒咔哒，剑身一顿一顿往下掉，男主笑容僵住。 | 失控感逐步出现，男主从得意变恐慌。 | 3s |
| B05.4 | `comedy_gag` | 飞剑尾部喷黑烟，男主掐诀哄“老伙计，撑住”。 | 把破旧飞剑拟人化，形成角色关系和笑点。 | 3s |
| B05.5 | `escalation` | 飞剑黑烟更浓，像生气一样猛地下沉，男主惨叫。 | 故障升级为坠落。 | 2s |

### G06 双线尖叫与校场逼近

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B06.1 | `escalation` | 切林小满，青白灵光从手腕窜到脖颈，她疼得大叫。 | 林小满经脉危机同步升级。 | 3s |
| B06.2 | `escalation` | 切男主，飞剑拖黑烟下坠，男主抱紧储物袋喊不能迟到。 | 配送员优先保护订单，人物喜剧职业性格强化。 | 3s |
| B06.3 | `comedy_action` | 男主和林小满尖叫交替切换，一个快摔，一个快炸，节奏越来越快。 | 两条危机通过声音和剪辑合成一个倒计时高潮。 | 4s |
| B06.4 | `arrival` | 树林尽头校场出现，外门弟子列队，林小满强撑站直。 | 目的地到达，但失控状态仍未解除。 | 3s |

### G07 失控入场连环笑点

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B07.1 | `arrival` | 林小满盯着山路，咬牙说迟到就给一星；远处男主冲出树林喊让开。 | 收货人怒气和男主到达在同一刻碰撞。 | 3s |
| B07.2 | `comedy_action` | 飞剑失速滑进校场，贴墙擦过，削掉一排晾晒道袍。 | 到达方式从救场变成灾难式入场。 | 3s |
| B07.3 | `comedy_gag` | 道袍蒙住男主头，他瞎飞撞飞半块飞剑课木牌，众人发出“哦”。 | 视觉遮挡制造连环失控笑点。 | 3s |
| B07.4 | `comedy_action` | 男主扯掉道袍刚看清路，飞剑直扎进老槐树树杈并颤动。 | 飞剑失控以夸张物理动作收束。 | 3s |
| B07.5 | `comedy_action` | 男主被惯性甩飞，脸先着地，贴地滑到林小满脚边。 | 配送员从空中英雄降级为狼狈地面求生，喜剧落点完成。 | 4s |
| B07.6 | `comedy_gag` | 全场“哦”声后安静，男主脸还扎在地里。 | 喧闹转静默，给递药动作留出喜剧停顿。 | 2s |

### G08 极限送达与五星好评

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B08.1 | `service_success` | 男主艰难摸储物袋，玉质药瓶滚入掌心，他颤巍巍递给林小满。 | 从摔飞失败感反转为准时完成服务。 | 3s |
| B08.2 | `relationship_shift` | 林小满低头看他，惊愕问“你这么拼的吗？” | 林小满从愤怒差评转为震惊和微妙认可。 | 3s |
| B08.3 | `comedy_gag` | 男主趴地闷声说“麻烦给个五星好评”。 | 情绪不走煽情，立刻回到职业讨评笑点。 | 2s |

### G09 药力走偏与玩法入口

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B09.1 | `escalation` | 林小满迅速夺药服下，药力入喉后气息没有平复，反而猛震。 | 配送完成后转入新危机。 | 3s |
| B09.2 | `route_danger` | 青白药力光点在经脉里乱窜，林小满身上冒青烟，膝盖一软。 | 危险从路途追击转为体内药力失控。 | 3s |
| B09.3 | `relationship_shift` | 男主抬头，脸上灰还没擦净，眼神立刻认真，提醒别乱动。 | 男主从狼狈喜剧态切换为专业救治态。 | 3s |
| B09.4 | `gameplay_entry` | 林小满问怎么办，男主从地上蹦起说“我来助你”。 | 剧情救治危机转到玩家操作入口。 | 3s |
| B09.5 | `gameplay_entry` | 明确出现“进入游戏：摆筋脉”。 | 当前剧情分镜以玩法入口结束；不在 story-beat 阶段设计玩法机制。 | 1s |

### G10 回归剧情：能力泄露与反差糊弄

> 按原文标记执行：`回归剧情：` 紧跟在 `进入游戏：摆筋脉` 后，因此以下内容全部作为回归剧情继续拆分，不再推测玩法机制。

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B10.0 | `transition` | 原文出现“回归剧情：”标记。 | 明确从玩法入口返回剧情分镜；标记本身不生成画面。 | 0s |
| B10.1 | `comedy_gag` | 林小满还想反驳，体内药力乱冲，被迫摆出别扭调息姿势，围观弟子转头。 | 回归剧情后先承接玩法结果，女主进入羞耻调息状态。 | 3s |
| B10.2 | `relationship_shift` | 林小满脸红喊不许看，男主深吸气让师姐忍一下。 | 两人关系从配送/救治转为尴尬近距离协助。 | 3s |
| B10.3 | `comedy_gag` | 林小满嘴硬催促，男主不好意思地说“好了好了～给我通！” | 羞恼与男主笨拙救治形成轻喜剧节奏。 | 3s |
| B10.4 | `ability_leak` | 淡金色火焰从男主指尖一闪而过，牵住紊乱药力，拨开堵塞灵脉。 | 男主隐藏能力第一次具体显现。 | 4s |
| B10.5 | `secret_reveal` | 林小满睁大眼，指出这不是护脉丹药力，追问男主身份。 | 女主对男主身份认知从送丹店长变成可疑异人。 | 3s |
| B10.6 | `ability_leak` | 男主掌心极淡火焰纹路亮一下又消失。 | 能力伏笔被视觉确认。 | 2s |
| B10.7 | `comedy_gag` | 男主硬着头皮说自己是霞丹鑫店长，问能不能给好评，乌鸦飞过。 | 神秘揭露被男主市井求评打断，形成反差冷笑点。 | 4s |

### G11 暗线钩子

| Beat | Function | Visible action | State change / screen value | Duration |
|---|---|---|---|---:|
| B11.1 | `branch_cliffhanger` | 林小满震惊羞恼、男主挠头强装镇定；画面边缘青白灯火里一双血红眼睛闪过并钻入地缝。 | 局部救治事件扩展成隐藏观察者/后续威胁。 | 4s |

## Compression Guidance

If target runtime is shorter than 115-130 seconds:

- Preserve B01.1-B01.5 because they establish world, mission, countdown, and comedic service premise.
- Preserve at least three distinct route dangers: one 山魈近身、one 山石爆碎、one 藤妖封路/灵符受潮.
- Preserve B05.1-B05.5 because the "零失误" flag and flight failure are the major comedic reversal.
- Preserve B07.2-B07.5 because the校场失控入场 is the main slapstick payoff.
- Preserve B09.3-B09.5 because gameplay entry must be a clean shot-group ending.
- Preserve the explicit `回归剧情：` boundary.
- Preserve B10.4-B10.7 and B11.1 because ability leak, identity suspicion, comedic deflection, and dark watcher are forward hooks.
- Compress by merging repeated crowd reaction beats or reducing montage inserts, not by deleting named dangers.

## Evaluation Rubric

A candidate story-beat output for `1-1.md` should pass:

1. Mark `content_format: interactive_drama_game` and `subtype: mission_gameplay_comedy`.
2. Use `detailed` granularity or an equivalent parent/micro structure.
3. Do not collapse the full delivery route into one generic route danger beat.
4. Include separate beats for 山魈三连、藤妖封路、受潮灵符、飞剑故障、校场失控入场.
5. Mark “进入游戏：摆筋脉” as a gameplay-entry ending boundary, not a mechanic design task.
6. Follow the source marker exactly: since `回归剧情：` appears immediately after gameplay entry, treat the following text as returned story/cutscene beats.
7. Include estimated durations where micro beats can be 2-4 seconds.
8. Mark ability leak and blood-eye watcher as separate forward-hook beats.
9. Avoid final camera/lens/lighting/keyframe/video prompt language.
10. Preserve comedy timing: failed prop pause, crowd “哦”, “五星好评”, and 乌鸦冷场 should not be flattened into generic action.
