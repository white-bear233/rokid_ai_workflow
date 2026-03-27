"""旅游规划 Agent 节点函数"""
import asyncio
import json
from typing import Literal, List, Dict, Optional
from langchain_core.messages import HumanMessage, SystemMessage

from agent.shared.llm_factory import create_llm
from agent.travel.state import TravelAgentState
from services.amap_service import AmapService
from utils.http_client import get_http_client
from utils.logger import setup_logger

logger = setup_logger(__name__)


# 高德 API 并发限制（每秒最多 1 个请求，避免 CUQPS_HAS_EXCEEDED_THE_LIMIT）
AMAP_RATE_LIMIT_DELAY = 0.3  # 驾车API限制较宽松，可以降低延迟


# ==================== 1. 智能海选节点 ====================

async def brainstorm_node(state: TravelAgentState) -> TravelAgentState:
    """
    智能海选节点：LLM 选出 15-20 个候选景点

    输入：state["request"]
    输出：state["raw_poi_names"]
    """
    request = state["request"]
    logger.info(f"[Brainstorm] 开始海选景点 - 目的地: {request.destination}, 天数: {request.days}")

    # 构建 Prompt
    system_prompt = f"""你是一位拥有20年经验的资深旅游规划师。

请根据用户的旅游需求，头脑风暴选出15-20个最著名、最合适的景点名称。

【用户需求】：
- 目的地：{request.destination}
- 游玩天数：{request.days}天
- 同行人群：{request.travelers}
- 游玩强度：{request.intensity}
- 兴趣偏好：{', '.join(request.preferences) if request.preferences else '无特殊偏好'}
- 必去景点：{', '.join(request.must_visit) if request.must_visit else '无'}
- 其他要求：{request.custom_requirements if request.custom_requirements else '无'}

【输出要求】：
1. 只返回景点名称，不要包含其他描述
2. 景点名称必须准确，不要编造
3. 必须包含用户指定的"必去景点"
4. 景点数量：15-20个
5. 每个景点单独一行，不要编号

【输出格式示例】：
故宫
天安门广场
长城
颐和园
..."""

    try:
        llm = create_llm(max_tokens=1000, temperature=0.8)
        messages = [SystemMessage(content=system_prompt)]
        response = await llm.ainvoke(messages)

        # 解析景点名称
        content = response.content
        poi_names = [line.strip() for line in content.strip().split('\n') if line.strip()]

        # 确保包含必去景点
        for must_visit in request.must_visit:
            if must_visit not in poi_names:
                poi_names.insert(0, must_visit)

        logger.info(f"[Brainstorm] 海选出 {len(poi_names)} 个景点")
        state["raw_poi_names"] = poi_names[:20]  # 限制最多20个

    except Exception as e:
        logger.error(f"[Brainstorm] 海选失败: {e}")
        state["raw_poi_names"] = request.must_visit  # 降级：只使用必去景点

    return state


# ==================== 2. 实体对齐与环境感知节点 ====================

def _merge_duplicate_pois(enriched_pois: List[Dict]) -> List[Dict]:
    """
    合并属于同一景区的子景点

    例如：将"杭州西湖风景名胜区-白堤"、"杭州西湖风景名胜区-三潭印月"
          合并为"杭州西湖风景名胜区"（包含多个子景点）

    Args:
        enriched_pois: 富化后的 POI 列表

    Returns:
        List[Dict]: 合并后的 POI 列表
    """
    if not enriched_pois:
        return []

    # 按主景区分组
    main_scenic_groups = {}

    for poi in enriched_pois:
        name = poi.get("name", "")

        # 识别主景区名称（去掉后缀）
        main_name = name
        if "-" in name:
            # "杭州西湖风景名胜区-白堤" -> "杭州西湖风景名胜区"
            main_name = name.split("-")[0].strip()

        if main_name not in main_scenic_groups:
            main_scenic_groups[main_name] = {
                "main_name": main_name,
                "sub_pois": [],
                "poi_data": poi
            }

        main_scenic_groups[main_name]["sub_pois"].append(name)

    # 合并 POI 数据
    merged_pois = []
    for group_data in main_scenic_groups.values():
        main_name = group_data["main_name"]
        sub_pois = group_data["sub_pois"]
        poi_data = group_data["poi_data"]

        if len(sub_pois) == 1:
            # 只有一个子景点，直接使用原数据
            merged_pois.append(poi_data)
        else:
            # 多个子景点，合并
            # 查找最合适的 POI 数据（优先使用不带后缀的，或者第一个）
            best_poi = poi_data

            # 更新 POI 信息
            merged_poi = best_poi.copy()
            merged_poi["name"] = main_name
            # 在地址或其他地方说明包含的子景点
            sub_poi_str = "、".join(sub_pois[:5])  # 最多显示5个
            if len(sub_pois) > 5:
                sub_poi_str += f" 等{len(sub_pois)}个景点"

            # 在地址或备注中说明
            original_address = merged_poi.get("address", "")
            if original_address and not original_address.endswith(")"):
                merged_poi["address"] = f"{original_address}（含{sub_poi_str}）"
            else:
                merged_poi["address"] = f"含{sub_poi_str}"

            logger.info(f"[Grounding] 合并景区: {main_name} 包含 {len(sub_pois)} 个子景点")

            merged_pois.append(merged_poi)

    logger.info(f"[Grounding] POI 去重完成: {len(enriched_pois)} -> {len(merged_pois)}")
    return merged_pois


