import os
import tempfile
import unittest

from core.formats import FormatCache, get_conversion_mode, get_target_formats


class FormatCacheTests(unittest.TestCase):
    def test_source_and_target_selection_maps_to_internal_mode(self):
        self.assertEqual(get_conversion_mode("Word", "TXT"), "Word 转 TXT")
        self.assertEqual(get_conversion_mode("PDF", "PDF（压缩）"), "PDF 压缩")
        self.assertEqual(
            get_target_formats("Excel"),
            ["PDF", "CSV"],
        )

    def test_pdf_compression_never_overwrites_source(self):
        cache = FormatCache()
        cache.set_mode("PDF 压缩")

        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "document.pdf")
            open(source, "wb").close()
            output = cache.get_output_path(source)

            self.assertNotEqual(os.path.normcase(source), os.path.normcase(output))
            self.assertTrue(output.endswith("document_compressed.pdf"))
            self.assertTrue(cache.uses_quality())

    def test_existing_output_gets_incremented_name(self):
        cache = FormatCache()
        cache.set_mode("PDF 合并")

        with tempfile.TemporaryDirectory() as folder:
            source = os.path.join(folder, "document.pdf")
            existing = os.path.join(folder, "document_merged.pdf")
            open(source, "wb").close()
            open(existing, "wb").close()

            self.assertTrue(
                cache.get_output_path(source).endswith("document_merged_1.pdf")
            )

    def test_quality_is_disabled_for_modes_that_ignore_it(self):
        cache = FormatCache()
        cache.set_mode("Word 转 TXT")
        self.assertFalse(cache.uses_quality())

    def test_switching_modes_does_not_mutate_global_extensions(self):
        cache = FormatCache()
        cache.set_mode("PDF 转 TXT")
        self.assertEqual(cache.exts_in, [".pdf"])
        cache.set_mode("Word 转 TXT")
        cache.set_mode("PDF 转 TXT")
        self.assertEqual(cache.exts_in, [".pdf"])

    def test_same_named_inputs_get_distinct_reserved_outputs(self):
        cache = FormatCache()
        cache.set_mode("Word 转 PDF")

        with tempfile.TemporaryDirectory() as folder:
            source_a = os.path.join(folder, "a", "document.docx")
            source_b = os.path.join(folder, "b", "document.docx")
            output_folder = os.path.join(folder, "output")
            os.makedirs(os.path.dirname(source_a))
            os.makedirs(os.path.dirname(source_b))
            open(source_a, "wb").close()
            open(source_b, "wb").close()
            reserved = set()

            output_a = cache.get_output_path(
                source_a, output_folder, True, reserved,
            )
            output_b = cache.get_output_path(
                source_b, output_folder, True, reserved,
            )
            self.assertNotEqual(output_a, output_b)
            self.assertTrue(output_b.endswith("document_1.pdf"))


if __name__ == "__main__":
    unittest.main()
