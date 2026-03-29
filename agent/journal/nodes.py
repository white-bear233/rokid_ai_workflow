"""游记生成 Agent 节点函数"""
import asyncio
import json
import re
from typing import List, Dict
from langchain_core.messages import SystemMessage, HumanMessage

from agent.shared.llm_factory import create_llm
from agent.journal.state import JournalAgentState, PhotoMetadata, NarrativeSegment
from agent.journal.style_prompts import (
    build_system_prompt,
    NARRATIVE_SEGMENT_TYPES,
    SCENE_TYPE_EMOTIONS
)
from services.vision_service import VisionService
from services.amap_service import AmapService
from utils.http_client import get_http_client
from utils.logger import setup_logger

logger = setup_logger(__name__)


# ==================== 1. 数据清洗节点 ====================

async def data_cleaning_node(state: JournalAgentState) -> JournalAgentState:
    """
    数据清洗节点：从照片元数据提取关键信息

    功能：
    1. 并发调用 VisionService 分析每张照片
    2. 调用 AmapService 获取地理位置信息
    3. 推测时间和天气
    4. 生成标签

    输入：state["photos"]
    输出：state["photo_metadata_list"], state["aggregated_tags"], state["timeline_order"]
    """
    photos = state["photos"]
    location_hint = state.get("location_hint", "")

    logger.info(f"[DataCleaning] 开始清洗 {len(photos)} 张照片")
    state["current_step"] = "data_cleaning"
    state["errors"] = state.get("errors", [])
    state["photo_metadata_list"] = []

    async with get_http_client() as client:
        vision_service = VisionService()
        amap_service = AmapService()

        async def process_single_photo(photo_base64: str, index: int) -> PhotoMetadata:
            """处理单张照片"""
            try:
                logger.info(f"[DataCleaning] 处理第 {index + 1} 张照片")

                # 1. 视觉分析 - 使用 extract_intent 方法
                vision_prompt = """分析这张旅游照片，提取以下信息（JSON格式）：
{
    "visual_entities": ["主体1", "主体2"],
    "scene_type": "建筑/自然/人物/美食/街景/夜景/其他",
    "objects": ["物体1", "物体2"],
    "image_description": "50字以内的图片描述",
    "time_hint": "早晨/上午/中午/下午/傍晚/夜晚",
    "weather_hint": "晴天/阴天/雨天/雪天/无法判断"
}"""

                intent_data, _ = await vision_service.extract_intent(
                    photo_base64,
                    location_hint or "未知地点",
                    vision_prompt,
                    client
                )

                visual_entities = intent_data.get("visual_entities", [])
                scene_type = intent_data.get("scene_type", "其他")
                objects = intent_data.get("objects", [])
                image_description = intent_data.get("image_description", "")
                time_period = intent_data.get("time_hint", "白天")
                weather_hint = intent_data.get("weather_hint", "无法判断")

                # 2. 地理位置识别
                location_name = ""
                location_address = ""
                location_coords = ""
                poi_info = None

                # 从视觉主体中提取可能的地点名称
                if visual_entities and location_hint:
                    # 尝试在高德搜索
                    for entity in visual_entities[:2]:  # 最多尝试前两个
                        poi_result = await amap_service.search_poi(
                            client, entity, location_hint
                        )
                        if poi_result:
                            location_name = poi_result.get("name", entity)
                            location_address = poi_result.get("address", "")
                            location_coords = poi_result.get("location", "")
                            poi_info = poi_result
                            break

                if not location_name:
                    location_name = location_hint or "未知地点"

                # 3. 生成标签
                tags = []
                tags.extend(visual_entities[:3])  # 主体标签
                tags.append(scene_type)  # 场景标签
                if weather_hint != "无法判断":
                    tags.append(weather_hint)  # 天气标签
                tags = list(set(tags))  # 去重

                # 4. 构建元数据
                metadata: PhotoMetadata = {
                    "photo_id": f"photo_{index}",
                    "image_base64": photo_base64,
                    "visual_entities": visual_entities,
                    "scene_type": scene_type,
                    "objects": objects,
                    "image_description": image_description,
                    "location_name": location_name,
                    "location_address": location_address,
                    "location_coords": location_coords,
                    "poi_info": poi_info,
                    "timestamp": None,  # 需要从EXIF提取，此处暂不实现
                    "time_period": time_period,
                    "weather_hint": weather_hint,
                    "tags": tags
                }

                logger.info(f"[DataCleaning] 照片 {index + 1} 处理完成 - 地点: {location_name}, 场景: {scene_type}")

                return metadata

            except Exception as e:
                logger.error(f"[DataCleaning] 照片 {index + 1} 处理失败: {e}")
                state["errors"].append(f"照片 {index + 1} 处理失败: {str(e)}")

                # 返回默认元数据
                return {
                    "photo_id": f"photo_{index}",
                    "image_base64": photo_base64,
                    "visual_entities": [],
                    "scene_type": "其他",
                    "objects": [],
                    "image_description": "",
                    "location_name": location_hint or "未知地点",
                    "location_address": "",
                    "location_coords": "",
                    "poi_info": None,
                    "timestamp": None,
                    "time_period": "白天",
                    "weather_hint": "无法判断",
                    "tags": []
                }

        # 并发处理所有照片
        metadata_tasks = [
            process_single_photo(photo, i)
            for i, photo in enumerate(photos)
        ]

        metadata_list = await asyncio.gather(*metadata_tasks)
        state["photo_metadata_list"] = list(metadata_list)

        # 5. 聚合标签
        all_tags = []
        for metadata in metadata_list:
            all_tags.extend(metadata.get("tags", []))

        # 标签去重并计数
        tag_counts = {}
        for tag in all_tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1

        # 按出现次数排序
        sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)
        state["aggregated_tags"] = [tag for tag, count in sorted_tags[:10]]

        # 6. 生成时间线顺序（基于时间段）
        time_order_map = {
            "早晨": 1, "上午": 2, "中午": 3,
            "下午": 4, "傍晚": 5, "夜晚": 6, "白天": 3
        }

        indexed_photos = [
            (i, time_order_map.get(m.get("time_period", "白天"), 3))
            for i, m in enumerate(metadata_list)
        ]
        indexed_photos.sort(key=lambda x: x[1])
        state["timeline_order"] = [i for i, _ in indexed_photos]

        # 7. 生成地点序列
        location_sequence = []
        for idx in state["timeline_order"]:
            loc = metadata_list[idx].get("location_name", "")
            if loc and (not location_sequence or location_sequence[-1] != loc):
                location_sequence.append(loc)

        state["location_sequence"] = location_sequence

        logger.info(f"[DataCleaning] 数据清洗完成 - 标签数: {len(state['aggregated_tags'])}, 地点数: {len(location_sequence)}")

    return state