async def grounding_node(state: TravelAgentState) -> TravelAgentState:
    """
    实体对齐与环境感知节点：并发调用高德 API 验真景点 + 获取天气

    输入：state["raw_poi_names"], state["request"].destination
    输出：state["enriched_pois"], state["weather_info"]
    """
    destination = state["request"].destination
    poi_names = state["raw_poi_names"]
    logger.info(f"[Grounding] 开始验真 {len(poi_names)} 个景点")

    async with get_http_client() as client:
        amap_service = AmapService()

        # 任务A：并发搜索所有 POI
        poi_tasks = [
            amap_service.search_poi(client, name, destination)
            for name in poi_names
        ]

        # 任务B：获取天气
        weather_task = amap_service.get_weather(client, destination)

        # 并发执行
        results = await asyncio.gather(
            *poi_tasks,
            weather_task,
            return_exceptions=True
        )

        # 解析 POI 结果（排除天气任务）
        enriched_pois = []
        for i, result in enumerate(results[:-1]):
            if isinstance(result, Exception):
                logger.warning(f"[Grounding] POI 搜索异常: {poi_names[i]} - {result}")
                continue
            if result is not None:
                enriched_pois.append(result)

        # 解析天气结果
        weather_info = results[-1]
        if isinstance(weather_info, Exception):
            logger.warning(f"[Grounding] 天气查询异常: {weather_info}")
            weather_info = "天气信息暂时不可获取"
        elif not weather_info:
            weather_info = "天气信息暂时不可获取"

        logger.info(f"[Grounding] 验真完成，成功富化 {len(enriched_pois)} 个景点")

        # 合并同一景区的子景点
        merged_pois = _merge_duplicate_pois(enriched_pois)

        state["enriched_pois"] = merged_pois
        state["weather_info"] = weather_info

    return state


# ==================== 3. 动态统筹引擎节点 ====================

