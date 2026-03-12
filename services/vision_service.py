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
            "你是一个专业的旅游问答意图分析专家。你的任务是结合用户提供的【当前位置】、【拍摄的图片】以及【提出的问题】，提取出最有利于搜索引擎检索的关键词组合。\n\n"
            "【提取规则】\n"
            "1. 识别图片的核心主体，提取名称（如：谯楼/臭鳜鱼）。\n"
            "2. ⚠️ **重要：每个独立概念之间必须用空格隔开，绝对不能连成长句！**\n"
            "3. 生成 3 个不同颗粒度的搜索词组合：\n"
            "   - [精确搜索词]：位置关键词 + 具体视觉主体 + 问题意图词（全部用空格分隔）\n"
            "   - [主体搜索词]：位置关键词 + 视觉主体名称 + 背景介绍词（全部用空格分隔）\n"
            "   - [泛化搜索词]：位置关键词 + 更大范围景点/类别 + 历史特色词（全部用空格分隔）\n\n"
            "【输出格式】（严格输出 JSON，不要输出任何其他内容）\n"
            '{\n'
            '  "visual_entity": "图片中的核心主体名称",\n'
            '  "search_queries": [\n'
            '    "精确搜索词（空格分隔）",\n'
            '    "主体搜索词（空格分隔）",\n'
            '    "泛化搜索词（空格分隔）"\n'
            '  ]\n'
            '}\n\n'
            "【正确示例】\n"
            "位置：黄山市 歙县 徽州古城\n"
            "问题：这个建筑是什么时候建造的？\n"
            "返回：\n"
            '{\n'
            '  "visual_entity": "谯楼",\n'
            '  "search_queries": [\n'
            '    "歙县 徽州古城 谯楼 建造年代",\n'
            '    "歙县 徽州古城 谯楼 历史介绍",\n'
            '    "徽州古城 古建筑 历史特色"\n'
            '  ]\n'
            '}\n\n'
            "【错误示例（避免）】\n"
            "❌ \"歙县徽州古城谯楼建造年代\" （错误：连成长句）\n"
            "✅ \"歙县 徽州古城 谯楼 建造年代\" （正确：空格分隔）"
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

            # 验证 JSON 结构
            if "visual_entity" not in intent_data:
                raise ValueError(f"JSON 缺少 visual_entity 字段: {intent_data}")
            if "search_queries" not in intent_data or not isinstance(intent_data["search_queries"], list):
                raise ValueError(f"JSON 缺少 search_queries 字段或格式错误: {intent_data}")
            if len(intent_data["search_queries"]) != 3:
                raise ValueError(f"search_queries 必须包含 3 个搜索词: {intent_data}")

            logger.info(f"[Stage 1] 提取成功 - 视觉主体: {intent_data['visual_entity']}")
            logger.info(f"[Stage 1] 搜索词: {intent_data['search_queries']}")

            return intent_data, result

        except httpx.HTTPStatusError as e:
            error_msg = f"API 错误 {e.response.status_code}: {e.response.text[:200]}"
            logger.error(f"[Stage 1] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"[Stage 1] 异常: {type(e).__name__}: {str(e)}")
            raise
