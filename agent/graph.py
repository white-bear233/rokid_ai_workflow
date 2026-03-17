"""LangGraph Agent 图构建"""
import os
from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from .state import GuideAgentState
from .tools import TOOLS, web_search_tool
from services.vision_service import VisionService
from utils.http_client import get_http_client
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ==================== 1. 创建 LLM ====================

def create_llm():
    """
    创建通义千问 LLM 实例

    使用 ChatOpenAI 兼容层调用通义千问 API
    """
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未配置")

    # 使用通义千问的兼容端点
    llm = ChatOpenAI(
        model="qwen-plus",
        openai_api_key=api_key,
        openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=0.7,
        max_tokens=300,  # 限制输出长度，与GenerationService保持一致
        timeout=120.0
    )

    return llm


# ==================== 2. Agent 节点 ====================

async def agent_node(state: GuideAgentState) -> GuideAgentState:
    """
    Agent 核心节点：负责决策和生成回复

    功能：
    1. 分析用户问题，决定是否调用工具
    2. 如果需要工具，返回工具调用消息
    3. 如果不需要工具，直接生成回复
    """
    logger.info(f"[Agent] 开始处理用户问题: {state['user_question']}")

    # 导览模式语气映射（参考GenerationService）
    mode_tone_map = {
        "默认模式": "专业、准确、简洁",
        "亲子模式": "活泼、亲切、生动有趣，适合小朋友理解",
        "情侣模式": "浪漫、温柔、富有诗意",
        "学术模式": "严谨、详细、引用史料",
        "故事模式": "讲故事般生动，引人入胜"
    }

    tone = mode_tone_map.get(state['user_mode'], "专业、友好")

    # 构建 System Prompt（参考GenerationService的精细设计）
    system_prompt = (
        "你是一个专业的、语气亲切的旅游向导。请根据用户提供的位置、视觉识别出的核心主体，"
        "以及搜索引擎检索到的参考资料，回答用户的问题。\n\n"
        "【重要信息】：\n"
        f"- 用户当前位置：{state['location']}\n"
        f"- 用户已提供图片，如需识别图片内容请调用 analyze_vision_tool\n"
        f"- 导览模式：{state['user_mode']}（{tone}）\n\n"
        "【回答要求】：\n"
        "1. ⚠️ 严格基于[参考资料]中的信息回答，**严禁编造或添加资料之外的年代、人物、事件等具体信息**。\n"
        "2. 如果资料中有明确的建造时间、历史事件，请直接引用；如果资料信息模糊或矛盾，请诚实地说明。\n"
        "3. 如果资料中没有明确答案，可以结合资料介绍【核心主体】的背景，但要明确说明'根据资料显示'或'资料记载'。\n"
        "4. 直接输出回答，语气要像一个贴心的真人导游，自然流畅，严禁出现"
        "\"根据参考资料1\"、\"搜索引擎显示\"等机械式话术。\n"
        f"5. 要求字数控制在180字以内，语气要符合{state['user_mode']}的风格。\n\n"
        "【工具使用规则】：\n"
        "1. ⚠️ 如果用户提供了图片并询问眼前事物（建筑、景点、物体等），必须先调用 analyze_vision_tool 识别图片！\n"
        "   识别类型的问题包括：\n"
        "   - 这是什么？这是什么建筑？\n"
        "   - 这栋建筑是什么时候建的？有什么历史？\n"
        "   - 这个地方有什么特色？\n"
        "   - 任何涉及眼前具体事物的识别或介绍问题\n"
        "2. 涉及气象、温度、风力、下雨情况，请调用 weather_query_tool。\n"
        "3. 涉及以下问题时，请调用 web_search_tool 进行联网搜索：\n"
        "   - 美食推荐、特色小吃、餐厅\n"
        "   - 景点介绍、旅游景点、值得看的地方\n"
        "   - 历史背景、文化介绍、建筑历史\n"
        "   - 交通路线、出行建议\n"
        "   - 住宿推荐、购物指南\n"
        "   - 其他需要实时信息或详细知识的问题\n\n"
        "【注意事项】：\n"
        "- 优先使用工具获取信息，不要仅凭知识回答\n"
        "- 收集到足够信息后，直接生成最终回复，不要再次调用工具\n"
        "- 视觉分析会返回识别主体，搜索会返回参考资料，请综合这些信息回答"
    )

    # 构建消息列表（在用户消息中包含位置信息）
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"当前位置：{state['location']}\n用户问题：{state['user_question']}")
    ]

    # 添加历史消息（如果有）
    if state.get("messages"):
        messages.extend(state["messages"])

    # 调用 LLM
    llm = create_llm()
    llm_with_tools = llm.bind_tools(TOOLS)

    response = await llm_with_tools.ainvoke(messages)

    logger.info(f"[Agent] LLM 响应类型: {type(response).__name__}")
    logger.debug(f"[Agent] LLM 响应内容: {response.content[:100] if hasattr(response, 'content') else response}")

    # 更新状态 - 追加而不是覆盖
    if "messages" not in state:
        state["messages"] = []
    state["messages"].append(response)

    return state


