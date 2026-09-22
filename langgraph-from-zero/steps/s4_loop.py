r"""里程碑 4：循环（LangGraph 的核心价值）。

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

# 最多试几次。这个数字必须显式写出来，不能靠框架兜底。
MAX_ATTEMPTS = 3


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
        "steps": [f"第 {attempt + 1} 轮：关键词「{keyword}」-> 命中 {len(hits)} 条"],
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
def should_continue(state: State) -> Literal["retrieve", "generate"]:
    """循环的出口条件。

    这里是全章最关键的地方：
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

    # 核心：条件边，retrieve 可能回到自己
    b.add_conditional_edges("retrieve", should_continue, {
        "retrieve": "retrieve",     # <- 这一行就是"循环"
        "generate": "generate",     # <- 这一行是"出口"
    })

    b.add_edge("generate", END)
    return b


if __name__ == "__main__":
    graph = build_graph().compile()

    print("=" * 62)
    print("场景 1：第一轮就检索到（应该只循环 1 次）")
    print("=" * 62)
    r = graph.invoke({"question": "保证金怎么算", "found": [], "steps": [], "attempts": 0})
    print("\n".join(f"  · {s}" for s in r["steps"]))
    print(f"\n答案: {r['answer']}")
    print(f"\n注意 found 累积了 {len(r['found'])} 条，steps 记了 {len(r['steps'])} 步")

    print("\n" + "=" * 62)
    print("场景 2：永远检索不到（应该循环 MAX_ATTEMPTS 次后放弃）")
    print("=" * 62)

    # 临时把 KB 清空，模拟"怎么都检索不到"
    KB.clear()
    r2 = graph.invoke({"question": "不存在的问题", "found": [], "steps": [], "attempts": 0})
    print("\n".join(f"  · {s}" for s in r2["steps"]))
    print(f"\n答案: {r2['answer']}")
    print(f"\n-> 循环了 {r2['attempts']} 次后放弃，没有死循环")

    print("\n" + "=" * 62)
    print("图结构（Mermaid）—— 注意 retrieve 上的自环")
    print("=" * 62)
    print(graph.get_graph().draw_mermaid())
