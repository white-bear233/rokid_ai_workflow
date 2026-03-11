"""数据模型定义"""
from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class GuideAnalyzeRequest(BaseModel):
    """导览分析请求模型"""
    image_base64: str = Field(..., description="Base64编码的图片 (带 data:image/... 前缀)")
    location: str = Field(..., description="用户位置描述")
    user_question: str = Field(..., description="用户提问")
    user_mode: str = Field(default="默认模式", description="导览模式：默认模式、亲子模式、情侣模式等")


class HealthResponse(BaseModel):
    """健康检查响应模型"""
    status: str = Field(default="healthy", description="服务状态")
    timestamp: str = Field(default_factory=lambda: datetime.now().isoformat(), description="时间戳")
    services: dict = Field(default_factory=dict, description="各服务状态")


class ErrorResponse(BaseModel):
    """错误响应模型"""
    error: str = Field(..., description="错误信息")
    detail: Optional[str] = Field(None, description="详细错误信息")
