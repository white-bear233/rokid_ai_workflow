"""Agent 工具定义"""
import asyncio
from langchain_core.tools import tool
from services.search_service import SearchService
from services.vision_service import VisionService
from utils.http_client import get_http_client
from utils.logger import setup_logger
import httpx

logger = setup_logger(__name__)


# ==================== 工具定义 ====================

@tool
def analyze_vision_tool(image_base64: str, location: str, question: str) -> str:
    """
    分析用户视野内的图像内容，识别物体并提供相关信息

    Args:
        image_base64: Base64编码的图片（带data:image前缀）
        location: 当前位置
        question: 用户问题

    Returns:
        识别结果和相关信息
    """
    logger.info(f"[Tool] 分析图片 - 位置: {location}, 问题: {question}")

    async def _analyze():
        try:
            async with get_http_client() as client:
                vision_service = VisionService()
                intent_data, _ = await vision_service.extract_intent(
                    image_base64, location, question, client
                )

                entity = intent_data.get("visual_entity", "未知物体")
                search_queries = intent_data.get("search_queries", [])

                result = f"识别到：{entity}"
                if search_queries:
                    result += f"\n搜索关键词：{', '.join(search_queries)}"

                return result
        except Exception as e:
            logger.error(f"[Tool] 视觉分析失败: {e}")
            return f"视觉分析失败: {str(e)}"

    try:
        return asyncio.run(_analyze())
    except Exception as e:
        logger.error(f"[Tool] 视觉分析异常: {e}")
        return f"视觉分析异常: {str(e)}"


@tool
def web_search_tool(query: str) -> str:
    """
    根据关键词进行联网搜索，获取相关信息

    Args:
        query: 搜索关键词（可以是多个关键词，用逗号分隔）

    Returns:
        搜索结果摘要
    """
    logger.info(f"[Tool] 联网搜索 - 关键词: {query}")

    async def _search():
        try:
            # 支持多个关键词
            queries = [q.strip() for q in query.split(",")]

            async with get_http_client() as client:
                search_service = SearchService()
                results = []

                for q in queries:
                    if q:  # 跳过空字符串
                        result = await search_service.search(q, client)
                        results.append(result)

                # 合并所有搜索结果
                combined_result = "\n\n".join(results)
                if combined_result:
                    # 明确标注为参考资料，与GenerationService保持一致
                    combined_result = f"【检索到的参考资料】：\n{combined_result}"
                return combined_result if combined_result else "未找到相关信息"
        except Exception as e:
            logger.error(f"[Tool] 搜索失败: {e}")
            return f"搜索失败: {str(e)}"

    try:
        return asyncio.run(_search())
    except Exception as e:
        logger.error(f"[Tool] 搜索异常: {e}")
        return f"搜索异常: {str(e)}"


