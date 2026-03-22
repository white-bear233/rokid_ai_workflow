"""LangGraph Agent 状态定义"""
from typing import TypedDict, Annotated, Sequence, Optional
from langchain_core.messages import BaseMessage
from langgraph.graph.message import add_messages


class GuideAgentState(TypedDict):
    """
    智能导览 Agent 的状态字典

    核心思想：
    - 无状态：每个 HTTP 请求创建独立的 State，请求结束即销毁
    - 消息累积：messages 使用 add_messages reducer，自动累积对话历史
    - 客户端输入不可变：image_base64、location 等参数在请求周期内保持不变
    """

    # 核心：记录单次 LangGraph 执行过程中的 LLM 对话消息
    # 使用 add_messages reducer，每次调用工具或生成回复时自动追加消息
    messages: Annotated[Sequence[BaseMessage], add_messages]

    # 客户端输入（不可变参数）
    image_base64: str  # Base64 编码的图片
    location: str  # 用户位置（如 "黄山市 歙县 徽州古城"）
    user_question: str  # 用户问题
    user_mode: str  # 导览模式（默认模式、亲子模式、情侣模式等）

    # 可选字段（用于存储中间结果）
    visual_analysis: Optional[str]  # 视觉分析结果
    visual_entity: Optional[str]  # 识别的主体名称
    image_description: Optional[str]  # 图片视觉描述（外观、颜色、特点，50字以内）
    question_type: Optional[str]  # 问题类型（identify/factual/background/recommend）
    search_queries: Optional[list[str]]  # 视觉分析生成的搜索词
    search_results: Optional[str]  # 搜索结果摘要
    weather_info: Optional[str]  # 天气查询结果
