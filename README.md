# code-reading-branch

接手一个陌生仓库时用的技能：先把「怎么跑起来」还原出来，再排一条只覆盖主干的阅读路线，然后在一个独立分支上写中文注释，最后用脚本证明没动过业务代码。

目标不是"读懂"，是**能改**——按路线读完能定位改动点、知道按什么顺序改、知道会影响谁。

## 它做什么

| 产出 | 解决什么 |
|---|---|
| 启动链路（六步 + 每步"错了会看到什么"） | 装不上、跑不起来 |
| 阅读路线（6~8 站，其余模块只标一句"不用关注"） | 不知道从哪读、注意力被平均分配 |
| 一次请求的旅程图（含循环与异步分支） | 每个文件都懂，但串不起来 |
| `reading/<日期>` 分支上的三档注释 | 注释长在代码旁边，跳转不丢上下文 |
| 改动地图 + 能力清单 + 踩坑 | 从"读懂"到"能改" |

## 环境要求

- 支持 `SKILL.md` 的 Agent：WorkBuddy / Claude Code / Cursor / Codex / Gemini CLI
- Python 3.8+（只有三个校验脚本需要，不用脚本可以不装）

## 安装

### 1. 克隆

```bash
git clone https://github.com/kkmilet/code-reading-branch.git
```

### 2. 放进 Agent 的 skills 目录

| Agent | 目录 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/` |
| Claude Code | `~/.claude/skills/` |
| Cursor | `~/.cursor/skills/` |
| Codex | `~/.codex/skills/` |
| Gemini CLI | `~/.gemini/skills/` |

```bash
cp -r code-reading-branch/skills/code-reading-branch ~/.workbuddy/skills/
```

Windows 把 `~/.workbuddy/skills/` 换成 `%USERPROFILE%\.workbuddy\skills\`。

没有 git 也可以：下载仓库 zip，把 `skills/code-reading-branch` 解压到上面的目录。

### 3. 验证

```bash
python ~/.workbuddy/skills/code-reading-branch/scripts/lint.py \
  ~/.workbuddy/skills/code-reading-branch/examples/READING.sample.md
```

输出 `✅ READING.sample.md 结构检查通过` 就装好了。

### 插件市场（可选）

```
/plugin marketplace add kkmilet/code-reading-branch
```

### 升级

```bash
cd code-reading-branch && git pull
cp -r skills/code-reading-branch ~/.workbuddy/skills/
```

> 仓库当前是 **private**。别人 clone 或 marketplace add 之前，需要把仓库改成 public，或把对方加成 collaborator。

## 使用

给它一个仓库路径和一句意图：

> 接手了这个项目，带我看一下：~/work/shop

> 这个仓库怎么跑起来？看完给我排个阅读顺序

> 帮我把核心模块注释一遍，我想能自己改

技能会先静默扫描，然后问一个选择题（整体过一遍 / 只看某条线 / 先搞清怎么跑），再出路线图等你确认。

## 三道闸门

注释分支的价值全在"只加不改"。三个脚本把它变成可验证的事：

```bash
python skills/code-reading-branch/scripts/verify.py     <repo>   # 剥离注释后与基线逐字节比对
python skills/code-reading-branch/scripts/check_refs.py <repo>   # 路径存在、符号真实、无同名歧义
python skills/code-reading-branch/scripts/lint.py       <repo>   # 站数、标签、卡片、术语条数
```

第一道不过就不交付。实测：往文件里改一行 `False` → `True`，立刻被拦下。

## 边界

- **只读**：只新增注释行和 `READING.md`，不改业务代码、不调格式
- **不执行**：不装依赖、不启动服务、不跑测试；启动结论靠静态证据推，每条标 `【文档明示】/【代码推断】/【未知】`
- **不猜**：推不出来的标 `【未知】`；写"没有 X"之前必须给出搜索范围

## 已知限制

- 没在真实会话里验证过自动触发，需要显式提到"接手 / 带我看 / 怎么跑起来"这类词
- 只在一个开源项目（smolagents，3 万行）上跑过，且只完整注释了 1 站
- 站排得好不好需要人读一遍判断，脚本查不出"这站该不该在这"

## 结构

```
.claude-plugin/marketplace.json
skills/code-reading-branch/
├── SKILL.md              主流程 S0–S8、四条红线、11 条自检
├── references/           讲解法、路线、注释规范、启动链路、旅程图、栈配方、交付物、文风
├── scripts/              三道闸门
└── examples/             导航样例、交付物样例
```

## License

MIT
