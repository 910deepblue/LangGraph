# LangGraph 从 0 到 1

配套教程：**[LangGraph从0到1搭建指南.md](./LangGraph从0到1搭建指南.md)**

这份指南面向「已经会一点 Python、做过 RAG、想搞明白 Agent 编排框架」的人。
讲法沿用同目录的 `F:\rag-from-zero\RAG从0到1搭建指南.md`：
先给结论再解释、标注真实踩过的坑、每个里程碑配可独立运行的脚本。

---

## 快速开始

```powershell
cd F:\langgraph-from-zero

# 1. 环境（uv，Python 3.12）
$env:UV_CACHE_DIR = "D:\DevEnv\uv\cache"
D:\DevEnv\uv\bin\uv.exe venv --python 3.12

# 2. 依赖
D:\DevEnv\uv\bin\uv.exe pip install -r requirements.txt `
  -i https://pypi.tuna.tsinghua.edu.cn/simple `
  -p "F:\langgraph-from-zero\.venv\Scripts\python.exe"

# 3. 配置（第 7 章起需要 API key）
copy .env.example .env
# 编辑 .env，填 OPENAI_API_KEY

# 4. 环境自检
.\.venv\Scripts\python.exe check_env.py

# 5. 逐个跑里程碑
.\.venv\Scripts\python.exe steps\s1_minimal.py
.\.venv\Scripts\python.exe steps\s2_state.py
.\.venv\Scripts\python.exe steps\s3_branch.py
.\.venv\Scripts\python.exe steps\s4_loop.py
.\.venv\Scripts\python.exe steps\s5_llm.py      # 需要 key
.\.venv\Scripts\python.exe steps\s6_tools.py    # 需要 key（没配会走降级）
.\.venv\Scripts\python.exe steps\s7_persist.py

# 6. 一次跑完全部，结果汇总到 _verify_report.txt
.\.venv\Scripts\python.exe run_all.py
```

---

## 七个里程碑

| 脚本 | 学到什么 | 对应章节 |
| --- | --- | --- |
| `steps/s1_minimal.py` | State / Node / Edge 三个概念，节点返回"增量" | 第 3 章 |
| `steps/s2_state.py` | ★ reducer：为什么循环里不加 `Annotated` 会丢数据 | 第 4 章 |
| `steps/s3_branch.py` | 条件边、路由函数、两种分叉写法 | 第 5 章 |
| `steps/s4_loop.py` | ★★ 循环：把条件边连回自己 + 防死循环 | 第 6 章 |
| `steps/s5_llm.py` | 把 LLM 调用封成节点，接上 RAG 的两段式 | 第 7 章 |
| `steps/s6_tools.py` | ReAct 循环：`agent ↔ tools`，`ToolNode` 预制件 | 第 8 章 |
| `steps/s7_persist.py` | 检查点、`thread_id`、人工审核中断、时间旅行 | 第 9 章 |

---

## 三个必须记住的点

**1. 节点返回「增量」，不修改 state。**

```python
# ❌ 原地改，LangGraph 看不到
def bad(state):
    state["answer"] = "x"

# ✅ 返回增量字典
def good(state):
    return {"answer": "x"}
```

**2. 循环里要累积的字段必须加 reducer。**

```python
class State(TypedDict):
    found: Annotated[list[str], add]   # 不加 add，每轮都会覆盖上一轮
```

**3. 有 checkpointer 就必须传 `thread_id`。**

```python
config = {"configurable": {"thread_id": "user-1"}}
graph.invoke(state, config)
```

---

## 和 RAG 项目的衔接

第 11 章讲怎么把 `F:\rag-from-zero` 迁过来。核心建议：

- **先包一层，不要重写**——把 `ask.py` 拆成 `retrieve` 节点 + `generate` 节点，逻辑一字不改
- **`eval_set.jsonl` 和 `eval.py` 保留不动**，用来对比迁移前后效果
- **先确认 Hit@5 没变差，再加分支和循环**

---

## 本机环境说明

| 项 | 值 |
| --- | --- |
| 位置 | `F:\langgraph-from-zero` |
| 虚拟环境 | `.venv`，Python 3.12.7（uv 管理） |
| langgraph | 1.2.11 |
| uv | `D:\DevEnv\uv\bin\uv.exe` 0.12.12 |
| uv 缓存 | `D:\DevEnv\uv\cache`（别落到 C 盘） |

**注意**：本指南统一按 LangGraph **1.x** 写。网上大量教程是 0.1~0.2 时代的，
用 `set_entry_point` / `set_finish_point` / `MessageGraph` 这些 API ——
**那些在 1.x 里已移除，照抄会报错**。具体对照表见指南开头「版本差异提示」。
