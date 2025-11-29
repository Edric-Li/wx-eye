"""
OCR 服务模块
使用 EasyOCR 进行跨平台文字识别（Windows/macOS/Linux）
"""

from __future__ import annotations

import hashlib
import logging
import time
from typing import TYPE_CHECKING

import numpy as np
from PIL import Image

if TYPE_CHECKING:
    import easyocr

logger = logging.getLogger(__name__)


class OCRService:
    """跨平台 OCR 服务

    使用 EasyOCR 从聊天截图中提取文字。
    支持中英文混合识别，延迟加载模型以优化启动速度。
    """

    # 用于变化检测的缩放尺寸（越小越快，但精度略降）
    DETECT_MAX_SIZE = 400

    def __init__(
        self,
        languages: list[str] | None = None,
        gpu: bool = False,
    ) -> None:
        """初始化 OCR 服务

        Args:
            languages: 识别语言列表，默认 ['ch_sim', 'en']
            gpu: 是否使用 GPU 加速
        """
        self._languages = languages or ["ch_sim", "en"]
        self._gpu = gpu
        self._reader: easyocr.Reader | None = None

        # 每个联系人的文字哈希缓存
        self._text_cache: dict[str, str] = {}

        logger.info(f"OCR 服务初始化: languages={self._languages}, gpu={self._gpu}")

    @property
    def reader(self) -> easyocr.Reader:
        """延迟加载 EasyOCR Reader"""
        if self._reader is None:
            import easyocr

            logger.info("正在加载 OCR 模型（首次加载可能需要几秒钟）...")
            self._reader = easyocr.Reader(
                self._languages,
                gpu=self._gpu,
                verbose=False,
            )
            logger.info("OCR 模型加载完成")
        return self._reader

    def extract_text(self, image: Image.Image) -> str:
        """从图片中提取文字

        Args:
            image: PIL Image 对象

        Returns:
            提取的文字，按从上到下顺序排列
        """
        total_start = time.time()

        # 转换为 numpy 数组
        convert_start = time.time()
        img_array = np.array(image)
        convert_time = (time.time() - convert_start) * 1000
        logger.debug(f"[OCR] 图片转换为 numpy 数组: {convert_time:.1f}ms, shape={img_array.shape}")

        # OCR 识别
        ocr_start = time.time()
        results = self.reader.readtext(img_array)
        ocr_time = (time.time() - ocr_start) * 1000
        logger.info(f"[OCR] EasyOCR 识别耗时: {ocr_time:.1f}ms, 识别到 {len(results)} 个文本块")

        # 按 y 坐标排序（从上到下）
        # results 格式: [(bbox, text, confidence), ...]
        # bbox 格式: [[x1,y1], [x2,y2], [x3,y3], [x4,y4]]
        sort_start = time.time()
        results.sort(key=lambda x: x[0][0][1])
        sort_time = (time.time() - sort_start) * 1000

        # 提取文字
        lines = [text for _, text, _ in results]
        total_time = (time.time() - total_start) * 1000

        logger.info(f"[OCR] 总耗时: {total_time:.1f}ms (转换={convert_time:.1f}ms, OCR={ocr_time:.1f}ms, 排序={sort_time:.1f}ms)")

        return "\n".join(lines)

    def extract_text_with_positions(
        self, image: Image.Image
    ) -> list[dict[str, any]]:
        """提取文字及其位置信息

        Args:
            image: PIL Image 对象

        Returns:
            包含文字和位置的列表 [{"text": str, "bbox": list, "confidence": float}, ...]
        """
        img_array = np.array(image)
        results = self.reader.readtext(img_array)

        # 按 y 坐标排序
        results.sort(key=lambda x: x[0][0][1])

        return [
            {
                "text": text,
                "bbox": bbox,
                "confidence": float(conf),
            }
            for bbox, text, conf in results
        ]

    def get_text_hash(self, text: str) -> str:
        """计算文字的哈希值"""
        # 标准化处理：去除空白字符差异
        normalized = "".join(text.split())
        return hashlib.md5(normalized.encode()).hexdigest()

    def _resize_for_detection(self, image: Image.Image) -> Image.Image:
        """缩小图片用于快速变化检测

        将图片缩小到 DETECT_MAX_SIZE，大幅提升 OCR 速度。
        因为只需要检测是否有变化，不需要精确识别内容。
        """
        width, height = image.size
        max_dim = max(width, height)

        if max_dim <= self.DETECT_MAX_SIZE:
            return image

        scale = self.DETECT_MAX_SIZE / max_dim
        new_width = int(width * scale)
        new_height = int(height * scale)

        return image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    def has_text_changed(
        self,
        contact: str,
        image: Image.Image,
    ) -> tuple[bool, str, str]:
        """检查联系人的聊天文字是否有变化

        使用缩小后的图片进行 OCR，大幅提升检测速度。
        因为只需判断是否有变化，不需要精确识别。

        Args:
            contact: 联系人名称
            image: 截图图片

        Returns:
            (是否有变化, 当前文字, 当前哈希)
        """
        # 缩小图片以加速 OCR（只用于变化检测）
        original_size = image.size
        small_image = self._resize_for_detection(image)
        small_size = small_image.size

        if original_size != small_size:
            logger.debug(
                f"[{contact}] 缩小图片用于检测: {original_size[0]}x{original_size[1]} -> "
                f"{small_size[0]}x{small_size[1]}"
            )

        current_text = self.extract_text(small_image)
        current_hash = self.get_text_hash(current_text)

        last_hash = self._text_cache.get(contact)

        if last_hash is None:
            # 首次识别
            self._text_cache[contact] = current_hash
            logger.debug(f"[{contact}] 首次 OCR 识别")
            return True, current_text, current_hash

        if last_hash == current_hash:
            # 文字无变化
            logger.debug(f"[{contact}] OCR 文字无变化")
            return False, current_text, current_hash

        # 有变化，更新缓存
        self._text_cache[contact] = current_hash
        logger.info(f"[{contact}] OCR 检测到文字变化")
        return True, current_text, current_hash

    def reset_cache(self, contact: str | None = None) -> None:
        """重置文字缓存

        Args:
            contact: 指定联系人，为 None 时重置所有
        """
        if contact is None:
            self._text_cache.clear()
            logger.info("已重置所有联系人的 OCR 缓存")
        elif contact in self._text_cache:
            del self._text_cache[contact]
            logger.info(f"已重置联系人 [{contact}] 的 OCR 缓存")

    def preload(self) -> None:
        """预加载 OCR 模型（可在启动时调用）"""
        _ = self.reader
