"""
pdf_chunker.py - 针对pdf格式的文档批量切块

职责:
1. 批量读取 source_dir 下的文档（.txt / .pdf / .md）
2. 每个文档自动创建 documents 记录（PG 自增 id + 自动生成 doc_uuid）
3. 按中/英文自动判断切块大小
4. 固定长度切分（中文按字符，英文按单词）
5. 支持 overlap（默认 15%）
6. 输出 JSONL 文件（第一行是 metadata）

不负责:
- OCR（由 pdf_ocr_preprocess.py 负责）
- 写入 chunks 表（由 indexer/load_chunks_into_pg.py 负责）
- 写入 Qdrant（由 indexer/build_index.py 负责）
"""

import json
import re
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger


# ============================================================
# 配置默认值
# ============================================================
DEFAULT_CHUNK_SIZE_ZH = 550       # 中文 chunk 大小（字符）
DEFAULT_CHUNK_SIZE_EN = 350       # 英文 chunk 大小（单词）
DEFAULT_OVERLAP_RATIO = 0.15      # 重叠比例

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "data" / "output" / "rag" / "chunks"


# ============================================================
# 文本读取
# ============================================================
def _read_txt(path: Path) -> str:
    """读取纯文本（.txt / .md）"""
    text = path.read_text(encoding="utf-8")
    logger.info(f"读取文本文件: {path.name}, {len(text)} 字符")
    return text


def _extract_pdf(path: Path) -> str:
    """提取文本型 PDF"""
    import pymupdf
    doc = pymupdf.open(str(path))
    pages_text = [page.get_text() for page in doc]
    doc.close()

    text = "".join(pages_text)
    logger.info(f"提取 PDF 文本: {path.name}, {len(pages_text)} 页, {len(text)} 字符")

    if len(text.strip()) < 100:
        logger.warning(
            f"⚠️ PDF 文本极少（{len(text)} 字符），可能是扫描版。"
            f"请先用 pdf_ocr_preprocess.py 做 OCR"
        )
    return text


def _extract_text(path: Path) -> str:
    """根据文件类型读取文本"""
    suffix = path.suffix.lower()
    if suffix in (".txt", ".md", ".markdown"):
        return _read_txt(path)
    elif suffix == ".pdf":
        return _extract_pdf(path)
    else:
        raise ValueError(f"不支持的文件类型: {suffix}")


# ============================================================
# 语言判断
# ============================================================
def _detect_language(text: str) -> str:
    """
    判断文本以中文还是英文为主

    按"中文字符数 / 中文字符数 + 英文单词数"判断
    """
    if not text or not text.strip():
        return "zh"

    chinese_count = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
    english_words = len(re.findall(r'[a-zA-Z]+', text))
    total = chinese_count + english_words

    if total == 0:
        return "zh"

    ratio = chinese_count / total
    lang = "zh" if ratio > 0.5 else "en"
    logger.info(
        f"语言判断: 中文 {chinese_count}, 英文 {english_words}, "
        f"中文占比 {ratio:.1%} → {lang}"
    )
    return lang


# ============================================================
# 切块
# ============================================================
def _split_zh(text: str, chunk_size: int, overlap: int) -> List[str]:
    """中文按字符切块"""
    if len(text) <= chunk_size:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end >= len(text):
            break
        start = end - overlap
    return chunks


def _split_en(text: str, chunk_size: int, overlap: int) -> List[str]:
    """英文按单词切块"""
    words = text.split()
    if len(words) <= chunk_size:
        return [" ".join(words)]

    chunks = []
    start = 0
    while start < len(words):
        end = min(start + chunk_size, len(words))
        chunks.append(" ".join(words[start:end]))
        if end >= len(words):
            break
        start = end - overlap
    return chunks


