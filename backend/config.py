"""
全局配置管理（通义千问）
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 项目根目录
BASE_DIR = Path(__file__).resolve().parent.parent

# ================================
# 通义千问 API 配置
# ================================

DASHSCOPE_API_KEY: str = os.getenv("DASHSCOPE_API_KEY", "")

# ================================
# 模型配置
# ================================

LLM_MODEL: str = os.getenv("LLM_MODEL", "qwen-max")
VISION_MODEL: str = os.getenv("VISION_MODEL", "qwen-vl-max")
LLM_TEMPERATURE: float = float(os.getenv("LLM_TEMPERATURE", "0.7"))
MAX_TOKENS: int = int(os.getenv("MAX_TOKENS", "4096"))

# ================================
# 应用配置
# ================================

PORT: int = int(os.getenv("PORT", "8501"))
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")

# ================================
# 数据目录配置
# ================================

DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_BASE_PATH = DATA_DIR / "knowledge"
FAISS_INDEX_DIR = DATA_DIR / "faiss_index"
UPLOADS_DIR = DATA_DIR / "uploads"
LOGS_DIR = BASE_DIR / "logs"
TRACE_DB_PATH = DATA_DIR / "app.db"

# ================================
# 向量检索配置
# ================================

TOP_K_RETRIEVAL: int = int(os.getenv("TOP_K_RETRIEVAL", "5"))


# 创建必要的目录
def ensure_directories():
    """确保所有必要的目录存在"""
    for directory in [DATA_DIR, KNOWLEDGE_BASE_PATH, FAISS_INDEX_DIR, UPLOADS_DIR, LOGS_DIR]:
        directory.mkdir(parents=True, exist_ok=True)

ensure_directories()


def get_api_key() -> str:
    """获取通义千问 API Key"""
    return DASHSCOPE_API_KEY


def validate_config() -> bool:
    """验证配置是否有效"""
    api_key = get_api_key()

    if not api_key or api_key.startswith("your_"):
        raise ValueError(
            "[错误] 未找到 DASHSCOPE_API_KEY!\n"
            "请在 .env 文件中设置你的通义千问 API Key。\n"
            "获取地址: https://dashscope.console.aliyun.com/\n"
            "[提示] 通义千问国内访问稳定，新用户有免费额度！"
        )

    return True


if __name__ == "__main__":
    try:
        validate_config()
        print("[OK] 配置验证通过!")
        print(f"   数据目录: {DATA_DIR}")
        print(f"   使用模型: {LLM_MODEL}")
    except ValueError as e:
        print(e)
