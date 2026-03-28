"""智能导览 Agent 节点函数"""
from typing import Literal
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

from agent.shared.llm_factory import create_llm
from agent.shared.tools import TOOLS
from agent.guide.state import GuideAgentState
from services.vision_service import VisionService
from services.search_service import SearchService
from utils.http_client import get_http_client
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ==================== Agent 节点 ====================

async def agent_node(state: GuideAgentState) -> GuideAgentState:
    """
    Agent 核心节点：负责决策和生成回复

    功能：
    1. 分析用户问题，决定是否调用工具
    2. 如果需要工具，返回工具调用消息
    3. 如果不需要工具，直接生成回复
    """
    logger.info(f"[Agent] 开始处理用户问题: {state['user_question']}")

    # 导览模式语气映射
    mode_tone_map = {
        "默认模式": "专业、准确、简洁",
        "亲子模式": "活泼、亲切、生动有趣，适合小朋友理解",
        "情侣模式": "浪漫、温柔、富有诗意",
        "学术模式": "严谨、详细、引用史料",
        "故事模式": "讲故事般生动，引人入胜"
    }

    tone = mode_tone_map.get(state['user_mode'], "专业、友好")

    # 构建 System Prompt
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
        "2. **自然表达**：\n"
        "   - ✅ 可以说：\"据说\"、\"历史上\"、\"相传\"、\"史料记载\"\n"
        "   - ❌ 避免：\"根据参考资料1\"、\"搜索引擎显示\"\n"
        "3. **字数控制**：\n"
        f"   - 严格控制在 180 字以内（含标点）\n"
        "4. **语气匹配**：\n"
        f"   - 严格按照 {state['user_mode']} 的风格（{tone}）\n\n"
        "【常用 POI 类型代码】（调用 nearby_poi_search_tool 时使用）:\n"
        "\n"
        "🍽️ 餐饮服务:\n"
        "  中餐厅(050100):\n"
        "    - 综合酒楼(050101)、四川菜/川菜(050102)、广东菜/粤菜(050103)\n"
        "    - 山东菜/鲁菜(050104)、江苏菜(050105)、浙江菜(050106)\n"
        "    - 上海菜(050107)、湖南菜/湘菜(050108)、安徽菜/徽菜(050109)\n"
        "    - 福建菜(050110)、北京菜(050111)、湖北菜/鄂菜(050112)\n"
        "    - 东北菜(050113)、云贵菜(050114)、西北菜(050115)\n"
        "    - 老字号(050116)、火锅店(050117)、特色/地方风味餐厅(050118)\n"
        "    - 海鲜酒楼(050119)、中式素菜馆(050120)、清真菜馆(050121)\n"
        "    - 台湾菜(050122)、潮州菜(050123)\n"
        "\n"
        "  外国餐厅(050200):\n"
        "    - 西餐厅/综合风味(050201)、日本料理(050202)、韩国料理(050203)\n"
        "    - 法式餐厅(050204)、意式餐厅(050205)、泰国/越南菜(050206)\n"
        "    - 美式风味(050208)、印度风味(050209)\n"
        "\n"
        "  快餐/饮品:\n"
        "    - 快餐厅(050300)、咖啡厅(050500)、茶艺馆(050600)、甜品店(050900)\n"
        "\n"
        "🚻 生活服务:\n"
        "  - 洗手间(200300)、停车场(150900)、加油站(010100)、充电站(011100)\n"
        "\n"
        "🛒 购物服务:\n"
        "  - 便利店(060100)、超市(060400)、商场(060500)\n"
        "\n"
        "🏨 酒店住宿:\n"
        "  - 酒店(100100)、宾馆(100200)、民宿(100300)\n"
        "\n"
        "🏥 医疗健康:\n"
        "  - 医院(090100)、诊所(090200)、药店(090300)\n"
        "\n"
        "🚇 交通设施:\n"
        "  - 地铁站(150500)、公交站(150700)、出租车站(150800)\n"
        "\n"
        "🎭 休闲娱乐:\n"
        "  - 电影院(060800)、KTV(060900)\n"
        "\n"
        "🏞️ 旅游景点:\n"
        "  - 景点(110100)、公园(110100)、博物馆(110200)\n"
        "\n"
        "【工具使用规则】：\n"
        "⚠️ 规则 1：当用户询问眼前具体事物时，第一步必须调用 analyze_vision_tool！\n"
        "规则 2：涉及气象、温度、风力、下雨情况，请调用 weather_query_tool。\n"
        "规则 3：涉及景点历史背景、人物生平、广义攻略，请调用 web_search_tool。\n"
        "规则 4：当用户询问周边设施时，请调用 nearby_poi_search_tool。\n"
        "  - \"附近有没有餐厅\" → nearby_poi_search_tool(location, \"050100\", 1000)\n"
        "  - \"找个洗手间\" → nearby_poi_search_tool(location, \"200300\", 500)\n"
        "  - \"最近的加油站\" → nearby_poi_search_tool(location, \"010100\", 500)\n"
        "  - \"想吃湘菜\" → nearby_poi_search_tool(location, \"050108\", 1000)\n"
        "\n"
        "【注意事项】：\n"
        "- 优先使用工具获取信息，不要仅凭知识回答\n"
        "- 收集到足够信息后，直接生成最终回复\n"
    )

    # 构建消息列表
    messages = [
        SystemMessage(content=system_prompt),
        HumanMessage(content=f"当前位置：{state['location']}\n用户问题：{state['user_question']}")
    ]

    # 添加历史消息（如果有）
    if state.get("messages"):
        messages.extend(state["messages"])

    # 调用 LLM
    llm = create_llm(max_tokens=300)
    llm_with_tools = llm.bind_tools(TOOLS)

    response = await llm_with_tools.ainvoke(messages)

    logger.info(f"[Agent] LLM 响应类型: {type(response).__name__}")

    # 更新状态 - 追加而不是覆盖
    if "messages" not in state:
        state["messages"] = []
    state["messages"].append(response)

    return state


# ==================== 视觉分析节点 ====================

async def vision_analysis_node(state: GuideAgentState) -> GuideAgentState:
    """
    视觉分析节点：调用视觉服务分析图片，并自动触发联网搜索
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

            # 存储到 state
            state["search_queries"] = search_queries
            state["visual_entity"] = visual_entity
            state["image_description"] = image_description
            state["question_type"] = question_type
            state["visual_analysis"] = f"识别主体：{visual_entity}"

            # 将视觉分析结果添加到消息历史
            state["messages"].append(
                ToolMessage(
                    content=f"✅ 视觉分析完成，【用户眼前的核心主体】：{visual_entity}",
                    tool_call_id="vision_analysis"
                )
            )

            # 自动调用联网搜索
            logger.info(f"[Vision Node] 自动触发搜索，使用 {len(search_queries)} 个搜索词")

            async with get_http_client() as search_client:
                search_service = SearchService()
                search_result = await search_service.multi_search_with_dedup(
                    search_queries,
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

        state["messages"].append(
            ToolMessage(
                content=error_msg,
                tool_call_id="vision_analysis"
            )
        )

    return state


# ==================== 工具条件路由 ====================

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
