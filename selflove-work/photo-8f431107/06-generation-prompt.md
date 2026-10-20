# 06 生成提示词（交给 Codex 内置 image_gen）

## 用法

1. 把原照作为**编辑目标**传给 Codex 的图像工具（本机路径见 `01-photo-facts.md`）；已核验的电影小样只作**绘制语言证据**，不要把电影整帧一起塞进提示当参考图（本技能小样版也不含整帧）。
2. 建议单张图调用，保持 4:3 与 1702×1276 输出；不要裁切、不要加边框。
3. 生成后按最后一节逐项自检，并把结果与原照、`05-substitution-table.md` 对照。

---

## 主提示词（中文，完整版）

**任务**：把这幅真实自拍**完整重绘**成“迈尔斯本土世界 + 彼得·B·帕克原生世界”联合参考的漫画动画影像（两世界共用造型、材质与印刷语言）。这是在照片上重建绘制结果，**不是**给照片加漫画滤镜、调色、边缘检测、网点或纸纹叠加。

**必须保持（内容与构图，不得改动）**
- 画面比例 4:3（1702×1276）；两人自拍近景；两人位置、体型关系、头向、可见表情、遮挡关系不变。
- 左侧男性：深棕短发（被风吹起、有逆光发丝亮束）、镜面护目太阳镜、浅钢蓝灰连帽外套（帽兜在头后）、黑色拉链内搭（领口露少量紫色内衬）、前伸比 V 的手。
- 右侧女性：棕色波浪及肩发、椭圆深色半镜面太阳镜、浅紫（薰衣草）连帽外套（白色拉链带、右下驼色图案与 `CAMEL` 刺绣）、黑色针织圆领内搭、胸前比 V 的手、左耳青绿珠饰耳环。
- 背景结构位置不变：左前景叠石玛尼堆/石墙（含少量彩色涂绘小石）、木栈道板面、左下铺装地面、两侧深色针叶林山坡、远景岩壁与竖向雪线、上部蓝天与白云、右侧木构棚屋与栏杆以及远处游人（保留其疏密与体量，可以概括）。- 主光方向不变：高角度太阳，来自画面前方偏左上；人物正面受光、下巴与发下有短接触影；冷暗部来自蓝色天光。

**面部（默认必须执行的动画化重构）**
- 以本人可辨识锚点为基准重新设计：脸型长宽关系、眉形、眼睑、鼻体与鼻翼、嘴唇体积、下颌轮廓、发际与发型外形、年龄感。
- 用简洁体块 + 选择性线条表现额头、眼窝、颧颊、鼻侧、下颌；哑光皮肤，亮面与眼神留净；允许受控的动画化五官比例调整。
- **不要**保留写实照片脸 + 叠纹理；**不要**把两人换成迈尔斯或彼得，**不要**套同一张动漫脸或统一放大眼睛；两位人物必须保留彼此不同的脸型与神态。
- 两副太阳镜按原照处理：男性镜片是**镜面**，保留其反射的木构建筑与暖窗内容（简化色形 + 高光），**不补造眼睛**；女性镜片为深色半镜面，保留灰蓝天光与石墙轮廓的暗反射。镜片高光属留净区。

**人物轮廓线条（重要验收项）**
- 先画头发、肩背、手臂、衣服、腿与遮挡的动画体块与明暗转折，再分配**短而不等粗**的墨线：阴面/接触转折可加重，亮面可以无黑线由色面直接承接，发束、衣褶、关节处用少量渐细或断续线。
- 每位人物在整图尺寸下都要能看见线宽跳变与局部停笔；**不要**平滑连续的同宽描边，**不要**整圈彩色描边冒充线条设计。

**建筑与结构的线条**
- 石墙、木棚、栏杆、板缝按体块与受光转折组织选择性墨线；近处关键檐口/立柱/砌块转角可有粗细深浅变化，远景结构减线、降对比。
- 不要全图连续等粗纯黑勾边，不要给每块石头/每根木条封闭描框，不要用发光描边代替轮廓。

