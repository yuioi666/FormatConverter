"""
core/image_tools.py — 图片相关转换（PIL）

转换函数签名: func(task: Task, app=None) -> bool
"""

import os
from typing import Optional

from PIL import Image

from utils.logger import logger
from core.engine import Task
from utils.helpers import ext_lower


def image_to_pdf(task: Task, app=None) -> bool:
    """单张图片 → PDF"""
    try:
        if "Ultra" in task.quality:
            res = 100
        elif "Standard" in task.quality:
            res = 90
        else:
            res = 70

        with Image.open(task.file_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(task.out_path, "PDF", resolution=res)
        return True
    except Exception as e:
        logger.error(f"图片转 PDF 失败: {e}")
        return False


def image_merge_pdf(task: Task, app=None) -> bool:
    """
    多张图片合并为同一 PDF (B4)
    由 engine 的合并逻辑调用，task.file_path 此时为特殊标记。
    实际实现在 engine 层。
    """
    return False


def image_convert(task: Task, app=None) -> bool:
    """图片格式互转 (B4) — PNG ↔ JPG ↔ BMP ↔ WebP"""
    try:
        with Image.open(task.file_path) as img:
            ext = ext_lower(task.out_path)

            if ext == '.jpg' or ext == '.jpeg':
                if img.mode in ('RGBA', 'P', 'LA'):
                    img = img.convert('RGB')
                img.save(task.out_path, "JPEG", quality=90)
            elif ext == '.png':
                img.save(task.out_path, "PNG")
            elif ext == '.bmp':
                img.save(task.out_path, "BMP")
            elif ext == '.webp':
                img.save(task.out_path, "WebP", quality=85)
            else:
                img.save(task.out_path)

        return True
    except Exception as e:
        logger.error(f"图片格式转换失败: {e}")
        return False