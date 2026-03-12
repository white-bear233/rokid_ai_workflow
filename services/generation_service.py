"""综合生成服务 - Stage 3: 大脑（纯文本 LLM）"""
import os
import json
import asyncio
import httpx
from utils.logger import setup_logger

logger = setup_logger(__name__)


class GenerationService:
    """纯文本生成服务 - 使用 Qwen-Max 高质量模型"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        # 使用 qwen-plus：速度更快，质量接近 Max，适合 AI 导览场景
        self.model = "qwen-plus"
        # 使用通义千问文本生成 API
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/text-generation/generation"
        self.timeout = 120.0

        # 导览模式语气映射
        self.mode_tone_map = {
            "默认模式": "专业、准确、简洁",
            "亲子模式": "活泼、亲切、生动有趣，适合小朋友理解",
            "情侣模式": "浪漫、温柔、富有诗意",
            "学术模式": "严谨、详细、引用史料",
            "故事模式": "讲故事般生动，引人入胜"
        }

    async def generate_stream(
        self,
        visual_entity: str,
        location: str,
        user_question: str,
        user_mode: str,
        search_results: str,
        client: httpx.AsyncClient
    ):
        """
        纯文本生成流式回复（不传图，只传文字）

        Args:
            visual_entity: 视觉识别的核心主体名称
            location: 用户位置
            user_question: 用户问题
            user_mode: 导览模式
            search_results: 搜索结果
            client: HTTP 客户端

        Yields:
            str: SSE 格式的流式数据
        """
        # 根据模式调整语气
        tone = self.mode_tone_map.get(user_mode, "专业、友好")

        system_prompt = (
            "你是一个专业的、语气亲切的旅游向导。请根据用户提供的位置、视觉识别出的核心主体，"
            "以及搜索引擎检索到的参考资料，回答用户的问题。\n\n"
            "【回答要求】：\n"
            "1. ⚠️ 严格基于[参考资料]中的信息回答，**严禁编造或添加资料之外的年代、人物、事件等具体信息**。\n"
            "2. 如果资料中有明确的建造时间、历史事件，请直接引用；如果资料信息模糊或矛盾，请诚实地说明。\n"
            "3. 如果资料中没有明确答案，可以结合资料介绍【核心主体】的背景，但要明确说明'根据资料显示'或'资料记载'。\n"
            "4. 直接输出回答，语气要像一个贴心的真人导游，自然流畅，严禁出现"
            "\"根据参考资料1\"、\"搜索引擎显示\"等机械式话术。\n"
            f"5. 要求字数控制在180字以内，语气要符合{user_mode}的风格（{tone}）。"
        )

        user_prompt = (
            f"【用户当前位置】：{location}\n"
            f"【用户眼前的核心主体】：{visual_entity}\n"
            f"【用户提问】：{user_question}\n\n"
            f"【检索到的参考资料】：\n{search_results}\n\n"
            f"请作为导游回答用户的问题："
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
                        "content": user_prompt
                    }
                ]
            },
            "parameters": {
                "result_format": "message",
                "max_tokens": 500
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"[Stage 3] 开始生成回复 (模式: {user_mode}, 模型: {self.model})")
            logger.debug(f"[Stage 3] 核心主体: {visual_entity}")

            # 使用非流式方式获取完整响应
            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            logger.info(f"[Stage 3] API 响应状态: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"[Stage 3] API 错误: {response.status_code} - {response.text[:200]}")
                error_msg = {"error": f"API 错误: {response.status_code}"}
                yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
                return

            result = response.json()
            logger.debug(f"[Stage 3] 响应结构: {json.dumps(result, ensure_ascii=False)[:300]}...")

            # 提取文本（文本生成 API 的返回格式与多模态不同）
            output = result.get("output", {})
            choices = output.get("choices", [])

            if not choices or len(choices) == 0:
                logger.warning("[Stage 3] 响应中没有 choices")
                yield f"data: [DONE]\n\n"
                return

            # 文本生成 API 直接返回 text 字段
            text = choices[0].get("message", {}).get("content", "")

            if not text:
                logger.warning("[Stage 3] 响应中没有文本内容")
                yield f"data: [DONE]\n\n"
                return

            logger.info(f"[Stage 3] 提取的完整文本: {text}")

            # 性能优化：直接一次性输出完整文本，不模拟流式
            # 这样可以大幅减少传输开销和客户端处理时间
            yield f"data: {json.dumps({'text': text}, ensure_ascii=False)}\n\n"

            # 发送完成信号
            yield f"data: [DONE]\n\n"
            logger.info("[Stage 3] 生成完成")

        except Exception as e:
            logger.error(f"[Stage 3] 生成失败: {type(e).__name__}: {str(e)}")
            error_msg = {"error": f"生成失败: {str(e)}"}
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
