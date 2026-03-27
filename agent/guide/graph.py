"""智能导览 Agent 图构建"""
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from agent.guide.state import GuideAgentState
from agent.guide.nodes import agent_node, vision_analysis_node, should_continue
from agent.shared.tools import TOOLS
from utils.logger import setup_logger

logger = setup_logger(__name__)


def create_guide_graph():
    """
    创建智能导览 Agent 的 LangGraph

    图结构：
    START -> agent_node
    agent_node -> (should_continue) -> tools / vision / END
    tools -> agent_node
    vision -> agent_node
    """
    logger.info("[Graph] 开始创建导览 LangGraph...")

    # 创建状态图
    graph = StateGraph(GuideAgentState)

    # 添加节点
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("vision", vision_analysis_node)

    # 设置入口点
    graph.set_entry_point("agent")

    # 添加边
    # agent -> 工具/视觉分析/结束
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "vision": "vision",
            "end": END
        }
    )

    # 工具 -> agent
    graph.add_edge("tools", "agent")

    # 视觉分析 -> agent
    graph.add_edge("vision", "agent")

    # 编译图
    app = graph.compile()

    logger.info("[Graph] 导览 LangGraph 创建成功")

    return app
