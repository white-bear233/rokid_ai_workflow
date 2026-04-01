"""智能导览 Agent 图构建"""
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from agent.guide.state import GuideAgentState
from agent.guide.nodes import (
    agent_node,
    vision_analysis_node,
    should_continue,
    tool_executor_node,
    structure_generator_node
)
from agent.shared.tools import TOOLS
from utils.logger import setup_logger

logger = setup_logger(__name__)


def create_guide_graph():
    """
    创建智能导览 Agent 的 LangGraph

    图结构：
    START -> agent_node
    agent_node -> (should_continue) -> tools / vision / structure_generator
    tools -> tool_executor -> agent_node
    vision -> agent_node
    structure_generator -> END
    """
    logger.info("[Graph] 开始创建导览 LangGraph...")

    # 创建状态图
    graph = StateGraph(GuideAgentState)

    # 添加节点
    graph.add_node("agent", agent_node)
    graph.add_node("tools", ToolNode(TOOLS))
    graph.add_node("tool_executor", tool_executor_node)
    graph.add_node("vision", vision_analysis_node)
    graph.add_node("structure_generator", structure_generator_node)

    # 设置入口点
    graph.set_entry_point("agent")

    # 添加边
    # agent -> 工具/视觉分析/结构化生成
    graph.add_conditional_edges(
        "agent",
        should_continue,
        {
            "tools": "tools",
            "vision": "vision",
            "end": "structure_generator"  # 修改：跳转到结构化生成
        }
    )

    # 工具 -> tool_executor -> agent
    graph.add_edge("tools", "tool_executor")
    graph.add_edge("tool_executor", "agent")

    # 视觉分析 -> agent
    graph.add_edge("vision", "agent")

    # 结构化生成 -> END
    graph.add_edge("structure_generator", END)

    # 编译图
    app = graph.compile()

    logger.info("[Graph] 导览 LangGraph 创建成功")

    return app
