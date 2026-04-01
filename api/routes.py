"""FastAPI 路由模块 - LangGraph Agent 版本"""
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
import json
import time
from models.schemas import (
    GuideAnalyzeRequest, TourRequest, JournalGenerateRequest,
    GuideResponse, GuideResponseData
)
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
        "version": "3.2.0"
    }


@router.post("/guide/analyze", response_model=GuideResponse, tags=["导览分析"])
async def guide_analyze(request: GuideAnalyzeRequest):
    """
    导览分析主入口 - LangGraph Agent（同步返回 JSON）

    **请求体**:
    - image_base64: Base64 编码的图片 (带 data:image/ 前缀)
    - location: 用户位置描述
    - user_question: 用户提问
    - user_mode: 导览模式（默认模式、亲子模式、情侣模式等）

    **返回**: 结构化 JSON 响应
    ```json
    {
      "code": 200,
      "message": "success",
      "data": {
        "guideText": "导览文字内容...",
        "guideCard": {
          "title": "推荐主题",
          "pages": [
            {
              "text": "每页导览文字",
              "image": {
                "id": "img_ref_1",
                "url": "https://...",
                "caption": "图片说明"
              }
            }
          ]
        }
      }
    }
    ```

    **字段说明**:
    - guideText: 主要导览文字
    - guideCard: 导览卡片（仅POI推荐场景，其他场景为null）
      - title: 推荐主题标题
      - pages: 推荐内容数组
        - text: 每页导览文字
        - image: 图片信息（id, url, caption）
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
        "weather_info": None,
        # 新增字段
        "response_type": None,
        "guide_text": None,
        "guide_card": None,
        "poi_results": None
    }

    logger.info(f"[API] 开始导览分析 - 问题: {request.user_question}")
    logger.info(f"[API] 位置: {request.location}, 模式: {request.user_mode}")

    try:
        start_time = time.time()

        # 同步执行图
        result = await graph.ainvoke(initial_state)

        # 提取结构化响应
        response_type = result.get("response_type", "text")
        guide_text = result.get("guide_text", "导览生成失败")
        guide_card = result.get("guide_card")

        total_time = time.time() - start_time
        logger.info(f"[API] 导览分析完成 - 类型: {response_type}, 耗时: {total_time:.2f}秒")

        return GuideResponse(
            code=200,
            message="success",
            data=GuideResponseData(
                guideText=guide_text,
                guideCard=guide_card if response_type == "card" else None
            )
        )

    except Exception as e:
        logger.error(f"[API] 导览分析失败: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"导览分析失败: {str(e)}")


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

