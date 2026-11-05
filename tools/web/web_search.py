"""
web_search.py - 联网搜索工具（基于 Tavily）
路径: /home/bina/LaLe/tools/search/web_search.py

职责:
1. 调用 Tavily API 搜索
2. 整理搜索结果（标题 + URL + 内容摘要）
3. 截断保护
4. 返回简洁文本
"""

import os
from pathlib import Path
from typing import Optional, List, Dict

from loguru import logger
from dotenv import load_dotenv


# ============================================================
# 配置
# ============================================================
# 路径计算：web_search.py → search/ → tools/ → LaLe/
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


# 截断长度
MAX_RESULT_LEN = 2000

# Tavily 配置
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
TAVILY_SEARCH_DEPTH = "basic"     # "basic" (1 credit) / "advanced" (2 credits)


# ============================================================
# 核心函数
# ============================================================
def web_search_tool(
    query: str,
    max_results: int = 5,
    search_depth: str = TAVILY_SEARCH_DEPTH,
    include_domains: Optional[List[str]] = None,
    exclude_domains: Optional[List[str]] = None,
    topic: str = "general",      # "general" / "news"
    time_range: Optional[str] = None,   # "day" / "week" / "month" / "year"
) -> str:
    """
    联网搜索工具

    Args:
        query: 查询文本
        max_results: 返回结果数
        search_depth: 搜索深度（"basic" / "advanced"）
        include_domains: 限定域名（如 ["gov.cn", "xinhuanet.com"]）
        exclude_domains: 排除域名
        topic: 主题（"general" / "news"）
        time_range: 时间范围（"day" / "week" / "month" / "year"）

    Returns:
        整理后的搜索结果（文本）
    """
    # 1. 检查 query
    if not query or not query.strip():
        return "[联网搜索失败: query 为空]"

    query = query.strip()

    # 2. 检查 API Key
    if not TAVILY_API_KEY:
        logger.warning("未设置 TAVILY_API_KEY，联网搜索不可用")
        return "[联网搜索失败: 未设置 TAVILY_API_KEY]"

    # 3. 调用 Tavily
    try:
        from tavily import TavilyClient

        client = TavilyClient(api_key=TAVILY_API_KEY)

        # 构造参数
        search_params = {
            "query": query,
            "max_results": max_results,
            "search_depth": search_depth,
            "topic": topic,
        }
        if include_domains:
            search_params["include_domains"] = include_domains
        if exclude_domains:
            search_params["exclude_domains"] = exclude_domains
        if time_range:
            search_params["time_range"] = time_range

        response = client.search(**search_params)

    except ImportError:
        return "[联网搜索失败: 未安装 tavily-python，请运行 pip install tavily-python]"
    except Exception as e:
        logger.error(f"Tavily 搜索失败: {e}")
        return f"[联网搜索失败: {e}]"

    # 4. 整理结果
    results = response.get("results", [])
    if not results:
        return "[联网搜索无结果]"

    lines = []
    for i, r in enumerate(results, 1):
        title = r.get("title", "").strip()
        url = r.get("url", "").strip()
        content = r.get("content", "").strip()
        score = r.get("score", 0.0)

        lines.append(f"[{i}] {title}")
        lines.append(f"    URL: {url}")
        lines.append(f"    相关度: {score:.2f}")
        lines.append(f"    内容: {content}")
        lines.append("")

    result_text = "\n".join(lines).strip()

    # 5. 截断保护
    if len(result_text) > MAX_RESULT_LEN:
        result_text = result_text[:MAX_RESULT_LEN] + "\n...[已截断]"

    logger.info(
        f"联网搜索: query={query!r}, "
        f"返回 {len(results)} 条, "
        f"长度 {len(result_text)} 字符"
    )

    return result_text


# ============================================================
# 命令行入口：测试
# ============================================================
if __name__ == "__main__":
    QUERY = "2025年政府工作报告 新质生产力 英文"
    MAX_RESULTS = 5

    print("=" * 60)
    print("联网搜索测试（Tavily）")
    print("=" * 60)
    print(f"Query: {QUERY}")
    print(f"max_results: {MAX_RESULTS}")
    print(f"API Key: {'已设置' if TAVILY_API_KEY else '未设置'}")
    print("=" * 60)

    result = web_search_tool(QUERY, max_results=MAX_RESULTS)

    print("\n" + "=" * 60)
    print(f"结果（{len(result)} 字符）:")
    print("=" * 60)
    print(result)