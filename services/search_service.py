"""联网搜索服务 - 使用 Bocha 博查 API"""
import os
import httpx
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SearchService:
    """Bocha 博查联网搜索服务"""

    def __init__(self):
        self.api_key = os.getenv("BOCHA_API_KEY", "")
        self.api_url = "https://api.bocha.cn/v1/web-search"
        self.timeout = 20.0

        if not self.api_key:
            logger.warning("BOCHA_API_KEY 未配置")

    async def search(self, keywords: str, client: httpx.AsyncClient) -> str:
        """
        搜索关键词并返回结果摘要

        Args:
            keywords: 搜索关键词
            client: HTTP 客户端

        Returns:
            str: 搜索结果摘要文本
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": keywords,
            "summary": True,
            "count": 10,
            "freshness": "noLimit"
        }

        try:
            logger.info(f"[Step 2] 开始搜索: {keywords}")

            response = await client.post(
                self.api_url,
                json=payload,
                headers=headers,
                timeout=self.timeout
            )
            response.raise_for_status()
            result = response.json()

            # 检查响应状态
            if result.get("code") != 200:
                logger.error(f"[Step 2] API 返回错误: {result.get('msg', 'Unknown error')}")
                return "（搜索服务返回错误，基于图片内容回答）"

            # 解析 Bocha 返回格式
            data = result.get("data", {})
            web_pages = data.get("webPages", {})
            web_results = web_pages.get("value", [])

            if web_results:
                search_snippets = []
                for item in web_results[:10]:
                    title = item.get("name", "")
                    # 优先使用 summary，其次使用 snippet
                    snippet = item.get("summary") or item.get("snippet", "")

                    if snippet:
                        if title:
                            search_snippets.append(f"• {title}: {snippet}")
                        else:
                            search_snippets.append(f"• {snippet}")

                search_results = "\n".join(search_snippets)
                logger.info(f"[Step 2] 搜索完成，获得 {len(search_snippets)} 条结果")
                return search_results
            else:
                logger.warning("[Step 2] 搜索无结果，使用空上下文")
                return "（暂无搜索结果，基于图片内容回答）"

        except httpx.HTTPStatusError as e:
            logger.error(f"[Step 2] 搜索失败 (HTTP {e.response.status_code}): {e.response.text[:200]}")
            return "（搜索服务暂时不可用，基于图片内容回答）"
        except Exception as e:
            logger.error(f"[Step 2] 搜索异常: {type(e).__name__}: {str(e)}")
            return "（搜索服务异常，基于图片内容回答）"
