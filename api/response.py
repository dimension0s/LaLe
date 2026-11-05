"""
response.py - 统一响应格式与全局异常处理
"""

from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def ok(data: Any = None, msg: str = "ok") -> dict:
    return {"code": 0, "data": data, "msg": msg}


def fail(code: int, msg: str, data: Any = None) -> dict:
    return {"code": code, "data": data, "msg": msg}


async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.status_code, "data": None, "msg": str(exc.detail)},
    )


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
):
    # exc.errors() 的 ctx 里可能含 ValueError 等对象，需 jsonable_encoder 转换
    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({
            "code": 422,
            "data": exc.errors(),
            "msg": "参数校验失败",
        }),
    )


async def unhandled_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"code": 500, "data": None, "msg": "服务器内部错误"},
    )