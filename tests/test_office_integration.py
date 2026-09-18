"""可选的 Microsoft Office 实机集成测试。

运行：
    $env:FORMATCONVERTER_OFFICE_TESTS = "1"
    python -m unittest tests.test_office_integration -v
"""

import os
import tempfile
import threading
import unittest

import comtypes
import comtypes.client
import fitz

from core.engine import ConversionEngine, Task
from core.office_com import (
    excel_to_csv,
    excel_to_pdf,
    ppt_to_pdf,
    word_to_pdf,
    word_to_txt,
)


OFFICE_TESTS_ENABLED = os.environ.get("FORMATCONVERTER_OFFICE_TESTS") == "1"


def make_task(source: str, output: str, mode: str) -> Task:
    return Task(
        iid=mode,
        file_path=source,
        mode=mode,
        quality="标准均衡 (Standard)",
        out_path=output,
        need_delete=False,
    )


@unittest.skipUnless(OFFICE_TESTS_ENABLED, "需要显式启用本机 Office 测试")
class OfficeIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        comtypes.CoInitialize()

    def tearDown(self):
        comtypes.CoUninitialize()
        self.temp_dir.cleanup()

    def run_engine_task(self, engine, task, timeout=30):
        finished = threading.Event()
        failures = []
        engine.callbacks.on_fail = lambda _task, reason: failures.append(reason)
        engine.callbacks.on_finish = finished.set
        self.assertTrue(engine.start([task]))
        self.assertTrue(finished.wait(timeout), "Office 转换超时")
        self.assertFalse(failures, failures[0] if failures else "")

    def test_word_to_txt_and_pdf(self):
        creator = comtypes.client.CreateObject("Word.Application")
        creator.Visible = False
        creator.DisplayAlerts = False
        try:
            source = os.path.join(self.temp_dir.name, "word-input.docx")
            txt_output = os.path.join(self.temp_dir.name, "word-output.txt")
            pdf_output = os.path.join(self.temp_dir.name, "word-output.pdf")

            document = creator.Documents.Add()
            document.Content.Text = "FormatConverter Office integration test"
            document.SaveAs2(source, FileFormat=16)  # wdFormatDocumentDefault
            document.Close(0)
        finally:
            creator.Quit()

        engine = ConversionEngine()
        engine.set_converter_funcs({
            "Word 转 TXT": word_to_txt,
            "Word 转 PDF": word_to_pdf,
        })
        self.run_engine_task(
            engine, make_task(source, txt_output, "Word 转 TXT"),
        )
        with open(txt_output, encoding="utf-8-sig") as stream:
            self.assertIn(
                "FormatConverter Office integration test",
                stream.read(),
            )

        self.run_engine_task(
            engine, make_task(source, pdf_output, "Word 转 PDF"),
        )
        with fitz.open(pdf_output) as pdf:
            self.assertGreaterEqual(pdf.page_count, 1)

    def test_excel_to_pdf(self):
        creator = comtypes.client.CreateObject("Excel.Application")
        creator.Visible = False
        creator.DisplayAlerts = False
        try:
            source = os.path.join(self.temp_dir.name, "excel-input.xlsx")
            output = os.path.join(self.temp_dir.name, "excel-output.pdf")
            csv_output = os.path.join(self.temp_dir.name, "excel-output.csv")

            workbook = creator.Workbooks.Add()
            sheet = workbook.Worksheets(1)
            sheet.Cells.Item(1, 1).Value2 = "FormatConverter"
            sheet.Cells.Item(2, 1).Value2 = "Excel integration test"
            workbook.SaveAs(source, FileFormat=51)  # xlOpenXMLWorkbook
            workbook.Close(False)
        finally:
            creator.Quit()

        engine = ConversionEngine()
        engine.set_converter_funcs({
            "Excel 转 PDF": excel_to_pdf,
            "Excel 转 CSV": excel_to_csv,
        })
        self.run_engine_task(
            engine, make_task(source, output, "Excel 转 PDF"),
        )
        with fitz.open(output) as pdf:
            self.assertGreaterEqual(pdf.page_count, 1)

        self.run_engine_task(
            engine, make_task(source, csv_output, "Excel 转 CSV"),
        )
        with open(csv_output, encoding="utf-8-sig") as stream:
            self.assertIn("FormatConverter", stream.read())

    def test_powerpoint_to_pdf(self):
        creator = comtypes.client.CreateObject("PowerPoint.Application")
        try:
            source = os.path.join(self.temp_dir.name, "slides-input.pptx")
            output = os.path.join(self.temp_dir.name, "slides-output.pdf")

            presentation = creator.Presentations.Add(WithWindow=False)
            slide = presentation.Slides.Add(1, 12)  # ppLayoutBlank
            text_box = slide.Shapes.AddTextbox(1, 50, 50, 500, 80)
            text_box.TextFrame.TextRange.Text = "FormatConverter PowerPoint test"
            presentation.SaveAs(source, 24)  # ppSaveAsOpenXMLPresentation
            presentation.Close()
        finally:
            creator.Quit()

        engine = ConversionEngine()
        engine.set_converter_funcs({"PPT 转 PDF": ppt_to_pdf})
        self.run_engine_task(
            engine, make_task(source, output, "PPT 转 PDF"),
        )
        with fitz.open(output) as pdf:
            self.assertGreaterEqual(pdf.page_count, 1)


if __name__ == "__main__":
    unittest.main()