async def planner_node(state: TravelAgentState) -> TravelAgentState:
    """
    动态统筹引擎节点：LLM 进行排期

    输入：state（使用 enriched_pois, weather_info, validation_errors, draft_itinerary）
    输出：state["draft_itinerary"]
    """
    request = state["request"]
    enriched_pois = state["enriched_pois"]
    weather_info = state["weather_info"]
    validation_errors = state.get("validation_errors", [])
    previous_itinerary = state.get("draft_itinerary", {})
    loop_count = state.get("loop_count", 1)

    logger.info(f"[Planner] 开始排期 - 可用景点: {len(enriched_pois)}, 第 {loop_count} 次规划")

    # 判断是初次规划还是调整
    is_adjustment = loop_count > 1 and previous_itinerary and validation_errors

    # 构建景点摘要（用于 LLM 理解）
    pois_summary = []
    for poi in enriched_pois:
        pois_summary.append(
            f"- {poi['name']} (ID: {poi['poi_id']}, 地址: {poi['address']}, "
            f"开放时间: {poi.get('opentime_week', '未知')}, "
            f"评分: {poi.get('rating', 0)})"
        )
    pois_text = "\n".join(pois_summary)

    # 构建提示信息
    error_hint = ""
    previous_hint = ""

    if is_adjustment:
        # 调整模式：显示上一次的行程和具体错误
        logger.info(f"[Planner] 调整模式 - 基于上一次行程进行修改")

        # 格式化上一次的行程（简化版，便于阅读）
        previous_summary = []
        for day_plan in previous_itinerary.get("daily_itinerary", []):
            day = day_plan.get("day", 0)
            activities = day_plan.get("activities", [])
            activity_list = [f"  - {act.get('poi_name')} ({act.get('time_window', '全天')})" for act in activities]
            previous_summary.append(f"第{day}天:\n" + "\n".join(activity_list))

        previous_hint = "\n\n【上一次的行程安排】（供参考）:\n" + "\n".join(previous_summary)

        error_hint = "\n\n【需要调整的问题】:\n" + "\n".join(validation_errors)
        error_hint += "\n\n⚠️ 调整要求：\n"
        error_hint += "1. 只调整距离超过10公里的景点对\n"
        error_hint += "2. 其他安排保持不变\n"
        error_hint += "3. 如果某天只有1-2个景点，可以适当增加景点\n"
        error_hint += "4. 确保所有必去景点都在行程中\n"
        error_hint += "5. 注意避开用餐时间（11:30-14:00、18:00-19:30）\n"
        error_hint += "6. 可以安排晚上景点（19:30之后），特别是有夜景的景点"
    else:
        # 初次规划模式
        if validation_errors:
            error_hint = "\n\n【重要提示】\n" + "\n".join(validation_errors)

    # 构建 Prompt（强制 JSON 输出）
    system_prompt = f"""你是一位专业的旅游规划师。请根据景点信息和天气情况，为用户规划详细的每日行程。

【用户需求】：
- 目的地：{request.destination}
- 游玩天数：{request.days}天
- 同行人群：{request.travelers}
- 游玩强度：{request.intensity}
- 必去景点：{', '.join(request.must_visit) if request.must_visit else '无'}

【可用景点列表】（只能从中选择，严禁捏造）：
{pois_text}

【天气情况】：
{weather_info}
{previous_hint}
{error_hint}

【排期要求】：
1. **必须包含所有必去景点**，这是硬性要求
2. 每天安排不超过3个景点（根据游玩强度调整）
3. 考虑开放时间，避免闭馆
4. 参考天气：有雨雪时优先安排室内景点
5. **相邻景点距离不超过10公里**（这是最重要的要求）
6. 只能从上述景点列表中选择，严禁使用列表外的景点

7. **时间安排细节**：
   - **避开午餐时间**：11:30-14:00 是用餐和休息时间，不要安排景点
   - **避开晚餐时间**：18:00-19:30 是用餐时间，不要安排景点
   - **晚上可以安排景点**：19:30 之后可以安排适合夜游的景点（如夜景、夜市、灯光秀等）
   - **全天开放景点优先**：对于全天开放的景点，可以灵活安排时间段

8. **游玩时间估算**：
   - 小型景点（如博物馆、小园林）：1-2小时
   - 中型景点（如雷峰塔、古镇）：2-3小时
   - 大型景区（如西湖、西溪湿地）：3-4小时或更久
   - 根据景点规模合理安排时长，不要过于匆忙

9. **适合晚上安排的景点**：
   - 有夜景灯光的景点（如雷峰塔夜景、西湖音乐喷泉）
   - 夜市、美食街（如河坊街、南宋御街）
   - 古镇夜景（如乌镇、西塘夜景）
   - 全天开放的景点可以根据需要安排晚上时段

【输出格式】（严格按 JSON 格式输出）：
{{
  "total_days": {request.days},
  "daily_itinerary": [
    {{
      "day": 1,
      "date": "第1天",
      "weather_adaptation": "晴天/雨天建议",
      "activities": [
        {{
          "time_window": "上午 9:00-12:00",
          "poi_name": "景点名称",
          "poi_id": "景点ID",
          "location": "经纬度",
          "cover_image": "封面图URL",
          "reason": "安排理由"
        }}
      ]
    }}
  ]
}}

**时间窗口参考**（根据实际情况调整）：
- 上午：9:00-12:00
- 下午：14:00-17:00 或 14:30-17:30
- 晚上：19:30-21:30（适合夜景、夜市）
- 全天：9:00-16:00（大型景区）

请直接输出 JSON，不要包含其他说明文字。"""

    try:
        # 使用 JSON 模式
        llm = create_llm(max_tokens=3000, temperature=0.7)
        messages = [SystemMessage(content=system_prompt)]
        response = await llm.ainvoke(messages)

        # 解析 JSON
        content = response.content.strip()
        # 移除可能的 markdown 代码块标记
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        itinerary = json.loads(content)

        # 添加景点详细信息
        for day_plan in itinerary.get("daily_itinerary", []):
            for activity in day_plan.get("activities", []):
                poi_id = activity.get("poi_id")
                # 从 enriched_pois 中查找详细信息
                for poi in enriched_pois:
                    if poi["poi_id"] == poi_id:
                        activity["location"] = poi["location"]
                        activity["cover_image"] = poi.get("cover_image", "")
                        break

        logger.info(f"[Planner] 排期完成，共 {itinerary.get('total_days', 0)} 天")
        state["draft_itinerary"] = itinerary

    except json.JSONDecodeError as e:
        logger.error(f"[Planner] JSON 解析失败: {e}")
        # 降级：创建简单行程
        state["draft_itinerary"] = _create_fallback_itinerary(request, enriched_pois)
    except Exception as e:
        logger.error(f"[Planner] 排期失败: {e}")
        state["draft_itinerary"] = _create_fallback_itinerary(request, enriched_pois)

    return state


