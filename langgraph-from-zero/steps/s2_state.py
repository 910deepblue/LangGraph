r"""里程碑 2：State 的归并策略（reducer）。

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
    # 想累积，但因为没有 reducer，上一轮的内容会被整个替换掉
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


# ============================================================
# 实验 C：混用 —— 这是真实 Agent 的 State 长相
# ============================================================
class AgentState(TypedDict):
    # --- 每次覆盖：当前问题、当前答案 ---
    question: str                              # 只关心最新的一次提问
    answer: str                                # 只关心最新的一版答案

    # --- 每次累积：历史记录、检索结果 ---
    found: Annotated[list[str], add]           # 检索到的片段，每轮都要留
    sources: Annotated[list[str], add]         # 引用来源，用于溯源


if __name__ == "__main__":
    print("=" * 62)
    print("实验 A：没有 reducer（默认覆盖）")
    print("=" * 62)
    r1 = g1.invoke({"n": 0, "log": []})
    print(f"跑了 3 轮，log 里只剩: {r1['log']}")
    print(f"→ 预期 3 条，实际 {len(r1['log'])} 条。前两轮的记录被冲掉了！")

    print("\n" + "=" * 62)
    print("实验 B：有 reducer（累加）")
    print("=" * 62)
    r2 = g2.invoke({"n": 0, "log": []})
    print(f"跑了 3 轮，log 里有: {r2['log']}")
    print(f"→ 预期 3 条，实际 {len(r2['log'])} 条。每轮都记下来了。")

    print("\n" + "=" * 62)
    print("实验 C：真实 Agent 的 State 长相（这里只演示定义）")
    print("=" * 62)
    print("question / answer  -> 覆盖（只关心最新值）")
    print("found / sources    -> Annotated + add（累积全过程）")
    print("\n判断口诀：这个字段在循环里被更新两次，第一次的值还有用吗？")
    print("          有用 -> 加 reducer；没用 -> 保持默认。")
