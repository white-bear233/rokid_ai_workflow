"""FastAPI 路由模块 - LangGraph Agent 版本"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
import time
from models.schemas import GuideAnalyzeRequest
from agent.graph import create_guide_graph
from utils.logger import setup_logger

logger = setup_logger(__name__)

# 创建路由
router = APIRouter(prefix="/api/v1", tags=["API"])


@router.get("/health", tags=["健康检查"])
async def health_check():
    """健康检查接口"""
    return {
        "status": "healthy",
        "agent": "LangGraph",
        "version": "3.1.0"
    }


@router.post("/guide/analyze", tags=["导览分析"])
async def guide_analyze(request: GuideAnalyzeRequest):
    """
    导览分析主入口 - LangGraph Agent（返回完整结果）

    **请求体**:
    - image_base64: Base64 编码的图片 (带 data:image/ 前缀)
    - location: 用户位置描述
    - user_question: 用户提问
    - user_mode: 导览模式（默认模式、亲子模式、情侣模式等）

    **返回**: JSON 格式的完整回复
    """
    # 创建 Agent 图
    try:
        graph = create_guide_graph()
    except Exception as e:
        logger.error(f"创建 Agent 图失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent 初始化失败: {str(e)}")

    try:
        # 记录请求开始时间
        start_time = time.time()

        # 构建初始状态
        initial_state = {
            "messages": [],
            "image_base64": request.image_base64,
            "location": request.location,
            "user_question": request.user_question,
            "user_mode": request.user_mode,
            "visual_analysis": None,
            "search_queries": None,
            "search_results": None,
            "weather_info": None
        }

        logger.info(f"[API] 开始 LangGraph Agent 执行")
        logger.info(f"[API] 问题: {request.user_question}")
        logger.info(f"[API] 位置: {request.location}")
        logger.info(f"[API] 模式: {request.user_mode}")

        # 执行 Agent 图并获取最终状态
        final_state = await graph.ainvoke(initial_state)

        execution_time = time.time() - start_time
        logger.info(f"[API] LangGraph Agent 执行完成，耗时: {execution_time:.2f}秒")

        # 从最终状态中提取回复
        messages = final_state.get("messages", [])
        final_message = None

        # 查找最后的 AI 消息（跳过 ToolMessage 和工具调用消息）
        from langchain_core.messages import ToolMessage
        for msg in reversed(messages):
            # 跳过工具消息
            if isinstance(msg, ToolMessage):
                continue
            # 跳过有工具调用的消息
            if hasattr(msg, 'tool_calls') and msg.tool_calls:
                continue
            # 找到有内容的消息
            if hasattr(msg, 'content') and msg.content:
                final_message = msg.content
                break

        if not final_message:
            # 如果没有找到最终消息，返回默认回复
            final_message = "抱歉，我暂时无法回答这个问题。请尝试换个方式提问。"

        # 提取额外的信息（如果有）
        visual_analysis = final_state.get("visual_analysis")
        search_results = final_state.get("search_results")
        weather_info = final_state.get("weather_info")

        response_data = {
            "status": "success",
            "reply": final_message,
            "metadata": {
                "location": request.location,
                "mode": request.user_mode,
                "visual_analysis": visual_analysis,
                "has_search_results": bool(search_results),
                "has_weather_info": bool(weather_info),
                "execution_time": f"{execution_time:.2f}s"
            }
        }

        total_time = time.time() - start_time
        logger.info(f"[API] 总耗时: {total_time:.2f}秒 | 准备返回响应")

        return response_data

    except Exception as e:
        logger.error(f"Agent 执行失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Agent 执行失败: {str(e)}")
