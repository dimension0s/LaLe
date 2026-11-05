"""
NLP 辅助模块路由：语法、术语、短语
"""
from fastapi import APIRouter, Depends
from fastapi.concurrency import run_in_threadpool

from api.dependencies import get_current_user_id
from api.response import ok, fail
from api.schemas.nlp import GrammarRequest, TerminologyRequest, PhraseRequest

from grammar.core import parse_grammar
from terminology.core import parse_terminology
from phrase.core import parse_phrase

router = APIRouter()


def _format_response(result_data, return_trace: bool) -> dict:
    """统一处理 (result, trace) 返回值"""
    if return_trace:
        result, trace = result_data
        data = result.to_dict()
        data["trace"] = trace.to_dict() if trace else None
    else:
        result = result_data
        data = result.to_dict()
    return data


@router.post("/grammar")
async def grammar_analysis(
    req: GrammarRequest,
    user_id: int = Depends(get_current_user_id),
):
    """语法解析"""
    try:
        result_data = await run_in_threadpool(
            parse_grammar,
            text=req.text,
            source_lang=req.source_lang,
            use_tools=req.use_tools,
            return_trace=req.return_trace,
        )
        return ok(data=_format_response(result_data, req.return_trace))
    except ValueError as e:
        return fail(400, str(e))
    except Exception as e:
        return fail(500, f"语法解析失败: {str(e)}")


@router.post("/terminology")
async def terminology_analysis(
    req: TerminologyRequest,
    user_id: int = Depends(get_current_user_id),
):
    """术语识别"""
    try:
        result_data = await run_in_threadpool(
            parse_terminology,
            text=req.text,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            use_tools=req.use_tools,
            return_trace=req.return_trace,
        )
        return ok(data=_format_response(result_data, req.return_trace))
    except ValueError as e:
        return fail(400, str(e))
    except Exception as e:
        return fail(500, f"术语识别失败: {str(e)}")


@router.post("/phrase")
async def phrase_analysis(
    req: PhraseRequest,
    user_id: int = Depends(get_current_user_id),
):
    """词组/搭配识别"""
    try:
        result_data = await run_in_threadpool(
            parse_phrase,
            text=req.text,
            source_lang=req.source_lang,
            target_lang=req.target_lang,
            use_tools=req.use_tools,
            return_trace=req.return_trace,
        )
        return ok(data=_format_response(result_data, req.return_trace))
    except ValueError as e:
        return fail(400, str(e))
    except Exception as e:
        return fail(500, f"词组识别失败: {str(e)}")