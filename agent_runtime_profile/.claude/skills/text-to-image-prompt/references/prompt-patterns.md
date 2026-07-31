# Prompt Patterns

## 5-Part Visual Formula

Use this when the user wants a complete image prompt from an idea.

1. Camera and composition:
   - Composition: centered symmetry, one-point perspective, rule of thirds, leading lines, or another clear layout.
   - Camera position: low-angle upward shot, eye-level shot, high-angle downward shot.
   - Framing: full body, half body, close-up, panorama.
   - Depth: everything clear, subject only clear, soft edge blur, shallow depth of field.

2. Subject:
   - Age, gender, identity, visible traits.
   - Face, makeup, hair, facial features.
   - Clothing color, material, silhouette.
   - Action and pose: relaxed/contracted, still/moving, body direction.

3. Environment:
   - Indoor/outdoor and precise place type.
   - Weather, time, and emotional tone shown through visible details.
   - Foreground and background anchors.

4. Light:
   - Direction: above, side, back, front, specific source.
   - Quality: soft, even, hard, harsh, directional.
   - Effects: reflection, neon, backlight, warm-cool contrast, none.

5. Color and texture:
   - Palette: warm, cool, warm-cool contrast, multicolor.
   - Saturation: saturated, pale, muted.
   - Texture: clean and smooth, grainy, rough, film still, real photography, illustration, 3D.

Example:

```text
镜头：低角度仰拍，中广角镜头，人物全身与周围环境都清晰可见，全景，大景深。
构图：中心对称与引导线构图，人物处于画面中心，两侧楼梯线条把视线拉向主体。
主体：穿红色西装与黄色内衬马甲的人，双臂舒展，在楼梯上起舞。
环境：连接上下街区的狭窄户外长街梯，两侧是高耸老旧公寓楼，形成夹击感。
光源：天空光从上方照下，在人物头顶、肩膀和阶梯积水上形成反光。
色调：高饱和暖调主导，红绿撞色，电影胶片颗粒质感。
```

## Reverse Image Prompt

When the user provides an image or asks to reverse-engineer a style, describe it as a prompt that can recreate a similar work.

Use these angles:

- Subject and scene setting.
- Style reference or medium.
- Color palette and tone.
- Composition and perspective.
- Detail supplements, light, texture, foreground/background.

Instruction template:

```text
分析这张图片，并生成一个能够指导 AI 作图工具重新创作类似作品的文生图提示词。提示词需从主体内容、场景设定、风格参考、色调色彩、构图视角、细节补充这些角度描述图片。
```

## Character Modular Prompt

Use this for portraits, character sheets, role images, recurring characters, and cases where the user wants to adjust one part without rebuilding the whole prompt.

Modules:

1. Role setting: one sentence describing who the character is and the overall aura.
2. Facial features: face shape, eyes, brows, skin, expression, marks.
3. Hair and accessories: hairstyle, length, ornament, texture.
4. Outfit and makeup: color, material, silhouette, gradient, surface detail.
5. Pose and action: posture, hand placement, gaze direction, body direction.
6. Environment and props: platform, room, street, symbolic object, foreground/background.
7. Light and texture: source direction, contrast, final medium.

Example modules:

```text
角色设定：女性，约22-25岁，体态轻盈，清冷、空灵、神秘，带有星辰般的孤高气质。
脸部特征：精致鹅蛋脸，五官清冷秀美，眉眼低垂，眼神疏离，眼尾下方有一颗银色泪滴，白皙肤色。
发型发饰：黑发及腰，发丝间散落细小星尘碎屑。
服装妆容：深蓝到银白渐变的星纱长裙，多层轻薄半透明材质，表面布满疏密有致的细小光点。
姿态动作：赤足站在浅灰石材高台边缘，双手在胸前轻轻捧住纸鹤，姿态安静，透出温柔期许。
```

## 12-Part Keyword Structure

Use this when the user wants comma-separated image keywords or multiple style variants.

Order:

```text
图片风格, 景别描述, 画面色彩, 摄影手法, 主体描述, 动作描述, 表情描述, 氛围描述, 画面效果, 画面细节, 光线描述, 背景描述
```

For an "AI image prompt agent" style response, generate 5 different style keyword groups unless the user requests a different count.

Example:

```text
写实风格，近景，以白色和浅蓝色为主色调，精准对焦摄影，海边少女有白皙皮肤，穿白色离肩上衣与浅蓝色牛仔裤，上衣衣角随意塞进裤子，双臂交叉抱在胸前，微微歪头，眼神灵动，带淡淡笑意，青春活力氛围，画面清晰锐利，色彩明快，顶级画质，细节纤毫毕现，明亮自然光均匀照亮少女并突出面部细节，背景是浅蓝天空与白色海浪
```

