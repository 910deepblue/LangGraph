# LangGraph 从 0 到 1 搭建指南

> 面向对象：已经会一点 Python、做过（或正在做）RAG、想搞明白 Agent 编排框架到底怎么回事的人。
> 目标：跟着做完，你手上会有一个能跑、能加分支、能循环、能中断等人确认的 Agent 项目。
> 环境：Windows + 本机已有资源（uv 0.12.12 / Anaconda / 本地 BGE 模型）。
> 配套文档：`F:\rag-from-zero\RAG从0到1搭建指南.md`（建议先看那份，本指南多处引用它）。

---

## ⚠️ 阅读前必看：本机现状核对表

**本指南的命令都基于下面这张表里的实际路径。你自己换位置的话，所有命令要跟着改。**

### 本机现状（2026-09-17 实测确认）

| 项 | 实际值 | 备注 |
| --- | --- | --- |
| 项目位置 | **`F:\langgraph-from-zero`** | 与 `F:\rag-from-zero` 同级 |
| uv | `D:\DevEnv\uv\bin\uv.exe`，版本 **0.12.12** | 比 pip 快很多，本指南统一用它 |
| uv 缓存 | `D:\DevEnv\uv\cache`（已在用户级环境变量设好） | 别让 wheel 落到 C 盘 |
| Python | **3.12.7**（uv 缓存里现成有，不额外下载） | 与 RAG 项目一致 |
| langgraph | **1.2.11** | `pip install langgraph` 自动带上 langchain-core，**不要**再单独装 langchain |
| langgraph-checkpoint-sqlite | **3.1.1** | 第 9 章持久化用 |
| langgraph-checkpoint-postgres | **3.1.2**（可选，本机未装） | 仅 §9.5「多进程 / 生产」需要，且要本地有 Postgres 服务 |
| openai | **3.14.1** | LLM 调用（OpenAI 兼容协议） |
| 已有参考项目 | `F:\rag-from-zero`（FAISS + BGE，已跑通） | 第 11 章会讲怎么迁移过来 |
| 已有 Agent 骨架 | `D:\tender-agent`（本次会话搭的，LangGraph 1.2.11） | 可作为可运行参考 |
| 磁盘余量 | C: ≈16GB / D: 充足 / E: ≈58GB / F: ≈46GB | C 盘紧张，**缓存别往 C 盘放** |

### 本指南的验证状态（2026-09-17 实测）

**全部 8 个脚本已实际跑通，退出码全为 0，stderr 全空：**

| 脚本 | 状态 | 验证内容 |
| --- | --- | --- |
| `check_env.py` | ✅ | 导入正常 + 最小图执行（41→42）+ reducer 生效（0+1+2=3） |
| `steps/s1_minimal.py` | ✅ | state 合并、节点返回增量 |
| `steps/s2_state.py` | ✅ | 无 reducer 时 3 轮只剩 1 条；有 reducer 时保留 3 条 |
| `steps/s3_branch.py` | ✅ | 4 个问题路由全部命中预期分支 |
| `steps/s4_loop.py` | ✅ | 命中即停；永远检索不到时循环 3 次后放弃 |
| `steps/s5_llm.py` | ✅ | 未配 key 时自动降级并回显 prompt 结构 |
| `steps/s6_tools.py` | ✅ | 3 个问题分别调对 3 个工具，ReAct 循环正常 |
| `steps/s7_persist.py` | ✅ | 中断生效、人工确认后继续、4 个检查点、`thread_id` 缺失报错 |

> **复现方式**：`.\.venv\Scripts\python.exe run_all.py`，结果写入 `_verify_report.txt`。
> 之所以要多这么一层脚本，是因为本机 PowerShell 捕获不到子进程输出（见第 12 章坑 11）。

### ⚠️ 版本差异提示（最容易踩的坑）

LangGraph 在 **0.2 → 1.0** 之间做了大量重构。网上大量教程还是 0.2 的写法，**照抄会报错**。本指南统一按 **1.x** 写：

| 你可能会看到的旧写法 | 1.x 正确写法 | 说明 |
| --- | --- | --- |
| `from langgraph.graph import MessageGraph` | `from langgraph.graph import MessagesState` + `StateGraph` | `MessageGraph` 已废弃 |
| `from langgraph.prebuilt import create_react_agent` | 仍然可用，但推荐 `langgraph.prebuilt.create_react_agent` 或自己搭图 | 签名有变 |
| `graph.set_entry_point("node")` | `graph.add_edge(START, "node")` | `set_entry_point` 已移除 |
| `graph.set_finish_point("node")` | `graph.add_edge("node", END)` | 同上 |
| `compile(checkpointer=...)` 不传 `thread_id` | **必须传** `thread_id` | 否则报 `ValueError` |

> **一句话教训：看到 `set_entry_point` / `set_finish_point` 的教程，直接关掉，那是 0.1~0.2 的写法。**

---

## 目录

