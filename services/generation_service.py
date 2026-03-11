"""综合生成服务 - 使用通义千问 VL 模型"""
import os
import json
import asyncio
import httpx
from utils.logger import setup_logger

logger = setup_logger(__name__)


class GenerationService:
    """综合多模态生成服务"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.model = "qwen-vl-plus"
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
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
        image_base64: str,
        location: str,
        user_question: str,
        user_mode: str,
        search_results: str,
        client: httpx.AsyncClient
    ):
        """
        综合图片和搜索结果生成流式回复

        Args:
            image_base64: Base64 编码的图片
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
            f"你是一位专业的导游。游客在{location}提出了问题：{user_question}。\n"
            f"请你**同时观察提供的图片**，并参考以下为你实时搜索到的最新资料：\n"
            f"{search_results}\n\n"
            f"为游客进行精准、生动的解答。请严格遵循{user_mode}的语气风格（{tone}）。"
            f"要求字数控制在180字以内，不要有多余的格式。"
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
                            {"text": f"请根据图片和搜索资料回答：{user_question}"}
                        ]
                    }
                ]
            },
            "parameters": {
                "result_format": "message",
                "incremental_output": True,
                "max_tokens": 500
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"[Step 3] 开始生成回复 (模式: {user_mode})")

            # 使用非流式方式获取完整响应
            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )

            logger.info(f"[Step 3] API 响应状态: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"[Step 3] API 错误: {response.status_code} - {response.text[:200]}")
                error_msg = {"error": f"API 错误: {response.status_code}"}
                yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
                return

            result = response.json()
            logger.info(f"[Step 3] 响应结构: {json.dumps(result, ensure_ascii=False)[:300]}...")

            # 提取文本
            output = result.get("output", {})
            choices = output.get("choices", [])

            if not choices or len(choices) == 0:
                logger.warning("[Step 3] 响应中没有 choices")
                yield f"data: [DONE]\n\n"
                return

            content = choices[0].get("message", {}).get("content", [])

            if not content or len(content) == 0:
                logger.warning("[Step 3] 响应中没有 content")
                yield f"data: [DONE]\n\n"
                return

            text = content[0].get("text", "")
            logger.info(f"[Step 3] 提取的完整文本: {text}")

            # 模拟逐字符流式输出
            if text:
                for char in text:
                    yield f"data: {json.dumps({'text': char}, ensure_ascii=False)}\n\n"
                    await asyncio.sleep(0.01)  # 小延迟模拟流式效果

            # 发送完成信号
            yield f"data: [DONE]\n\n"
            logger.info("[Step 3] 生成完成")

        except Exception as e:
            logger.error(f"[Step 3] 生成失败: {type(e).__name__}: {str(e)}")
            error_msg = {"error": f"生成失败: {str(e)}"}
            yield f"data: {json.dumps(error_msg, ensure_ascii=False)}\n\n"
