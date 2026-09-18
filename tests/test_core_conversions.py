import os
import tempfile
import unittest

import fitz
from PIL import Image

from core.engine import Task
from core.image_tools import image_convert, image_merge_pdf, image_to_pdf
from core.pdf_tools import (
    pdf_compress,
    pdf_merge,
    pdf_to_images,
    pdf_to_txt,
    pdf_to_word,
    txt_to_pdf,
)


def make_task(source, output, mode, input_files=None):
    return Task(
        iid=mode,
        file_path=source,
        mode=mode,
        quality="标准均衡 (Standard)",
        out_path=output,
        need_delete=False,
        input_files=input_files,
    )


def create_pdf(path, text):
    with fitz.open() as document:
        page = document.new_page()
        page.insert_text((72, 72), text)
        document.save(path)


class CoreConversionTests(unittest.TestCase):
    def test_pdf_text_images_merge_and_compress(self):
        with tempfile.TemporaryDirectory() as folder:
            first = os.path.join(folder, "first.pdf")
            second = os.path.join(folder, "second.pdf")
            create_pdf(first, "First PDF")
            create_pdf(second, "Second PDF")

            text_output = os.path.join(folder, "first.txt")
            self.assertTrue(pdf_to_txt(
                make_task(first, text_output, "PDF 转 TXT"),
            ))
            with open(text_output, encoding="utf-8-sig") as stream:
                self.assertIn("First PDF", stream.read())

            word_output = os.path.join(folder, "first.docx")
            self.assertTrue(pdf_to_word(
                make_task(first, word_output, "PDF 转 Word"),
            ))
            self.assertGreater(os.path.getsize(word_output), 0)

            image_folder = os.path.join(folder, "images")
            self.assertTrue(pdf_to_images(
                make_task(first, image_folder, "PDF 转 图片"),
            ))
            self.assertTrue(os.path.isfile(os.path.join(image_folder, "1.png")))

            merged = os.path.join(folder, "merged.pdf")
            self.assertTrue(pdf_merge(make_task(
                first, merged, "PDF 合并", [first, second],
            )))
            with fitz.open(merged) as document:
                self.assertEqual(document.page_count, 2)

            compressed = os.path.join(folder, "compressed.pdf")
            self.assertTrue(pdf_compress(
                make_task(first, compressed, "PDF 压缩"),
            ))
            with fitz.open(compressed) as document:
                self.assertEqual(document.page_count, 1)

    def test_text_and_image_conversions(self):
        with tempfile.TemporaryDirectory() as folder:
            text_source = os.path.join(folder, "input.txt")
            with open(text_source, "w", encoding="utf-8") as stream:
                stream.write("FormatConverter text test")
            text_pdf = os.path.join(folder, "text.pdf")
            self.assertTrue(txt_to_pdf(
                make_task(text_source, text_pdf, "TXT 转 PDF"),
            ))
            with fitz.open(text_pdf) as document:
                self.assertEqual(document.page_count, 1)

            first_image = os.path.join(folder, "first.png")
            second_image = os.path.join(folder, "second.jpg")
            Image.new("RGB", (80, 60), "red").save(first_image)
            Image.new("RGB", (80, 60), "blue").save(second_image)

            image_pdf = os.path.join(folder, "image.pdf")
            self.assertTrue(image_to_pdf(
                make_task(first_image, image_pdf, "图片 转 PDF"),
            ))
            with fitz.open(image_pdf) as document:
                self.assertEqual(document.page_count, 1)

            converted = os.path.join(folder, "converted.png")
            self.assertTrue(image_convert(
                make_task(second_image, converted, "图片格式转换"),
            ))
            with Image.open(converted) as image:
                self.assertEqual(image.format, "PNG")

            merged = os.path.join(folder, "images.pdf")
            self.assertTrue(image_merge_pdf(make_task(
                first_image,
                merged,
                "图片 合并 PDF",
                [first_image, second_image],
            )))
            with fitz.open(merged) as document:
                self.assertEqual(document.page_count, 2)


if __name__ == "__main__":
    unittest.main()
