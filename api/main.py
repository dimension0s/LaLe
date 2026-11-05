"""
main.py - FastAPI 应用入口
"""
import sys
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from api.response import (
    http_exception_handler,
    unhandled_exception_handler,
    validation_exception_handler,
)
from api.routes import (
    account as account_routes,
    auth as auth_routes,
    integration as integration_routes,
    dictionary as dictionary_routes,
    notes as notes_routes,
    recycle as recycle_routes,
    search as search_routes,
    upload as upload_routes,
    vocabulary as vocabulary_routes,
    translation as translation_routes,
    nlp as nlp_routes,
    web as web_routes,
    dashboard as dashboard_routes
)


# 获取项目根目录
PROJECT_ROOT = Path(__file__).resolve().parent.parent
upload_dir = PROJECT_ROOT / "data" / "user_uploads"
os.makedirs(upload_dir, exist_ok=True)

app = FastAPI(title="LaLe API", version="0.1.0")
app.mount("/uploads", StaticFiles(directory=str(upload_dir)), name="uploads")

# 挂载用户头像的静态目录
avatar_dir = Path(__file__).resolve().parent.parent / "data" / "user_avatars"
os.makedirs(avatar_dir, exist_ok=True)
app.mount("/avatars", StaticFiles(directory=str(avatar_dir)), name="avatars")


CORS_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:3000",
    "http://127.0.0.1:5173",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.add_exception_handler(HTTPException, http_exception_handler)
app.add_exception_handler(RequestValidationError, validation_exception_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)


app.include_router(auth_routes.router, prefix="/api/auth", tags=["auth"])
app.include_router(account_routes.router, prefix="/api/account", tags=["account"])
app.include_router(upload_routes.router, prefix="/api/documents", tags=["documents"])
app.include_router(notes_routes.router, prefix="/api/notes", tags=["notes"])
app.include_router(integration_routes.router, prefix="/api/integrations", tags=["integrations"])
app.include_router(recycle_routes.router, prefix="/api/recycle", tags=["recycle"])
app.include_router(search_routes.router, prefix="/api/search", tags=["search"])
app.include_router(dictionary_routes.router, prefix="/api/dictionary", tags=["dictionary"])
app.include_router(vocabulary_routes.router, prefix="/api/vocabulary", tags=["vocabulary"])
app.include_router(translation_routes.router, prefix="/api/translation", tags=["translation"])
app.include_router(nlp_routes.router, prefix="/api/nlp", tags=["nlp"])
app.include_router(web_routes.router, prefix="/api/web", tags=["web"])
app.include_router(dashboard_routes.router, prefix="/api/dashboard", tags=["dashboard"])

@app.get("/health")
def health():
    return {"code": 0, "data": {"status": "ok"}, "msg": "ok"}