"""
base.py - parsers 基类和公共工具
路径: /home/bina/LaLe/user_manager/parsers/base.py
"""

import hashlib
import json
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from loguru import logger


# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


# ============================================================
# 抽象基类
# ============================================================
class BaseParser(ABC):
    """文件解析器基类"""

    file_type: str = ""

    def __init__(self):
        pass

    @abstractmethod
    def parse(self, file_path: str) -> Dict:
        """
        解析文件，返回关键信息

        Returns:
            {
                "file_name": "...",
                "file_type": "...",
                "source_channel": "file",
                "file_path": "...",
                "file_size": ...,
                "created_at": "...",   # 文件系统创建时间
                "parsed_at": "...",    # 解析时间
            }
        """
        pass

    # -------------------- 公共工具 --------------------
    def _build_base_info(self, file_path: str) -> Dict:
        """构造基础信息"""
        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {file_path}")

        stat = path.stat()

        return {
            "file_name": path.name,
            "file_type": self.file_type,
            "source_channel": "file",
            "file_path": str(path),
            "file_size": stat.st_size,
            "created_at": datetime.fromtimestamp(stat.st_ctime).isoformat(),
            "parsed_at": datetime.now().isoformat(),
        }

    def _calc_file_hash(self, file_path: str) -> str:
        """计算文件哈希（MD5）"""
        md5 = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                md5.update(chunk)
        return md5.hexdigest()


# ============================================================
# 公共函数
# ============================================================
def save_parsed_json(data: Dict, output_dir: str = None) -> str:
    """
    保存解析结果为 JSON

    Args:
        data: 解析结果
        output_dir: 输出目录（默认 data/output/user_files_parsed/）

    Returns:
        保存路径
    """
    if output_dir is None:
        output_dir = PROJECT_ROOT / "data" / "output" / "user_files_parsed"
    else:
        output_dir = Path(output_dir)

    output_dir.mkdir(parents=True, exist_ok=True)

    file_name = Path(data["file_name"]).stem
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = output_dir / f"{file_name}_{timestamp}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    logger.info(f"✅ 解析结果已保存: {output_path}")
    return str(output_path)