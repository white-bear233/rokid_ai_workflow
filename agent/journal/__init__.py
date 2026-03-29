"""游记生成 Agent 模块

基于 LangGraph 构建的游记生成 Agent，支持：
- 多照片并发分析
- 智能叙事规划
- 多风格写作（文艺/幽默/简洁/故事）
- 多用户模式（默认/亲子/情侣）
"""
from agent.journal.graph import create_journal_graph

__all__ = ["create_journal_graph"]
