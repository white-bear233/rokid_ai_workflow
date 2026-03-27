"""旅游规划 Agent 图构建"""
from langgraph.graph import StateGraph, END

from agent.travel.state import TravelAgentState
from agent.travel.nodes import (
    brainstorm_node,
    grounding_node,
    planner_node,
    validator_node,
    validation_router
)
from utils.logger import setup_logger

logger = setup_logger(__name__)


def create_travel_graph():
    """
    创建旅游规划 Agent 的 LangGraph

    图结构：
    START -> brainstorm -> grounding -> planner -> validator
    validator -> (validation_router) -> planner / END
    """
    logger.info("[Graph] 开始创建旅游规划 LangGraph...")

    # 创建状态图
    graph = StateGraph(TravelAgentState)

    # 添加节点
    graph.add_node("brainstorm", brainstorm_node)
    graph.add_node("grounding", grounding_node)
    graph.add_node("planner", planner_node)
    graph.add_node("validator", validator_node)

    # 设置入口点
    graph.set_entry_point("brainstorm")

    # 添加边
    # brainstorm -> grounding
    graph.add_edge("brainstorm", "grounding")

    # grounding -> planner
    graph.add_edge("grounding", "planner")

    # planner -> validator
    graph.add_edge("planner", "validator")

    # validator -> 条件路由
    graph.add_conditional_edges(
        "validator",
        validation_router,
        {
            "planner": "planner",
            "end": END
        }
    )

    # 编译图
    app = graph.compile()

    logger.info("[Graph] 旅游规划 LangGraph 创建成功")

    return app