@tool
def weather_query_tool(location: str) -> str:
    """
    查询指定位置的天气预报信息（最近几天）

    Args:
        location: 位置描述（如：黄山市 歙县 徽州古城）

    Returns:
        天气预报摘要
    """
    logger.info(f"[Tool] 查询天气预报 - 位置: {location}")

    async def _query_weather():
        try:
            import os
            amap_key = os.getenv("AMAP_API_KEY", "")

            if not amap_key or amap_key == "your_amap_api_key_here":
                logger.warning("[Tool] AMAP_API_KEY 未配置")
                return await _query_weather_with_hefeng(location)

            # 使用高德地图天气API
            # 提取城市名称（取位置字符串的第一部分作为城市）
            city = location.split()[0] if location else location

            url = "https://restapi.amap.com/v3/weather/weatherInfo"
            params = {
                "key": amap_key,
                "city": city,
                "extensions": "all"  # all: 返回天气预报, base: 返回实况
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url, params=params)
                response.raise_for_status()
                result = response.json()

                # 检查响应状态
                if result.get("status") != "1":
                    error_msg = result.get("info", "未知错误")
                    logger.error(f"[Tool] 高德天气API错误: {error_msg}")
                    return await _query_weather_with_hefeng(location)

                # 解析天气数据
                forecasts = result.get("forecasts", [])
                lives = result.get("lives", [])

                city_name = ""

                # 优先使用预报数据
                if forecasts and len(forecasts) > 0:
                    # 有预报数据
                    forecast_data = forecasts[0]
                    city_name = forecast_data.get("city", "")

                    # 获取多日预报
                    weather_cast = forecast_data.get("casts", [])
                    if not weather_cast:
                        logger.warning("[Tool] 预报数据为空")
                        return await _query_weather_with_hefeng(location)

                    # 构建多日天气预报
                    forecast_parts = []
                    for i, day_cast in enumerate(weather_cast[:3]):  # 取前3天
                        date_str = day_cast.get("date", "")
                        week = day_cast.get("week", "")
                        day_weather = day_cast.get("dayweather", "")
                        day_temp = day_cast.get("daytemp", "")
                        night_temp = day_cast.get("nighttemp", "")
                        weather_desc = day_cast.get("dayweather", "")
                        wind_desc = day_cast.get("daypower", "")

                        # 处理日期显示
                        if week:
                            date_display = f"{week}({date_str})"
                        else:
                            date_display = date_str

                        # 温度范围
                        temp_range = f"{night_temp}~{day_temp}°C" if day_temp and night_temp else f"{day_temp}°C"

                        # 天气描述
                        weather_info = weather_desc

                        forecast_parts.append(f"{date_display}：{weather_info}，{temp_range}")

                    reply = f"【天气预报】：{city_name}未来几天天气如下：\n" + "\n".join(forecast_parts)
                    reply += "\n\n建议根据天气情况合理安排出行，雨天记得带伞哦～"

                    logger.info(f"[Tool] 天气预报查询成功: {city_name} {len(forecast_parts)}天预报")
                    return reply

                elif lives and len(lives) > 0:
                    # 没有预报数据，使用实况
                    live_data = lives[0]
                    city_name = live_data.get("city", "")
                    weather = live_data.get("weather", "")
                    temperature = live_data.get("temperature", "")
                    winddirection = live_data.get("winddirection", "")
                    windpower = live_data.get("windpower", "")
                    humidity = live_data.get("humidity", "")

                    # 构建天气描述
                    weather_desc = f"{weather}"
                    temp_desc = f"{temperature}°C"

                    # 风力描述
                    wind_desc = ""
                    if windpower and windpower != "≤0":
                        windpower_value = windpower.replace("≤", "").strip()
                        try:
                            wind_power_num = int(windpower_value)
                            if wind_power_num <= 2:
                                wind_desc = "微风"
                            elif wind_power_num <= 5:
                                wind_desc = f"{windpower}级风"
                            else:
                                wind_desc = f"{windpower}级大风"
                        except ValueError:
                            wind_desc = f"{windpower}级风"
                    if winddirection:
                        wind_desc = f"{winddirection}风{wind_desc}" if wind_desc else f"{winddirection}风"

                    # 组装回复
                    reply = f"【天气实况】：{city_name}当前天气：{weather_desc}，{temp_desc}"
                    if wind_desc:
                        reply += f"，{wind_desc}"
                    reply += "。"

                    logger.info(f"[Tool] 天气查询成功: {city_name} {weather_desc} {temp_desc}")
                    return reply
                else:
                    logger.warning("[Tool] 高德天气API返回数据为空")
                    return await _query_weather_with_hefeng(location)

        except httpx.HTTPStatusError as e:
            logger.error(f"[Tool] 高德天气API HTTP错误: {e.response.status_code}")
            return await _query_weather_with_hefeng(location)
        except Exception as e:
            logger.error(f"[Tool] 高德天气查询异常: {e}")
            return await _query_weather_with_hefeng(location)

    async def _query_weather_with_hefeng(location: str) -> str:
        """使用和风天气API作为备用方案"""
        try:
            # 使用免费的和风天气GeoAPI
            # 先获取城市的location key
            city = location.split()[0] if location else location

            # 和风天气API（免费版）
            geo_url = "https://geoapi.qweather.com/v2/city/lookup"
            params = {"location": city, "key": "your_qweather_key"}  # 需要申请key

            # 由于和风天气也需要API key，这里返回一个通用回复
            # 建议用户配置高德API key
            logger.warning("[Tool] 天气API未配置，返回通用回复")

            # 返回一个基于常识的天气建议
            return f"【天气查询结果】：{location}的天气信息暂时无法获取。建议出行前查看当地天气预报，并根据季节准备合适的衣物。"

        except Exception as e:
            logger.error(f"[Tool] 备用天气查询失败: {e}")
            return f"天气查询暂时不可用，建议查看当地天气预报"

    try:
        return asyncio.run(_query_weather())
    except Exception as e:
        logger.error(f"[Tool] 天气查询异常: {e}")
        return f"天气查询异常: {str(e)}"


