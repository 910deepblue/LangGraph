"""大模型客户端封装。

设计要点：只暴露 get_client() 和 chat() 两个入口。
这样以后要换 provider（DeepSeek -> 通义 -> 本地 LoRA），
只改这个文件，节点代码一行不用动。
"""

from functools import lru_cache

from openai import OpenAI

from src.config import (
    MAX_TOKENS,
    MODEL_NAME,
    OPENAI_API_KEY,
    OPENAI_BASE_URL,
    TEMPERATURE,
)


# 全局单例：OpenAI 客户端内部维护连接池，重复创建会浪费资源
@lru_cache(maxsize=1)
def get_client() -> OpenAI:
    if not OPENAI_API_KEY:
        raise RuntimeError(
            "OPENAI_API_KEY 未设置。请在 .env 里配置，或检查 .env 是否被正确加载。"
        )
    return OpenAI(api_key=OPENAI_API_KEY, base_url=OPENAI_BASE_URL)


def chat(messages: list[dict], temperature: float | None = None) -> str:
    """调用大模型，返回文本。

    Args:
        messages: OpenAI 格式的消息列表，形如
                  [{"role": "system", "content": "..."},
                   {"role": "user", "content": "..."}]
        temperature: 不传则用配置里的默认值

    Returns:
        模型生成的文本
    """
    resp = get_client().chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        temperature=TEMPERATURE if temperature is None else temperature,
        max_tokens=MAX_TOKENS,
    )
    return resp.choices[0].message.content or ""