**材质（分别设计，不统一粗糙度）**
- 皮肤：哑光色面 + 有限柔和过渡；额头、眉间、鼻翼、眼口附近选择性线条；眼神与亮面留净。
- 头发：先整体体积与发束分群，再少量方向性亮束；不要逐根描线，不要换成别人的发型。
- 涂层尼龙外套（钢蓝灰与浅紫）：宽缓受光带 + 缝线结构；亮部不糊成塑料白斑，暗部保留布料褶皱厚度。
- 黑色针织内搭：大暗面为主，仅肩线与领口有窄亮边；不要全黑成一块死板剪影。
- 镜面/半镜面镜片：映像、透射、表面高光分层；保留原照的反射布局与遮挡，不增加反射对象。
- 石材（玛尼堆/石墙/铺装）：哑光宽面色面 + 砌缝与体积暗面分开，不出现镜面倒影。
- 木材（栈道板/棚屋/栏杆）：板缝与顺向纹理、厚度关系；不要把所有木头画成橙棕平铺纹。
- 针叶林：先分树干与树冠体块，近处少量纵向树皮线，远处合并为低细节深绿色团。
- 天空与云：大面积色面 + 网点过渡；云边界柔和，不做硬边白描。
- 雪线：承托面上的厚度与柔边，不是白色描边或自发光。

**光影**
- 一个主光（高角度前上偏左）；区分固有色、照明色、体积阴影、投影、接触暗部与反射。
- 暗部可有冷蓝色，但必须保留少量最深的稳定暗形（黑衣、发下、石缝）；不要整体降成三阶硬色块，也不要全场泛蓝。

**配色（按已核验替色表；HEX 是参照不是像素指令）**
- 天空高光/云最亮面 → 约 `#E2EEE8`（帧 390）。
- 云与雾化远天的中间调 → 约 `#9EA8BB`（帧 203，雾化淡蓝；**源照的饱和天蓝保留原色相**，不要按此降饱和）。
- 石砌墙中间调 → 约 `#6B696B`（帧 200）；石面亮部 → 约 `#C6C5C3`（帧 079）。
- 铺装受光面/暖中间色 → 约 `#CCB5AD`（帧 073）。
- 两人头发暗部与体积 → 约 `#3E373E`（帧 195）。
- 女性面部亮面与两人受光肤色上限 → 约 `#CE988D`（帧 305）；男性面部/颈部中间调 → 约 `#A27D79`（帧 305）；手背受光 → 约 `#DDBBAC`（帧 071）。
- 黑衣/发下/石缝等最深色域上限 → 约 `#222432`（帧 089）。
- 女性外套暗面与蓝紫布中间色 → 约 `#55699F`（帧 079）。
- 两副镜片暗底与暗反射 → 约 `#45434A`（帧 310）。
- **未匹配区规则**：远山岩壁、雾光、针叶林、木栈道、木棚栏杆、云、雪线、男性外套涂层布未找到可核验的同材质电影色。这些区域**按原照自身色相与明度关系重绘**，只迁移绘制语言（体块、选择性线条、网点/排线/丝网、彩版错位），**不要**用电影里的蓝板、车漆、室内白墙或瓦面颜色顶替，也不要自行编造新的电影色。这是本图“严格电影替色未完成”的部分，如实保留原照色彩逻辑。

**景深与主次**
- 焦点：两人面部与上半身。
- 近处遮挡（前伸的手、右下外套）可略柔；远景岩壁、林木、游人、棚屋降低结构细节、纹理与彩边对比，合并为低对比色团；远处窗格、小字与人脸细节可以不可读。
- 不要全景等锐或全景等糊，不要用锐利密网点把焦点抢回远景。

**四层印刷语言（缺一层即不合格；但也不能变成复古波点海报）**
1. **大圆点**：少量、可辨，只落在少数**原有色面**上（如外套受光面、石墙面、铺装面）；不要在脸上铺点。
2. **中尺度排线**：随形体与转折方向组织，用于阴影与体积读取（如下颌/鼻侧、衣褶暗面、石墙暗部、树木暗部）。
3. **低对比细丝网**：较大次要面上出现（天空、铺装、墙面、木面）；纹理越广对比越低；100% 观看时能区分它和压缩噪点。
4. **局部双彩印刷错版**：取色来自本图已定两色；**每位焦点人物**的身体/衣物外缘都要有局部窄幅错版（不能只有头发彩边）；背景结构边缘可更宽、更软、对比更低。核心形体稳定、五官对齐、遮挡正确；不做整图 RGB 平移、不做整圈彩虹贴纸边。

