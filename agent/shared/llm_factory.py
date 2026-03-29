"""LLM 工厂模块 - 统一管理 LLM 初始化"""
import os
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.messages import BaseMessage


def create_llm(
    model: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 3000,
    timeout: float = 120.0
) -> ChatOpenAI:
    """
    创建 LLM 实例

    默认使用通义千问 qwen-plus，通过 ChatOpenAI 兼容层调用

    Args:
        model: 模型名称，默认从环境变量 LLM_MODEL 读取，否则使用 qwen-plus
        temperature: 温度参数，控制随机性
        max_tokens: 最大输出 token 数
        timeout: 请求超时时间（秒）

    Returns:
        ChatOpenAI: LLM 实例

    Raises:
        ValueError: 当 API Key 未配置时
    """
    api_key = os.getenv("DASHSCOPE_API_KEY", "")
    if not api_key:
        raise ValueError("DASHSCOPE_API_KEY 未配置")

    # 支持通过环境变量或参数指定模型
    if model is None:
        model = os.getenv("LLM_MODEL", "qwen-plus")

    # 使用通义千问的兼容端点
    llm = ChatOpenAI(
        model=model,
        openai_api_key=api_key,
        openai_api_base="https://dashscope.aliyuncs.com/compatible-mode/v1",
        temperature=temperature,
        max_tokens=max_tokens,
        timeout=timeout
    )

    return llm