## Avoid Prompt Pollution

### Replace abstract words with visible evidence

Weak:

```text
一个很治愈、很有电影感的女生。
```

Better:

```text
清晨的城市公交站，一个女生站在阳光里等车。她穿白色衬衫，晨光照亮衣服和脸部轮廓，风轻轻吹动头发。远处街道有行人和缓慢驶过的车辆，画面干净明亮。
```

Break feelings into:

- Space: where the person is.
- Action: what the person is doing.
- Objects: important visual anchors.
- Light and composition: how the viewer sees the scene.

### Replace negative words with positive results

Weak:

```text
不要下雨。不要夸张表情。不要动漫风。
```

Better:

```text
晴天午后，阳光照在地面，空气清透。人物表情平静，嘴唇自然闭合，眼神放松，面部肌肉自然。真实摄影质感，自然皮肤纹理，真实镜头光影。
```

Formula:

```text
否定内容 -> 明确地点 + 明确状态 + 明确材质 + 明确光线
```

### Replace template words with real actions

Template words often trigger stock imagery: 创业, 约会, 直播, 庆祝, 成功, 商务, 职场, 旅行.

Formula:

```text
模板大词 -> 具体人物 + 真实空间 + 连续动作 + 关键物体 + 自然状态
```

Examples:

```text
凌晨的小房间里，一个年轻人坐在折叠桌前修改方案。桌上放着泡面盒、笔记本电脑和写满修改痕迹的草稿纸。房间灯光很暗，电脑屏幕和小台灯照亮他的侧脸，他盯着屏幕认真思考。
```

```text
两个人坐在便利店门口的长椅上，一人手里拿着热饮，另一人低头笑着看她。旁边是路灯和安静的夜晚街道，两个人穿普通日常衣服，身体自然靠近。
```

### Specify directional object relationships

For phones, tablets, monitors, drawing paper, mirrors, books, car doors, weapons, and cup handles, specify:

- Person's body direction.
- Gaze direction.
- Object orientation.
- Hand contact.
- Camera angle.
- Which side the viewer can see.

Formula:

```text
人物朝向 + 视线方向 + 物体朝向 + 手部动作 + 镜头角度
```

Examples:

```text
医院病房里，一个年轻人靠坐在病床上，双手拿着一台平板电脑。平板屏幕朝向人物，屏幕背面朝向镜头，人物低头注视屏幕，中景侧面视角。
```

```text
一个小男孩坐在桌边画画，身体侧对镜头，画纸平放在桌面上，画纸顶部朝向男孩，底部朝向镜头。男孩低头看着画纸，右手握住彩色铅笔，镜头从桌面侧前方拍摄。
```

## Universal Prompt Formula

```text
时间与地点 + 人物身份与外观 + 正在进行的动作 + 关键物体与空间关系 + 表情和身体状态 + 光线、构图与景别 + 最终媒介质感
```

Examples:

```text
清晨的城市公交站，一个二十岁左右的女生站在站牌旁等车。她穿白色衬衫和浅色长裙，双手自然握着帆布包。风轻轻吹动她的头发，远处街道有行人和缓慢驶过的车辆。晨光从侧后方照亮人物轮廓，中景，三分法构图，浅景深，真实摄影质感，自然皮肤纹理。
```

```text
凌晨的小出租屋里，一个二十多岁的年轻人坐在折叠桌前修改方案。他穿普通灰色卫衣，左手扶着额头，右手操作笔记本电脑。桌面放着泡面盒、咖啡杯和写满修改痕迹的草稿纸。电脑屏幕和小台灯照亮人物侧脸，中景侧面视角，房间安静，真实摄影质感。
```

```text
夜晚的便利店门口，一男一女并排坐在长椅上。女生双手捧着热饮，男生微微侧过身体看向她，低头轻轻笑了一下。路灯从侧后方照亮两人的轮廓，背景是安静街道和模糊车灯，中景，浅景深，真实自然的日常氛围。
```

## Pre-Generation Checklist

Before finalizing, check:

- Does the prompt accidentally name objects the user does not want?
- Are abstract words supported by visible evidence?
- Are template words replaced with concrete actions?
- Is the person's action clear?
- What is the person holding?
- Where is the person looking?
- Which direction is the person's body facing?
- For screens, drawings, mirrors, books, and other directional objects, is the orientation clear?
- Do space, subject, light source, and camera angle conflict?
- Does the prompt tell the AI what should appear instead of only what to avoid?
