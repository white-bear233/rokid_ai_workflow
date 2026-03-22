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
from services.search_service import SearchService
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
        f"- 视觉识别主体：{state.get('visual_entity', '未知')}\n"
        f"- 问题类型：{state.get('question_type', '未知')}\n"
        f"- 图片描述：{state.get('image_description', '无')}\n"
        f"- 导览模式：{state['user_mode']}（{tone}）\n\n"
        "【图片描述使用规则】：\n"
        "根据问题类型决定是否在回答中使用图片描述：\n"
        "- ✅ identify（识别类）：必须使用完整描述\n"
        "  例：\"这是谯楼，一座古老的城门楼，青砖灰瓦，飞檐翘角...\"\n"
        "- ⚠️ factual（事实类）：可选使用描述（简短融入）\n"
        "  例：\"谯楼（这座明代城门楼）建于...\"\n"
        "- ❌ background（背景类）：通常不需要描述\n"
        "  直接介绍历史背景，不描述外观\n"
        "- ⚠️ recommend（推荐类）：可选使用描述（增强代入感）\n"
        "  例：\"眼前的徽派古建筑很值得一看...\"\n\n"
        "【资料使用原则】：\n"
        "1. **参考优先，但不盲从**：\n"
        "   - 参考资料提供信息基础，但不是唯一来源\n"
        "   - 可以结合自己的知识补充细节，但要保持谨慎\n"
        "   - 如果资料明显错误（如年代矛盾、常识错误），用自己的知识纠正\n\n"
        "2. **资料质量判断**（CoT 思维链）：\n"
        "   使用资料前，快速判断：\n"
        "   - 资料之间是否互相矛盾？\n"
        "   - 年代、数字是否合理？\n"
        "   - 是否有明显的事实错误？\n\n"
        "   判断后决定：\n"
        "   - 资料可靠 → 直接使用\n"
        "   - 资料模糊 → 说\"据记载...\"、\"史料显示...\"\n"
        "   - 资料矛盾 → 说\"关于这点，不同记载不一...\"\n"
        "   - 资料错误 → 用知识纠正，说明\"根据历史记载...\"\n\n"
        "3. **回答层次**：\n"
        "   - 确定性信息（年代、事件）→ 优先使用资料\n"
        "   - 背景性信息（文化、意义）→ 可以适度补充\n"
        "   - 感受性描述（体验、建议）→ 自由发挥\n\n"
        "【语言风格要求】：\n"
        "1. **地点冗余控制**：\n"
        "   - ❌ 避免：每句话都重复地点名称\n"
        "   - ✅ 建议：首次提到后，用\"这里\"、\"这座\"、\"该建筑\"等代词\n"
        "   - 例子：\n"
        "     * 好的：\"徽州古城的谯楼建于明初，这里是古城的门户...\"\n"
        "     * 避免：\"徽州古城的谯楼建于明初。徽州古城历史悠久...\"\n\n"
        "2. **自然表达**：\n"
        "   - ✅ 可以说：\"据说\"、\"历史上\"、\"相传\"、\"史料记载\"\n"
        "   - ❌ 避免：\"根据参考资料1\"、\"搜索引擎显示\"\n"
        "   - 💡 直接说事实，而非\"根据XX说事实\"\n\n"
        "3. **字数控制**：\n"
        f"   - 严格控制在 180 字以内（含标点）\n"
        "   - 结构：开头直答（1-2句）→ 核心信息 → 结尾总结（1句）\n"
        "   - 信息量大时，优先保留核心，删减次要\n\n"
        "4. **语气匹配**：\n"
        f"   - 严格按照 {state['user_mode']} 的风格（{tone}）\n"
        "   - 像真人导游一样自然流畅，不要机械\n\n"
        "【工具使用规则】：\n"
        "⚠️ 规则 1：当用户询问眼前具体事物时，第一步必须调用 analyze_vision_tool！\n"
        "   这不是可选项，是必须的第一步！即使位置名称已经给出了答案也要调用！\n"
        "   因为图片中有位置名称无法表达的细节（具体外观、当前状态等）\n\n"
        "   必须调用视觉工具的问题类型：\n"
        "   • 这是什么？这是什么建筑？\n"
        "   • 这栋建筑是什么时候建的？有什么历史？\n"
        "   • 这是誰？这是谁的房子？\n"
        "   • 这个地方有什么特色？\n"
        "   • 任何涉及眼前具体事物的识别或介绍问题\n\n"
        "   不要跳过视觉工具！如果位置是'南京拉贝故居'，问题是'这是什么'，\n"
        "   你不能只根据位置名称回答，必须先调用 analyze_vision_tool！\n\n"
        "规则 2：涉及气象、温度、风力、下雨情况，请调用 weather_query_tool。\n\n"
        "规则 3：涉及以下问题时，请调用 web_search_tool 进行联网搜索：\n"
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
            image_description = intent_data.get("image_description", "")
            question_type = intent_data.get("question_type", "")

            logger.info(f"[Vision Node] 分析成功: {visual_entity}")
            logger.info(f"[Vision Node] 搜索词: {search_queries}")
            logger.info(f"[Vision Node] 图片描述: {image_description}")
            logger.info(f"[Vision Node] 问题类型: {question_type}")

            # 存储到 state
            state["search_queries"] = search_queries
            state["visual_entity"] = visual_entity  # 存储识别的主体
            state["image_description"] = image_description  # 存储图片描述
            state["question_type"] = question_type  # 存储问题类型
            state["visual_analysis"] = f"识别主体：{visual_entity}"

            # 将视觉分析结果添加到消息历史
            from langchain_core.messages import ToolMessage
            state["messages"].append(
                ToolMessage(
                    content=f"✅ 视觉分析完成，【用户眼前的核心主体】：{visual_entity}",
                    tool_call_id="vision_analysis"
                )
            )

            # 🚀 自动调用联网搜索（使用 multi_search_with_dedup）
            # search_queries 始终至少包含一个搜索词
            logger.info(f"[Vision Node] 自动触发搜索，使用 {len(search_queries)} 个搜索词")

            # 直接调用 SearchService 的 multi_search_with_dedup 方法
            async with get_http_client() as search_client:
                search_service = SearchService()
                search_result = await search_service.multi_search_with_dedup(
                    search_queries,  # 直接传入列表
                    search_client
                )

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
