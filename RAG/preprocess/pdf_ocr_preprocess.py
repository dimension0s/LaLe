"""
pdf_ocr_preprocess.py - 扫描版 PDF 的 OCR 批量预处理
路径: /home/bina/LaLe/RAG/preprocess/pdf_ocr_preprocess.py

职责:
1. 批量读取 source_dir 下的扫描版 PDF
2. 用 RapidOCR 做 OCR
3. 输出纯文本文件（文件名 = PDF 文件名）
4. 支持增量更新（skip_existing）

不负责:
- 创建 documents 记录（由 pdf_chunker.py 负责）
- 文本切块（由 pdf_chunker.py 负责）
"""

from pathlib import Path
from typing import Dict, Optional

import pymupdf
import numpy as np
from loguru import logger
from rapidocr import RapidOCR


# ============================================================
# 配置
# ============================================================
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SOURCE_DIR = PROJECT_ROOT / "data" / "output" / "translation_books"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "rag" / "source_text"


# ============================================================
# OCR 核心
# ============================================================
class PDFOCRPreprocessor:
    """扫描版 PDF OCR 预处理器（基于 RapidOCR）"""

    def __init__(self):
        logger.info("正在加载 RapidOCR 模型...")
        self.ocr = RapidOCR()
        logger.info("✅ RapidOCR 模型加载完成")

    def pdf_to_images(self, pdf_path: str, dpi: int = 300) -> list:
        """将 PDF 每页渲染为 numpy 图像数组"""
        doc = pymupdf.open(pdf_path)
        mat = pymupdf.Matrix(dpi / 72, dpi / 72)
        images = []

        for page in doc:
            pix = page.get_pixmap(matrix=mat)
            img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
                pix.height, pix.width, pix.n
            )
            if pix.n == 4:
                img = img[:, :, :3]
            images.append(img)

        doc.close()
        logger.info(f"PDF 渲染完成: {len(images)} 页")
        return images

    def ocr_single_pdf(self, pdf_path: str, dpi: int = 300) -> str:
        """对单个扫描版 PDF 做 OCR（内部函数）"""
        images = self.pdf_to_images(pdf_path, dpi)
        all_texts = []

        for i, img in enumerate(images, 1):
            try:
                result = self.ocr(img)
                if result and result.txts:
                    all_texts.append("\n".join(result.txts))

                if i % 10 == 0:
                    logger.info(f"OCR 进度: {i}/{len(images)} 页")
            except Exception as e:
                logger.warning(f"第 {i} 页 OCR 失败: {e}")
                continue

        full_text = "\n\n".join(all_texts)
        logger.info(f"OCR 完成: {len(full_text)} 字符")
        return full_text

    def process_and_save(
        self,
        pdf_path: str,
        output_dir: Path,
        dpi: int = 300,
    ) -> str:
        """处理单个 PDF 并保存结果（内部函数）"""
        full_text = self.ocr_single_pdf(pdf_path, dpi)

        # 用输入 PDF 的文件名（去扩展名）作为输出名
        source_name = Path(pdf_path).stem
        output_path = output_dir / f"{source_name}.txt"

        with open(output_path, "w", encoding="utf-8") as f:
            f.write(full_text)

        logger.info(f"✅ OCR 结果已保存: {output_path}")
        return str(output_path)


