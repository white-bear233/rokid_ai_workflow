"""FastAPI 路由模块"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
from models.schemas import GuideAnalyzeRequest
from services.vision_service import VisionService
from services.search_service import SearchService
from services.generation_service import GenerationService
from utils.http_client import get_http_client
from utils.logger import setup_logger

logger = setup_logger(__name__)

# 创建路由
router = APIRouter(prefix="/api/v1", tags=["API"])

# 初始化服务（每个请求创建新实例）
def get_services():
    """获取服务实例"""
    return {
        "vision": VisionService(),
        "search": SearchService(),
        "generation": GenerationService()
    }


@router.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查接口"""
    services = get_services()
    return {
        "status": "healthy",
        "services": {
            "dashscope": bool(services["vision"].api_key),
            "bocha": bool(services["search"].api_key)
        }
    }


@router.post("/guide/analyze", tags=["导览分析"])
async def guide_analyze(request: GuideAnalyzeRequest):
    """
    导览分析主入口 - SSE 流式响应（三阶接力模式）

    **请求体**:
    - image_base64: Base64 编码的图片 (带 data:image/ 前缀)
    - location: 用户位置描述
    - user_question: 用户提问
    - user_mode: 导览模式（默认模式、亲子模式、情侣模式等）

    **返回**: SSE 流式文本
    """
    # 验证 API Keys
    services = get_services()
    if not services["vision"].api_key:
        raise HTTPException(status_code=500, detail="DASHSCOPE_API_KEY 未配置")
    if not services["search"].api_key:
        raise HTTPException(status_code=500, detail="BOCHA_API_KEY 未配置")

    # 异步生成流式响应
    async def generate():
        """生成 SSE 流式数据 - 三阶接力"""
        try:
            async with get_http_client() as client:
                # Stage 1: 眼睛（VLM 意图提取与多梯队拆词）
                yield f"data: {json.dumps({'status': 'processing', 'step': 1, 'message': '正在分析图片意图...'}, ensure_ascii=False)}\n\n"

                try:
                    intent_data, _ = await services["vision"].extract_intent(
                        request.image_base64,
                        request.location,
                        request.user_question,
                        client
                    )
                    visual_entity = intent_data.get("visual_entity", "")
                    search_queries = intent_data.get("search_queries", [])

                    if not visual_entity or not search_queries or len(search_queries) != 3:
                        raise ValueError(f"意图提取数据格式错误: {intent_data}")

                except Exception as e:
                    error_msg = f"意图提取失败: {str(e)}"
                    logger.error(error_msg)
                    yield f"data: {json.dumps({'status': 'error', 'message': f'500: {error_msg}'}, ensure_ascii=False)}\n\n"
                    return

                # Stage 2: 检索（梯队式并发搜索与去重融合）
                yield f"data: {json.dumps({'status': 'processing', 'step': 2, 'keywords': search_queries, 'message': '正在联网搜索...'}, ensure_ascii=False)}\n\n"

                search_results = await services["search"].multi_search_with_dedup(
                    search_queries,
                    client
                )

                # Stage 3: 大脑（纯文本 LLM 生成回复）
                yield f"data: {json.dumps({'status': 'processing', 'step': 3, 'message': '正在生成回复...'}, ensure_ascii=False)}\n\n"

                logger.info(f"[API] 开始流式生成，visual_entity: {visual_entity}")

                # 流式生成最终回复（不传图，只传文字）
                chunk_count = 0
                async for chunk in services["generation"].generate_stream(
                    visual_entity,
                    request.location,
                    request.user_question,
                    request.user_mode,
                    search_results,
                    client
                ):
                    logger.debug(f"[API] 收到 chunk {chunk_count}: {chunk[:50] if chunk else '(empty)'}...")
                    yield chunk
                    chunk_count += 1

                logger.info(f"[API] 流式生成完成，总共 {chunk_count} 个 chunks")

        except Exception as e:
            logger.error(f"生成响应失败: {e}", exc_info=True)
            error_msg = {"status": "error", "message": str(e)}
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
            "X-Accel-Buffering": "no"
        }
    )
