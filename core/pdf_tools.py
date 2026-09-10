"""
core/pdf_tools.py — PDF 相关转换（PyMuPDF / pdf2docx / ReportLab）

转换函数签名: func(task: Task, app=None) -> bool
"""

import os
from typing import Optional

import fitz  # PyMuPDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

from utils.logger import logger
from core.engine import Task
from core.font_detector import get_current_font


def pdf_to_word(task: Task, app=None) -> bool:
    """PDF → Word（使用 pdf2docx）"""
    try:
        from pdf2docx import Converter
        cv = Converter(task.file_path)
        cv.convert(task.out_path)
        cv.close()
        return True
    except Exception as e:
        logger.error(f"PDF 转 Word 失败: {e}")
        return False


def pdf_to_images(task: Task, app=None) -> bool:
    """PDF → 图片（每页提取）"""
    try:
        if "Ultra" in task.quality:
            mat_val, res = 3, 100
        elif "Standard" in task.quality:
            mat_val, res = 2, 90
        else:
            mat_val, res = 1, 70

        doc = fitz.open(task.file_path)
        matrix = fitz.Matrix(mat_val, mat_val)
        for idx, page in enumerate(doc):
            pix = page.get_pixmap(matrix=matrix)
            page_path = os.path.join(task.out_path, f"{idx + 1}.png")
            pix.save(page_path)
        doc.close()
        return True
    except Exception as e:
        logger.error(f"PDF 转图片失败: {e}")
        return False


def pdf_to_txt(task: Task, app=None) -> bool:
    """PDF → TXT"""
    try:
        doc = fitz.open(task.file_path)
        with open(task.out_path, 'w', encoding='utf-8') as f:
            for page in doc:
                f.write(page.get_text())
        doc.close()
        return True
    except Exception as e:
        logger.error(f"PDF 转 TXT 失败: {e}")
        return False


def txt_to_pdf(task: Task, app=None) -> bool:
    """TXT → PDF（ReportLab 手绘）"""
    try:
        c = canvas.Canvas(task.out_path, pagesize=A4)
        h = A4[1]
        font_name = get_current_font()
        try:
            with open(task.file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            with open(task.file_path, 'r', encoding='gbk') as f:
                lines = f.readlines()

        y = h - 40
        c.setFont(font_name, 10)
        for line in lines:
            if y < 40:
                c.showPage()
                y = h - 40
                c.setFont(font_name, 10)
            c.drawString(40, y, line.rstrip('\n\r'))
            y -= 15
        c.save()
        return True
    except Exception as e:
        logger.error(f"TXT 转 PDF 失败: {e}")
        return False


def pdf_merge(task: Task, app=None) -> bool:
    """
    PDF 合并 (B4)
    注意：此函数会从 task 上下文中读取所有待合并的 PDF 路径。
    task 为多文件任务的最后一个文件，合并列表通过 engine 传递。
    实际调用时由 engine 的合并逻辑包装。
    """
    # 合并由 engine 中的 _do_pdf_merge 处理
    # 此保留以供直接调用
    return False


def pdf_compress(task: Task, app=None) -> bool:
    """PDF 压缩 (B4) — 降低图片 DPI 重编码"""
    try:
        doc = fitz.open(task.file_path)
        out_doc = fitz.open()

        for page_num in range(len(doc)):
            page = doc[page_num]
            # 按质量引擎决定 DPI
            if "Ultra" in task.quality:
                zoom = 1.5
            elif "Standard" in task.quality:
                zoom = 1.0
            else:
                zoom = 0.5

            pix = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            new_page = out_doc.new_page(width=pix.width, height=pix.height)
            new_page.insert_image(new_page.rect, pixmap=pix)

        out_doc.save(task.out_path, deflate=True, garbage=4)
        out_doc.close()
        doc.close()

        # 检查是否确实变小了
        orig_size = os.path.getsize(task.file_path)
        new_size = os.path.getsize(task.out_path)
        ratio = new_size / orig_size * 100 if orig_size > 0 else 0
        logger.info(f"PDF 压缩: {orig_size//1024}KB → {new_size//1024}KB ({ratio:.0f}%)")

        return True
    except Exception as e:
        logger.error(f"PDF 压缩失败: {e}")
        return False