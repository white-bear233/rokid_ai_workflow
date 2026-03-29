"""游记生成 Agent 图构建"""
from langgraph.graph import StateGraph, END

from agent.journal.state import JournalAgentState
from agent.journal.nodes import (
    data_cleaning_node,
    narrative_planning_node,
    styled_writing_node
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


def create_journal_graph():
    """
    创建游记生成 Agent 的 LangGraph

    图结构（线性流程）：
    START -> data_cleaning -> narrative_planning -> styled_writing -> END

    各节点职责：
    - data_cleaning: 数据清洗，从照片提取元数据
    - narrative_planning: 叙事规划，决定游记结构
    - styled_writing: 风格化写作，生成游记内容
    """
    logger.info("[Graph] 开始创建游记生成 LangGraph...")

    # 创建状态图
    graph = StateGraph(JournalAgentState)

    # 添加节点
    graph.add_node("data_cleaning", data_cleaning_node)
    graph.add_node("narrative_planning", narrative_planning_node)
    graph.add_node("styled_writing", styled_writing_node)

    # 设置入口点
    graph.set_entry_point("data_cleaning")

    # 添加边（线性流程）
    # data_cleaning -> narrative_planning
    graph.add_edge("data_cleaning", "narrative_planning")

    # narrative_planning -> styled_writing
    graph.add_edge("narrative_planning", "styled_writing")

    # styled_writing -> END
    graph.add_edge("styled_writing", END)

    # 编译图
    app = graph.compile()

    logger.info("[Graph] 游记生成 LangGraph 创建成功")

    return app