# ============================================================
# 单文档切块（内部函数，供批量调用）
# ============================================================
def _chunk_single_document(
    source_path: Path,
    document_id: int,
    doc_uuid: str,
    title: str,
    category: str,
    language: Optional[str],
    chunk_size_zh: int,
    chunk_size_en: int,
    overlap_ratio: float,
    output_dir: Path,
) -> int:
    """
    切分单个文档并保存为 JSONL

    Returns:
        切出的 chunk 数量
    """
    # 1. 读取文本
    full_text = _extract_text(source_path)
    if not full_text.strip():
        logger.warning(f"文档内容为空: {source_path.name}")
        return 0

    # 2. 判断语言
    detected_lang = _detect_language(full_text)
    final_lang = language or detected_lang

    # 3. 切块
    if detected_lang == "zh":
        chunk_size = chunk_size_zh
        overlap = int(chunk_size_zh * overlap_ratio)
        raw_chunks = _split_zh(full_text, chunk_size, overlap)
    else:
        chunk_size = chunk_size_en
        overlap = int(chunk_size_en * overlap_ratio)
        raw_chunks = _split_en(full_text, chunk_size, overlap)

    # 4. 组装 chunks
    chunks = []
    for content in raw_chunks:
        content = content.strip()
        if not content:
            continue
        chunks.append({
            "chunk_uid": str(uuid.uuid4()),
            "document_id": document_id,
            "content": content,
        })

    logger.info(
        f"切块完成: {len(chunks)} 个 chunk "
        f"(语言={final_lang}, 大小={chunk_size}, overlap={overlap})"
    )

    # 5. 保存 JSONL（第一行 metadata + 后续 chunks）
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{document_id}.jsonl"

    metadata = {
        "_type": "metadata",
        "document_id": document_id,
        "doc_uuid": doc_uuid,
        "title": title,
        "category": category,
        "language": final_lang,
        "source_file": str(source_path),
        "total_chunks": len(chunks),
        "created_at": datetime.utcnow().isoformat(),
    }

    with open(output_path, "w", encoding="utf-8") as f:
        # 第一行：metadata
        f.write(json.dumps(metadata, ensure_ascii=False) + "\n")
        # 后续行：chunks
        for item in chunks:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    logger.info(f"✅ 已保存: {output_path}")
    return len(chunks)


# ============================================================
# 批量切块（唯一对外入口）
# ============================================================
def chunk_all(
    source_dir: str,
    output_dir: Optional[str] = None,
    category: str = "未分类",
    language: Optional[str] = None,
    chunk_size_zh: int = DEFAULT_CHUNK_SIZE_ZH,
    chunk_size_en: int = DEFAULT_CHUNK_SIZE_EN,
    overlap_ratio: float = DEFAULT_OVERLAP_RATIO,
    skip_existing: bool = True,   # ← 新增
) -> Dict[str, Dict]:
    """
    批量切块（自动创建 documents 记录，支持幂等）

    Args:
        source_dir: 源文档目录（.txt / .pdf / .md）
        output_dir: 输出 JSONL 目录（默认 LaLe/data/output/rag/chunks）
        category: 文档分类
        language: 语言（None 表示自动判断）
        chunk_size_zh: 中文 chunk 大小（字符）
        chunk_size_en: 英文 chunk 大小（单词）
        overlap_ratio: 重叠比例
        skip_existing: 如果 JSONL 已存在，跳过（默认 True）

    Returns:
        {文件名: {"document_id": ..., "doc_uuid": ..., "chunks": ..., "skipped": ...}}
    """
    source_dir = Path(source_dir)
    if not source_dir.exists():
        raise FileNotFoundError(f"源目录不存在: {source_dir}")

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    output_dir = Path(output_dir)

    # 1. 查找所有支持的文档
    extensions = [".txt", ".pdf", ".md", ".markdown"]
    files = []
    for ext in extensions:
        files.extend(source_dir.glob(f"*{ext}"))
    files = sorted(files)

    if not files:
        logger.warning(f"目录下没有支持的文档: {source_dir}")
        return {}

    logger.info(f"发现 {len(files)} 个文档")

    # 2. 延迟导入 PG
    from RAG.database import get_session
    from RAG.orm_models import Document

    results = {}
    for file_path in files:
        logger.info(f"\n{'=' * 60}")
        logger.info(f"处理: {file_path.name}")
        logger.info(f"{'=' * 60}")

        try:
            # 用文件名（不含扩展名）作为标题
            title = file_path.stem

            # ============================================
            # ✅ 幂等检查：按 title 查询 documents
            # ============================================
            if skip_existing:
                with get_session() as session:
                    existing_doc = session.query(Document).filter_by(title=title).first()

                if existing_doc:
                    # 检查 JSONL 是否已存在
                    existing_jsonl = output_dir / f"{existing_doc.id}.jsonl"

                    if existing_jsonl.exists():
                        logger.info(
                            f"⏭️  跳过（已存在）: {file_path.name} → "
                            f"document_id={existing_doc.id}, "
                            f"JSONL={existing_jsonl.name}"
                        )
                        results[file_path.name] = {
                            "document_id": existing_doc.id,
                            "doc_uuid": existing_doc.doc_uuid,
                            "chunks": 0,
                            "skipped": True,
                        }
                        continue
                    else:
                        # JSONL 缺失，复用文档记录，重新切块
                        logger.info(
                            f"复用文档记录: id={existing_doc.id}, "
                            f"title={title}（JSONL 缺失，重新切块）"
                        )
                        document_id = existing_doc.id
                        doc_uuid = existing_doc.doc_uuid

                        chunk_count = _chunk_single_document(
                            source_path=file_path,
                            document_id=document_id,
                            doc_uuid=doc_uuid,
                            title=title,
                            category=category,
                            language=language,
                            chunk_size_zh=chunk_size_zh,
                            chunk_size_en=chunk_size_en,
                            overlap_ratio=overlap_ratio,
                            output_dir=output_dir,
                        )

                        results[file_path.name] = {
                            "document_id": document_id,
                            "doc_uuid": doc_uuid,
                            "chunks": chunk_count,
                            "skipped": False,
                        }
                        continue

            # ============================================
            # 创建新文档记录
            # ============================================
            doc_uuid = str(uuid.uuid4())

            with get_session() as session:
                doc = Document(
                    doc_uuid=doc_uuid,
                    title=title,
                    category=category,
                    language=language or "zh",
                )
                session.add(doc)
                session.flush()
                document_id = doc.id
                doc_uuid = doc.doc_uuid

            logger.info(
                f"创建文档记录: id={document_id}, "
                f"doc_uuid={doc_uuid}, title={title}"
            )

            # 切块
            chunk_count = _chunk_single_document(
                source_path=file_path,
                document_id=document_id,
                doc_uuid=doc_uuid,
                title=title,
                category=category,
                language=language,
                chunk_size_zh=chunk_size_zh,
                chunk_size_en=chunk_size_en,
                overlap_ratio=overlap_ratio,
                output_dir=output_dir,
            )

            results[file_path.name] = {
                "document_id": document_id,
                "doc_uuid": doc_uuid,
                "chunks": chunk_count,
                "skipped": False,
            }

        except Exception as e:
            logger.error(f"处理失败: {file_path.name} - {e}")
            results[file_path.name] = {"error": str(e)}

    return results