- [第 0 章 先搞清楚 LangGraph 是什么](#第-0-章-先搞清楚-langgraph-是什么)
- [第 1 章 四个核心概念（就这四个）](#第-1-章-四个核心概念就这四个)
- [第 2 章 建项目骨架与环境](#第-2-章-建项目骨架与环境)
- [第 3 章 里程碑 1：20 行跑通最小图](#第-3-章-里程碑-120-行跑通最小图)
- [第 4 章 里程碑 2：状态进阶（reducer 与多字段设计）](#第-4-章-里程碑-2状态进阶reducer-与多字段设计)
- [第 5 章 里程碑 3：分支与条件边](#第-5-章-里程碑-3分支与条件边)
- [第 6 章 里程碑 4：循环（LangGraph 的核心价值）](#第-6-章-里程碑-4循环langgraph-的核心价值)
- [第 7 章 里程碑 5：接上大模型](#第-7-章-里程碑-5接上大模型)
- [第 8 章 里程碑 6：工具调用（从写死流程到模型自选）](#第-8-章-里程碑-6工具调用从写死流程到模型自选)
- [第 9 章 里程碑 7：持久化与人在回路](#第-9-章-里程碑-7持久化与人在回路)
- [第 10 章 可视化、流式与调试](#第-10-章-可视化流式与调试)
- [第 11 章 工程化：把你的 RAG 迁过来](#第-11-章-工程化把你的-rag-迁过来)
- [第 12 章 本机高频坑清单](#第-12-章-本机高频坑清单)
- [第 13 章 学习路线](#第-13-章-学习路线)

---

## 第 0 章 先搞清楚 LangGraph 是什么

一句话：**LangGraph = 用「图」来编排 LLM 应用的状态机框架。**

### 为什么需要它

你 RAG 指南里的链路是**线性的**：

```
问题 → 向量化 → 检索 Top-K → 拼 prompt → 大模型生成 → 完
```

这种流程一行行写下去就够了，**不需要任何框架**。你那份指南第 1 章甚至明确说「不用框架，先手写」——这个判断在纯 RAG 场景下完全正确。

但一旦出现**分支和循环**，线性代码就开始崩：

| 场景 | 线性代码怎么写 | 问题 |
| --- | --- | --- |
| 按问题类型走不同检索路径 | `if 条文查询: ... elif 语义: ...` | 还能忍 |
| 检索不理想 → 换关键词**再检一次** | 要写 `while` + 一堆状态变量 | 开始丑 |
| 多轮：查法条 → 发现要查释义 → 再查 → 综合 | 嵌套循环 | 无法维护 |
| 中途**人工审核**再继续 | 得把函数拆两半、状态存数据库、再读回来 | 噩梦 |
| 多轮对话要记住上下文 | 自己维护历史数组、控制长度 | 繁琐易错 |

**这五种场景，LangGraph 都是为它们设计的。**

### LangGraph 的核心思路

```
把每一步做成一个「节点」(node)
节点之间用「边」(edge) 连起来
整个流程共享一份「状态」(state)
有分支就画条件边，要循环就把边连回去
```

就这三句话，没有更多了。

### 它和 LangChain 的关系（最容易搞混）

| | LangChain | LangGraph |
| --- | --- | --- |
| 抽象单位 | Chain（链） | Graph（图） |
| 流程形态 | 基本线性（DAG，不能有环） | **支持环**，也就是循环 |
| 状态 | 在各组件间隐式传递，不透明 | **显式**的 State 对象，你能随时查看 |
| 中断恢复 | 不支持 | 原生支持（checkpointer） |
| 适合 | 简单问答、单轮 RAG、固定流水线 | Agent、多步推理、人在回路 |
| 调试难度 | 黑盒，出错难定位 | 状态可见，每步可打点 |

> **一句话记住：LangChain 是流水线，LangGraph 是流程图。需要循环和分支就用后者。**

**为什么有 LangChain 还要造 LangGraph**：因为 Agent 的本质就是循环——「思考 → 调工具 → 看结果 → 再思考」。LangChain 的 Chain 是 DAG，**结构上就不允许有环**，硬做出来只能是把循环塞进一个组件内部，那就又变成黑盒了。

### 它和另外几条路线的对比

| 方案 | 做法 | 适合 | 代价 |
| --- | --- | --- | --- |
| 纯 Python 手写 | `while` + `if` + 函数调用 | 流程固定、步骤少（≤5 步） | 状态管理要自己写，复杂了就无法维护 |
| LangChain Chain | 把组件串成链 | 单轮 RAG | 不能有循环 |
| **LangGraph** | 图 + 显式状态 | **Agent、多步、人在回路** | 要理解状态和 reducer |
| 各家 Agent SDK | 厂商封装好的 Agent | 快速搭个能用的 | 定制受限，换厂商要重写 |

> **注意：不要因为"框架高级"就上 LangGraph。** 你那份 RAG 指南里"先手写一遍"的忠告在这里同样成立——
> 如果流程就是线性的四步，手写 50 行比 LangGraph 更清楚。

---

## 第 1 章 四个核心概念（就这四个）

把这四个吃透，LangGraph 就懂了 80%。剩下的都是它们的组合。

| 概念 | 是什么 | 类比 | 代码长什么样 |
| --- | --- | --- | --- |
| **State** | 在所有节点间流转的数据 | 传送带上的托盘 | `class State(TypedDict): ...` |
| **Node** | 一个函数，接收 state，返回**要更新的字段** | 工位 | `def my_node(state) -> dict: ...` |
| **Edge** | 节点之间的固定连接 | 传送带 | `builder.add_edge("a", "b")` |
| **Conditional Edge** | 一个函数，动态决定下一个节点 | 岔路口 | `builder.add_conditional_edges("a", decide)` |

### 三个必须一开始就建立的直觉

**直觉 1：节点不修改 state，而是返回「增量」。**

这是最容易搞错的地方。看对比：

```python
# ❌ 错误：原地修改，没有返回值
def bad_node(state):
    state["answer"] = "hello"      # LangGraph 看不到这个修改
    # 没有 return

# ✅ 正确：返回一个字典，LangGraph 负责合并
def good_node(state):
    return {"answer": "hello"}
```



LangGraph 拿到 `{"answer": "hello"}` 后，会把它**合并**进原 state。原 state 里其他字段（比如 `question`）保持不变。

**直觉 2：`START` 和 `END` 是虚拟节点。**

它们不是你要实现的东西，只是标记入口和出口：

```python
from langgraph.graph import StateGraph, START, END
```

-  `add_edge(START, "first_node")` = 图从 `first_node` 开始
-  `add_edge("last_node", END)` = 走到 `last_node` 就结束

**直觉 3：图必须先 `compile()` 才能跑。**

```python
builder = StateGraph(State)   # 建造者，用来描述图
builder.add_node(...)
builder.add_edge(...)

graph = builder.compile()     # 编译成可执行的图
graph.invoke({...})           # 跑
```

**为什么分两步**：`compile()` 会做结构校验（检查有没有孤立节点、能不能从 START 走到 END），并生成执行计划。分开的好处是 `builder` 可以复用、可以在编译时挂 checkpointer。

### 术语对照表（看官方文档时用）

| 中文 | 英文 | 含义 |
| --- | --- | --- |
| 节点 | node | 一个处理步骤 |
| 边 | edge | 节点间的连接 |
| 条件边 | conditional edge | 动态选择下一个节点 |
| 状态 | state | 流转的数据 |
| 归并函数 | reducer | 决定新值怎么和旧值合并 |
| 检查点 | checkpoint | 某一步的状态快照，用于恢复 |
| 线程 | thread | 一个独立会话（用 thread_id 区分） |
| 超级步 | superstep | 一轮并行执行（同一轮内多个节点同时跑） |

---

## 第 2 章 建项目骨架与环境

### 2.1 目录结构（先建好，别乱跑）

```text
langgraph-from-zero/
├─ data/                       # 练习用的输入数据（可选）
├─ storage/                    # 持久化产物（checkpoint、索引）
│   └─ checkpoints.db          # SQLite 检查点（第 9 章用）
├─ src/
│   ├─ __init__.py
│   ├─ config.py               # 所有配置集中在这
│   ├─ state.py                # ★ State 定义（所有图的共享状态）
│   ├─ llm.py                  # 大模型客户端封装
│   └─ tools.py                # ★ 工具定义（给模型用的）
├─ steps/                      # ★ 每个里程碑一个可独立运行的脚本
│   ├─ s1_minimal.py           # 第 3 章：最小图
│   ├─ s2_state.py             # 第 4 章：reducer
│   ├─ s3_branch.py            # 第 5 章：分支
│   ├─ s4_loop.py              # 第 6 章：循环
│   ├─ s5_llm.py               # 第 7 章：接大模型
│   ├─ s6_tools.py             # 第 8 章：工具调用
│   └─ s7_persist.py           # 第 9 章：持久化
├─ app.py                      # 最终的完整 Agent 入口
├─ check_env.py                # 环境自检
├─ requirements.txt
└─ .env                        # 密钥（不要提交到 git）
```

**为什么按 `steps/` 一个一个脚本放**：这是本指南和大多数教程最大的不同。大多数教程一上来就给你一个完整 Agent，你跑通了也不知道哪步在干什么。**每个里程碑一个独立脚本，你可以逐个跑、逐个改、逐个验证。** 最后 `app.py` 是把它们拼起来的结果。

### 2.2 建目录

在 PowerShell 里：

```powershell
mkdir F:\langgraph-from-zero
cd F:\langgraph-from-zero
mkdir data, storage, src, steps
ni src\__init__.py -ItemType File
```

> ⚠️ **注意**：目录名和位置随你放，但一旦定了，后面所有命令的 `cd` 都要跟着改。
> 本指南统一按 `F:\langgraph-from-zero` 写。

### 2.3 虚拟环境

你有 uv，用它最快。**先把 uv 的缓存目录指到 D 盘**（虽然本机已经设了用户级环境变量，但显式设一遍更保险）：

```powershell
cd F:\langgraph-from-zero

# 保险起见显式设一遍（只对当前窗口生效）
$env:UV_CACHE_DIR          = "D:\DevEnv\uv\cache"
$env:UV_PYTHON_INSTALL_DIR = "D:\DevEnv\uv\python"
$env:UV_TOOL_DIR           = "D:\DevEnv\uv\tools"

D:\DevEnv\uv\bin\uv.exe venv --python 3.12
```

**不需要激活**，直接用 `.\.venv\Scripts\python.exe` 更省事，避免 PowerShell 执行策略的麻烦。

> 如果你确实想激活：
> ```powershell
> Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
> .\.venv\Scripts\Activate.ps1
> ```
> 激活成功后命令行前面会出现 `(langgraph-from-zero)`。

### 2.4 依赖清单

`requirements.txt`：

```text
# --- 核心：LangGraph（会自动带上 langchain-core）---
langgraph>=1.0
# --- LLM 调用：用 OpenAI 兼容协议，一家 SDK 通吃所有厂商 ---
openai
# --- 配置与密钥 ---
python-dotenv
# --- 第 9 章持久化用 ---
langgraph-checkpoint-sqlite
# --- §9.5：要上 PostgresSaver（多进程 / 生产）时再装，需要本地有 Postgres 服务 ---
# langgraph-checkpoint-postgres
# psycopg[binary,pool]
# --- 第 10 章可视化会用到（可选）---
# grandalf

# --- 以下为第 11 章「把 RAG 迁过来」时才需要，前 10 章可以先不装 ---
# sentence-transformers>=3.0
# faiss-cpu
# pymupdf
```

### 安装依赖

> 🔴 **关键：一条命令装完，不要分两次装。**
>
> 这是从 RAG 指南「坑 0：torch 缝合怪」血泪教训里来的通用规则：
> **同一个包，绝对不要用两个不同的索引源分两次装。**

```powershell
cd F:\langgraph-from-zero
D:\DevEnv\uv\bin\uv.exe pip install -r requirements.txt `
  -i https://pypi.tuna.tsinghua.edu.cn/simple `
  -p "F:\langgraph-from-zero\.venv\Scripts\python.exe"
```

> ⚠️ **注意：本指南这一批依赖不含 torch，所以很快（几十秒）。**
> 如果你取消注释了 `sentence-transformers` 那两行，就会带上 torch 下载——
> **那就要按 RAG 指南 §2.3 加 `-c constraints.txt` 锁版本，并且准备好 70 分钟下载时间。**
> **建议：先把前 10 章学完（不装 torch），第 11 章再补。**

✅ **本机实测的完成标志**：

```text
Resolved 30 packages in 5s
Installed 30 packages in 4s
 + langgraph==1.2.11
 + langchain-core==1.6.3
 ...
EXIT: 0
```

**`Installed` 列表里出现 `langgraph==1.2.11`，没有第二个 langchain 大包**，才算干净。

### 2.5 环境自检

`check_env.py`：

```python
"""环境自检：确认 LangGraph 能正常导入、版本正确。

为什么必须有这个脚本：`uv pip install` 输出 `Checked N packages` 不代表包能用，
只有 import 成功才算数（RAG 指南坑 0 的教训）。
"""

import sys

print("Python:", sys.version.split()[0])

# --- 核心导入：这三行能跑通，环境就没问题 ---
try:
    from langgraph.graph import StateGraph, START, END
    print("langgraph.graph 导入成功")
except Exception as e:
    print(f"❌ langgraph 导入失败: {e}")
    sys.exit(1)

try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    print("langchain_core.messages 导入成功")
except Exception as e:
    print(f"❌ langchain-core 导入失败: {e}")
    sys.exit(1)

try:
    from langgraph.checkpoint.memory import MemorySaver
    print("langgraph.checkpoint.memory 导入成功")
except Exception as e:
    print(f"❌ checkpointer 导入失败: {e}")
    sys.exit(1)

# --- 版本信息（langgraph 1.x 的版本号不在顶层，用 importlib 拿）---
from importlib.metadata import version, PackageNotFoundError

for pkg in ["langgraph", "langchain-core", "openai", "python-dotenv"]:
    try:
        print(f"{pkg}: {version(pkg)}")
    except PackageNotFoundError:
        print(f"{pkg}: 未安装")

# --- 最小可运行验证：真跑一个两步图，确认不是"装得上但用不了" ---
from typing import TypedDict


class Smoke(TypedDict):
    n: int


def inc(state: Smoke) -> dict:
    return {"n": state["n"] + 1}


b = StateGraph(Smoke)
b.add_node("inc", inc)
b.add_edge(START, "inc")
b.add_edge("inc", END)
g = b.compile()

out = g.invoke({"n": 41})
assert out["n"] == 42, f"图执行结果不对: {out}"
print(f"\n✅ 最小图执行成功: 41 -> {out['n']}")
```

跑：

```powershell
cd F:\langgraph-from-zero
.\.venv\Scripts\python.exe check_env.py
```

> ℹ️ **本机实测的"正确输出"长这样，照这个比对：**
> ```text
> Python: 3.12.7
> langgraph.graph 导入成功
> langchain_core.messages 导入成功
> langgraph.checkpoint.memory 导入成功
> langgraph: 1.2.11
> langchain-core: 1.6.3
> openai: 2.x.x
> python-dotenv: 1.2.x
>
> ✅ 最小图执行成功: 41 -> 42
> ```

**最后一行是 `✅ 最小图执行成功`，就可以进第 3 章了。任何一行 ❌，先回去解决，不要往前走。**

> ⚠️ **【新增】两条注意**：
> 1. **不要单独 `pip install langchain`**。那个大包会带来一堆你不需要的依赖，还可能和 `langchain-core` 版本冲突。`langgraph` 已经自带所需的 core。
> 2. **`langgraph.__version__` 在 1.x 里可能不存在**。用 `importlib.metadata.version("langgraph")` 更可靠（自检脚本里就是这么写的）。

---

## 第 3 章 里程碑 1：20 行跑通最小图

**这一步的目标不是做功能，是让你亲眼看到 state 到底怎么在节点之间流动。** 不接模型、不接数据库，纯内存。

`steps/s1_minimal.py`：

```python
"""里程碑 1：最小可运行图。

本章你会看到：
  1. State 怎么定义
  2. 节点怎么接收 state、怎么返回值
  3. 边怎么连
  4. 最终结果从哪拿

运行：
    .\.venv\Scripts\python.exe steps\s1_minimal.py
"""

from typing import TypedDict

from langgraph.graph import StateGraph, START, END


# ============================================================
# 1) 定义 State —— 这就是那份在所有节点间流转的"托盘"
# ============================================================
class State(TypedDict):
    """图的共享状态。

    TypedDict 只是类型提示，LangGraph 运行时不强校验。
    写清楚类型是为了让 IDE 能补全、也让你自己看得懂。
    """
    text: str        # 输入：用户给的原始文本
    upper: str       # 中间产物：转大写后的文本
    length: int      # 最终产物：长度


# ============================================================
# 2) 定义节点 —— 每个节点是一个函数：接收 state，返回"要更新的字段"
# ============================================================
def to_upper(state: State) -> dict:
    """把 text 转成大写，写入 upper 字段。

    注意：这里只返回 {"upper": ...}，不返回完整的 state。
    LangGraph 会把它合并进原 state，text 字段保持不变。
    """
    print(f"  [to_upper] 收到 text={state['text']!r}")
    return {"upper": state["text"].upper()}


def count_len(state: State) -> dict:
    """读取上一步产出的 upper，算长度写入 length。"""
    # 这里能直接读到 upper，说明上一步的返回值已经合并进 state 了
    print(f"  [count_len] 收到 upper={state['upper']!r}")
    return {"length": len(state["upper"])}


# ============================================================
# 3) 建图 —— 先描述，再编译
# ============================================================
builder = StateGraph(State)

# add_node(节点名, 处理函数)
# 节点名是字符串，后面连边时用它引用；处理函数是上面定义的函数
builder.add_node("to_upper", to_upper)
builder.add_node("count_len", count_len)

# add_edge(起点, 终点)
# START 和 END 是虚拟节点，从 langgraph.graph 导入，不需要自己实现
builder.add_edge(START, "to_upper")        # 入口 -> to_upper
builder.add_edge("to_upper", "count_len")  # to_upper -> count_len
builder.add_edge("count_len", END)         # count_len -> 出口

# compile() 把描述编译成可执行的图，会做结构校验
graph = builder.compile()


# ============================================================
# 4) 跑
# ============================================================
if __name__ == "__main__":
    print("开始执行图：")
    result = graph.invoke({"text": "hello langgraph"})

    # invoke 返回的是最终完整 state，是个 dict
    print(f"\n最终 state: {result}")
    print(f"取单个字段: result['length'] = {result['length']}")
```

跑：

```powershell
.\.venv\Scripts\python.exe steps\s1_minimal.py
```

**预期输出**：

```text
开始执行图：
  [to_upper] 收到 text='hello langgraph'
  [count_len] 收到 upper='HELLO LANGGRAPH'

最终 state: {'text': 'hello langgraph', 'upper': 'HELLO LANGGRAPH', 'length': 15}
取单个字段: result['length'] = 15
```

### 你必须从这一步带走的四个认知

**1. 节点返回值是「增量」，不是完整 state。**

`to_upper` 只返回了 `{"upper": ...}`，但最终 result 里 `text` 还在。这说明 LangGraph 做了**合并**，不是替换。

这个设计有个直接好处：**节点不需要知道 state 里有什么其他字段**，只关心自己负责的那部分。这让节点可以独立开发、独立测试。

**2. `graph.invoke()` 返回的是最终完整 state，不是某个返回值。**

你想要哪个字段就 `result["length"]`。这一点和普通函数调用不同——普通函数返回什么就拿到什么，这里永远拿到整份 state。

**3. `START` 和 `END` 是虚拟节点，不用你定义。**

它们是标记，不是逻辑。`add_edge(START, "to_upper")` 的语义是"图从这里开始"。

**4. 图的执行顺序由「边」决定，不由代码顺序决定。**

我把 `to_upper` 写在前面只是习惯，真正决定顺序的是 `add_edge`。如果你把边连成 `START → count_len → to_upper → END`，它会按那个顺序跑（然后 `count_len` 会因为读不到 `upper` 而 `KeyError`）。

> ⚠️ **常见错误：节点返回了不存在的字段**
>
> ```python
> def bad(state):
>     return {"uppper": "typo"}   # 拼错了
> ```
> LangGraph 默认**不报错**，会把这个字段塞进 state。你后面 `state["upper"]` 就 `KeyError` 了，还找不到原因。
> **TypedDict 是提示不是校验。** 想要强校验，自己在节点里断言。

> ⚠️ **常见错误：忘了连 END**
>
> 如果忘了 `add_edge("count_len", END)`，编译时不一定报错，但 `invoke` 可能挂住或行为异常。
> **规矩：每个分支的终点都要连到 END。**

---

## 第 4 章 里程碑 2：状态进阶（reducer 与多字段设计）

第 3 章的状态是简单的"覆盖"语义：新值替换旧值。**但循环场景下，覆盖会毁掉一切。** 这一章讲清楚 reducer。

### 4.1 默认行为：覆盖

先做个实验，`steps/s2_state.py` 的前半部分：

```python
"""里程碑 2：State 的归并策略（reducer）。

本章你会看到：
  1. 默认是"覆盖"，循环里会丢数据
  2. 用 Annotated + reducer 改成"累加"
  3. 同一个 State 里可以混用两种策略
  4. 消息历史为什么必须用 add_messages

运行：
    .\.venv\Scripts\python.exe steps\s2_state.py
"""

from operator import add
from typing import Annotated, TypedDict

from langgraph.graph import StateGraph, START, END


# ============================================================
# 实验 A：默认覆盖 —— 循环里只有最后一个值留下来
# ============================================================
class OverwriteState(TypedDict):
    n: int
    log: list[str]          # ← 没有 reducer，默认覆盖


def step_overwrite(state: OverwriteState) -> dict:
    n = state["n"] + 1
    # ❌ 想累积，但因为没有 reducer，上一轮的内容会被整个替换掉
    return {"n": n, "log": [f"第 {n} 轮"]}


def keep_going_overwrite(state: OverwriteState) -> str:
    return "loop" if state["n"] < 3 else "done"


b1 = StateGraph(OverwriteState)
b1.add_node("loop", step_overwrite)
b1.add_node("done", lambda s: {})       # 空节点，只用来收尾
b1.add_edge(START, "loop")
b1.add_conditional_edges("loop", keep_going_overwrite, {"loop": "loop", "done": "done"})
b1.add_edge("done", END)
g1 = b1.compile()

print("=" * 60)
print("实验 A：没有 reducer（默认覆盖）")
print("=" * 60)
r1 = g1.invoke({"n": 0, "log": []})
print(f"跑了 3 轮，log 里只剩: {r1['log']}")
print(f"→ 预期只有 1 条，实际 {len(r1['log'])} 条。前两轮的记录被冲掉了！")
```

**预期输出**：

```text
跑了 3 轮，log 里只剩: ['第 3 轮']
→ 预期只有 1 条，实际 1 条。前两轮的记录被冲掉了！
```

### 4.2 解法：`Annotated` + reducer

```python
# ============================================================
# 实验 B：加 reducer —— 累积而不是覆盖
# ============================================================

def append(left: list[str], right: list[str]) -> list[str]:
    """自定义 reducer：把新旧值拼起来。

    约定：
      - left  = state 里的旧值
      - right = 节点返回的新值
      - 返回值会被写回 state

    必须处理 None：如果某个节点没更新这个字段，
    LangGraph 在首次调用时可能传入 None（取决于是否给了初始值）。
    """
    return (left or []) + (right or [])


class AccumulateState(TypedDict):
    n: int
    # Annotated[类型, 归并函数]
    # 语义：这个字段被更新时，不覆盖，而是调用 append(旧值, 新值)
    log: Annotated[list[str], append]


def step_accumulate(state: AccumulateState) -> dict:
    n = state["n"] + 1
    return {"n": n, "log": [f"第 {n} 轮"]}     # 现在这样写就能累积了


def keep_going_accumulate(state: AccumulateState) -> str:
    return "loop" if state["n"] < 3 else "done"


b2 = StateGraph(AccumulateState)
b2.add_node("loop", step_accumulate)
b2.add_node("done", lambda s: {})
b2.add_edge(START, "loop")
b2.add_conditional_edges("loop", keep_going_accumulate, {"loop": "loop", "done": "done"})
b2.add_edge("done", END)
g2 = b2.compile()

print("\n" + "=" * 60)
print("实验 B：有 reducer（累加）")
print("=" * 60)
r2 = g2.invoke({"n": 0, "log": []})
print(f"跑了 3 轮，log 里有: {r2['log']}")
print(f"→ 预期 3 条，实际 {len(r2['log'])} 条。每轮都记下来了。")
```

**预期输出**：

```text
跑了 3 轮，log 里有: ['第 1 轮', '第 2 轮', '第 3 轮']
→ 预期 3 条，实际 3 条。每轮都记下来了。
```

### 4.3 内置 reducer：`operator.add` 和 `add_messages`

**大多数情况下你不需要自己写 reducer**，官方提供了现成的：

```python
# --- 方案一：operator.add ---
# 对 list 就是拼接，对 int 就是相加，对 str 就是相接
from operator import add
from typing import Annotated, TypedDict


class State(TypedDict):
    items: Annotated[list[str], add]     # list 拼接
    total: Annotated[int, add]           # 数字累加
```

> ⚠️ **注意 `operator.add` 对 list 是拼接，不是去重。**
> 如果同一段内容可能被加两次，你会得到重复项。需要去重就自己写 reducer。

**方案二：`add_messages`（消息历史专用，最重要）**

```python
from langchain_core.messages import AnyMessage
from langgraph.graph import MessagesState


# 官方预置的 State，专门用于对话
class MessagesState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
```

`add_messages` 比 `operator.add` 多做了三件事：

| 行为 | 说明 |
| --- | --- |
| **按 id 去重** | 同一个 id 的消息会被**替换**而不是追加（用于"重新生成"、"编辑消息"） |
| **自动转格式** | 传 `("user", "你好")` 这种元组，会自动转成 `HumanMessage` |
| **支持删除** | 传 `RemoveMessage(id=...)` 可以删掉某条历史 |

**为什么消息历史必须用它**：多轮对话里你要更新一条已有的消息（比如用户点了"重新生成"），用 `operator.add` 会变成两条重复消息；`add_messages` 会正确地替换。

### 4.4 一个 State 里混用两种策略（实战写法）

真实项目里，有的字段要覆盖，有的要累积：

```python
# ============================================================
# 实验 C：混用 —— 这是真实 Agent 的 State 长相
# ============================================================

class AgentState(TypedDict):
    # --- 每次覆盖：当前问题、当前答案 ---
    question: str                              # 只关心最新的一次提问
    answer: str                                # 只关心最新的一版答案

    # --- 每次累积：历史记录、检索结果、引用来源 ---
    messages: Annotated[list, add_messages]    # 对话历史，必须累积
    found: Annotated[list[str], add]           # 检索到的片段，每轮都要留
    sources: Annotated[list[str], add]         # 引用来源，用于溯源
```

**怎么判断该用哪种**：

| 字段的性质 | 用什么 | 例子 |
| --- | --- | --- |
| 只关心最新值 | 默认（覆盖） | 当前问题、当前答案、当前意图、计数器 |
| 要保留全过程 | `Annotated[..., add]` | 检索结果、日志、引用来源 |
| 是对话消息 | `Annotated[..., add_messages]` | messages |

> **一句话判断法：这个字段在循环里被更新两次，第一次的值还有用吗？有用 → 加 reducer；没用 → 保持默认。**

### 4.5 多个 reducer 同时触发时的并行语义

LangGraph 有个重要特性：**同一轮超级步（superstep）里，多个节点可能并行执行。**

```python
# 如果同一轮里 nodeA 和 nodeB 都往同一个带 reducer 的字段写入，
# LangGraph 会依次调用 reducer 合并：
#   result = reducer(reducer(旧值, A的更新), B的更新)
```

**这在没有 reducer 时会直接报错**：

```python
class State(TypedDict):
    value: int          # 无 reducer


# 如果 nodeA 和 nodeB 同一轮都返回 {"value": ...}
# → InvalidUpdateError: At key 'value': Can receive only one value per step.
#   Use an Annotated key to handle multiple values.
```

**看到这个报错，就是这里的问题**——给它加个 reducer（比如 `Annotated[int, add]`）。

### 你必须从这一步带走的三个认知

1. **默认是覆盖，循环里会丢数据。** 这是新手最高频的坑，且症状隐蔽（不报错，只是数据少了）。
2. **`Annotated[类型, reducer]` 是 LangGraph 最核心的语法糖**。理解它就理解了 LangGraph 一半。
3. **`add_messages` 是消息历史的标准答案**，别用 `operator.add` 代替——会丢失去重和替换能力。

---

## 第 5 章 里程碑 3：分支与条件边

现在让图根据输入走不同的路。这是 LangGraph 从"线性流水线"变成"流程图"的第一步。

### 5.1 核心 API：`add_conditional_edges`

```python
builder.add_conditional_edges(
    "起点节点名",           # 从哪个节点出发
    routing_function,      # 路由函数：接收 state，返回下一个节点名
    {                      # （可选）路径映射字典
        "返回值A": "实际节点名A",
        "返回值B": "实际节点名B",
    },
)
```

**路由函数的契约**：

```python
def routing_function(state: State):
    # 只看 state，不做副作用（不要在这里改数据、不要调 API）
    return "某个节点名"
```

> ⚠️ **路由函数一定要是「纯函数」**。
> 它可能在编译期被调用做静态分析，也可能在运行时被调用。如果里面改了 state 或发了请求，
> 行为会不可预测。**路由函数只做判断，不做事情。**

### 5.2 完整示例：按问题类型分支

`steps/s3_branch.py`：

```python
"""里程碑 3：条件边（分支）。

本章你会看到：
  1. 怎么从 START 直接分叉（写法 A，推荐）
  2. 怎么用一个"路由节点"做中间层（写法 B）
  3. 三种条件边的用法：字典映射 / 直接返回 / 多返回值并行

运行：
    .\.venv\Scripts\python.exe steps\s3_branch.py
"""

import re
from typing import Literal, TypedDict

from langgraph.graph import StateGraph, START, END


class State(TypedDict):
    question: str
    intent: str        # 路由结果（记录下来便于调试）
    answer: str


# ============================================================
# 路由函数：接收 state，返回下一个节点名
# ============================================================
def classify(state: State) -> Literal["law_lookup", "knowledge_qa", "chitchat"]:
    """判断问题意图。

    返回类型用 Literal 声明有三个好处：
      1. IDE 能提示有哪些分支，写错就报
      2. LangGraph 画图时能正确识别分支（get_graph() 用得上）
      3. 你自己看代码时一目了然

    ⚠️ 重要：路由函数只做判断，不要在这里改 state 或调 API。
    """
    q = state["question"]

    # 1) 关系型问题优先判定
    #    必须在条文编号之前：像「第三十四条引用了哪些条款」这种问题
    #    同时命中条文号和关系词，但真正想问的是关系，不是条文原文。
    if any(w in q for w in ["引用", "关联", "相关条款", "有哪些关系"]):
        return "law_lookup"

    # 2) 出现条文编号 → 精确查询
    if re.search(r"第\s*[零一二三四五六七八九十百千0-9]+\s*条", q):
        return "law_lookup"

    # 3) 短句 + 问候词 → 闲聊
    if len(q) <= 8 and any(w in q for w in ["你好", "hi", "hello", "在吗"]):
        return "chitchat"

    # 4) 兜底：理解型问题走语义检索
    return "knowledge_qa"


# ============================================================
# 三个分支的处理节点
# ============================================================
def handle_law(state: State) -> dict:
    return {
        "intent": "law_lookup",
        "answer": f"[条文查询] 正在查《招标投标法实施条例》中的相关条文：{state['question']}",
    }


def handle_qa(state: State) -> dict:
    return {
        "intent": "knowledge_qa",
        "answer": f"[语义检索] 正在进行向量检索并生成回答：{state['question']}",
    }


def handle_chat(state: State) -> dict:
    return {
        "intent": "chitchat",
        "answer": "你好，我是招标合规助手。可以问我法规条文、合规判断或条款关系。",
    }


# ============================================================
# 写法 A（推荐）：直接从 START 条件分叉
# ============================================================
def build_graph_a() -> StateGraph:
    """最简洁的写法：不需要中间路由节点。"""
    b = StateGraph(State)
    b.add_node("law_lookup", handle_law)
    b.add_node("knowledge_qa", handle_qa)
    b.add_node("chitchat", handle_chat)

    # 第一个参数传 START，直接从入口分叉
    b.add_conditional_edges(
        START,
        classify,
        {
            # 左边 = classify 的返回值，右边 = 实际节点名
            "law_lookup": "law_lookup",
            "knowledge_qa": "knowledge_qa",
            "chitchat": "chitchat",
        },
    )

    # 每个分支都要连到 END
    b.add_edge("law_lookup", END)
    b.add_edge("knowledge_qa", END)
    b.add_edge("chitchat", END)
    return b


# ============================================================
# 写法 B：先过一个"路由节点"，再分叉
# ============================================================
def build_graph_b() -> StateGraph:
    """当你需要在分叉前做点事（记录日志、写 intent）时用这种。

    注意：这个"路由节点"必须真的存在，不能只在 add_edge 里引用它。
    这是新手最容易犯的错：写了 add_edge(START, "router") 但没 add_node("router", ...)，
    运行报 ValueError: 'router' is not a valid node
    """
    b = StateGraph(State)
    b.add_node("router", lambda state: state)   # 原样透传，但可以做点别的
    b.add_node("law_lookup", handle_law)
    b.add_node("knowledge_qa", handle_qa)
    b.add_node("chitchat", handle_chat)

    b.add_edge(START, "router")
    b.add_conditional_edges("router", classify, {
        "law_lookup": "law_lookup",
        "knowledge_qa": "knowledge_qa",
        "chitchat": "chitchat",
    })
    b.add_edge("law_lookup", END)
    b.add_edge("knowledge_qa", END)
    b.add_edge("chitchat", END)
    return b


if __name__ == "__main__":
    graph = build_graph_a().compile()

    test_questions = [
        "第三十四条怎么规定的",
        "第三十四条引用了哪些条款",
        "投标保证金应该注意什么",
        "你好",
    ]

    print("=" * 60)
    print("写法 A：直接从 START 分叉")
    print("=" * 60)
    for q in test_questions:
        r = graph.invoke({"question": q, "intent": "", "answer": ""})
        print(f"\n问题: {q}")
        print(f"意图: {r['intent']}")
        print(f"回答: {r['answer']}")

    # 看看图结构（Mermaid 文本，可以贴到 mermaid.live 看）
    print("\n" + "=" * 60)
    print("图结构（Mermaid）")
    print("=" * 60)
    print(graph.get_graph().draw_mermaid())
```

跑：

```powershell
.\.venv\Scripts\python.exe steps\s3_branch.py
```

> ⚠️ **常见错误：`add_edge(START, "router")` 但没定义 router 节点**
>
> ```python
> builder.add_edge(START, "router")     # ❌ router 不存在
> ```
> 报错：
> ```text
> ValueError: 'router' is not a valid node
> ```
> **两种修法**：要么改用写法 A（直接在 START 上条件分叉），要么真的 `add_node("router", ...)`。

### 5.3 条件边的三种进阶用法

**用法一：省略映射字典**

如果路由函数的返回值**直接就是节点名**，映射字典可以省：

```python
b.add_conditional_edges(START, classify)
# 等价于
b.add_conditional_edges(START, classify, {
    "law_lookup": "law_lookup",
    "knowledge_qa": "knowledge_qa",
    "chitchat": "chitchat",
})
```

**什么时候该显式写**：节点名以后可能改。映射字典把"判断逻辑"和"节点命名"解耦了。**我建议显式写。**

**用法二：返回列表 → 多个分支并行执行**

路由函数可以返回**一个列表**，LangGraph 会让这些节点**并行跑**：

```python
def fan_out(state: State) -> list[str]:
    """同时走三条路（比如同时查法条、查向量库、查图谱）"""
    return ["search_law", "search_vector", "search_graph"]


b.add_conditional_edges("start", fan_out, ["search_law", "search_vector", "search_graph"])
```

**注意**：这些节点必须各自把结果写进**不同的字段**，或者字段带 reducer。否则会触发第 4.5 章那个 `InvalidUpdateError`。

并行执行完，它们的下游节点会等**全部**完成才执行——这就是"汇合"。

**用法三：`Send` API —— 动态创建节点实例（进阶）**

当你要对**一个列表里的每一项**都跑一遍同一个节点时用（比如"对检索到的 10 个片段各做一次摘要"）：

```python
from langgraph.types import Send


def map_over_docs(state: State) -> list[Send]:
    """为每个文档创建一个 summarize 节点实例。"""
    return [Send("summarize", {"doc": d}) for d in state["docs"]]


b.add_conditional_edges("split", map_over_docs, ["summarize"])
b.add_edge("summarize", "reduce")     # 所有实例跑完后汇合到 reduce
```

这个用法在官方文档里叫 **map-reduce 模式**。前 10 章用不到，知道有这么个东西就行。

### 你必须从这一步带走的三个认知

1. **路由函数是纯函数**：只判断，不做事情。改 state 要放到节点里。
2. **`Literal` 声明返回值不是必须的，但强烈建议**——它让分支可见、可校验、可画图。
3. **每个分支都要能走到 END**。漏连的话图可能挂住或行为异常。

---

## 第 6 章 里程碑 4：循环（LangGraph 的核心价值）

**这一章是 LangGraph 存在的最主要理由。** 你的 Agent 里几乎全是循环：检索 → 判断够不够 → 不够再检索。

### 6.1 循环怎么画

**没有特殊语法。** 循环就是**在条件边的映射里把节点连回上游**：

```python
b.add_conditional_edges("retrieve", should_continue, {
    "retrieve": "retrieve",      # ← 连回自己，这就是循环
    "generate": "generate",
})
```

对比第 5 章的分支——分支是"往前走不回头"，循环是多了一个"往回指"的箭头。

### 6.2 完整示例：检索-判断-再检索

`steps/s4_loop.py`：

```python
"""里程碑 4：循环（LangGraph 的核心价值）。

本章你会看到：
  1. 循环怎么写（把条件边连回自己）
  2. 为什么循环里必须用 reducer
  3. 怎么防死循环（两种方式 + 推荐做法）
  4. 循环的实际价值：Agent 的"思考-行动-观察"

运行：
    .\.venv\Scripts\python.exe steps\s4_loop.py
"""

from operator import add
from typing import Annotated, Literal, TypedDict

from langgraph.graph import StateGraph, START, END


# ============================================================
# 假的"知识库"：用来模拟"第一次检索不到，换个词就检索到了"
# ============================================================
KB = {
    "保证金": ["第二十六条：投标保证金不得超过招标项目估算价的2%。"],
    "联合体": ["第三十七条：招标人应当在招标公告中载明是否接受联合体投标。"],
}


class State(TypedDict):
    question: str

    # --- 累积字段：必须加 reducer ---
    # 如果不加 add，每轮检索结果会覆盖上一轮的，
    # 你就永远只看到最后一次的结果。
    found: Annotated[list[str], add]
    steps: Annotated[list[str], add]

    # --- 覆盖字段：只关心最新值 ---
    attempts: int      # 已经试了几次
    answer: str        # 最终答案


# ============================================================
# 节点 1：检索
# ============================================================
def retrieve(state: State) -> dict:
    """按轮次换不同的关键词检索。

    真实场景里这里会是：
      embedder.encode_query(改写后的问题) -> faiss_store.search()
    """
    attempt = state.get("attempts", 0)

    # 第 1 轮用"保证金"，第 2 轮换"联合体"
    keywords = ["保证金", "联合体"]
    keyword = keywords[attempt] if attempt < len(keywords) else ""
    hits = KB.get(keyword, [])

    return {
        "found": hits,
        "steps": [f"第 {attempt + 1} 轮：关键词「{keyword}」→ 命中 {len(hits)} 条"],
        "attempts": attempt + 1,
    }


# ============================================================
# 节点 2：生成（真项目里会调 LLM）
# ============================================================
def generate(state: State) -> dict:
    """把累积的 found 拼成上下文，生成答案。"""
    context = "\n".join(state["found"]) or "（没有检索到相关资料）"
    return {
        "answer": f"根据检索到的资料：\n{context}",
        "steps": ["生成答案"],
    }


# ============================================================
# 路由函数：决定是"接着检索"还是"去生成"
# ============================================================
# 最多试几次。这个数字必须显式写出来，不能靠框架兜底。
MAX_ATTEMPTS = 3


def should_continue(state: State) -> Literal["retrieve", "generate"]:
    """循环的出口条件。

    ⚠️ 这里是全章最关键的地方：
      条件边的逻辑写错，LangGraph 不会报错，只会默默走错路。
      务必保证两个出口都可达：
        - 找到了东西 -> generate
        - 试太多次了 -> generate（放弃）
      如果两个条件都不满足，返回 retrieve 继续循环。
    """
    # 出口 1：检索到东西了，够了
    if state["found"]:
        return "generate"

    # 出口 2：试太多次了，放弃（防死循环的业务层保险）
    if state["attempts"] >= MAX_ATTEMPTS:
        return "generate"

    # 否则继续循环
    return "retrieve"


# ============================================================
# 建图
# ============================================================
def build_graph() -> StateGraph:
    b = StateGraph(State)
    b.add_node("retrieve", retrieve)
    b.add_node("generate", generate)

    b.add_edge(START, "retrieve")

    # ★ 核心：条件边，retrieve 可能回到自己
    b.add_conditional_edges("retrieve", should_continue, {
        "retrieve": "retrieve",     # ← 这一行就是"循环"
        "generate": "generate",     # ← 这一行是"出口"
    })

    b.add_edge("generate", END)
    return b


if __name__ == "__main__":
    graph = build_graph().compile()

    print("=" * 60)
    print("场景 1：第一轮就检索到（应该只循环 1 次）")
    print("=" * 60)
    r = graph.invoke({"question": "保证金怎么算", "found": [], "steps": [], "attempts": 0})
    print("\n".join(f"  · {s}" for s in r["steps"]))
    print(f"\n答案: {r['answer']}")
    print(f"注意 found 累积了 {len(r['found'])} 条，steps 记了 {len(r['steps'])} 步")

    print("\n" + "=" * 60)
    print("场景 2：永远检索不到（应该循环 MAX_ATTEMPTS 次后放弃）")
    print("=" * 60)

    # 临时把 KB 清空，模拟"怎么都检索不到"
    KB.clear()
    r2 = graph.invoke({"question": "不存在的问题", "found": [], "steps": [], "attempts": 0})
    print("\n".join(f"  · {s}" for s in r2["steps"]))
    print(f"\n答案: {r2['answer']}")
    print(f"→ 循环了 {r2['attempts']} 次后放弃，没有死循环")

    print("\n" + "=" * 60)
    print("图结构（Mermaid）—— 注意 retrieve 上的自环")
    print("=" * 60)
    print(graph.get_graph().draw_mermaid())
```

跑：

```powershell
.\.venv\Scripts\python.exe steps\s4_loop.py
```

**预期输出（场景 1）**：

```text
  · 第 1 轮：关键词「保证金」→ 命中 1 条
  · 生成答案

答案: 根据检索到的资料：
第二十六条：投标保证金不得超过招标项目估算价的2%。
注意 found 累积了 1 条，steps 记了 2 步
```

**场景 2**：循环 3 次后放弃。

### 6.3 防死循环：三种方式

**LangGraph 不会自动帮你防死循环。** 如果 `should_continue` 永远返回 `"retrieve"`，图会一直转到报错为止。

**方式一：`recursion_limit`（框架级保险）**

```python
# 编译时不能设置，要在 invoke 时传
graph.invoke(state, config={"recursion_limit": 25})
```

超过上限抛 `GraphRecursionError`。**默认值是 25。**

> ⚠️ **注意：`recursion_limit` 计的是「超级步」数，不是节点执行次数。**
> 一个超级步可能包含多个并行节点。所以「循环 10 次」不等于「超级步 10 次」，
> 如果循环体里有并行节点，消耗会更快。

**方式二：业务层计数器（★ 推荐）**

就像上面的 `attempts` 字段。理由：

| 方式 | 报错信息 | 用户体验 |
| --- | --- | --- |
| `recursion_limit` | `GraphRecursionError` 整个请求失败 | ❌ 用户拿到异常 |
| 业务计数器 | 无报错，走正常出口 | ✅ 用户拿到"没找到，请换个问法" |

**方式三：两者都用（生产推荐）**

业务计数器负责正常降级，`recursion_limit` 作为最后的兜底（防止你的计数器逻辑本身有 bug）。

```python
# 生产写法
result = graph.invoke(
    state,
    config={
        "recursion_limit": 50,        # 兜底：绝不允许超过 50 步
        "configurable": {"thread_id": "user-1"},
    },
)
```

### 6.4 循环的典型应用场景

| 场景 | 循环体 | 出口条件 |
| --- | --- | --- |
| **检索重试** | 换关键词再检索 | 找到相关内容 / 试够次数 |
| **ReAct Agent** | agent 思考 → 调工具 → 观察 | 模型不再需要调工具 |
| **多跳推理** | 查 A → 从 A 里发现要查 B → 查 B | 不需要新查询了 |
| **自我纠错** | 生成 → 校验 → 不合格就重生成 | 校验通过 / 重试次数上限 |
| **多轮对话** | 用户输入 → 处理 → 输出 | 用户结束会话 |

### 你必须从这一步带走的四个认知

1. **循环就是"条件边连回上游"，没有特殊语法。**
2. **循环体里要累积的字段必须加 reducer。** 不加就是每轮覆盖，这是最容易踩的坑。
3. **防死循环要在业务层做，不要只靠 `recursion_limit`。** 前者给用户友好降级，后者给系统兜底。
4. **条件边写错不报错，只走错路。** 这是 LangGraph 最难调的地方——**节点里多打日志，多跑 `stream_mode="updates"` 看每步。**

---

## 第 7 章 里程碑 5：接上大模型

前面都是假的。现在把结构换成真实的 LLM 调用。

### 7.1 核心认知：LangGraph 不绑定任何 LLM 库

**这一点必须搞清楚**：LangGraph 只负责"流程怎么走"，**它不关心你怎么调模型**。

你可以用：

| 方式 | 优点 | 缺点 |
| --- | --- | --- |
| `openai` SDK（**推荐**） | 兼容 DeepSeek / 通义 / Kimi / 硅基流动 / Ollama，换模型只改两行 | 无 |
| `langchain_openai.ChatOpenAI` | 和 LangChain 生态衔接好 | 多一层抽象，调试多一层 |
| `requests` 手撸 | 最透明 | 要自己处理重试、流式、错误 |

**我推荐 `openai` SDK**，理由和你 RAG 指南第 6 章选它完全一样：**只要服务兼容 OpenAI 协议，换厂商就是改 `base_url` 和 `model` 两个字符串，代码一个字不用动。**

### 7.2 配置密钥

`.env`：

```text
# 方案 A：DeepSeek（性价比高，中文好）
OPENAI_API_KEY=sk-你的key
OPENAI_BASE_URL=https://api.deepseek.com/v1
MODEL_NAME=deepseek-chat

# 方案 B：通义千问（DashScope，OpenAI 兼容）
# OPENAI_API_KEY=sk-你的key
# OPENAI_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
# MODEL_NAME=qwen-plus

# 方案 C：本地 Ollama（先 ollama pull qwen2.5:7b-instruct）
# OPENAI_API_KEY=ollama
# OPENAI_BASE_URL=http://localhost:11434/v1
# MODEL_NAME=qwen2.5:7b-instruct

# 方案 D：本地 LoRA（910demo 那套，不走 OpenAI 协议）
# LLM_PROVIDER=local
# LORA_BASE_MODEL=Qwen/Qwen2.5-1.5B-Instruct
# LORA_ADAPTER_PATH=D:\path\to\adapter
```

### 7.3 LLM 客户端封装

`src/config.py`：

```python
"""所有配置集中在这一个文件。

为什么这么做：等你开始调 temperature、调 top_k 的时候会感谢自己。
分散在各处的话，改一个参数要全文搜索。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# load_dotenv 默认【不覆盖】已存在的系统环境变量。
# 这是好事：系统级配置优先，避免 .env 意外覆盖掉全局设置。
# 但要注意：如果你在 .env 里写了 HF_HOME 这种系统已有的变量，它不会生效。
load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = ROOT / "storage"
CHECKPOINT_DB = STORAGE_DIR / "checkpoints.db"

# --- LLM ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")

# --- 生成参数 ---
# 问答场景要稳，温度调低。这是从 RAG 指南第 7.1 节来的经验。
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))

# --- Agent 行为 ---
# 最多循环几轮（防死循环，见第 6.3 节）
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "6"))
# 是否打印每步 trace
VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"
```

`src/llm.py`：

```python
"""大模型客户端封装。

设计要点：只暴露一个 get_llm() 函数，返回一个可调用的对象。
这样以后要换 provider（DeepSeek -> 通义 -> 本地 LoRA），
只改这个文件，节点代码一行不用动。
"""

from functools import lru_cache

from openai import OpenAI

from src.config import MAX_TOKENS, MODEL_NAME, OPENAI_API_KEY, OPENAI_BASE_URL, TEMPERATURE

# 全局单例：OpenAI 客户端内部维护连接池，重复创建会浪费资源
@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY 未设置。请在 .env 里配置，或检查 .env 是否被正确加载。"
        )
    return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def chat(messages: list[dict], temperature: float | None = None) -> str:
    """调用大模型，返回文本。

    Args:
        messages: OpenAI 格式的消息列表，形如
                  [{"role": "system", "content": "..."},
                   {"role": "user", "content": "..."}]
        temperature: 不传则用配置里的默认值

    Returns:
        模型生成的文本
    """
    resp = get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE if temperature is None else temperature,
        max_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content or ""
```

### 7.4 接进图里

`steps/s5_llm.py`：

```python
"""里程碑 5：把 LLM 接进图。

本章你会看到：
  1. LLM 调用就是个普通节点，没有任何特殊之处
  2. prompt 怎么放（RAG 指南第 7.1 节的约束在这里同样适用）
  3. 怎么把调用封装成节点，让结构保持清晰

运行（需要先在 .env 里配好 key）：
    .\.venv\Scripts\python.exe steps\s5_llm.py
"""

import sys
from pathlib import Path
from operator import add
from typing import Annotated, TypedDict

# 让脚本能 import src/ 里的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.graph import StateGraph, START, END   # noqa: E402

from src.llm import chat                              # noqa: E402


# ============================================================
# prompt 模板：和你 RAG 指南里的写法保持一致
# ============================================================
# 三条约束，缺一不可（RAG 指南 7.1 节）：
#   1. 明确"资料没有就说未提及" -> 防幻觉
#   2. 要求标注引用编号      -> 可溯源
#   3. 先结论后依据          -> 好读
SYSTEM_PROMPT = """你是一个严谨的招标投标合规助手。

要求：
1. 严格依据【参考资料】回答，资料中没有的信息直接说"资料中未提及"，绝对不要编造。
2. 涉及具体事实的地方，用 [1] [2] 标注它来自哪条资料。
3. 回答简洁，先给结论，再给依据。
4. 如果问题与招标投标无关，礼貌说明你的职责范围。"""

USER_TEMPLATE = """【参考资料】
{context}

【问题】
{question}"""


class State(TypedDict):
    question: str
    context: Annotated[list[str], add]
    answer: str
    steps: Annotated[list[str], add]


# ============================================================
# 节点 1：检索（这里假装，真实场景换成你的 FaissStore.search）
# ============================================================
def retrieve(state: State) -> dict:
    """真实场景替换成：
        from src.embedder import Embedder
        from src.vector_store import FaissStore
        hits = store.search(embedder.encode_query(q), k=5)
    """
    fake_hits = [
        "第二十六条：招标人在招标文件中要求投标人提交投标保证金的，"
        "投标保证金不得超过招标项目估算价的2%。",
        "第三十七条：招标人应当在资格预审公告、招标公告或者投标邀请书中"
        "载明是否接受联合体投标。",
    ]
    return {"context": fake_hits, "steps": [f"检索命中 {len(fake_hits)} 条"]}


# ============================================================
# 节点 2：生成
# ============================================================
def generate(state: State) -> dict:
    """把检索结果拼进 prompt，调模型。"""
    # 每条资料编号，让模型能引用 [1] [2]
    context = "\n\n".join(
        f"[{i}] {text}" for i, text in enumerate(state["context"], start=1)
    )

    answer = chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": USER_TEMPLATE.format(context=context, question=state["question"]),
        },
    ])
    return {"answer": answer, "steps": ["生成答案"]}


def build_graph() -> StateGraph:
    b = StateGraph(State)
    b.add_node("retrieve", retrieve)
    b.add_node("generate", generate)
    b.add_edge(START, "retrieve")
    b.add_edge("retrieve", "generate")
    b.add_edge("generate", END)
    return b


if __name__ == "__main__":
    graph = build_graph().compile()

    question = "投标保证金最多能收多少？"
    print(f"问题：{question}\n")

    result = graph.invoke({
        "question": question,
        "context": [],
        "answer": "",
        "steps": [],
    })

    print("执行轨迹:")
    for s in result["steps"]:
        print(f"  · {s}")
    print(f"\n{'=' * 60}\n回答\n{'=' * 60}")
    print(result["answer"])
```

### 7.5 用 `stream` 看实时进度

长回答时，你可以逐 token 输出（打字机效果）：

```python
# stream_mode="messages" 会输出 LLM 的每个 token
for chunk, metadata in graph.stream(
    {"question": "投标保证金最多能收多少？", "context": [], "answer": "", "steps": []},
    stream_mode="messages",
):
    # chunk 是消息片段，metadata 里有它在哪个节点产生的
    if hasattr(chunk, "content") and chunk.content:
        print(chunk.content, end="", flush=True)
```

**这在做界面时非常有用**——用户不用干等 10 秒。

### 你必须从这一步带走的三个认知

1. **LLM 调用就是个普通节点。** LangGraph 不管你怎么调模型，你怎么会调就怎么写。
2. **prompt 约束和 RAG 指南第 7.1 节完全一致**。框架换了，prompt 该写的还得写。**换框架不解决幻觉问题。**
3. **推荐 `openai` SDK 而不是 LangChain 的封装**。少一层抽象，调试时少一层困惑。

---

## 第 8 章 里程碑 6：工具调用（从写死流程到模型自选）

第 7 章的写法有个局限：**流程是写死的**（必须先检索再生成）。真实 Agent 需要**模型自己决定调哪个工具、调几次**。

### 8.1 核心机制：ReAct 循环

```
┌─────────────────────────────────────────┐
│  agent 节点：把消息历史给模型            │
│  → 模型返回「我要调 search_law」         │
└──────────────┬──────────────────────────┘
               ↓ 条件边判断：模型要调工具吗？
        ┌──────┴──────┐
       是              否
        ↓              ↓
┌───────────────┐    END
│ tools 节点    │
│ 执行工具      │
│ 把结果加进消息│
└───────┬───────┘
        │
        └──── 连回 agent（这就是循环）
```

**这个结构就是所有 ReAct Agent 的本质**，没有更多了。

### 8.2 定义工具

`src/tools.py`：

```python
"""工具定义。

设计要点：用 @tool 装饰器，函数名即工具名，docstring 即工具描述。
模型是靠 docstring 判断该不该调这个工具的，所以描述必须写清楚。
"""

from langchain_core.tools import tool


@tool
def search_law(article: str) -> str:
    """根据条文编号精确查询《招标投标法实施条例》原文。

    适用场景：用户明确提到了条文编号，例如"第三十四条"、"第26条"。
    不适用：用户问"是什么意思"、"怎么理解"这类理解型问题。

    Args:
        article: 条文编号，格式形如 "第三十四条" 或 "第26条"

    Returns:
        该条文的原文内容；如果没找到，返回提示信息
    """
    # 真实场景：查询 SQLite 条文库
    # conn.execute("SELECT text FROM clauses WHERE article = ?", (article,))
    fake_db = {
        "第三十四条": "投标人不得相互串通投标报价，不得排挤其他投标人的公平竞争。",
        "第二十六条": "投标保证金不得超过招标项目估算价的2%。",
    }
    result = fake_db.get(article)
    if result is None:
        return f"未找到 {article} 的原文。可用的条文有：{', '.join(fake_db)}"
    return f"{article}：{result}"


@tool
def search_knowledge(query: str) -> str:
    """语义检索招标合规知识库，用于理解型、判断型问题。

    适用场景：
      - "投标保证金应该注意什么？"
      - "一个境外公司能不能参加国内的招标？"
      - "联合体投标有什么要求？"
    不适用：用户明确要求某一条原文时，请改用 search_law。

    Args:
        query: 用户的自然语言问题

    Returns:
        与问题最相关的若干法规片段，带来源标注
    """
    # 真实场景：embedder.encode_query -> faiss_store.search -> 拼结果
    return (
        "[1] （《招标投标法实施条例》第三十七条）"
        "招标人接受联合体投标并进行资格预审的，"
        "联合体应当在提交资格预审申请文件前组成。\n\n"
        "[2] （《招标投标法实施条例》第二十六条）"
        "投标保证金不得超过招标项目估算价的2%。"
    )


@tool
def list_my_tools() -> str:
    """列出当前可用的所有工具。

    适用场景：用户问"你能做什么"、"有哪些功能"。
    不适用：任何实质性的问题都不该调这个。
    """
    return "可用工具：search_law（条文精确查询）、search_knowledge（语义检索）"


#: 工具列表，统一在这里维护
ALL_TOOLS = [search_law, search_knowledge, list_my_tools]
```

> ⚠️ **这是全章最重要的一条注意：`@tool` 对 docstring 极度敏感。**
>
> **模型是靠 docstring 判断该不该调这个工具的。**
>
> | docstring 写法 | 效果 |
> | --- | --- |
> | `"""查询"""` | ❌ 模型不知道什么时候用，可能永远不调，也可能乱调 |
> | `"""根据条文编号查询法规原文。Args: article: 形如'第三十四条'"""` | ✅ 模型能准确判断 |
>
> **写 docstring 的原则**：
> 1. **说清楚适用场景**，最好带上例子
> 2. **说清楚不适用场景**——当有多个相似工具时，这条最关键
> 3. **参数要说明格式**，比如 `article` 是 "第三十四条" 而不是 "34"
>
> **这和我们前面讲的路由规则、以及 RAG 指南里的 prompt 约束是同一个道理：你描述得越清楚，路由越准。**

### 8.3 完整示例

`steps/s6_tools.py`：

```python
"""里程碑 6：工具调用（ReAct Agent）。

本章你会看到：
  1. 用 @tool 定义工具，用 bind_tools 绑定到模型
  2. ToolNode 和 tools_condition 这两个官方预制件
  3. 经典的 agent <-> tools 循环
  4. 为什么必须自己加防死循环

运行（需要先在 .env 里配好 key）：
    .\.venv\Scripts\python.exe steps\s6_tools.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import HumanMessage, SystemMessage  # noqa: E402
from langgraph.graph import StateGraph, MessagesState, START, END  # noqa: E402
from langgraph.prebuilt import ToolNode, tools_condition  # noqa: E402

from src.llm import get_client  # noqa: E402
from src.config import MODEL_NAME, TEMPERATURE, MAX_ITERATIONS  # noqa: E402
from src.tools import ALL_TOOLS  # noqa: E402


SYSTEM_PROMPT = """你是一个招标投标合规助手。

你可以调用工具来查询信息：
  - 用户提到具体条文编号时，用 search_law
  - 用户问理解型问题时，用 search_knowledge

调用工具拿到资料后，严格依据资料回答。
资料中没有的信息直接说"资料中未提及"，不要编造。"""


# ============================================================
# 把工具绑定到模型
# ============================================================
class BoundLLM:
    """把 OpenAI 客户端包装成"会调工具"的对象。

    为什么要这层包装：LangGraph 的 ToolNode / tools_condition 期望
    拿到的是 LangChain 的 AIMessage 格式（带 .tool_calls 属性）。
    这里做个转换，好处是不用引入 langchain_openai 整套依赖。
    """

    def __init__(self):
        self.client = get_client()
        # 把 @tool 定义的函数转成 OpenAI 的 function-calling schema
        self.tool_schemas = [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.args_schema.model_json_schema(),
                },
            }
            for t in ALL_TOOLS
        ]

    def invoke(self, messages):
        """接收 LangChain 消息列表，返回 LangChain AIMessage。

        这是为了兼容 ToolsNode 的输入输出约定。
        """
        from langchain_core.messages import AIMessage

        # LangChain 消息 -> OpenAI 格式
        oai_messages = []
        for m in messages:
            role = {"human": "user", "ai": "assistant", "system": "system"}.get(
                m.type, "user"
            )
            oai_messages.append({"role": role, "content": m.content or ""})

        resp = self.client.chat.completions.create(
            model=MODEL_NAME,
            messages=oai_messages,
            tools=self.tool_schemas,
            temperature=TEMPERATURE,
        )

        msg = resp.choices[0].message

        # OpenAI 格式 -> LangChain AIMessage
        tool_calls = []
        for tc in (msg.tool_calls or []):
            import json
            tool_calls.append({
                "name": tc.function.name,
                "args": json.loads(tc.function.arguments),
                "id": tc.id,
            })

        return AIMessage(content=msg.content or "", tool_calls=tool_calls)


# ============================================================
# agent 节点
# ============================================================
llm = BoundLLM()


def agent_node(state: MessagesState) -> dict:
    """把整个消息历史给模型，让模型决定下一步。"""
    response = llm.invoke(state["messages"])
    return {"messages": [response]}


# ============================================================
# 建图
# ============================================================
def build_graph() -> StateGraph:
    b = StateGraph(MessagesState)

    b.add_node("agent", agent_node)
    # ToolNode 是官方预制件：自动执行工具、把结果包成 ToolMessage
    b.add_node("tools", ToolNode(ALL_TOOLS))

    b.add_edge(START, "agent")

    # tools_condition 是官方预制件：
    #   如果模型的 AIMessage 里有 tool_calls -> 返回 "tools"
    #   否则 -> 返回 END 对应的特殊值
    b.add_conditional_edges("agent", tools_condition)

    # ★ 关键：工具执行完回到 agent，形成 ReAct 循环
    b.add_edge("tools", "agent")

    return b


if __name__ == "__main__":
    graph = build_graph().compile()

    questions = [
        "第三十四条是什么内容？",          # 应该调 search_law
        "投标保证金有什么要求？",          # 应该调 search_knowledge
        "你能做什么？",                    # 应该调 list_my_tools
    ]

    for q in questions:
        print("=" * 60)
        print(f"问题：{q}")
        print("=" * 60)

        result = graph.invoke(
            {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=q),
                ]
            },
            config={"recursion_limit": MAX_ITERATIONS * 2 + 2},   # 防死循环
        )

        # 打印执行轨迹：模型调了什么工具
        print("执行轨迹:")
        for m in result["messages"]:
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    print(f"  → 调用工具 {tc['name']}({tc['args']})")
            if m.type == "tool":
                preview = (m.content or "")[:80].replace("\n", " ")
                print(f"  ← 工具返回: {preview}...")

        print(f"\n最终回答:\n{result['messages'][-1].content}\n")
```

### 8.4 `ToolsNode` 和 `tools_condition` 到底是什么

**`ToolNode(tools)`** —— 一个预制的节点，帮你做三件事：

1. 从最后一条 `AIMessage` 里读出 `tool_calls`
2. 逐个执行对应的工具函数
3. 把结果包成 `ToolMessage` 追加到消息列表

**你不用自己写这个节点**，除非有特殊需求（比如要做权限控制、要做工具调用日志）。

**`tools_condition`** —— 一个预制的路由函数，帮你判断：

```python
# 它做的事大概等价于：
def tools_condition(state) -> str:
    last = state["messages"][-1]
    if getattr(last, "tool_calls", None):
        return "tools"      # 模型要调工具
    return END              # 不调了，结束
```

> ⚠️ **`tools_condition` 的默认节点名**
>
> 它默认假设你的工具节点叫 `"tools"`。如果你起了别的名字：
> ```python
> b.add_node("my_tools", ToolNode(ALL_TOOLS))
> b.add_conditional_edges("agent", tools_condition, {"tools": "my_tools"})
> ```
> 要用映射字典改一下，否则会报找不到节点。

### 8.5 为什么必须自己防死循环

`tools_condition` **只判断"模型还想不想调工具"**，它不管模型会不会陷入"调 A → 不行 → 再调 A → 不行"的循环。

**真实案例**：模型调了 `search_law("第三十四条")`，工具返回"未找到"，模型不甘心，又调 `search_law("第三十四条")`，如此反复。

**所以要用 `recursion_limit` 兜底**（上面代码里已经加了）。

> **更好的做法**：在你自己写的 agent 节点里记录调用次数，超过上限就强制返回一个"我已经尝试多次但没找到"的答案。
> 这比直接抛 `GraphRecursionError` 用户体验好得多。

### 你必须从这一步带走的三个认知

1. **ReAct 就是 `agent ↔ tools` 循环**。理解了第 6 章的循环，这里就没有新东西了。
2. **`@tool` 的 docstring 就是模型的"使用说明书"**。写得越清楚，模型选得越准。
3. **`ToolNode` + `tools_condition` 是预制件，不是必须**。想完全掌控就自己写节点和路由函数。

---

## 第 9 章 里程碑 7：持久化与人在回路

**这是 LangGraph 相对其他框架最独一无二的能力。**

### 9.1 Checkpointer 是什么

**Checkpointer = 在图执行的每一步自动存快照。**

存了之后能做三件事：

| 能力 | 说明 | 用途 |
| --- | --- | --- |
| **多轮会话** | 同一个 `thread_id` 自动带上历史 | 聊天机器人不用自己维护历史 |
| **中断恢复** | 进程崩了，从上次的位置继续 | 长时间任务 |
| **时间旅行** | 回到任意历史检查点，从那里重新跑 | 调试、A/B 测试不同分支 |
| **人在回路** | 跑到一半停下，等人确认 | 合规审核、人工把关 |

### 9.2 三种 Checkpointer

| 实现 | 引入 | 持久性 | 适用 |
| --- | --- | --- | --- |
| `MemorySaver` | `langgraph.checkpoint.memory` | 进程重启就丢 | 开发调试 |
| `SqliteSaver` | `langgraph.checkpoint.sqlite` | 落盘，单文件 | **个人项目推荐** |
| `PostgresSaver` | `langgraph.checkpoint.postgres` | 落盘，支持并发 | **多进程 / 多实例** |
| `AsyncPostgresSaver` | `langgraph.checkpoint.postgres.aio` | 同上，异步版 | FastAPI async 端点 |

**我推荐 `SqliteSaver` 起步** —— 和你 RAG 项目用 SQLite 而不是 Docker 的思路一致：**零部署、单文件、能备份、够用。**

**选哪个的判断标准是「有几个进程」，不是「数据有多重要」**：

| 你的部署形态 | 该用 |
| --- | --- |
| 本地跑脚本、单进程 | `MemorySaver` |
| 单机、单进程、要跨重启保留会话 | `SqliteSaver` |
| `uvicorn --workers 4`、多个容器实例、团队共享 | **`PostgresSaver`（§9.5）** |

SQLite 是**单文件、单写者**。一旦有多个进程同时写检查点，就会撞 `database is locked`。**这才是上 Postgres 的真正理由** —— 不是因为「生产环境听起来更高级」。

### 9.3 完整示例

`steps/s7_persist.py`：

```python
"""里程碑 7：持久化与人在回路。

本章你会看到：
  1. MemorySaver 怎么用，thread_id 为什么必须有
  2. SqliteSaver 怎么做真正的持久化
  3. 多轮会话怎么自动带上历史
  4. interrupt_before 怎么实现"人工审核后再继续"
  5. 时间旅行：从任意历史检查点重新跑

运行：
    .\.venv\Scripts\python.exe steps\s7_persist.py
"""

import sys
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.checkpoint.memory import MemorySaver   # noqa: E402
from langgraph.graph import StateGraph, START, END   # noqa: E402
from operator import add                             # noqa: E402


class State(TypedDict):
    question: str
    draft: str
    approved: str          # 人工审核结果
    log: Annotated[list[str], add]


# ============================================================
# 节点 1：生成草稿（模拟）
# ============================================================
def draft_answer(state: State) -> dict:
    return {
        "draft": f"[草稿] 针对「{state['question']}」的合规建议：……（此处省略 300 字）",
        "log": ["生成草稿"],
    }


# ============================================================
# 节点 2：定稿（人工审核后才会执行）
# ============================================================
def finalize(state: State) -> dict:
    return {
        "approved": f"【已审核通过】\n{state['draft']}",
        "log": ["人工审核完成，定稿"],
    }


def build_graph(checkpointer):
    b = StateGraph(State)
    b.add_node("draft", draft_answer)
    b.add_node("finalize", finalize)

    b.add_edge(START, "draft")
    b.add_edge("draft", "finalize")
    b.add_edge("finalize", END)

    return b.compile(
        checkpointer=checkpointer,
        # ★ 关键：在 finalize 之前暂停，等人确认
        interrupt_before=["finalize"],
    )


if __name__ == "__main__":
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer)

    # ★ thread_id 是会话标识，同一个 thread_id 的历史会累积
    config = {"configurable": {"thread_id": "user-001"}}

    print("=" * 60)
    print("第 1 步：跑图，会停在 finalize 之前")
    print("=" * 60)
    graph.invoke({"question": "投标保证金有什么要求", "log": []}, config)

    # 查看当前停在哪
    snapshot = graph.get_state(config)
    print(f"当前状态: {snapshot.values}")
    print(f"下一步要执行: {snapshot.next}")     # 应该是 ('finalize',)
    print("→ 图已暂停，等待人工审核")

    print("\n" + "=" * 60)
    print("第 2 步：人工确认后继续（传 None 表示"继续上次")")
    print("=" * 60)
    graph.invoke(None, config)

    final = graph.get_state(config)
    print(f"最终状态:\n{final.values['approved']}")
    print(f"\n执行轨迹: {final.values['log']}")

    print("\n" + "=" * 60)
    print("第 3 步：查看历史检查点（时间旅行）")
    print("=" * 60)
    history = list(graph.get_state_history(config))
    print(f"共记录了 {len(history)} 个检查点:")
    for i, h in enumerate(reversed(history)):
        nxt = h.next if h.next else ("（结束）",)
        print(f"  [{i}] next={nxt}  log={h.values.get('log', [])}")
```

跑：

```powershell
.\.venv\Scripts\python.exe steps\s7_persist.py
```

**预期输出**：

```text
第 1 步：跑图，会停在 finalize 之前
当前状态: {'question': '投标保证金有什么要求', 'draft': '[草稿] ...', 'log': ['生成草稿']}
下一步要执行: ('finalize',)
→ 图已暂停，等待人工审核

第 2 步：人工确认后继续
最终状态:
【已审核通过】
[草稿] 针对「投标保证金有什么要求」的合规建议：……

执行轨迹: ['生成草稿', '人工审核完成，定稿']

第 3 步：查看历史检查点
共记录了 N 个检查点:
  [0] next=（结束）  log=['生成草稿', '人工审核完成，定稿']
  [1] next=('finalize',)  log=['生成草稿']
  [2] next=('draft',)  log=[]
```

### 9.4 换成 SqliteSaver（持久化到文件）

```python
# 需要先装：uv pip install langgraph-checkpoint-sqlite
from langgraph.checkpoint.sqlite import SqliteSaver

# 用 with 保证连接正确关闭
with SqliteSaver.from_conn_string("storage/checkpoints.db") as checkpointer:
    graph = build_graph(checkpointer)
    graph.invoke({...}, config)
```

> ⚠️ **注意：SqliteSaver 的 `from_conn_string` 是上下文管理器。**
> 直接调用需要接 `with`，否则连接会泄漏。要脱离 `with` 用，得传一个 `sqlite3.Connection` 对象进去。
>
> ```python
> import sqlite3
> conn = sqlite3.connect("storage/checkpoints.db", check_same_thread=False)
> checkpointer = SqliteSaver(conn)
> ```

### 9.5 换成 PostgresSaver（多进程 / 生产）

#### 9.5.1 先确认：你**真的**需要吗

看到「生产」两个字就上 Postgres，是新手最容易犯的过度设计。Postgres 换来的是**部署成本**：多一个服务进程、要管账号密码、要备份、要处理连接串泄漏、要监控磁盘。

**唯一硬性理由是「多进程并发写」**：

| 现象 | 根因 |
| --- | --- |
| `sqlite3.OperationalError: database is locked` | 两个 worker 同时写同一个 `.db` 文件 |
| 检查点莫名丢失 / 回滚 | 同上，SQLite 的写入是互斥的 |
| 容器滚动更新时会话全没了 | 每个容器本地一个 `.db`，谁也不认识谁 |

**所以判断标准很简单**：

```text
单进程（python app.py / uvicorn 不带 --workers）→ SqliteSaver，够了，别折腾
多进程 / 多容器 / 多台机器共享会话          → PostgresSaver（本节）
```

`D:\tender-agent` 那个 FastAPI 骨架，**如果只用默认单 worker 跑，SQLite 就完全够用**；等你真上多实例部署的那天再切过来。

#### 9.5.2 装依赖

```powershell
uv pip install langgraph-checkpoint-postgres "psycopg[binary,pool]"
```

| 包 | 为什么 |
| --- | --- |
| `langgraph-checkpoint-postgres` | saver 本体，当前版本 **3.1.2**（Python ≥ 3.10） |
| `psycopg` | 会自动被带上（Psycopg 3，纯 Python 实现） |
| `[binary]` | 换成预编译二进制。**Windows 上基本必装** —— 否则可能因为找不到 `pg_config` 而编译失败 |
| `[pool]` | 提供 `psycopg_pool`，生产用连接池才有（§9.5.5） |

> ⚠️ 注意包名是 `langgraph-checkpoint-postgres`，**和主包 `langgraph` 是两个包**，必须单独装。

#### 9.5.3 起一个 Postgres（Docker 最省事）

```yaml
# docker-compose.yml
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data   # ← 不挂卷，容器一删数据全没
volumes:
  pgdata:
```

```powershell
docker compose up -d postgres
docker compose exec postgres pg_isready -U postgres   # 确认起来了
```

连接串长这样（`postgres://` 和 `postgresql://` 两种前缀 psycopg 都认）：

```text
postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable
```

> ⚠️ `sslmode=disable` 只在本地开发这么写。**连云数据库时必须去掉**（云厂商一般要求 TLS），否则要么连不上要么数据明文过网。

#### 9.5.4 最小可用写法

```python
import os
from langgraph.checkpoint.postgres import PostgresSaver

DB_URI = os.getenv("POSTGRES_URI", "postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable")

# from_conn_string 返回的是「上下文管理器」，不是 saver 本身，所以必须 with
with PostgresSaver.from_conn_string(DB_URI) as checkpointer:
    checkpointer.setup()        # ★ 第一次用必须手动调，建表（见下方警告）

    graph = build_graph(checkpointer)          # 你的建图函数
    config = {"configurable": {"thread_id": "tender-001"}}
    result = graph.invoke({"question": "投标保证金上限是多少？"}, config)
    print(result["answer"])
```

> ⚠️🔴 **`setup()` 不会自动跑。** 忘了它，第一次执行就报：
>
> ```text
> psycopg.errors.UndefinedTable: relation "checkpoints" does not exist
> ```
>
> 它会创建 `checkpoints` / `checkpoint_blobs` / `checkpoint_writes` / `checkpoint_migrations` 这几张表。
> **只需跑一次**（重复调是幂等的，不报错，但没必要每次启动都调）。
> 建议单独放一个初始化脚本，或者塞进部署流程：
>
> ```python
> # scripts/init_db.py —— 部署时跑一次
> from langgraph.checkpoint.postgres import PostgresSaver
> with PostgresSaver.from_conn_string(os.environ["POSTGRES_URI"]) as cp:
>     cp.setup()
>     print("检查点表已就绪")
> ```

#### 9.5.5 三处必须注意的参数（官方点名的坑）

如果你**不**用 `from_conn_string`，而是自己建连接传进去，那两个参数**一个都不能少**：

```python
import psycopg
from psycopg.rows import dict_row            # ← 少这个就报 TypeError
from langgraph.checkpoint.postgres import PostgresSaver

conn = psycopg.connect(
    DB_URI,
    autocommit=True,                          # ← 少这个建表可能不提交
    row_factory=dict_row,                     # ← 少这个读取时 TypeError
)
checkpointer = PostgresSaver(conn)
checkpointer.setup()
```

> ⚠️🔴 **为什么这两个是硬要求**

| 参数 | 少了会怎样 | 原因 |
| --- | --- | --- |
| `autocommit=True` | `.setup()` **看起来成功，表却没了** | 建表语句不自动提交，连接关闭即回滚 |
| `row_factory=dict_row` | `TypeError: tuple indices must be integers or slices, not str` | saver 内部用 `row["column_name"]` 取列；默认 `tuple_row` 只支持 `row[0]` |

> **第一条最难查**：没有报错、没有异常，你只是过一会儿发现「表不存在」。
> 反过来说 —— **能用 `from_conn_string()` 就用它，内部已经帮你设好了**，不用自己操心。

#### 9.5.6 生产写法：连接池

图**每执行一步就写一次检查点**。长会话、多请求下，反复建连接的开销很可观。生产用池：

```python
import os
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool
from langgraph.checkpoint.postgres import PostgresSaver

pool = ConnectionPool(
    conninfo=os.environ["POSTGRES_URI"],
    max_size=20,                                        # 池大小，按「worker 数 × 单请求并发」估
    kwargs={"autocommit": True, "row_factory": dict_row},  # ← 注意在 kwargs 里，不是顶层参数
    open=True,                                          # 启动时就把连接建好
)

checkpointer = PostgresSaver(pool)
checkpointer.setup()          # 仍然只需第一次
```

> ⚠️ **`autocommit` / `row_factory` 是放在 `kwargs` 里传给「每一条连接」的**，直接写成 `ConnectionPool(autocommit=True)` 是无效的 —— 这个参数名 `ConnectionPool` 不认。
>
> 用池的好处还有：**`PostgresSaver(pool)` 不需要 `with`**，生命周期交给池自己管，放在 FastAPI 的模块级变量或 `app.state` 里都行。

#### 9.5.7 FastAPI 里用：异步版（`AsyncPostgresSaver`）

`D:\tender-agent` 的 API 是 FastAPI。**如果你用 `async def` 端点，就该配异步 saver，别用同步的把事件循环堵住。**

```python
from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver      # ← .aio 子模块

@asynccontextmanager
async def lifespan(app: FastAPI):
    # 整个应用生命周期内持有一个 saver
    async with AsyncPostgresSaver.from_conn_string(os.environ["POSTGRES_URI"]) as checkpointer:
        await checkpointer.setup()                    # ★ 异步版必须 await
        app.state.graph = build_graph(checkpointer)
        yield
    # 退出时自动关闭连接

app = FastAPI(lifespan=lifespan)


@app.post("/ask")
async def ask(payload: dict, thread_id: str = "default"):
    # 注意：用的是 ainvoke，不是 invoke
    result = await app.state.graph.ainvoke(
        {"question": payload["question"]},
        {"configurable": {"thread_id": thread_id}},
    )
    return {"answer": result["answer"]}
```

> ⚠️🔴 **同步 / 异步不能混用**
>
> | 配错 | 结果 |
> | --- | --- |
> | `AsyncPostgresSaver` + `graph.invoke()` | 报错（异步 saver 只实现 `aget/aput`） |
> | `PostgresSaver` + `graph.ainvoke()` | 同步 IO 卡住事件循环，并发直接崩 |
>
> **一个项目里只选一套。** 已经有异步端点 → 全异步；纯脚本 → 全同步。
>
> ⚠️ 另外：异步版 `.setup()` 是**协程**。忘记 `await` 不会报错，只会给你一条 `RuntimeWarning: coroutine ... was never awaited`，然后表根本没建 —— 又是一个「静默失败」。

#### 9.5.8 两个生产必须处理的运维问题

**① `thread_id` 有长度上限（255 字符）**

```python
# ❌ 把整段问题当成 thread_id —— 迟早爆
# config = {"configurable": {"thread_id": f"用户{uid}-{question}"}}

# ✅ 用 UUID 或哈希
import uuid
config = {"configurable": {"thread_id": str(uuid.uuid4())}}
```

> 官方明确说明：`thread_id` 存在长度受限的列里，**保持在 255 字符以内**，超了直接数据库报错。

**② 检查点会无限膨胀**

每执行一步存一条。一个跑了 200 轮的会话就是 200+ 行，加上 `checkpoint_blobs` 里的状态快照，**磁盘涨得比你想象的快**。

```sql
-- 清理 30 天没动过的会话（按需改成 cron / 定时任务）
DELETE FROM checkpoints
WHERE thread_id IN (
    SELECT thread_id FROM checkpoints
    GROUP BY thread_id
    HAVING MAX(created_at) < now() - interval '30 days'
);
```

> 官方建议：**定期修剪或设置保留策略**。别等磁盘告警了才想起来这事。

#### 9.5.9 安全开关

```powershell
# 限制检查点反序列化的类型范围
$env:LANGGRAPH_STRICT_MSGPACK = "true"
```

> 官方安全提示：设置 `LANGGRAPH_STRICT_MSGPACK=true`，或在创建 checkpointer 时显式传 `allowed_msgpack_modules`。
> 作用是**把反序列化限制在已知安全类型内** —— 万一数据库被写入恶意内容，防止反序列化时执行任意代码。
> **自建或共享的 Postgres，建议直接打开。**

#### 9.5.10 一套代码支持两种 saver（推荐）

不要为了换 saver 去改业务代码。抽一个工厂函数，靠环境变量切换：

```python
# src/checkpointer.py
"""按环境变量返回 checkpointer：开发用 SQLite，生产用 Postgres，业务代码零改动。"""

import os
import sqlite3
from pathlib import Path


def get_checkpointer(backend: str | None = None):
    backend = (backend or os.getenv("CHECKPOINT_BACKEND", "sqlite")).lower()

    if backend == "memory":
        from langgraph.checkpoint.memory import MemorySaver
        return MemorySaver()

    if backend == "sqlite":
        from langgraph.checkpoint.sqlite import SqliteSaver
        Path("storage").mkdir(exist_ok=True)
        # 这里不用 from_conn_string 的 with 形式 —— 我们要长期持有这个连接
        conn = sqlite3.connect("storage/checkpoints.db", check_same_thread=False)
        return SqliteSaver(conn)

    if backend == "postgres":
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool
        from langgraph.checkpoint.postgres import PostgresSaver

        pool = ConnectionPool(
            conninfo=os.environ["POSTGRES_URI"],
            max_size=int(os.getenv("PG_POOL_SIZE", "20")),
            kwargs={"autocommit": True, "row_factory": dict_row},
            open=True,
        )
        cp = PostgresSaver(pool)
        cp.setup()        # 幂等，第一次会建表
        return cp

    raise ValueError(f"未知的 CHECKPOINT_BACKEND: {backend}")


# 用法完全不变
# graph = build_graph(get_checkpointer())
```

配套 `.env`：

```text
# 本地开发（默认）
CHECKPOINT_BACKEND=sqlite

# 上多实例时改成这样，代码一行不用动
# CHECKPOINT_BACKEND=postgres
# POSTGRES_URI=postgresql://postgres:postgres@localhost:5432/postgres?sslmode=disable
# PG_POOL_SIZE=20
```

> **为什么要池写法而不是 `with`**：`with PostgresSaver.from_conn_string(...)` 的生命周期捆在一个代码块里，而 FastAPI 需要**全局持有一个 saver**。用池可以脱离 `with`，这是最干净的写法。

#### 9.5.11 SQLite → Postgres 迁移时要注意

**检查点表可以不清，但不通用。** 两边的表结构、序列化格式由各自的包维护，**别指望把 `.db` 里的数据导进 Postgres**。

实操建议：**换 saver = 丢掉历史会话**。用户重新开一轮就是了，检查点本来就是临时状态，不是业务数据。

> ⚠️ 如果**会话历史对你是业务数据**（比如审核记录要留档），那它就不该只躺在 checkpoint 里 —— 应该让节点把关键结果**显式写进你自己的业务表**。**checkpoint 是「执行状态」，不是「业务数据」。** 这条分界线一开始就要划清楚。

#### 9.5.12 你必须从这一节带走的三个认知

1. **`setup()` 必须手动跑一次。** 忘了就 `relation "checkpoints" does not exist`；这是新手上 Postgres 的第一号报错。
2. **手动建连接必须同时给 `autocommit=True` 和 `row_factory=dict_row`。** 前者缺失是**静默丢表**（最阴险），后者缺失是 `TypeError`（还算友好）。
3. **选 saver 看「进程数」，不看「数据重要性」。** 单进程用 SQLite 是完全体面的选择，不是偷懒。

> 📌 **本节说明**：内容依据 `langgraph-checkpoint-postgres` **3.1.2** 官方文档（2026-08-08 发布）整理。
> **本机尚未接真实 Postgres 实例实测** —— §9.4 的 `SqliteSaver` 是跑过的，本节的 Postgres 部分需要你本地起一个实例才能验证。
> 需要我把依赖装上、起个 Postgres 跑通一遍（并补一个 `steps/s8_postgres.py` 可运行脚本）的话，跟我说。

### 9.6 多轮会话（聊天机器人最常用）

**同一个 `thread_id` 的多次 `invoke`，会自动带上历史。** 你不需要自己维护消息数组。

```python
config = {"configurable": {"thread_id": "chat-001"}}

# 第 1 轮
graph.invoke({"messages": [HumanMessage(content="投标保证金怎么算？")]}, config)

# 第 2 轮（不传历史，历史自动带上）
graph.invoke({"messages": [HumanMessage(content="那联合体投标呢？")]}, config)

# ← 模型能看到第 1 轮的内容，所以"那"能被正确理解
```

**这是 Checkpointer 最实用的功能。** 没有它，你得自己维护一个 `messages` 列表、每次手动传、还要控制长度。

> ⚠️ **跨进程/跨天要继续会话，必须用 `SqliteSaver` 或 `PostgresSaver`。**
> `MemorySaver` 是纯内存的，进程一关就没了，"这个用户昨天的对话"无从谈起。

### 9.7 怎么修改状态（人工干预）

有时审核人要**直接改内容**，而不是只点"通过"：

```python
# 拿到当前状态
state = graph.get_state(config)

# 用 update_state 打补丁（会生成新检查点）
graph.update_state(
    config,
    {"draft": "【人工修改版】投标保证金不得超过估算价的 2%..."},
    as_node="draft",        # 假装这个修改是 draft 节点做的
)
```

**`as_node` 是干什么的**：告诉 LangGraph"这个修改来自哪个节点"，它据此决定下一步该走哪。**不传的话可能走错分支。**

### 你必须从这一步带走的三个认知

1. **`thread_id` 是会话隔离的唯一依据。** 有 checkpointer 就必须传，否则报 `ValueError`。
2. **`MemorySaver` 只适合开发**。要跨重启就用 `SqliteSaver`（单进程，§9.4）；要跨进程 / 多实例才上 `PostgresSaver`（§9.5）。**判断依据是「有几个进程在写」。**
3. **`interrupt_before` 是合规场景的刚需**。传统写法要几百行状态管理，这里一个参数。

> **两分钟自测**：`MemorySaver` / `SqliteSaver` / `PostgresSaver` 分别在什么情况下用？
> 答不上来的话，回看 §9.2 的判断表。

---

## 第 10 章 可视化、流式与调试

### 10.1 把图画出来看

```python
print(graph.get_graph().draw_mermaid())
```

输出 Mermaid 文本，贴到 https://mermaid.live 就能看到图。

**带 checkpointer 的图还能看结构详情**：

```python
# 查看某个线程的历史执行路径
for state in graph.get_state_history(config):
    print(state.next, state.values.get("steps"))
```

> **强烈建议：复杂图不先画一眼就调，纯属自虐。**
> 尤其当你怀疑"条件边是不是走错了"的时候，图上一眼就能看出来。

### 10.2 流式输出的三档模式

```python
for chunk in graph.stream(inputs, stream_mode="updates"):
    print(chunk)
```

| `stream_mode` | 输出内容 | 用途 |
| --- | --- | --- |
| `"values"` | 每步之后的**完整 state** | 想看全局变化 |
| `"updates"` | 每步**只输出增量** | ★ 调试首选，最好读 |
| `"messages"` | LLM **逐 token** 输出 | 打字机效果 |
| `"custom"` | 你在节点里 `get_stream_writer()` 写的内容 | 自定义进度 |

**多模式同时开**：

```python
for mode, chunk in graph.stream(inputs, stream_mode=["updates", "messages"]):
    print(f"[{mode}] {chunk}")
```

**`"updates"` 的实用调试写法**：

```python
for chunk in graph.stream(state, stream_mode="updates"):
    for node_name, update in chunk.items():
        print(f"▶ {node_name}")
        for k, v in (update or {}).items():
            preview = str(v)[:100]
            print(f"    {k} = {preview}")
```

**这样你能清楚看到每个节点干了什么、返回了什么。** 调试 LangGraph 主要靠这个。

### 10.3 环境变量开启详细日志

```powershell
$env:LANGCHAIN_VERBOSE = "true"
$env:DEBUG = "true"
```

会打印 LangChain/LangGraph 的内部调用链。**信息量很大，只在实在找不到问题时开。**

### 10.4 本机高频坑清单

这些是在你这台机器上真会碰到的，按遇到概率排序。

---

#### 坑 1 🔴 节点忘了 return，或原地改了 state

**症状**：`InvalidUpdateError`，或者字段莫名其妙没更新。

```python
# ❌ 错误写法
def bad_node(state: State) -> dict:
    state["answer"] = "x"      # 原地修改，LangGraph 看不到
    # 没有 return

# ✅ 正确写法
def good_node(state: State) -> dict:
    return {"answer": "x"}
```

**为什么容易犯**：写普通函数习惯了"改完就完了"，而 LangGraph 要求你返回**增量字典**。

**规矩：永远 `return {...}`，永远不要原地改 state。**

---

#### 坑 2 🔴 循环里忘了加 reducer，数据被覆盖

**症状**：跑完循环，`steps` / `found` 里只剩最后一条，前面的都没了。**不报错。**

```python
# ❌ 覆盖
class State(TypedDict):
    found: list[str]

# ✅ 累积
class State(TypedDict):
    found: Annotated[list[str], add]
```

**这个坑最阴险的地方是不报错**。你只会觉得"怎么数据少了"，然后怀疑自己逻辑写错了。

**排查方法**：在循环体里 `print(len(state["found"]))`。如果永远是 0 或 1，就是没加 reducer。

---

#### 坑 3 🔴 条件边写错，不报错只走错路

**症状**：流程走了意料之外的分支，但**没有任何报错**。

```python
def decide(state) -> str:
    if state["score"] > 0.5:
        return "high"
    return "low"          # ← 如果映射字典里没有 "low"，运行时才炸
```

**排查方法**：

1. 路由函数里 `print(f"路由决策: {decision}")`
2. 用 `stream_mode="updates"` 看实际执行了哪些节点
3. `graph.get_graph().draw_mermaid()` 对照图结构

**这是 LangGraph 最难调的地方，因为它是"静默失败"。**

---

#### 坑 4 没有 `thread_id` 就用 checkpointer

**症状**：

```text
ValueError: Checkpointer requires one or more of the following 'configurable' keys:
  thread_id, checkpoint_ns, checkpoint_id
```

**原因**：挂了 checkpointer 就必须有会话标识，否则它不知道该把状态存到哪个"桶"里。

```python
config = {"configurable": {"thread_id": "user-1"}}
graph.invoke(state, config)
```

---

#### 坑 5 `add_edge(START, "x")` 但 `x` 没定义

**症状**：

```text
ValueError: 'x' is not a valid node
```

**两种修法**：

- 要么真的 `add_node("x", func)`
- 要么改成 `add_conditional_edges(START, routing_func, {...})`

**这个坑的典型触发**：从教程复制代码时，教程定义了 `router` 节点但你没复制那一行。

---

#### 坑 6 装了旧版教程的 API

**症状**：`AttributeError: 'StateGraph' object has no attribute 'set_entry_point'`

**原因**：网上大量教程是 LangGraph 0.1~0.2 时代的，1.x 已移除这些方法。

| 旧 API | 1.x 替代 |
| --- | --- |
| `set_entry_point("node")` | `add_edge(START, "node")` |
| `set_finish_point("node")` | `add_edge("node", END)` |
| `MessageGraph()` | `StateGraph(MessagesState)` |

**看到这两种 API 的教程，直接关掉。**

---

#### 坑 7 循环没出口 → `GraphRecursionError`

**症状**：

```text
GraphRecursionError: Recursion limit of 25 reached without hitting a stop condition.
```

**这个报错信息其实很有用**，它明确告诉你是循环问题。

**修法**：

```python
# 临时抬高上限（治标）
graph.invoke(state, config={"recursion_limit": 100})

# 真正的修法：检查路由函数的出口条件
```

**根治：在业务层加计数器**（第 6.3 节）。

---

#### 坑 8 `@tool` 的 docstring 写得太水，模型不调工具

**症状**：模型该调工具的时候不调，或者调错工具。

```python
# ❌ 模型完全不知道什么时候用
@tool
def search_law(article: str) -> str:
    """查询法规。"""
    ...

# ✅ 说明白适用场景 + 不适用场景 + 参数格式
@tool
def search_law(article: str) -> str:
    """根据条文编号精确查询法规原文。

    适用：用户明确提到条文编号，如"第三十四条"。
    不适用：理解型问题请用 search_knowledge。

    Args:
        article: 形如 "第三十四条" 或 "第26条"
    """
    ...
```

**判断标准**：把你的 docstring 单独拿出来给别人看，他能不能准确说出"什么时候该调这个工具"。**不能就重写。**

---

#### 坑 9 同一字段被同轮多个节点写入，且没有 reducer

**症状**：

```text
InvalidUpdateError: At key 'value': Can receive only one value per step.
  Use an Annotated key to handle multiple values.
```

**原因**：同一超级步里有并行节点，都往同一个字段写。

**修法**：加 reducer。

```python
value: Annotated[int, add]      # 允许多个更新合并
```

> ⚠️ **注意这个报错在「图有并行分支」时才会出现**。
> 如果你的图是严格线性的，永远不会遇到——所以第一次见到会很懵。

---

#### 坑 10 Windows 上 `MemorySaver` 在 Jupyter 里反复 compile 丢状态

**症状**：在 Jupyter 里跑，第二次 `invoke` 发现历史没了。

**原因**：每次 `builder.compile()` 都生成新对象，`MemorySaver` 如果也是新建的就丢了。

**修法**：把 `graph` 和 `checkpointer` 存成全局变量，只建一次。

```python
# 在 cell 1 里
CHECKPOINTER = MemorySaver()
GRAPH = build_graph(CHECKPOINTER)

# 后面都用 GRAPH，不要再 compile
```

---

#### 坑 11 Windows 上 PowerShell 看不到子进程输出（本机实测，很容易误判）

**症状**：在 PowerShell 里跑 `python xxx.py`，**什么输出都没有**，也不报错，让你以为脚本没跑或卡住了。

**实测发现**：本机环境下 Python 子进程的 stdout/stderr 都可能被静默吞掉，
`$LASTEXITCODE` 读出来是空的，`| Out-String` 也是空的。

**最坑的是**：`uv venv`、`uv pip install` 这类命令执行失败时**你也看不到报错**。
本指南实测就踩到一次——`uv venv` 建 `.venv` 失败了，但因为没有任何输出，
我以为建好了，后面跑脚本才发现 `python.exe` 根本不存在。

**解法一：让 Python 自己写文件**（最可靠）

```python
# 不要依赖 shell 捕获，自己落盘
from pathlib import Path

result = do_something()
Path("out.txt").write_text(str(result), encoding="utf-8")
```

**解法二：用 `subprocess` 在 Python 里跑，自己收集结果**

本项目的 `run_all.py` 就是这么做的：

```python
import subprocess, sys

proc = subprocess.run(
    [sys.executable, "steps/s1_minimal.py"],
    capture_output=True, text=True, encoding="utf-8",
)
print(proc.returncode, proc.stdout, proc.stderr)
```

**解法三：关键操作必须显式验证结果**

```powershell
# 不要只看命令有没有报错，要检查产物是否真的存在
Test-Path "F:\langgraph-from-zero\.venv\Scripts\python.exe"
```

**一句话教训：在本机环境下，任何"建环境 / 装包 / 跑脚本"的关键操作，
都要用 `Test-Path` 之类的方式验证结果，不能只看命令有没有返回错误。**

---

#### 坑 12 Python 3.12 的转义序列警告

**症状**：

```text
SyntaxWarning: invalid escape sequence '\.'
```

**原因**：docstring 里写了 Windows 路径，反斜杠被当转义序列：

```python
# ❌ 会打警告（\v \S 不是合法转义）
def f():
    """运行：
        .\.venv\Scripts\python.exe xxx.py
    """
```

**解法：docstring 改成 raw string**

```python
# ✅ 加个 r 前缀
def f():
    r"""运行：
        .\.venv\Scripts\python.exe xxx.py
    """
```

**注意**：这是 **Python 3.12 才开始报的**警告。3.11 及以前是静默的，
所以从旧版本升上来的代码会突然冒出一堆这种警告。**不影响运行，但很吵。**

---

#### 坑 13 中文引号嵌套导致 SyntaxError

**症状**：

```text
SyntaxError: invalid syntax. Perhaps you forgot a comma?
```

**原因**：在 `print("...")` 里用了中文全角引号 `"` `"` 包裹内容：

```python
# ❌ 中文引号虽然看着像引号，但 Python 不认，字符串提前结束了
print("第 4 步：演示"有 checkpointer 但不传 thread_id"会报错")

# ✅ 用中文书名号或直角引号代替
print("第 4 步：演示「有 checkpointer 但不传 thread_id」会报错")
```

**这个坑特别阴**：中文引号 `"` `"` 在编辑器里看起来和英文 `"` 几乎一样，
眼睛扫过去找不出来。**写包含中文的字符串时，内层引用一律用「」或『』。**

---

## 第 11 章 工程化：把你的 RAG 迁过来

现在把你 `F:\rag-from-zero` 的 RAG 迁移成一个 LangGraph Agent。

### 11.1 迁移策略：先包一层，不要重写

**最重要的一条建议**：**先原样保留你那些模块，用节点包一层。**

```python
# src/retriever_node.py
from src.config import INDEX_PATH, CHUNK_META_PATH, TOP_K
from src.embedder import Embedder
from src.vector_store import FaissStore


def retrieve_node(state: AgentState) -> dict:
    """把原来的 ask.py 里的检索部分搬过来，原样调用。"""
    embedder = Embedder()
    store = FaissStore(INDEX_PATH, CHUNK_META_PATH).load()
    hits = store.search(embedder.encode_query(state["question"]), k=TOP_K)

    return {
        "found": [m["text"] for _, m in hits],
        "sources": [m["source"] for _, m in hits],
    }
```

**为什么不要一上来就重写**：你的 RAG 已经跑通了，效果你知道。重写等于引入新的不确定性，出问题时分不清是"框架的锅"还是"你改坏了"。

**正确顺序**：

1. 把 `ask.py` 拆成 `retrieve` 节点 + `generate` 节点，**逻辑一个字不改**
2. 跑通，确认结果和原来 `ask.py` 一致
3. 再加分支、加循环、加工具
4. 每加一样，用你的 `eval_set.jsonl` 对比效果

### 11.2 对应关系表

| `rag-from-zero` 里的东西 | 在 LangGraph 里变成 |
| --- | --- |
| `src/retriever.py` 的 `search()` | `retrieve` 节点内部调用 |
| `src/retriever.py` 的 `HybridRetriever` | 同一个节点内部调用，接口不变 |
| `src/reranker.py` 的 `rerank()` | `retrieve` 节点内部调用，或在后面加一个 `rerank` 节点 |
| `ask.py` 的 `build_context()` | `generate` 节点里拼 prompt |
| `src/llm.py` 的 `chat()` | `generate` 节点内调用 |
| `ask.py` 的 `ask()` | 被 `app.py` 的 `graph.invoke()` 替代 |
| `eval.py` | **保留不动**，用来对比迁移前后 |

> ✅ **关键：`eval.py` 和 `eval_set.jsonl` 保留不动。**
> 这是你判断"迁移后有没有变差"的唯一依据，也是 RAG 指南第 8.2 节反复强调的。
> **上了框架之后，你更需要这个数字。**

### 11.3 目标架构：完整 Agent

```
                    ┌─────────────┐
                    │   route     │  意图路由
                    └──────┬──────┘
              ┌────────────┼────────────┐
              ↓            ↓            ↓
        ┌──────────┐  ┌──────────┐  ┌──────────┐
        │law_lookup│  │  hybrid  │  │ graph_qa │
        │条文精确查│  │ 混合检索 │  │ 图谱查询 │
        └─────┬────┘  └─────┬────┘  └─────┬────┘
              │            ↓            │
              │      ┌──────────┐       │
              │      │ rerank   │       │
              │      └─────┬────┘       │
              └────────────┼────────────┘
                           ↓
                    ┌─────────────┐
                    │  generate   │  调 LLM
                    └──────┬──────┘
                           ↓
                    ┌─────────────┐
                    │    guard    │  引用校验 / 拒答
                    └──────┬──────┘
                           ↓
                    ┌─────────────┐
                    │ check_gap   │  依据够不够？
                    └──────┬──────┘
                    够 ↙        ↘ 不够
              ┌──────────┐   ┌──────────┐
              │   END    │   │ 改写查询 │
              └──────────┘   └─────┬────┘
                                   │
                            连回 hybrid（循环）
```

**这张图里的每一块，你都学过了**：

| 模块 | 对应章节 |
| --- | --- |
| `route` 分支 | 第 5 章 |
| `law_lookup` / `hybrid` / `graph_qa` 并行或分支 | 第 5 章 |
| `check_gap` → 改写查询 → 连回检索 | **第 6 章（循环）** |
| `generate` | 第 7 章 |
| `guard` | 自己写，逻辑参考 `D:\tender-agent` |
| 会话历史 | 第 9 章 |
| 人工审核 | 第 9 章 `interrupt_before` |

### 11.4 什么时候该上 LangGraph

**不要因为"框架高级"就迁。** 判断标准：

| 你的需求 | 该不该上 |
| --- | --- |
| 就是线性 RAG，四步走完 | ❌ 手写 50 行更清楚 |
| 要按问题类型走不同检索 | 🟡 可以上，手写 if-else 也行 |
| 检索不到要**换词重试** | ✅ 该上（循环） |
| 要做**多跳推理** | ✅ 该上 |
| 要**人工审核**环节 | ✅ 强烈建议 |
| 要**多轮对话**带上下文 | ✅ 该上（省掉一堆历史管理代码） |
| 只是换个模块（换 embedding） | ❌ 和框架无关 |

### 11.5 评估：迁移后必须对比

```python
# eval_compare.py —— 对比 ask.py 和 agent 的检索命中率
# 复用你 RAG 指南第 8.2 节的 eval_set.jsonl

import json
from src.config import INDEX_PATH, CHUNK_META_PATH
from src.embedder import Embedder
from src.vector_store import FaissStore

embedder = Embedder()
store = FaissStore(INDEX_PATH, CHUNK_META_PATH).load()

cases = [json.loads(l) for l in open("eval_set.jsonl", encoding="utf-8") if l.strip()]

# --- 基线：原来的 ask.py 逻辑 ---
hit_old = 0
for c in cases:
    hits = store.search(embedder.encode_query(c["question"]), k=5)
    if any(m["source"] == c["expect_source"] for _, m in hits):
        hit_old += 1

# --- 新版：走 agent 的检索节点 ---
from agent_nodes import retrieve_node   # 你自己的节点

hit_new = 0
for c in cases:
    out = retrieve_node({"question": c["question"]})
    if c["expect_source"] in out["sources"]:
        hit_new += 1

print(f"迁移前 Hit@5 = {hit_old / len(cases):.1%}")
print(f"迁移后 Hit@5 = {hit_new / len(cases):.1%}")
print(f"差异 = {(hit_new - hit_old) / len(cases):+.1%}")
```

**只有这个数字没变差，迁移才算成功。** 否则说明你迁移过程中改坏了什么。

---

## 第 12 章 学习路线

### 建议的推进节奏

```text
第 3 章   最小图          → 理解 state 怎么流动、节点返回增量
第 4 章   reducer         → ★ 理解"覆盖 vs 累积"，循环场景的命脉
第 5 章   条件边          → 理解分支，学会写路由函数
第 6 章   循环            → ★★ 最重要，理解为什么需要 LangGraph
第 7 章   接 LLM          → 把 RAG 串进来，拿到第一个能用的
第 8 章   工具节点        → 从"写死流程"到"模型自选工具"
第 9 章   持久化 + 中断   → 生产必需的检查点与人工审核
第 11 章  迁移 RAG        → 用评估集验证迁移没变差
```

**和第 4、6 章一样要注意的**：这两章讲的是 LangGraph 独有、其他框架没有的东西。第 3、5、7 章的概念（状态、分支、调模型）其实很通用，学过别的框架也见过。

### 和你 RAG 指南的对应关系

| RAG 指南 | LangGraph 对应 | 衔接点 |
| --- | --- | --- |
| 第 3 章 最小 RAG | 第 3 章 最小图 | 都是"先跑通再优化" |
| 第 4-5 章 解析/切分/建库 | —— | **和编排框架完全无关**，这部分不用动 |
| 第 6 章 接大模型 | 第 7 章 接 LLM | 直接把 `ask.py` 拆成两个节点 |
| 第 7 章 检索优化 | 第 6 章 循环 | "检索不够就再检索"就是循环 |
| 第 8.2 章 评估集 | 第 11.5 节 | **框架换了，评估集照样用** |
| 第 8.3 章 什么时候上框架 | 第 11.4 节 | 判断标准一致 |

### 两面都要记住的话

> **RAG 指南**：RAG 的效果，20% 取决于大模型，80% 取决于你的文档解析、切分和检索策略。

> **本指南**：LangGraph 只解决「流程怎么走」，不解决「每一步做得好不好」。

**这两句话是互补的**：

- 你检索做得再好，如果流程是错的（比如该循环的时候没循环），也答不对；
- 你流程画得再漂亮，如果检索捞不到正确资料，照样是胡说。

**框架是骨架，检索和 prompt 是血肉。别指望骨架能代替血肉。**

---

## 附：文件清单速查

| 文件 | 作用 | 对应章节 |
| --- | --- | --- |
| `check_env.py` | 环境自检（含最小图执行验证） | §2.5 |
| `src/config.py` | 所有配置集中在这 | §7.3 |
| `src/llm.py` | LLM 客户端封装 | §7.3 |
| `src/tools.py` | ★ 工具定义（docstring 就是模型的使用说明书） | §8.2 |
| `src/state.py` | ★ State 定义（所有图的共享状态） | §4.4 |
| `steps/s1_minimal.py` | 里程碑 1：最小图 | 第 3 章 |
| `steps/s2_state.py` | 里程碑 2：reducer | 第 4 章 |
| `steps/s3_branch.py` | 里程碑 3：分支 | 第 5 章 |
| `steps/s4_loop.py` | 里程碑 4：循环 | 第 6 章 |
| `steps/s5_llm.py` | 里程碑 5：接大模型 | 第 7 章 |
| `steps/s6_tools.py` | 里程碑 6：工具调用 | 第 8 章 |
| `steps/s7_persist.py` | 里程碑 7：持久化 + 人在回路 | 第 9 章 |
| `app.py` | 最终完整 Agent 入口 | 第 11 章 |
| `eval_compare.py` | 迁移前后效果对比 | §11.5 |
| `storage/checkpoints.db` | SQLite 检查点（自动生成） | §9.4 |

---

## 附：API 速查表

```python
# ---------- 导入 ----------
from langgraph.graph import StateGraph, START, END, MessagesState
from langgraph.prebuilt import ToolNode, tools_condition
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
# --- 以下两个需要额外装：uv pip install langgraph-checkpoint-postgres "psycopg[binary,pool]" ---
from langgraph.checkpoint.postgres import PostgresSaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.types import Send
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import tool
from typing import Annotated, TypedDict, Literal
from operator import add

# ---------- 建图 ----------
builder = StateGraph(State)                          # 定义图
builder.add_node("name", func)                       # 加节点
builder.add_node("name", func, retry_policy=...)      # 带重试
builder.add_edge(START, "first")                     # 固定边
builder.add_edge("last", END)                        # 连到出口
builder.add_conditional_edges("from", router, {...}) # 条件边
builder.add_conditional_edges(START, router)         # 从入口分叉
graph = builder.compile()                            # 编译
graph = builder.compile(checkpointer=cp)             # 带检查点
graph = builder.compile(
    checkpointer=cp,
    interrupt_before=["node"],                       # 执行前暂停
    interrupt_after=["node"],                        # 执行后暂停
)

# ---------- 执行 ----------
graph.invoke(inputs)                                 # 跑，返回最终 state
graph.invoke(inputs, config)                         # 带配置
graph.invoke(None, config)                           # 从暂停处继续
graph.stream(inputs, stream_mode="updates")          # 流式
graph.stream(inputs, stream_mode=["updates", "messages"])

# ---------- 状态操作 ----------
snap = graph.get_state(config)                       # 当前状态
snap.values                                          # state 内容
snap.next                                            # 下一步节点名
for s in graph.get_state_history(config): ...        # 历史检查点
graph.update_state(config, {"field": val}, as_node="x")  # 打补丁
graph.get_graph().draw_mermaid()                     # 可视化

# ---------- 配置 ----------
config = {
    "configurable": {"thread_id": "user-1"},         # 会话 ID（有 cp 时必填）
    "recursion_limit": 25,                           # 最大步数
}
```

---

## 附：State 字段设计速查

| 字段性质 | 写法 | 例子 |
| --- | --- | --- |
| 只关心最新值 | `name: str` | 当前问题、当前答案、计数器、意图 |
| 要累积（去重） | `name: Annotated[list[str], add]` | 检索结果、日志、引用来源 |
| 要累积（消息） | `name: Annotated[list, add_messages]` | 对话历史 |
| 要合并字典 | `name: Annotated[dict, lambda a, b: {**(a or {}), **(b or {})}]` | 累积的中间结果 |
| 要最大值 | `name: Annotated[float, max]` | 追踪最高分 |

**判断口诀**：**这个字段在循环里被更新两次，第一次的值还有用吗？有用 → 加 reducer；没用 → 保持默认。**
