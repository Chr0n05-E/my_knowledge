# 个人知识库

用 Markdown 记录概念和自己的理解，再把笔记之间的关系生成可浏览的知识图谱。

这个仓库既保存个人笔记，也包含新建笔记、检查结构和生成图谱的工具。可以用 Obsidian 编辑，也可以用任意文本编辑器。AI 用于按需解释概念、分析原理和澄清误解；不维护长期学习规划、每日任务或学习档案。具体协作约定见 [AGENTS.md](AGENTS.md)。

## 能做什么

- 按领域和概念组织笔记，记录定义、自己的理解、例子、反例和未解决的问题。
- 用文件夹表示层级，用双链和关系标签表示前置依赖、对比、应用、引用等联系。
- 检查缺失的父节点、悬空链接、重复标题、层级循环和缺少的必要章节。
- 生成包含目录、搜索、笔记正文和交互图谱的网页，支持层次布局和力导向布局。
- 通过 Python 图形界面新建笔记、构建图谱和打开 Obsidian。

![知识库控制台](docs/gui.png)

![知识图谱网页](docs/web_graph.png)

## 快速开始

建议使用 Python 3.11 或更新版本。图形界面需要 Python 的 `tkinter` 支持；Windows 标准 Python 安装通常自带。

```powershell
git clone https://github.com/Chr0n05-E/my_knowledge.git
cd my_knowledge
python -m pip install pyyaml
python tools/build.py
```

构建后，用浏览器打开 `out/index.html`。网页无需启动服务器；数学公式渲染需要联网加载 KaTeX。

PyYAML 用于完整读取配置和笔记的 YAML。未安装时脚本会退回简易解析器，自定义关系等复杂配置可能无法生效。

### 使用图形界面

```powershell
python tools/gui.pyw
```

Windows 下也可以使用 `pythonw tools/gui.pyw`，或在 `.pyw` 文件关联正确时直接双击。界面提供新建笔记、构建 / 体检、打开图谱网页和打开 Obsidian 等功能。

需要桌面快捷方式时运行：

```powershell
python tools/install_shortcut.py
```

### 使用 Obsidian

将仓库根目录作为 vault 打开。建议在“文件与链接 → 排除的文件”中加入 `out/`、`tools/`、`templates/` 和 `docs/`，让 Obsidian 图谱聚焦笔记。

Obsidian 不是运行构建工具的必要条件。

## 目录结构

```text
.
├─ notes/                 个人笔记，知识库的主要内容
├─ templates/             概念和领域笔记模板
├─ tools/
│  ├─ new.py              新建笔记
│  ├─ build.py            校验并生成网页、图谱数据和大纲
│  ├─ gui.pyw             图形界面
│  ├─ install_shortcut.py Windows 快捷方式安装工具
│  └─ viewer/index.html   图谱网页模板
├─ docs/                  操作指南和界面截图
├─ kb.config.yml          关系类型、校验规则、输出路径等配置
├─ AGENTS.md              AI 协作约定
└─ out/                   构建产物，已被 Git 忽略
```

`notes/` 是原始内容，`out/` 可以重新生成。不要直接修改生成的网页来保存笔记。

## 新建与编写笔记

笔记的 ID 是它相对 `notes/` 的路径，不含 `.md`。例如 `science/computer_science/data_structure/hash_map` 对应同路径下的 Markdown 文件。

```powershell
# 新建领域或分支：显式使用 --type domain
python tools/new.py math/algebra --title 代数 --type domain

# 新建概念
python tools/new.py math/algebra/group_theory --title 群论 --type concept
```

已有文件默认不会被覆盖。新建后打开笔记填写内容，再重新构建。上面的命令仅作示例，运行时会实际创建文件。

概念笔记建议包含：

- 定义：概念的严格含义。
- 我的理解：用自己的话说明它在说什么，以及曾经卡住的地方。
- 直觉 / 为什么：它解决什么问题，为什么需要它。
- 关键结论、边界与反例、与其它概念的关系。
- 未解决的问题和参考来源。

当前配置要求 `type: concept` 的笔记包含“我的理解”章节。这个检查只校验章节是否存在，不判断内容是否正确，也不代表已经掌握。

### 表达概念之间的关系

文件夹自动决定基本层级。其他关系可以在正文中写成“标签：双链”：

```markdown
## 与其它概念的关系

- 前置：[[math/algebra|代数]]
- 对比：[[另一个概念的ID|显示名称]]
- 应用于：[[某个应用的ID]]
```

也可以在 frontmatter 的 `relations` 中声明关系。标签、颜色、线型和方向在 [kb.config.yml](kb.config.yml) 中配置。双链目标需要对应实际存在的笔记，否则构建会提示悬空链接。

## 构建与检查

```powershell
python tools/build.py          # 构建并打印报告
python tools/build.py --open   # 构建后打开网页
python tools/build.py --strict # 将警告也视为失败
```

默认生成：

| 文件 | 用途 |
|---|---|
| `out/index.html` | 阅读笔记、搜索和浏览图谱 |
| `out/graph.json` | 节点、关系边和关系类型数据 |
| `out/KNOWLEDGE-MAP.md` | 可供大纲或思维导图工具使用的层级列表 |
| `out/assets/` | 笔记引用的图片副本 |

修改笔记或配置后，需要重新构建，网页才会显示最新内容。分享网页时，应一起提供 `index.html` 和它引用的 `assets/`。

## 版本管理

笔记、模板、配置、工具和文档由 Git 管理；构建产物与本机 Obsidian 配置被忽略。提交前检查改动范围，按需选择文件：

```powershell
git status
git add -- notes/某条笔记.md
git commit -m "更新概念笔记"
git push origin main
```

仓库不会自动执行学习记录同步。提交和推送按具体需求进行。

更多功能和故障排查见 [知识库操作指南](docs/操作指南.md)。