# ==================== 3. 视觉分析节点（特殊处理）====================

async def vision_analysis_node(state: GuideAgentState) -> GuideAgentState:
    """
    视觉分析节点：调用视觉服务分析图片，并自动触发联网搜索

    注意：这个节点需要单独处理，因为视觉服务需要图片数据
    """
    logger.info("[Vision Node] 开始分析图片...")

    try:
        async with get_http_client() as client:
            vision_service = VisionService()
            intent_data, _ = await vision_service.extract_intent(
                state["image_base64"],
                state["location"],
                state["user_question"],
                client
            )

            visual_entity = intent_data.get("visual_entity", "")
            search_queries = intent_data.get("search_queries", [])

            logger.info(f"[Vision Node] 分析成功: {visual_entity}")
            logger.info(f"[Vision Node] 搜索词: {search_queries}")

            # 存储搜索词到 state
            state["search_queries"] = search_queries
            state["visual_analysis"] = f"识别主体：{visual_entity}"

            # 将视觉分析结果添加到消息历史
            from langchain_core.messages import ToolMessage
            state["messages"].append(
                ToolMessage(
                    content=f"✅ 视觉分析完成，【用户眼前的核心主体】：{visual_entity}",
                    tool_call_id="vision_analysis"
                )
            )

            # 🚀 自动调用联网搜索工具
            if search_queries:
                logger.info(f"[Vision Node] 自动触发搜索，使用 {len(search_queries)} 个搜索词")

                # 将搜索词列表转换为逗号分隔的字符串
                search_query_str = ", ".join(search_queries)

                # 调用搜索工具
                search_result = await web_search_tool(search_query_str)

                # 存储搜索结果
                state["search_results"] = search_result

                # 将搜索结果添加到消息历史
                state["messages"].append(
                    ToolMessage(
                        content=search_result,
                        tool_call_id="auto_search"
                    )
                )

                logger.info(f"[Vision Node] 搜索完成，结果长度: {len(search_result)}")

    except Exception as e:
        logger.error(f"[Vision Node] 处理失败: {str(e)}", exc_info=True)
        error_msg = f"视觉分析失败: {str(e)}"

        from langchain_core.messages import ToolMessage
        state["messages"].append(
            ToolMessage(
                content=error_msg,
                tool_call_id="vision_analysis"
            )
        )

    return state


# ==================== 4. 工具条件路由 ====================

def should_continue(state: GuideAgentState) -> Literal["tools", "vision", "end"]:
    """
    决定下一步：
    - 如果 LLM 返回了工具调用，跳转到相应的工具节点
    - 如果 LLM 返回了最终回复，结束流程
    """
    messages = state["messages"]
    last_message = messages[-1] if messages else None

    if not last_message:
        return "end"

    # 检查是否有工具调用
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        tool_name = last_message.tool_calls[0]["name"]

        logger.info(f"[Router] LLM 决定调用工具: {tool_name}")

        # 特殊处理视觉分析
        if tool_name == "analyze_vision_tool":
            return "vision"
        else:
            return "tools"

    logger.info("[Router] LLM 生成最终回复，结束流程")
    return "end"


# ==================== 5. 创建图 ====================

def create_guide_graph():
    """
    创建智能导览 Agent 的 LangGraph

    图结构：
    START -> agent_node
    agent_node -> (should_continue) -> tools / vision / END
    tools -> agent_node
    vision -> agent_node
    """
    logger.info("[Graph] 开始创建 LangGraph...")

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

    logger.info("[Graph] LangGraph 创建成功")

    return app