# ==================== 2. 叙事规划节点 ====================

async def narrative_planning_node(state: JournalAgentState) -> JournalAgentState:
    """
    叙事规划节点：根据标签组合决定写作结构

    功能：
    1. 分析照片内容和地点序列
    2. 决定叙事结构（写景→抒情→感悟→结尾）
    3. 确定游记主题
    4. 设计情感曲线

    输入：state["photo_metadata_list"], state["aggregated_tags"]
    输出：state["narrative_structure"], state["theme"], state["emotion_curve"]
    """
    metadata_list = state["photo_metadata_list"]
    aggregated_tags = state["aggregated_tags"]
    timeline_order = state["timeline_order"]
    location_sequence = state["location_sequence"]
    user_mode = state.get("user_mode", "默认模式")

    logger.info(f"[NarrativePlanning] 开始叙事规划")
    state["current_step"] = "narrative_planning"

    # 构建照片摘要
    photo_summaries = []
    for i, idx in enumerate(timeline_order):
        m = metadata_list[idx]
        photo_summaries.append({
            "index": i,
            "original_index": idx,
            "location": m.get("location_name", ""),
            "scene": m.get("scene_type", ""),
            "description": m.get("image_description", ""),
            "time_period": m.get("time_period", ""),
            "entities": m.get("visual_entities", [])
        })

    # 构建 LLM Prompt
    system_prompt = f"""你是一位资深旅游游记编辑，擅长规划游记的叙事结构。

请根据以下照片信息，规划一篇游记的叙事结构。

【照片信息】（按时间顺序）：
{json.dumps(photo_summaries, ensure_ascii=False, indent=2)}

【聚合标签】：
{', '.join(aggregated_tags)}

【地点序列】：
{' → '.join(location_sequence)}

【用户模式】：{user_mode}

【任务】：
1. 确定游记主题（如"徽州古城寻古之旅"、"春日西湖漫步"等）
2. 设计叙事结构（将照片分配到不同的叙事片段）
3. 设计情感曲线（游记的情感起伏）

【叙事片段类型】：
- 开篇：游记开头，引入主题
- 写景：描述景色、建筑、风景
- 抒情：表达感受、情感
- 感悟：旅行中的思考、领悟
- 结尾：游记收束，总结或展望

【输出格式】（严格输出 JSON）：
{{
    "theme": "游记主题",
    "narrative_structure": [
        {{
            "segment_type": "开篇/写景/抒情/感悟/结尾",
            "photo_indices": [0, 1],
            "content_prompt": "这部分要写什么内容的提示",
            "order": 1
        }}
    ],
    "emotion_curve": ["平缓", "高潮", "平缓", "温馨"]
}}

注意：
1. 每张照片至少要分配到一个片段
2. 片段顺序要符合叙事逻辑
3. 情感曲线要与内容匹配
4. 根据用户模式调整情感基调"""

    try:
        llm = create_llm(max_tokens=1500, temperature=0.7)
        messages = [SystemMessage(content=system_prompt)]
        response = await llm.ainvoke(messages)

        # 解析 JSON
        content = response.content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        plan_data = json.loads(content)

        state["theme"] = plan_data.get("theme", "旅行记录")
        state["narrative_structure"] = plan_data.get("narrative_structure", [])
        state["emotion_curve"] = plan_data.get("emotion_curve", ["平缓"])

        logger.info(f"[NarrativePlanning] 规划完成 - 主题: {state['theme']}, 片段数: {len(state['narrative_structure'])}")

    except Exception as e:
        logger.error(f"[NarrativePlanning] 规划失败: {e}")
        state["errors"] = state.get("errors", [])
        state["errors"].append(f"叙事规划失败: {str(e)}")

        # 降级：创建简单的叙事结构
        state["theme"] = "旅行记录"
        state["narrative_structure"] = [
            {
                "segment_type": "开篇",
                "photo_indices": [],
                "content_prompt": "简要介绍这次旅行的背景",
                "order": 1
            },
            {
                "segment_type": "写景",
                "photo_indices": list(range(len(metadata_list))),
                "content_prompt": "描述旅途中的景色和见闻",
                "order": 2
            },
            {
                "segment_type": "结尾",
                "photo_indices": [],
                "content_prompt": "总结这次旅行的感受",
                "order": 3
            }
        ]
        state["emotion_curve"] = ["平缓", "温馨"]

    return state


