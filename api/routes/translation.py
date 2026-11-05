"""
翻译路由
"""

from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.translation import TranslationRequest
from translation.core import translate

router = APIRouter()


@router.post("")
async def translate_text(
    req: TranslationRequest,
    user_id: int = Depends(get_current_user_id),
):
    """
    翻译接口（耗时操作，放在线程池中执行）
    """
    try:
        # 使用 run_in_threadpool 避免阻塞 FastAPI 的异步事件循环
        result_data = await run_in_threadpool(
            translate,
            text=req.text,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            mode=req.mode,
            use_tools=req.use_tools,
            return_trace=req.return_trace,
        )

        # 解析返回值（取决于 return_trace 参数）
        if req.return_trace:
            result, trace = result_data
            data = result.to_dict()
            data["trace"] = trace.to_dict()
        else:
            result = result_data
            data = result.to_dict()

        return ok(data=data)

    except ValueError as e:
        # 参数错误（比如 text 为空）在业务层被 raise
        return fail(400, str(e))
    except Exception as e:
        # 捕获超时或 API Key 错误
        return fail(500, f"翻译失败: {str(e)}")