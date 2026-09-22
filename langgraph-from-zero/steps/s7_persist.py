r"""里程碑 7：持久化与人在回路。

本章你会看到：
  1. MemorySaver 怎么用，thread_id 为什么必须有
  2. 多轮会话怎么自动带上历史
  3. interrupt_before 怎么实现"人工审核后再继续"
  4. 时间旅行：从任意历史检查点重新跑

运行：
    .\.venv\Scripts\python.exe steps\s7_persist.py
"""

import sys
from operator import add
from pathlib import Path
from typing import Annotated, TypedDict

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.checkpoint.memory import MemorySaver   # noqa: E402
from langgraph.graph import StateGraph, START, END   # noqa: E402


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
        # 关键：在 finalize 之前暂停，等人确认
        interrupt_before=["finalize"],
    )


if __name__ == "__main__":
    checkpointer = MemorySaver()
    graph = build_graph(checkpointer)

    # thread_id 是会话标识，同一个 thread_id 的历史会累积
    config = {"configurable": {"thread_id": "user-001"}}

    print("=" * 62)
    print("第 1 步：跑图，会停在 finalize 之前")
    print("=" * 62)
    graph.invoke({"question": "投标保证金有什么要求", "log": []}, config)

    # 查看当前停在哪
    snapshot = graph.get_state(config)
    print(f"当前状态: {snapshot.values}")
    print(f"下一步要执行: {snapshot.next}")     # 应该是 ('finalize',)
    print("-> 图已暂停，等待人工审核")

    print("\n" + "=" * 62)
    print("第 2 步：人工确认后继续（传 None 表示继续上次）")
    print("=" * 62)
    graph.invoke(None, config)

    final = graph.get_state(config)
    print(f"最终状态:\n{final.values['approved']}")
    print(f"\n执行轨迹: {final.values['log']}")

    print("\n" + "=" * 62)
    print("第 3 步：查看历史检查点（时间旅行）")
    print("=" * 62)
    history = list(graph.get_state_history(config))
    print(f"共记录了 {len(history)} 个检查点:")
    for i, h in enumerate(reversed(history)):
        nxt = h.next if h.next else ("（结束）",)
        print(f"  [{i}] next={nxt}  log={h.values.get('log', [])}")

    # ------------------------------------------------------------
    print("\n" + "=" * 62)
    print("第 4 步：演示「有 checkpointer 但不传 thread_id」会报错")
    print("=" * 62)
    try:
        graph.invoke({"question": "test", "log": []}, {})
    except Exception as e:
        print(f"果然报错: {type(e).__name__}")
        print(f"  {str(e)[:200]}")
        print("-> 所以有 checkpointer 时，config 里必须有 thread_id")