# ==================== 3. 风格化写作节点 ====================

async def styled_writing_node(state: JournalAgentState) -> JournalAgentState:
    """
    风格化写作节点：调用 LLM 生成游记

    功能：
    1. 根据选定的写作风格配置 Prompt
    2. 按叙事结构逐段生成内容
    3. 组装完整游记
    4. 生成标题

    输入：state["narrative_structure"], state["photo_metadata_list"]
    输出：state["draft_journal"], state["refined_journal"], state["title"]
    """
    writing_style = state.get("writing_style", "文艺")
    user_mode = state.get("user_mode", "默认模式")
    narrative_structure = state["narrative_structure"]
    metadata_list = state["photo_metadata_list"]
    theme = state.get("theme", "旅行记录")
    custom_requirements = state.get("custom_requirements", "")

    logger.info(f"[StyledWriting] 开始风格化写作 - 风格: {writing_style}, 模式: {user_mode}")
    state["current_step"] = "styled_writing"

    # 获取组合提示词
    system_prompt = build_system_prompt(writing_style, user_mode)

    # 构建照片描述摘要
    def get_photo_descriptions(indices: List[int]) -> str:
        """获取指定照片的描述"""
        descs = []
        for idx in indices:
            if 0 <= idx < len(metadata_list):
                m = metadata_list[idx]
                desc = m.get("image_description", "")
                loc = m.get("location_name", "")
                scene = m.get("scene_type", "")
                if desc:
                    descs.append(f"- {loc}（{scene}）：{desc}")
        return "\n".join(descs) if descs else "（无照片参考）"

    # 逐段生成
    segments_content = []

    for segment in narrative_structure:
        segment_type = segment.get("segment_type", "写景")
        photo_indices = segment.get("photo_indices", [])
        content_prompt = segment.get("content_prompt", "")

        photo_descriptions = get_photo_descriptions(photo_indices)

        # 计算本片段的字数配额（整篇游记控制在 100 字以内）
        total_segments = len(narrative_structure)
        segment_quota = max(15, 80 // total_segments)  # 每个片段的字数配额，更严格

        # 获取片段类型配置
        segment_config = NARRATIVE_SEGMENT_TYPES.get(segment_type, NARRATIVE_SEGMENT_TYPES["写景"])

        segment_prompt = f"""{system_prompt}

请根据以下照片的**真实内容**，写一句简短的游记：

【照片中的真实场景】：
{photo_descriptions}

【写作提示】：{content_prompt}

⚠️ **字数硬性要求：最多 {segment_quota} 字！超出即失败！**

要求：
1. 必须基于照片真实场景，写真景真情
2. 添加 1-2 个 emoji
3. 不要 markdown，直接输出纯文本
4. **字数绝对不能超过 {segment_quota} 字**

直接输出（{segment_quota}字以内）："""

        try:
            llm = create_llm(max_tokens=500, temperature=0.8)
            messages = [HumanMessage(content=segment_prompt)]
            response = await llm.ainvoke(messages)

            segment_content = response.content.strip()
            segments_content.append({
                "type": segment_type,
                "content": segment_content
            })

            logger.info(f"[StyledWriting] 片段 '{segment_type}' 生成完成")

        except Exception as e:
            logger.error(f"[StyledWriting] 片段 '{segment_type}' 生成失败: {e}")
            segments_content.append({
                "type": segment_type,
                "content": f"（{segment_type}部分生成失败）"
            })

    # 组装游记
    draft_parts = []
    for seg in segments_content:
        content = seg["content"]
        # 根据片段类型添加换行
        if seg["type"] == "结尾":
            draft_parts.append(f"\n{content}")
        elif seg["type"] == "开篇":
            draft_parts.append(content)
        else:
            draft_parts.append(f"\n\n{content}")

    state["draft_journal"] = "".join(draft_parts)

    # 生成标题
    title_prompt = f"""请为以下游记生成一个标题（10字以内）：

【游记主题】：{theme}
【用户模式】：{user_mode}
【游记内容】：
{state['draft_journal'][:300]}...

【风格】：{writing_style}

只输出标题，不要包含其他内容。"""

    try:
        llm = create_llm(max_tokens=50, temperature=0.9)
        messages = [HumanMessage(content=title_prompt)]
        response = await llm.ainvoke(messages)
        state["title"] = response.content.strip().replace('"', '').replace('"', '')
    except Exception as e:
        logger.error(f"[StyledWriting] 标题生成失败: {e}")
        state["title"] = theme

    # 润色（可选，根据风格决定是否需要）
    if writing_style == "文艺":
        refine_prompt = f"""请对以下游记进行润色，使其更加流畅、优美：

{state['draft_journal']}

要求：
1. 保持原意不变
2. 语言更加优美流畅
3. 修正可能的语法错误
4. 不要改变段落结构

直接输出润色后的游记，不要包含其他说明。"""

        try:
            llm = create_llm(max_tokens=1000, temperature=0.5)
            messages = [HumanMessage(content=refine_prompt)]
            response = await llm.ainvoke(messages)
            state["refined_journal"] = response.content.strip()
        except Exception as e:
            logger.error(f"[StyledWriting] 润色失败: {e}")
            state["refined_journal"] = state["draft_journal"]
    else:
        state["refined_journal"] = state["draft_journal"]

    logger.info(f"[StyledWriting] 写作完成 - 标题: {state['title']}, 字数: {len(state['refined_journal'])}")

    return state
