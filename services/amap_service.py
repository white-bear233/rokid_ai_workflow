"""高德地图 API 服务"""
import os
import httpx
from typing import Dict, List, Optional
from utils.logger import setup_logger

logger = setup_logger(__name__)


class AmapService:
    """高德地图 API 封装服务"""

    # 常见城市代码映射
    COMMON_CITYCODES = {
        "北京": "010",
        "上海": "021",
        "广州": "020",
        "深圳": "0755",
        "杭州": "0571",
        "南京": "025",
        "西安": "029",
        "成都": "028",
        "重庆": "023",
        "武汉": "027",
        "苏州": "0512",
        "天津": "022",
        "郑州": "0371",
        "长沙": "0731",
        "沈阳": "024",
        "青岛": "0532",
        "大连": "0411",
        "厦门": "0592",
        "哈尔滨": "0451",
        "济南": "0531",
        "昆明": "0871",
        "合肥": "0551",
        "太原": "0351",
        "南宁": "0771",
        "乌鲁木齐": "0991",
        "贵阳": "0851",
        "兰州": "0931",
        "南昌": "0791",
        "福州": "0591",
        "石家庄": "0311",
        "长春": "0431",
        "呼和浩特": "0471",
        "海口": "0898",
        "银川": "0951",
        "西宁": "0971",
        "拉萨": "0891",
        "台北": "02",
        "香港": "852",
        "澳门": "853"
    }

    def __init__(self):
        self.api_key = os.getenv("AMAP_API_KEY", "")
        self._citycode_cache = self.COMMON_CITYCODES.copy()  # 初始化常用城市代码
        if not self.api_key:
            logger.warning("AMAP_API_KEY 未配置")

    async def search_poi(
        self,
        client: httpx.AsyncClient,
        keywords: str,
        region: str
    ) -> Optional[Dict]:
        """
        搜索 POI（景点）

        API 文档: https://lbs.amap.com/api/webservice/guide/api/search

        Args:
            client: HTTP 客户端
            keywords: 搜索关键词（景点名）
            region: 搜索区域（城市名）

        Returns:
            Dict: POI 信息，包含 poi_id, name, location, typecode, address,
                  rating, opentime_week, cost, cover_image 等
            None: 搜索失败时
        """
        if not self.api_key:
            logger.error("AMAP_API_KEY 未配置，无法搜索 POI")
            return None

        url = "https://restapi.amap.com/v5/place/text"
        params = {
            "key": self.api_key,
            "keywords": keywords,
            "region": region,
            "show_fields": "business,photos",
            "page_size": 1
        }

        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            result = response.json()

            # 检查响应状态
            if result.get("status") != "1":
                error_msg = result.get("info", "未知错误")
                logger.error(f"[高德POI] API 错误: {error_msg}")
                return None

            # 解析 POI 数据
            pois = result.get("pois", [])
            if not pois:
                logger.warning(f"[高德POI] 未找到景点: {keywords}")
                return None

            poi = pois[0]

            # 提取所需字段
            enriched_poi = {
                "poi_id": poi.get("id", ""),
                "name": poi.get("name", keywords),
                "location": poi.get("location", ""),  # 经纬度 "lng,lat"
                "typecode": poi.get("typecode", ""),
                "address": poi.get("address", ""),
                "rating": poi.get("rating", 0.0),
                "opentime_week": poi.get("biz_ext", {}).get("open_time", ""),
                "cost": poi.get("biz_ext", {}).get("cost", ""),
                "cover_image": ""
            }

            # 提取封面图
            photos = poi.get("photos", [])
            if photos:
                enriched_poi["cover_image"] = photos[0].get("url", "")

            logger.info(f"[高德POI] 搜索成功: {poi.get('name')}")
            return enriched_poi

        except httpx.HTTPStatusError as e:
            logger.error(f"[高德POI] HTTP 错误: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"[高德POI] 搜索异常: {e}")
            return None

    async def _get_citycode(self, client: httpx.AsyncClient, city: str) -> Optional[str]:
        """
        获取城市代码（citycode），带缓存

        Args:
            client: HTTP 客户端
            city: 城市名称

        Returns:
            str: 城市代码（如 "010"），失败返回 None
        """
        # 检查缓存
        if city in self._citycode_cache:
            return self._citycode_cache[city]

        url = "https://restapi.amap.com/v3/config/district"
        params = {
            "key": self.api_key,
            "keywords": city,
            "subdistrict": "0"
        }

        try:
            response = await client.get(url, params=params, timeout=10.0)
            response.raise_for_status()
            result = response.json()

            logger.debug(f"[高德城市代码] 查询结果: {result}")

            if result.get("status") == "1":
                districts = result.get("districts", [])
                if districts:
                    district = districts[0]
                    # 尝试直接获取 citycode
                    citycode = district.get("citycode")
                    if citycode:
                        logger.info(f"[高德城市代码] 获取成功: {city} -> {citycode}")
                        self._citycode_cache[city] = citycode
                        return citycode

                    # 如果没有 citycode，尝试从 adcode 提取
                    adcode = district.get("adcode", "")
                    if adcode and len(adcode) >= 4:
                        # 副省级城市前4位，普通城市前2位+00
                        if len(adcode) == 6:
                            citycode = adcode[:4] if adcode[2:4] != "00" else adcode[:2] + "00"
                            logger.info(f"[高德城市代码] 从 adcode 提取: {city} -> {citycode}")
                            self._citycode_cache[city] = citycode
                            return citycode

            logger.warning(f"[高德城市代码] 未找到城市代码: {city}")
            return None

        except Exception as e:
            logger.error(f"[高德城市代码] 获取失败: {e}")
            return None

    async def get_weather(
        self,
        client: httpx.AsyncClient,
        city: str
    ) -> str:
        """
        获取天气预报

        API 文档: https://lbs.amap.com/api/webservice/guide/api/weatherinfo

        Args:
            client: HTTP 客户端
            city: 城市名称

        Returns:
            str: 天气预报描述
        """
        if not self.api_key:
            logger.warning("AMAP_API_KEY 未配置，返回空天气信息")
            return "天气信息暂时不可获取"

        url = "https://restapi.amap.com/v3/weather/weatherInfo"
        params = {
            "key": self.api_key,
            "city": city,
            "extensions": "all"  # all: 返回天气预报
        }

        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            result = response.json()

            # 检查响应状态
            if result.get("status") != "1":
                error_msg = result.get("info", "未知错误")
                logger.error(f"[高德天气] API 错误: {error_msg}")
                return "天气信息暂时不可获取"

            # 解析天气数据
            forecasts = result.get("forecasts", [])
            if not forecasts:
                return "天气信息暂时不可获取"

            forecast_data = forecasts[0]
            city_name = forecast_data.get("city", city)
            casts = forecast_data.get("casts", [])

            # 构建天气预报描述
            weather_parts = []
            for cast in casts[:3]:  # 取前3天
                date = cast.get("date", "")
                week = cast.get("week", "")
                day_weather = cast.get("dayweather", "")
                day_temp = cast.get("daytemp", "")
                night_temp = cast.get("nighttemp", "")

                date_display = f"{week}({date})" if week else date
                temp_range = f"{night_temp}~{day_temp}°C"

                weather_parts.append(f"{date_display}：{day_weather}，{temp_range}")

            weather_info = f"{city_name}未来几天天气：\n" + "\n".join(weather_parts)
            logger.info(f"[高德天气] 获取成功: {city_name}")

            return weather_info

        except httpx.HTTPStatusError as e:
            logger.error(f"[高德天气] HTTP 错误: {e.response.status_code}")
            return "天气信息暂时不可获取"
        except Exception as e:
            logger.error(f"[高德天气] 获取异常: {e}")
            return "天气信息暂时不可获取"

    async def get_driving_route(
        self,
        client: httpx.AsyncClient,
        origin: str,
        destination: str
    ) -> Optional[dict]:
        """
        获取驾车路线规划

        API 文档: https://lbs.amap.com/api/webservice/guide/api/direction#driving

        Args:
            client: HTTP 客户端
            origin: 起点经纬度 "lng,lat"
            destination: 终点经纬度 "lng,lat"

        Returns:
            dict: 包含 distance（米）和 duration（秒）
            None: 查询失败时
        """
        if not self.api_key:
            logger.error("[高德驾车] AMAP_API_KEY 未配置，无法规划路线")
            return None

        # 验证经纬度格式
        if not origin or not destination:
            logger.error(f"[高德驾车] 经纬度为空 - origin: {origin}, destination: {destination}")
            return None

        if "," not in origin or "," not in destination:
            logger.error(f"[高德驾车] 经纬度格式错误 - origin: {origin}, destination: {destination}")
            return None

        url = "https://restapi.amap.com/v3/direction/driving"
        params = {
            "key": self.api_key,
            "origin": origin,
            "destination": destination,
            "extensions": "base"  # 返回基础信息
        }

        logger.debug(f"[高德驾车] 请求参数: origin={origin}, destination={destination}")

        try:
            response = await client.get(url, params=params, timeout=30.0)
            response.raise_for_status()
            result = response.json()

            # 检查响应状态
            if result.get("status") != "1":
                error_msg = result.get("info", "未知错误")
                logger.error(f"[高德驾车] API 错误: {error_msg}")
                return None

            # 解析路线数据
            route = result.get("route", {})
            paths = route.get("paths", [])

            if not paths:
                logger.warning(f"[高德驾车] 未找到驾车路线: {origin} -> {destination}")
                return None

            # 获取第一个方案
            first_path = paths[0]
            distance = first_path.get("distance", "0")  # 单位：米
            duration = first_path.get("duration", "0")  # 单位：秒

            route_info = {
                "distance": int(distance) if distance else 0,
                "duration": int(duration) if duration else 0
            }

            logger.info(f"[高德驾车] 路线规划成功 - 距离: {route_info['distance']}米, 耗时: {route_info['duration']}秒")

            return route_info

        except httpx.HTTPStatusError as e:
            logger.error(f"[高德驾车] HTTP 错误: {e.response.status_code}")
            return None
        except Exception as e:
            logger.error(f"[高德驾车] 规划异常: {e}")
            return None
