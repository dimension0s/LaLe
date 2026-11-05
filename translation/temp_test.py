"""测试模型提示词的暂时脚本"""

from translation.models_config import get_translation_config
from translation.prompts.direct_prompt import DIRECT_SYSTEM_PROMPT, DIRECT_PROMPT_TEMPLATE

import requests

config = get_translation_config()
prompt = DIRECT_PROMPT_TEMPLATE.format(
    source_lang="英语",
    target_lang="中文",
    text="It is reasonable to assume that the economy will continue to improve.",
)

response = requests.post(
    f"{config.base_url}/chat/completions",
    headers={"Authorization": f"Bearer {config.api_key}"},
    json={
        "model": config.model_name,
        "messages": [
            {"role": "system", "content": DIRECT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "response_format": {"type": "json_object"},
    },
)

print(response.json()["choices"][0]["message"]["content"])