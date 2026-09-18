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
            res, jpeg_quality = 300, 95
        elif "Standard" in task.quality:
            res, jpeg_quality = 150, 85
        else:
            res, jpeg_quality = 96, 70

        with Image.open(task.file_path) as img:
            if img.mode != 'RGB':
                img = img.convert('RGB')
            img.save(
                task.out_path,
                "PDF",
                resolution=res,
                quality=jpeg_quality,
                optimize=True,
            )
        return True
    except Exception as e:
        task.error = f"图片转 PDF 失败: {e}"
        logger.error(task.error)
        return False


def image_merge_pdf(task: Task, app=None) -> bool:
    """将 ``task.input_files`` 中的图片按顺序合并为 PDF。"""
    images = []
    try:
        supported = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}
        image_paths = [
            path for path in task.input_files
            if ext_lower(path) in supported
        ]
        if not image_paths:
            task.error = "没有可合并的图片文件"
            logger.error(task.error)
            return False

        for image_path in image_paths:
            with Image.open(image_path) as source:
                images.append(source.convert("RGB"))

        images[0].save(
            task.out_path,
            "PDF",
            save_all=True,
            append_images=images[1:],
            resolution=150,
            quality=85,
            optimize=True,
        )
        logger.info(f"合并 {len(images)} 张图片 → {task.out_path}")
        return True
    except Exception as e:
        task.error = f"图片合并 PDF 失败: {e}"
        logger.error(task.error)
        return False
    finally:
        for image in images:
            image.close()


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
        task.error = f"图片格式转换失败: {e}"
        logger.error(task.error)
        return False
