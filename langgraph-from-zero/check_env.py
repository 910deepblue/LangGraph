r"""环境自检：确认 LangGraph 能正常导入、版本正确。

为什么必须有这个脚本：`uv pip install` 输出 `Checked N packages` 不代表包能用，
只有 import 成功才算数（RAG 指南坑 0 的教训）。

运行：
    .\.venv\Scripts\python.exe check_env.py
"""

import sys

print("Python:", sys.version.split()[0])

# --- 核心导入：这三块能跑通，环境就没问题 ---
try:
    from langgraph.graph import StateGraph, START, END
    print("langgraph.graph 导入成功")
except Exception as e:
    print(f"[FAIL] langgraph 导入失败: {e}")
    sys.exit(1)

try:
    from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
    print("langchain_core.messages 导入成功")
except Exception as e:
    print(f"[FAIL] langchain-core 导入失败: {e}")
    sys.exit(1)

try:
    from langgraph.checkpoint.memory import MemorySaver
    print("langgraph.checkpoint.memory 导入成功")
except Exception as e:
    print(f"[FAIL] checkpointer 导入失败: {e}")
    sys.exit(1)

try:
    from langgraph.prebuilt import ToolNode, tools_condition
    print("langgraph.prebuilt 导入成功")
except Exception as e:
    print(f"[FAIL] prebuilt 导入失败: {e}")
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
print(f"\n[OK] 最小图执行成功: 41 -> {out['n']}")

# --- 再验证 reducer 是否生效（第 4 章的核心机制）---
from operator import add
from typing import Annotated


class Acc(TypedDict):
    total: Annotated[int, add]


b2 = StateGraph(Acc)
b2.add_node("a", lambda s: {"total": 1})
b2.add_node("b", lambda s: {"total": 2})
b2.add_edge(START, "a")
b2.add_edge("a", "b")
b2.add_edge("b", END)
out2 = b2.compile().invoke({"total": 0})
assert out2["total"] == 3, f"reducer 没生效: {out2}"
print(f"[OK] reducer 执行成功: 0 + 1 + 2 = {out2['total']}")

print("\n环境自检全部通过。可以开始第 3 章了。")
