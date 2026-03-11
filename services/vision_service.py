"""视觉关键词提取服务"""
import json
import os
from typing import Tuple
import httpx
from utils.logger import setup_logger

logger = setup_logger(__name__)


class VisionService:
    """视觉关键词提取服务 - 使用通义千问 VL 模型"""

    def __init__(self):
        self.api_key = os.getenv("DASHSCOPE_API_KEY", "")
        self.model = "qwen-vl-plus"
        self.api_url = "https://dashscope.aliyuncs.com/api/v1/services/aigc/multimodal-generation/generation"
        self.timeout = 90.0

        if not self.api_key:
            logger.warning("DASHSCOPE_API_KEY 未配置")

    async def extract_keywords(
        self,
        image_base64: str,
        location: str,
        user_question: str,
        client: httpx.AsyncClient
    ) -> Tuple[str, str]:
        """
        从图片中提取搜索关键词

        Args:
            image_base64: Base64 编码的图片
            location: 用户位置
            user_question: 用户问题
            client: HTTP 客户端

        Returns:
            Tuple[str, str]: (关键词, 原始响应)

        Raises:
            ValueError: 提取失败或关键词为空
        """
        system_prompt = (
            f"你是一个图像分析专家。用户当前位置在{location}。"
            f"请观察图片并结合用户提问 '{user_question}'，"
            f"提取出最有利于在搜索引擎上查找背景资料的关键词（不超过5个词，用空格隔开）。"
            f"【严格指令】：绝对不要输出任何解释性句子，严禁闲聊！"
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
                            {"text": f"请帮我提取关键词"}
                        ]
                    }
                ]
            },
            "parameters": {
                "result_format": "message",
                "max_tokens": 100
            }
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            logger.info(f"[Step 1] 开始请求通义千问 API...")
            logger.debug(f"[Step 1] 位置: {location}, 问题: {user_question}")

            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            logger.info(f"[Step 1] API 响应状态: {response.status_code}")
            logger.debug(f"[Step 1] API 响应结构: {list(result.keys())}")

            # 安全解析关键词
            if "output" not in result:
                raise ValueError(f"响应缺少 output 字段: {result}")

            if "choices" not in result["output"] or len(result["output"]["choices"]) == 0:
                raise ValueError(f"响应缺少 choices 字段: {result}")

            message = result["output"]["choices"][0].get("message", {})
            content = message.get("content", [])

            if not content or len(content) == 0:
                raise ValueError(f"响应内容为空: {message}")

            keywords = content[0].get("text", "").strip()

            if not keywords:
                raise ValueError("提取的关键词为空")

            logger.info(f"[Step 1] 提取的关键词: {keywords}")
            return keywords, result

        except httpx.HTTPStatusError as e:
            error_msg = f"API 错误 {e.response.status_code}: {e.response.text[:200]}"
            logger.error(f"[Step 1] {error_msg}")
            raise ValueError(error_msg)
        except Exception as e:
            logger.error(f"[Step 1] 异常: {type(e).__name__}: {str(e)}")
            raise
