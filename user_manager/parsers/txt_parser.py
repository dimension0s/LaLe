"""
txt_parser.py - TXT / MD 解析器
路径: /home/bina/LaLe/user_manager/parsers/txt_parser.py
"""

from pathlib import Path
from typing import Dict

from loguru import logger

from user_manager.parsers.base import BaseParser, save_parsed_json


class TXTParser(BaseParser):
    """TXT / MD 解析器"""

    def parse(self, file_path: str, file_type: str = None) -> Dict:
        """解析 TXT / MD"""
        # 判断类型
        suffix = Path(file_path).suffix.lower()
        if file_type is None:
            if suffix in (".md", ".markdown"):
                self.file_type = "md"
            else:
                self.file_type = "txt"
        else:
            self.file_type = file_type

        # 只构造基础信息
        info = self._build_base_info(file_path)

        logger.info(f"TXT 解析完成: {info['file_name']}")
        return info


# ============================================================
# 便捷函数
# ============================================================
def parse_txt(file_path: str, save_json: bool = True) -> Dict:
    """解析 TXT / MD 并可选保存 JSON"""
    parser = TXTParser()
    result = parser.parse(file_path)
    if save_json:
        save_parsed_json(result)
    return result


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    FILE_PATH = "/mnt/e/英语/test.txt"
    SAVE_JSON = True
    # ================================================

    print("=" * 60)
    print("TXT 解析测试")
    print("=" * 60)
    print(f"文件: {FILE_PATH}")
    print("=" * 60)

    result = parse_txt(FILE_PATH, save_json=SAVE_JSON)

    print("\n" + "=" * 60)
    print("✅ 解析完成")
    print("=" * 60)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))