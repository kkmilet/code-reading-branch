# 交付物样例（以 smolagents 为例）

这份文件演示 `references/artifacts.md` 里要求的四样东西长什么样。真实产出时它们是 `READING.md` 的一部分，这里拆出来是为了看清结构。

## 一、假设表

| 我的判断 | 依据 | 如果错了会怎样 |
|---|---|---|
| `src/` 是主代码，`examples/` 只是用法示例 | 两个目录的 import 方向：examples 依赖 src，反之无 | 若 examples 里藏了核心实现，第 5 站会漏东西 |
| HTTP 不是主要入口，库调用才是 | 没有路由文件；`[project.scripts]` 只登记了两个 CLI | 若你们实际只用 CLI，第 7 站要提前到第 2 站 |
| `tests/` 覆盖了主链路行为 | 27 个测试文件、12.9k 行，体量与源码相当 | 若测试只覆盖边角，第 6 站的"验证方式"就不成立 |

## 二、能力清单

### 核心能力

#### C-01 用代码当行动 ★★★

- **一句话**：模型不返回 tool_call，而是直接写一段 Python，由框架执行
- **什么时候用**：任务需要组合多步、循环、条件判断时；比一个个调工具灵活
- **最小片段**：见下方「最小调用片段」
- **代码位置**：`CodeAgent`（src/smolagents/agents.py）
- **高频度依据**：`examples/` 下 25 个示例中 21 个用 `CodeAgent`（`grep -rl "CodeAgent" examples | wc -l`）

#### C-02 工具即类 ★★★

- **一句话**：继承 `Tool`、填四个属性、实现 `forward`，就能被 Agent 调用
- **什么时候用**：接内部系统、包装一段固定逻辑
- **最小片段**：
  ```python
  class MyTool(Tool):
      name = "my_tool"
      description = "做什么、输入什么、返回什么"
      inputs = {"query": {"type": "string", "description": "查询词"}}
      output_type = "string"
      def forward(self, query: str) -> str:
          return "结果"
  ```
- **代码位置**：`Tool`（src/smolagents/tools.py）
- **高频度依据**：`examples/` 中 19 个示例定义了自定义工具

#### C-03 模型可替换 ★★

- **一句话**：所有厂商收口成 `generate(messages) -> ChatMessage`
- **什么时候用**：换供应商、本地跑、降成本
- **代码位置**：`Model`（src/smolagents/models.py）
- **高频度依据**：README 用 7 个小节分别演示 7 种模型接入

### 常用能力（表格，不展开）

| 能力 | 一句话 | 位置 |
|---|---|---|
| 多步循环与步数上限 | 最多转几圈，防死循环 | `_run_stream`（src/smolagents/agents.py） |
| 计划步骤 | 每隔 N 步让模型先做计划 | `_run_stream`（src/smolagents/agents.py） |
| 流式输出 | 每步结果边跑边吐 | `run(stream=True)`（src/smolagents/agents.py） |
| 远程沙箱执行 | 代码不在本机跑 | `remote_executors.py`（src/smolagents/） |

## 三、踩坑（四段式）

### 坑 1：代码执行报错但没有中断

- **现象**：`agent.run()` 正常返回，但中间某一步实际上是异常；日志里只有一条 observation，看不到 traceback
- **原因**：`_step_stream` 捕获执行异常后写进 `ActionStep.error` / `observations`，循环继续，把错误当成"这一步的结果"喂给模型
- **解决**：调试时看 `result.steps` 里每一步的 `error` 字段，不要只看最终输出
- **如何避免**：把 `return_full_result=True` 作为调试默认值，先看 `steps` 再看 `output`
- **验证情况**：读代码推断，未实际运行

### 坑 2：同名文件导致阅读跳错

- **现象**：注释里写 `→ agents.py`，点过去发现是 `tests/fixtures/agents.py`，不是主实现
- **原因**：仓库里存在同名文件；短路径无法唯一定位
- **解决**：引用一律写相对仓库根的完整路径
- **如何避免**：交付前跑 `check_refs.py`，同名会直接报错
- **验证情况**：本项目实测（10 条歧义）

## 四、最小调用片段

> 照抄自 `README.md` 的 Quick Start，未运行验证。需要 `HF_TOKEN` 才能真跑。

```python
# pip install "smolagents[toolkit]"
from smolagents import CodeAgent, WebSearchTool, InferenceClientModel

model = InferenceClientModel()
agent = CodeAgent(tools=[WebSearchTool()], model=model, stream_outputs=True)

agent.run("How many seconds would it take for a leopard at full speed to run through Pont des Arts?")
```

这段代码走完整条主链：`run` 进循环，`CodeAgent` 走 `_step_stream`，`generate` 调模型，执行器跑代码，结果回到 Memory。

## 五、过期说明

- **需要重跑**：`src/smolagents/` 新增或删除模块、`Model.generate` 契约变更、主循环入口改名
- **不用重跑**：新增某个模型的适配、修 bug、加示例
- **重跑方式**：新开 `reading/<新日期>` 分支，覆盖 `READING.md`