**留净区**：眼神与镜片高光、唇部、手指指节、人物亮面转折；印刷纹理不覆盖这些区域。

**明度预检（目标）**
- 原照整图 L* 分位：P25 21.8 / P50 43.7 / P75 58.3；P5 5.7 / P95 80.7。
- 输出应保持近似的整图明暗分布与排序：云/铺装/受光外套为亮端，黑衣与发下保持最深，森林中暗、远山中间调偏冷。
- 不要把整图统一压暗或提亮；暗部可以有色，但必须留住最深深暗锚点。

**动作、文字与附加模式**
- 动作：无（静姿，只有 V 手势，不加爆点、速度线、拟声字）。
- 文字：除原照既有的 `CAMEL` 刺绣外，**只允许**下方这一句已确认的内心字幕；不得再加标题、对白、拟声字或其他装饰文字。
- 不启用蜘蛛感应背景、不加故障破碎、不做分镜、不加 UI/黑边/撕纸/白贴纸圈。

**内心字幕（用户已于本轮明确确认，必须加入）**
- **逐字文案（必须完全一致，不得改写、不得译文）**：`风把头发吹乱了，这张我舍不得删。`
- **语言**：简体中文。**视角**：画面右侧女性的第一人称内心念头（不是对白，不是旁白，也不是男性的想法）。
- **形式**：单个**横向矩形**黄色内心框；平直边、近黑色粗边；黄底内带细密红/深色半调网点；**不要**指向嘴部的尖尾（避免被读成对白）。
- **字形**：黑色、手写、略倾斜、笔画有粗细起伏的大字；短句**单框**，不拆句。
- **位置**：画面**上方留白区**（天空/云一带，建议横向居中偏右、与两人头部保持距离）；不得遮挡眼睛、脸、太阳镜、嘴唇、手、发际或其他身份锚点，也不得压住 `CAMEL` 刺绣。
- **尺寸与对比**：框高约为画面高度的 8%–12%，宽度按句子长度决定；对比要够高以保证即时可读，但不得用大黄框淹没画面。
- **逐字核验**：出图后逐字比对，任何缺字、错字、乱码、挤压或笔画粘连都算未通过；此时**放弃画面内文字**，改出无文字版由你后期加字，不要把近似字当准确文案交付。

**禁止导入**：电影角色本人及其服装、发型、道具、标志、电影字幕与 UI、播放器界面、破损与特殊能力、原照不存在的楼体/植被/天气/灯具。

---

## Condensed English instruction（同一决策，供图像工具使用）

