"""FastAPI 路由模块 - LangGraph Agent 版本"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
import time
from models.schemas import GuideAnalyzeRequest, TourRequest, JournalGenerateRequest
from agent.guide.graph import create_guide_graph
from agent.travel.graph import create_travel_graph
from agent.journal.graph import create_journal_graph
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
    data: {"status": "processing", "step": 1, "message": "正在分析图片..."}
    data: {"status": "processing", "step": 2, "message": "正在联网搜索相关信息..."}
    data: {"text": "您"}
    data: {"text": "眼前"}
    data: {"text": "这座"}
    ...
    data: [DONE]
    ```

    **事件类型**:
    - 进度事件：{"status": "processing", "step": N, "message": "..."}
    - 文本片段：{"text": "内容片段"}
    - 完成标志：data: [DONE]
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
        SSE 流式生成器 - 符合 Android 客户端规范

        输出格式：
        - 进度事件：{"status": "processing", "step": N, "message": "..."}
        - 文本片段：{"text": "内容片段"}
        - 完成标志：data: [DONE]
        """
        start_time = time.time()
        final_message = None
        step = 0

        try:
            # 发送初始进度
            step += 1
            progress_data = json.dumps({
                "status": "processing",
                "step": step,
                "message": "正在分析图片..."
            }, ensure_ascii=False)
            yield f"data: {progress_data}\n\n"

            # 使用 astream 获取流式事件
            async for event in graph.astream(initial_state):
                # 记录事件类型
                event_type = list(event.keys())[0] if event else "unknown"
                logger.debug(f"[API-SSE] 事件类型: {event_type}")

                # 处理视觉分析节点
                if event_type == "vision":
                    node_data = event[event_type]

                    # 提取数据
                    search_queries = node_data.get("search_queries", [])
                    visual_entity = node_data.get("visual_entity", "")
                    image_description = node_data.get("image_description", "")

                    step += 1

                    # 发送识别结果
                    if visual_entity:
                        progress_data = json.dumps({
                            "status": "processing",
                            "step": step,
                            "message": f"识别主体: {visual_entity}"
                        }, ensure_ascii=False)
                        yield f"data: {progress_data}\n\n"

                    # 发送图片描述
                    if image_description:
                        step += 1
                        progress_data = json.dumps({
                            "status": "processing",
                            "step": step,
                            "message": f"图片描述: {image_description[:50]}...",
                            "image_description": image_description
                        }, ensure_ascii=False)
                        yield f"data: {progress_data}\n\n"

                    # 发送搜索关键词
                    if search_queries:
                        step += 1
                        keywords_str = "、".join(search_queries)
                        progress_data = json.dumps({
                            "status": "processing",
                            "step": step,
                            "message": f"搜索关键词: {keywords_str}",
                            "search_queries": search_queries
                        }, ensure_ascii=False)
                        yield f"data: {progress_data}\n\n"

                    step += 1
                    progress_data = json.dumps({
                        "status": "processing",
                        "step": step,
                        "message": "正在联网搜索相关信息..."
                    }, ensure_ascii=False)
                    yield f"data: {progress_data}\n\n"

                # 处理工具节点
                elif event_type == "tools":
                    # 检查是否是周边搜索工具
                    node_data = event[event_type]
                    messages = node_data.get("messages", [])

                    # 判断工具类型并发送相应的进度消息
                    tool_message = ""
                    if messages:
                        last_msg = messages[-1]
                        # 通过消息内容判断工具类型
                        if hasattr(last_msg, 'content') and last_msg.content:
                            content_str = str(last_msg.content)
                            if "周边" in content_str or "POI" in content_str or "设施" in content_str:
                                tool_message = "正在搜索周边设施..."
                            elif "天气" in content_str:
                                tool_message = "正在查询天气信息..."
                            else:
                                tool_message = "正在获取更多信息..."

                    step += 1
                    progress_data = json.dumps({
                        "status": "processing",
                        "step": step,
                        "message": tool_message or "正在处理工具调用..."
                    }, ensure_ascii=False)
                    yield f"data: {progress_data}\n\n"

                # 检查是否是 agent 节点的输出
                elif event_type == "agent":
                    node_data = event[event_type]
                    messages = node_data.get("messages", [])

                    if messages:
                        last_message = messages[-1]

                        # 只处理 AIMessage 且有内容的消息（跳过工具调用）
                        from langchain_core.messages import AIMessage
                        if isinstance(last_message, AIMessage):
                            # 跳过有工具调用的消息
                            if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
                                logger.debug(f"[API-SSE] 跳过工具调用消息")
                                continue

                            # 获取内容
                            content = last_message.content
                            if content:
                                final_message = content
                                logger.debug(f"[API-SSE] 准备发送内容: {content[:50]}...")

                                # 🎯 关键改动：分块发送文本（逐字或逐词）
                                # 方案1：逐字发送（更流畅）
                                # for char in content:
                                #     chunk_data = json.dumps({"text": char}, ensure_ascii=False)
                                #     yield f"data: {chunk_data}\n\n"

                                # 方案2：逐词发送（更实用，推荐）
                                # 按照空格和标点符号分割
                                import re
                                words = re.findall(r'[\s\S]', content)  # 逐字符
                                # words = re.findall(r'[^，。！？\s]+[，。！？]?', content)  # 逐词/句

                                for word in words:
                                    chunk_data = json.dumps({"text": word}, ensure_ascii=False)
                                    yield f"data: {chunk_data}\n\n"
                                    # 可选：添加延迟模拟流式效果
                                    # import asyncio
                                    # await asyncio.sleep(0.01)

            # 流式输出完成，发送结束标记
            total_time = time.time() - start_time
            logger.info(f"[API-SSE] 流式输出完成，总耗时: {total_time:.2f}秒")

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


