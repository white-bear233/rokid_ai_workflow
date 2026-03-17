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
    导览分析主入口 - LangGraph Agent（SSE 流式响应）

    **请求体**:
    - image_base64: Base64 编码的图片 (带 data:image/ 前缀)
    - location: 用户位置描述
    - user_question: 用户提问
    - user_mode: 导览模式（默认模式、亲子模式、情侣模式等）

    **返回**: SSE 流式响应，格式为：
    ```
    data: {"content": "部分内容"}
    data: {"content": "更多内容"}
    data: [DONE]
    ```
    """
    # 创建 Agent 图
    try:
        graph = create_guide_graph()
    except Exception as e:
        logger.error(f"创建 Agent 图失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent 初始化失败: {str(e)}")

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

    logger.info(f"[API] 开始 LangGraph Agent SSE 流式执行")
    logger.info(f"[API] 问题: {request.user_question}")
    logger.info(f"[API] 位置: {request.location}")
    logger.info(f"[API] 模式: {request.user_mode}")

    async def generate_sse():
        """
        SSE 流式生成器
        """
        start_time = time.time()
        final_message = None

        try:
            # 使用 astream 获取流式事件
            async for event in graph.astream(initial_state):
                # 记录事件类型
                event_type = list(event.keys())[0] if event else "unknown"
                logger.debug(f"[API-SSE] 事件类型: {event_type}")

                # 检查是否是 agent 节点的输出
                if event_type == "agent":
                    node_data = event[event_type]
                    messages = node_data.get("messages", [])

                    if messages:
                        last_message = messages[-1]

                        # 只处理 AIMessage 且有内容的消息（跳过工具调用）
                        from langchain_core.messages import AIMessage, ToolMessage
                        if isinstance(last_message, AIMessage):
                            # 跳过有工具调用的消息
                            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                                logger.debug(f"[API-SSE] 跳过工具调用消息")
                                continue

                            # 获取内容
                            content = last_message.content
                            if content:
                                # 发送 SSE 格式数据
                                sse_data = json.dumps({"content": content}, ensure_ascii=False)
                                logger.debug(f"[API-SSE] 发送内容: {content[:50]}...")
                                yield f"data: {sse_data}\n\n"
                                final_message = content

                # 处理其他节点（工具执行等）
                elif event_type in ["tools", "vision"]:
                    logger.debug(f"[API-SSE] {event_type} 节点执行完成")

            # 流式输出完成，发送结束标记
            total_time = time.time() - start_time
            logger.info(f"[API-SSE] 流式输出完成，总耗时: {total_time:.2f}秒")

            # 发送元数据（可选）
            if final_message:
                metadata = {
                    "metadata": {
                        "location": request.location,
                        "mode": request.user_mode,
                        "execution_time": f"{total_time:.2f}s"
                    }
                }
                yield f"data: {json.dumps(metadata, ensure_ascii=False)}\n\n"

            # 发送结束标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[API-SSE] Agent 执行失败: {e}", exc_info=True)
            # 发送错误信息
            error_data = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {error_data}\n\n"
            yield "data: [DONE]\n\n"

    # 返回 SSE 流式响应
    return StreamingResponse(
        generate_sse(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # 禁用 Nginx 缓冲
        }
    )
