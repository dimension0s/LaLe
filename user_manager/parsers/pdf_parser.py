"""
pdf_parser.py - PDF 解析器
路径: /home/bina/LaLe/user_manager/parsers/pdf_parser.py
"""

from typing import Dict

from loguru import logger

from user_manager.parsers.base import BaseParser, save_parsed_json


class PDFParser(BaseParser):
    """PDF 解析器"""

    file_type = "pdf"

    def parse(self, file_path: str) -> Dict:
        """解析 PDF"""
        # 只构造基础信息
        info = self._build_base_info(file_path)

        logger.info(f"PDF 解析完成: {info['file_name']}")
        return info


# ============================================================
# 便捷函数
# ============================================================
def parse_pdf(file_path: str, save_json: bool = True) -> Dict:
    """解析 PDF 并可选保存 JSON"""
    parser = PDFParser()
    result = parser.parse(file_path)
    if save_json:
        save_parsed_json(result)
    return result


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("用法: python -m user_manager.parsers.pdf_parser <pdf_path>")
        sys.exit(1)

    result = parse_pdf(sys.argv[1])
    print("\n解析结果:")
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))
# 使用命令
# python -m user_manager.parsers.pdf_parser "/mnt/e/英语/magazine/The Economist_20260926.pdf"