> Full redraw (no photo layer, no filter) of the attached selfie into a hand-drawn animated comic frame in the Miles-morales-home / Peter-B-616 native-world shared language. Keep 4:3, both people, their positions, head angles, sunglasses, jackets (steel-blue hooded nylon on the left, lavender hooded nylon with white zip and a small camel logo on the right), black inner tops, both V-hand gestures, and the background layout (stacked-stone cairn and stone wall on the left with a few painted stones, wooden boardwalk planks, sunlit paving lower-left, dark conifer slopes, distant hazy rock walls with snow streaks, blue sky with soft cumulus, wooden hut and railing with distant visitors on the right). Keep the single high sun from the front-upper-left, short contact shadows, cool blue ambient in the shadows. Rebuild both faces as designed cinematic animation heads (block-based planes, selective lines, matte skin, clean highlight areas) while keeping each person recognizable and clearly different from the other; do not swap in film characters, do not use one shared anime face, do not keep a photoreal face with texture on top. Mirror sunglasses stay opaque and keep their simplified reflected content. Design contour lines with deliberate width changes and local line breaks, letting lit edges be carried by flat colour instead of black outlines; no uniform black outline, no rainbow glow outline. Distinct material responses: matte skin, grouped hair masses with a few directional light strands, coated nylon with broad light bands and visible seams, black knit kept dark with only narrow light edges, matte stone with joints separated from volume shadows, wood with plank joints and grain direction, conifers merged into low-detail dark masses in the distance, sky and clouds as broad colour fields with halftone transitions, snow with soft thick edges. Depth: focus on faces and upper bodies, distant rock, forest, visitors and hut reduced in detail, texture and colour-fringe contrast. Print language, all four visible: a few readable large dots on existing colour planes, mid-scale hatching following form and shadow, wide low-contrast fine screen mesh on larger secondary surfaces, and local two-colour misregistration on each person's body/clothing edges (narrow) plus softer wider low-contrast misregistration on background structure edges. Keep eyes, lips, fingers and mirror highlights clean. Verified colour anchors: sky highlight #E2EEE8, hazy sky #9EA8BB, stone midtone #6B696B, stone light #C6C5C3, warm paving #CCB5AD, hair dark #3E373E, skin light #CE988D, skin mid #A27D79, hand highlight #DDBBAC, deepest dark #222432, blue-violet cloth #55699F, dark lens #45434A. For distant rock, forest, boardwalk, hut, clouds, snow and the left jacket, no verified film colour exists: keep the photo's own hues and value relationships and only translate the drawing language; do not substitute film blue panels, car paint, interior walls or roof tiles. no borders, no UI, no added characters, props or buildings, no action effects. Add exactly one inner-monologue caption and no other text: a single wide yellow rectangular thought box, flat near-black thick border, fine halftone dots inside the yellow, no speech tail pointing at any mouth, placed in the upper empty sky area clear of both faces, sunglasses, hands, hairlines and the camel embroidery; inside it, bold slightly slanted handwritten black Simplified-Chinese characters reading exactly: 风把头发吹乱了，这张我舍不得删。 — this is the right-hand woman's first-person inner thought. Verify every character after generation; if any character is wrong, missing or malformed, output the version without any in-image text instead.

---

## 生成后自检清单

1. **文件**：能打开、方向正确、比例仍为 4:3（±1%）、无黑边。
2. **内容**：仍是两个人、位置/遮挡/手势/眼镜/服装款式与配色一致；背景石墙、栈道、木棚、远山、云的位置关系未变；远处游人没有被清空，也没有新增楼体。
3. **完整重绘**：忽略点/线/彩边后，人物和环境是否仍独立读作**绘制动画**？脸上是否同时做到“动画重构”与“本人可辨”？
4. **人物线条**：整图与放大两种尺度下，每位人物是否都有线宽跳变、局部停笔与色面承接？若只有平滑同宽轮廓 + 彩边，判造型失败。
5. **材质**：皮肤/头发/涂层布/黑色针织/镜片/石材/木材/林木/天空/雪是否各有不同响应？镜片是否仍是镜面且不补造眼睛？
6. **光影与配色**：主光方向、投影、接触暗部是否按原照？整图 L* 分位与明暗排序是否接近原照？未匹配区是否保持原照色相而没有被电影蓝/车漆色顶替？
7. **四层印刷**：缩小能看到大点与排线的分工，100% 能看到低对比细网目；局部双彩错版是否在**身体/衣物**上可辨（不是只有头发），且核心形体不裂？
8. **景深**：远景是否退后、主体是否突出；有没有抠图白边、模糊侵入脸部、背景锐利纹理抢焦？
9. **内心字幕（已确认项，单独验收）**：黄色矩形框、黑粗边、黄底细网点、无尖尾；文案逐字为 `风把头发吹乱了，这张我舍不得删。`，简体中文、手写略斜、单框；位置在画面上方留白区，未遮挡脸/眼/镜片/唇/手/发际与 `CAMEL` 刺绣；字形无缺字错字。任一项不满足即按“放弃画面内文字、改出无文字版”处理。
10. **污染检查**：除第 9 项那一句外，没有电影角色、标志、其他字幕、UI、拟声字、分镜、感应线、故障碎块、无来源光球。
