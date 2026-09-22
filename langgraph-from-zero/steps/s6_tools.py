r"""里程碑 6：工具调用（ReAct Agent）。

本章你会看到：
  1. 用 @tool 定义工具，把工具绑定到模型
  2. ToolNode 和 tools_condition 这两个官方预制件
  3. 经典的 agent <-> tools 循环
  4. 为什么必须自己加防死循环

运行（需要先在 .env 里配好 key）：
    .\.venv\Scripts\python.exe steps\s6_tools.py

注意：本脚本自带一个"假模型"降级模式。如果没配 API key，
会自动用规则模拟模型选择工具，让你依然能看清整条链路怎么跑。
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage  # noqa: E402
from langgraph.graph import StateGraph, MessagesState, START, END  # noqa: E402
from langgraph.prebuilt import ToolNode, tools_condition  # noqa: E402

from src.config import MAX_ITERATIONS, MODEL_NAME, OPENAI_API_KEY, TEMPERATURE  # noqa: E402
from src.tools import ALL_TOOLS  # noqa: E402


SYSTEM_PROMPT = """你是一个招标投标合规助手。

你可以调用工具来查询信息：
  - 用户提到具体条文编号时，用 search_law
  - 用户问理解型问题时，用 search_knowledge
  - 用户问你能做什么时，用 list_my_tools

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

    def __init__(self) -> None:
        from src.llm import get_client

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
        """接收 LangChain 消息列表，返回 LangChain AIMessage。"""
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
            tool_calls.append({
                "name": tc.function.name,
                "args": json.loads(tc.function.arguments),
                "id": tc.id,
            })

        return AIMessage(content=msg.content or "", tool_calls=tool_calls)


class FakeLLM:
    """降级用的假模型：用规则模拟"模型决定调什么工具"。

    没配 API key 时用它，这样你依然能看清 ReAct 循环怎么转。
    它只做最简单的关键词判断，真实模型比这聪明得多。
    """

    def invoke(self, messages):
        last_human = ""
        for m in reversed(messages):
            if m.type == "human":
                last_human = m.content or ""
                break

        # 已经有工具返回结果了 -> 直接总结，不再调工具（循环的出口）
        if any(m.type == "tool" for m in messages):
            tool_msgs = [m.content for m in messages if m.type == "tool"]
            return AIMessage(
                content="（假模型总结）根据工具返回的资料：\n" + "\n".join(tool_msgs)
            )

        # 还没调过工具 -> 按关键词决定调哪个
        import re

        m = re.search(r"第\s*[零一二三四五六七八九十百千0-9]+\s*条", last_human)
        if m:
            return AIMessage(
                content="",
                tool_calls=[{
                    "name": "search_law",
                    "args": {"article": m.group(0)},
                    "id": "fake-1",
                }],
            )
        if "做什么" in last_human or "功能" in last_human:
            return AIMessage(
                content="",
                tool_calls=[{"name": "list_my_tools", "args": {}, "id": "fake-2"}],
            )
        return AIMessage(
            content="",
            tool_calls=[{
                "name": "search_knowledge",
                "args": {"query": last_human},
                "id": "fake-3",
            }],
        )


# ============================================================
# agent 节点
# ============================================================
USE_REAL_LLM = bool(OPENAI_API_KEY)
llm = BoundLLM() if USE_REAL_LLM else FakeLLM()


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

    # 关键：工具执行完回到 agent，形成 ReAct 循环
    b.add_edge("tools", "agent")

    return b


if __name__ == "__main__":
    graph = build_graph().compile()

    print(f"模式: {'真实 LLM (' + MODEL_NAME + ')' if USE_REAL_LLM else '假模型（未配 OPENAI_API_KEY）'}")

    questions = [
        "第三十四条是什么内容？",          # 应该调 search_law
        "投标保证金有什么要求？",          # 应该调 search_knowledge
        "你能做什么？",                    # 应该调 list_my_tools
    ]

    for q in questions:
        print("\n" + "=" * 62)
        print(f"问题：{q}")
        print("=" * 62)

        result = graph.invoke(
            {
                "messages": [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=q),
                ]
            },
            # 防死循环：超过这个步数直接抛错，不无限转
            config={"recursion_limit": MAX_ITERATIONS * 2 + 2},
        )

        # 打印执行轨迹：模型调了什么工具
        print("执行轨迹:")
        for m in result["messages"]:
            if getattr(m, "tool_calls", None):
                for tc in m.tool_calls:
                    print(f"  -> 调用工具 {tc['name']}({tc['args']})")
            if m.type == "tool":
                preview = (m.content or "")[:80].replace("\n", " ")
                print(f"  <- 工具返回: {preview}...")

        print(f"\n最终回答:\n{result['messages'][-1].content}")
