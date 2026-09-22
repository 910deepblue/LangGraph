r"""里程碑 5：把 LLM 接进图。

本章你会看到：
  1. LLM 调用就是个普通节点，没有任何特殊之处
  2. prompt 怎么放（RAG 指南第 7.1 节的约束在这里同样适用）
  3. 怎么把调用封装成节点，让结构保持清晰

运行（需要先在 .env 里配好 key）：
    .\.venv\Scripts\python.exe steps\s5_llm.py
"""

import sys
from operator import add
from pathlib import Path
from typing import Annotated, TypedDict

# 让脚本能 import src/ 里的模块
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from langgraph.graph import StateGraph, START, END   # noqa: E402

from src.config import MODEL_NAME, OPENAI_API_KEY     # noqa: E402
from src.llm import chat                              # noqa: E402


# ============================================================
# prompt 模板：和 RAG 指南里的写法保持一致
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
    """把检索结果拼进 prompt，调模型。

    没配 API key 时会走降级路径，用拼接代替模型输出，
    这样你依然能看清"检索 -> 拼 prompt -> 生成"这条链路怎么走。
    """
    # 每条资料编号，让模型能引用 [1] [2]
    context = "\n\n".join(
        f"[{i}] {text}" for i, text in enumerate(state["context"], start=1)
    )

    prompt = USER_TEMPLATE.format(context=context, question=state["question"])

    if not OPENAI_API_KEY:
        # 降级：不调模型，直接回显拼好的 prompt 结构
        sep = "-" * 40
        answer = (
            "【降级模式】未配置 OPENAI_API_KEY，这里本应是模型的输出。\n"
            "下面是实际会发给模型的完整 prompt，你可以看到结构：\n"
            f"{sep}\n"
            f"system: {SYSTEM_PROMPT.splitlines()[0]}\n"
            f"{sep}\n"
            f"user:\n{prompt}"
        )
        return {"answer": answer, "steps": ["[降级] 未配 key，回显 prompt 结构"]}

    answer = chat([
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt},
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

    mode = f"真实 LLM ({MODEL_NAME})" if OPENAI_API_KEY else "降级模式（未配 OPENAI_API_KEY）"
    print(f"模式：{mode}")

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
