"""
prompts 子包
路径: /home/bina/LaLe/translation_traces/prompts/__init__.py
"""

from .direct_prompt import DIRECT_SYSTEM_PROMPT, DIRECT_PROMPT_TEMPLATE
from .indirect_prompt import INDIRECT_SYSTEM_PROMPT, INDIRECT_PROMPT_TEMPLATE

__all__ = [
    "DIRECT_SYSTEM_PROMPT",
    "DIRECT_PROMPT_TEMPLATE",
    "INDIRECT_SYSTEM_PROMPT",
    "INDIRECT_PROMPT_TEMPLATE",
]