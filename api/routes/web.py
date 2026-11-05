"""
Web 搜索路由（基于 Tavily）
"""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.web import WebSearchRequest
from tools.web.web_search import web_search_tool

router = APIRouter()


@router.post("/search")
async def search_web(
    req: WebSearchRequest,
    user_id: int = Depends(get_current_user_id),
):
    """联网搜索"""
    try:
        result_text = await run_in_threadpool(
            web_search_tool,
            query=req.query,
            max_results=req.max_results,
            search_depth=req.search_depth,
            include_domains=req.include_domains,
            exclude_domains=req.exclude_domains,
            topic=req.topic,
            time_range=req.time_range,
        )

        # web_search_tool 返回的是字符串，如果以 [联网搜索失败 开头，说明业务报错
        if result_text.startswith("[联网搜索失败"):
            return fail(400, result_text)

        return ok(data={"query": req.query, "result": result_text})

    except Exception as e:
        return fail(500, f"联网搜索异常: {str(e)}")