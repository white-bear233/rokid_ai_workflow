"""
AI 导览微服务 - FastAPI 主应用
模块化异步架构：视觉分析 → Bocha搜索 → 流式生成
"""

import sys
import io
from contextlib import asynccontextmanager
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()

# 修复 Windows 控制台编码
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import httpx
import os
import json

from api.routes import router
from utils.logger import setup_logger

logger = setup_logger('app')

# 创建 FastAPI 应用
app = FastAPI(
    title="AI 导览微服务",
    description="AR旅游助手后端AI服务 - 视觉分析+联网搜索+流式生成",
    version="2.0.0"
)

# CORS 配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 注册路由
app.include_router(router)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    dashscope_key = os.getenv("DASHSCOPE_API_KEY", "")
    bocha_key = os.getenv("BOCHA_API_KEY", "")

    if not dashscope_key:
        logger.warning("⚠️  DASHSCOPE_API_KEY 未配置")
    if not bocha_key:
        logger.warning("⚠️  BOCHA_API_KEY 未配置")

    logger.info("🚀 AI 导览微服务启动完成")
    logger.info("📡 框架: FastAPI")
    logger.info("✅ 支持异步处理")

    yield

    # 关闭时
    logger.info("👋 AI 导览微服务关闭")


# 设置生命周期
app.router.lifespan_context = lifespan


@app.get("/", tags=["根路由"])
async def root():
    """根路径"""
    return {
        "service": "AI 导览微服务",
        "version": "2.0.0",
        "framework": "FastAPI",
        "features": [
            "视觉关键词提取 (通义千问 VL)",
            "Bocha 联网搜索",
            "多模态流式生成"
        ],
        "endpoints": {
            "health": "/api/v1/health",
            "analyze": "/api/v1/guide/analyze",
            "docs": "/docs"
        }
    }


@app.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查接口（兼容旧路由）"""
    from services.vision_service import VisionService
    from services.search_service import SearchService

    vision_service = VisionService()
    search_service = SearchService()

    return {
        "status": "healthy",
        "timestamp": httpx.get("http://worldtimeapi.org/api/timezone").json().get('datetime', ''),
        "services": {
            "dashscope": bool(vision_service.api_key),
            "bocha": bool(search_service.api_key)
        }
    }


if __name__ == "__main__":
    import uvicorn

    logger.info("=" * 60)
    logger.info("启动 AI 导览微服务")
    logger.info("=" * 60)
    logger.info("📡 服务地址: http://0.0.0.0:8000")
    logger.info("📖 API 文档: http://localhost:8000/docs")
    logger.info("=" * 60)

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
