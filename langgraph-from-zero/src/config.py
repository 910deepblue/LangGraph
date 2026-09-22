"""所有配置集中在这一个文件。

为什么这么做：等你开始调 temperature、调 top_k 的时候会感谢自己。
分散在各处的话，改一个参数要全文搜索。
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# load_dotenv 默认【不覆盖】已存在的系统环境变量。
# 这是好事：系统级配置优先，避免 .env 意外覆盖掉全局设置。
# 但要注意：如果你在 .env 里写了 HF_HOME 这种系统已有的变量，它不会生效。
load_dotenv()

ROOT = Path(__file__).resolve().parent.parent
STORAGE_DIR = ROOT / "storage"
CHECKPOINT_DB = STORAGE_DIR / "checkpoints.db"

# --- LLM ---
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.deepseek.com/v1")
MODEL_NAME = os.getenv("MODEL_NAME", "deepseek-chat")

# --- 生成参数 ---
# 问答场景要稳，温度调低。这是从 RAG 指南第 7.1 节来的经验。
TEMPERATURE = float(os.getenv("TEMPERATURE", "0.2"))
MAX_TOKENS = int(os.getenv("MAX_TOKENS", "1024"))

# --- Agent 行为 ---
# 最多循环几轮（防死循环，见第 6.3 节）
MAX_ITERATIONS = int(os.getenv("MAX_ITERATIONS", "6"))
# 是否打印每步 trace
VERBOSE = os.getenv("VERBOSE", "true").lower() == "true"
