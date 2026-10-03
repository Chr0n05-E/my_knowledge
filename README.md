# 分层知识图谱知识库

这是一个「用 Markdown 写内容、用 frontmatter 描述结构、用脚本生成图谱」的个人知识库骨架。
目标形态就是你描述的那样：

```
顶层领域（工程学 / 数学 / 理学 / 文学 / 美学）
   └── 分支（计算机科学 / 解析数论 / 代数 / 书法 …）
         └── 更深的分支（算法 / 群论 / 行草 …）
               └── 叶子节点 = 你对某个概念的阐释和理解
```

同时它还有第二种视角：**任意两个节点之间可以连边**（双链），所以它既是树，也是图。

---

## 1. 设计要点：为什么这么搭

小白最容易踩的坑是把「知识库」当成「找一个软件然后把东西丢进去」。真正决定成败的是三层分离：

| 层 | 你用什么 | 说明 |
|---|---|---|
| **数据层** | 一个 `notes/` 目录里的纯 Markdown 文件 | 不锁定任何软件。任何编辑器、任何脚本、十年后都能读。这一层必须是你自己的。 |
| **结构层** | 每个文件顶部的 YAML frontmatter + 双链 | 「层级」和「关联」被显式写出来，而不是藏在某个软件的数据库里。 |
| **视图层** | `out/graph.html`（可交互）、`out/KNOWLEDGE-MAP.md`（大纲/思维导图）、`out/graph.json`（给别的工具） | 视图是可再生的产物，随时可以删掉重建，也可以换成别的工具。 |

这样做的直接好处：

- **层级不需要额外配置**：`id` 就是文件路径，父节点由路径自动推出；想给一个概念再挂到第二个父节点下，只加一行 `parents` 即可。
- **叶子节点的价值是可检验的**：脚本会检查概念笔记里有没有「我的理解」这一章。知识库里最贵的不是摘抄，是你自己的话。
- **视图随时可以换**：换成 Obsidian 的 graph view、换成 markmap 的思维导图、换成 Gephi 的图分析，都只是读同一份 `graph.json`。

---

## 2. 目录结构

```
E:\Knowledge\
├─ notes/                          ← 你的全部内容都在这里（唯一需要长期手工维护的地方）
│  ├─ engineering.md               工程学
│  ├─ engineering/
│  │  └─ computer-science.md       计算机科学
│  │     └─ computer-science/algorithms.md
│  │        └─ .../algorithms/binary-search.md    ← 叶子：你自己的理解
│  ├─ math.md  math/algebra.md  math/algebra/linear-algebra.md
│  ├─ science.md  literature.md  aesthetics.md
├─ templates/                      ← 新建笔记用的两个模板
│  ├─ concept.md                   叶子概念笔记模板
│  └─ domain.md                    分支/领域节点模板
├─ tools/
│  ├─ build.py                     校验 + 生成三个视图（含图片拷贝到 out/assets/）
│  ├─ new.py                       按模板新建一条笔记
│  ├─ make_sample_figure.py        生成示例插图（演示图片管线）
│  └─ viewer/index.html            图谱查看器模板（build.py 把数据塞进去）
└─ out/                            构建产物，可以随时删（已 gitignore）
   ├─ graph.html                   ★ 双击打开：左侧折叠树 + 右侧正文 + 全局力导向图
   ├─ KNOWLEDGE-MAP.md             缩进大纲，可直接喂给 markmap / Markmind
   └─ graph.json                   节点+边，给别的工具用
```

---

## 3. 三条命令

```powershell
# 1) 新建一条笔记（自动放在正确的目录，frontmatter 自动填好）
python tools\new.py math/algebra/group-theory --title 群论 --tags 代数,抽象代数

# 2) 写内容（任何编辑器：记事本 / VS Code / Obsidian / 思源 都行）
code notes\math\algebra\group-theory.md

# 3) 重建图谱并打开
python tools\build.py --open
```

`build.py` 会做校验并打印报告，例如：

```
知识库构建报告  2026-10-03 18:55
  节点 16 个（领域 12 / 概念 4），链接边 25 条
  警告 math/algebra/group-theory: 缺少章节 ['我的理解']（叶子节点本该是你自己的理解）
  警告 math/algebra/group-theory: 链接 [[某某]] 指向不存在的节点（先建空笔记也算）
```

加 `--strict` 时只要有警告就返回非零退出码，适合挂进 git pre-commit。

---

## 4. 笔记约定（整个系统唯一需要记住的规则）

### 4.1 frontmatter 字段

```yaml
---
id: math/algebra/linear-algebra     # 必须等于相对 notes/ 的路径（不含 .md），脚本会校验
title: 线性代数                      # 图谱上显示的名字
type: concept                       # domain（领域/分支节点）| concept（叶子概念）
parents: [math/algebra, engineering/computer-science]   # 父节点，可多个；第一项与目录一致
aliases: [Linear Algebra, 线代]      # 别名，双链可以直接写别名
tags: [代数, 矩阵]
status: evergreen                   # seed 未成形 | growing 在写 | evergreen 已稳定
created: 2026-02-14
updated: 2026-02-14
---
```

