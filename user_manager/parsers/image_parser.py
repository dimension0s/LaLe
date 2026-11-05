"""
image_parser.py - 图片解析器（OCR）
路径: /home/bina/LaLe/user_manager/parsers/image_parser.py

职责:
1. 提取图片元信息
2. 使用 RapidOCR 识别图片中的文字
3. 返回基础信息 + 识别文本

依赖:
- RapidOCR（项目已安装）
- Pillow（用于图片元信息）
"""

import sys
from pathlib import Path
from typing import Dict, Optional

# 兼容直接运行
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from loguru import logger

from user_manager.parsers.base import BaseParser, save_parsed_json


# ============================================================
# 配置
# ============================================================
SUPPORTED_IMAGE_EXTENSIONS = {
    ".png", ".jpg", ".jpeg", ".bmp", ".tiff", ".tif", ".webp"
}


class ImageParser(BaseParser):
    """图片解析器（OCR）"""

    file_type = "image"

    def __init__(self):
        super().__init__()
        self._ocr = None

    def _load_ocr(self):
        """延迟加载 RapidOCR"""
        if self._ocr is None:
            try:
                from rapidocr import RapidOCR
                self._ocr = RapidOCR()
                logger.info("RapidOCR 模型已加载")
            except ImportError:
                raise ImportError(
                    "未安装 rapidocr，请运行: pip install rapidocr"
                )
        return self._ocr

    def parse(self, file_path: str) -> Dict:
        """
        解析图片

        Returns:
            {
                ...基础信息...,
                "ocr_text": "识别到的文字（可能为空）",
                "ocr_success": bool,
                "ocr_error": str（如果失败）,
            }
        """
        # 1. 判断类型
        suffix = Path(file_path).suffix.lower()
        if suffix not in SUPPORTED_IMAGE_EXTENSIONS:
            raise ValueError(f"不支持的图片格式: {suffix}")

        self.file_type = "image"

        # 2. 基础信息
        info = self._build_base_info(file_path)

        # 3. 图片元信息（宽高）
        try:
            from PIL import Image
            with Image.open(file_path) as img:
                info["image_width"] = img.width
                info["image_height"] = img.height
                info["image_mode"] = img.mode
                logger.info(
                    f"图片信息: {info['file_name']}, "
                    f"{img.width}x{img.height}, mode={img.mode}"
                )
        except Exception as e:
            logger.warning(f"图片元信息提取失败: {e}")
            info["image_width"] = None
            info["image_height"] = None
            info["image_mode"] = None

        # 4. OCR 识别
        ocr_text, ocr_success, ocr_error = self._run_ocr(file_path)
        info["ocr_text"] = ocr_text
        info["ocr_success"] = ocr_success
        info["ocr_error"] = ocr_error

        if ocr_success:
            logger.info(
                f"OCR 完成: {info['file_name']}, "
                f"{len(ocr_text)} 字符"
            )
        else:
            logger.warning(f"OCR 失败: {info['file_name']}, {ocr_error}")

        return info

    def _run_ocr(self, file_path: str) -> tuple:
        """
        运行 OCR

        Returns:
            (text, success, error)
        """
        try:
            ocr = self._load_ocr()
            result = ocr(file_path)

            if result is None:
                return "", True, ""

            # RapidOCR 返回 RapidOCROutput
            txts = getattr(result, "txts", None)
            if not txts:
                return "", True, ""

            text = "\n".join(txts)
            return text, True, ""

        except ImportError as e:
            return "", False, str(e)
        except Exception as e:
            logger.error(f"OCR 异常: {e}")
            return "", False, str(e)


# ============================================================
# 便捷函数
# ============================================================
def parse_image(file_path: str, save_json: bool = True) -> Dict:
    """解析图片并可选保存 JSON"""
    parser = ImageParser()
    result = parser.parse(file_path)
    if save_json:
        save_parsed_json(result)
    return result


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 测试参数
    # ================================================
    FILE_PATH = "/mnt/e/英语/test_picture.png"   # ← 改成你的图片路径
    SAVE_JSON = True
    # ================================================

    print("=" * 60)
    print("图片 OCR 解析测试")
    print("=" * 60)
    print(f"文件: {FILE_PATH}")
    print("=" * 60)

    result = parse_image(FILE_PATH, save_json=SAVE_JSON)

    print("\n" + "=" * 60)
    print("✅ 解析完成")
    print("=" * 60)
    import json
    print(json.dumps(result, ensure_ascii=False, indent=2))