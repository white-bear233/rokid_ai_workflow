"""联网搜索服务 - Stage 2: 检索"""
import os
import asyncio
from typing import List, Dict
import httpx
from utils.logger import setup_logger

logger = setup_logger(__name__)


class SearchService:
    """Bocha 博查联网搜索服务 - 梯队式并发搜索与去重融合"""

    def __init__(self):
        self.api_key = os.getenv("BOCHA_API_KEY", "")
        self.api_url = "https://api.bocha.cn/v1/web-search"
        self.timeout = 20.0

        if not self.api_key:
            logger.warning("BOCHA_API_KEY 未配置")

    async def _single_search(
        self,
        query: str,
        client: httpx.AsyncClient
    ) -> List[Dict]:
        """
        单次搜索，返回网页结果列表

        Args:
            query: 搜索关键词
            client: HTTP 客户端

        Returns:
            List[Dict]: 网页结果列表，包含 url, title, snippet
        """
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "query": query,
            "summary": True,
            "count": 10,
            "freshness": "noLimit"
        }

        try:
            logger.debug(f"[Stage 2] 搜索关键词: {query}")

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
                logger.error(f"[Stage 2] API 返回错误: {result.get('msg', 'Unknown error')}")
                return []

            # 解析 Bocha 返回格式
            data = result.get("data", {})
            web_pages = data.get("webPages", {})
            web_results = web_pages.get("value", [])

            # 提取结果
            results = []
            for item in web_results:
                url = item.get("url", "")
                title = item.get("name", "")
                snippet = item.get("summary") or item.get("snippet", "")

                if url and snippet:
                    results.append({
                        "url": url,
                        "title": title,
                        "snippet": snippet
                    })

            logger.debug(f"[Stage 2] 关键词 '{query}' 获得 {len(results)} 条结果")
            return results

        except httpx.HTTPStatusError as e:
            logger.error(f"[Stage 2] 搜索失败 (HTTP {e.response.status_code}): {e.response.text[:200]}")
            return []
        except Exception as e:
            logger.error(f"[Stage 2] 搜索异常: {type(e).__name__}: {str(e)}")
            return []

    async def multi_search_with_dedup(
        self,
        search_queries: List[str],
        client: httpx.AsyncClient
    ) -> str:
        """
        并发搜索与去重融合（支持可变数量搜索词）

        Args:
            search_queries: 1-2 个精准的搜索词
            client: HTTP 客户端

        Returns:
            str: 去重后的搜索结果摘要文本
        """
        if len(search_queries) < 1 or len(search_queries) > 2:
            logger.error(f"[Stage 2] 必须提供 1-2 个搜索词，当前: {len(search_queries)}")
            return "（搜索服务异常，基于图片内容回答）"

        # 并发搜索所有关键词
        logger.info(f"[Stage 2] 开始并发搜索，共 {len(search_queries)} 个词...")
        for i, query in enumerate(search_queries):
            logger.info(f"[Stage 2] 搜索词 {i+1}: {query}")

        # 动态并发搜索
        results_list = await asyncio.gather(
            *[self._single_search(query, client) for query in search_queries]
        )

        # 动态截断策略
        # 第1个搜索词：取前 5 条
        # 第2个搜索词（如果有）：取前 3 条
        truncated_results = []
        for i, results in enumerate(results_list):
            if results:
                if i == 0:
                    truncated_results.extend(results[:5])
                else:
                    truncated_results.extend(results[:3])

        logger.info(f"[Stage 2] 截断后共 {len(truncated_results)} 条结果")

        # URL 去重
        seen_urls = set()
        unique_results = []
        for result in truncated_results:
            url = result.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(result)

        logger.info(f"[Stage 2] URL 去重后剩余 {len(unique_results)} 条结果")

        # 格式化为文本
        if unique_results:
            search_snippets = []
            for i, item in enumerate(unique_results, 1):
                title = item.get("title", "")
                snippet = item.get("snippet", "")
                if title:
                    search_snippets.append(f"[资料{i}] {title}: {snippet}")
                else:
                    search_snippets.append(f"[资料{i}] {snippet}")

            search_results = "\n".join(search_snippets)
            logger.info(f"[Stage 2] 搜索完成，获得 {len(search_snippets)} 条高质量结果")
            return search_results
        else:
            logger.warning("[Stage 2] 所有搜索均无结果，使用空上下文")
            return "（暂无搜索结果，基于图片内容回答）"

    # 保留旧接口以兼容（如果需要）
    async def search(self, keywords: str, client: httpx.AsyncClient) -> str:
        """
        兼容旧接口的单次搜索

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
            logger.info(f"[Stage 2] 开始搜索: {keywords}")

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
                logger.error(f"[Stage 2] API 返回错误: {result.get('msg', 'Unknown error')}")
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
                logger.info(f"[Stage 2] 搜索完成，获得 {len(search_snippets)} 条结果")
                return search_results
            else:
                logger.warning("[Stage 2] 搜索无结果，使用空上下文")
                return "（暂无搜索结果，基于图片内容回答）"

        except httpx.HTTPStatusError as e:
            logger.error(f"[Stage 2] 搜索失败 (HTTP {e.response.status_code}): {e.response.text[:200]}")
            return "（搜索服务暂时不可用，基于图片内容回答）"
        except Exception as e:
            logger.error(f"[Stage 2] 搜索异常: {type(e).__name__}: {str(e)}")
            return "（搜索服务异常，基于图片内容回答）"
