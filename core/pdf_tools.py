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
    cv = None
    try:
        from pdf2docx import Converter
        cv = Converter(task.file_path)
        cv.convert(task.out_path)
        return True
    except Exception as e:
        task.error = f"PDF 转 Word 失败: {e}"
        logger.error(task.error)
        return False
    finally:
        if cv is not None:
            try:
                cv.close()
            except Exception:
                pass


def pdf_to_images(task: Task, app=None) -> bool:
    """PDF → 图片（每页提取）"""
    try:
        if "Ultra" in task.quality:
            mat_val = 3
        elif "Standard" in task.quality:
            mat_val = 2
        else:
            mat_val = 1

        os.makedirs(task.out_path, exist_ok=True)
        with fitz.open(task.file_path) as doc:
            matrix = fitz.Matrix(mat_val, mat_val)
            for idx, page in enumerate(doc):
                pix = page.get_pixmap(matrix=matrix, alpha=False)
                page_path = os.path.join(task.out_path, f"{idx + 1}.png")
                pix.save(page_path)
        return True
    except Exception as e:
        task.error = f"PDF 转图片失败: {e}"
        logger.error(task.error)
        return False


def pdf_to_txt(task: Task, app=None) -> bool:
    """PDF → TXT"""
    try:
        with fitz.open(task.file_path) as doc:
            with open(task.out_path, 'w', encoding='utf-8-sig') as f:
                for page in doc:
                    f.write(page.get_text())
        return True
    except Exception as e:
        task.error = f"PDF 转 TXT 失败: {e}"
        logger.error(task.error)
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
        task.error = f"TXT 转 PDF 失败: {e}"
        logger.error(task.error)
        return False


def pdf_merge(task: Task, app=None) -> bool:
    """将 ``task.input_files`` 中的 PDF 按顺序合并。"""
    out_doc = None
    try:
        pdf_paths = [
            path for path in task.input_files
            if path.lower().endswith(".pdf")
        ]
        if not pdf_paths:
            task.error = "没有可合并的 PDF 文件"
            logger.error(task.error)
            return False

        out_doc = fitz.open()
        for pdf_path in pdf_paths:
            with fitz.open(pdf_path) as source:
                out_doc.insert_pdf(source)
        out_doc.save(task.out_path, deflate=True)
        logger.info(f"合并 {len(pdf_paths)} 个 PDF → {task.out_path}")
        return True
    except Exception as e:
        task.error = f"PDF 合并失败: {e}"
        logger.error(task.error)
        return False
    finally:
        if out_doc is not None:
            out_doc.close()


def pdf_compress(task: Task, app=None) -> bool:
    """PDF 压缩 (B4) — 降低图片 DPI 重编码"""
    doc = None
    out_doc = None
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
        out_doc = None
        doc.close()
        doc = None

        # 检查是否确实变小了
        orig_size = os.path.getsize(task.file_path)
        new_size = os.path.getsize(task.out_path)
        ratio = new_size / orig_size * 100 if orig_size > 0 else 0
        logger.info(f"PDF 压缩: {orig_size//1024}KB → {new_size//1024}KB ({ratio:.0f}%)")

        return True
    except Exception as e:
        task.error = f"PDF 压缩失败: {e}"
        logger.error(task.error)
        return False
    finally:
        if out_doc is not None:
            out_doc.close()
        if doc is not None:
            doc.close()
