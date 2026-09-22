"""工具定义。

设计要点：用 @tool 装饰器，函数名即工具名，docstring 即工具描述。
模型是靠 docstring 判断该不该调这个工具的，所以描述必须写清楚。
"""

from langchain_core.tools import tool


@tool
def search_law(article: str) -> str:
    """根据条文编号精确查询《招标投标法实施条例》原文。

    适用场景：用户明确提到了条文编号，例如"第三十四条"、"第26条"。
    不适用：用户问"是什么意思"、"怎么理解"这类理解型问题，请改用 search_knowledge。

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
        "第三十七条": "招标人应当在资格预审公告、招标公告或者投标邀请书中载明是否接受联合体投标。",
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
