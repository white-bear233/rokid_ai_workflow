"""视觉意图分析服务 - Stage 1: 眼睛"""
import json
import os
from typing import Dict, Tuple
import httpx
from utils.logger import setup_logger

logger = setup_logger(__name__)


class VisionService:
    """视觉意图分析服务 - 使用通义千问 VL 模型（Qwen-VL-Plus）"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.model = "qwen-vl-plus"
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        self.timeout = 90.0

        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY 未配置")

    async def extract_intent(
        self,
        image_base64: str,
        location: str,
        user_question: str,
        client: httpx.AsyncClient
    ) -> Tuple[Dict, str]:
        """
        从图片中提取视觉意图和3个不同颗粒度的搜索词

        Args:
            image_base64: Base64 编码的图片
            location: 用户位置
            user_question: 用户问题
            client: HTTP 客户端

        Returns:
            Tuple[Dict, str]: (visual_entity + search_queries, 原始响应)

        Raises:
            ValueError: 提取失败或解析失败
        """
        system_prompt = (
            "你是一个专业的旅游问答意图分析专家。你的任务是分析用户提供的【图片】、【位置】、【问题】，"
            "结合你自己的知识，生成最精准的搜索关键词。\n\n"
            "【分析流程】（CoT 思维链）：\n\n"
            "步骤 1：识别核心主体\n"
            "- 从图片中识别主要物体（建筑/景点/食物等）\n"
            "- 提取名称（如：谯楼、故宫、臭鳜鱼）\n\n"
            "步骤 2：判断问题类型\n"
            "- factual（事实性）：年代、人物、数字等\n"
            "- background（背景性）：历史、文化、特色、故事\n"
            "- identify（识别性）：是什么\n"
            "- recommend（推荐性）：推荐、建议\n\n"
            "步骤 3：评估搜索策略\n"
            "问自己：\n"
            "1. 主体是否足够知名？\n"
            "   - 知名（故宫、长城、天安门）→ 可以不加地点\n"
            "   - 不知名（谯楼）→ 需要加地点\n\n"
            "2. 问题类型是什么？\n"
            "   - 事实性（年代）→ 主体 + 事实词\n"
            "   - 背景性（历史）→ 主体 + 背景词\n"
            "   - 推荐性（推荐）→ 位置 + 推荐词\n\n"
            "步骤 4：生成搜索词\n"
            "规则：\n"
            "- ⚠️ 必须至少生成 1 个搜索词\n"
            "- ⚠️ 搜索词必须包含 visual_entity（识别的主体名称）\n"
            "- 每个独立概念用空格分隔，不要连成长句\n"
            "- 地点只在需要时加\n"
            "- 生成 1-2 个精准词，不要泛化\n\n"
            "步骤 5：描述图片内容\n"
            "- 结合识别主体，描述图片中具体是什么\n"
            "- 限制在 50 字以内\n"
            "- 输出到 JSON 中的 image_description 字段\n\n"
            "【地点使用规则】：\n"
            "✅ 必须加：\n"
            "  - 同名建筑（钟楼、城门、文庙）\n"
            "  - 地方特产（臭鳜鱼、毛豆腐）\n"
            "  - 推荐类问题\n\n"
            "⚠️ 可选加：\n"
            "  - 地方性建筑（谯楼、许国石坊）\n\n"
            "❌ 不需要加：\n"
            "  - 通用类别（徽派建筑、古建筑）\n"
            "  - 知名建筑（故宫、长城）\n\n"
            "【输出格式】（严格输出 JSON）：\n"
            '{\n'
            '  "visual_entity": "核心主体名称",\n'
            '  "question_type": "factual/background/identify/recommend",\n'
            '  "image_description": "主体名称 + 建筑类型/特征 + 外观特点，50字以内",\n'
            '  "search_queries": [\n'
            '    "搜索词1（必须包含，至少要有主体名称）",\n'
            '    "搜索词2（可选）"\n'
            '  ]\n'
            '}\n\n'
            "⚠️ 重要约束：\n"
            "- search_queries 必须至少包含 1 个搜索词\n"
            "- 搜索词必须包含 visual_entity（识别的主体）\n\n"
            "【场景示例】\n\n"
            "📍 场景 1：地方性建筑 + 事实性问题\n"
            "位置：黄山市 歙县 徽州古城\n"
            "图片：谯楼\n"
            "问题：这个建筑是什么时候建的？\n"
            '{\n'
            '  "visual_entity": "谯楼",\n'
            '  "question_type": "factual",\n'
            '  "search_queries": ["歙县 谯楼 建造年代"]\n'
            '}\n\n'
            "📍 场景 2a：知名建筑 + 识别性问题\n"
            "位置：北京市\n"
            "图片：天安门\n"
            "问题：这是什么？\n"
            '{\n'
            '  "visual_entity": "天安门",\n'
            '  "question_type": "identify",\n'
            '  "search_queries": ["天安门"]\n'
            '}\n\n'
            "📍 场景 2b：不知名建筑 + 识别性问题\n"
            "位置：黄山市 歙县 徽州古城\n"
            "图片：许国石坊\n"
            "问题：这是什么？\n"
            '{\n'
            '  "visual_entity": "许国石坊",\n'
            '  "question_type": "identify",\n'
            '  "search_queries": ["歙县 许国石坊 介绍"]\n'
            '}\n\n'
            "📍 场景 3：地方特产 + 背景性问题\n"
            "位置：黄山市 歙县\n"
            "图片：臭鳜鱼\n"
            "问题：这个有什么特色？\n"
            '{\n'
            '  "visual_entity": "臭鳜鱼",\n'
            '  "question_type": "background",\n'
            '  "search_queries": ["徽州 臭鳜鱼 特色 起源"]\n'
            '}\n\n'
            "📍 场景 4：推荐性问题\n"
            "位置：徽州古城\n"
            "图片：街道\n"
            "问题：附近有什么好吃的？\n"
            '{\n'
            '  "visual_entity": "徽州古城街道",\n'
            '  "question_type": "recommend",\n'
            '  "search_queries": ["徽州古城 美食 推荐", "徽州古城 小吃"]\n'
            '}\n\n'
            "【错误示例（避免）】\n"
            "❌ \"歙县徽州古城谯楼建造年代\" （错误：连成长句）\n"
            "❌ {\"search_queries\": []} （错误：必须至少包含一个搜索词）\n"
            "❌ {\"search_queries\": [\"建造年代\"]} （错误：不包含主体）\n"
            "✅ {\"search_queries\": [\"歙县 谯楼 建造年代\"]} （正确：包含主体，空格分隔）"
        )

        payload = {
            "model": self.model,
            "input": {
                "messages": [
                    {
                        "role": "system",
                        "content": system_prompt
                    },
                    {
                        "role": "user",
                        "content": [
                            {"image": image_base64},
                            {"text": f"当前位置：{location}\n用户问题：{user_question}\n\n请分析图片并按要求输出 JSON。"}
                        ]
                    }
                ]
            },
            "parameters": {
                "result_format": "message",
                "max_tokens": 300
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"[Stage 1] 开始请求通义千问 VL API...")
            logger.debug(f"[Stage 1] 位置: {location}, 问题: {user_question}")

            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            logger.info(f"[Stage 1] API 响应状态: {response.status_code}")
            logger.debug(f"[Stage 1] API 响应结构: {list(result.keys())}")

            # 安全解析响应
            if "output" not in result:
                raise ValueError(f"响应缺少 output 字段: {result}")

            if "choices" not in result["output"] or len(result["output"]["choices"]) == 0:
                raise ValueError(f"响应缺少 choices 字段: {result}")

            message = result["output"]["choices"][0].get("message", {})
            content = message.get("content", [])

            if not content or len(content) == 0:
                raise ValueError(f"响应内容为空: {message}")

            raw_text = content[0].get("text", "").strip()

            if not raw_text:
                raise ValueError("提取的文本为空")

            # 解析 JSON
            try:
                # 尝试直接解析
                intent_data = json.loads(raw_text)
            except json.JSONDecodeError:
                # 尝试提取 JSON 部分
                import re
                json_match = re.search(r'\{[\s\S]*\}', raw_text)
                if json_match:
                    intent_data = json.loads(json_match.group())
                else:
                    raise ValueError(f"无法从响应中提取有效 JSON: {raw_text}")

            # 验证 JSON 结构 - 兼容 visual_entity（单数）和 visual_entities（复数）
            if "visual_entity" not in intent_data and "visual_entities" not in intent_data:
                raise ValueError(f"JSON 缺少 visual_entity/visual_entities 字段: {intent_data}")

            # 统一转换为 visual_entity（单数）供后续使用
            if "visual_entities" in intent_data and "visual_entity" not in intent_data:
                entities = intent_data["visual_entities"]
                intent_data["visual_entity"] = entities[0] if entities else ""

            # question_type 是可选字段，游记场景可能不返回此字段
            if "question_type" not in intent_data:
                intent_data["question_type"] = "identify"  # 默认值
                logger.info("[Stage 1] question_type 未返回，使用默认值: identify")

            # 处理 question_type：如果包含多个类型，提取第一个有效的
            valid_types = ["factual", "background", "identify", "recommend"]
            raw_question_type = intent_data["question_type"]

            # 如果 question_type 包含空格（如 "factual background"），提取第一个有效类型
            if " " in raw_question_type:
                for word in raw_question_type.split():
                    if word in valid_types:
                        intent_data["question_type"] = word
                        logger.info(f"[Stage 1] question_type 包含多个词，自动提取: {raw_question_type} -> {word}")
                        break
                else:
                    # 如果没有找到有效类型，使用第一个
                    intent_data["question_type"] = raw_question_type.split()[0]
                    logger.warning(f"[Stage 1] question_type 无效，自动提取第一个词: {raw_question_type} -> {intent_data['question_type']}")

            # 验证 question_type 是否在有效类型中（仅当存在时才验证）
            if "question_type" in intent_data and intent_data["question_type"] not in valid_types:
                logger.warning(f"[Stage 1] question_type '{intent_data['question_type']}' 不在有效类型中，使用默认值")
                intent_data["question_type"] = "identify"

            # search_queries 是可选字段（游记场景不需要，问答场景需要）
            if "search_queries" in intent_data:
                if not isinstance(intent_data["search_queries"], list):
                    logger.warning(f"[Stage 1] search_queries 格式错误，已忽略")
                    intent_data["search_queries"] = []
                elif len(intent_data["search_queries"]) > 0:
                    # 验证搜索词是否包含主体
                    visual_entity = intent_data.get("visual_entity", "")
                    for query in intent_data["search_queries"]:
                        if visual_entity and visual_entity not in query:
                            logger.warning(f"[Stage 1] 搜索词 '{query}' 不包含主体 '{visual_entity}'")
                    logger.info(f"[Stage 1] 搜索词: {intent_data['search_queries']}")
            else:
                # 游记场景不需要 search_queries，初始化为空列表
                intent_data["search_queries"] = []

            # image_description 是可选字段，如果存在则验证长度
            if "image_description" in intent_data and intent_data["image_description"]:
                desc_len = len(intent_data["image_description"])
                if desc_len > 50:
                    logger.warning(f"[Stage 1] image_description 长度 {desc_len} 超过 50 字建议，但允许通过")

            logger.info(f"[Stage 1] 提取成功 - 视觉主体: {intent_data.get('visual_entity', '未知')}")

            return intent_data, result

        except httpx.HTTPStatusError as e:
            error_msg = f"API 错误 {e.response.status_code}: {e.response.text[:200]}"
            logger.error(f"[Stage 1] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"[Stage 1] 异常: {type(e).__name__}: {str(e)}")
            raise
