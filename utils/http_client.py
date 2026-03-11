"""HTTP 客户端工具"""
import httpx
import asyncio


def get_http_client():
    """
    获取配置好的 HTTP 客户端
    禁用代理以避免本地访问问题
    """
    return httpx.AsyncClient(
        trust_env=False,
        timeout=120.0
    )


async def close_http_client(client):
    """关闭 HTTP 客户端"""
    await client.aclose()
