"""
models_config.py - 术语识别模块的模型配置
路径: /home/bina/LaLe/terminology/models_config.py

职责:
- 术语识别用的模型配置
- 复用 DeepSeek
"""

import os
from dataclasses import dataclass
from typing import Optional
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录 .env
PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# ============================================================
# 术语识别模型配置
# ============================================================
@dataclass
class TerminologyModelConfig:
    """术语识别模型配置"""
    model_name: str = "deepseek-chat"
    api_key: Optional[str] = None
    base_url: str = "https://api.deepseek.com/v1"
    max_tokens: int = 4096
    temperature: float = 0.2      # 术语识别用较低温度（更稳定）
    timeout: int = 90
    max_retries: int = 3

    def __post_init__(self):
        if not self.api_key:
            self.api_key = os.getenv("DEEPSEEK_API_KEY")

    def to_dict(self) -> dict:
        return {
            "model": self.model_name,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }


# ============================================================
# 默认实例
# ============================================================
DEFAULT_TERMINOLOGY_CONFIG = TerminologyModelConfig()


def get_terminology_config() -> TerminologyModelConfig:
    """获取术语识别模型配置"""
    return DEFAULT_TERMINOLOGY_CONFIG