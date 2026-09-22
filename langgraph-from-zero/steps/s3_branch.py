r"""里程碑 3：条件边（分支）。

本章你会看到：
  1. 怎么从 START 直接分叉（写法 A，推荐）
  2. 怎么用一个"路由节点"做中间层（写法 B）
  3. 条件边的进阶用法：省略映射字典 / 返回列表并行

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

    重要：路由函数只做判断，不要在这里改 state 或调 API。
    """
    q = state["question"]

    # 1) 关系型问题优先判定
    #    必须在条文编号之前：像「第三十四条引用了哪些条款」这种问题
    #    同时命中条文号和关系词，但真正想问的是关系，不是条文原文。
    if any(w in q for w in ["引用", "关联", "相关条款", "有哪些关系"]):
        return "law_lookup"

    # 2) 出现条文编号 -> 精确查询
    if re.search(r"第\s*[零一二三四五六七八九十百千0-9]+\s*条", q):
        return "law_lookup"

    # 3) 短句 + 问候词 -> 闲聊
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

    print("=" * 62)
    print("写法 A：直接从 START 分叉")
    print("=" * 62)
    for q in test_questions:
        r = graph.invoke({"question": q, "intent": "", "answer": ""})
        print(f"\n问题: {q}")
        print(f"意图: {r['intent']}")
        print(f"回答: {r['answer']}")

    print("\n" + "=" * 62)
    print("图结构（Mermaid）")
    print("=" * 62)
    print(graph.get_graph().draw_mermaid())
