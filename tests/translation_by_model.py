"""调用模型翻译测试"""

import sys
from pathlib import Path
# 添加 translation_rag 目录到 Python 路径
translation_dir = Path("/home/bina/LaLe/tools/translation_rag")
sys.path.insert(0, str(translation_dir))
from translate_by_model import translate

text_a = "On economic policy alone,the president has used tariffs to usurp Congress’staxing powers and launched attack after attack on the independence of the Federal Reserve, which he accuses of keeping interest rates too high."
text_b = "Damp squib or cunning retreat"
text_c = "damp squib"
result = translate(text_b,source_lang="英语", target_lang="中文")

print("翻译结果：")
print(result)














