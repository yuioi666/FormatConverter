import os
import tempfile
import unittest

from core.engine import Task
from core.office_com import excel_to_pdf, word_to_txt


def make_task(source: str, output: str, mode: str) -> Task:
    return Task(
        iid="1",
        file_path=source,
        mode=mode,
        quality="标准均衡 (Standard)",
        out_path=output,
        need_delete=False,
    )


class FakeRange:
    Text = "第一段\r第二段\r\x07"


class FakeDocument:
    def __init__(self):
        self.closed = False

    def Range(self):
        return FakeRange()

    def Close(self, *_args):
        self.closed = True


class FakeDocuments:
    def __init__(self):
        self.document = FakeDocument()

    def Open(self, *_args, **_kwargs):
        return self.document


class FakeWordApp:
    def __init__(self):
        self.Documents = FakeDocuments()


class FakeWorkbook:
    def __init__(self):
        self.export_kwargs = None
        self.closed = False

    def ExportAsFixedFormat(self, **kwargs):
        self.export_kwargs = kwargs

    def Close(self, *_args):
        self.closed = True


class FakeWorkbooks:
    def __init__(self):
        self.workbook = FakeWorkbook()

    def Open(self, *_args, **_kwargs):
        return self.workbook


class FakeExcelApp:
    def __init__(self):
        self.Workbooks = FakeWorkbooks()


class OfficeConversionTests(unittest.TestCase):
    def test_word_to_txt_uses_shared_word_instance(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "input.docx")
            output = os.path.join(folder, "output.txt")
            open(source, "wb").close()
            app = FakeWordApp()

            self.assertTrue(word_to_txt(
                make_task(source, output, "Word 转 TXT"), app,
            ))
            with open(output, "r", encoding="utf-8-sig") as stream:
                self.assertEqual(stream.read(), "第一段\n第二段\n")
            self.assertTrue(app.Documents.document.closed)

    def test_excel_to_pdf_uses_export_api_and_closes_workbook(self):
        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "input.xlsx")
            output = os.path.join(folder, "output.pdf")
            open(source, "wb").close()
            app = FakeExcelApp()

            self.assertTrue(excel_to_pdf(
                make_task(source, output, "Excel 转 PDF"), app,
            ))
            workbook = app.Workbooks.workbook
            self.assertEqual(workbook.export_kwargs["Type"], 0)
            self.assertEqual(workbook.export_kwargs["Quality"], 0)
            self.assertTrue(workbook.closed)

    def test_missing_office_instance_reports_actionable_error(self):
        task = make_task("missing.xlsx", "output.pdf", "Excel 转 PDF")
        self.assertFalse(excel_to_pdf(task, None))
        self.assertIn("Microsoft Excel", task.error)


if __name__ == "__main__":
    unittest.main()