要点：

- **`id` = 路径**。所以「层级」天然存在，不需要额外配置；`notes/math/algebra/group-theory.md` 的 id 就是 `math/algebra/group-theory`。
- **`parents` 可以写多个**。这是树与图的接口：树只认第一个（与目录一致的那个）父节点，其余父节点会以虚线画进图谱。典型用法：`线性代数` 同时挂在 `代数` 和 `计算机科学` 下。
- `title` 重复时脚本会警告（双链解析会歧义）。
- 想换语言/换分类体系都随便，脚本不关心 id 里的词是什么，只关心路径存在。

### 4.2 双链与图片

在正文里写 `[[math/algebra|代数]]` 或 `[[群论]]`（先按 id 精确匹配，再按 title / 别名匹配）。
找不到目标时脚本会警告，图谱里显示为黄色虚线的「悬空链接」——这正是你该去补的洞。

图片两种写法都支持，构建时会被拷进 `out/assets/` 并改写路径（笔记本身保持原样）：

```markdown
![](attachments/diagram.png)          ← 相对本文档目录
![[zhongfeng-vs-pianfeng.png]]        ← wiki 写法，按文件名在整个 notes/ 里找（Obsidian 习惯）
```

找不到的图片会出现在构建报告的警告里。示例：`notes/aesthetics/calligraphy/zhongfeng.md` 里那张墨量示意图，就是由 `tools/make_sample_figure.py` 用 numpy+Pillow 画出来的（书法这类学科没有图基本没法写）。

### 4.3 叶子笔记的章节

`type: concept` 的笔记必须包含 **`## 我的理解`**（可用 `REQUIRED_SECTIONS` 改）。
模板默认给的结构：

| 章节 | 回答的问题 | 为什么需要 |
|---|---|---|
| 定义 | 严格定义是什么 | 防止你用模糊的日常语言自欺 |
| **我的理解** | 它到底在说什么？你在哪儿卡过？你用什么图像记住它？ | **整个知识库的心脏**，抄书的内容零价值 |
| 直觉 / 为什么 | 它为什么被发明？没它会怎样？ | 把定义挂到因果链上，才记得住 |
| 关键结论 | 能拿来就用的结论/公式 | 复习时的抓手 |
| 边界与反例 | 什么时候不成立？容易和什么混淆？ | 区分「背过」和「懂了」的分水岭 |
| 与其它概念的关系 | 上依赖、横对比、下推广 | 这些双链就是图谱的边 |
| 未解决的问题 | 你还不知道什么 | 笔记「活着」的证据，下次入口 |
| 参考 | 书的哪一章、读到哪儿 | 可追溯 |

---

## 5. 三个视图怎么用

**`out/graph.html`（主力）** —— 双击打开，单文件、数据全内嵌、不用服务器：

- 左侧是可折叠的层级树（这就是「思维导图」的阅读形态）；
- 右侧是笔记正文，公式用 KaTeX 渲染（需联网加载 CDN；断网时公式显示为原始 LaTeX，不影响阅读）；
- 顶栏切到「图谱」是全局力导向图：灰实线=层级、紫虚线=多父挂载、橙虚线=双链关联；底部图例可按顶层领域筛选；滚轮缩放、拖动平移、单击节点跳转；
- 搜索框支持标题/id/标签/别名/正文全文（按 `/` 聚焦，`Esc` 清空）；
- URL 带 `#节点id`，可以直接分享/收藏某个知识点的位置；`?view=graph` 可让它打开时直接进入图谱视图（例如 `graph.html?view=graph#math/algebra`）。

**`out/KNOWLEDGE-MAP.md`（思维导图）** —— 纯缩进大纲。三种用法：

1. 拖进 <https://markmap.js.org/repl> 立刻得到可交互思维导图；
2. Obsidian 装 Markmind / Enhancing Mindmap 插件后直接打开；
3. 任何支持 Markdown 大纲的工具（幕布、Xmind 导入、Freeplane 的 Markdown 导入）。

**`out/graph.json`（给程序）** —— `nodes` 带 frontmatter 字段与渲染好的 HTML，`edges` 带 `kind`（`tree` / `cross` / `link`）。想接 Cytoscape.js / G6 / Neo4j / Gephi 都是几十行的事。

---

## 6. 接哪个编辑器？

数据层是纯 Markdown，所以下面是**同一份笔记**的不同前台，可以随时换、也可以同时开：

| 编辑器 | 怎么接 | 适合 |
|---|---|---|
| **VS Code**（已可用） | 打开 `E:\Knowledge` 文件夹，装 Markdown All in One + Foam（可选，提供双链与图谱） | 想用脚本、想完全掌控、不想引入软件 |
| **Obsidian** | 打开文件夹作为 vault；`out/` 已 gitignore，可另设 Obsidian 忽略 | 最省事的图谱视图、插件生态最大（Dataview、Excalidraw、Markmind） |
| **思源笔记 SiYuan** | 用「导入 Markdown 文件夹」；或直接把它当独立工具另建库 | 中文体验好、自带块级引用与关系图、开源 |
| **Logseq** | 作为 graph 目录打开；它偏好 outliner（每条都是 bullet），与本库的「章节式」写法略有摩擦 | 大纲式思考、每日笔记流 |
| **Trilium / Anytype 等** | 用导入功能，注意它们的层级是「树节点」而非 frontmatter | 想要一体化客户端 |