def _create_fallback_itinerary(request, enriched_pois):
    """创建降级行程（当 LLM 失败时）"""
    pois_per_day = max(1, min(len(enriched_pois) // request.days, 3))
    daily_itinerary = []

    for day in range(request.days):
        start_idx = day * pois_per_day
        end_idx = min(start_idx + pois_per_day, len(enriched_pois))
        day_pois = enriched_pois[start_idx:end_idx]

        activities = []
        for poi in day_pois:
            activities.append({
                "time_window": "全天",
                "poi_name": poi["name"],
                "poi_id": poi["poi_id"],
                "location": poi["location"],
                "cover_image": poi.get("cover_image", ""),
                "reason": "根据用户偏好推荐"
            })

        daily_itinerary.append({
            "day": day + 1,
            "date": f"第{day + 1}天",
            "weather_adaptation": "根据当天天气灵活调整",
            "activities": activities
        })

    return {
        "total_days": request.days,
        "daily_itinerary": daily_itinerary
    }


# ==================== 4. 逻辑校验节点 ====================

async def validator_node(state: TravelAgentState) -> TravelAgentState:
    """
    逻辑校验节点：检查相邻景点的通勤距离

    输入：state["draft_itinerary"]
    输出：state["validation_errors"], state["loop_count"]
    """
    itinerary = state["draft_itinerary"]
    destination = state["request"].destination
    loop_count = state.get("loop_count", 0)

    logger.info(f"[Validator] 开始校验路线 (第 {loop_count + 1} 次)")

    validation_errors = []

    async with get_http_client() as client:
        amap_service = AmapService()

        # 遍历每天的活动
        for day_plan in itinerary.get("daily_itinerary", []):
            day = day_plan.get("day", 0)
            activities = day_plan.get("activities", [])

            # 检查相邻景点的通勤距离
            for i in range(len(activities) - 1):
                current = activities[i]
                next_act = activities[i + 1]

                origin = current.get("location", "")
                destination_loc = next_act.get("location", "")

                logger.debug(f"[Validator] 检查路线: {current.get('poi_name')} -> {next_act.get('poi_name')}")
                logger.debug(f"[Validator] origin: {origin}, destination: {destination_loc}")

                if not origin or not destination_loc:
                    logger.warning(f"[Validator] 跳过（缺少坐标）: {current.get('poi_name')} -> {next_act.get('poi_name')}")
                    continue

                # 避免 API 并发超限，添加延迟
                await asyncio.sleep(AMAP_RATE_LIMIT_DELAY)

                # 调用驾车路线规划 API
                route_info = await amap_service.get_driving_route(
                    client,
                    origin,
                    destination_loc
                )

                if route_info is None:
                    continue  # 查询失败，跳过

                distance = route_info.get("distance", 0)  # 单位：米
                duration = route_info.get("duration", 0)  # 单位：秒

                # 检查是否超过 10 公里（10000 米）
                if distance > 10000:
                    error_msg = (
                        f"第{day}天：从「{current.get('poi_name')}」到「{next_act.get('poi_name')}」"
                        f"距离 {distance / 1000:.1f} 公里（超过10公里），请重新安排。"
                    )
                    validation_errors.append(error_msg)
                    logger.warning(f"[Validator] {error_msg}")
                else:
                    logger.info(f"[Validator] 路线合格: {current.get('poi_name')} -> {next_act.get('poi_name')}, "
                               f"距离: {distance}米 ({distance/1000:.1f}公里)")

    # 更新状态
    loop_count += 1
    state["loop_count"] = loop_count
    state["validation_errors"] = validation_errors

    if validation_errors:
        logger.info(f"[Validator] 校验失败，发现 {len(validation_errors)} 个问题，需要重排")
    else:
        logger.info("[Validator] 校验通过，行程有效")

    return state


# ==================== 条件路由 ====================

def validation_router(state: TravelAgentState) -> Literal["planner", "end"]:
    """
    条件路由：决定是回重排还是结束

    - 有错误且 loop_count < 3 -> 回 planner
    - 否则 -> END
    """
    validation_errors = state.get("validation_errors", [])
    loop_count = state.get("loop_count", 0)

    if validation_errors and loop_count < 3:
        logger.info(f"[Router] 路由回 planner (第 {loop_count} 次重排)")
        return "planner"

    logger.info("[Router] 路由到 END")
    return "end"
