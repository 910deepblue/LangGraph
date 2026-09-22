r"""里程碑 1：最小可运行图。

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