### Obsidian + Dataview：让领域节点自动列出下级

如果你用 Obsidian，装上 Dataview 后，领域节点的「地图」章节可以不用手写：

````markdown
```dataview
LIST
FROM "notes"
WHERE contains(parents, this.id)
SORT title ASC
```
````

这样「地图」永远与真实结构同步，手写列表可以只剩「我在这里的进度」这类真需要人写的部分。

---

## 7. 分类方法论：树会强迫单选，图允许多归属

你举的例子已经暴露了核心矛盾：**数学既属于理学，又常常被当成独立大类；计算机科学既属于工程学，又长在数学上。** 这是分类法的固有问题，不是你的错。三条实战规则：

1. **顶层只放 5–9 个「领域」，不追求学科分类正确**。它的作用是把图谱分成几块颜色，方便定位，不是学术声明。想两处都挂，就写两个 `parents`。
2. **一个节点只在树里出现一次，但在图里可以有任意多条边**。所以：目录位置（`id`）代表「你平时从哪儿找到它」，其余归属用 `parents` 和双链表达。
3. **叶子笔记要「原子化」**：一条笔记只讲一个概念，标题就是概念名。写不下去说明这个节点还没到叶子（该继续拆分支），写得下去但越写越长说明该拆成两条。

命名建议：`id` 用英文小写短横线（`analytic-number-theory`，避免中文路径在同步/命令行里的麻烦），`title` 用中文。想全用中文也行，脚本不关心——只要别在 id 里用空格和 `/` 之外的特殊符号。

---

## 8. 长期维护

```powershell
git init                     # 建议立刻做：知识库的价值来自十年的增量，而不是一次整理
git add -A ; git commit -m "初始化知识库骨架"
```

- 每天的真实流程只有两步：**`new.py` 建条目 → 写「我的理解」**。图谱是副产物，不要为了画图而整理。
- 每篇笔记写完就更新 `updated`，`status` 从 `seed` 推向 `evergreen`。
- `python tools\build.py` 当体检：悬空链接、缺「我的理解」、成环、标题撞车都会报出来。
- 备份：git 远端（私有仓库）+ 定期压缩包。`out/` 不用备份（能重建）。

---

## 9. 什么时候需要「真正的」图数据库？

**大概率不需要。** 分界点大致是：

| 需求 | 现在的骨架够用吗 |
|---|---|
| 几百 ~ 几千条笔记，人读为主 | 够（Markdown + 双链 + 本视图） |
| 想按条件查询（「所有 status=seed 且属于数学的笔记」） | 够（Dataview / 自己写 20 行脚本） |
| 想算中心度、找社区、看哪些概念是枢纽 | 勉强（导出 graph.json 喂 NetworkX / Gephi 跑一次） |
| 想让程序频繁做多跳推理（A 的 A 的 B 是什么）、增量更新上万节点 | 该上图数据库（Kùzu / Neo4j 社区版） |
| 想用 LLM 自动从书籍/论文抽实体关系建成大图 | 该上 GraphRAG / Graphiti 这类管线，但**抽出来的图不是「你的理解」**，只适合当检索索引 |

我的建议：先在 Markdown 里把结构写对。结构写对了，换引擎是半天的事；结构没写对，换什么引擎都是垃圾进垃圾出。

---

## 10. 常见问题

**Q：`build.py` 报「父节点没有对应笔记」怎么办？**
在 `notes/` 下建一个空的分支笔记（`python tools\new.py <父id> --title <名字> --domain`）即可。领域节点可以很短，它的价值在于当子节点的归属点。

**Q：数学公式不渲染？**
查看器从 CDN 加载 KaTeX，需要联网。断网时公式显示为 `$...$` 原始文本——数据本身没问题，联网刷新即可。完全不想要公式渲染，可把 `tools/viewer/index.html` 末尾两个 KaTeX `<script>` 删掉再 `build.py`。

**Q：目录结构能改吗？**
能。只要 `id` 与文件路径一致，随便重命名目录（改完跑一次 `build.py`，双链会按 title/别名兜底解析）。

**Q：想加「书籍」「论文」这类节点？**
加一种 `type: book`，在 `templates/` 里加模板，在 `tools/new.py` 的 choices 里加上它，并在 `build.py` 里决定它在图谱里的颜色/形状。结构层是你的，脚本只是执行者。

**Q：为什么不全自动（让 AI 直接读我的文件生成知识库）？**
可以自动生成**结构**（分类、双链候选、缺失概念的提醒），但「我的理解」这一栏必须由人写——否则得到的是一个搜索引擎，不是知识库。AI 最合适的角色是审计者：指出哪些叶子节点还是空的、哪些概念被反复引用却还没建条目、哪些链接指向了不存在的节点。
