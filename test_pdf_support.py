"""
test_pdf_support.py — PDF-only 论文支持的测试
"""

import shutil
import tempfile
import unittest
from pathlib import Path


class TestExtractArchivePdf(unittest.TestCase):
    """downloader: PDF 文件应当被直接保存，而非尝试解压"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_pdf_saved_to_extract_dir(self):
        """当 archive 是 PDF 时，应保存为 {stem}.pdf 到解压目录"""
        from downloader import extract_archive

        # 造一个最小 PDF（合法 PDF header）
        pdf_bytes = b"%PDF-1.4\n%%EOF\n"
        archive_path = self.tmp / "2505.03735.gz"
        archive_path.write_bytes(pdf_bytes)

        extract_dir = self.tmp / "2505.03735"
        extract_archive(archive_path, extract_dir)

        saved = extract_dir / "2505.03735.pdf"
        self.assertTrue(saved.exists(), "应当在解压目录下生成 .pdf 文件")
        self.assertEqual(saved.read_bytes(), pdf_bytes)

    def test_non_pdf_non_gzip_raises(self):
        """既不是 tar/gz 也不是 PDF 时，应抛出异常"""
        from downloader import extract_archive

        archive_path = self.tmp / "bad.gz"
        archive_path.write_bytes(b"THIS IS NOT VALID")

        extract_dir = self.tmp / "bad"
        with self.assertRaises(Exception):
            extract_archive(archive_path, extract_dir)


class TestFixPdfHeadings(unittest.TestCase):
    """converter: PDF 转出的 bold 标题应被规范化为 Markdown heading"""

    def setUp(self):
        from converter import fix_pdf_headings
        self.fix = fix_pdf_headings

    def test_top_level_section(self):
        md = "**1** **Introduction**\n\nSome text."
        result = self.fix(md)
        self.assertIn("# 1 Introduction", result)

    def test_subsection(self):
        md = "**2.1** **Related Works**\n\nContent."
        result = self.fix(md)
        self.assertIn("## 2.1 Related Works", result)

    def test_sub_subsection(self):
        md = "**3.1.2** **Details**\n\nContent."
        result = self.fix(md)
        self.assertIn("### 3.1.2 Details", result)

    def test_abstract_heading(self):
        md = "**Abstract**\n\nText."
        result = self.fix(md)
        self.assertIn("## Abstract", result)

    def test_references_heading(self):
        md = "**References**\n\nText."
        result = self.fix(md)
        self.assertIn("## References", result)

    def test_body_bold_unchanged(self):
        """正文中的加粗（非标题）不应被修改"""
        md = "Some **bold** text in the middle of a sentence."
        result = self.fix(md)
        self.assertIn("**bold**", result)


class TestConvertPdfFallback(unittest.TestCase):
    """converter.convert: 无 tex 文件时应自动走 PDF 转换路径"""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def test_convert_uses_pdf_when_no_tex(self):
        """paper_dir 中只有 PDF 时，convert 应生成 full_paper.md"""
        try:
            import pymupdf4llm  # noqa: F401
        except ImportError:
            self.skipTest("pymupdf4llm 未安装")

        from converter import convert

        # 用真实 PDF 测试：复制现有的测试 PDF
        real_pdf = Path("data/2505.03735.pdf")
        if not real_pdf.exists():
            self.skipTest("测试用 PDF 不存在")

        paper_dir = self.tmp / "2505.03735"
        paper_dir.mkdir()
        shutil.copy(real_pdf, paper_dir / "2505.03735.pdf")

        result = convert("2505.03735", data_dir=str(self.tmp))

        self.assertTrue(result.exists(), "full_paper.md 应当被生成")
        content = result.read_text(encoding="utf-8")
        self.assertGreater(len(content), 1000, "转换结果不应为空")
        # 应当包含正确的 Markdown 标题
        self.assertIn("# 1 Introduction", content)


if __name__ == "__main__":
    unittest.main()
