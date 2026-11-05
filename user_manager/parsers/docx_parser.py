"""
docx_parser.py - DOC / DOCX 解析器
路径: /home/bina/LaLe/user_manager/parsers/docx_parser.py
"""

from pathlib import Path
from typing import Dict

from loguru import logger

from user_manager.parsers.base import BaseParser, save_parsed_json


class DocxParser(BaseParser):
    """DOC / DOCX 解析器"""

    def parse(self, file_path: str) -> Dict:
        """解析 DOC / DOCX"""
        # 判断类型
        suffix = Path(file_path).suffix.lower()
        if suffix == ".doc":
            self.file_type = "doc"
        else:
            self.file_type = "docx"

        # 只构造基础信息
        info = self._build_base_info(file_path)

        logger.info(f"DOCX 解析完成: {info['file_name']}")
        return info


# ============================================================
# 便捷函数
# ============================================================
def parse_docx(file_path: str, save_json: bool = True) -> Dict:
    """解析 DOC / DOCX 并可选保存 JSON"""
    parser = DocxParser()
    result = parser.parse(file_path)
    if save_json:
        save_parsed_json(result)
    return result


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    FILE_PATH = "/mnt/e/英语/test.docx"   # ← 改成你的 DOCX 路径
    SAVE_JSON = True
    # ================================================

    print("=" * 60)
    print("DOCX 解析测试")
    print("=" * 60)
    print(f"文件: {FILE_PATH}")
    print("=" * 60)

    result = parse_docx(FILE_PATH, save_json=SAVE_JSON)

    print("\n" + "=" * 60)
    print("✅ 解析完成")
    print("=" * 60)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))

# 不使用命令运行，可能间接路径导入失败，因此推荐命令运行，参考pdf_parser.py