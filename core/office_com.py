"""
core/office_com.py — Microsoft Office COM 封装

处理 Word / Excel / PPT 的自动化操作。
所有函数接收 Task 对象和 comtypes Application 对象。
"""

import os

from utils.logger import logger
from core.engine import Task


def _prepare_office_task(task: Task, app, app_name: str) -> bool:
    """检查 Office 实例和输出目录，并写入可展示的错误信息。"""
    if app is None:
        task.error = f"无法启动 Microsoft {app_name}，请确认已安装桌面版 Office"
        logger.error(task.error)
        return False
    os.makedirs(os.path.dirname(os.path.abspath(task.out_path)), exist_ok=True)
    return True


def word_to_pdf(task: Task, app) -> bool:
    """Word → PDF"""
    if not _prepare_office_task(task, app, "Word"):
        return False
    doc = None
    try:
        doc = app.Documents.Open(os.path.abspath(task.file_path), ReadOnly=True)
        ultra = "Ultra" in task.quality
        optimize_for = 1 if "Speed" in task.quality else 0
        doc.ExportAsFixedFormat(
            os.path.abspath(task.out_path),
            ExportFormat=17,  # pdf
            OptimizeFor=optimize_for,
            BitmapMissingFonts=ultra,
        )
        return True
    except Exception as e:
        task.error = f"Word 转 PDF 失败: {e}"
        logger.error(task.error)
        return False
    finally:
        if doc is not None:
            try:
                doc.Close(0)
            except Exception:
                pass


def excel_to_pdf(task: Task, app) -> bool:
    """Excel → PDF"""
    if not _prepare_office_task(task, app, "Excel"):
        return False
    wb = None
    try:
        wb = app.Workbooks.Open(
            os.path.abspath(task.file_path),
            UpdateLinks=0,
            ReadOnly=True,
        )
        kval = 0 if ("Ultra" in task.quality or "Standard" in task.quality) else 1
        wb.ExportAsFixedFormat(
            Type=0,
            Filename=os.path.abspath(task.out_path),
            Quality=kval,
            IncludeDocProperties=True,
            IgnorePrintAreas=False,
            OpenAfterPublish=False,
        )
        return True
    except Exception as e:
        task.error = f"Excel 转 PDF 失败: {e}"
        logger.error(task.error)
        return False
    finally:
        if wb is not None:
            try:
                wb.Close(False)
            except Exception:
                pass


def ppt_to_pdf(task: Task, app) -> bool:
    """PPT → PDF"""
    if not _prepare_office_task(task, app, "PowerPoint"):
        return False
    ppt = None
    try:
        ppt = app.Presentations.Open(os.path.abspath(task.file_path), WithWindow=False)
        ppt.SaveAs(os.path.abspath(task.out_path), 32)  # ppSaveAsPDF
        return True
    except Exception as e:
        task.error = f"PPT 转 PDF 失败: {e}"
        logger.error(task.error)
        return False
    finally:
        if ppt is not None:
            try:
                ppt.Close()
            except Exception:
                pass


def word_to_txt(task: Task, app=None) -> bool:
    """Word → UTF-8 TXT。Office 实例由工作线程统一管理。"""
    if not _prepare_office_task(task, app, "Word"):
        return False
    doc = None
    try:
        doc = app.Documents.Open(os.path.abspath(task.file_path), ReadOnly=True)
        content = doc.Range().Text
        # Word 使用 \r 和表格结束符 \x07；转换为普通文本换行。
        content = content.replace("\r\x07", "\n").replace("\x07", "")
        content = content.replace("\r", "\n")
        with open(task.out_path, "w", encoding="utf-8-sig", newline="") as stream:
            stream.write(content)
        return True
    except Exception as e:
        task.error = f"Word 转 TXT 失败: {e}"
        logger.error(task.error)
        return False
    finally:
        if doc is not None:
            try:
                doc.Close(0)
            except Exception:
                pass


def excel_to_csv(task: Task, app=None) -> bool:
    """Excel → UTF-8 CSV。Office 实例由工作线程统一管理。"""
    if not _prepare_office_task(task, app, "Excel"):
        return False
    wb = None
    try:
        wb = app.Workbooks.Open(
            os.path.abspath(task.file_path),
            UpdateLinks=0,
            ReadOnly=True,
        )
        wb.SaveAs(os.path.abspath(task.out_path), FileFormat=62)  # xlCSVUTF8
        return True
    except Exception as e:
        task.error = f"Excel 转 CSV 失败: {e}"
        logger.error(task.error)
        return False
    finally:
        if wb is not None:
            try:
                wb.Close(False)
            except Exception:
                pass
