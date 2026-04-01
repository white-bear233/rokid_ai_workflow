"""数据模型定义"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime


# ==================== 导览响应模型 ====================

class GuideCardImage(BaseModel):
    """导览卡片图片"""
    id: str = Field(..., description="图片唯一ID")
    url: str = Field(..., description="图片URL")
    caption: str = Field(..., description="图片说明")


class GuideCardPage(BaseModel):
    """导览卡片单页"""
    text: str = Field(..., description="每页导览文字")
    image: Optional[GuideCardImage] = Field(None, description="图片信息")


class GuideCard(BaseModel):
    """导览卡片"""
    title: str = Field(..., description="推荐主题标题")
    pages: List[GuideCardPage] = Field(..., description="推荐内容数组")


class GuideResponseData(BaseModel):
    """导览响应数据"""
    guideText: str = Field(..., description="主要导览文字")
    guideCard: Optional[GuideCard] = Field(None, description="导览卡片（推荐场景）")


class GuideResponse(BaseModel):
    """导览响应"""
    code: int = Field(default=200, description="状态码")
    message: str = Field(default="success", description="消息")
    data: GuideResponseData


# ==================== 请求模型 ====================

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


class TourRequest(BaseModel):
    """旅游规划请求模型"""
    destination: str = Field(..., description="目的地，如'北京'")
    start_date: str = Field(..., description="开始日期，ISO格式如'2024-03-28'")
    end_date: str = Field(..., description="结束日期，ISO格式如'2024-03-30'")
    travel_mode: str = Field(..., description="同行人群，如'带父母'")
    intensity: str = Field(..., description="游玩强度，如'悠闲慢游'")
    preferences: List[str] = Field(default_factory=list, description="偏好列表，如['历史文化', '自然风光']")
    must_visit: List[str] = Field(default_factory=list, description="必去景点列表")
    custom_requirements: str = Field(default="", description="用户自定义要求")

    @field_validator('end_date')
    @classmethod
    def validate_dates(cls, v, info):
        """校验日期有效性"""
        start_date = info.data.get('start_date')
        if start_date:
            start = datetime.strptime(start_date, "%Y-%m-%d")
            end = datetime.strptime(v, "%Y-%m-%d")
            days = (end - start).days + 1
            if days < 1:
                raise ValueError("结束日期必须大于等于开始日期")
            if days > 15:
                raise ValueError("游玩天数不能超过15天")
        return v

    def get_days(self) -> int:
        """计算游玩天数"""
        start = datetime.strptime(self.start_date, "%Y-%m-%d")
        end = datetime.strptime(self.end_date, "%Y-%m-%d")
        return (end - start).days + 1


class JournalGenerateRequest(BaseModel):
    """游记生成请求模型"""
    photos: List[str] = Field(..., description="Base64编码的图片列表 (最多9张)")
    location_hint: str = Field(default="", description="用户提供的地点提示")
    writing_style: str = Field(default="文艺", description="写作风格：文艺/幽默/简洁/故事")
    user_mode: str = Field(default="默认模式", description="用户模式：默认模式/亲子模式/情侣模式")
    custom_requirements: str = Field(default="", description="用户自定义要求")

    @field_validator('photos')
    @classmethod
    def validate_photos(cls, v):
        """校验照片数量"""
        if not v or len(v) == 0:
            raise ValueError("至少需要1张照片")
        if len(v) > 9:
            raise ValueError("最多支持9张照片")
        return v

    @field_validator('writing_style')
    @classmethod
    def validate_writing_style(cls, v):
        """校验写作风格"""
        valid_styles = ["文艺", "幽默", "简洁", "故事"]
        if v not in valid_styles:
            raise ValueError(f"写作风格必须是以下之一: {valid_styles}")
        return v

    @field_validator('user_mode')
    @classmethod
    def validate_user_mode(cls, v):
        """校验用户模式"""
        valid_modes = ["默认模式", "亲子模式", "情侣模式"]
        if v not in valid_modes:
            raise ValueError(f"用户模式必须是以下之一: {valid_modes}")
        return v

