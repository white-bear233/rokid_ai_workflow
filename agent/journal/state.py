"""游记生成 Agent 状态定义"""
from typing import TypedDict, List, Dict, Optional


class PhotoMetadata(TypedDict):
    """单张照片的元数据"""
    # 基础信息
    photo_id: str                    # 照片唯一标识
    image_base64: str                # Base64 编码的图片

    # 视觉分析结果 (来自 VisionService)
    visual_entities: List[str]       # 识别的主体列表
    scene_type: str                  # 场景类型 (建筑/自然/人物/美食等)
    objects: List[str]               # 识别到的物体
    image_description: str           # 图片描述 (50字以内)

    # 地理位置信息 (来自 AmapService)
    location_name: str               # 地点名称
    location_address: str            # 详细地址
    location_coords: str             # 经纬度 "lng,lat"
    poi_info: Optional[Dict]         # POI 详细信息

    # 时间信息
    timestamp: Optional[str]         # 拍摄时间 (ISO 格式，需从 EXIF 提取)
    time_period: str                 # 时间段 (早晨/上午/中午/下午/傍晚/夜晚)

    # 天气推测
    weather_hint: str                # 天气推测 (晴天/阴天/雨天/雪天)

    # 标签
    tags: List[str]                  # 综合标签


class NarrativeSegment(TypedDict):
    """叙事片段"""
    segment_type: str                # 片段类型 (开篇/写景/抒情/感悟/结尾)
    photo_indices: List[int]         # 关联的照片索引
    content_prompt: str              # 写作提示
    order: int                       # 顺序


class JournalAgentState(TypedDict):
    """
    游记生成 Agent 的状态字典

    核心流程：
    1. 数据清洗：从多张照片提取结构化元数据
    2. 叙事规划：决定游记结构和叙事顺序
    3. 风格化写作：根据选定风格生成游记
    """

    # ========== 客户端输入（不可变）==========
    photos: List[str]                # Base64 编码的图片列表
    location_hint: str               # 用户提供的地点提示 (可选)
    writing_style: str               # 写作风格 (文艺/幽默/简洁/故事)
    user_mode: str                   # 用户模式 (默认模式/亲子模式/情侣模式)
    custom_requirements: str         # 用户自定义要求 (可选)

    # ========== 数据清洗节点输出 ==========
    photo_metadata_list: List[PhotoMetadata]  # 清洗后的照片元数据列表
    aggregated_tags: List[str]       # 聚合标签 (所有照片的标签汇总)
    timeline_order: List[int]        # 时间顺序 (照片索引按时间排序)
    location_sequence: List[str]     # 地点序列 (按时间排序的地点名称)

    # ========== 叙事规划节点输出 ==========
    narrative_structure: List[NarrativeSegment]  # 叙事结构
    theme: str                       # 游记主题
    emotion_curve: List[str]         # 情感曲线 (平缓/高潮/平缓)

    # ========== 风格化写作节点输出 ==========
    draft_journal: str               # 生成的游记初稿
    refined_journal: str             # 润色后的游记
    title: str                       # 游记标题

    # ========== 控制字段 ==========
    current_step: str                # 当前处理步骤
    errors: List[str]                # 错误信息列表
