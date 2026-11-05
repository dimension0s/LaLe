"""
models_config.py - 翻译模块的模型配置
复用 RAG 模块的 DeepSeek 配置，专注翻译任务
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
# 翻译模型配置（DeepSeek）
# ============================================================
@dataclass
class TranslationModelConfig:
    """翻译模型配置"""
    model_name: str = "deepseek-chat"
    api_key: Optional[str] = None
    base_url: str = "https://api.deepseek.com/v1"
    max_tokens: int = 4096
    temperature: float = 0.3      # 翻译任务用较低温度
    timeout: int = 90             # 翻译可能较慢
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
DEFAULT_TRANSLATION_CONFIG = TranslationModelConfig()


def get_translation_config() -> TranslationModelConfig:
    """获取翻译模型配置"""
    return DEFAULT_TRANSLATION_CONFIG