# ============================================================
# 命令行入口
# ============================================================
if __name__ == "__main__":
    # ================================================
    # 在这里修改参数
    # ================================================
    SOURCE_DIR = "/home/bina/LaLe/data/output/rag/source_text"
    OUTPUT_DIR = "/home/bina/LaLe/data/output/rag/chunks"
    CATEGORY = "翻译"
    LANGUAGE = None   # None 表示自动判断
    SKIP_EXISTING = True   # ← 新增：跳过已存在的
    # ================================================

    print("=" * 60)
    print("批量切块")
    print("=" * 60)
    print(f"源目录: {SOURCE_DIR}")
    print(f"输出目录: {OUTPUT_DIR}")
    print(f"分类: {CATEGORY}")
    print(f"语言: {'自动判断' if LANGUAGE is None else LANGUAGE}")
    print(f"跳过已存在: {SKIP_EXISTING}")
    print("=" * 60)

    results = chunk_all(
        source_dir=SOURCE_DIR,
        output_dir=OUTPUT_DIR,
        category=CATEGORY,
        language=LANGUAGE,
        skip_existing=SKIP_EXISTING,
    )

    print("\n" + "=" * 60)
    print(f"✅ 批量切块完成: {len(results)} 个文档")
    print("=" * 60)

    # 统计
    processed = 0
    skipped = 0
    failed = 0

    for filename, info in results.items():
        if "error" in info:
            print(f"  ❌ {filename}: {info['error']}")
            failed += 1
        elif info.get("skipped"):
            print(
                f"  ⏭️  {filename}: "
                f"document_id={info['document_id']}, "
                f"已存在"
            )
            skipped += 1
        else:
            print(
                f"✅ {filename}: "
                f"document_id={info['document_id']}, "
                f"doc_uuid={info['doc_uuid'][:8]}..., "
                f"chunks={info['chunks']}"
            )
            processed += 1

    print("\n" + "-" * 60)
    print(f"总计: 处理 {processed} 个, 跳过 {skipped} 个, 失败 {failed} 个")
    print("-" * 60)