@router.post("/tour/plan", tags=["旅游规划"])
async def tour_plan(request: TourRequest):
    """
    旅游规划主入口 - LangGraph Agent（同步返回 JSON）

    **请求体**:
    - destination: 目的地（如"北京"）
    - start_date: 开始日期（ISO格式，如"2024-03-28"）
    - end_date: 结束日期（ISO格式，如"2024-03-30"）
    - travel_mode: 同行人群（如"带父母"）
    - intensity: 游玩强度（如"悠闲慢游"）
    - preferences: 偏好列表（如["历史文化", "自然风光"]）
    - must_visit: 必去景点列表（如["故宫"]）
    - custom_requirements: 用户自定义要求

    **返回**: 结构化 JSON 行程单，包含每日活动详情
    """
    # 创建 Agent 图
    try:
        graph = create_travel_graph()
    except Exception as e:
        logger.error(f"创建旅游规划 Agent 图失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent 初始化失败: {str(e)}")

    # 构建初始状态
    initial_state = {
        "request": request,
        "raw_poi_names": [],
        "enriched_pois": [],
        "weather_info": "",
        "weather_by_date": {},
        "draft_itinerary": {},
        "validation_errors": [],
        "loop_count": 0
    }

    logger.info(f"[API] 开始旅游规划 - 目的地: {request.destination}, 日期: {request.start_date} ~ {request.end_date}")

    try:
        # 执行图（同步执行）
        result = await graph.ainvoke(initial_state)

        # 提取最终行程
        itinerary = result.get("draft_itinerary", {})

        if not itinerary:
            raise HTTPException(status_code=500, detail="行程生成失败")

        logger.info(f"[API] 旅游规划完成 - 总天数: {itinerary.get('total_days', 0)}")

        return {
            "success": True,
            "itinerary": itinerary,
            "weather_info": result.get("weather_info", ""),
            "total_pois": len(result.get("enriched_pois", [])),
            "loop_count": result.get("loop_count", 0)
        }

    except Exception as e:
        logger.error(f"[API] 旅游规划失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"旅游规划失败: {str(e)}")


@router.post("/journal/generate", tags=["游记生成"])
async def journal_generate(request: JournalGenerateRequest):
    """
    游记生成主入口 - LangGraph Agent（SSE 流式响应）

    **请求体**:
    - photos: Base64 编码的图片列表 (最多9张)
    - location_hint: 用户提供的地点提示 (可选)
    - writing_style: 写作风格 (文艺/幽默/简洁/故事)
    - user_mode: 用户模式 (默认模式/亲子模式/情侣模式)
    - custom_requirements: 用户自定义要求 (可选)

    **返回**: SSE 流式响应
    """
    # 创建 Agent 图
    try:
        graph = create_journal_graph()
    except Exception as e:
        logger.error(f"创建游记生成 Agent 图失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Agent 初始化失败: {str(e)}")

    # 构建初始状态
    initial_state = {
        "photos": request.photos,
        "location_hint": request.location_hint,
        "writing_style": request.writing_style,
        "user_mode": request.user_mode,
        "custom_requirements": request.custom_requirements,
        "photo_metadata_list": [],
        "aggregated_tags": [],
        "timeline_order": [],
        "location_sequence": [],
        "narrative_structure": [],
        "theme": "",
        "emotion_curve": [],
        "draft_journal": "",
        "refined_journal": "",
        "title": "",
        "current_step": "",
        "errors": []
    }

    logger.info(f"[API] 开始游记生成 - 照片数: {len(request.photos)}, 风格: {request.writing_style}, 模式: {request.user_mode}")

    async def generate_sse():
        """SSE 流式生成器"""
        start_time = time.time()
        step = 0

        try:
            # 发送初始进度
            step += 1
            progress_data = json.dumps({
                "status": "processing",
                "step": step,
                "message": f"开始处理 {len(request.photos)} 张照片..."
            }, ensure_ascii=False)
            yield f"data: {progress_data}\n\n"

            # 使用 astream 获取流式事件
            async for event in graph.astream(initial_state):
                event_type = list(event.keys())[0] if event else "unknown"
                node_data = event[event_type]

                # 处理数据清洗节点
                if event_type == "data_cleaning":
                    step += 1
                    progress_data = json.dumps({
                        "status": "processing",
                        "step": step,
                        "message": f"正在分析照片..."
                    }, ensure_ascii=False)
                    yield f"data: {progress_data}\n\n"

                    # 发送聚合标签
                    aggregated_tags = node_data.get("aggregated_tags", [])
                    if aggregated_tags:
                        step += 1
                        progress_data = json.dumps({
                            "status": "processing",
                            "step": step,
                            "message": f"识别标签: {', '.join(aggregated_tags[:5])}",
                            "tags": aggregated_tags
                        }, ensure_ascii=False)
                        yield f"data: {progress_data}\n\n"

                    # 发送地点序列
                    location_sequence = node_data.get("location_sequence", [])
                    if location_sequence:
                        step += 1
                        progress_data = json.dumps({
                            "status": "processing",
                            "step": step,
                            "message": f"游览路线: {' → '.join(location_sequence)}",
                            "locations": location_sequence
                        }, ensure_ascii=False)
                        yield f"data: {progress_data}\n\n"

                # 处理叙事规划节点
                elif event_type == "narrative_planning":
                    step += 1
                    progress_data = json.dumps({
                        "status": "processing",
                        "step": step,
                        "message": "正在规划游记结构..."
                    }, ensure_ascii=False)
                    yield f"data: {progress_data}\n\n"

                    # 发送主题
                    theme = node_data.get("theme", "")
                    if theme:
                        step += 1
                        progress_data = json.dumps({
                            "status": "processing",
                            "step": step,
                            "message": f"游记主题: {theme}",
                            "theme": theme
                        }, ensure_ascii=False)
                        yield f"data: {progress_data}\n\n"

                # 处理风格化写作节点
                elif event_type == "styled_writing":
                    step += 1
                    progress_data = json.dumps({
                        "status": "processing",
                        "step": step,
                        "message": "正在生成游记内容..."
                    }, ensure_ascii=False)
                    yield f"data: {progress_data}\n\n"

                    # 流式发送游记内容
                    title = node_data.get("title", "")
                    journal = node_data.get("refined_journal", "")

                    if title:
                        title_data = json.dumps({
                            "type": "title",
                            "content": title
                        }, ensure_ascii=False)
                        yield f"data: {title_data}\n\n"

                    if journal:
                        # 逐字发送
                        for char in journal:
                            chunk_data = json.dumps({
                                "type": "text",
                                "content": char
                            }, ensure_ascii=False)
                            yield f"data: {chunk_data}\n\n"

            # 发送完成事件
            total_time = time.time() - start_time
            complete_data = json.dumps({
                "status": "completed",
                "message": "游记生成完成",
                "processing_time": total_time
            }, ensure_ascii=False)
            yield f"data: {complete_data}\n\n"

            # 发送结束标记
            yield "data: [DONE]\n\n"

        except Exception as e:
            logger.error(f"[API-SSE] 游记生成失败: {e}", exc_info=True)
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
            "X-Accel-Buffering": "no"
        }
    )

