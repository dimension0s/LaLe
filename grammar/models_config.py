"""
models_config.py - 语法解析模块的模型配置
路径: /home/bina/LaLe/grammar/models_config.py

职责:
- 语法解析用的模型配置
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
# 语法解析模型配置
# ============================================================
@dataclass
class GrammarModelConfig:
    """语法解析模型配置"""
    model_name: str = "deepseek-chat"
    api_key: Optional[str] = None
    base_url: str = "https://api.deepseek.com/v1"
    max_tokens: int = 4096
    temperature: float = 0.2      # 语法分析用较低温度（更稳定）
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
DEFAULT_GRAMMAR_CONFIG = GrammarModelConfig()


def get_grammar_config() -> GrammarModelConfig:
    """获取语法解析模型配置"""
    return DEFAULT_GRAMMAR_CONFIG