"""对pdf做简单预处理，即手动确认定位页后编写脚本跳过，保留剩余内容，因此只改变页数参数和input_path内容即可。
  兼容扫描版pdf，文字版pdf"""
import pymupdf as fitz
from pathlib import Path


def preprocess_pdf(input_path, output_path, start_page=1):
    """
    跳过 start_page 之前的所有页面，从第 start_page 页开始保留到结尾。

    参数:
        input_path:  输入PDF路径
        output_path: 输出PDF路径（父目录会自动创建）
        start_page:  从第几页开始保留（1-based，含该页）
    """
    doc = fitz.open(input_path)
    total = doc.page_count

    if start_page < 1:
        start_page = 1
    if start_page > total:
        raise ValueError(f"start_page={start_page} 超过总页数 {total}")

    cut = start_page - 1  # 转为 0-based

    new_doc = fitz.open()
    new_doc.insert_pdf(doc, from_page=cut, to_page=total - 1)

    new_doc.save(output_path)

    new_doc.close()
    doc.close()
    return cut


if __name__ == "__main__":
    # ============ 在这里填写你的参数 ============

    # 输入PDF路径（WSL 下访问 Windows E 盘）
    INPUT_PATH = r"/mnt/e/英语/翻译书籍/英汉翻译基础教程.pdf"

    # 输出PDF路径
    OUTPUT_PATH = r"/home/bina/LaLe/data/output/translation_books/英汉翻译基础教程_预处理.pdf"  # 采取绝对路径

    # 从第几页开始保留（1-based，含该页）
    # 人工翻PDF，确定正文从第几页开始，填在这里
    START_PAGE = 11

    # ==========================================

    cut = preprocess_pdf(
        input_path=INPUT_PATH,
        output_path=OUTPUT_PATH,
        start_page=START_PAGE,
    )

    print(f"原始总页数处理完成，已从第 {cut + 1} 页开始保留")
    print(f"输出文件：{OUTPUT_PATH}")