"""
core/office_com.py — Microsoft Office COM 封装

处理 Word / Excel / PPT 的自动化操作。
所有函数接收 Task 对象和 comtypes Application 对象。
"""

import os
from typing import Optional

from utils.logger import logger
from core.engine import Task


def word_to_pdf(task: Task, app) -> bool:
    """Word → PDF"""
    try:
        doc = app.Documents.Open(task.file_path)
        ultra = "Ultra" in task.quality
        doc.ExportAsFixedFormat(
            task.out_path,
            ExportFormat=17,  # pdf
            OptimizeFor=0,
            BitmapMissingFonts=ultra,
        )
        doc.Close(0)
        return True
    except Exception as e:
        logger.error(f"Word 转 PDF 失败: {e}")
        return False


def excel_to_pdf(task: Task, app) -> bool:
    """Excel → PDF"""
    try:
        wb = app.Workbooks.Open(task.file_path)
        kval = 0 if ("Ultra" in task.quality or "Standard" in task.quality) else 1
        wb.ExportAsFixedFormat(0, task.out_path, Quality=kval)
        wb.Close(0)
        return True
    except Exception as e:
        logger.error(f"Excel 转 PDF 失败: {e}")
        return False


def ppt_to_pdf(task: Task, app) -> bool:
    """PPT → PDF"""
    try:
        ppt = app.Presentations.Open(task.file_path, WithWindow=False)
        ppt.SaveAs(task.out_path, 32)  # ppSaveAsPDF
        ppt.Close()
        return True
    except Exception as e:
        logger.error(f"PPT 转 PDF 失败: {e}")
        return False


def word_to_txt(task: Task, app=None) -> bool:
    """Word → TXT (B4 新格式)"""
    import comtypes.client
    try:
        comtypes.client.CoInitialize()
        wdApp = comtypes.client.CreateObject("Word.Application")
        wdApp.Visible = False
        doc = wdApp.Documents.Open(task.file_path)
        content = doc.Range().Text
        with open(task.out_path, 'w', encoding='utf-8') as f:
            f.write(content)
        doc.Close(0)
        wdApp.Quit()
        comtypes.client.CoUninitialize()
        return True
    except Exception as e:
        logger.error(f"Word 转 TXT 失败: {e}")
        return False


def excel_to_csv(task: Task, app=None) -> bool:
    """Excel → CSV (B4 新格式)"""
    import comtypes.client
    try:
        comtypes.client.CoInitialize()
        xlApp = comtypes.client.CreateObject("Excel.Application")
        xlApp.Visible = False
        wb = xlApp.Workbooks.Open(task.file_path)
        # xlCSV = 6
        wb.SaveAs(task.out_path, FileFormat=6)
        wb.Close(0)
        xlApp.Quit()
        comtypes.client.CoUninitialize()
        return True
    except Exception as e:
        logger.error(f"Excel 转 CSV 失败: {e}")
        return False