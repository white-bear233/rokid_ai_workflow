"""旅游规划 Agent 状态定义"""
from typing import TypedDict, List, Dict, Optional
from models.schemas import TourRequest


class TravelAgentState(TypedDict):
    """
    旅游规划 Agent 的状态字典

    核心思想：
    - 漏斗式架构：LLM海选 -> API验真 -> LLM排期 -> API校验 -> [重排或结束]
    - 支持循环优化：校验失败后回重排节点，最多3次
    """

    # 客户端输入（不可变）
    request: TourRequest  # 前端原始输入

    # LLM 海选结果
    raw_poi_names: List[str]  # LLM 选出的景点名称列表（15-20个）

    # API 验真结果
    enriched_pois: List[Dict]  # 高德 API 富化后的真实景点数据
    weather_info: str  # 目的地天气预报（整体描述，用于 LLM prompt）
    weather_by_date: Dict[str, str]  # 按日期索引的天气信息 {"2024-03-28": "晴 12~20°C"}

    # LLM 排期结果
    draft_itinerary: Dict  # 行程单 JSON（校验通过后作为最终结果）

    # 校验结果
    validation_errors: List[str]  # 路线校验失败的报错信息
    loop_count: int  # 重排循环次数，初始为0
