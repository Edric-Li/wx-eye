"""
图像对比模块
使用感知哈希算法对比图像差异
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

import imagehash
from PIL import Image


class DifferenceLevel(Enum):
    """差异级别"""

    IDENTICAL = "identical"  # 完全相同
    SIMILAR = "similar"  # 相似（微小变化）
    DIFFERENT = "different"  # 不同（明显变化）


@dataclass
class CompareResult:
    """对比结果"""

    level: DifferenceLevel
    hash_distance: int
    is_significant: bool  # 是否是有意义的变化
    description: str


class ImageComparator:
    """图像对比器"""

    def __init__(
        self,
        hash_size: int = 16,  # 哈希大小，越大越精确
        similar_threshold: int = 10,  # 相似阈值（<= 此值认为没变化）
        different_threshold: int = 15,  # 不同阈值
    ) -> None:
        self.hash_size = hash_size
        self.similar_threshold = similar_threshold
        self.different_threshold = different_threshold
        self._last_hash: imagehash.ImageHash | None = None
        self._last_image: Image.Image | None = None

    def compute_hash(self, img: Image.Image) -> imagehash.ImageHash:
        """计算图像的感知哈希"""
        return imagehash.phash(img, hash_size=self.hash_size)

    def compare(self, img1: Image.Image, img2: Image.Image) -> CompareResult:
        """对比两张图片"""
        hash1 = self.compute_hash(img1)
        hash2 = self.compute_hash(img2)
        distance = hash1 - hash2

        if distance == 0:
            return CompareResult(
                level=DifferenceLevel.IDENTICAL,
                hash_distance=distance,
                is_significant=False,
                description="图片完全相同",
            )
        elif distance <= self.similar_threshold:
            return CompareResult(
                level=DifferenceLevel.SIMILAR,
                hash_distance=distance,
                is_significant=False,
                description=f"图片相似，微小变化 (距离: {distance})",
            )
        else:
            return CompareResult(
                level=DifferenceLevel.DIFFERENT,
                hash_distance=distance,
                is_significant=True,
                description=f"图片明显不同 (距离: {distance})",
            )

    def compare_with_last(self, img: Image.Image) -> tuple[CompareResult, bool]:
        """
        与上一张图片对比

        Returns:
            Tuple[CompareResult, bool]: (对比结果, 是否是第一张图片)
        """
        current_hash = self.compute_hash(img)

        if self._last_hash is None:
            self._last_hash = current_hash
            self._last_image = img.copy()
            return (
                CompareResult(
                    level=DifferenceLevel.DIFFERENT,
                    hash_distance=0,
                    is_significant=True,
                    description="首张截图",
                ),
                True,
            )

        distance = self._last_hash - current_hash

        if distance == 0:
            result = CompareResult(
                level=DifferenceLevel.IDENTICAL,
                hash_distance=distance,
                is_significant=False,
                description="与上一张完全相同",
            )
        elif distance <= self.similar_threshold:
            result = CompareResult(
                level=DifferenceLevel.SIMILAR,
                hash_distance=distance,
                is_significant=False,
                description=f"与上一张相似 (距离: {distance})",
            )
        else:
            result = CompareResult(
                level=DifferenceLevel.DIFFERENT,
                hash_distance=distance,
                is_significant=True,
                description=f"与上一张不同 (距离: {distance})",
            )

        # 只有检测到显著变化时才更新上一张
        if result.is_significant:
            self._last_hash = current_hash
            self._last_image = img.copy()

        return result, False

    def reset(self) -> None:
        """重置状态"""
        self._last_hash = None
        self._last_image = None

    def get_last_image(self) -> Image.Image | None:
        """获取上一张有效图片"""
        return self._last_image
