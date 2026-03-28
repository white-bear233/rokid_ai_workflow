"""
POI 类型映射器
负责从 CSV 加载 POI 分类数据，提供精准和模糊匹配功能
"""
import csv
from pathlib import Path
from typing import Optional, List
from difflib import get_close_matches
from dataclasses import dataclass
from utils.logger import setup_logger

logger = setup_logger(__name__)


@dataclass
class POICategory:
    """POI 分类数据结构"""
    new_type: str      # 高德 POI 类型代码 (如 "050400")
    big_category: str  # 大类 (如 "餐饮服务")
    mid_category: str  # 中类 (如 "中餐厅")
    sub_category: str  # 小类 (如 "中餐厅")


class POIMapper:
    """POI 类型映射器 - 单例模式"""

    _instance: Optional['POIMapper'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if POIMapper._initialized:
            return

        self._categories: List[POICategory] = []
        self._type_code_map: dict = {}
        self._sub_category_map: dict = {}
        self._mid_category_map: dict = {}
        self._big_category_map: dict = {}

        POIMapper._initialized = True

    def load_from_csv(self, csv_path: str) -> bool:
        """
        从 CSV 文件加载 POI 数据

        Args:
            csv_path: CSV 文件路径

        Returns:
            bool: 加载是否成功
        """
        try:
            path = Path(csv_path)
            if not path.exists():
                logger.error(f"[POI Mapper] CSV 文件不存在: {csv_path}")
                return False

            # 清空旧数据
            self._categories.clear()
            self._type_code_map.clear()
            self._sub_category_map.clear()
            self._mid_category_map.clear()
            self._big_category_map.clear()

            with open(path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)

                for row in reader:
                    category = POICategory(
                        new_type=row['NEW_TYPE'],
                        big_category=row['大类'],
                        mid_category=row['中类'],
                        sub_category=row['小类']
                    )

                    self._categories.append(category)
                    self._type_code_map[category.new_type] = category

                    # 建立分类索引
                    self._sub_category_map.setdefault(category.sub_category, []).append(category)
                    if category.mid_category not in self._mid_category_map:
                        self._mid_category_map[category.mid_category] = []
                    if category.mid_category not in [c.mid_category for c in self._mid_category_map[category.mid_category]]:
                        self._mid_category_map[category.mid_category].append(category)

                    if category.big_category not in self._big_category_map:
                        self._big_category_map[category.big_category] = []
                    if category.big_category not in [c.big_category for c in self._big_category_map[category.big_category]]:
                        self._big_category_map[category.big_category].append(category)

            logger.info(f"[POI Mapper] 加载完成: {len(self._categories)} 条 POI 分类")
            logger.info(f"[POI Mapper] 索引统计 - 大类: {len(self._big_category_map)}, 中类: {len(self._mid_category_map)}, 小类: {len(self._sub_category_map)}")
            return True

        except Exception as e:
            logger.error(f"[POI Mapper] 加载失败: {e}")
            return False

    def match(self, user_input: str) -> Optional[str]:
        """
        匹配用户输入到 POI 类型代码

        匹配优先级:
        1. 小类精准匹配
        2. 中类精准匹配
        3. 大类精准匹配
        4. 小类模糊匹配
        5. 中类模糊匹配

        Args:
            user_input: 用户输入的 POI 类型描述

        Returns:
            str: 匹配到的 NEW_TYPE 代码，未匹配返回 None
        """
        if not user_input or not self._categories:
            return None

        user_input = user_input.strip()

        # 1. 小类精准匹配
        if user_input in self._sub_category_map:
            categories = self._sub_category_map[user_input]
            best = self._get_best_match(categories)
            logger.info(f"[POI Mapper] 小类精准匹配: {user_input} -> {best.new_type}")
            return best.new_type

        # 2. 中类精准匹配
        if user_input in self._mid_category_map:
            categories = self._mid_category_map[user_input]
            best = self._get_best_match(categories)
            logger.info(f"[POI Mapper] 中类精准匹配: {user_input} -> {best.new_type}")
            return best.new_type

        # 3. 大类精准匹配
        if user_input in self._big_category_map:
            categories = self._big_category_map[user_input]
            best = self._get_best_match(categories)
            logger.info(f"[POI Mapper] 大类精准匹配: {user_input} -> {best.new_type}")
            return best.new_type

        # 4. 模糊匹配（使用 difflib）
        all_sub_categories = list(self._sub_category_map.keys())
        all_mid_categories = list(self._mid_category_map.keys())

        # 小类模糊匹配
        matches = get_close_matches(user_input, all_sub_categories, n=1, cutoff=0.6)
        if matches:
            best_match = matches[0]
            categories = self._sub_category_map[best_match]
            best = self._get_best_match(categories)
            logger.info(f"[POI Mapper] 小类模糊匹配: {user_input} -> {best_match} -> {best.new_type}")
            return best.new_type

        # 中类模糊匹配
        matches = get_close_matches(user_input, all_mid_categories, n=1, cutoff=0.6)
        if matches:
            best_match = matches[0]
            categories = self._mid_category_map[best_match]
            best = self._get_best_match(categories)
            logger.info(f"[POI Mapper] 中类模糊匹配: {user_input} -> {best_match} -> {best.new_type}")
            return best.new_type

        logger.warning(f"[POI Mapper] 未找到匹配: {user_input}")
        return None

    def _get_best_match(self, categories: List[POICategory]) -> POICategory:
        """
        从多个匹配结果中选择最佳的一个
        优先选择 NEW_TYPE 最长的（更具体）
        """
        if len(categories) == 1:
            return categories[0]
        return max(categories, key=lambda x: len(x.new_type))

    def get_all_categories(self) -> List[POICategory]:
        """获取所有 POI 分类"""
        return self._categories

    def get_category_by_code(self, type_code: str) -> Optional[POICategory]:
        """根据类型代码获取分类信息"""
        return self._type_code_map.get(type_code)


# 全局单例
poi_mapper = POIMapper()