@tool
def nearby_poi_search_tool(location: str, poi_type_code: str, radius: int = 1000) -> str:
    """
    搜索用户当前位置周边的指定类型 POI（如餐厅、洗手间、停车场、便利店等）

    Args:
        location: 位置描述（如 "黄山市 徽州古城"）
        poi_type_code: POI 类型代码（如 "050100"中餐厅、"200300"洗手间、"010100"加油站）
        radius: 搜索半径（米），默认 1000，用户说"最近"时用 500，说"附近"时用 1000

    Returns:
        JSON字符串，包含POI列表及图片信息，供后续结构化处理使用
    """
    logger.info(f"[Tool] 周边POI搜索 - 位置: {location}, 类型: {poi_type_code}, 半径: {radius}m")

    async def _search():
        try:
            import json
            from services.amap_service import AmapService

            async with get_http_client() as client:
                amap_service = AmapService()

                # 1. 地理编码：位置 → 经纬度
                coordinates = await amap_service.geocode(client, location)
                if not coordinates:
                    return json.dumps({
                        "success": False,
                        "error": f"无法获取位置坐标: {location}"
                    }, ensure_ascii=False)

                # 2. 周边搜索
                pois = await amap_service.search_nearby_pois(
                    client,
                    location=coordinates,
                    poi_type=poi_type_code,
                    radius=radius,
                    page_size=10
                )

                if pois is None:
                    return json.dumps({
                        "success": False,
                        "error": "周边搜索服务暂时不可用"
                    }, ensure_ascii=False)

                if not pois:
                    return json.dumps({
                        "success": False,
                        "error": f"在 {location} 周边 {radius}米内未找到该类型的设施"
                    }, ensure_ascii=False)

                # 3. 格式化为JSON（包含照片）
                formatted_pois = []
                for poi in pois[:5]:  # 只取前5个
                    formatted_poi = {
                        "name": poi.get("name", ""),
                        "address": poi.get("address", ""),
                        "distance": poi.get("distance", "未知"),
                        "rating": poi.get("rating", "暂无"),
                        "cost": poi.get("cost", "暂无"),
                        "tag": poi.get("tag", ""),
                        "photos": poi.get("photos", [])[:1]  # 只取第一张照片
                    }
                    formatted_pois.append(formatted_poi)

                result = {
                    "success": True,
                    "count": len(formatted_pois),
                    "pois": formatted_pois
                }

                logger.info(f"[Tool] POI搜索成功: 找到 {len(formatted_pois)} 个结果")
                return json.dumps(result, ensure_ascii=False)

        except Exception as e:
            logger.error(f"[Tool] 周边搜索失败: {e}")
            import json
            return json.dumps({
                "success": False,
                "error": f"周边搜索失败: {str(e)}"
            }, ensure_ascii=False)

    try:
        return asyncio.run(_search())
    except Exception as e:
        logger.error(f"[Tool] 周边搜索异常: {e}")
        import json
        return json.dumps({
            "success": False,
            "error": f"周边搜索异常: {str(e)}"
        }, ensure_ascii=False)


# ==================== 工具列表 ====================

TOOLS = [analyze_vision_tool, web_search_tool, weather_query_tool, nearby_poi_search_tool]