# ============================================================
# 批量 OCR（唯一对外入口）
# ============================================================
def ocr_all(
    source_dir: Optional[str] = None,
    output_dir: Optional[str] = None,
    dpi: int = 300,
    skip_existing: bool = True,
) -> Dict[str, Dict]:
    """
    批量 OCR（支持增量更新）

    Args:
        source_dir: PDF 目录（默认 LaLe/data/output/translation_books）
        output_dir: 输出 txt 目录（默认 LaLe/data/output/rag/source_text）
        dpi: 渲染分辨率
        skip_existing: 如果输出 txt 已存在，跳过

    Returns:
        {文件名: {"output_path": ..., "chars": ..., "skipped": ...}}
    """
    # 1. 解析目录
    source_dir = Path(source_dir) if source_dir else DEFAULT_SOURCE_DIR
    output_dir = Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR

    if not source_dir.exists():
        raise FileNotFoundError(f"源目录不存在: {source_dir}")

    output_dir.mkdir(parents=True, exist_ok=True)

    # 2. 查找所有 PDF
    pdf_files = sorted(source_dir.glob("*.pdf"))
    if not pdf_files:
        logger.warning(f"目录下没有 PDF: {source_dir}")
        return {}

    logger.info(f"发现 {len(pdf_files)} 个 PDF")

    # 3. 判断哪些需要 OCR
    to_process = []
    results = {}

    for pdf_file in pdf_files:
        output_path = output_dir / f"{pdf_file.stem}.txt"

        if skip_existing and output_path.exists():
            # 跳过已存在的
            chars = len(output_path.read_text(encoding="utf-8"))
            logger.info(f"⏭️  跳过（已存在）: {pdf_file.name} → {output_path.name} ({chars} 字符)")
            results[pdf_file.name] = {
                "output_path": str(output_path),
                "chars": chars,
                "skipped": True,
            }
        else:
            to_process.append(pdf_file)

    # 4. 如果没有需要处理的，直接返回
    if not to_process:
        logger.info("所有 PDF 已处理过，无需 OCR")
        return results

    logger.info(f"需要 OCR: {len(to_process)} 个 PDF")

    # 5. 加载 OCR 模型（只加载一次）
    preprocessor = PDFOCRPreprocessor()

    # 6. 逐个处理
    for pdf_file in to_process:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"处理: {pdf_file.name}")
        logger.info(f"{'=' * 60}")

        try:
            output_path = preprocessor.process_and_save(
                pdf_path=str(pdf_file),
                output_dir=output_dir,
                dpi=dpi,
            )

            chars = len(Path(output_path).read_text(encoding="utf-8"))
            results[pdf_file.name] = {
                "output_path": output_path,
                "chars": chars,
                "skipped": False,
            }
        except Exception as e:
            logger.error(f"处理失败: {pdf_file.name} - {e}")
            results[pdf_file.name] = {"error": str(e), "skipped": False}

    return results


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 在这里修改参数
    # ================================================
    SOURCE_DIR = None        # None 表示用默认值（data/output/translation_books）
    OUTPUT_DIR = None        # None 表示用默认值（data/output/rag/source_text）
    DPI = 300
    SKIP_EXISTING = True     # 增量更新：已存在则跳过
    # ================================================

    print("=" * 60)
    print("批量 OCR 预处理 (RapidOCR)")
    print("=" * 60)
    print(f"源目录: {SOURCE_DIR or DEFAULT_SOURCE_DIR}")
    print(f"输出目录: {OUTPUT_DIR or DEFAULT_OUTPUT_DIR}")
    print(f"DPI: {DPI}")
    print(f"skip_existing: {SKIP_EXISTING}")
    print("=" * 60)

    results = ocr_all(
        source_dir=SOURCE_DIR,
        output_dir=OUTPUT_DIR,
        dpi=DPI,
        skip_existing=SKIP_EXISTING,
    )

    print("\n" + "=" * 60)
    print(f"✅ 批量 OCR 完成: {len(results)} 个文档")
    print("=" * 60)

    skipped = 0
    processed = 0
    failed = 0

    for filename, info in results.items():
        if "error" in info:
            print(f"  ❌ {filename}: {info['error']}")
            failed += 1
        elif info.get("skipped"):
            print(f"  ⏭️  {filename}: 已存在 ({info['chars']} 字符)")
            skipped += 1
        else:
            print(f"  ✅ {filename}: {info['chars']} 字符 → {Path(info['output_path']).name}")
            processed += 1

    print("\n" + "-" * 60)
    print(f"总计: 处理 {processed} 个, 跳过 {skipped} 个, 失败 {failed} 个")
    print("-" * 60)
